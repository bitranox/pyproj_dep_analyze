"""End-to-end integration tests with real PyPI and GitHub API calls.

These tests verify the full analysis pipeline against real-world pyproject.toml
files, making actual network requests to PyPI and GitHub APIs.

Run with: pytest tests/test_e2e_analysis.py -v --run-slow
Skip with: pytest -m "not slow" (default in pyproject.toml)

Each test generates two JSON output files:
- {name}_analysis.json: Standard analysis result (OutdatedEntry list)
- {name}_enriched.json: Enriched analysis with full metadata

Output files are stored in tests/e2e_outputs/{category}/.

Top 3 most complex files per category (by dependency count):
- build_system_requires: tox (55), setuptools (52), tortoise-orm (44)
- dependency_groups: airflow (250), napari (198), langflow (183)
- hatch_envs_dependencies: prefect (147), marimo (90), mem0 (57)
- optional_dependencies: litestar (101), bentoml (99), dvc (86)
- pdm_dependencies: pdm (52), tortoise_orm (42), griffe (40)
- poetry_dependencies: strawberry (100), textual (44), poetry (38)
- poetry_group_dependencies: OpenHands (133), nicegui (66), aws-lambda-powertools (65)
- project_dependencies: unsloth (610), zenml (114), sqlalchemy (97)
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pyproj_dep_analyze.analyzer import (
    run_analysis,
    run_enriched_analysis,
)

# Mark all tests in this module as slow (skipped by default) and os_agnostic
pytestmark = [pytest.mark.slow, pytest.mark.e2e, pytest.mark.os_agnostic]


TESTDATA_DIR = Path(__file__).parent / "testdata"
E2E_OUTPUT_DIR = Path(__file__).parent / "e2e_outputs"

# Top 3 most complex pyproject.toml files per category (hardcoded)
E2E_TEST_FILES: dict[str, list[str]] = {
    "build_system_requires": [
        "pyproject_tox.toml",  # 55 deps
        "pyproject_setuptools.toml",  # 52 deps
        "pyproject_tortoise_tortoise-orm.toml",  # 44 deps
    ],
    "dependency_groups": [
        "pyproject_apache_airflow.toml",  # 250 deps
        "pyproject_napari_napari.toml",  # 198 deps
        "pyproject_langflow-ai_langflow.toml",  # 183 deps
    ],
    "hatch_envs_dependencies": [
        "pyproject_prefect.toml",  # 147 deps
        "pyproject_marimo.toml",  # 90 deps
        "pyproject_mem0.toml",  # 57 deps
    ],
    "optional_dependencies": [
        "pyproject_litestar.toml",  # 101 deps
        "pyproject_bentoml.toml",  # 99 deps
        "pyproject_dvc.toml",  # 86 deps
    ],
    "pdm_dependencies": [
        "pyproject_pdm.toml",  # 52 deps
        "pyproject_tortoise_orm.toml",  # 42 deps
        "pyproject_griffe.toml",  # 40 deps
    ],
    "poetry_dependencies": [
        "pyproject_strawberry.toml",  # 100 deps
        "pyproject_textual.toml",  # 44 deps
        "pyproject_poetry.toml",  # 38 deps
    ],
    "poetry_group_dependencies": [
        "pyproject_OpenHands_OpenHands.toml",  # 133 deps
        "pyproject_nicegui.toml",  # 66 deps
        "pyproject_awslabs_aws-lambda-powertools-python.toml",  # 65 deps
    ],
    "project_dependencies": [
        "pyproject_unslothai_unsloth.toml",  # 610 deps
        "pyproject_zenml-io_zenml.toml",  # 114 deps
        "pyproject_sqlalchemy.toml",  # 97 deps
    ],
}


def _run_and_save_analysis(pyproject_path: Path, output_dir: Path) -> None:
    """Run both standard and enriched analysis, save JSON outputs."""
    stem = pyproject_path.stem  # e.g., "pyproject_fastapi_fastapi"

    # Define output paths
    standard_output = output_dir / f"{stem}_analysis.json"
    enriched_output = output_dir / f"{stem}_enriched.json"

    # Delete existing output files to ensure fresh results
    standard_output.unlink(missing_ok=True)
    enriched_output.unlink(missing_ok=True)

    # Standard analysis
    result = run_analysis(pyproject_path)
    standard_output.write_text(
        json.dumps(
            {
                "pyproject_path": str(pyproject_path),
                "python_versions": result.python_versions,
                "total_dependencies": result.total_dependencies,
                "update_count": result.update_count,
                "entries": [e.model_dump(mode="json") for e in result.entries],
            },
            indent=2,
        )
    )

    # Enriched analysis
    enriched = run_enriched_analysis(pyproject_path)
    enriched_output.write_text(json.dumps(enriched.model_dump(mode="json"), indent=2))

    # Basic assertions
    assert result.total_dependencies > 0, f"Expected dependencies in {pyproject_path.name}"
    assert len(result.entries) > 0, f"Expected analysis entries for {pyproject_path.name}"
    assert enriched.packages, f"Expected enriched packages for {pyproject_path.name}"


# ════════════════════════════════════════════════════════════════════════════
# build_system_requires - Top 3 complex files
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.e2e
@pytest.mark.network
def test_e2e_build_system_requires_tox() -> None:
    """E2E test for tox pyproject.toml (55 deps)."""
    _run_and_save_analysis(
        TESTDATA_DIR / "build_system_requires" / "pyproject_tox.toml",
        E2E_OUTPUT_DIR / "build_system_requires",
    )


@pytest.mark.e2e
@pytest.mark.network
def test_e2e_build_system_requires_setuptools() -> None:
    """E2E test for setuptools pyproject.toml (52 deps)."""
    _run_and_save_analysis(
        TESTDATA_DIR / "build_system_requires" / "pyproject_setuptools.toml",
        E2E_OUTPUT_DIR / "build_system_requires",
    )


@pytest.mark.e2e
@pytest.mark.network
def test_e2e_build_system_requires_tortoise_orm() -> None:
    """E2E test for tortoise-orm pyproject.toml (44 deps)."""
    _run_and_save_analysis(
        TESTDATA_DIR / "build_system_requires" / "pyproject_tortoise_tortoise-orm.toml",
        E2E_OUTPUT_DIR / "build_system_requires",
    )


# ════════════════════════════════════════════════════════════════════════════
# dependency_groups - Top 3 complex files (PEP 735)
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.e2e
@pytest.mark.network
def test_e2e_dependency_groups_airflow() -> None:
    """E2E test for Apache Airflow pyproject.toml (250 deps)."""
    _run_and_save_analysis(
        TESTDATA_DIR / "dependency_groups" / "pyproject_apache_airflow.toml",
        E2E_OUTPUT_DIR / "dependency_groups",
    )


@pytest.mark.e2e
@pytest.mark.network
def test_e2e_dependency_groups_napari() -> None:
    """E2E test for napari pyproject.toml (198 deps)."""
    _run_and_save_analysis(
        TESTDATA_DIR / "dependency_groups" / "pyproject_napari_napari.toml",
        E2E_OUTPUT_DIR / "dependency_groups",
    )


@pytest.mark.e2e
@pytest.mark.network
def test_e2e_dependency_groups_langflow() -> None:
    """E2E test for langflow pyproject.toml (183 deps)."""
    _run_and_save_analysis(
        TESTDATA_DIR / "dependency_groups" / "pyproject_langflow-ai_langflow.toml",
        E2E_OUTPUT_DIR / "dependency_groups",
    )


# ════════════════════════════════════════════════════════════════════════════
# hatch_envs_dependencies - Top 3 complex files
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.e2e
@pytest.mark.network
def test_e2e_hatch_envs_prefect() -> None:
    """E2E test for Prefect pyproject.toml (147 deps)."""
    _run_and_save_analysis(
        TESTDATA_DIR / "hatch_envs_dependencies" / "pyproject_prefect.toml",
        E2E_OUTPUT_DIR / "hatch_envs_dependencies",
    )


@pytest.mark.e2e
@pytest.mark.network
def test_e2e_hatch_envs_marimo() -> None:
    """E2E test for marimo pyproject.toml (90 deps)."""
    _run_and_save_analysis(
        TESTDATA_DIR / "hatch_envs_dependencies" / "pyproject_marimo.toml",
        E2E_OUTPUT_DIR / "hatch_envs_dependencies",
    )


@pytest.mark.e2e
@pytest.mark.network
def test_e2e_hatch_envs_mem0() -> None:
    """E2E test for mem0 pyproject.toml (57 deps)."""
    _run_and_save_analysis(
        TESTDATA_DIR / "hatch_envs_dependencies" / "pyproject_mem0.toml",
        E2E_OUTPUT_DIR / "hatch_envs_dependencies",
    )


# ════════════════════════════════════════════════════════════════════════════
# optional_dependencies - Top 3 complex files
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.e2e
@pytest.mark.network
def test_e2e_optional_dependencies_litestar() -> None:
    """E2E test for litestar pyproject.toml (101 deps)."""
    _run_and_save_analysis(
        TESTDATA_DIR / "optional_dependencies" / "pyproject_litestar.toml",
        E2E_OUTPUT_DIR / "optional_dependencies",
    )


@pytest.mark.e2e
@pytest.mark.network
def test_e2e_optional_dependencies_bentoml() -> None:
    """E2E test for bentoml pyproject.toml (99 deps)."""
    _run_and_save_analysis(
        TESTDATA_DIR / "optional_dependencies" / "pyproject_bentoml.toml",
        E2E_OUTPUT_DIR / "optional_dependencies",
    )


@pytest.mark.e2e
@pytest.mark.network
def test_e2e_optional_dependencies_dvc() -> None:
    """E2E test for dvc pyproject.toml (86 deps)."""
    _run_and_save_analysis(
        TESTDATA_DIR / "optional_dependencies" / "pyproject_dvc.toml",
        E2E_OUTPUT_DIR / "optional_dependencies",
    )


# ════════════════════════════════════════════════════════════════════════════
# pdm_dependencies - Top 3 complex files
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.e2e
@pytest.mark.network
def test_e2e_pdm_dependencies_pdm() -> None:
    """E2E test for PDM pyproject.toml (52 deps)."""
    _run_and_save_analysis(
        TESTDATA_DIR / "pdm_dependencies" / "pyproject_pdm.toml",
        E2E_OUTPUT_DIR / "pdm_dependencies",
    )


@pytest.mark.e2e
@pytest.mark.network
def test_e2e_pdm_dependencies_tortoise_orm() -> None:
    """E2E test for tortoise-orm pyproject.toml (42 deps)."""
    _run_and_save_analysis(
        TESTDATA_DIR / "pdm_dependencies" / "pyproject_tortoise_orm.toml",
        E2E_OUTPUT_DIR / "pdm_dependencies",
    )


@pytest.mark.e2e
@pytest.mark.network
def test_e2e_pdm_dependencies_griffe() -> None:
    """E2E test for griffe pyproject.toml (40 deps)."""
    _run_and_save_analysis(
        TESTDATA_DIR / "pdm_dependencies" / "pyproject_griffe.toml",
        E2E_OUTPUT_DIR / "pdm_dependencies",
    )


# ════════════════════════════════════════════════════════════════════════════
# poetry_dependencies - Top 3 complex files
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.e2e
@pytest.mark.network
def test_e2e_poetry_dependencies_strawberry() -> None:
    """E2E test for strawberry-graphql pyproject.toml (100 deps)."""
    _run_and_save_analysis(
        TESTDATA_DIR / "poetry_dependencies" / "pyproject_strawberry.toml",
        E2E_OUTPUT_DIR / "poetry_dependencies",
    )


@pytest.mark.e2e
@pytest.mark.network
def test_e2e_poetry_dependencies_textual() -> None:
    """E2E test for textual pyproject.toml (44 deps)."""
    _run_and_save_analysis(
        TESTDATA_DIR / "poetry_dependencies" / "pyproject_textual.toml",
        E2E_OUTPUT_DIR / "poetry_dependencies",
    )


@pytest.mark.e2e
@pytest.mark.network
def test_e2e_poetry_dependencies_poetry() -> None:
    """E2E test for poetry pyproject.toml (38 deps)."""
    _run_and_save_analysis(
        TESTDATA_DIR / "poetry_dependencies" / "pyproject_poetry.toml",
        E2E_OUTPUT_DIR / "poetry_dependencies",
    )


# ════════════════════════════════════════════════════════════════════════════
# poetry_group_dependencies - Top 3 complex files
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.e2e
@pytest.mark.network
def test_e2e_poetry_group_openhands() -> None:
    """E2E test for OpenHands pyproject.toml (133 deps)."""
    _run_and_save_analysis(
        TESTDATA_DIR / "poetry_group_dependencies" / "pyproject_OpenHands_OpenHands.toml",
        E2E_OUTPUT_DIR / "poetry_group_dependencies",
    )


@pytest.mark.e2e
@pytest.mark.network
def test_e2e_poetry_group_nicegui() -> None:
    """E2E test for nicegui pyproject.toml (66 deps)."""
    _run_and_save_analysis(
        TESTDATA_DIR / "poetry_group_dependencies" / "pyproject_nicegui.toml",
        E2E_OUTPUT_DIR / "poetry_group_dependencies",
    )


@pytest.mark.e2e
@pytest.mark.network
def test_e2e_poetry_group_aws_lambda_powertools() -> None:
    """E2E test for aws-lambda-powertools-python pyproject.toml (65 deps)."""
    _run_and_save_analysis(
        TESTDATA_DIR / "poetry_group_dependencies" / "pyproject_awslabs_aws-lambda-powertools-python.toml",
        E2E_OUTPUT_DIR / "poetry_group_dependencies",
    )


# ════════════════════════════════════════════════════════════════════════════
# project_dependencies - Top 3 complex files (PEP 621)
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.e2e
@pytest.mark.network
def test_e2e_project_dependencies_unsloth() -> None:
    """E2E test for unsloth pyproject.toml (610 deps)."""
    _run_and_save_analysis(
        TESTDATA_DIR / "project_dependencies" / "pyproject_unslothai_unsloth.toml",
        E2E_OUTPUT_DIR / "project_dependencies",
    )


@pytest.mark.e2e
@pytest.mark.network
def test_e2e_project_dependencies_zenml() -> None:
    """E2E test for zenml pyproject.toml (114 deps)."""
    _run_and_save_analysis(
        TESTDATA_DIR / "project_dependencies" / "pyproject_zenml-io_zenml.toml",
        E2E_OUTPUT_DIR / "project_dependencies",
    )


@pytest.mark.e2e
@pytest.mark.network
def test_e2e_project_dependencies_sqlalchemy() -> None:
    """E2E test for sqlalchemy pyproject.toml (97 deps)."""
    _run_and_save_analysis(
        TESTDATA_DIR / "project_dependencies" / "pyproject_sqlalchemy.toml",
        E2E_OUTPUT_DIR / "project_dependencies",
    )
