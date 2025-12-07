"""Repository metadata resolver for GitHub/GitLab.

Purpose
-------
Detect repository URLs from PyPI metadata and fetch lightweight
repository information without security-specific data.

Contents
--------
* :func:`detect_repo_url` - Extract repo URL from PyPI project_urls
* :func:`parse_repo_url` - Parse owner/repo from URL
* :class:`RepoResolver` - Async resolver for repository metadata

System Role
-----------
Provides repository metadata enrichment for packages. Works alongside
version_resolver to provide additional context about package sources.
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

import httpx
from pydantic import BaseModel, ConfigDict

from .models import RepoMetadata, RepoType

if TYPE_CHECKING:
    from .schemas import GitHubRepoResponseSchema

logger = logging.getLogger(__name__)

# URL patterns for repository detection
_RE_GITHUB_URL = re.compile(
    r"(?:https?://)?(?:www\.)?github\.com/([^/]+)/([^/\s?#]+)",
    re.IGNORECASE,
)
_RE_GITLAB_URL = re.compile(
    r"(?:https?://)?(?:www\.)?gitlab\.com/([^/]+)/([^/\s?#]+)",
    re.IGNORECASE,
)

# GitHub API endpoint
GITHUB_REPO_API = "https://api.github.com/repos/{owner}/{repo}"

# HTTP header constants for GitHub API requests
_HEADER_ACCEPT = "Accept"
_HEADER_USER_AGENT = "User-Agent"
_HEADER_AUTHORIZATION = "Authorization"
_GITHUB_ACCEPT_VALUE = "application/vnd.github.v3+json"
_USER_AGENT_VALUE = "pyproj-dep-analyze/1.0"


class ProjectUrlKey(str, Enum):
    """Known project URL keys from PyPI metadata.

    Represents common keys found in project_urls that typically
    point to repository locations.
    """

    SOURCE = "Source"
    SOURCE_CODE = "Source Code"
    REPOSITORY = "Repository"
    CODE = "Code"
    GITHUB = "GitHub"
    HOMEPAGE = "Homepage"
    HOME = "Home"


class CacheKeyPrefix(str, Enum):
    """Cache key prefixes for repository types."""

    GITHUB = "github"
    GITLAB = "gitlab"


def _make_cache_key(prefix: CacheKeyPrefix, owner: str, repo: str) -> str:
    """Create a typed cache key.

    Args:
        prefix: Cache key prefix enum.
        owner: Repository owner.
        repo: Repository name.

    Returns:
        Formatted cache key string.
    """
    return f"{prefix.value}:{owner}/{repo}"


# Priority order for project_urls keys that likely contain source repo
_REPO_URL_KEYS = tuple(ProjectUrlKey)


class PyPIUrlMetadata(BaseModel):
    """Metadata for PyPI package URL resolution.

    Contains URL information needed to detect repository locations.

    Attributes:
        project_urls: Dict of labeled URLs from PyPI info (e.g., Source, Homepage).
        home_page: Fallback home_page URL from PyPI metadata.
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    project_urls: dict[str, str] = {}
    home_page: str | None = None


class ParsedRepoUrl(BaseModel):
    """Result of parsing a repository URL.

    Contains the structured information extracted from a repository URL.

    Attributes:
        repo_type: The type of repository hosting platform.
        owner: Repository owner/organization name.
        repo_name: Repository name.
    """

    model_config = ConfigDict(frozen=True)

    repo_type: RepoType
    owner: str | None = None
    repo_name: str | None = None


def detect_repo_url(metadata: PyPIUrlMetadata) -> str | None:
    """Detect repository URL from PyPI metadata.

    Args:
        metadata: PyPI URL metadata containing project_urls and home_page.

    Returns:
        Detected repository URL or None.
    """
    # Check known keys in priority order
    for key_enum in _REPO_URL_KEYS:
        key_value = key_enum.value
        for url_key, url in metadata.project_urls.items():
            if key_value.lower() in url_key.lower():
                if _RE_GITHUB_URL.search(url) or _RE_GITLAB_URL.search(url):
                    return url

    # Fallback: check home_page
    if metadata.home_page:
        if _RE_GITHUB_URL.search(metadata.home_page) or _RE_GITLAB_URL.search(metadata.home_page):
            return metadata.home_page

    return None


def parse_repo_url(url: str) -> ParsedRepoUrl:
    """Parse repository URL into structured result.

    Args:
        url: Repository URL.

    Returns:
        ParsedRepoUrl containing repo_type, owner, and repo_name.
    """
    github_match = _RE_GITHUB_URL.search(url)
    if github_match:
        owner = github_match.group(1)
        repo = github_match.group(2)
        if repo.endswith(".git"):
            repo = repo[:-4]
        return ParsedRepoUrl(repo_type=RepoType.GITHUB, owner=owner, repo_name=repo)

    gitlab_match = _RE_GITLAB_URL.search(url)
    if gitlab_match:
        owner = gitlab_match.group(1)
        repo = gitlab_match.group(2)
        if repo.endswith(".git"):
            repo = repo[:-4]
        return ParsedRepoUrl(repo_type=RepoType.GITLAB, owner=owner, repo_name=repo)

    return ParsedRepoUrl(repo_type=RepoType.UNKNOWN, owner=None, repo_name=None)


def _empty_repo_cache() -> dict[str, RepoMetadata]:
    """Return empty cache dict for dataclass default.

    Note: Dict is used for cache storage where keys are dynamic package names
    and values are typed RepoMetadata models. This is an acceptable pattern
    for runtime caches with typed values.
    """
    return {}


@dataclass
class RepoResolver:
    """Async resolver for repository metadata.

    Attributes:
        timeout: Request timeout in seconds.
        github_token: Optional GitHub token for API authentication.
        cache: In-memory cache of resolved metadata.
    """

    timeout: float = 30.0
    github_token: str | None = None
    cache: dict[str, RepoMetadata] = field(default_factory=_empty_repo_cache)

    def __repr__(self) -> str:
        """Return repr with token redacted."""
        token_display = "***" if self.github_token else "None"
        return f"RepoResolver(timeout={self.timeout}, github_token={token_display})"

    def _get_github_headers(self) -> dict[str, str]:
        """Get HTTP headers for GitHub API requests.

        Note: HTTP headers are inherently key-value pairs. Dict is acceptable
        at this boundary as it matches the httpx API contract.
        """
        headers = {
            _HEADER_ACCEPT: _GITHUB_ACCEPT_VALUE,
            _HEADER_USER_AGENT: _USER_AGENT_VALUE,
        }
        if self.github_token:
            headers[_HEADER_AUTHORIZATION] = f"token {self.github_token}"
        return headers

    async def resolve_github_async(self, owner: str, repo: str) -> RepoMetadata:
        """Fetch repository metadata from GitHub API.

        Args:
            owner: Repository owner.
            repo: Repository name.

        Returns:
            Populated RepoMetadata instance.
        """
        cache_key = _make_cache_key(CacheKeyPrefix.GITHUB, owner, repo)
        if cache_key in self.cache:
            return self.cache[cache_key]

        metadata = await self._fetch_github_metadata(owner, repo)
        self.cache[cache_key] = metadata
        return metadata

    async def _fetch_github_metadata(self, owner: str, repo: str) -> RepoMetadata:
        """Fetch metadata from GitHub API."""
        from .schemas import GitHubRepoResponseSchema

        url = GITHUB_REPO_API.format(owner=owner, repo=repo)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, headers=self._get_github_headers())

            if response.status_code != 200:
                logger.warning("GitHub API returned %d for %s/%s", response.status_code, owner, repo)
                return RepoMetadata(repo_type=RepoType.GITHUB, owner=owner, name=repo)

            parsed = GitHubRepoResponseSchema.model_validate(response.json())
            return self._build_metadata_from_schema(parsed, owner, repo)

        except httpx.TimeoutException:
            logger.warning("Timeout fetching GitHub metadata for %s/%s", owner, repo)
            return RepoMetadata(repo_type=RepoType.GITHUB, owner=owner, name=repo)
        except Exception as e:
            logger.warning("Error fetching GitHub metadata: %s", e)
            return RepoMetadata(repo_type=RepoType.GITHUB, owner=owner, name=repo)

    def _build_metadata_from_schema(
        self,
        parsed: GitHubRepoResponseSchema,
        owner: str,
        repo: str,
    ) -> RepoMetadata:
        """Build RepoMetadata from parsed Pydantic schema."""
        return RepoMetadata(
            repo_type=RepoType.GITHUB,
            url=parsed.html_url,
            owner=owner,
            name=repo,
            stars=parsed.stargazers_count,
            forks=parsed.forks_count,
            open_issues=parsed.open_issues_count,
            default_branch=parsed.default_branch,
            last_commit_date=parsed.pushed_at,
            created_at=parsed.created_at,
            description=parsed.description,
        )

    async def resolve_from_pypi_metadata_async(
        self,
        metadata: PyPIUrlMetadata,
    ) -> RepoMetadata | None:
        """Resolve repository metadata from PyPI metadata.

        Args:
            metadata: PyPI URL metadata containing project_urls and home_page.

        Returns:
            RepoMetadata if a repository was detected, None otherwise.
        """
        repo_url = detect_repo_url(metadata)
        if not repo_url:
            return None

        parsed = parse_repo_url(repo_url)

        if parsed.repo_type == RepoType.GITHUB and parsed.owner and parsed.repo_name:
            return await self.resolve_github_async(parsed.owner, parsed.repo_name)

        # Return basic metadata for non-GitHub repos
        return RepoMetadata(
            repo_type=parsed.repo_type,
            url=repo_url,
            owner=parsed.owner,
            name=parsed.repo_name,
        )

    async def resolve_many_async(
        self,
        metadata_list: list[PyPIUrlMetadata],
        concurrency: int = 10,
    ) -> list[RepoMetadata | None]:
        """Resolve repository metadata for multiple packages.

        Args:
            metadata_list: List of PyPIUrlMetadata instances.
            concurrency: Maximum concurrent requests.

        Returns:
            List of RepoMetadata or None for each input.
        """
        semaphore = asyncio.Semaphore(concurrency)

        async def resolve_one(
            metadata: PyPIUrlMetadata,
        ) -> RepoMetadata | None:
            async with semaphore:
                return await self.resolve_from_pypi_metadata_async(metadata)

        tasks = [resolve_one(meta) for meta in metadata_list]
        return await asyncio.gather(*tasks)


__all__ = [
    "CacheKeyPrefix",
    "ParsedRepoUrl",
    "ProjectUrlKey",
    "PyPIUrlMetadata",
    "RepoResolver",
    "detect_repo_url",
    "parse_repo_url",
]
