"""Domain models for dependency analysis (dataclasses).

Purpose
-------
Define core data structures for the dependency analysis domain layer.
These are pure dataclasses used for internal business logic.

For external data serialization, use the Pydantic schemas in schemas.py.

Contents
--------
* :class:`Action` - Enumeration of possible actions for dependencies
* :class:`OutdatedEntry` - Data class representing a dependency analysis result
* :class:`DependencyInfo` - Parsed dependency information
* :class:`PythonVersion` - Represents a Python version
* :class:`AnalysisResult` - Complete analysis result

Data Flow Pattern
-----------------
External Input → Pydantic (validate) → Dataclass (domain) → Pydantic (serialize) → Output

System Role
-----------
Provides the canonical data structures that flow through the analysis pipeline.
These dataclasses are dependency-free and used for pure business logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

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


@dataclass(frozen=True, slots=True)
class OutdatedEntry:
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
    """

    package: str
    python_version: str
    current_version: str | None
    latest_version: str | None
    action: Action


def _empty_str_list() -> list[str]:
    """Return an empty string list for dataclass defaults."""
    return []


@dataclass(slots=True)
class DependencyInfo:
    """Parsed information about a single dependency.

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
    extras: list[str] = field(default_factory=_empty_str_list)
    source: str = ""
    is_git_dependency: bool = False
    git_url: str | None = None
    git_ref: str | None = None


@dataclass(frozen=True, slots=True)
class PythonVersion:
    """Represents a Python version like 3.11 or 3.12.

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


def _empty_entry_list() -> list[OutdatedEntry]:
    """Return an empty OutdatedEntry list for dataclass defaults."""
    return []


@dataclass(slots=True)
class AnalysisResult:
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

    entries: list[OutdatedEntry] = field(default_factory=_empty_entry_list)
    python_versions: list[str] = field(default_factory=_empty_str_list)
    total_dependencies: int = 0
    update_count: int = 0
    delete_count: int = 0
    check_manually_count: int = 0


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
    "DependencyInfo",
    "KNOWN_PYTHON_VERSIONS",
    "OutdatedEntry",
    "PythonVersion",
]
