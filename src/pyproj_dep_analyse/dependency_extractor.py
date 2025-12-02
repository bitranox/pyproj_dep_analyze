"""Extractor for dependencies from pyproject.toml files.

Purpose
-------
Extract all dependencies from various sections of a pyproject.toml file,
supporting multiple build systems (poetry, pdm, hatch, flit, setuptools).

Contents
--------
* :func:`extract_dependencies` - Main function to extract all dependencies
* :func:`load_pyproject` - Load and parse a pyproject.toml file
* :class:`DependencySource` - Enum of known dependency source sections

System Role
-----------
The first stage of the analysis pipeline. Reads the pyproject.toml and
collects all dependencies from known and inferred sections.
"""

from __future__ import annotations

import logging
import re
import tomllib
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Any, cast

from .models import DependencyInfo
from .schemas import PoetryDependencySpec

logger = logging.getLogger(__name__)

# Precompiled regex patterns for dependency parsing
_RE_POETRY_SPEC = re.compile(r"^([a-zA-Z0-9._-]+)(?:\[([^\]]+)\])?\s*\(([^)]+)\)(.*)$")
_RE_STANDARD_SPEC = re.compile(r"^([a-zA-Z0-9._-]+)(?:\[([^\]]+)\])?(.*)$")
_RE_GIT_NAME_URL = re.compile(r"^([a-zA-Z0-9._-]+)\s*@\s*(.+)$")
_RE_GIT_REF = re.compile(r"^(.+?)(?:@([^@]+))?$")
_RE_REPO_NAME = re.compile(r"/([a-zA-Z0-9._-]+?)(?:\.git)?(?:@|$)")


class DependencySource(str, Enum):
    """Known sections that contain dependencies."""

    PROJECT_DEPENDENCIES = "project.dependencies"
    PROJECT_OPTIONAL = "project.optional-dependencies"
    BUILD_REQUIRES = "build-system.requires"
    POETRY_DEPS = "tool.poetry.dependencies"
    POETRY_DEV = "tool.poetry.dev-dependencies"
    POETRY_GROUP = "tool.poetry.group.*.dependencies"
    PDM_DEPS = "tool.pdm.dependencies"
    PDM_DEV = "tool.pdm.dev-dependencies"
    HATCH_DEPS = "tool.hatch.metadata.dependencies"
    HATCH_ENV = "tool.hatch.envs.*.dependencies"
    FLIT_REQUIRES = "tool.flit.metadata.requires"
    SETUPTOOLS_DYNAMIC = "tool.setuptools.dynamic.dependencies"
    DEPENDENCY_GROUPS = "dependency-groups"


def load_pyproject(path: Path | str) -> dict[str, Any]:
    """Load and parse a pyproject.toml file.

    Args:
        path: Path to the pyproject.toml file.

    Returns:
        Parsed TOML content.

    Raises:
        FileNotFoundError: If the file does not exist.
        tomllib.TOMLDecodeError: If the file is not valid TOML.
    """
    path = Path(path)
    with path.open("rb") as f:
        return tomllib.load(f)


def _get_nested(data: dict[str, Any], path: str) -> Any | None:
    """Get a nested value from a dict using dot notation.

    Args:
        data: The dictionary to search.
        path: Dot-separated path like "project.dependencies".

    Returns:
        The value if found, None otherwise.
    """
    keys = path.split(".")
    current = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
        if current is None:
            return None
    return current


@lru_cache(maxsize=1024)
def _normalize_package_name(name: str) -> str:
    """Normalize a package name according to PEP 503.

    Args:
        name: The package name to normalize.

    Returns:
        Normalized package name (lowercase, hyphens to underscores).
    """
    return name.lower().replace("-", "_").replace(".", "_")


def _parse_dependency_string(dep_str: str, source: str) -> DependencyInfo | None:
    """Parse a dependency specification string (PEP 508 or Poetry format)."""
    dep_str = dep_str.strip()
    if not dep_str:
        return None

    if _is_git_dependency(dep_str):
        return _parse_git_dependency(dep_str, source)

    return _parse_pypi_dependency(dep_str, source)


def _is_git_dependency(dep_str: str) -> bool:
    """Check if a dependency string is a git dependency."""
    return any(prefix in dep_str.lower() for prefix in ["git+", "git://", "@git+"])


def _parse_pypi_dependency(dep_str: str, source: str) -> DependencyInfo | None:
    """Parse a PyPI dependency string."""
    # Handle Poetry-style parentheses: "package (>=1.0)"
    dep_str = dep_str.replace(" (", "(").replace("( ", "(")

    # Split by semicolon to get markers
    marker_parts = dep_str.split(";", 1)
    spec_part = marker_parts[0].strip()
    python_markers = marker_parts[1].strip() if len(marker_parts) > 1 else None

    name, extras, version_constraints = _parse_spec_part(spec_part)
    if not name:
        return None

    return DependencyInfo(
        name=_normalize_package_name(name),
        raw_spec=dep_str,
        version_constraints=version_constraints,
        python_markers=python_markers,
        extras=extras,
        source=source,
        is_git_dependency=False,
        git_url=None,
        git_ref=None,
    )


def _parse_spec_part(spec: str) -> tuple[str, list[str], str]:
    """Parse the specification part (name[extras]version).

    Args:
        spec: The specification string like "package[extra]>=1.0".

    Returns:
        Tuple of (name, extras, version_constraints).
    """
    # Handle Poetry parentheses format: name (>=1.0)
    poetry_match = _RE_POETRY_SPEC.match(spec)
    if poetry_match:
        name = poetry_match.group(1)
        extras_str = poetry_match.group(2) or ""
        version = poetry_match.group(3)
        extras = [e.strip() for e in extras_str.split(",") if e.strip()]
        return name, extras, version

    # Standard format: name[extras]>=version
    # Match name and optional extras first
    main_match = _RE_STANDARD_SPEC.match(spec)
    if not main_match:
        return "", [], ""

    name = main_match.group(1)
    extras_str = main_match.group(2) or ""
    version_part = main_match.group(3).strip()

    extras = [e.strip() for e in extras_str.split(",") if e.strip()]

    # Extract version constraints (everything after the name/extras)
    version_constraints = version_part.strip()

    return name, extras, version_constraints


def _parse_git_dependency(dep_str: str, source: str) -> DependencyInfo:
    """Parse a git dependency specification (git+url or package @ git+url)."""
    name, git_url = _extract_git_name_and_url(dep_str)
    git_url, git_ref = _extract_git_ref(git_url)

    if not name and git_url:
        name = _extract_repo_name_from_url(git_url)

    return DependencyInfo(
        name=_normalize_package_name(name) if name else "unknown",
        raw_spec=dep_str,
        version_constraints="",
        python_markers=None,
        extras=[],
        source=source,
        is_git_dependency=True,
        git_url=git_url,
        git_ref=git_ref,
    )


def _extract_git_name_and_url(dep_str: str) -> tuple[str, str | None]:
    """Extract package name and git URL from dependency string."""
    at_match = _RE_GIT_NAME_URL.match(dep_str)
    if at_match:
        return at_match.group(1), at_match.group(2).strip()
    return "", dep_str


def _extract_git_ref(git_url: str | None) -> tuple[str | None, str | None]:
    """Extract URL and ref (branch/tag) from git URL."""
    if not git_url:
        return None, None
    url_ref_match = _RE_GIT_REF.match(git_url)
    if url_ref_match:
        return url_ref_match.group(1), url_ref_match.group(2)
    return git_url, None


def _extract_repo_name_from_url(git_url: str) -> str:
    """Extract repository name from git URL."""
    repo_match = _RE_REPO_NAME.search(git_url)
    return repo_match.group(1) if repo_match else ""


def _extract_from_list(deps: list[Any], source: str) -> list[DependencyInfo]:
    """Extract dependencies from a list of strings.

    Args:
        deps: List of dependency specifications.
        source: The source section name.

    Returns:
        List of parsed dependencies.
    """
    result: list[DependencyInfo] = []
    for dep in deps:
        if isinstance(dep, str):
            parsed = _parse_dependency_string(dep, source)
            if parsed:
                result.append(parsed)
    return result


def _poetry_git_to_dependency(
    name: str,
    spec_dict: dict[str, Any],
    poetry_spec: PoetryDependencySpec,
    source: str,
) -> DependencyInfo:
    """Convert Poetry git spec to DependencyInfo."""
    git_ref = poetry_spec.rev or poetry_spec.tag or poetry_spec.branch
    return DependencyInfo(
        name=_normalize_package_name(name),
        raw_spec=str(spec_dict),
        version_constraints="",
        python_markers=poetry_spec.python,
        extras=list(poetry_spec.extras),
        source=source,
        is_git_dependency=True,
        git_url=poetry_spec.git,
        git_ref=git_ref,
    )


def _poetry_version_to_dependency(
    name: str,
    poetry_spec: PoetryDependencySpec,
    source: str,
) -> DependencyInfo:
    """Convert Poetry version spec to DependencyInfo."""
    constraint = poetry_spec.version
    if constraint:
        # Handle Poetry ^ and ~ operators
        constraint = constraint.replace("^", ">=")
    return DependencyInfo(
        name=_normalize_package_name(name),
        raw_spec=f"{name}{poetry_spec.version}" if poetry_spec.version else name,
        version_constraints=constraint,
        python_markers=poetry_spec.python,
        extras=list(poetry_spec.extras),
        source=source,
        is_git_dependency=False,
        git_url=None,
        git_ref=None,
    )


def _parse_poetry_dict_spec(name: str, spec_dict: dict[str, Any], source: str) -> DependencyInfo:
    """Parse a Poetry dict-style dependency specification."""
    poetry_spec = PoetryDependencySpec.model_validate(spec_dict)

    if poetry_spec.git:
        return _poetry_git_to_dependency(name, spec_dict, poetry_spec, source)
    return _poetry_version_to_dependency(name, poetry_spec, source)


def _parse_dict_item(name: str, spec: Any, source: str) -> DependencyInfo | None:
    """Parse a single dict item to DependencyInfo."""
    if isinstance(spec, str):
        return _parse_dependency_string(f"{name}{spec}", source)
    if isinstance(spec, dict):
        spec_dict = cast(dict[str, Any], spec)
        return _parse_poetry_dict_spec(name, spec_dict, source)
    return None


def _extract_from_dict(deps: dict[str, Any], source: str) -> list[DependencyInfo]:
    """Extract dependencies from a dict (Poetry/PDM style).

    Handles formats like:
    - {"requests": "^2.0"}
    - {"numpy": {"version": ">=1.0", "python": "<3.12"}}
    - {"optional-dep": {"version": ">=1.0", "optional": true}}

    Args:
        deps: Dictionary of dependencies.
        source: The source section name.

    Returns:
        List of parsed dependencies.
    """
    result: list[DependencyInfo] = []

    for name, spec in deps.items():
        if name.lower() == "python":
            continue
        parsed = _parse_dict_item(name, spec, source)
        if parsed:
            result.append(parsed)

    return result


def _extract_poetry_groups(data: dict[str, Any]) -> list[DependencyInfo]:
    """Extract dependencies from Poetry group definitions.

    Args:
        data: The full pyproject.toml data.

    Returns:
        List of dependencies from all Poetry groups.
    """
    result: list[DependencyInfo] = []
    groups = _get_nested(data, "tool.poetry.group")
    if not isinstance(groups, dict):
        return result

    for group_name, group_data in cast("dict[str, Any]", groups).items():
        if isinstance(group_data, dict) and "dependencies" in group_data:
            deps = cast("dict[str, Any] | list[str]", group_data["dependencies"])
            source = f"tool.poetry.group.{str(group_name)}.dependencies"
            if isinstance(deps, dict):
                result.extend(_extract_from_dict(deps, source))
            else:
                result.extend(_extract_from_list(deps, source))

    return result


def _extract_hatch_envs(data: dict[str, Any]) -> list[DependencyInfo]:
    """Extract dependencies from Hatch environment definitions.

    Args:
        data: The full pyproject.toml data.

    Returns:
        List of dependencies from all Hatch environments.
    """
    result: list[DependencyInfo] = []
    envs = _get_nested(data, "tool.hatch.envs")
    if not isinstance(envs, dict):
        return result

    for env_name, env_data in cast("dict[str, Any]", envs).items():
        if isinstance(env_data, dict) and "dependencies" in env_data:
            deps = cast("list[str]", env_data["dependencies"])
            source = f"tool.hatch.envs.{str(env_name)}.dependencies"
            result.extend(_extract_from_list(deps, source))

    return result


def _extract_dependency_groups(data: dict[str, Any]) -> list[DependencyInfo]:
    """Extract dependencies from PEP 735 dependency-groups.

    Args:
        data: The full pyproject.toml data.

    Returns:
        List of dependencies from all dependency groups.
    """
    result: list[DependencyInfo] = []
    groups = data.get("dependency-groups")
    if not isinstance(groups, dict):
        return result

    for group_name, deps in cast("dict[str, Any]", groups).items():
        source = f"dependency-groups.{str(group_name)}"
        if isinstance(deps, list):
            result.extend(_extract_from_list(cast("list[str]", deps), source))

    return result


def _extract_optional_dependencies(data: dict[str, Any]) -> list[DependencyInfo]:
    """Extract dependencies from project.optional-dependencies.

    Args:
        data: The full pyproject.toml data.

    Returns:
        List of optional dependencies.
    """
    result: list[DependencyInfo] = []
    optional = _get_nested(data, "project.optional-dependencies")
    if not isinstance(optional, dict):
        return result

    for extra_name, deps in cast("dict[str, Any]", optional).items():
        source = f"project.optional-dependencies.{str(extra_name)}"
        if isinstance(deps, list):
            result.extend(_extract_from_list(cast("list[str]", deps), source))

    return result


def _extract_from_path(data: dict[str, Any], path: str, source: DependencySource) -> list[DependencyInfo]:
    """Extract dependencies from a nested path."""
    nested = _get_nested(data, path)
    if isinstance(nested, list):
        return _extract_from_list(cast("list[str]", nested), source.value)
    if isinstance(nested, dict):
        return _extract_from_dict(cast("dict[str, Any]", nested), source.value)
    return []


def _extract_poetry_deps(data: dict[str, Any]) -> list[DependencyInfo]:
    """Extract all Poetry-style dependencies."""
    result: list[DependencyInfo] = []
    result.extend(_extract_from_path(data, "tool.poetry.dependencies", DependencySource.POETRY_DEPS))
    result.extend(_extract_from_path(data, "tool.poetry.dev-dependencies", DependencySource.POETRY_DEV))
    result.extend(_extract_poetry_groups(data))
    return result


def _extract_pdm_deps(data: dict[str, Any]) -> list[DependencyInfo]:
    """Extract all PDM-style dependencies."""
    result: list[DependencyInfo] = []
    result.extend(_extract_from_path(data, "tool.pdm.dependencies", DependencySource.PDM_DEPS))
    result.extend(_extract_from_path(data, "tool.pdm.dev-dependencies", DependencySource.PDM_DEV))
    return result


def extract_dependencies(data: dict[str, Any]) -> list[DependencyInfo]:
    """Extract all dependencies from a parsed pyproject.toml.

    Args:
        data: Parsed pyproject.toml content.

    Returns:
        List of all dependencies found in the file.
    """
    result: list[DependencyInfo] = []

    # Standard PEP 621
    result.extend(_extract_from_path(data, "project.dependencies", DependencySource.PROJECT_DEPENDENCIES))
    result.extend(_extract_optional_dependencies(data))
    result.extend(_extract_from_path(data, "build-system.requires", DependencySource.BUILD_REQUIRES))

    # Build tool dependencies
    result.extend(_extract_poetry_deps(data))
    result.extend(_extract_pdm_deps(data))
    result.extend(_extract_from_path(data, "tool.hatch.metadata.dependencies", DependencySource.HATCH_DEPS))
    result.extend(_extract_hatch_envs(data))
    result.extend(_extract_from_path(data, "tool.flit.metadata.requires", DependencySource.FLIT_REQUIRES))

    # PEP 735 dependency-groups
    result.extend(_extract_dependency_groups(data))

    logger.debug("Extracted %d dependencies from pyproject.toml", len(result))
    return result


def get_requires_python(data: dict[str, Any]) -> str | None:
    """Get the requires-python value from pyproject.toml.

    Args:
        data: Parsed pyproject.toml content.

    Returns:
        The requires-python value or None if not specified.
    """
    return _get_nested(data, "project.requires-python")


__all__ = [
    "DependencySource",
    "extract_dependencies",
    "get_requires_python",
    "load_pyproject",
]
