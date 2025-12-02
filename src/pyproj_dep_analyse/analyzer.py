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
from .models import Action, AnalysisResult, DependencyInfo, OutdatedEntry, PythonVersion
from .python_version_parser import parse_requires_python
from .schemas import OutdatedEntrySchema
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
        return Action.CHECK_MANUALLY, dep.git_ref, "unknown"

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
        return Action.CHECK_MANUALLY, current_version, "unknown"

    if current_version is None:
        return Action.NONE, None, latest_version

    if _version_is_greater(latest_version, current_version):
        return Action.UPDATE, current_version, latest_version

    return Action.NONE, current_version, latest_version


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
    return OutdatedEntry(
        package=dep.name,
        python_version=str(py_ver),
        current_version=current,
        latest_version=latest,
        action=action,
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

    def _get_python_versions(self, data: dict[str, object]) -> list[PythonVersion]:
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


def entry_to_dict(entry: OutdatedEntry) -> dict[str, str | None]:
    """Convert an OutdatedEntry to a dictionary for JSON serialization.

    Args:
        entry: The entry to convert.

    Returns:
        Dictionary representation of the entry.
    """
    schema = OutdatedEntrySchema(
        package=entry.package,
        python_version=entry.python_version,
        current_version=entry.current_version,
        latest_version=entry.latest_version,
        action=entry.action,
    )
    return schema.model_dump()


def write_outdated_json(
    entries: list[OutdatedEntry],
    output_path: Path | str,
) -> None:
    """Write analysis results to an outdated.json file.

    Uses Pydantic for type-safe JSON serialization at the output boundary.

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

    data = [entry_to_dict(entry) for entry in entries]

    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    logger.info("Wrote %d entries to %s", len(entries), path)


__all__ = [
    "Analyzer",
    "analyze_pyproject",
    "create_analyzer",
    "determine_action",
    "entry_to_dict",
    "run_analysis",
    "write_outdated_json",
]
