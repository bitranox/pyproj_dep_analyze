"""Parser for requires-python version specifiers.

Purpose
-------
Parse `requires-python` expressions from pyproject.toml and derive the list
of valid Python versions that satisfy the requirements.

Contents
--------
* :func:`parse_requires_python` - Parse a requires-python string into version list
* :func:`version_satisfies` - Check if a version satisfies a constraint
* :class:`VersionConstraint` - Represents a single version constraint

System Role
-----------
Provides the foundation for determining which Python versions to analyze.
The resulting version list drives the per-version dependency analysis.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from functools import lru_cache
from typing import TYPE_CHECKING

from .models import KNOWN_PYTHON_VERSIONS, PythonVersion

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from collections.abc import Sequence

# Precompiled regex for version constraint parsing
_RE_CONSTRAINT = re.compile(r"^(>=|<=|!=|==|~=|>|<)?\s*(\d+(?:\.\d+)*)")


@dataclass(frozen=True, slots=True)
class VersionConstraint:
    """A single version constraint like >=3.9 or <4.0.

    Attributes:
        operator: The comparison operator (>=, <=, >, <, ==, !=, ~=).
        version: The version being compared against.
    """

    operator: str
    version: PythonVersion


@lru_cache(maxsize=128)
def _parse_constraint(constraint_str: str) -> VersionConstraint | None:
    """Parse a single constraint string like '>=3.9' into a VersionConstraint.

    Args:
        constraint_str: A version constraint string (e.g., ">=3.9", "<4.0").

    Returns:
        Parsed constraint or None if unparseable.
    """
    constraint_str = constraint_str.strip()
    if not constraint_str:
        return None

    # Match operator and version
    match = _RE_CONSTRAINT.match(constraint_str)
    if not match:
        return None

    operator = match.group(1) or ">="
    version_str = match.group(2)

    # Ensure we have at least major.minor
    parts = version_str.split(".")
    if len(parts) == 1:
        version_str = f"{parts[0]}.0"

    try:
        version = PythonVersion.from_string(version_str)
    except ValueError:
        return None

    return VersionConstraint(operator=operator, version=version)


def _version_satisfies_constraint(version: PythonVersion, constraint: VersionConstraint) -> bool:
    """Check if a version satisfies a single constraint.

    Args:
        version: The version to check.
        constraint: The constraint to check against.

    Returns:
        True if the version satisfies the constraint.
    """
    op = constraint.operator
    cv = constraint.version

    if op == ">=":
        return version >= cv
    if op == ">":
        return version > cv
    if op == "<=":
        return version <= cv
    if op == "<":
        return version < cv
    if op == "==":
        return version == cv
    if op == "!=":
        return version != cv
    if op == "~=":
        # Compatible release: ~=3.9 means >=3.9, <4.0
        return version >= cv and version.major == cv.major

    return False


def version_satisfies(version: PythonVersion, constraints: Sequence[VersionConstraint]) -> bool:
    """Check if a version satisfies all constraints.

    Args:
        version: The version to check.
        constraints: List of constraints that must all be satisfied.

    Returns:
        True if the version satisfies all constraints.
    """
    return all(_version_satisfies_constraint(version, c) for c in constraints)


@lru_cache(maxsize=256)
def _parse_requires_python_cached(requires_python: str) -> tuple[PythonVersion, ...]:
    """Cached implementation of requires-python parsing.

    Args:
        requires_python: The requires-python specification string.

    Returns:
        Tuple of Python versions satisfying the requirement, sorted ascending.
    """
    # Split by comma to get individual constraints
    constraint_strs = [c.strip() for c in requires_python.split(",")]
    constraints: list[VersionConstraint] = []

    for cs in constraint_strs:
        constraint = _parse_constraint(cs)
        if constraint:
            constraints.append(constraint)

    if not constraints:
        logger.warning(
            "Could not parse requires-python value: %r. Using all known Python versions.",
            requires_python,
        )
        return tuple(KNOWN_PYTHON_VERSIONS)

    # Filter known versions by constraints
    valid_versions = [v for v in KNOWN_PYTHON_VERSIONS if version_satisfies(v, constraints)]

    return tuple(sorted(valid_versions))


def parse_requires_python(requires_python: str | None) -> list[PythonVersion]:
    """Parse a requires-python string and return list of valid Python versions.

    Example:
        >>> parse_requires_python(">=3.9")
        [PythonVersion(major=3, minor=9), PythonVersion(major=3, minor=10), ...]

        >>> parse_requires_python(">=3.10,<3.12")
        [PythonVersion(major=3, minor=10), PythonVersion(major=3, minor=11)]

    Args:
        requires_python: The requires-python specification string (e.g.,
            ">=3.9,<4.0"). If None, returns all known Python 3.x versions.

    Returns:
        List of Python versions satisfying the requirement, sorted ascending.
    """
    if not requires_python:
        # Default: all known Python 3.x versions
        return list(KNOWN_PYTHON_VERSIONS)

    return list(_parse_requires_python_cached(requires_python))


def python_version_to_string(version: PythonVersion) -> str:
    """Convert a PythonVersion to its string representation.

    Args:
        version: The version to convert.

    Returns:
        String representation like "3.11".
    """
    return str(version)


__all__ = [
    "VersionConstraint",
    "parse_requires_python",
    "python_version_to_string",
    "version_satisfies",
]
