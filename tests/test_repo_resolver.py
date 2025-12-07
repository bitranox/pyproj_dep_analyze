"""Repository resolver stories: packages reveal their source repositories.

The repo_resolver module detects repository URLs from PyPI metadata and fetches
lightweight repository information from GitHub/GitLab. These tests verify URL
detection, parsing, and API response handling.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from pyproj_dep_analyze.models import RepoMetadata, RepoType
from pyproj_dep_analyze.repo_resolver import (
    PyPIUrlMetadata,
    RepoResolver,
    detect_repo_url,
    parse_repo_url,
    _RE_GITHUB_URL,  # pyright: ignore[reportPrivateUsage]
    _RE_GITLAB_URL,  # pyright: ignore[reportPrivateUsage]
    GITHUB_REPO_API,
)


# ════════════════════════════════════════════════════════════════════════════
# RepoMetadata: The repository metadata container
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.os_agnostic
def test_repo_metadata_stores_repo_type() -> None:
    from pyproj_dep_analyze.models import RepoType

    metadata = RepoMetadata(repo_type=RepoType.GITHUB)

    assert metadata.repo_type == RepoType.GITHUB


@pytest.mark.os_agnostic
def test_repo_metadata_stores_url() -> None:
    from pyproj_dep_analyze.models import RepoType

    metadata = RepoMetadata(repo_type=RepoType.GITHUB, url="https://github.com/owner/repo")

    assert metadata.url == "https://github.com/owner/repo"


@pytest.mark.os_agnostic
def test_repo_metadata_stores_owner_and_name() -> None:
    from pyproj_dep_analyze.models import RepoType

    metadata = RepoMetadata(repo_type=RepoType.GITHUB, owner="psf", name="requests")

    assert metadata.owner == "psf"
    assert metadata.name == "requests"


@pytest.mark.os_agnostic
def test_repo_metadata_stores_stats() -> None:
    from pyproj_dep_analyze.models import RepoType

    metadata = RepoMetadata(
        repo_type=RepoType.GITHUB,
        stars=50000,
        forks=9000,
        open_issues=100,
    )

    assert metadata.stars == 50000
    assert metadata.forks == 9000
    assert metadata.open_issues == 100


@pytest.mark.os_agnostic
def test_repo_metadata_stores_dates() -> None:
    from pyproj_dep_analyze.models import RepoType

    metadata = RepoMetadata(
        repo_type=RepoType.GITHUB,
        last_commit_date="2024-01-15T10:00:00Z",
        created_at="2011-02-13T18:38:17Z",
    )

    assert metadata.last_commit_date == "2024-01-15T10:00:00Z"
    assert metadata.created_at == "2011-02-13T18:38:17Z"


@pytest.mark.os_agnostic
def test_repo_metadata_defaults() -> None:
    metadata = RepoMetadata()

    assert metadata.repo_type == "unknown"  # Default value
    assert metadata.url is None
    assert metadata.owner is None
    assert metadata.name is None
    assert metadata.stars is None


# ════════════════════════════════════════════════════════════════════════════
# detect_repo_url: Extract repository URL from PyPI metadata
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.os_agnostic
def test_detect_repo_url_finds_github_in_source_key() -> None:
    metadata = PyPIUrlMetadata(project_urls={"Source": "https://github.com/psf/requests"})

    result = detect_repo_url(metadata)

    assert result == "https://github.com/psf/requests"


@pytest.mark.os_agnostic
def test_detect_repo_url_finds_github_in_source_code_key() -> None:
    metadata = PyPIUrlMetadata(project_urls={"Source Code": "https://github.com/psf/requests"})

    result = detect_repo_url(metadata)

    assert result == "https://github.com/psf/requests"


@pytest.mark.os_agnostic
def test_detect_repo_url_finds_github_in_repository_key() -> None:
    metadata = PyPIUrlMetadata(project_urls={"Repository": "https://github.com/psf/requests"})

    result = detect_repo_url(metadata)

    assert result == "https://github.com/psf/requests"


@pytest.mark.os_agnostic
def test_detect_repo_url_finds_github_in_homepage_key() -> None:
    metadata = PyPIUrlMetadata(project_urls={"Homepage": "https://github.com/psf/requests"})

    result = detect_repo_url(metadata)

    assert result == "https://github.com/psf/requests"


@pytest.mark.os_agnostic
def test_detect_repo_url_finds_gitlab_url() -> None:
    metadata = PyPIUrlMetadata(project_urls={"Source": "https://gitlab.com/owner/project"})

    result = detect_repo_url(metadata)

    assert result == "https://gitlab.com/owner/project"


@pytest.mark.os_agnostic
def test_detect_repo_url_uses_home_page_fallback() -> None:
    metadata = PyPIUrlMetadata(project_urls={}, home_page="https://github.com/psf/requests")

    result = detect_repo_url(metadata)

    assert result == "https://github.com/psf/requests"


@pytest.mark.os_agnostic
def test_detect_repo_url_returns_none_for_non_repo_urls() -> None:
    metadata = PyPIUrlMetadata(project_urls={"Homepage": "https://requests.readthedocs.io"})

    result = detect_repo_url(metadata)

    assert result is None


@pytest.mark.os_agnostic
def test_detect_repo_url_returns_none_for_empty_urls() -> None:
    metadata = PyPIUrlMetadata(project_urls={})

    result = detect_repo_url(metadata)

    assert result is None


@pytest.mark.os_agnostic
def test_detect_repo_url_case_insensitive_key_matching() -> None:
    metadata = PyPIUrlMetadata(project_urls={"SOURCE CODE": "https://github.com/psf/requests"})

    result = detect_repo_url(metadata)

    assert result == "https://github.com/psf/requests"


# ════════════════════════════════════════════════════════════════════════════
# parse_repo_url: Parse owner and repo from URL
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.os_agnostic
def test_parse_repo_url_extracts_github_owner_repo() -> None:
    from pyproj_dep_analyze.models import RepoType

    parsed = parse_repo_url("https://github.com/psf/requests")

    assert parsed.repo_type == RepoType.GITHUB
    assert parsed.owner == "psf"
    assert parsed.repo_name == "requests"


@pytest.mark.os_agnostic
def test_parse_repo_url_strips_git_suffix() -> None:
    parsed = parse_repo_url("https://github.com/psf/requests.git")

    assert parsed.repo_name == "requests"


@pytest.mark.os_agnostic
def test_parse_repo_url_handles_www_prefix() -> None:
    from pyproj_dep_analyze.models import RepoType

    parsed = parse_repo_url("https://www.github.com/psf/requests")

    assert parsed.repo_type == RepoType.GITHUB
    assert parsed.owner == "psf"


@pytest.mark.os_agnostic
def test_parse_repo_url_extracts_gitlab_owner_repo() -> None:
    from pyproj_dep_analyze.models import RepoType

    parsed = parse_repo_url("https://gitlab.com/owner/project")

    assert parsed.repo_type == RepoType.GITLAB
    assert parsed.owner == "owner"
    assert parsed.repo_name == "project"


@pytest.mark.os_agnostic
def test_parse_repo_url_returns_unknown_for_other_hosts() -> None:
    from pyproj_dep_analyze.models import RepoType

    parsed = parse_repo_url("https://bitbucket.org/owner/repo")

    assert parsed.repo_type == RepoType.UNKNOWN
    assert parsed.owner is None
    assert parsed.repo_name is None


@pytest.mark.os_agnostic
def test_parse_repo_url_handles_http_prefix() -> None:
    from pyproj_dep_analyze.models import RepoType

    parsed = parse_repo_url("http://github.com/psf/requests")

    assert parsed.repo_type == RepoType.GITHUB
    assert parsed.owner == "psf"


# ════════════════════════════════════════════════════════════════════════════
# RepoResolver: Async resolver for repository metadata
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.os_agnostic
def test_repo_resolver_has_default_timeout() -> None:
    resolver = RepoResolver()

    assert resolver.timeout == 30.0


@pytest.mark.os_agnostic
def test_repo_resolver_accepts_custom_timeout() -> None:
    resolver = RepoResolver(timeout=60.0)

    assert resolver.timeout == 60.0


@pytest.mark.os_agnostic
def test_repo_resolver_accepts_github_token() -> None:
    resolver = RepoResolver(github_token="test-token")

    assert resolver.github_token == "test-token"


@pytest.mark.os_agnostic
def test_repo_resolver_repr_redacts_token() -> None:
    resolver = RepoResolver(github_token="secret-token")

    repr_str = repr(resolver)

    assert "secret-token" not in repr_str
    assert "***" in repr_str


@pytest.mark.os_agnostic
def test_repo_resolver_repr_shows_none_when_no_token() -> None:
    resolver = RepoResolver()

    repr_str = repr(resolver)

    assert "github_token=None" in repr_str


@pytest.mark.os_agnostic
def test_repo_resolver_has_empty_cache_initially() -> None:
    resolver = RepoResolver()

    assert resolver.cache == {}


@pytest.mark.os_agnostic
def test_repo_resolver_returns_cached_result() -> None:
    from pyproj_dep_analyze.models import RepoType

    resolver = RepoResolver()
    cached_metadata = RepoMetadata(repo_type=RepoType.GITHUB, owner="psf", name="requests", stars=50000)
    resolver.cache["github:psf/requests"] = cached_metadata

    result = asyncio.run(resolver.resolve_github_async("psf", "requests"))

    assert result == cached_metadata


@pytest.mark.os_agnostic
def test_repo_resolver_github_headers_include_accept() -> None:
    resolver = RepoResolver()

    headers = resolver._get_github_headers()  # pyright: ignore[reportPrivateUsage]

    assert "Accept" in headers
    assert "application/vnd.github.v3+json" in headers["Accept"]


@pytest.mark.os_agnostic
def test_repo_resolver_github_headers_include_user_agent() -> None:
    resolver = RepoResolver()

    headers = resolver._get_github_headers()  # pyright: ignore[reportPrivateUsage]

    assert "User-Agent" in headers


@pytest.mark.os_agnostic
def test_repo_resolver_github_headers_include_auth_when_token_set() -> None:
    resolver = RepoResolver(github_token="test-token")

    headers = resolver._get_github_headers()  # pyright: ignore[reportPrivateUsage]

    assert "Authorization" in headers
    assert headers["Authorization"] == "token test-token"


@pytest.mark.os_agnostic
def test_repo_resolver_github_headers_no_auth_when_no_token() -> None:
    resolver = RepoResolver()

    headers = resolver._get_github_headers()  # pyright: ignore[reportPrivateUsage]

    assert "Authorization" not in headers


@pytest.mark.os_agnostic
def test_repo_resolver_parses_github_response() -> None:
    resolver = RepoResolver()
    github_data: dict[str, object] = {
        "html_url": "https://github.com/psf/requests",
        "stargazers_count": 50000,
        "forks_count": 9000,
        "open_issues_count": 100,
        "default_branch": "main",
        "pushed_at": "2024-01-15T10:00:00Z",
        "created_at": "2011-02-13T18:38:17Z",
        "description": "A simple HTTP library",
    }
    from pyproj_dep_analyze.models import RepoType
    from pyproj_dep_analyze.schemas import GitHubRepoResponseSchema

    parsed = GitHubRepoResponseSchema.model_validate(github_data)
    result = resolver._build_metadata_from_schema(parsed, "psf", "requests")  # pyright: ignore[reportPrivateUsage]

    assert result.repo_type == RepoType.GITHUB
    assert result.owner == "psf"
    assert result.name == "requests"
    assert result.stars == 50000
    assert result.forks == 9000
    assert result.open_issues == 100
    assert result.default_branch == "main"
    assert result.description == "A simple HTTP library"


@pytest.mark.os_agnostic
def test_repo_resolver_handles_missing_github_fields() -> None:
    from pyproj_dep_analyze.models import RepoType
    from pyproj_dep_analyze.schemas import GitHubRepoResponseSchema

    resolver = RepoResolver()
    github_data: dict[str, object] = {}

    parsed = GitHubRepoResponseSchema.model_validate(github_data)
    result = resolver._build_metadata_from_schema(parsed, "psf", "requests")  # pyright: ignore[reportPrivateUsage]

    assert result.repo_type == RepoType.GITHUB
    assert result.owner == "psf"
    assert result.name == "requests"
    assert result.stars is None
    assert result.url is None


@pytest.mark.os_agnostic
def test_repo_resolver_fetch_handles_non_200_response() -> None:
    from pyproj_dep_analyze.models import RepoType

    resolver = RepoResolver()

    mock_response = MagicMock()
    mock_response.status_code = 404

    with patch("httpx.AsyncClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.get.return_value = mock_response
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.__aexit__.return_value = None
        mock_client.return_value = mock_instance

        result = asyncio.run(resolver._fetch_github_metadata("nonexistent", "repo"))  # pyright: ignore[reportPrivateUsage]

    assert result.repo_type == RepoType.GITHUB
    assert result.owner == "nonexistent"
    assert result.name == "repo"
    assert result.stars is None


@pytest.mark.os_agnostic
def test_repo_resolver_fetch_handles_timeout() -> None:
    from pyproj_dep_analyze.models import RepoType

    resolver = RepoResolver()

    with patch("httpx.AsyncClient") as mock_client:
        mock_instance = AsyncMock()
        mock_instance.get.side_effect = httpx.TimeoutException("timeout")
        mock_instance.__aenter__.return_value = mock_instance
        mock_instance.__aexit__.return_value = None
        mock_client.return_value = mock_instance

        result = asyncio.run(resolver._fetch_github_metadata("owner", "repo"))  # pyright: ignore[reportPrivateUsage]

    assert result.repo_type == RepoType.GITHUB
    assert result.stars is None


@pytest.mark.os_agnostic
def test_repo_resolver_resolve_from_pypi_returns_none_no_repo_url() -> None:
    resolver = RepoResolver()
    metadata = PyPIUrlMetadata(project_urls={"Documentation": "https://docs.example.com"})

    result = asyncio.run(resolver.resolve_from_pypi_metadata_async(metadata))

    assert result is None


@pytest.mark.os_agnostic
def test_repo_resolver_resolve_from_pypi_returns_none_for_non_github_gitlab() -> None:
    # detect_repo_url only detects GitHub and GitLab URLs
    resolver = RepoResolver()
    metadata = PyPIUrlMetadata(project_urls={"Source": "https://bitbucket.org/owner/repo"})

    result = asyncio.run(resolver.resolve_from_pypi_metadata_async(metadata))

    # Returns None because detect_repo_url doesn't recognize Bitbucket
    assert result is None


@pytest.mark.os_agnostic
def test_repo_resolver_resolve_from_pypi_returns_metadata_for_gitlab() -> None:
    resolver = RepoResolver()
    metadata = PyPIUrlMetadata(project_urls={"Source": "https://gitlab.com/owner/project"})

    result = asyncio.run(resolver.resolve_from_pypi_metadata_async(metadata))

    assert result is not None
    assert result.repo_type == RepoType.GITLAB
    assert result.owner == "owner"
    assert result.name == "project"


@pytest.mark.os_agnostic
def test_repo_resolver_resolve_many_returns_list() -> None:
    resolver = RepoResolver()
    # Pre-populate cache
    resolver.cache["github:psf/requests"] = RepoMetadata(repo_type=RepoType.GITHUB, owner="psf", name="requests")

    metadata_list = [
        PyPIUrlMetadata(project_urls={"Source": "https://github.com/psf/requests"}),
        PyPIUrlMetadata(project_urls={}),  # No repo URL
    ]

    result = asyncio.run(resolver.resolve_many_async(metadata_list))

    assert len(result) == 2
    assert result[0] is not None
    assert result[1] is None


# ════════════════════════════════════════════════════════════════════════════
# URL regex patterns
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.os_agnostic
def test_github_url_regex_matches_https() -> None:
    match = _RE_GITHUB_URL.search("https://github.com/psf/requests")

    assert match is not None
    assert match.group(1) == "psf"
    assert match.group(2) == "requests"


@pytest.mark.os_agnostic
def test_github_url_regex_matches_http() -> None:
    match = _RE_GITHUB_URL.search("http://github.com/psf/requests")

    assert match is not None


@pytest.mark.os_agnostic
def test_gitlab_url_regex_matches_https() -> None:
    match = _RE_GITLAB_URL.search("https://gitlab.com/owner/project")

    assert match is not None
    assert match.group(1) == "owner"
    assert match.group(2) == "project"


# ════════════════════════════════════════════════════════════════════════════
# Constants
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.os_agnostic
def test_github_repo_api_url_has_placeholders() -> None:
    assert "{owner}" in GITHUB_REPO_API
    assert "{repo}" in GITHUB_REPO_API


# ════════════════════════════════════════════════════════════════════════════
# Module exports
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.os_agnostic
def test_module_exports_repo_resolver() -> None:
    from pyproj_dep_analyze import repo_resolver

    assert hasattr(repo_resolver, "RepoResolver")


@pytest.mark.os_agnostic
def test_module_exports_detect_repo_url() -> None:
    from pyproj_dep_analyze import repo_resolver

    assert hasattr(repo_resolver, "detect_repo_url")


@pytest.mark.os_agnostic
def test_module_exports_parse_repo_url() -> None:
    from pyproj_dep_analyze import repo_resolver

    assert hasattr(repo_resolver, "parse_repo_url")
