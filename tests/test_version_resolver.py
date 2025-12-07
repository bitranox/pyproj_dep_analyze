"""Version resolver stories: dependencies reveal their latest versions.

The version_resolver module resolves package versions from PyPI and GitHub.
These tests verify the resolution logic, caching, and error handling using
mocked HTTP responses to isolate from external APIs.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import httpx
import pytest

from pyproj_dep_analyze import version_resolver as resolver_mod
from pyproj_dep_analyze.models import DependencyInfo, PythonVersion
from pyproj_dep_analyze.schemas import GitHubReleaseSchema, GitHubTagSchema, PyPIFullResponseSchema, PyPIReleaseFileSchema
from pyproj_dep_analyze.version_resolver import (
    VersionResolver,
    VersionResult,
    _extract_version_from_tag,  # pyright: ignore[reportPrivateUsage]
    _find_latest_compatible_version,  # pyright: ignore[reportPrivateUsage]
    _find_version_from_releases,  # pyright: ignore[reportPrivateUsage]
    _find_version_from_tags,  # pyright: ignore[reportPrivateUsage]
    _is_python_compatible,  # pyright: ignore[reportPrivateUsage]
    _parse_github_url,  # pyright: ignore[reportPrivateUsage]
    _version_sort_key,  # pyright: ignore[reportPrivateUsage]
    resolve_pypi_version_cached,
)


# ════════════════════════════════════════════════════════════════════════════
# VersionResult: The resolution result container
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.os_agnostic
def test_version_result_stores_latest_version() -> None:
    result = VersionResult(latest_version="1.2.3")

    assert result.latest_version == "1.2.3"


@pytest.mark.os_agnostic
def test_version_result_defaults_to_none_latest() -> None:
    result = VersionResult()

    assert result.latest_version is None


@pytest.mark.os_agnostic
def test_version_result_stores_is_unknown_flag() -> None:
    result = VersionResult(is_unknown=True)

    assert result.is_unknown is True


@pytest.mark.os_agnostic
def test_version_result_defaults_is_unknown_to_false() -> None:
    result = VersionResult()

    assert result.is_unknown is False


@pytest.mark.os_agnostic
def test_version_result_stores_error_message() -> None:
    result = VersionResult(error="Connection failed")

    assert result.error == "Connection failed"


@pytest.mark.os_agnostic
def test_version_result_defaults_error_to_none() -> None:
    result = VersionResult()

    assert result.error is None


# ════════════════════════════════════════════════════════════════════════════
# VersionResolver: The async resolver with caching
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.os_agnostic
def test_version_resolver_has_default_timeout() -> None:
    resolver = VersionResolver()

    assert resolver.timeout == 30.0


@pytest.mark.os_agnostic
def test_version_resolver_accepts_custom_timeout() -> None:
    resolver = VersionResolver(timeout=60.0)

    assert resolver.timeout == 60.0


@pytest.mark.os_agnostic
def test_version_resolver_accepts_github_token() -> None:
    resolver = VersionResolver(github_token="test-token")

    assert resolver.github_token == "test-token"


@pytest.mark.os_agnostic
def test_version_resolver_defaults_to_empty_cache() -> None:
    resolver = VersionResolver()

    assert resolver.cache == {}


@pytest.mark.os_agnostic
def test_version_resolver_repr_redacts_token() -> None:
    resolver = VersionResolver(github_token="secret-token")

    repr_str = repr(resolver)

    assert "secret-token" not in repr_str
    assert "***" in repr_str


@pytest.mark.os_agnostic
def test_version_resolver_repr_shows_none_when_no_token() -> None:
    resolver = VersionResolver()

    repr_str = repr(resolver)

    assert "github_token=None" in repr_str


@pytest.mark.os_agnostic
def test_version_resolver_get_headers_includes_user_agent() -> None:
    resolver = VersionResolver()

    headers = resolver._get_headers()  # pyright: ignore[reportPrivateUsage]

    assert "User-Agent" in headers


@pytest.mark.os_agnostic
def test_version_resolver_get_headers_includes_accept_json() -> None:
    resolver = VersionResolver()

    headers = resolver._get_headers()  # pyright: ignore[reportPrivateUsage]

    assert headers["Accept"] == "application/json"


@pytest.mark.os_agnostic
def test_version_resolver_get_headers_excludes_auth_for_non_github() -> None:
    resolver = VersionResolver(github_token="test-token")

    headers = resolver._get_headers(for_github=False)  # pyright: ignore[reportPrivateUsage]

    assert "Authorization" not in headers


@pytest.mark.os_agnostic
def test_version_resolver_get_headers_includes_auth_for_github() -> None:
    resolver = VersionResolver(github_token="test-token")

    headers = resolver._get_headers(for_github=True)  # pyright: ignore[reportPrivateUsage]

    assert headers["Authorization"] == "token test-token"


@pytest.mark.os_agnostic
def test_version_resolver_get_headers_no_auth_without_token() -> None:
    resolver = VersionResolver()

    headers = resolver._get_headers(for_github=True)  # pyright: ignore[reportPrivateUsage]

    assert "Authorization" not in headers


# ════════════════════════════════════════════════════════════════════════════
# _extract_version_from_tag: Version extraction from git tags
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.os_agnostic
def test_extract_version_from_simple_version_tag() -> None:
    result = _extract_version_from_tag("1.2.3")  # pyright: ignore[reportPrivateUsage]

    assert result == "1.2.3"


@pytest.mark.os_agnostic
def test_extract_version_from_v_prefixed_tag() -> None:
    result = _extract_version_from_tag("v1.2.3")  # pyright: ignore[reportPrivateUsage]

    assert result == "1.2.3"


@pytest.mark.os_agnostic
def test_extract_version_from_release_prefixed_tag() -> None:
    result = _extract_version_from_tag("release-1.2.3")  # pyright: ignore[reportPrivateUsage]

    assert result == "1.2.3"


@pytest.mark.os_agnostic
def test_extract_version_from_version_prefixed_tag() -> None:
    result = _extract_version_from_tag("version-1.2.3")  # pyright: ignore[reportPrivateUsage]

    assert result == "1.2.3"


@pytest.mark.os_agnostic
def test_extract_version_from_two_part_version() -> None:
    result = _extract_version_from_tag("v1.2")  # pyright: ignore[reportPrivateUsage]

    assert result == "1.2"


@pytest.mark.os_agnostic
def test_extract_version_returns_none_for_empty_tag() -> None:
    result = _extract_version_from_tag("")  # pyright: ignore[reportPrivateUsage]

    assert result is None


@pytest.mark.os_agnostic
def test_extract_version_returns_none_for_non_version_tag() -> None:
    result = _extract_version_from_tag("latest")  # pyright: ignore[reportPrivateUsage]

    assert result is None


@pytest.mark.os_agnostic
def test_extract_version_handles_prerelease_suffix() -> None:
    result = _extract_version_from_tag("v1.2.3-beta1")  # pyright: ignore[reportPrivateUsage]

    assert result == "1.2.3-beta1"


@pytest.mark.os_agnostic
def test_extract_version_handles_uppercase_v() -> None:
    result = _extract_version_from_tag("V1.2.3")  # pyright: ignore[reportPrivateUsage]

    assert result == "1.2.3"


# ════════════════════════════════════════════════════════════════════════════
# _find_version_from_releases: GitHub release version finder
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.os_agnostic
def test_find_version_from_releases_returns_stable_release() -> None:
    releases = [
        GitHubReleaseSchema(tag_name="v2.0.0-beta", prerelease=True, draft=False),
        GitHubReleaseSchema(tag_name="v1.0.0", prerelease=False, draft=False),
    ]

    result = _find_version_from_releases(releases)  # pyright: ignore[reportPrivateUsage]

    assert result == "1.0.0"


@pytest.mark.os_agnostic
def test_find_version_from_releases_skips_draft_releases() -> None:
    releases = [
        GitHubReleaseSchema(tag_name="v2.0.0", prerelease=False, draft=True),
        GitHubReleaseSchema(tag_name="v1.0.0", prerelease=False, draft=False),
    ]

    result = _find_version_from_releases(releases)  # pyright: ignore[reportPrivateUsage]

    assert result == "1.0.0"


@pytest.mark.os_agnostic
def test_find_version_from_releases_falls_back_to_first_if_no_stable() -> None:
    releases = [
        GitHubReleaseSchema(tag_name="v2.0.0-beta", prerelease=True, draft=False),
        GitHubReleaseSchema(tag_name="v1.0.0-alpha", prerelease=True, draft=False),
    ]

    result = _find_version_from_releases(releases)  # pyright: ignore[reportPrivateUsage]

    assert result == "2.0.0-beta"


@pytest.mark.os_agnostic
def test_find_version_from_releases_returns_none_for_empty_list() -> None:
    result = _find_version_from_releases([])  # pyright: ignore[reportPrivateUsage]

    assert result is None


@pytest.mark.os_agnostic
def test_find_version_from_releases_skips_non_version_tags() -> None:
    releases = [
        GitHubReleaseSchema(tag_name="latest", prerelease=False, draft=False),
        GitHubReleaseSchema(tag_name="v1.0.0", prerelease=False, draft=False),
    ]

    result = _find_version_from_releases(releases)  # pyright: ignore[reportPrivateUsage]

    assert result == "1.0.0"


# ════════════════════════════════════════════════════════════════════════════
# _find_version_from_tags: GitHub tag version finder
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.os_agnostic
def test_find_version_from_tags_returns_highest_version() -> None:
    tags = [
        GitHubTagSchema(name="v1.0.0"),
        GitHubTagSchema(name="v2.0.0"),
        GitHubTagSchema(name="v1.5.0"),
    ]

    result = _find_version_from_tags(tags)  # pyright: ignore[reportPrivateUsage]

    assert result == "2.0.0"


@pytest.mark.os_agnostic
def test_find_version_from_tags_returns_none_for_empty_list() -> None:
    result = _find_version_from_tags([])  # pyright: ignore[reportPrivateUsage]

    assert result is None


@pytest.mark.os_agnostic
def test_find_version_from_tags_skips_non_version_tags() -> None:
    tags = [
        GitHubTagSchema(name="latest"),
        GitHubTagSchema(name="v1.0.0"),
    ]

    result = _find_version_from_tags(tags)  # pyright: ignore[reportPrivateUsage]

    assert result == "1.0.0"


@pytest.mark.os_agnostic
def test_find_version_from_tags_returns_none_when_no_version_tags() -> None:
    tags = [
        GitHubTagSchema(name="latest"),
        GitHubTagSchema(name="stable"),
    ]

    result = _find_version_from_tags(tags)  # pyright: ignore[reportPrivateUsage]

    assert result is None


# ════════════════════════════════════════════════════════════════════════════
# _version_sort_key: Version string sorting
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.os_agnostic
def test_version_sort_key_extracts_numeric_parts() -> None:
    result = _version_sort_key("1.2.3")  # pyright: ignore[reportPrivateUsage]

    assert result == (1, 2, 3)


@pytest.mark.os_agnostic
def test_version_sort_key_handles_two_part_version() -> None:
    result = _version_sort_key("1.2")  # pyright: ignore[reportPrivateUsage]

    assert result == (1, 2)


@pytest.mark.os_agnostic
def test_version_sort_key_returns_zero_for_no_numbers() -> None:
    result = _version_sort_key("latest")  # pyright: ignore[reportPrivateUsage]

    assert result == (0,)


@pytest.mark.os_agnostic
def test_version_sort_key_is_cached() -> None:
    _version_sort_key.cache_clear()  # pyright: ignore[reportPrivateUsage]
    _version_sort_key("1.2.3")  # pyright: ignore[reportPrivateUsage]
    _version_sort_key("1.2.3")  # pyright: ignore[reportPrivateUsage]

    info = _version_sort_key.cache_info()  # pyright: ignore[reportPrivateUsage]

    assert info.hits >= 1


# ════════════════════════════════════════════════════════════════════════════
# _parse_github_url: GitHub URL parsing
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.os_agnostic
def test_parse_github_url_from_https_url() -> None:
    owner, repo = _parse_github_url("https://github.com/owner/repo")  # pyright: ignore[reportPrivateUsage]

    assert owner == "owner"
    assert repo == "repo"


@pytest.mark.os_agnostic
def test_parse_github_url_from_git_plus_https() -> None:
    owner, repo = _parse_github_url("git+https://github.com/owner/repo.git")  # pyright: ignore[reportPrivateUsage]

    assert owner == "owner"
    assert repo == "repo"


@pytest.mark.os_agnostic
def test_parse_github_url_from_ssh_url() -> None:
    owner, repo = _parse_github_url("git@github.com:owner/repo.git")  # pyright: ignore[reportPrivateUsage]

    assert owner == "owner"
    assert repo == "repo"


@pytest.mark.os_agnostic
def test_parse_github_url_with_ref() -> None:
    owner, repo = _parse_github_url("git+https://github.com/owner/repo.git@v1.0.0")  # pyright: ignore[reportPrivateUsage]

    assert owner == "owner"
    assert repo == "repo"


@pytest.mark.os_agnostic
def test_parse_github_url_returns_none_for_non_github() -> None:
    owner, repo = _parse_github_url("https://gitlab.com/owner/repo")  # pyright: ignore[reportPrivateUsage]

    assert owner is None
    assert repo is None


@pytest.mark.os_agnostic
def test_parse_github_url_returns_none_for_invalid_url() -> None:
    owner, repo = _parse_github_url("not-a-url")  # pyright: ignore[reportPrivateUsage]

    assert owner is None
    assert repo is None


# ════════════════════════════════════════════════════════════════════════════
# VersionResolver: Async PyPI resolution
# ════════════════════════════════════════════════════════════════════════════


@dataclass
class MockResponse:
    """Mock HTTP response for testing."""

    status_code: int = 200
    _json: dict[str, Any] | list[Any] | None = None

    def json(self) -> dict[str, Any] | list[Any]:
        return self._json or {}

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                "Error",
                request=httpx.Request("GET", "http://test"),
                response=httpx.Response(self.status_code),
            )


@pytest.mark.os_agnostic
def test_resolver_returns_cached_pypi_result() -> None:
    resolver = VersionResolver()
    cached_result = VersionResult(latest_version="1.0.0")
    resolver.cache["pypi:requests"] = cached_result

    async def run() -> VersionResult:
        return await resolver.resolve_pypi_async("requests")

    result = asyncio.run(run())

    assert result is cached_result


@pytest.mark.os_agnostic
def test_resolver_parse_pypi_response_extracts_version() -> None:
    resolver = VersionResolver()
    mock_response = MockResponse(
        status_code=200,
        _json={"info": {"version": "2.31.0"}, "releases": {}},
    )

    result = resolver._parse_pypi_response(mock_response)  # pyright: ignore[reportPrivateUsage, reportArgumentType]

    assert result.latest_version == "2.31.0"


@pytest.mark.os_agnostic
def test_resolver_parse_pypi_response_handles_missing_version() -> None:
    resolver = VersionResolver()
    mock_response = MockResponse(
        status_code=200,
        _json={"info": {"version": ""}, "releases": {}},
    )

    result = resolver._parse_pypi_response(mock_response)  # pyright: ignore[reportPrivateUsage, reportArgumentType]

    assert result.is_unknown is True


# ════════════════════════════════════════════════════════════════════════════
# VersionResolver: Async GitHub resolution
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.os_agnostic
def test_resolver_returns_cached_github_result() -> None:
    resolver = VersionResolver()
    cached_result = VersionResult(latest_version="1.0.0")
    resolver.cache["github:owner/repo"] = cached_result

    async def run() -> VersionResult:
        return await resolver.resolve_github_async("owner", "repo")

    result = asyncio.run(run())

    assert result is cached_result


# ════════════════════════════════════════════════════════════════════════════
# VersionResolver: resolve_async dispatching
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.os_agnostic
def test_resolver_dispatches_pypi_dependency_to_pypi() -> None:
    resolver = VersionResolver()
    resolver.cache["pypi:requests"] = VersionResult(latest_version="2.31.0")
    dep = DependencyInfo(name="requests", raw_spec="requests>=2.0")

    async def run() -> VersionResult:
        return await resolver.resolve_async(dep)

    result = asyncio.run(run())

    assert result.latest_version == "2.31.0"


@pytest.mark.os_agnostic
def test_resolver_returns_unknown_for_unparseable_git_url() -> None:
    resolver = VersionResolver()
    dep = DependencyInfo(
        name="custom",
        raw_spec="custom",
        is_git_dependency=True,
        git_url="https://bitbucket.org/owner/repo",
    )

    async def run() -> VersionResult:
        return await resolver.resolve_async(dep)

    result = asyncio.run(run())

    assert result.is_unknown is True
    assert "Could not parse GitHub URL" in (result.error or "")


@pytest.mark.os_agnostic
def test_resolver_dispatches_github_dependency_to_github() -> None:
    resolver = VersionResolver()
    resolver.cache["github:owner/repo"] = VersionResult(latest_version="1.0.0")
    dep = DependencyInfo(
        name="custom",
        raw_spec="custom",
        is_git_dependency=True,
        git_url="git+https://github.com/owner/repo.git",
    )

    async def run() -> VersionResult:
        return await resolver.resolve_async(dep)

    result = asyncio.run(run())

    assert result.latest_version == "1.0.0"


# ════════════════════════════════════════════════════════════════════════════
# VersionResolver: resolve_sync wrapper
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.os_agnostic
def test_resolve_sync_returns_cached_result() -> None:
    resolver = VersionResolver()
    resolver.cache["pypi:requests"] = VersionResult(latest_version="2.31.0")
    dep = DependencyInfo(name="requests", raw_spec="requests>=2.0")

    result = resolver.resolve_sync(dep)

    assert result.latest_version == "2.31.0"


# ════════════════════════════════════════════════════════════════════════════
# VersionResolver: resolve_many_async concurrent resolution
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.os_agnostic
def test_resolve_many_returns_dict_of_results() -> None:
    resolver = VersionResolver()
    resolver.cache["pypi:requests"] = VersionResult(latest_version="2.31.0")
    resolver.cache["pypi:httpx"] = VersionResult(latest_version="0.25.0")

    deps = [
        DependencyInfo(name="requests", raw_spec="requests>=2.0"),
        DependencyInfo(name="httpx", raw_spec="httpx>=0.20"),
    ]

    async def run() -> dict[str, VersionResult]:
        return await resolver.resolve_many_async(deps)

    results = asyncio.run(run())

    assert results["requests"].latest_version == "2.31.0"
    assert results["httpx"].latest_version == "0.25.0"


@pytest.mark.os_agnostic
def test_resolve_many_respects_concurrency_limit() -> None:
    resolver = VersionResolver()
    resolver.cache["pypi:pkg1"] = VersionResult(latest_version="1.0.0")
    resolver.cache["pypi:pkg2"] = VersionResult(latest_version="2.0.0")
    resolver.cache["pypi:pkg3"] = VersionResult(latest_version="3.0.0")

    deps = [
        DependencyInfo(name="pkg1", raw_spec="pkg1"),
        DependencyInfo(name="pkg2", raw_spec="pkg2"),
        DependencyInfo(name="pkg3", raw_spec="pkg3"),
    ]

    async def run() -> dict[str, VersionResult]:
        return await resolver.resolve_many_async(deps, concurrency=2)

    results = asyncio.run(run())

    assert len(results) == 3


# ════════════════════════════════════════════════════════════════════════════
# resolve_pypi_version_cached: Synchronous cached lookup
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.os_agnostic
def test_resolve_pypi_version_cached_exists() -> None:
    assert callable(resolve_pypi_version_cached)


@pytest.mark.os_agnostic
def test_resolve_pypi_version_cached_is_lru_cached() -> None:
    assert hasattr(resolve_pypi_version_cached, "cache_clear")
    assert hasattr(resolve_pypi_version_cached, "cache_info")


# ════════════════════════════════════════════════════════════════════════════
# Module Exports: __all__ completeness
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.os_agnostic
def test_module_exports_version_resolver() -> None:
    assert "VersionResolver" in resolver_mod.__all__


@pytest.mark.os_agnostic
def test_module_exports_version_result() -> None:
    assert "VersionResult" in resolver_mod.__all__


@pytest.mark.os_agnostic
def test_module_exports_resolve_pypi_version_cached() -> None:
    assert "resolve_pypi_version_cached" in resolver_mod.__all__


# ════════════════════════════════════════════════════════════════════════════
# Module Constants: API endpoints
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.os_agnostic
def test_pypi_api_url_contains_placeholder() -> None:
    assert "{package}" in resolver_mod.PYPI_API_URL


@pytest.mark.os_agnostic
def test_github_api_releases_contains_placeholders() -> None:
    assert "{owner}" in resolver_mod.GITHUB_API_RELEASES
    assert "{repo}" in resolver_mod.GITHUB_API_RELEASES


@pytest.mark.os_agnostic
def test_github_api_tags_contains_placeholders() -> None:
    assert "{owner}" in resolver_mod.GITHUB_API_TAGS
    assert "{repo}" in resolver_mod.GITHUB_API_TAGS


@pytest.mark.os_agnostic
def test_default_timeout_is_positive() -> None:
    assert resolver_mod.DEFAULT_TIMEOUT > 0


# ════════════════════════════════════════════════════════════════════════════
# _is_python_compatible: Python version compatibility checking
# ════════════════════════════════════════════════════════════════════════════

# Common Python version instances for testing
PY38 = PythonVersion(major=3, minor=8)
PY39 = PythonVersion(major=3, minor=9)
PY310 = PythonVersion(major=3, minor=10)
PY311 = PythonVersion(major=3, minor=11)
PY312 = PythonVersion(major=3, minor=12)


@pytest.mark.os_agnostic
def test_is_python_compatible_returns_true_when_no_constraint() -> None:
    """No requires_python means compatible with all versions."""
    result = _is_python_compatible(None, PY38)  # pyright: ignore[reportPrivateUsage]

    assert result is True


@pytest.mark.os_agnostic
def test_is_python_compatible_returns_true_for_matching_constraint() -> None:
    """Version within constraint range is compatible."""
    result = _is_python_compatible(">=3.8", PY310)  # pyright: ignore[reportPrivateUsage]

    assert result is True


@pytest.mark.os_agnostic
def test_is_python_compatible_returns_false_for_version_below_minimum() -> None:
    """Version below minimum is not compatible."""
    result = _is_python_compatible(">=3.10", PY38)  # pyright: ignore[reportPrivateUsage]

    assert result is False


@pytest.mark.os_agnostic
def test_is_python_compatible_handles_upper_bound() -> None:
    """Version at or above upper bound is not compatible."""
    result = _is_python_compatible(">=3.8,<3.10", PY310)  # pyright: ignore[reportPrivateUsage]

    assert result is False


@pytest.mark.os_agnostic
def test_is_python_compatible_handles_empty_string() -> None:
    """Empty string is treated as no constraint."""
    result = _is_python_compatible("", PY38)  # pyright: ignore[reportPrivateUsage]

    assert result is True


# ════════════════════════════════════════════════════════════════════════════
# _find_latest_compatible_version: Python-version-aware version finding
# ════════════════════════════════════════════════════════════════════════════


def _make_pypi_response(
    latest_version: str,
    latest_requires_python: str | None,
    releases: dict[str, str | None],
) -> PyPIFullResponseSchema:
    """Create a mock PyPI response for testing.

    Args:
        latest_version: The version in info.version.
        latest_requires_python: The requires_python in info.
        releases: Dict of version -> requires_python for releases.

    Returns:
        A PyPIFullResponseSchema instance.
    """
    from pyproj_dep_analyze.schemas import PyPIFullInfoSchema

    release_files: dict[str, list[PyPIReleaseFileSchema]] = {}
    for ver, req_py in releases.items():
        release_files[ver] = [PyPIReleaseFileSchema(requires_python=req_py)]

    return PyPIFullResponseSchema(
        info=PyPIFullInfoSchema(
            name="test-package",
            version=latest_version,
            requires_python=latest_requires_python,
        ),
        releases=release_files,
    )


@pytest.mark.os_agnostic
def test_find_latest_compatible_returns_info_version_when_no_python_version() -> None:
    """Without python_version, returns the absolute latest."""
    response = _make_pypi_response(
        latest_version="2.0.0",
        latest_requires_python=">=3.10",
        releases={"2.0.0": ">=3.10", "1.0.0": ">=3.8"},
    )

    result = _find_latest_compatible_version(response, python_version=None)  # pyright: ignore[reportPrivateUsage]

    assert result == "2.0.0"


@pytest.mark.os_agnostic
def test_find_latest_compatible_returns_latest_when_compatible() -> None:
    """Returns latest when it's compatible with target Python."""
    response = _make_pypi_response(
        latest_version="2.0.0",
        latest_requires_python=">=3.8",
        releases={"2.0.0": ">=3.8", "1.0.0": ">=3.7"},
    )

    result = _find_latest_compatible_version(response, python_version=PY310)  # pyright: ignore[reportPrivateUsage]

    assert result == "2.0.0"


@pytest.mark.os_agnostic
def test_find_latest_compatible_returns_older_version_for_older_python() -> None:
    """Returns older compatible version when latest requires newer Python."""
    response = _make_pypi_response(
        latest_version="2.0.0",
        latest_requires_python=">=3.10",
        releases={"2.0.0": ">=3.10", "1.5.0": ">=3.9", "1.0.0": ">=3.8"},
    )

    result = _find_latest_compatible_version(response, python_version=PY38)  # pyright: ignore[reportPrivateUsage]

    assert result == "1.0.0"


@pytest.mark.os_agnostic
def test_find_latest_compatible_returns_none_when_no_compatible_version() -> None:
    """Returns None when no version is compatible."""
    response = _make_pypi_response(
        latest_version="2.0.0",
        latest_requires_python=">=3.12",
        releases={"2.0.0": ">=3.12", "1.0.0": ">=3.11"},
    )

    result = _find_latest_compatible_version(response, python_version=PY38)  # pyright: ignore[reportPrivateUsage]

    assert result is None


@pytest.mark.os_agnostic
def test_find_latest_compatible_skips_empty_releases() -> None:
    """Skips releases with no files."""
    from pyproj_dep_analyze.schemas import PyPIFullInfoSchema

    response = PyPIFullResponseSchema(
        info=PyPIFullInfoSchema(
            name="test-package",
            version="2.0.0",
            requires_python=">=3.10",
        ),
        releases={
            "2.0.0": [PyPIReleaseFileSchema(requires_python=">=3.10")],
            "1.5.0": [],  # Empty - should be skipped
            "1.0.0": [PyPIReleaseFileSchema(requires_python=">=3.8")],
        },
    )

    result = _find_latest_compatible_version(response, python_version=PY38)  # pyright: ignore[reportPrivateUsage]

    assert result == "1.0.0"


@pytest.mark.os_agnostic
def test_find_latest_compatible_handles_no_requires_python_in_release() -> None:
    """Release without requires_python is considered compatible with all."""
    response = _make_pypi_response(
        latest_version="2.0.0",
        latest_requires_python=">=3.10",
        releases={"2.0.0": ">=3.10", "1.0.0": None},  # No requires_python
    )

    result = _find_latest_compatible_version(response, python_version=PY38)  # pyright: ignore[reportPrivateUsage]

    assert result == "1.0.0"


# ════════════════════════════════════════════════════════════════════════════
# VersionResolver: Python-version-specific cache keys
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.os_agnostic
def test_resolver_uses_different_cache_keys_per_python_version() -> None:
    """Cache key includes Python version for version-specific lookups."""
    resolver = VersionResolver()

    # Pre-populate cache with different results per Python version
    resolver.cache["pypi:requests:3.8"] = VersionResult(latest_version="2.28.0")
    resolver.cache["pypi:requests:3.10"] = VersionResult(latest_version="2.31.0")

    async def run_38() -> VersionResult:
        return await resolver.resolve_pypi_async("requests", PY38)

    async def run_310() -> VersionResult:
        return await resolver.resolve_pypi_async("requests", PY310)

    result_38 = asyncio.run(run_38())
    result_310 = asyncio.run(run_310())

    assert result_38.latest_version == "2.28.0"
    assert result_310.latest_version == "2.31.0"


@pytest.mark.os_agnostic
def test_resolver_cache_key_without_python_version() -> None:
    """Cache key without Python version for unconstrained lookups."""
    resolver = VersionResolver()
    resolver.cache["pypi:requests"] = VersionResult(latest_version="2.31.0")

    async def run() -> VersionResult:
        return await resolver.resolve_pypi_async("requests", python_version=None)

    result = asyncio.run(run())

    assert result.latest_version == "2.31.0"


@pytest.mark.os_agnostic
def test_resolver_parse_pypi_response_with_python_version() -> None:
    """Parser finds compatible version when Python version specified."""
    resolver = VersionResolver()
    mock_response = MockResponse(
        status_code=200,
        _json={
            "info": {"version": "2.31.0", "requires_python": ">=3.10"},
            "releases": {
                "2.31.0": [{"requires_python": ">=3.10"}],
                "2.28.0": [{"requires_python": ">=3.8"}],
            },
        },
    )

    result = resolver._parse_pypi_response(  # pyright: ignore[reportPrivateUsage]
        mock_response,  # pyright: ignore[reportArgumentType]
        python_version=PY38,
    )

    assert result.latest_version == "2.28.0"
