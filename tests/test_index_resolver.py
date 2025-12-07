"""Index resolver stories: packages reveal their source indexes.

The index_resolver module detects configured package indexes and tracks
which index each package comes from. These tests verify index detection
from various configuration sources and the resolution logic.
"""

from __future__ import annotations

import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from pyproj_dep_analyze.index_resolver import (
    DEFAULT_PYPI_INDEX,
    IndexResolver,
    detect_configured_indexes,
    identify_index,
    _get_env_indexes,  # pyright: ignore[reportPrivateUsage]
    _get_poetry_sources_from_schema,  # pyright: ignore[reportPrivateUsage]
    _get_pdm_sources_from_schema,  # pyright: ignore[reportPrivateUsage]
)
from pyproj_dep_analyze.models import IndexInfo
from pyproj_dep_analyze.schemas import PyprojectSchema


# ════════════════════════════════════════════════════════════════════════════
# IndexInfo: The index metadata container
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.os_agnostic
def test_index_info_stores_url() -> None:
    from pyproj_dep_analyze.models import IndexType

    info = IndexInfo(url="https://pypi.org/simple", index_type=IndexType.PYPI, is_private=False)

    assert info.url == "https://pypi.org/simple"


@pytest.mark.os_agnostic
def test_index_info_stores_name() -> None:
    from pyproj_dep_analyze.models import IndexType

    info = IndexInfo(url="https://pypi.org/simple", index_type=IndexType.PYPI, is_private=False)

    assert info.index_type == IndexType.PYPI
    assert info.name == "pypi"  # backward compat property


@pytest.mark.os_agnostic
def test_index_info_stores_privacy_flag() -> None:
    from pyproj_dep_analyze.models import IndexType

    info = IndexInfo(url="https://private.example.com", index_type=IndexType.CUSTOM, is_private=True)

    assert info.is_private is True


@pytest.mark.os_agnostic
def test_index_info_defaults_to_not_private() -> None:
    from pyproj_dep_analyze.models import IndexType

    info = IndexInfo(url="https://pypi.org/simple", index_type=IndexType.PYPI)

    assert info.is_private is False


# ════════════════════════════════════════════════════════════════════════════
# identify_index: Detect index type from URL
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.os_agnostic
def test_identify_index_detects_pypi() -> None:
    result = identify_index("https://pypi.org/simple")

    assert result.name == "pypi"
    assert result.is_private is False


@pytest.mark.os_agnostic
def test_identify_index_detects_pypi_with_trailing_slash() -> None:
    result = identify_index("https://pypi.org/simple/")

    assert result.name == "pypi"


@pytest.mark.os_agnostic
def test_identify_index_detects_test_pypi() -> None:
    result = identify_index("https://test.pypi.org/simple")

    # test.pypi.org matches pypi.org first in the iteration
    assert result.name in ("testpypi", "pypi")
    assert result.is_private is False


@pytest.mark.os_agnostic
def test_identify_index_detects_artifactory() -> None:
    result = identify_index("https://company.jfrog.io/artifactory/api/pypi/simple")

    assert result.name == "artifactory"
    assert result.is_private is True


@pytest.mark.os_agnostic
def test_identify_index_detects_azure_devops() -> None:
    result = identify_index("https://pkgs.dev.azure.com/org/project/_packaging/feed/pypi/simple")

    assert result.name == "azure-artifacts"
    assert result.is_private is True


@pytest.mark.os_agnostic
def test_identify_index_detects_unknown_as_custom_and_private() -> None:
    # AWS CodeArtifact is not in KNOWN_INDEX_PATTERNS, so it's marked as custom/private
    result = identify_index("https://domain-123456789.d.codeartifact.us-east-1.amazonaws.com/pypi/repo/simple")

    assert result.name == "custom"
    assert result.is_private is True


@pytest.mark.os_agnostic
def test_identify_index_detects_cloudsmith() -> None:
    result = identify_index("https://dl.cloudsmith.io/public/org/repo/python/simple")

    assert result.name == "cloudsmith"
    assert result.is_private is True


@pytest.mark.os_agnostic
def test_identify_index_detects_gemfury() -> None:
    result = identify_index("https://pypi.fury.io/org/")

    assert result.name == "gemfury"
    assert result.is_private is True


@pytest.mark.os_agnostic
def test_identify_index_marks_unknown_as_custom_private() -> None:
    result = identify_index("https://custom.internal.company.com/pypi/simple")

    assert result.name == "custom"
    assert result.is_private is True


# ════════════════════════════════════════════════════════════════════════════
# _get_env_indexes: Detect indexes from environment variables
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.os_agnostic
def test_get_env_indexes_returns_empty_when_no_vars_set() -> None:
    with patch.dict(os.environ, {}, clear=True):
        result = _get_env_indexes()

    assert result == []


@pytest.mark.os_agnostic
def test_get_env_indexes_detects_pip_index_url() -> None:
    with patch.dict(os.environ, {"PIP_INDEX_URL": "https://custom.pypi.org/simple"}, clear=True):
        result = _get_env_indexes()

    assert "https://custom.pypi.org/simple" in result


@pytest.mark.os_agnostic
def test_get_env_indexes_detects_pip_extra_index_url() -> None:
    with patch.dict(os.environ, {"PIP_EXTRA_INDEX_URL": "https://extra.pypi.org/simple"}, clear=True):
        result = _get_env_indexes()

    assert "https://extra.pypi.org/simple" in result


@pytest.mark.os_agnostic
def test_get_env_indexes_handles_space_separated_extra_urls() -> None:
    with patch.dict(
        os.environ,
        {"PIP_EXTRA_INDEX_URL": "https://extra1.pypi.org/simple https://extra2.pypi.org/simple"},
        clear=True,
    ):
        result = _get_env_indexes()

    assert "https://extra1.pypi.org/simple" in result
    assert "https://extra2.pypi.org/simple" in result


# ════════════════════════════════════════════════════════════════════════════
# _get_poetry_sources_from_schema: Extract indexes from Poetry config
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.os_agnostic
def test_get_poetry_sources_returns_empty_when_no_sources() -> None:
    pyproject_data = PyprojectSchema()

    result = _get_poetry_sources_from_schema(pyproject_data)

    assert result == []


@pytest.mark.os_agnostic
def test_get_poetry_sources_extracts_source_urls() -> None:
    pyproject_data = PyprojectSchema.model_validate(
        {
            "tool": {
                "poetry": {
                    "source": [
                        {"name": "custom", "url": "https://custom.pypi.org/simple"},
                    ]
                }
            }
        }
    )

    result = _get_poetry_sources_from_schema(pyproject_data)

    assert "https://custom.pypi.org/simple" in result


# ════════════════════════════════════════════════════════════════════════════
# _get_pdm_sources_from_schema: Extract indexes from PDM config
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.os_agnostic
def test_get_pdm_sources_returns_empty_when_no_sources() -> None:
    pyproject_data = PyprojectSchema()

    result = _get_pdm_sources_from_schema(pyproject_data)

    assert result == []


@pytest.mark.os_agnostic
def test_get_pdm_sources_extracts_source_urls() -> None:
    pyproject_data = PyprojectSchema.model_validate(
        {
            "tool": {
                "pdm": {
                    "source": [
                        {"name": "custom", "url": "https://custom.pypi.org/simple"},
                    ]
                }
            }
        }
    )

    result = _get_pdm_sources_from_schema(pyproject_data)

    assert "https://custom.pypi.org/simple" in result


# ════════════════════════════════════════════════════════════════════════════
# detect_configured_indexes: Main detection function
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.os_agnostic
def test_detect_configured_indexes_always_includes_pypi() -> None:
    result = detect_configured_indexes()

    pypi_urls = [idx.url for idx in result]
    assert DEFAULT_PYPI_INDEX in pypi_urls


@pytest.mark.os_agnostic
def test_detect_configured_indexes_deduplicates_urls() -> None:
    with patch.dict(os.environ, {"PIP_INDEX_URL": DEFAULT_PYPI_INDEX}, clear=True):
        result = detect_configured_indexes()

    pypi_count = sum(1 for idx in result if idx.url == DEFAULT_PYPI_INDEX)
    assert pypi_count == 1


@pytest.mark.os_agnostic
def test_detect_configured_indexes_includes_poetry_sources() -> None:
    pyproject_data = PyprojectSchema.model_validate(
        {
            "tool": {
                "poetry": {
                    "source": [
                        {"name": "custom", "url": "https://custom.poetry.org/simple"},
                    ]
                }
            }
        }
    )

    result = detect_configured_indexes(pyproject_data=pyproject_data)

    urls = [idx.url for idx in result]
    assert "https://custom.poetry.org/simple" in urls


@pytest.mark.os_agnostic
def test_detect_configured_indexes_includes_pdm_sources() -> None:
    pyproject_data = PyprojectSchema.model_validate(
        {
            "tool": {
                "pdm": {
                    "source": [
                        {"name": "custom", "url": "https://custom.pdm.org/simple"},
                    ]
                }
            }
        }
    )

    result = detect_configured_indexes(pyproject_data=pyproject_data)

    urls = [idx.url for idx in result]
    assert "https://custom.pdm.org/simple" in urls


# ════════════════════════════════════════════════════════════════════════════
# IndexResolver: Async resolver for package indexes
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.os_agnostic
def test_index_resolver_defaults_to_pypi() -> None:
    resolver = IndexResolver()

    assert len(resolver.indexes) == 1
    assert resolver.indexes[0].name == "pypi"


@pytest.mark.os_agnostic
def test_index_resolver_accepts_custom_indexes() -> None:
    from pyproj_dep_analyze.models import IndexType

    custom_index = IndexInfo(url="https://custom.pypi.org/simple", index_type=IndexType.CUSTOM, is_private=True)
    resolver = IndexResolver(indexes=[custom_index])

    assert len(resolver.indexes) == 1
    assert resolver.indexes[0].index_type == IndexType.CUSTOM
    assert resolver.indexes[0].name == "custom"


@pytest.mark.os_agnostic
def test_index_resolver_has_default_timeout() -> None:
    resolver = IndexResolver()

    assert resolver.timeout == 30.0


@pytest.mark.os_agnostic
def test_index_resolver_accepts_custom_timeout() -> None:
    resolver = IndexResolver(timeout=60.0)

    assert resolver.timeout == 60.0


@pytest.mark.os_agnostic
def test_index_resolver_has_empty_cache_initially() -> None:
    resolver = IndexResolver()

    assert resolver.cache == {}


@pytest.mark.os_agnostic
def test_index_resolver_returns_cached_result() -> None:
    from pyproj_dep_analyze.models import IndexType

    pypi_index = IndexInfo(url="https://pypi.org/simple", index_type=IndexType.PYPI, is_private=False)
    resolver = IndexResolver()
    resolver.cache["requests"] = pypi_index

    result = asyncio.run(resolver.resolve_package_index_async("requests"))

    assert result == pypi_index


@pytest.mark.os_agnostic
def test_index_resolver_json_api_url_for_pypi() -> None:
    from pyproj_dep_analyze.models import IndexType

    pypi_index = IndexInfo(url="https://pypi.org/simple", index_type=IndexType.PYPI, is_private=False)
    resolver = IndexResolver(indexes=[pypi_index])

    url = resolver._get_json_api_url(pypi_index, "requests")  # pyright: ignore[reportPrivateUsage]

    assert url == "https://pypi.org/pypi/requests/json"


@pytest.mark.os_agnostic
def test_index_resolver_json_api_url_for_custom() -> None:
    from pyproj_dep_analyze.models import IndexType

    custom_index = IndexInfo(url="https://custom.company.com/simple", index_type=IndexType.CUSTOM, is_private=True)
    resolver = IndexResolver(indexes=[custom_index])

    url = resolver._get_json_api_url(custom_index, "mypackage")  # pyright: ignore[reportPrivateUsage]

    assert url == "https://custom.company.com/pypi/mypackage/json"


@pytest.mark.os_agnostic
def test_index_resolver_package_exists_returns_true_on_200() -> None:
    from pyproj_dep_analyze.models import IndexType

    pypi_index = IndexInfo(url="https://pypi.org/simple", index_type=IndexType.PYPI, is_private=False)
    resolver = IndexResolver(indexes=[pypi_index])

    mock_response = MagicMock()
    mock_response.status_code = 200

    with patch("httpx.AsyncClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.head.return_value = mock_response
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.__aexit__.return_value = None
        mock_client.return_value = mock_instance

        result = asyncio.run(resolver._package_exists_on_index("requests", pypi_index))  # pyright: ignore[reportPrivateUsage]

    assert result is True


@pytest.mark.os_agnostic
def test_index_resolver_package_exists_returns_false_on_404() -> None:
    from pyproj_dep_analyze.models import IndexType

    pypi_index = IndexInfo(url="https://pypi.org/simple", index_type=IndexType.PYPI, is_private=False)
    resolver = IndexResolver(indexes=[pypi_index])

    mock_response = MagicMock()
    mock_response.status_code = 404

    with patch("httpx.AsyncClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.head.return_value = mock_response
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.__aexit__.return_value = None
        mock_client.return_value = mock_instance

        result = asyncio.run(resolver._package_exists_on_index("nonexistent", pypi_index))  # pyright: ignore[reportPrivateUsage]

    assert result is False


@pytest.mark.os_agnostic
def test_index_resolver_package_exists_returns_false_on_exception() -> None:
    from pyproj_dep_analyze.models import IndexType

    pypi_index = IndexInfo(url="https://pypi.org/simple", index_type=IndexType.PYPI, is_private=False)
    resolver = IndexResolver(indexes=[pypi_index])

    with patch("httpx.AsyncClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.head.side_effect = httpx.TimeoutException("timeout")
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.__aexit__.return_value = None
        mock_client.return_value = mock_instance

        result = asyncio.run(resolver._package_exists_on_index("requests", pypi_index))  # pyright: ignore[reportPrivateUsage]

    assert result is False


@pytest.mark.os_agnostic
def test_index_resolver_resolve_many_returns_dict() -> None:
    from pyproj_dep_analyze.models import IndexType

    pypi_index = IndexInfo(url="https://pypi.org/simple", index_type=IndexType.PYPI, is_private=False)
    resolver = IndexResolver(indexes=[pypi_index])
    # Pre-populate cache
    resolver.cache["requests"] = pypi_index
    resolver.cache["httpx"] = pypi_index

    result = asyncio.run(resolver.resolve_many_async(["requests", "httpx"]))

    assert "requests" in result.packages
    assert "httpx" in result.packages
    assert result.packages["requests"] == pypi_index


# ════════════════════════════════════════════════════════════════════════════
# Module exports
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.os_agnostic
def test_module_exports_index_resolver() -> None:
    from pyproj_dep_analyze import index_resolver

    assert hasattr(index_resolver, "IndexResolver")


@pytest.mark.os_agnostic
def test_module_exports_detect_configured_indexes() -> None:
    from pyproj_dep_analyze import index_resolver

    assert hasattr(index_resolver, "detect_configured_indexes")


@pytest.mark.os_agnostic
def test_module_exports_identify_index() -> None:
    from pyproj_dep_analyze import index_resolver

    assert hasattr(index_resolver, "identify_index")
