"""Core analyzer that evaluates dependencies and determines actions.

Purpose
-------
Orchestrate the dependency analysis pipeline: parse the pyproject.toml,
extract dependencies, resolve versions, and determine actions for each
dependency per Python version.

Contents
--------
* :func:`analyze_pyproject` - Main API function for analyzing a pyproject.toml
* :func:`determine_action` - Determine the action for a dependency
* :class:`Analyzer` - Stateful analyzer with caching

System Role
-----------
The central component that coordinates all other modules to produce
the final analysis results. This is the main entry point for the library.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

from .dependency_extractor import extract_dependencies, get_requires_python, load_pyproject
from .index_resolver import IndexResolver, detect_configured_indexes
from .models import (
    Action,
    AnalysisResult,
    CompatibilityStatus,
    DependencyInfo,
    EnrichedAnalysisResult,
    EnrichedEntry,
    EnrichedSummary,
    IndexInfo,
    IndexType,
    OutdatedEntry,
    PyPIMetadata,
    PythonVersion,
    VersionStatus,
)
from .python_version_parser import parse_requires_python
from .repo_resolver import RepoResolver
from .schemas import PyprojectSchema
from .version_resolver import VersionResolver, VersionResult

logger = logging.getLogger(__name__)

# Precompiled regex patterns for version constraint parsing
_RE_VERSION_GE = re.compile(r">=\s*([0-9][0-9a-zA-Z._-]*)")
_RE_VERSION_EQ = re.compile(r"==\s*([0-9][0-9a-zA-Z._-]*)")
_RE_VERSION_COMPAT = re.compile(r"~=\s*([0-9][0-9a-zA-Z._-]*)")
_RE_VERSION_BARE = re.compile(r"^([0-9][0-9a-zA-Z._-]*)$")
_RE_NUMERIC_PARTS = re.compile(r"\d+")

# Precompiled regex patterns for Python version markers
_RE_MARKER_LT = re.compile(r"python_version\s*<\s*['\"]?(\d+\.\d+)['\"]?")
_RE_MARKER_LE = re.compile(r"python_version\s*<=\s*['\"]?(\d+\.\d+)['\"]?")
_RE_MARKER_GT = re.compile(r"python_version\s*>\s*['\"]?(\d+\.\d+)['\"]?")
_RE_MARKER_GE = re.compile(r"python_version\s*>=\s*['\"]?(\d+\.\d+)['\"]?")
_RE_MARKER_EQ = re.compile(r"python_version\s*==\s*['\"]?(\d+\.\d+)['\"]?")
_RE_MARKER_NE = re.compile(r"python_version\s*!=\s*['\"]?(\d+\.\d+)['\"]?")


@lru_cache(maxsize=512)
def _parse_version_constraint_minimum(constraints: str) -> str | None:
    """Extract the minimum version from a constraint string.

    Args:
        constraints: Version constraints like ">=1.0,<2.0" or "^1.5.0".

    Returns:
        The minimum version specified, or None if unparseable.
    """
    if not constraints:
        return None

    # Handle Poetry ^ operator (compatible release)
    if constraints.startswith("^"):
        return constraints[1:].split(",")[0].strip()

    # Handle ~ operator (compatible release)
    if constraints.startswith("~"):
        return constraints[1:].split(",")[0].strip()

    # Look for >= or == as minimum version
    for pattern in (_RE_VERSION_GE, _RE_VERSION_EQ, _RE_VERSION_COMPAT):
        match = pattern.search(constraints)
        if match:
            return match.group(1)

    # If just a version number, that's the minimum
    version_match = _RE_VERSION_BARE.match(constraints.strip())
    if version_match:
        return version_match.group(1)

    return None


@lru_cache(maxsize=512)
def _version_tuple(version: str) -> tuple[int, ...]:
    """Convert version string to tuple for comparison.

    Args:
        version: Version string like "1.2.3".

    Returns:
        Tuple of version components.
    """
    # Extract numeric parts, ignoring pre-release suffixes
    parts = _RE_NUMERIC_PARTS.findall(version.split("-")[0].split("+")[0])
    return tuple(int(p) for p in parts) if parts else (0,)


def _version_is_greater(v1: str, v2: str) -> bool:
    """Check if v1 is greater than v2.

    Args:
        v1: First version string.
        v2: Second version string.

    Returns:
        True if v1 > v2.
    """
    return _version_tuple(v1) > _version_tuple(v2)


def _dependency_applies_to_python_version(
    dep: DependencyInfo,
    python_version: PythonVersion,
) -> bool:
    """Check if a dependency applies to a specific Python version."""
    if not dep.python_markers:
        return True

    marker = dep.python_markers.strip()
    patterns = _get_marker_patterns(python_version)

    for pattern, evaluator in patterns:
        result = _try_evaluate_marker(pattern, evaluator, marker)
        if result is not None:
            return result

    # If we can't parse the marker, assume it applies
    return True


def _get_marker_patterns(
    python_version: PythonVersion,
) -> list[tuple[re.Pattern[str], Callable[[str], bool]]]:
    """Get marker patterns and their evaluators for a Python version."""
    return [
        (_RE_MARKER_LT, lambda m: python_version < PythonVersion.from_string(m)),
        (_RE_MARKER_LE, lambda m: python_version <= PythonVersion.from_string(m)),
        (_RE_MARKER_GT, lambda m: python_version > PythonVersion.from_string(m)),
        (_RE_MARKER_GE, lambda m: python_version >= PythonVersion.from_string(m)),
        (_RE_MARKER_EQ, lambda m: python_version == PythonVersion.from_string(m)),
        (_RE_MARKER_NE, lambda m: python_version != PythonVersion.from_string(m)),
    ]


def _try_evaluate_marker(
    pattern: re.Pattern[str],
    evaluator: Callable[[str], bool],
    marker: str,
) -> bool | None:
    """Try to evaluate a marker pattern, returning None if it doesn't match."""
    match = pattern.search(marker)
    if not match:
        return None
    try:
        return evaluator(match.group(1))
    except ValueError:
        return None


def _determine_git_action(
    dep: DependencyInfo,
    version_result: VersionResult,
) -> tuple[Action, str | None, str | None]:
    """Determine action for a git dependency."""
    if version_result.is_unknown:
        return Action.CHECK_MANUALLY, dep.git_ref, VersionStatus.UNKNOWN.value

    current = dep.git_ref
    latest = version_result.latest_version
    if latest and current and _version_is_greater(latest, current):
        return Action.UPDATE, current, latest

    return Action.CHECK_MANUALLY, current, latest


def _determine_pypi_action(
    dep: DependencyInfo,
    version_result: VersionResult,
) -> tuple[Action, str | None, str | None]:
    """Determine action for a PyPI dependency."""
    current_version = _parse_version_constraint_minimum(dep.version_constraints)
    latest_version = version_result.latest_version

    if version_result.is_unknown or latest_version is None:
        return Action.CHECK_MANUALLY, current_version, VersionStatus.UNKNOWN.value

    if current_version is None:
        return Action.NONE, None, latest_version

    if _version_is_greater(latest_version, current_version):
        return Action.UPDATE, current_version, latest_version

    return Action.NONE, current_version, latest_version


def _generate_note(
    action: Action,
    package: str,
    python_version: str,
    current_version: str | None,
    latest_version: str | None,
    is_git_dependency: bool,
) -> str:
    """Generate a human/LLM-readable note explaining the analysis result.

    Args:
        action: The determined action for this dependency.
        package: Package name.
        python_version: Python version string (e.g., "3.11").
        current_version: Currently specified version or None.
        latest_version: Latest available version or None/"unknown".
        is_git_dependency: Whether this is a git-based dependency.

    Returns:
        Explanatory note for this analysis result.
    """
    if action == Action.DELETE:
        return (
            f"Package '{package}' has a Python version marker that excludes Python {python_version}. "
            f"This dependency should be removed from configurations targeting Python {python_version}, "
            f"or the marker is intentional (e.g., backport packages like 'tomli' for Python <3.11)."
        )

    if action == Action.UPDATE:
        if is_git_dependency:
            return (
                f"Git dependency '{package}' has a newer release available. "
                f"Current ref: {current_version}, latest release: {latest_version}. "
                f"Consider updating the git reference to the latest version."
            )
        return f"Package '{package}' can be updated from {current_version} to {latest_version}. Review the changelog for breaking changes before updating."

    if action == Action.CHECK_MANUALLY:
        if latest_version == VersionStatus.UNKNOWN.value:
            if is_git_dependency:
                return (
                    f"Git dependency '{package}' requires manual verification. "
                    f"Could not determine latest version from GitHub releases/tags. "
                    f"This may be a private repository, or the project doesn't use GitHub releases. "
                    f"SECURITY: Verify this is a legitimate package and not a typosquatting attempt."
                )
            return (
                f"Package '{package}' requires manual verification. "
                f"Could not determine latest version from PyPI. "
                f"This may be a private/internal package, or PyPI API was unavailable. "
                f"SECURITY: Verify this is a legitimate package and not a dependency confusion attack."
            )
        # Git dependency with some version info but unclear status
        return (
            f"Git dependency '{package}' requires manual verification. "
            f"Current ref: {current_version or 'unspecified'}, found version: {latest_version}. "
            f"Unable to automatically compare versions. Check if an update is needed."
        )

    # Action.NONE - up to date
    if current_version is None:
        return (
            f"Package '{package}' has no version constraint specified (accepts any version). "
            f"Latest available version is {latest_version}. "
            f"Consider pinning to a specific version range for reproducible builds."
        )

    return f"Package '{package}' is up to date at version {current_version} (latest: {latest_version}) for Python {python_version}."


def _generate_summary_note(
    total_packages: int,
    updates_available: int,
    up_to_date: int,
    check_manually: int,
    from_private_index: int,
    indexes: list[IndexInfo] | None = None,
) -> str:
    """Generate a human/LLM-readable summary note.

    Args:
        total_packages: Total number of packages analyzed.
        updates_available: Number of packages with updates available.
        up_to_date: Number of packages that are up to date.
        check_manually: Number of packages requiring manual verification.
        from_private_index: Number of packages from private indexes.
        indexes: List of configured package indexes (for security analysis).

    Returns:
        Summary note explaining the analysis results.
    """
    parts: list[str] = [f"Analyzed {total_packages} dependencies."]

    if updates_available > 0:
        parts.append(f"{updates_available} can be updated.")

    if up_to_date > 0:
        parts.append(f"{up_to_date} are up to date.")

    if check_manually > 0:
        parts.append(f"{check_manually} require manual verification - SECURITY: Review these for potential dependency confusion or typosquatting.")

    if from_private_index > 0:
        parts.append(f"{from_private_index} are from private indexes - ensure these are from trusted internal sources.")

    # Check for index configuration security issues
    if indexes:
        has_pypi = any(idx.index_type == IndexType.PYPI for idx in indexes)
        has_private = any(idx.is_private for idx in indexes)

        if has_pypi and has_private:
            # Find position of first private index vs PyPI
            pypi_pos = next((i for i, idx in enumerate(indexes) if idx.index_type == IndexType.PYPI), -1)
            private_pos = next((i for i, idx in enumerate(indexes) if idx.is_private), -1)

            if pypi_pos >= 0 and private_pos >= 0 and pypi_pos < private_pos:
                parts.append(
                    "WARNING: PyPI is configured before private index - "
                    "this may expose you to dependency confusion attacks. "
                    "Consider setting private index as primary (--index-url) and PyPI as extra (--extra-index-url)."
                )

    return " ".join(parts)


def _generate_enriched_note(
    action: Action,
    package: str,
    current_version: str | None,
    latest_version: str | None,
    is_git_dependency: bool,
    license_info: str | None = None,
    stars: int | None = None,
    forks: int | None = None,
    latest_release_date: str | None = None,
) -> str:
    """Generate an enriched human/LLM-readable note with metadata context.

    Args:
        action: The determined action for this dependency.
        package: Package name.
        current_version: Currently specified version or None.
        latest_version: Latest available version or None/"unknown".
        is_git_dependency: Whether this is a git-based dependency.
        license_info: SPDX license identifier or None.
        stars: GitHub stars count or None.
        forks: GitHub forks count or None.
        latest_release_date: ISO date of latest release or None.

    Returns:
        Enriched explanatory note for this analysis result.
    """
    # Build base note
    base_note = _generate_note(
        action=action,
        package=package,
        python_version="all",  # Enriched analysis is version-agnostic
        current_version=current_version,
        latest_version=latest_version,
        is_git_dependency=is_git_dependency,
    )

    # Add metadata context
    metadata_parts: list[str] = []

    if license_info:
        metadata_parts.append(f"License: {license_info}")

    if stars is not None:
        metadata_parts.append(f"{stars:,} stars")

    if forks is not None:
        metadata_parts.append(f"{forks:,} forks")

    if latest_release_date:
        # Extract just the date part from ISO timestamp
        date_part = latest_release_date.split("T")[0] if "T" in latest_release_date else latest_release_date
        metadata_parts.append(f"last release: {date_part}")

    if metadata_parts:
        metadata_str = " | ".join(metadata_parts)
        return f"{base_note} [{metadata_str}]"

    return base_note


def _create_entry_for_version(
    dep: DependencyInfo,
    py_ver: PythonVersion,
    version_result: VersionResult,
) -> OutdatedEntry:
    """Create a single analysis entry for a dependency and Python version.

    Args:
        dep: The dependency being analyzed.
        py_ver: The Python version context.
        version_result: Result from version resolution.

    Returns:
        Analysis entry for this combination.
    """
    action, current, latest = determine_action(dep, py_ver, version_result)
    note = _generate_note(
        action=action,
        package=dep.name,
        python_version=str(py_ver),
        current_version=current,
        latest_version=latest,
        is_git_dependency=dep.is_git_dependency,
    )
    return OutdatedEntry(
        package=dep.name,
        python_version=str(py_ver),
        current_version=current,
        latest_version=latest,
        action=action,
        note=note,
    )


def _generate_entries_for_dependency(
    dep: DependencyInfo,
    python_versions: list[PythonVersion],
    version_results: dict[str, VersionResult],
) -> list[OutdatedEntry]:
    """Generate entries for a single dependency across all Python versions.

    Args:
        dep: The dependency to analyze.
        python_versions: List of valid Python versions.
        version_results: Map of package names to version results.

    Returns:
        List of entries for this dependency.
    """
    version_result = version_results.get(dep.name, VersionResult(is_unknown=True))
    return [_create_entry_for_version(dep, py_ver, version_result) for py_ver in python_versions]


def _generate_entries(
    dependencies: list[DependencyInfo],
    python_versions: list[PythonVersion],
    version_results: dict[str, VersionResult],
) -> list[OutdatedEntry]:
    """Generate analysis entries for all dependency × Python version combinations.

    Args:
        dependencies: List of all dependencies.
        python_versions: List of valid Python versions.
        version_results: Map of package names to version results.

    Returns:
        List of all analysis entries.
    """
    entries: list[OutdatedEntry] = []
    for dep in dependencies:
        entries.extend(_generate_entries_for_dependency(dep, python_versions, version_results))
    return entries


def _count_actions(entries: list[OutdatedEntry]) -> dict[Action, int]:
    """Count entries by action type.

    Args:
        entries: List of analysis entries.

    Returns:
        Map of action types to counts.
    """
    counts: dict[Action, int] = dict.fromkeys(Action, 0)
    for entry in entries:
        counts[entry.action] += 1
    return counts


def determine_action(
    dep: DependencyInfo,
    python_version: PythonVersion,
    version_result: VersionResult,
) -> tuple[Action, str | None, str | None]:
    """Determine the action for a dependency.

    Args:
        dep: The dependency being analyzed.
        python_version: The Python version context.
        version_result: Result from version resolution.

    Returns:
        Tuple of (action, current_version, latest_version).
    """
    if not _dependency_applies_to_python_version(dep, python_version):
        return Action.DELETE, None, None

    if dep.is_git_dependency:
        return _determine_git_action(dep, version_result)

    return _determine_pypi_action(dep, version_result)


@dataclass
class Analyzer:
    """Stateful analyzer for pyproject.toml dependency analysis.

    Attributes:
        github_token: Optional GitHub token for API authentication.
        timeout: Request timeout in seconds.
        concurrency: Maximum concurrent API requests.
        resolver: The version resolver instance.
    """

    github_token: str | None = None
    timeout: float = 30.0
    concurrency: int = 10
    resolver: VersionResolver = field(init=False)

    def __post_init__(self) -> None:
        """Initialize and validate the analyzer configuration."""
        if self.timeout <= 0:
            raise ValueError(f"timeout must be positive, got {self.timeout}")
        if self.concurrency <= 0:
            raise ValueError(f"concurrency must be positive, got {self.concurrency}")

        self.resolver = VersionResolver(
            timeout=self.timeout,
            github_token=self.github_token,
        )

    async def analyze_async(self, pyproject_path: Path | str) -> AnalysisResult:
        """Analyze a pyproject.toml file asynchronously."""
        path = Path(pyproject_path)
        logger.info("Analyzing %s", path)

        data = load_pyproject(path)
        python_versions = self._get_python_versions(data)
        dependencies = extract_dependencies(data)
        logger.info("Found %d dependencies", len(dependencies))

        unique_deps = {dep.name: dep for dep in dependencies}
        logger.debug("Unique packages: %d", len(unique_deps))

        version_results = await self.resolver.resolve_many_async(
            list(unique_deps.values()),
            concurrency=self.concurrency,
        )

        return self._build_result(dependencies, python_versions, version_results, unique_deps)

    def _get_python_versions(self, data: PyprojectSchema) -> list[PythonVersion]:
        """Extract and parse Python version requirements."""
        requires_python = get_requires_python(data)
        python_versions = parse_requires_python(requires_python)
        logger.debug("Valid Python versions: %s", [str(v) for v in python_versions])
        return python_versions

    def _build_result(
        self,
        dependencies: list[DependencyInfo],
        python_versions: list[PythonVersion],
        version_results: dict[str, VersionResult],
        unique_deps: dict[str, DependencyInfo],
    ) -> AnalysisResult:
        """Build the final analysis result."""
        entries = _generate_entries(dependencies, python_versions, version_results)
        counts = _count_actions(entries)
        return AnalysisResult(
            entries=entries,
            python_versions=[str(v) for v in python_versions],
            total_dependencies=len(unique_deps),
            update_count=counts[Action.UPDATE],
            delete_count=counts[Action.DELETE],
            check_manually_count=counts[Action.CHECK_MANUALLY],
        )

    def analyze(
        self,
        pyproject_path: Path | str,
    ) -> AnalysisResult:
        """Synchronous wrapper for analyze_async.

        Args:
            pyproject_path: Path to the pyproject.toml file.

        Returns:
            Complete analysis result with all entries.
        """
        return asyncio.run(self.analyze_async(pyproject_path))

    async def analyze_enriched_async(self, pyproject_path: Path | str) -> EnrichedAnalysisResult:
        """Analyze with full metadata enrichment.

        Args:
            pyproject_path: Path to pyproject.toml.

        Returns:
            Enriched analysis result with PyPI and repo metadata.
        """
        from datetime import datetime, timezone

        path = Path(pyproject_path)
        logger.info("Analyzing %s (enriched mode)", path)

        data = load_pyproject(path)
        python_versions = self._get_python_versions(data)
        dependencies = extract_dependencies(data)

        unique_deps = {dep.name: dep for dep in dependencies}
        version_results = await self.resolver.resolve_many_async(
            list(unique_deps.values()),
            concurrency=self.concurrency,
        )

        # Detect configured indexes
        indexes = detect_configured_indexes(pyproject_data=data, project_dir=path.parent)

        # Resolve index for each package
        index_resolver = IndexResolver(indexes=indexes, timeout=self.timeout)
        index_resolution = await index_resolver.resolve_many_async(
            list(unique_deps.keys()),
            concurrency=self.concurrency,
        )
        index_results = index_resolution.packages

        # Build dependency graph and reverse graph (required_by)
        dep_graph = self._build_dependency_graph(version_results)
        reverse_graph = self._build_reverse_dependency_graph(dep_graph)

        # Resolve repository metadata
        repo_resolver = RepoResolver(timeout=self.timeout, github_token=self.github_token)
        enriched_packages = await self._build_enriched_packages(
            unique_deps,
            version_results,
            index_results,
            python_versions,
            repo_resolver,
            reverse_graph,
        )

        return EnrichedAnalysisResult(
            analyzed_at=datetime.now(timezone.utc).isoformat(),
            pyproject_path=str(path),
            python_versions=[str(v) for v in python_versions],
            indexes_configured=indexes,
            packages=enriched_packages,
            dependency_graph=dep_graph,
            summary=self._compute_enriched_summary(enriched_packages, indexes),
        )

    async def _build_enriched_packages(
        self,
        unique_deps: dict[str, DependencyInfo],
        version_results: dict[str, VersionResult],
        index_results: dict[str, IndexInfo | None],
        python_versions: list[PythonVersion],
        repo_resolver: RepoResolver,
        reverse_graph: dict[str, list[str]],
    ) -> list[EnrichedEntry]:
        """Build enriched package entries with metadata."""
        packages: list[EnrichedEntry] = []

        for name, dep in unique_deps.items():
            version_result = version_results.get(name, VersionResult(is_unknown=True))
            index_info = index_results.get(name)

            # Resolve repo metadata if PyPI metadata available
            repo_meta = None
            if version_result.pypi_metadata:
                from .repo_resolver import PyPIUrlMetadata

                metadata = PyPIUrlMetadata(
                    project_urls=version_result.pypi_metadata.project_urls,
                    home_page=version_result.pypi_metadata.home_page,
                )
                repo_meta = await repo_resolver.resolve_from_pypi_metadata_async(metadata)

            # Compute Python compatibility
            py_compat = {
                str(pv): CompatibilityStatus.COMPATIBLE if _dependency_applies_to_python_version(dep, pv) else CompatibilityStatus.EXCLUDED
                for pv in python_versions
            }

            # Determine action
            action, current, latest = determine_action(dep, python_versions[0], version_result)

            # Extract direct dependencies
            direct_deps = _extract_dependency_names(version_result.pypi_metadata)

            # Get reverse dependencies (who requires this package)
            required_by = reverse_graph.get(name, [])

            # Generate enriched note with metadata context
            note = _generate_enriched_note(
                action=action,
                package=name,
                current_version=current,
                latest_version=latest,
                is_git_dependency=dep.is_git_dependency,
                license_info=version_result.pypi_metadata.license if version_result.pypi_metadata else None,
                stars=repo_meta.stars if repo_meta else None,
                forks=repo_meta.forks if repo_meta else None,
                latest_release_date=version_result.pypi_metadata.latest_release_date if version_result.pypi_metadata else None,
            )

            packages.append(
                EnrichedEntry(
                    name=name,
                    requested_version=dep.version_constraints or None,
                    resolved_version=current,
                    latest_version=latest,
                    action=action,
                    note=note,
                    source=dep.source,
                    index_info=index_info,
                    python_compatibility=py_compat,
                    pypi_metadata=version_result.pypi_metadata,
                    repo_metadata=repo_meta,
                    direct_dependencies=direct_deps,
                    required_by=required_by,
                )
            )

        return packages

    def _build_dependency_graph(self, version_results: dict[str, VersionResult]) -> dict[str, list[str]]:
        """Build dependency graph from requires_dist."""
        graph: dict[str, list[str]] = {}

        for name, result in version_results.items():
            if result.pypi_metadata and result.pypi_metadata.requires_dist:
                deps = _extract_dependency_names(result.pypi_metadata)
                if deps:
                    graph[name] = deps

        return graph

    def _build_reverse_dependency_graph(self, dep_graph: dict[str, list[str]]) -> dict[str, list[str]]:
        """Build reverse dependency graph (what requires each package).

        Args:
            dep_graph: Forward dependency graph (package -> its dependencies).

        Returns:
            Reverse graph (package -> packages that depend on it).
        """
        reverse: dict[str, list[str]] = {}

        for package, dependencies in dep_graph.items():
            for dep in dependencies:
                if dep not in reverse:
                    reverse[dep] = []
                reverse[dep].append(package)

        return reverse

    def _compute_enriched_summary(
        self,
        packages: list[EnrichedEntry],
        indexes: list[IndexInfo],
    ) -> EnrichedSummary:
        """Compute summary statistics.

        Args:
            packages: List of enriched package entries.
            indexes: List of configured indexes.

        Returns:
            EnrichedSummary with computed statistics.
        """
        total = len(packages)
        updates = sum(1 for pkg in packages if pkg.action == Action.UPDATE)
        up_to_date = sum(1 for pkg in packages if pkg.action == Action.NONE)
        check_manually = sum(1 for pkg in packages if pkg.action == Action.CHECK_MANUALLY)
        from_pypi = sum(1 for pkg in packages if pkg.index_info and pkg.index_info.index_type == IndexType.PYPI)
        from_private = sum(1 for pkg in packages if pkg.index_info and pkg.index_info.is_private)

        # Generate summary note
        note = _generate_summary_note(
            total_packages=total,
            updates_available=updates,
            up_to_date=up_to_date,
            check_manually=check_manually,
            from_private_index=from_private,
            indexes=indexes,
        )

        return EnrichedSummary(
            total_packages=total,
            updates_available=updates,
            up_to_date=up_to_date,
            check_manually=check_manually,
            from_pypi=from_pypi,
            from_private_index=from_private,
            note=note,
        )

    def analyze_enriched(self, pyproject_path: Path | str) -> EnrichedAnalysisResult:
        """Synchronous wrapper for analyze_enriched_async.

        Args:
            pyproject_path: Path to the pyproject.toml file.

        Returns:
            Enriched analysis result.
        """
        return asyncio.run(self.analyze_enriched_async(pyproject_path))


def _extract_dependency_names(pypi_metadata: PyPIMetadata | None) -> list[str]:
    """Extract package names from requires_dist.

    Args:
        pypi_metadata: PyPI metadata containing requires_dist.

    Returns:
        List of normalized package names.
    """
    if not pypi_metadata or not pypi_metadata.requires_dist:
        return []

    deps: list[str] = []
    for req in pypi_metadata.requires_dist:
        # Extract package name: take first word, strip extras/markers/versions
        dep_name = req.split()[0].split("[")[0].split(";")[0].split("<")[0].split(">")[0].split("=")[0].split("!")[0].strip()
        if dep_name:
            deps.append(dep_name.lower().replace("-", "_"))
    return deps


def create_analyzer(
    *,
    github_token: str | None = None,
    timeout: float = 30.0,
    concurrency: int = 10,
) -> Analyzer:
    """Create an Analyzer instance with the given configuration.

    Args:
        github_token: Optional GitHub token for API authentication.
        timeout: Request timeout in seconds.
        concurrency: Maximum concurrent API requests.

    Returns:
        Configured analyzer instance.
    """
    return Analyzer(
        github_token=github_token,
        timeout=timeout,
        concurrency=concurrency,
    )


def run_analysis(
    pyproject_path: Path | str,
    *,
    github_token: str | None = None,
    timeout: float = 30.0,
    concurrency: int = 10,
) -> AnalysisResult:
    """Analyze a pyproject.toml file and return the full result.

    Args:
        pyproject_path: Path to the pyproject.toml file.
        github_token: Optional GitHub token for API authentication.
        timeout: Request timeout in seconds.
        concurrency: Maximum concurrent API requests.

    Returns:
        Complete analysis result with entries and statistics.
    """
    analyzer = create_analyzer(
        github_token=github_token,
        timeout=timeout,
        concurrency=concurrency,
    )
    return analyzer.analyze(pyproject_path)


def analyze_pyproject(
    pyproject_path: Path | str,
    *,
    github_token: str | None = None,
    timeout: float = 30.0,
    concurrency: int = 10,
) -> list[OutdatedEntry]:
    """Analyze a pyproject.toml file and return outdated entries.

    This is the main API function for the library.

    Args:
        pyproject_path: Path to the pyproject.toml file.
        github_token: Optional GitHub token for API authentication.
        timeout: Request timeout in seconds.
        concurrency: Maximum concurrent API requests.

    Returns:
        List of analysis entries for all dependencies.

    Example:
        >>> entries = analyze_pyproject("pyproject.toml")  # doctest: +SKIP
        >>> for entry in entries:  # doctest: +SKIP
        ...     if entry.action == Action.UPDATE:  # doctest: +SKIP
        ...         print(f"{entry.package}: {entry.current_version} -> {entry.latest_version}")  # doctest: +SKIP
    """
    return run_analysis(
        pyproject_path,
        github_token=github_token,
        timeout=timeout,
        concurrency=concurrency,
    ).entries


def write_outdated_json(
    entries: list[OutdatedEntry],
    output_path: Path | str,
) -> None:
    """Write analysis results to an outdated.json file.

    Uses Pydantic's model_dump(mode='json') to serialize enums as strings.

    Args:
        entries: List of analysis entries.
        output_path: Path to the output JSON file.

    Raises:
        ValueError: If output_path is not a valid file path.
    """
    path = Path(output_path).resolve()

    # Validate path is a file, not a directory
    if path.is_dir():
        raise ValueError(f"Output path must be a file, not a directory: {path}")

    # Ensure parent directory exists
    path.parent.mkdir(parents=True, exist_ok=True)

    # Serialize Pydantic models with mode='json' to convert enums to strings
    data = [entry.model_dump(mode="json") for entry in entries]

    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    logger.info("Wrote %d entries to %s", len(entries), path)


def write_enriched_json(
    result: EnrichedAnalysisResult,
    output_path: Path | str,
) -> None:
    """Write enriched analysis results to JSON file.

    Uses Pydantic's model_dump with mode='json' and by_alias=True to properly
    serialize enums as strings and apply serialization aliases.

    Args:
        result: Enriched analysis result.
        output_path: Path to output JSON file.

    Raises:
        ValueError: If output_path is not a valid file path.
    """
    path = Path(output_path).resolve()

    # Validate path is a file, not a directory
    if path.is_dir():
        raise ValueError(f"Output path must be a file, not a directory: {path}")

    # Ensure parent directory exists
    path.parent.mkdir(parents=True, exist_ok=True)

    # Serialize with mode='json' to convert enums and by_alias=True for aliases
    # (e.g., index_info -> index)
    with path.open("w", encoding="utf-8") as f:
        f.write(result.model_dump_json(indent=2, by_alias=True))

    logger.info("Wrote enriched analysis to %s", path)


def run_enriched_analysis(
    pyproject_path: Path | str,
    *,
    github_token: str | None = None,
    timeout: float = 30.0,
    concurrency: int = 10,
) -> EnrichedAnalysisResult:
    """Analyze a pyproject.toml file with full enrichment.

    Args:
        pyproject_path: Path to the pyproject.toml file.
        github_token: Optional GitHub token for API authentication.
        timeout: Request timeout in seconds.
        concurrency: Maximum concurrent API requests.

    Returns:
        Enriched analysis result with metadata.
    """
    analyzer = create_analyzer(
        github_token=github_token,
        timeout=timeout,
        concurrency=concurrency,
    )
    return analyzer.analyze_enriched(pyproject_path)


__all__ = [
    "Analyzer",
    "analyze_pyproject",
    "create_analyzer",
    "determine_action",
    "run_analysis",
    "run_enriched_analysis",
    "write_enriched_json",
    "write_outdated_json",
]
