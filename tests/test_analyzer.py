"""Analyzer module stories: each test reveals one truth.

The dependency analyzer transforms pyproject.toml configurations into
actionable insights. These tests verify that each component speaks
its single purpose clearly.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from pyproj_dep_analyse.models import (
    Action,
    AnalysisResult,
    DependencyInfo,
    KNOWN_PYTHON_VERSIONS,
    OutdatedEntry,
    PythonVersion,
)
from pyproj_dep_analyse.schemas import OutdatedEntrySchema
from pyproj_dep_analyse.python_version_parser import (
    VersionConstraint,
    parse_requires_python,
    version_satisfies,
)
from pyproj_dep_analyse.dependency_extractor import (
    extract_dependencies,
    get_requires_python,
    load_pyproject,
)
from pyproj_dep_analyse.analyzer import (
    Analyzer,
    analyze_pyproject,
    create_analyzer,
    determine_action,
    entry_to_dict,
    run_analysis,
    write_outdated_json,
    _count_actions,  # pyright: ignore[reportPrivateUsage]
    _dependency_applies_to_python_version,  # pyright: ignore[reportPrivateUsage]
    _determine_git_action,  # pyright: ignore[reportPrivateUsage]
    _determine_pypi_action,  # pyright: ignore[reportPrivateUsage]
    _generate_entries,  # pyright: ignore[reportPrivateUsage]
    _parse_version_constraint_minimum,  # pyright: ignore[reportPrivateUsage]
    _version_is_greater,  # pyright: ignore[reportPrivateUsage]
    _version_tuple,  # pyright: ignore[reportPrivateUsage]
)
from pyproj_dep_analyse.version_resolver import (
    VersionResolver,
    VersionResult,
    _extract_version_from_tag,  # pyright: ignore[reportPrivateUsage]
    _parse_github_url,  # pyright: ignore[reportPrivateUsage]
)


TESTDATA_DIR = Path(__file__).parent / "testdata"


# ════════════════════════════════════════════════════════════════════════════
# PythonVersion: The numeric heartbeat of version comparisons
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.os_agnostic
def test_python_version_stores_major_and_minor_components() -> None:
    version = PythonVersion(3, 11)

    assert version.major == 3
    assert version.minor == 11


@pytest.mark.os_agnostic
def test_python_version_renders_as_dot_separated_string() -> None:
    version = PythonVersion(3, 12)

    assert str(version) == "3.12"


@pytest.mark.os_agnostic
def test_python_version_compares_less_than_correctly() -> None:
    assert PythonVersion(3, 9) < PythonVersion(3, 10)


@pytest.mark.os_agnostic
def test_python_version_compares_greater_than_correctly() -> None:
    assert PythonVersion(3, 11) > PythonVersion(3, 10)


@pytest.mark.os_agnostic
def test_python_version_compares_equal_correctly() -> None:
    assert PythonVersion(3, 10) == PythonVersion(3, 10)


@pytest.mark.os_agnostic
def test_python_version_compares_less_equal_correctly() -> None:
    assert PythonVersion(3, 10) <= PythonVersion(3, 10)
    assert PythonVersion(3, 9) <= PythonVersion(3, 10)


@pytest.mark.os_agnostic
def test_python_version_compares_greater_equal_correctly() -> None:
    assert PythonVersion(3, 10) >= PythonVersion(3, 10)
    assert PythonVersion(3, 11) >= PythonVersion(3, 10)


@pytest.mark.os_agnostic
def test_python_version_compares_not_equal_correctly() -> None:
    assert PythonVersion(3, 9) != PythonVersion(3, 11)


@pytest.mark.os_agnostic
def test_python_version_parses_two_part_string() -> None:
    version = PythonVersion.from_string("3.11")

    assert version.major == 3
    assert version.minor == 11


@pytest.mark.os_agnostic
def test_python_version_parses_three_part_string_ignoring_patch() -> None:
    version = PythonVersion.from_string("3.12.1")

    assert version.major == 3
    assert version.minor == 12


@pytest.mark.os_agnostic
def test_python_version_rejects_single_number() -> None:
    with pytest.raises(ValueError, match="Invalid Python version format"):
        PythonVersion.from_string("3")


@pytest.mark.os_agnostic
def test_python_version_rejects_non_numeric_string() -> None:
    with pytest.raises(ValueError):
        PythonVersion.from_string("invalid")


@pytest.mark.os_agnostic
def test_python_version_comparison_with_incompatible_type_returns_not_implemented() -> None:
    version = PythonVersion(3, 11)

    assert version.__lt__("not a version") == NotImplemented
    assert version.__gt__("not a version") == NotImplemented
    assert version.__le__("not a version") == NotImplemented
    assert version.__ge__("not a version") == NotImplemented


# ════════════════════════════════════════════════════════════════════════════
# OutdatedEntry: The data carrier of dependency analysis
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.os_agnostic
def test_outdated_entry_stores_all_fields() -> None:
    entry = OutdatedEntry(
        package="requests",
        python_version="3.11",
        current_version="2.28.0",
        latest_version="2.31.0",
        action=Action.UPDATE,
    )

    assert entry.package == "requests"
    assert entry.python_version == "3.11"
    assert entry.current_version == "2.28.0"
    assert entry.latest_version == "2.31.0"
    assert entry.action == Action.UPDATE


@pytest.mark.os_agnostic
def test_outdated_entry_is_immutable() -> None:
    entry = OutdatedEntry("pkg", "3.11", "1.0", "2.0", Action.UPDATE)

    with pytest.raises(AttributeError):
        entry.package = "new"  # type: ignore[misc]


@pytest.mark.os_agnostic
def test_outdated_entry_serializes_to_pydantic_schema() -> None:
    entry = OutdatedEntry(
        package="numpy",
        python_version="3.10",
        current_version="1.24.0",
        latest_version="1.26.0",
        action=Action.UPDATE,
    )

    schema = OutdatedEntrySchema(
        package=entry.package,
        python_version=entry.python_version,
        current_version=entry.current_version,
        latest_version=entry.latest_version,
        action=entry.action,
    )
    data = schema.model_dump()

    assert data["package"] == "numpy"
    assert data["action"] == "update"


@pytest.mark.os_agnostic
def test_outdated_entry_serializes_none_values_correctly() -> None:
    entry = OutdatedEntry(
        package="unknown",
        python_version="3.11",
        current_version=None,
        latest_version="unknown",
        action=Action.CHECK_MANUALLY,
    )

    schema = OutdatedEntrySchema(
        package=entry.package,
        python_version=entry.python_version,
        current_version=entry.current_version,
        latest_version=entry.latest_version,
        action=entry.action,
    )
    data = schema.model_dump()

    assert data["current_version"] is None


# ════════════════════════════════════════════════════════════════════════════
# Action: The vocabulary of recommendations
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.os_agnostic
def test_action_update_has_value_update() -> None:
    assert Action.UPDATE.value == "update"


@pytest.mark.os_agnostic
def test_action_delete_has_value_delete() -> None:
    assert Action.DELETE.value == "delete"


@pytest.mark.os_agnostic
def test_action_none_has_value_none() -> None:
    assert Action.NONE.value == "none"


@pytest.mark.os_agnostic
def test_action_check_manually_has_value_check_manually() -> None:
    assert Action.CHECK_MANUALLY.value == "check manually"


# ════════════════════════════════════════════════════════════════════════════
# parse_requires_python: The gatekeeper of Python compatibility
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.os_agnostic
def test_requires_python_includes_versions_at_or_above_minimum() -> None:
    versions = parse_requires_python(">=3.9")

    assert PythonVersion(3, 9) in versions
    assert PythonVersion(3, 10) in versions
    assert PythonVersion(3, 11) in versions


@pytest.mark.os_agnostic
def test_requires_python_excludes_versions_below_minimum() -> None:
    versions = parse_requires_python(">=3.9")

    assert PythonVersion(3, 8) not in versions


@pytest.mark.os_agnostic
def test_requires_python_respects_upper_bound() -> None:
    versions = parse_requires_python(">=3.10,<3.12")

    assert PythonVersion(3, 10) in versions
    assert PythonVersion(3, 11) in versions
    assert PythonVersion(3, 12) not in versions


@pytest.mark.os_agnostic
def test_requires_python_respects_lower_bound_in_range() -> None:
    versions = parse_requires_python(">=3.10,<3.12")

    assert PythonVersion(3, 9) not in versions


@pytest.mark.os_agnostic
def test_requires_python_matches_exact_version() -> None:
    versions = parse_requires_python("==3.11")

    assert versions == [PythonVersion(3, 11)]


@pytest.mark.os_agnostic
def test_requires_python_excludes_not_equal_version() -> None:
    versions = parse_requires_python(">=3.10,!=3.11")

    assert PythonVersion(3, 10) in versions
    assert PythonVersion(3, 11) not in versions
    assert PythonVersion(3, 12) in versions


@pytest.mark.os_agnostic
def test_requires_python_compatible_release_includes_same_major() -> None:
    versions = parse_requires_python("~=3.10")

    assert PythonVersion(3, 10) in versions
    assert PythonVersion(3, 11) in versions
    assert PythonVersion(3, 9) not in versions


@pytest.mark.os_agnostic
def test_requires_python_none_returns_all_known_versions() -> None:
    versions = parse_requires_python(None)

    assert len(versions) == len(KNOWN_PYTHON_VERSIONS)


@pytest.mark.os_agnostic
def test_requires_python_empty_string_returns_all_known_versions() -> None:
    versions = parse_requires_python("")

    assert len(versions) == len(KNOWN_PYTHON_VERSIONS)


@pytest.mark.os_agnostic
def test_requires_python_unparseable_returns_all_known_versions() -> None:
    versions = parse_requires_python("this-is-not-valid")

    assert len(versions) == len(KNOWN_PYTHON_VERSIONS)


@pytest.mark.os_agnostic
def test_requires_python_greater_than_excludes_boundary() -> None:
    versions = parse_requires_python(">3.10")

    assert PythonVersion(3, 10) not in versions
    assert PythonVersion(3, 11) in versions


@pytest.mark.os_agnostic
def test_requires_python_less_equal_includes_boundary() -> None:
    versions = parse_requires_python("<=3.10")

    assert PythonVersion(3, 10) in versions
    assert PythonVersion(3, 11) not in versions


@pytest.mark.os_agnostic
def test_version_constraint_dataclass_stores_operator_and_version() -> None:
    constraint = VersionConstraint(operator=">=", version=PythonVersion(3, 10))

    assert constraint.operator == ">="
    assert constraint.version == PythonVersion(3, 10)


@pytest.mark.os_agnostic
def test_version_satisfies_checks_all_constraints() -> None:
    constraints = [
        VersionConstraint(operator=">=", version=PythonVersion(3, 9)),
        VersionConstraint(operator="<", version=PythonVersion(3, 12)),
    ]

    assert version_satisfies(PythonVersion(3, 10), constraints)
    assert not version_satisfies(PythonVersion(3, 8), constraints)
    assert not version_satisfies(PythonVersion(3, 12), constraints)


# ════════════════════════════════════════════════════════════════════════════
# Dependency Extractor: The archaeologist of pyproject.toml
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.os_agnostic
def test_load_pyproject_parses_toml_file() -> None:
    data = load_pyproject(TESTDATA_DIR / "pyproject_fastapi_fastapi.toml")

    assert "project" in data
    assert data["project"]["name"] == "fastapi"


@pytest.mark.os_agnostic
def test_load_pyproject_raises_on_missing_file() -> None:
    with pytest.raises(FileNotFoundError):
        load_pyproject(TESTDATA_DIR / "nonexistent.toml")


@pytest.mark.os_agnostic
def test_get_requires_python_extracts_version_constraint() -> None:
    data = load_pyproject(TESTDATA_DIR / "pyproject_fastapi_fastapi.toml")

    requires = get_requires_python(data)

    assert requires == ">=3.8"


@pytest.mark.os_agnostic
def test_get_requires_python_returns_none_when_absent() -> None:
    data: dict[str, Any] = {"project": {"name": "test"}}

    requires = get_requires_python(data)

    assert requires is None


@pytest.mark.os_agnostic
def test_extract_dependencies_finds_pep621_dependencies() -> None:
    data = load_pyproject(TESTDATA_DIR / "pyproject_fastapi_fastapi.toml")

    deps = extract_dependencies(data)
    names = {d.name for d in deps}

    assert "starlette" in names
    assert "pydantic" in names


@pytest.mark.os_agnostic
def test_extract_dependencies_finds_poetry_dependencies() -> None:
    data = load_pyproject(TESTDATA_DIR / "pyproject_python-poetry_poetry.toml")

    deps = extract_dependencies(data)
    names = {d.name for d in deps}

    assert "poetry_core" in names or "cleo" in names


@pytest.mark.os_agnostic
def test_extract_dependencies_finds_optional_dependencies() -> None:
    data = load_pyproject(TESTDATA_DIR / "pyproject_fastapi_fastapi.toml")

    deps = extract_dependencies(data)
    sources = {d.source for d in deps}

    assert any("optional-dependencies" in s for s in sources)


@pytest.mark.os_agnostic
def test_extract_dependencies_finds_build_requires() -> None:
    data = load_pyproject(TESTDATA_DIR / "pyproject_pytorch_pytorch.toml")

    deps = extract_dependencies(data)
    sources = {d.source for d in deps}

    assert "build-system.requires" in sources


@pytest.mark.os_agnostic
def test_extract_dependencies_finds_dependency_groups() -> None:
    data = load_pyproject(TESTDATA_DIR / "pyproject_pytorch_pytorch.toml")

    deps = extract_dependencies(data)
    sources = {d.source for d in deps}

    assert any("dependency-groups" in s for s in sources)


@pytest.mark.os_agnostic
def test_extract_dependencies_finds_poetry_groups() -> None:
    data = load_pyproject(TESTDATA_DIR / "pyproject_python-poetry_poetry.toml")

    deps = extract_dependencies(data)
    sources = {d.source for d in deps}

    assert any("tool.poetry.group" in s for s in sources)


@pytest.mark.os_agnostic
def test_extract_dependencies_captures_python_markers() -> None:
    data = load_pyproject(TESTDATA_DIR / "pyproject_python-poetry_poetry.toml")

    deps = extract_dependencies(data)
    marker_deps = [d for d in deps if d.python_markers]

    assert len(marker_deps) > 0


@pytest.mark.os_agnostic
def test_extract_dependencies_captures_extras() -> None:
    data = load_pyproject(TESTDATA_DIR / "pyproject_python-poetry_poetry.toml")

    deps = extract_dependencies(data)

    assert any("cachecontrol" in d.name or "filecache" in str(d.extras) for d in deps)


@pytest.mark.os_agnostic
def test_extract_dependencies_returns_empty_list_for_no_dependencies() -> None:
    data: dict[str, Any] = {"project": {"name": "empty", "version": "1.0.0"}}

    deps = extract_dependencies(data)

    assert len(deps) == 0


@pytest.mark.os_agnostic
def test_extract_dependencies_normalizes_package_names() -> None:
    data = {"project": {"dependencies": ["My-Package>=1.0"]}}

    deps = extract_dependencies(data)

    assert deps[0].name == "my_package"


@pytest.mark.os_agnostic
def test_extract_dependencies_identifies_git_dependencies() -> None:
    data = {"project": {"dependencies": ["mypackage @ git+https://github.com/user/repo.git"]}}

    deps = extract_dependencies(data)

    assert deps[0].is_git_dependency is True
    assert "github.com" in (deps[0].git_url or "")


# ════════════════════════════════════════════════════════════════════════════
# Version Constraint Parsing: The numerologist
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.os_agnostic
def test_parse_version_constraint_extracts_gte_minimum() -> None:
    result = _parse_version_constraint_minimum(">=1.0.0")

    assert result == "1.0.0"


@pytest.mark.os_agnostic
def test_parse_version_constraint_extracts_gte_two_parts() -> None:
    result = _parse_version_constraint_minimum(">=2.5")

    assert result == "2.5"


@pytest.mark.os_agnostic
def test_parse_version_constraint_extracts_equality() -> None:
    result = _parse_version_constraint_minimum("==1.2.3")

    assert result == "1.2.3"


@pytest.mark.os_agnostic
def test_parse_version_constraint_extracts_caret() -> None:
    result = _parse_version_constraint_minimum("^1.5.0")

    assert result == "1.5.0"


@pytest.mark.os_agnostic
def test_parse_version_constraint_extracts_tilde() -> None:
    result = _parse_version_constraint_minimum("~1.5.0")

    assert result == "1.5.0"


@pytest.mark.os_agnostic
def test_parse_version_constraint_extracts_from_range() -> None:
    result = _parse_version_constraint_minimum(">=1.0,<2.0")

    assert result == "1.0"


@pytest.mark.os_agnostic
def test_parse_version_constraint_returns_none_for_invalid() -> None:
    result = _parse_version_constraint_minimum("not-a-version")

    assert result is None


@pytest.mark.os_agnostic
def test_parse_version_constraint_returns_none_for_empty() -> None:
    result = _parse_version_constraint_minimum("")

    assert result is None


@pytest.mark.os_agnostic
def test_version_is_greater_compares_major_versions() -> None:
    assert _version_is_greater("2.0.0", "1.0.0")


@pytest.mark.os_agnostic
def test_version_is_greater_compares_minor_versions() -> None:
    assert _version_is_greater("1.1.0", "1.0.0")


@pytest.mark.os_agnostic
def test_version_is_greater_compares_patch_versions() -> None:
    assert _version_is_greater("1.0.1", "1.0.0")


@pytest.mark.os_agnostic
def test_version_is_greater_returns_false_when_less() -> None:
    assert not _version_is_greater("1.0.0", "2.0.0")


@pytest.mark.os_agnostic
def test_version_is_greater_returns_false_when_equal() -> None:
    assert not _version_is_greater("1.0.0", "1.0.0")


# ════════════════════════════════════════════════════════════════════════════
# GitHub URL Parsing: The cartographer of git addresses
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.os_agnostic
def test_parse_github_url_extracts_owner_and_repo_from_https() -> None:
    owner, repo = _parse_github_url("https://github.com/user/repo.git")

    assert owner == "user"
    assert repo == "repo"


@pytest.mark.os_agnostic
def test_parse_github_url_extracts_from_git_plus_https() -> None:
    owner, repo = _parse_github_url("git+https://github.com/user/repo.git")

    assert owner == "user"
    assert repo == "repo"


@pytest.mark.os_agnostic
def test_parse_github_url_extracts_from_ssh() -> None:
    owner, repo = _parse_github_url("git+ssh://git@github.com/user/repo.git")

    assert owner == "user"
    assert repo == "repo"


@pytest.mark.os_agnostic
def test_parse_github_url_strips_ref_from_url() -> None:
    owner, repo = _parse_github_url("git+https://github.com/user/repo.git@v1.0.0")

    assert owner == "user"
    assert repo == "repo"


@pytest.mark.os_agnostic
def test_parse_github_url_returns_none_for_non_github() -> None:
    owner, repo = _parse_github_url("https://gitlab.com/user/repo.git")

    assert owner is None
    assert repo is None


# ════════════════════════════════════════════════════════════════════════════
# Version Tag Extraction: The decoder of release names
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.os_agnostic
def test_extract_version_from_tag_strips_v_prefix() -> None:
    result = _extract_version_from_tag("v1.2.3")

    assert result == "1.2.3"


@pytest.mark.os_agnostic
def test_extract_version_from_tag_handles_no_prefix() -> None:
    result = _extract_version_from_tag("1.2.3")

    assert result == "1.2.3"


@pytest.mark.os_agnostic
def test_extract_version_from_tag_handles_release_prefix() -> None:
    result = _extract_version_from_tag("release-1.2.3")

    assert result == "1.2.3"


@pytest.mark.os_agnostic
def test_extract_version_from_tag_handles_version_prefix() -> None:
    result = _extract_version_from_tag("version-1.0.0")

    assert result == "1.0.0"


@pytest.mark.os_agnostic
def test_extract_version_from_tag_returns_none_for_non_version() -> None:
    assert _extract_version_from_tag("latest") is None
    assert _extract_version_from_tag("main") is None


@pytest.mark.os_agnostic
def test_extract_version_from_tag_returns_none_for_empty() -> None:
    assert _extract_version_from_tag("") is None


# ════════════════════════════════════════════════════════════════════════════
# determine_action: The oracle of dependency fate
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.os_agnostic
def test_determine_action_recommends_update_when_newer_exists() -> None:
    dep = DependencyInfo(
        name="requests",
        raw_spec="requests>=2.28.0",
        version_constraints=">=2.28.0",
    )
    version_result = VersionResult(latest_version="2.31.0")

    action, current, latest = determine_action(dep, PythonVersion(3, 11), version_result)

    assert action == Action.UPDATE
    assert current == "2.28.0"
    assert latest == "2.31.0"


@pytest.mark.os_agnostic
def test_determine_action_recommends_none_when_up_to_date() -> None:
    dep = DependencyInfo(
        name="requests",
        raw_spec="requests>=2.31.0",
        version_constraints=">=2.31.0",
    )
    version_result = VersionResult(latest_version="2.31.0")

    action, _, _ = determine_action(dep, PythonVersion(3, 11), version_result)

    assert action == Action.NONE


@pytest.mark.os_agnostic
def test_determine_action_recommends_delete_when_marker_excludes_version() -> None:
    dep = DependencyInfo(
        name="tomli",
        raw_spec="tomli>=1.0.0; python_version < '3.11'",
        version_constraints=">=1.0.0",
        python_markers="python_version < '3.11'",
    )
    version_result = VersionResult(latest_version="2.0.0")

    action, _, _ = determine_action(dep, PythonVersion(3, 11), version_result)

    assert action == Action.DELETE


@pytest.mark.os_agnostic
def test_determine_action_recommends_check_manually_when_unknown() -> None:
    dep = DependencyInfo(
        name="internal_package",
        raw_spec="internal_package",
        version_constraints="",
        is_git_dependency=True,
        git_url="https://github.com/internal/pkg",
    )
    version_result = VersionResult(is_unknown=True)

    action, _, _ = determine_action(dep, PythonVersion(3, 11), version_result)

    assert action == Action.CHECK_MANUALLY


@pytest.mark.os_agnostic
def test_determine_action_handles_git_dependency_with_version() -> None:
    dep = DependencyInfo(
        name="mypackage",
        raw_spec="mypackage",
        version_constraints="",
        is_git_dependency=True,
        git_url="https://github.com/user/repo",
        git_ref="v1.0.0",
    )
    version_result = VersionResult(latest_version="2.0.0")

    action, current, latest = determine_action(dep, PythonVersion(3, 11), version_result)

    assert action == Action.UPDATE
    assert current == "v1.0.0"
    assert latest == "2.0.0"


@pytest.mark.os_agnostic
def test_determine_action_handles_dependency_with_no_version_constraint() -> None:
    dep = DependencyInfo(
        name="package",
        raw_spec="package",
        version_constraints="",
    )
    version_result = VersionResult(latest_version="1.0.0")

    action, current, latest = determine_action(dep, PythonVersion(3, 11), version_result)

    assert action == Action.NONE
    assert current is None
    assert latest == "1.0.0"


# ════════════════════════════════════════════════════════════════════════════
# AnalysisResult: The summary of all findings
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.os_agnostic
def test_analysis_result_stores_entries_and_counts() -> None:
    result = AnalysisResult(
        entries=[
            OutdatedEntry("pkg1", "3.11", "1.0", "2.0", Action.UPDATE),
            OutdatedEntry("pkg2", "3.11", "1.0", "1.0", Action.NONE),
        ],
        python_versions=["3.11"],
        total_dependencies=2,
        update_count=1,
    )

    assert len(result.entries) == 2
    assert result.total_dependencies == 2
    assert result.update_count == 1


@pytest.mark.os_agnostic
def test_analysis_result_defaults_to_empty() -> None:
    result = AnalysisResult()

    assert result.entries == []
    assert result.python_versions == []
    assert result.total_dependencies == 0


# ════════════════════════════════════════════════════════════════════════════
# VersionResult: The messenger from PyPI and GitHub
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.os_agnostic
def test_version_result_stores_latest_version() -> None:
    result = VersionResult(latest_version="1.2.3")

    assert result.latest_version == "1.2.3"
    assert result.is_unknown is False


@pytest.mark.os_agnostic
def test_version_result_indicates_unknown_state() -> None:
    result = VersionResult(is_unknown=True, error="Test error")

    assert result.is_unknown is True
    assert result.latest_version is None
    assert result.error == "Test error"


# ════════════════════════════════════════════════════════════════════════════
# DependencyInfo: The structured knowledge of a single dependency
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.os_agnostic
def test_dependency_info_stores_basic_fields() -> None:
    dep = DependencyInfo(
        name="requests",
        raw_spec="requests>=2.28.0",
        version_constraints=">=2.28.0",
        source="project.dependencies",
    )

    assert dep.name == "requests"
    assert dep.version_constraints == ">=2.28.0"
    assert dep.source == "project.dependencies"


@pytest.mark.os_agnostic
def test_dependency_info_defaults_to_non_git() -> None:
    dep = DependencyInfo(name="pkg", raw_spec="pkg")

    assert dep.is_git_dependency is False
    assert dep.git_url is None


@pytest.mark.os_agnostic
def test_dependency_info_stores_git_fields() -> None:
    dep = DependencyInfo(
        name="mypkg",
        raw_spec="mypkg @ git+https://github.com/user/repo.git@v1.0",
        is_git_dependency=True,
        git_url="git+https://github.com/user/repo.git",
        git_ref="v1.0",
    )

    assert dep.is_git_dependency is True
    assert dep.git_url == "git+https://github.com/user/repo.git"
    assert dep.git_ref == "v1.0"


# ════════════════════════════════════════════════════════════════════════════
# Analyzer: The orchestrator of analysis
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.os_agnostic
def test_create_analyzer_returns_configured_instance() -> None:
    analyzer = create_analyzer(timeout=60.0, concurrency=5)

    assert analyzer.timeout == 60.0
    assert analyzer.concurrency == 5


@pytest.mark.os_agnostic
def test_analyzer_validates_positive_timeout() -> None:
    with pytest.raises(ValueError, match="timeout must be positive"):
        Analyzer(timeout=0)


@pytest.mark.os_agnostic
def test_analyzer_validates_positive_concurrency() -> None:
    with pytest.raises(ValueError, match="concurrency must be positive"):
        Analyzer(concurrency=0)


@pytest.mark.os_agnostic
def test_analyzer_stores_github_token() -> None:
    analyzer = Analyzer(github_token="test-token")

    assert analyzer.github_token == "test-token"


# ════════════════════════════════════════════════════════════════════════════
# VersionResolver: The async fetcher of version truth
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.os_agnostic
def test_version_resolver_stores_configuration() -> None:
    resolver = VersionResolver(timeout=45.0, github_token="secret")

    assert resolver.timeout == 45.0


@pytest.mark.os_agnostic
def test_version_resolver_repr_redacts_token() -> None:
    resolver = VersionResolver(github_token="secret-token")

    assert "***" in repr(resolver)
    assert "secret-token" not in repr(resolver)


@pytest.mark.os_agnostic
def test_version_resolver_repr_shows_none_when_no_token() -> None:
    resolver = VersionResolver()

    assert "github_token=None" in repr(resolver)


# ════════════════════════════════════════════════════════════════════════════
# entry_to_dict: The serializer at the boundary
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.os_agnostic
def test_entry_to_dict_converts_to_serializable_dict() -> None:
    entry = OutdatedEntry("pkg", "3.11", "1.0", "2.0", Action.UPDATE)

    result = entry_to_dict(entry)

    assert result["package"] == "pkg"
    assert result["python_version"] == "3.11"
    assert result["action"] == "update"


# ════════════════════════════════════════════════════════════════════════════
# write_outdated_json: The persistence mechanism
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.os_agnostic
def test_write_outdated_json_creates_file(tmp_path: Path) -> None:
    entries = [OutdatedEntry("pkg", "3.11", "1.0", "2.0", Action.UPDATE)]
    output_path = tmp_path / "output.json"

    write_outdated_json(entries, output_path)

    assert output_path.exists()


@pytest.mark.os_agnostic
def test_write_outdated_json_creates_parent_directories(tmp_path: Path) -> None:
    entries = [OutdatedEntry("pkg", "3.11", "1.0", "2.0", Action.UPDATE)]
    output_path = tmp_path / "nested" / "dir" / "output.json"

    write_outdated_json(entries, output_path)

    assert output_path.exists()


@pytest.mark.os_agnostic
def test_write_outdated_json_rejects_directory_path(tmp_path: Path) -> None:
    entries = [OutdatedEntry("pkg", "3.11", "1.0", "2.0", Action.UPDATE)]

    with pytest.raises(ValueError, match="must be a file"):
        write_outdated_json(entries, tmp_path)


@pytest.mark.os_agnostic
def test_write_outdated_json_writes_valid_json(tmp_path: Path) -> None:
    import json

    entries = [OutdatedEntry("pkg", "3.11", "1.0", "2.0", Action.UPDATE)]
    output_path = tmp_path / "output.json"

    write_outdated_json(entries, output_path)

    with output_path.open() as f:
        data = json.load(f)

    assert len(data) == 1
    assert data[0]["package"] == "pkg"


# ════════════════════════════════════════════════════════════════════════════
# Real-world pyproject.toml files: Integration stories
# ════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def pyproject_files() -> list[Path]:
    """Provide all pyproject.toml test files."""
    return list(TESTDATA_DIR.glob("pyproject_*.toml"))


@pytest.mark.os_agnostic
def test_all_testdata_files_are_parseable(pyproject_files: list[Path]) -> None:
    for path in pyproject_files:
        data = load_pyproject(path)
        assert isinstance(data, dict)


@pytest.mark.os_agnostic
def test_all_testdata_files_yield_dependencies(pyproject_files: list[Path]) -> None:
    total_deps = 0

    for path in pyproject_files:
        data = load_pyproject(path)
        deps = extract_dependencies(data)
        total_deps += len(deps)

    assert total_deps > 100


@pytest.mark.os_agnostic
def test_fastapi_pyproject_contains_starlette() -> None:
    data = load_pyproject(TESTDATA_DIR / "pyproject_fastapi_fastapi.toml")
    deps = extract_dependencies(data)
    names = {d.name for d in deps}

    assert "starlette" in names


@pytest.mark.os_agnostic
def test_fastapi_pyproject_contains_pydantic() -> None:
    data = load_pyproject(TESTDATA_DIR / "pyproject_fastapi_fastapi.toml")
    deps = extract_dependencies(data)
    names = {d.name for d in deps}

    assert "pydantic" in names


@pytest.mark.os_agnostic
def test_django_pyproject_contains_asgiref() -> None:
    path = TESTDATA_DIR / "pyproject_django_django.toml"
    if path.exists():
        data = load_pyproject(path)
        deps = extract_dependencies(data)
        names = {d.name for d in deps}

        assert "asgiref" in names


@pytest.mark.os_agnostic
def test_pytest_pyproject_contains_pluggy() -> None:
    path = TESTDATA_DIR / "pyproject_pytest-dev_pytest.toml"
    if path.exists():
        data = load_pyproject(path)
        deps = extract_dependencies(data)
        names = {d.name for d in deps}

        assert "pluggy" in names


@pytest.mark.os_agnostic
def test_pydantic_pyproject_contains_typing_extensions() -> None:
    path = TESTDATA_DIR / "pyproject_pydantic_pydantic.toml"
    if path.exists():
        data = load_pyproject(path)
        deps = extract_dependencies(data)
        names = {d.name for d in deps}

        assert "typing_extensions" in names


# ════════════════════════════════════════════════════════════════════════════
# Analyzer Internal Helpers: Marker evaluation and action determination
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.os_agnostic
def test_dependency_applies_when_no_markers() -> None:
    dep = DependencyInfo(name="pkg", raw_spec="pkg>=1.0")

    assert _dependency_applies_to_python_version(dep, PythonVersion(3, 11)) is True


@pytest.mark.os_agnostic
def test_dependency_applies_when_marker_matches_lt() -> None:
    dep = DependencyInfo(
        name="tomli",
        raw_spec="tomli>=1.0; python_version < '3.11'",
        python_markers="python_version < '3.11'",
    )

    assert _dependency_applies_to_python_version(dep, PythonVersion(3, 10)) is True
    assert _dependency_applies_to_python_version(dep, PythonVersion(3, 11)) is False


@pytest.mark.os_agnostic
def test_dependency_applies_when_marker_matches_le() -> None:
    dep = DependencyInfo(
        name="pkg",
        raw_spec="pkg; python_version <= '3.10'",
        python_markers="python_version <= '3.10'",
    )

    assert _dependency_applies_to_python_version(dep, PythonVersion(3, 10)) is True
    assert _dependency_applies_to_python_version(dep, PythonVersion(3, 11)) is False


@pytest.mark.os_agnostic
def test_dependency_applies_when_marker_matches_gt() -> None:
    dep = DependencyInfo(
        name="pkg",
        raw_spec="pkg; python_version > '3.9'",
        python_markers="python_version > '3.9'",
    )

    assert _dependency_applies_to_python_version(dep, PythonVersion(3, 9)) is False
    assert _dependency_applies_to_python_version(dep, PythonVersion(3, 10)) is True


@pytest.mark.os_agnostic
def test_dependency_applies_when_marker_matches_ge() -> None:
    dep = DependencyInfo(
        name="pkg",
        raw_spec="pkg; python_version >= '3.10'",
        python_markers="python_version >= '3.10'",
    )

    assert _dependency_applies_to_python_version(dep, PythonVersion(3, 9)) is False
    assert _dependency_applies_to_python_version(dep, PythonVersion(3, 10)) is True


@pytest.mark.os_agnostic
def test_dependency_applies_when_marker_matches_eq() -> None:
    dep = DependencyInfo(
        name="pkg",
        raw_spec="pkg; python_version == '3.11'",
        python_markers="python_version == '3.11'",
    )

    assert _dependency_applies_to_python_version(dep, PythonVersion(3, 10)) is False
    assert _dependency_applies_to_python_version(dep, PythonVersion(3, 11)) is True


@pytest.mark.os_agnostic
def test_dependency_applies_when_marker_matches_ne() -> None:
    dep = DependencyInfo(
        name="pkg",
        raw_spec="pkg; python_version != '3.10'",
        python_markers="python_version != '3.10'",
    )

    assert _dependency_applies_to_python_version(dep, PythonVersion(3, 10)) is False
    assert _dependency_applies_to_python_version(dep, PythonVersion(3, 11)) is True


@pytest.mark.os_agnostic
def test_dependency_applies_defaults_to_true_for_unparseable_marker() -> None:
    dep = DependencyInfo(
        name="pkg",
        raw_spec="pkg; sys_platform == 'linux'",
        python_markers="sys_platform == 'linux'",
    )

    assert _dependency_applies_to_python_version(dep, PythonVersion(3, 11)) is True


@pytest.mark.os_agnostic
def test_determine_git_action_returns_check_manually_when_unknown() -> None:
    dep = DependencyInfo(
        name="pkg",
        raw_spec="pkg",
        is_git_dependency=True,
        git_ref="v1.0.0",
    )
    version_result = VersionResult(is_unknown=True)

    action, current, latest = _determine_git_action(dep, version_result)

    assert action == Action.CHECK_MANUALLY
    assert current == "v1.0.0"
    assert latest == "unknown"


@pytest.mark.os_agnostic
def test_determine_git_action_returns_update_when_newer() -> None:
    dep = DependencyInfo(
        name="pkg",
        raw_spec="pkg",
        is_git_dependency=True,
        git_ref="1.0.0",
    )
    version_result = VersionResult(latest_version="2.0.0")

    action, current, latest = _determine_git_action(dep, version_result)

    assert action == Action.UPDATE
    assert current == "1.0.0"
    assert latest == "2.0.0"


@pytest.mark.os_agnostic
def test_determine_git_action_returns_check_manually_when_same_or_older() -> None:
    dep = DependencyInfo(
        name="pkg",
        raw_spec="pkg",
        is_git_dependency=True,
        git_ref="2.0.0",
    )
    version_result = VersionResult(latest_version="1.0.0")

    action, _, _ = _determine_git_action(dep, version_result)

    assert action == Action.CHECK_MANUALLY


@pytest.mark.os_agnostic
def test_determine_pypi_action_returns_check_manually_when_unknown() -> None:
    dep = DependencyInfo(name="pkg", raw_spec="pkg>=1.0", version_constraints=">=1.0")
    version_result = VersionResult(is_unknown=True)

    action, _, latest = _determine_pypi_action(dep, version_result)

    assert action == Action.CHECK_MANUALLY
    assert latest == "unknown"


@pytest.mark.os_agnostic
def test_determine_pypi_action_returns_none_when_no_current_version() -> None:
    dep = DependencyInfo(name="pkg", raw_spec="pkg", version_constraints="")
    version_result = VersionResult(latest_version="1.0.0")

    action, current, latest = _determine_pypi_action(dep, version_result)

    assert action == Action.NONE
    assert current is None
    assert latest == "1.0.0"


@pytest.mark.os_agnostic
def test_determine_pypi_action_returns_update_when_newer() -> None:
    dep = DependencyInfo(name="pkg", raw_spec="pkg>=1.0", version_constraints=">=1.0")
    version_result = VersionResult(latest_version="2.0.0")

    action, current, latest = _determine_pypi_action(dep, version_result)

    assert action == Action.UPDATE
    assert current == "1.0"
    assert latest == "2.0.0"


@pytest.mark.os_agnostic
def test_determine_pypi_action_returns_none_when_up_to_date() -> None:
    dep = DependencyInfo(name="pkg", raw_spec="pkg>=2.0.0", version_constraints=">=2.0.0")
    version_result = VersionResult(latest_version="2.0.0")

    action, _, _ = _determine_pypi_action(dep, version_result)

    assert action == Action.NONE


@pytest.mark.os_agnostic
def test_generate_entries_creates_all_combinations() -> None:
    deps = [
        DependencyInfo(name="pkg1", raw_spec="pkg1>=1.0", version_constraints=">=1.0"),
        DependencyInfo(name="pkg2", raw_spec="pkg2>=1.0", version_constraints=">=1.0"),
    ]
    versions = [PythonVersion(3, 10), PythonVersion(3, 11)]
    results = {
        "pkg1": VersionResult(latest_version="2.0"),
        "pkg2": VersionResult(latest_version="2.0"),
    }

    entries = _generate_entries(deps, versions, results)

    assert len(entries) == 4  # 2 deps × 2 versions


@pytest.mark.os_agnostic
def test_count_actions_tallies_all_action_types() -> None:
    entries = [
        OutdatedEntry("pkg1", "3.11", "1.0", "2.0", Action.UPDATE),
        OutdatedEntry("pkg2", "3.11", "1.0", "2.0", Action.UPDATE),
        OutdatedEntry("pkg3", "3.11", None, None, Action.DELETE),
        OutdatedEntry("pkg4", "3.11", "?", "?", Action.CHECK_MANUALLY),
    ]

    counts = _count_actions(entries)

    assert counts[Action.UPDATE] == 2
    assert counts[Action.DELETE] == 1
    assert counts[Action.CHECK_MANUALLY] == 1
    assert counts[Action.NONE] == 0


@pytest.mark.os_agnostic
def test_version_tuple_extracts_numeric_parts() -> None:
    assert _version_tuple("1.2.3") == (1, 2, 3)
    assert _version_tuple("1.2") == (1, 2)


@pytest.mark.os_agnostic
def test_version_tuple_handles_prerelease() -> None:
    assert _version_tuple("1.2.3-beta1") == (1, 2, 3)
    assert _version_tuple("1.2.3+build") == (1, 2, 3)


@pytest.mark.os_agnostic
def test_version_tuple_returns_zero_for_no_numbers() -> None:
    assert _version_tuple("latest") == (0,)


# ════════════════════════════════════════════════════════════════════════════
# run_analysis and analyze_pyproject: High-level API functions
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.os_agnostic
def test_run_analysis_with_mock_resolver(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("""
[project]
name = "test"
requires-python = ">=3.10"
dependencies = ["requests>=2.28.0"]
""")

    # Mock the version resolver to avoid network calls
    async def mock_resolve_many(*args: Any, **kwargs: Any) -> dict[str, VersionResult]:
        return {"requests": VersionResult(latest_version="2.31.0")}

    original_init = VersionResolver.__init__

    def patched_init(self: Any, *args: Any, **kwargs: Any) -> None:
        original_init(self, *args, **kwargs)
        self.resolve_many_async = mock_resolve_many

    monkeypatch.setattr(VersionResolver, "__init__", patched_init)

    result = run_analysis(pyproject)

    assert isinstance(result, AnalysisResult)
    assert len(result.entries) > 0
    assert any(e.package == "requests" for e in result.entries)


@pytest.mark.os_agnostic
def test_analyze_pyproject_returns_list_of_entries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("""
[project]
name = "test"
requires-python = ">=3.10"
dependencies = ["httpx>=0.24.0"]
""")

    async def mock_resolve_many(*args: Any, **kwargs: Any) -> dict[str, VersionResult]:
        return {"httpx": VersionResult(latest_version="0.25.0")}

    original_init = VersionResolver.__init__

    def patched_init(self: Any, *args: Any, **kwargs: Any) -> None:
        original_init(self, *args, **kwargs)
        self.resolve_many_async = mock_resolve_many

    monkeypatch.setattr(VersionResolver, "__init__", patched_init)

    entries = analyze_pyproject(pyproject)

    assert isinstance(entries, list)
    assert all(isinstance(e, OutdatedEntry) for e in entries)
