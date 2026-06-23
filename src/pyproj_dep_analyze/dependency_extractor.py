"""Extractor for dependencies from pyproject.toml files.

Purpose
-------
Extract all dependencies from various sections of a pyproject.toml file,
supporting multiple build systems (poetry, pdm, hatch, setuptools).

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
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Any

import rtoml

from .models import DependencyInfo, DependencyMarker, GitProtocol
from .schemas import PoetryDependencySpec, PyprojectSchema

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
    SETUPTOOLS_DYNAMIC = "tool.setuptools.dynamic.dependencies"
    DEPENDENCY_GROUPS = "dependency-groups"


def _load_pyproject_raw(path: Path | str) -> dict[str, Any]:
    """Load and parse a pyproject.toml file as raw dict (INTERNAL ONLY).

    Internal function for backward compatibility. Use load_pyproject()
    for validated Pydantic model.

    Args:
        path: Path to the pyproject.toml file.

    Returns:
        Parsed TOML content as raw dict.

    Raises:
        FileNotFoundError: If the file does not exist.
        rtoml.TomlParsingError: If the file is not valid TOML.
    """
    path = Path(path)
    return rtoml.load(path)


def load_pyproject(path: Path | str) -> PyprojectSchema:
    """Load and parse a pyproject.toml file into validated schema.

    This is the primary entry point for loading pyproject files. It parses
    the TOML at the system boundary and returns a validated Pydantic model.

    Args:
        path: Path to the pyproject.toml file.

    Returns:
        Validated PyprojectSchema instance.

    Raises:
        FileNotFoundError: If the file does not exist.
        rtoml.TomlParsingError: If the file is not valid TOML.
        pydantic.ValidationError: If the TOML doesn't match expected schema.
    """
    raw_data = _load_pyproject_raw(path)
    return PyprojectSchema.model_validate(raw_data)


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
    """Check if a dependency string is a git dependency.

    Uses GitProtocol enum to check for known git protocol prefixes.
    """
    dep_lower = dep_str.lower()
    return any(prefix.value in dep_lower for prefix in GitProtocol)


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


def _extract_from_list(deps: list[str], source: str) -> list[DependencyInfo]:
    """Extract dependencies from a list of strings.

    Args:
        deps: List of dependency specifications (strings only).
        source: The source section name.

    Returns:
        List of parsed dependencies.
    """
    result: list[DependencyInfo] = []
    for dep in deps:
        parsed = _parse_dependency_string(dep, source)
        if parsed:
            result.append(parsed)
    return result


def _poetry_git_to_dependency(
    name: str,
    poetry_spec: PoetryDependencySpec,
    source: str,
) -> DependencyInfo:
    """Convert Poetry git spec to DependencyInfo."""
    git_ref = poetry_spec.rev or poetry_spec.tag or poetry_spec.branch
    raw_spec = f"{name}@git+{poetry_spec.git}" + (f"@{git_ref}" if git_ref else "")
    return DependencyInfo(
        name=_normalize_package_name(name),
        raw_spec=raw_spec,
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


def _parse_poetry_validated_spec(name: str, poetry_spec: PoetryDependencySpec, source: str) -> DependencyInfo:
    """Parse a validated Poetry dependency specification.

    Args:
        name: The dependency name.
        poetry_spec: Validated Poetry dependency specification.
        source: The source section name.

    Returns:
        Parsed DependencyInfo.
    """
    if poetry_spec.git:
        return _poetry_git_to_dependency(name, poetry_spec, source)
    return _poetry_version_to_dependency(name, poetry_spec, source)


def _parse_dict_item(
    name: str,
    spec: str | dict[str, str | list[str] | bool | None] | list[dict[str, str | list[str] | bool | None]],
    source: str,
) -> DependencyInfo | None:
    """Parse a single dict item to DependencyInfo.

    Handles Poetry/PDM dependency specifications:
    - String: "^2.0"
    - Dict: {version = ">=1.0", python = "<3.12"}
    - List of dicts: [{version = ">=1.0", python = "<3.10"}, {version = ">=2.0", python = ">=3.10"}]

    Validates at the boundary before passing to internal functions.

    Note: isinstance checks are necessary here for runtime type discrimination
    since the spec parameter is a union type that cannot be statically determined.
    """
    if isinstance(spec, str):
        return _parse_dependency_string(f"{name}{spec}", source)
    if isinstance(spec, dict):
        # Validate at boundary before passing to internal function
        poetry_spec = PoetryDependencySpec.model_validate(spec)
        return _parse_poetry_validated_spec(name, poetry_spec, source)
    # spec is list[dict[...]] - for list of constraint dicts, use the first one
    # (Poetry uses these for python-version-specific constraints)
    if spec:
        poetry_spec = PoetryDependencySpec.model_validate(spec[0])
        return _parse_poetry_validated_spec(name, poetry_spec, source)
    return None


def _extract_poetry_groups_from_schema(data: PyprojectSchema) -> list[DependencyInfo]:
    """Extract dependencies from Poetry group definitions.

    Args:
        data: The validated pyproject.toml schema.

    Returns:
        List of dependencies from all Poetry groups.
    """
    result: list[DependencyInfo] = []
    groups = data.tool.poetry.group

    for group_name, group_schema in groups.items():
        source = f"tool.poetry.group.{group_name}.dependencies"
        # Access dependencies through the schema field
        for dep_name, dep_spec in group_schema.dependencies.items():
            if dep_name.lower() == DependencyMarker.PYTHON.value:
                continue
            parsed = _parse_dict_item(dep_name, dep_spec, source)
            if parsed:
                result.append(parsed)

    return result


def _extract_hatch_envs_from_schema(data: PyprojectSchema) -> list[DependencyInfo]:
    """Extract dependencies from Hatch environment definitions.

    Args:
        data: The validated pyproject.toml schema.

    Returns:
        List of dependencies from all Hatch environments.
    """
    result: list[DependencyInfo] = []
    envs = data.tool.hatch.envs

    for env_name, env_schema in envs.items():
        source = f"tool.hatch.envs.{env_name}.dependencies"
        result.extend(_extract_from_list(env_schema.dependencies, source))

    return result


def _extract_dependency_groups_from_schema(data: PyprojectSchema) -> list[DependencyInfo]:
    """Extract dependencies from PEP 735 dependency-groups.

    Args:
        data: The validated pyproject.toml schema.

    Returns:
        List of dependencies from all dependency groups.

    Note: isinstance checks are necessary here for runtime type discrimination
    because dependency-groups can contain either string specs or IncludeGroupSchema
    objects, which cannot be statically determined.
    """
    from .schemas import IncludeGroupSchema

    result: list[DependencyInfo] = []

    for group_name, deps in data.dependency_groups.items():
        source = f"dependency-groups.{group_name}"
        # Filter out include-group references, only process string dependencies
        string_deps = [d for d in deps if isinstance(d, str)]
        result.extend(_extract_from_list(string_deps, source))
        # Log or skip IncludeGroupSchema references (they're resolved at install time)
        for dep in deps:
            if isinstance(dep, IncludeGroupSchema):
                logger.debug("Skipping include-group reference: %s", dep.include_group)

    return result


def _extract_optional_dependencies_from_schema(data: PyprojectSchema) -> list[DependencyInfo]:
    """Extract dependencies from project.optional-dependencies.

    Args:
        data: The validated pyproject.toml schema.

    Returns:
        List of optional dependencies.
    """
    result: list[DependencyInfo] = []

    for extra_name, deps in data.project.optional_dependencies.items():
        source = f"project.optional-dependencies.{extra_name}"
        result.extend(_extract_from_list(deps, source))

    return result


def _extract_poetry_deps_from_schema(data: PyprojectSchema) -> list[DependencyInfo]:
    """Extract all Poetry-style dependencies from schema."""
    result: list[DependencyInfo] = []

    # Main dependencies
    for name, spec in data.tool.poetry.dependencies.items():
        if name.lower() == DependencyMarker.PYTHON.value:
            continue
        parsed = _parse_dict_item(name, spec, DependencySource.POETRY_DEPS.value)
        if parsed:
            result.append(parsed)

    # Dev dependencies
    for name, spec in data.tool.poetry.dev_dependencies.items():
        if name.lower() == DependencyMarker.PYTHON.value:
            continue
        parsed = _parse_dict_item(name, spec, DependencySource.POETRY_DEV.value)
        if parsed:
            result.append(parsed)

    # Group dependencies
    result.extend(_extract_poetry_groups_from_schema(data))

    return result


def _extract_pdm_deps_from_schema(data: PyprojectSchema) -> list[DependencyInfo]:
    """Extract all PDM-style dependencies from schema."""
    result: list[DependencyInfo] = []

    # Main dependencies
    for name, spec in data.tool.pdm.dependencies.items():
        if name.lower() == DependencyMarker.PYTHON.value:
            continue
        parsed = _parse_dict_item(name, spec, DependencySource.PDM_DEPS.value)
        if parsed:
            result.append(parsed)

    # Dev dependencies - can be either dict of name:spec or dict of group:list[str]
    # isinstance checks necessary for runtime type discrimination of PDM's flexible format
    for name, dev_spec in data.tool.pdm.dev_dependencies.items():
        if name.lower() == DependencyMarker.PYTHON.value:
            continue
        # Check if spec is a list (PDM dev-dependency group style)
        if isinstance(dev_spec, list):
            source = f"tool.pdm.dev-dependencies.{name}"
            result.extend(_extract_from_list(dev_spec, source))
        else:
            # String or dict spec - handle as normal dependency
            parsed = _parse_dict_item(name, dev_spec, DependencySource.PDM_DEV.value)
            if parsed:
                result.append(parsed)

    return result


def extract_dependencies(data: PyprojectSchema) -> list[DependencyInfo]:
    """Extract all dependencies from a validated pyproject.toml schema.

    Args:
        data: Validated PyprojectSchema instance.

    Returns:
        List of all dependencies found in the file.
    """
    result: list[DependencyInfo] = []

    # Standard PEP 621
    result.extend(_extract_from_list(list(data.project.dependencies), DependencySource.PROJECT_DEPENDENCIES.value))
    result.extend(_extract_optional_dependencies_from_schema(data))
    result.extend(_extract_from_list(list(data.build_system.requires), DependencySource.BUILD_REQUIRES.value))

    # Build tool dependencies
    result.extend(_extract_poetry_deps_from_schema(data))
    result.extend(_extract_pdm_deps_from_schema(data))
    result.extend(_extract_from_list(list(data.tool.hatch.metadata.dependencies), DependencySource.HATCH_DEPS.value))
    result.extend(_extract_hatch_envs_from_schema(data))

    # PEP 735 dependency-groups
    result.extend(_extract_dependency_groups_from_schema(data))

    logger.debug("Extracted %d dependencies from pyproject.toml", len(result))
    return result


def get_requires_python(data: PyprojectSchema) -> str | None:
    """Get the requires-python value from pyproject.toml schema.

    Args:
        data: Validated PyprojectSchema instance.

    Returns:
        The requires-python value or None if not specified.
    """
    return data.project.requires_python


__all__ = [
    "DependencySource",
    "extract_dependencies",
    "get_requires_python",
    "load_pyproject",
]
