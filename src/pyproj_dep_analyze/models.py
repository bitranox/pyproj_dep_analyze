"""Domain models for dependency analysis.

Purpose
-------
Define core data structures for the dependency analysis domain layer.
Uses Pydantic models for data that needs serialization, and dataclasses
for internal logic with custom behavior.

Data Flow Pattern
-----------------
External Input → Pydantic (validate) → Pydantic models (domain + serialize) → Output

This eliminates unnecessary conversions between dataclasses and Pydantic schemas.

System Role
-----------
Provides the canonical data structures that flow through the analysis pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from collections.abc import Sequence


class Action(str, Enum):
    """Actions that can be recommended for a dependency.

    Attributes:
        UPDATE: A newer compatible version exists.
        DELETE: The dependency should be removed for this Python version.
        NONE: The dependency is correct and up to date.
        CHECK_MANUALLY: Manual verification required (e.g., GitHub packages
            without releases).
    """

    UPDATE = "update"
    DELETE = "delete"
    NONE = "none"
    CHECK_MANUALLY = "check manually"


class VersionStatus(str, Enum):
    """Status indicator for version resolution.

    Attributes:
        UNKNOWN: Version could not be determined.
    """

    UNKNOWN = "unknown"


class RepoType(str, Enum):
    """Repository hosting platform types.

    Attributes:
        GITHUB: GitHub repository.
        GITLAB: GitLab repository.
        BITBUCKET: Bitbucket repository.
        UNKNOWN: Unknown or unsupported repository type.
    """

    GITHUB = "github"
    GITLAB = "gitlab"
    BITBUCKET = "bitbucket"
    UNKNOWN = "unknown"


class CompatibilityStatus(str, Enum):
    """Python version compatibility status.

    Attributes:
        COMPATIBLE: Dependency is compatible with the Python version.
        EXCLUDED: Dependency is excluded via Python markers.
        UNKNOWN: Compatibility could not be determined.
    """

    COMPATIBLE = "compatible"
    EXCLUDED = "excluded"
    UNKNOWN = "unknown"


class IndexType(str, Enum):
    """Package index types.

    Attributes:
        PYPI: Public PyPI (pypi.org).
        TESTPYPI: Test PyPI (test.pypi.org).
        ARTIFACTORY: JFrog Artifactory.
        DEVPI: devpi server.
        AZURE_ARTIFACTS: Azure DevOps Artifacts.
        CLOUDSMITH: Cloudsmith.
        GEMFURY: Gemfury.
        ANACONDA: Anaconda.org.
        CUSTOM: Unknown/custom index (assumed private).
    """

    PYPI = "pypi"
    TESTPYPI = "testpypi"
    ARTIFACTORY = "artifactory"
    DEVPI = "devpi"
    AZURE_ARTIFACTS = "azure-artifacts"
    CLOUDSMITH = "cloudsmith"
    GEMFURY = "gemfury"
    ANACONDA = "anaconda"
    CUSTOM = "custom"


class OutputFormat(str, Enum):
    """Output format options for CLI display.

    Attributes:
        JSON: Output results as JSON.
        TABLE: Output results as formatted table with summary.
        SUMMARY: Output only summary statistics.
    """

    JSON = "json"
    TABLE = "table"
    SUMMARY = "summary"


class ConfigFormat(str, Enum):
    """Configuration display format options.

    Attributes:
        HUMAN: Human-readable formatted output.
        JSON: JSON output.
    """

    HUMAN = "human"
    JSON = "json"


class DependencyMarker(str, Enum):
    """Special dependency markers used in pyproject.toml parsing.

    Attributes:
        PYTHON: Python version specification in dependencies section.
    """

    PYTHON = "python"


class GitProtocol(str, Enum):
    """Git protocol prefixes used in dependency URLs.

    Attributes:
        GIT_PLUS: git+ prefix (e.g., git+https://...).
        GIT_PROTO: git:// protocol.
        AT_GIT_PLUS: @git+ prefix in package @ git+url format.
    """

    GIT_PLUS = "git+"
    GIT_PROTO = "git://"
    AT_GIT_PLUS = "@git+"


class DeploymentTarget(str, Enum):
    """Deployment target configuration layers.

    Specifies where configuration files should be deployed.

    Attributes:
        APP: System-wide application config.
        HOST: Host-specific configuration.
        USER: User-specific configuration.
    """

    APP = "app"
    HOST = "host"
    USER = "user"


# --- Pydantic Models (for data that needs serialization) ---


class OutdatedEntry(BaseModel):
    """Represents a dependency analysis result for a specific Python version.

    This is the primary output data structure, used both for JSON serialization
    and as the API return type.

    Attributes:
        package: The name of the package being analyzed.
        python_version: The Python version this analysis applies to (e.g., "3.11").
        current_version: The currently specified version, or None if not
            determinable.
        latest_version: The latest available version, or None/"unknown" if not
            determinable.
        action: The recommended action for this dependency.
        note: Human/LLM-readable explanation of what this record means.
    """

    model_config = ConfigDict(frozen=True)

    package: str = Field(description="The name of the package")
    python_version: str = Field(description="The Python version this applies to")
    current_version: str | None = Field(description="Currently specified version")
    latest_version: str | None = Field(description="Latest available version")
    action: Action = Field(description="Recommended action")
    note: str = Field(default="", description="Human/LLM-readable explanation of this analysis result")


def _empty_str_list() -> list[str]:
    """Return an empty string list for defaults."""
    return []


def _empty_str_dict() -> dict[str, str]:
    """Return an empty string dict for defaults."""
    return {}


class VersionMetrics(BaseModel):
    """Computed metrics from version history for quality assessment.

    These metrics help detect abandoned packages and unusual release patterns.

    Attributes:
        release_count: Total number of releases.
        latest_release_age_days: Days since the latest release.
        first_release_age_days: Days since the first release (project age).
        avg_days_between_releases: Average days between consecutive releases.
        min_days_between_releases: Minimum gap between releases (detect rapid-fire releases).
        max_days_between_releases: Maximum gap between releases (detect abandonment periods).
        releases_last_year: Number of releases in the last 365 days.
        release_dates: List of ISO timestamps for all releases (sorted oldest first).
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    release_count: int = 0
    latest_release_age_days: int | None = None
    first_release_age_days: int | None = None
    avg_days_between_releases: float | None = None
    min_days_between_releases: int | None = None
    max_days_between_releases: int | None = None
    releases_last_year: int = 0
    release_dates: list[str] = Field(default_factory=_empty_str_list)


class DownloadStats(BaseModel):
    """Download statistics from PyPI.

    Note: PyPI BigQuery data is not directly accessible via API.
    These stats come from pypistats.org API or similar services.

    Attributes:
        total_downloads: Total downloads across all time (if available).
        last_month_downloads: Downloads in the last 30 days.
        last_week_downloads: Downloads in the last 7 days.
        last_day_downloads: Downloads in the last 24 hours.
        fetched_at: ISO timestamp when stats were retrieved.
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    total_downloads: int | None = None
    last_month_downloads: int | None = None
    last_week_downloads: int | None = None
    last_day_downloads: int | None = None
    fetched_at: str | None = None


class PyPIMetadata(BaseModel):
    """Enriched metadata from PyPI API response.

    Attributes:
        summary: One-line package description.
        license: SPDX license identifier or license text.
        home_page: Primary project URL.
        project_urls: Dict of labeled URLs (Source, Documentation, etc.).
        author: Package author name.
        author_email: Package author email.
        maintainer: Package maintainer name.
        maintainer_email: Package maintainer email.
        available_versions: List of all released version strings.
        first_release_date: ISO timestamp of first release.
        latest_release_date: ISO timestamp of latest release.
        requires_python: Python version constraint from package.
        requires_dist: List of dependency specifications.
        version_metrics: Computed release pattern metrics.
        download_stats: Download statistics (requires separate API call).
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    summary: str | None = None
    license: str | None = None
    home_page: str | None = None
    project_urls: dict[str, str] = Field(default_factory=_empty_str_dict)
    author: str | None = None
    author_email: str | None = None
    maintainer: str | None = None
    maintainer_email: str | None = None
    available_versions: list[str] = Field(default_factory=_empty_str_list)
    first_release_date: str | None = None
    latest_release_date: str | None = None
    requires_python: str | None = None
    requires_dist: list[str] = Field(default_factory=_empty_str_list)
    version_metrics: VersionMetrics | None = None
    download_stats: DownloadStats | None = None


class RepoMetadata(BaseModel):
    """Lightweight repository metadata (non-security).

    Attributes:
        repo_type: Repository host type.
        url: Canonical repository URL.
        owner: Repository owner/organization.
        name: Repository name.
        stars: Star/favorite count.
        forks: Fork count.
        open_issues: Open issue count.
        default_branch: Default branch name.
        last_commit_date: ISO timestamp of last commit.
        created_at: ISO timestamp of repository creation.
        description: Repository description.
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    repo_type: RepoType = RepoType.UNKNOWN
    url: str | None = None
    owner: str | None = None
    name: str | None = None
    stars: int | None = None
    forks: int | None = None
    open_issues: int | None = None
    default_branch: str | None = None
    last_commit_date: str | None = None
    created_at: str | None = None
    description: str | None = None


class IndexInfo(BaseModel):
    """Information about a package index source.

    Attributes:
        url: The index URL (e.g., https://pypi.org/simple).
        index_type: Type of package index.
        is_private: Whether this is a private/internal index.
    """

    model_config = ConfigDict(frozen=True)

    url: str
    index_type: IndexType
    is_private: bool = False

    @property
    def name(self) -> str:
        """Return the index type value as name for backward compatibility."""
        return self.index_type.value


class IndexPatternMapping(BaseModel):
    """Mapping from URL pattern to index type and privacy.

    Attributes:
        pattern: URL substring pattern to match (e.g., "pypi.org").
        index_type: The type of package index.
        is_private: Whether this index is private/internal.
    """

    model_config = ConfigDict(frozen=True)

    pattern: str
    index_type: IndexType
    is_private: bool


# Well-known index patterns for identification
KNOWN_INDEX_PATTERNS: list[IndexPatternMapping] = [
    IndexPatternMapping(pattern="pypi.org", index_type=IndexType.PYPI, is_private=False),
    IndexPatternMapping(pattern="test.pypi.org", index_type=IndexType.TESTPYPI, is_private=False),
    IndexPatternMapping(pattern="pythonhosted.org", index_type=IndexType.PYPI, is_private=False),
    IndexPatternMapping(pattern=".jfrog.io", index_type=IndexType.ARTIFACTORY, is_private=True),
    IndexPatternMapping(pattern="devpi", index_type=IndexType.DEVPI, is_private=True),
    IndexPatternMapping(pattern="pkgs.dev.azure.com", index_type=IndexType.AZURE_ARTIFACTS, is_private=True),
    IndexPatternMapping(pattern=".cloudsmith.io", index_type=IndexType.CLOUDSMITH, is_private=True),
    IndexPatternMapping(pattern=".fury.io", index_type=IndexType.GEMFURY, is_private=True),
    IndexPatternMapping(pattern=".anaconda.org", index_type=IndexType.ANACONDA, is_private=False),
    IndexPatternMapping(pattern="conda.anaconda.org", index_type=IndexType.ANACONDA, is_private=False),
]


class PackageIndexResolutions(BaseModel):
    """Batch result of package index resolutions.

    Attributes:
        packages: Dict mapping package names to their resolved IndexInfo (or None if not found).
    """

    model_config = ConfigDict(frozen=True)

    packages: dict[str, IndexInfo | None]


# --- Dataclasses (for internal logic with custom behavior) ---


def _empty_extras_list() -> list[str]:
    """Return an empty string list for dataclass defaults."""
    return []


@dataclass(slots=True)
class DependencyInfo:
    """Parsed information about a single dependency.

    Kept as dataclass because it's internal-only and not serialized to JSON.

    Attributes:
        name: The normalized package name.
        raw_spec: The original specification string.
        version_constraints: Version constraints (e.g., ">=1.0,<2.0").
        python_markers: Python version markers (e.g., "python_version < '3.10'").
        extras: Optional extras requested (e.g., ["dev", "test"]).
        source: Where this dependency was found (e.g., "project.dependencies").
        is_git_dependency: Whether this is a git/GitHub dependency.
        git_url: The git URL if this is a git dependency.
        git_ref: The git reference (tag/branch/commit) if specified.
    """

    name: str
    raw_spec: str
    version_constraints: str = ""
    python_markers: str | None = None
    extras: list[str] = field(default_factory=_empty_extras_list)
    source: str = ""
    is_git_dependency: bool = False
    git_url: str | None = None
    git_ref: str | None = None


@dataclass(frozen=True, slots=True)
class PythonVersion:
    """Represents a Python version like 3.11 or 3.12.

    Kept as dataclass because it has custom comparison operators.

    Attributes:
        major: Major version number (e.g., 3).
        minor: Minor version number (e.g., 11).
    """

    major: int
    minor: int

    def __str__(self) -> str:
        """Return version as string like '3.11'."""
        return f"{self.major}.{self.minor}"

    def __lt__(self, other: object) -> bool:
        """Compare versions for sorting."""
        if not isinstance(other, PythonVersion):
            return NotImplemented
        return (self.major, self.minor) < (other.major, other.minor)

    def __le__(self, other: object) -> bool:
        """Compare versions."""
        if not isinstance(other, PythonVersion):
            return NotImplemented
        return (self.major, self.minor) <= (other.major, other.minor)

    def __gt__(self, other: object) -> bool:
        """Compare versions."""
        if not isinstance(other, PythonVersion):
            return NotImplemented
        return (self.major, self.minor) > (other.major, other.minor)

    def __ge__(self, other: object) -> bool:
        """Compare versions."""
        if not isinstance(other, PythonVersion):
            return NotImplemented
        return (self.major, self.minor) >= (other.major, other.minor)

    @classmethod
    def from_string(cls, version_str: str) -> PythonVersion:
        """Parse a version string like '3.11' into a PythonVersion.

        Args:
            version_str: Version string in format "major.minor" or
                "major.minor.patch".

        Returns:
            Parsed version object.

        Raises:
            ValueError: If the version string cannot be parsed.
        """
        parts = version_str.strip().split(".")
        if len(parts) < 2:
            msg = f"Invalid Python version format: {version_str}"
            raise ValueError(msg)
        return cls(major=int(parts[0]), minor=int(parts[1]))


# --- Pydantic Models for Analysis Results ---


def _empty_entry_list() -> list[OutdatedEntry]:
    """Return an empty OutdatedEntry list for defaults."""
    return []


class AnalysisResult(BaseModel):
    """Complete result of analyzing a pyproject.toml file.

    Attributes:
        entries: List of all analyzed dependencies with their statuses.
        python_versions: List of Python versions that were analyzed.
        total_dependencies: Total number of unique dependencies found.
        update_count: Number of dependencies requiring updates.
        delete_count: Number of dependencies recommended for deletion.
        check_manually_count: Number of dependencies requiring manual
            verification.
    """

    model_config = ConfigDict(frozen=True)

    entries: list[OutdatedEntry] = Field(default_factory=_empty_entry_list)
    python_versions: list[str] = Field(default_factory=_empty_str_list)
    total_dependencies: int = 0
    update_count: int = 0
    delete_count: int = 0
    check_manually_count: int = 0


class EnrichedSummary(BaseModel):
    """Summary statistics for enriched analysis results.

    Attributes:
        total_packages: Total number of packages analyzed.
        updates_available: Number of packages with updates available.
        up_to_date: Number of packages that are up to date.
        check_manually: Number of packages requiring manual verification.
        from_pypi: Number of packages sourced from public PyPI.
        from_private_index: Number of packages from private indexes.
        note: Human/LLM-readable summary of the analysis results.
    """

    model_config = ConfigDict(frozen=True)

    total_packages: int = 0
    updates_available: int = 0
    up_to_date: int = 0
    check_manually: int = 0
    from_pypi: int = 0
    from_private_index: int = 0
    note: str = Field(default="", description="Human/LLM-readable summary of analysis results")


def _empty_compat_dict() -> dict[str, CompatibilityStatus]:
    """Return an empty compatibility dict for defaults."""
    return {}


class EnrichedEntry(BaseModel):
    """Enriched dependency analysis entry with full metadata.

    Attributes:
        name: Normalized package name.
        requested_version: Version constraint from pyproject.toml.
        resolved_version: Currently resolved/installed version.
        latest_version: Latest available version.
        action: Recommended action (update, none, check_manually).
        note: Human/LLM-readable explanation of this analysis result.
        source: Where dependency was declared.
        index_info: Information about which package index served this package.
        python_compatibility: Dict mapping Python version to compatibility status.
        pypi_metadata: Enriched PyPI metadata.
        repo_metadata: Repository metadata.
        direct_dependencies: List of direct dependency names (what this package depends on).
        required_by: List of packages that depend on this package (reverse dependencies).
    """

    model_config = ConfigDict(frozen=True)

    name: str
    requested_version: str | None = None
    resolved_version: str | None = None
    latest_version: str | None = None
    action: Action = Action.NONE
    note: str = Field(default="", description="Human/LLM-readable explanation of this analysis result")
    source: str = ""
    index_info: IndexInfo | None = None
    python_compatibility: dict[str, CompatibilityStatus] = Field(default_factory=_empty_compat_dict)
    pypi_metadata: PyPIMetadata | None = None
    repo_metadata: RepoMetadata | None = None
    direct_dependencies: list[str] = Field(default_factory=_empty_str_list)
    required_by: list[str] = Field(default_factory=_empty_str_list)


def _empty_enriched_entry_list() -> list[EnrichedEntry]:
    """Return an empty EnrichedEntry list for defaults."""
    return []


def _empty_index_info_list() -> list[IndexInfo]:
    """Return an empty IndexInfo list for defaults."""
    return []


def _empty_str_list_dict() -> dict[str, list[str]]:
    """Return an empty dict of string lists for defaults."""
    return {}


def _default_enriched_summary() -> EnrichedSummary:
    """Return default EnrichedSummary for defaults."""
    return EnrichedSummary()


class EnrichedAnalysisResult(BaseModel):
    """Complete enriched analysis result.

    Attributes:
        analyzed_at: ISO timestamp of analysis.
        pyproject_path: Path to analyzed pyproject.toml.
        python_versions: List of Python versions analyzed.
        indexes_configured: List of configured package indexes.
        packages: List of enriched package entries.
        dependency_graph: Dict mapping package to its dependencies.
        summary: Analysis summary statistics.
    """

    model_config = ConfigDict(frozen=True)

    analyzed_at: str
    pyproject_path: str
    python_versions: list[str] = Field(default_factory=_empty_str_list)
    indexes_configured: list[IndexInfo] = Field(default_factory=_empty_index_info_list)
    packages: list[EnrichedEntry] = Field(default_factory=_empty_enriched_entry_list)
    dependency_graph: dict[str, list[str]] = Field(default_factory=_empty_str_list_dict)
    summary: EnrichedSummary = Field(default_factory=_default_enriched_summary)


# Known Python versions to consider (current and near-future)
KNOWN_PYTHON_VERSIONS: Sequence[PythonVersion] = (
    PythonVersion(3, 8),
    PythonVersion(3, 9),
    PythonVersion(3, 10),
    PythonVersion(3, 11),
    PythonVersion(3, 12),
    PythonVersion(3, 13),
    PythonVersion(3, 14),
    PythonVersion(3, 15),
)


__all__ = [
    "Action",
    "AnalysisResult",
    "CompatibilityStatus",
    "ConfigFormat",
    "DependencyInfo",
    "DependencyMarker",
    "DeploymentTarget",
    "DownloadStats",
    "EnrichedAnalysisResult",
    "EnrichedEntry",
    "EnrichedSummary",
    "GitProtocol",
    "IndexInfo",
    "IndexPatternMapping",
    "IndexType",
    "KNOWN_INDEX_PATTERNS",
    "KNOWN_PYTHON_VERSIONS",
    "OutdatedEntry",
    "OutputFormat",
    "PackageIndexResolutions",
    "PyPIMetadata",
    "PythonVersion",
    "RepoMetadata",
    "RepoType",
    "VersionMetrics",
    "VersionStatus",
]
