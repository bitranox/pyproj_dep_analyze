"""Version resolvers for PyPI and GitHub packages.

Purpose
-------
Determine the latest compatible version for each dependency by querying
PyPI or GitHub APIs based on the package source.

Contents
--------
* :func:`resolve_pypi_version` - Get latest version from PyPI
* :func:`resolve_github_version` - Get latest version from GitHub releases/tags
* :func:`resolve_version` - Main resolver that dispatches to the appropriate source
* :class:`VersionResolver` - Async resolver with caching and rate limiting

System Role
-----------
Handles all external API calls to determine latest available versions.
Uses caching to minimize API requests and respects rate limits.
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from functools import lru_cache

import httpx
from pydantic import TypeAdapter

from .models import DependencyInfo, PyPIMetadata, PythonVersion, VersionMetrics
from .python_version_parser import parse_requires_python
from .schemas import GitHubReleaseSchema, GitHubTagSchema, PyPIFullResponseSchema

logger = logging.getLogger(__name__)

# Precompiled regex patterns for version extraction
_RE_VERSION_SIMPLE = re.compile(r"^v?(\d+\.\d+(?:\.\d+)?(?:[.-]?\w+)?)$", re.IGNORECASE)
_RE_VERSION_PREFIXED = re.compile(r"^(?:release|version|ver)[_-]?v?(\d+\.\d+(?:\.\d+)?(?:[.-]?\w+)?)$", re.IGNORECASE)
_RE_NUMERIC_PARTS = re.compile(r"\d+")
_RE_GIT_PREFIX = re.compile(r"^git\+")
_RE_GIT_SUFFIX = re.compile(r"\.git(?=@|$)")
_RE_GITHUB_URL = re.compile(r"github\.com[/:]([^/]+)/([^/@]+)")

# PyPI API endpoints
PYPI_API_URL = "https://pypi.org/pypi/{package}/json"

# GitHub API endpoints
GITHUB_API_RELEASES = "https://api.github.com/repos/{owner}/{repo}/releases"
GITHUB_API_TAGS = "https://api.github.com/repos/{owner}/{repo}/tags"

# Default timeout for API requests
DEFAULT_TIMEOUT = 30.0


@dataclass
class VersionResult:
    """Result of a version resolution attempt.

    Attributes:
        latest_version: The latest version found, or None if not found.
        is_unknown: Whether the version could not be determined.
        error: Error message if resolution failed.
        pypi_metadata: Enriched PyPI metadata if available.
    """

    latest_version: str | None = None
    is_unknown: bool = False
    error: str | None = None
    pypi_metadata: PyPIMetadata | None = None


def _empty_cache() -> dict[str, VersionResult]:
    """Return an empty cache dict for dataclass defaults."""
    return {}


@dataclass
class VersionResolver:
    """Async version resolver with caching.

    Attributes:
        timeout: Request timeout in seconds.
        github_token: Optional GitHub token for API authentication.
        cache: In-memory cache of resolved versions.
    """

    timeout: float = DEFAULT_TIMEOUT
    github_token: str | None = None
    cache: dict[str, VersionResult] = field(default_factory=_empty_cache)
    _pending: dict[str, asyncio.Future[VersionResult]] = field(default_factory=lambda: {}, repr=False)

    def __repr__(self) -> str:
        """Return repr with token redacted."""
        token_display = "***" if self.github_token else "None"
        return f"VersionResolver(timeout={self.timeout}, github_token={token_display})"

    def _get_headers(self, for_github: bool = False) -> dict[str, str]:
        """Get HTTP headers for API requests."""
        headers = {"Accept": "application/json", "User-Agent": "pyproj-dep-analyze/1.0"}
        if for_github and self.github_token:
            headers["Authorization"] = f"token {self.github_token}"
        return headers

    async def resolve_pypi_async(
        self,
        package_name: str,
        python_version: PythonVersion | None = None,
    ) -> VersionResult:
        """Resolve the latest Python-compatible version of a package from PyPI.

        Args:
            package_name: The normalized package name.
            python_version: Target Python version to check compatibility against.
                If None, returns the absolute latest version.

        Returns:
            Result containing the latest compatible version or error.
        """
        # Include Python version in cache key for version-specific lookups
        py_key = f":{python_version}" if python_version else ""
        cache_key = f"pypi:{package_name}{py_key}"
        if cache_key in self.cache:
            return self.cache[cache_key]

        # Check if another task is already fetching this package+version combo
        if cache_key in self._pending:
            return await self._pending[cache_key]

        # Create a future for this fetch to prevent duplicate requests
        loop = asyncio.get_running_loop()
        future: asyncio.Future[VersionResult] = loop.create_future()
        self._pending[cache_key] = future

        try:
            result = await self._fetch_pypi_version(package_name, python_version)
            self.cache[cache_key] = result
            future.set_result(result)
            return result
        except Exception as exc:
            future.set_exception(exc)
            raise
        finally:
            self._pending.pop(cache_key, None)

    async def _fetch_pypi_version(
        self,
        package_name: str,
        python_version: PythonVersion | None = None,
    ) -> VersionResult:
        """Fetch version from PyPI API."""
        url = PYPI_API_URL.format(package=package_name)
        try:
            return await self._query_pypi_api(url, package_name, python_version)
        except httpx.TimeoutException:
            return VersionResult(is_unknown=True, error=f"Timeout querying PyPI for {package_name}")
        except httpx.HTTPError as e:
            return VersionResult(is_unknown=True, error=f"HTTP error querying PyPI: {e}")
        except Exception as e:
            return VersionResult(is_unknown=True, error=f"Error querying PyPI: {e}")

    async def _query_pypi_api(
        self,
        url: str,
        package_name: str,
        python_version: PythonVersion | None = None,
    ) -> VersionResult:
        """Query PyPI API and parse response."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url, headers=self._get_headers())

        if response.status_code == 404:
            return VersionResult(is_unknown=True, error=f"Package {package_name} not found on PyPI")

        response.raise_for_status()
        return self._parse_pypi_response(response, python_version)

    def _parse_pypi_response(
        self,
        response: httpx.Response,
        python_version: PythonVersion | None = None,
    ) -> VersionResult:
        """Parse PyPI API response into VersionResult with full metadata.

        If python_version is specified, finds the latest version compatible with
        that Python version by checking requires_python for each release.

        Note: Parsing response twice (minimal schema and full schema) is intentional:
        - Minimal schema for backward compatibility check
        - Full schema for metadata extraction

        We store the raw JSON data once at this boundary to avoid calling response.json()
        twice, which would be more expensive than validating twice.
        """
        # Store raw response at boundary to avoid double JSON parsing
        # This is a boundary where external API data enters the system
        raw_data = response.json()

        # Parse full response schema for metadata extraction and version finding
        full_response = PyPIFullResponseSchema.model_validate(raw_data)
        metadata = _extract_pypi_metadata(full_response)

        # Find latest compatible version
        latest = _find_latest_compatible_version(full_response, python_version)

        if latest:
            return VersionResult(latest_version=latest, pypi_metadata=metadata)
        return VersionResult(is_unknown=True, error="No compatible version found", pypi_metadata=metadata)

    async def resolve_github_async(
        self,
        owner: str,
        repo: str,
    ) -> VersionResult:
        """Resolve the latest version from GitHub releases or tags.

        Args:
            owner: GitHub repository owner.
            repo: GitHub repository name.

        Returns:
            Result containing the latest version or error.
        """
        cache_key = f"github:{owner}/{repo}"
        if cache_key in self.cache:
            return self.cache[cache_key]

        # Check if another task is already fetching this repo
        if cache_key in self._pending:
            return await self._pending[cache_key]

        # Create a future for this fetch to prevent duplicate requests
        loop = asyncio.get_running_loop()
        future: asyncio.Future[VersionResult] = loop.create_future()
        self._pending[cache_key] = future

        try:
            result = await self._fetch_github_version(owner, repo)
            self.cache[cache_key] = result
            future.set_result(result)
            return result
        except Exception as exc:
            future.set_exception(exc)
            raise
        finally:
            self._pending.pop(cache_key, None)

    async def _fetch_github_version(self, owner: str, repo: str) -> VersionResult:
        """Fetch version from GitHub API (releases then tags)."""
        try:
            return await self._query_github_api(owner, repo)
        except httpx.TimeoutException:
            return VersionResult(is_unknown=True, error=f"Timeout querying GitHub for {owner}/{repo}")
        except httpx.HTTPError as e:
            return VersionResult(is_unknown=True, error=f"HTTP error querying GitHub: {e}")
        except Exception as e:
            return VersionResult(is_unknown=True, error=f"Error querying GitHub: {e}")

    async def _query_github_api(self, owner: str, repo: str) -> VersionResult:
        """Query GitHub API for releases then tags."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            version = await self._try_github_releases(client, owner, repo)
            if version:
                return VersionResult(latest_version=version)

            version = await self._try_github_tags(client, owner, repo)
            if version:
                return VersionResult(latest_version=version)

            return VersionResult(
                latest_version=None,
                is_unknown=True,
                error="No releases or version tags found",
            )

    async def _try_github_releases(
        self,
        client: httpx.AsyncClient,
        owner: str,
        repo: str,
    ) -> str | None:
        """Try to get version from GitHub releases."""
        releases_url = GITHUB_API_RELEASES.format(owner=owner, repo=repo)
        response = await client.get(releases_url, headers=self._get_headers(for_github=True))

        if response.status_code != 200:
            return None

        releases_adapter = TypeAdapter(list[GitHubReleaseSchema])
        releases = releases_adapter.validate_python(response.json())
        return _find_version_from_releases(releases)

    async def _try_github_tags(
        self,
        client: httpx.AsyncClient,
        owner: str,
        repo: str,
    ) -> str | None:
        """Try to get version from GitHub tags."""
        tags_url = GITHUB_API_TAGS.format(owner=owner, repo=repo)
        response = await client.get(tags_url, headers=self._get_headers(for_github=True))

        if response.status_code != 200:
            return None

        tags_adapter = TypeAdapter(list[GitHubTagSchema])
        tags = tags_adapter.validate_python(response.json())
        return _find_version_from_tags(tags)

    async def resolve_async(
        self,
        dep: DependencyInfo,
        python_version: PythonVersion | None = None,
    ) -> VersionResult:
        """Resolve the latest version for a dependency.

        Dispatches to PyPI or GitHub resolver based on dependency type.

        Args:
            dep: The dependency to resolve.
            python_version: Optional Python version context.

        Returns:
            Result containing the latest version or error.
        """
        if dep.is_git_dependency and dep.git_url:
            owner, repo = _parse_github_url(dep.git_url)
            if owner is not None and repo is not None:
                return await self.resolve_github_async(owner, repo)
            return VersionResult(
                latest_version=None,
                is_unknown=True,
                error="Could not parse GitHub URL",
            )
        return await self.resolve_pypi_async(dep.name, python_version)

    def resolve_sync(
        self,
        dep: DependencyInfo,
        python_version: PythonVersion | None = None,
    ) -> VersionResult:
        """Synchronous version of resolve_async.

        Args:
            dep: The dependency to resolve.
            python_version: Optional Python version context.

        Returns:
            Result containing the latest version or error.
        """
        return asyncio.run(self.resolve_async(dep, python_version))

    async def resolve_many_async(
        self,
        deps: list[DependencyInfo],
        python_version: PythonVersion | None = None,
        concurrency: int = 10,
    ) -> dict[str, VersionResult]:
        """Resolve versions for multiple dependencies concurrently.

        Args:
            deps: List of dependencies to resolve.
            python_version: Optional Python version context.
            concurrency: Maximum number of concurrent requests.

        Returns:
            Map of package names to version results.
        """
        semaphore = asyncio.Semaphore(concurrency)

        async def resolve_with_limit(dep: DependencyInfo) -> tuple[str, VersionResult]:
            """Resolve a single dependency while respecting the concurrency limit.

            Args:
                dep: The dependency to resolve.

            Returns:
                Tuple of (package_name, version_result).
            """
            async with semaphore:
                result = await self.resolve_async(dep, python_version)
                return dep.name, result

        tasks = [resolve_with_limit(dep) for dep in deps]
        results = await asyncio.gather(*tasks)
        return dict(results)


@lru_cache(maxsize=512)
def _extract_version_from_tag(tag: str) -> str | None:
    """Extract a version number from a git tag.

    Handles formats like:
    - "v1.2.3"
    - "1.2.3"
    - "release-1.2.3"
    - "version-1.2"

    Args:
        tag: The git tag string.

    Returns:
        Extracted version or None if not a version tag.
    """
    if not tag:
        return None

    # Try to extract version pattern
    for pattern in (_RE_VERSION_SIMPLE, _RE_VERSION_PREFIXED):
        match = pattern.match(tag)
        if match:
            return match.group(1)

    return None


def _find_version_from_releases(releases: list[GitHubReleaseSchema]) -> str | None:
    """Find the latest version from GitHub releases.

    Prefers non-prerelease, non-draft releases.

    Args:
        releases: List of GitHub releases.

    Returns:
        The latest version found, or None.
    """
    # Find latest non-prerelease if available
    for release in releases:
        if not release.prerelease and not release.draft:
            version = _extract_version_from_tag(release.tag_name)
            if version:
                return version

    # Fall back to any release
    if releases:
        return _extract_version_from_tag(releases[0].tag_name)

    return None


def _find_version_from_tags(tags: list[GitHubTagSchema]) -> str | None:
    """Find the latest version from GitHub tags.

    Args:
        tags: List of GitHub tags.

    Returns:
        The latest version found, or None.
    """
    version_tags: list[str] = []
    for tag in tags:
        version = _extract_version_from_tag(tag.name)
        if version:
            version_tags.append(version)

    if version_tags:
        version_tags.sort(key=_version_sort_key, reverse=True)
        return version_tags[0]

    return None


@lru_cache(maxsize=512)
def _version_sort_key(version: str) -> tuple[int, ...]:
    """Create a sortable key from a version string.

    Args:
        version: Version string like "1.2.3".

    Returns:
        Tuple of integers for sorting.
    """
    # Extract numeric parts
    parts = _RE_NUMERIC_PARTS.findall(version)
    return tuple(int(p) for p in parts) if parts else (0,)


@lru_cache(maxsize=256)
def _parse_github_url(url: str) -> tuple[str | None, str | None]:
    """Parse GitHub owner and repo from a git URL.

    Args:
        url: Git URL like "git+https://github.com/owner/repo.git".

    Returns:
        Tuple of (owner, repo) or (None, None) if not parseable.
    """
    # Remove git+ prefix
    cleaned = _RE_GIT_PREFIX.sub("", url)
    # Remove .git suffix (can be before @ref or at end)
    cleaned = _RE_GIT_SUFFIX.sub("", cleaned)

    # Parse GitHub URL
    match = _RE_GITHUB_URL.search(cleaned)
    if match:
        return match.group(1), match.group(2)

    return None, None


def _find_latest_compatible_version(
    response: PyPIFullResponseSchema,
    python_version: PythonVersion | None = None,
) -> str | None:
    """Find the latest version compatible with a Python version.

    Args:
        response: Full PyPI API response with releases.
        python_version: Target Python version. If None, returns the absolute latest.

    Returns:
        Latest compatible version string, or None if none found.
    """
    # If no Python version specified, return the latest from info
    if python_version is None:
        return response.info.version or None

    # Check if the absolute latest version is compatible
    latest_version = response.info.version
    latest_requires_python = response.info.requires_python

    if latest_version and _is_python_compatible(latest_requires_python, python_version):
        return latest_version

    # Sort versions in descending order and find first compatible one
    versions = list(response.releases.keys())
    versions.sort(key=_version_sort_key, reverse=True)

    for version in versions:
        files = response.releases.get(version, [])
        if not files:
            continue

        # Get requires_python from first file (all files in a release have same requires_python)
        requires_python = files[0].requires_python if files else None

        if _is_python_compatible(requires_python, python_version):
            return version

    return None


def _is_python_compatible(requires_python: str | None, python_version: PythonVersion) -> bool:
    """Check if a requires_python specifier is compatible with a Python version.

    Args:
        requires_python: The requires-python specifier (e.g., ">=3.8", ">=3.9,<3.12").
        python_version: The Python version to check.

    Returns:
        True if compatible (or if requires_python is not specified).
    """
    if not requires_python:
        # No constraint means compatible with all versions
        return True

    compatible_versions = parse_requires_python(requires_python)
    return python_version in compatible_versions


def _extract_pypi_metadata(parsed_response: PyPIFullResponseSchema) -> PyPIMetadata:
    """Extract enriched metadata from PyPI API response.

    Args:
        parsed_response: Validated PyPI full response schema.

    Returns:
        Populated PyPIMetadata instance.
    """
    try:
        info = parsed_response.info

        # Extract version list
        available_versions = list(parsed_response.releases.keys())

        # Find first and latest release dates
        first_date, latest_date = _extract_release_dates(parsed_response)

        # Extract all release dates and compute metrics
        all_release_dates = _extract_all_release_dates(parsed_response)
        version_metrics = _compute_version_metrics(all_release_dates)

        return PyPIMetadata(
            summary=info.summary,
            license=info.license,
            home_page=info.home_page,
            project_urls=info.project_urls or {},
            author=info.author,
            author_email=info.author_email,
            maintainer=info.maintainer,
            maintainer_email=info.maintainer_email,
            available_versions=available_versions,
            first_release_date=first_date,
            latest_release_date=latest_date,
            requires_python=info.requires_python,
            requires_dist=info.requires_dist or [],
            version_metrics=version_metrics,
        )
    except Exception as e:
        logger.debug("Failed to extract PyPI metadata: %s", e)
        return PyPIMetadata()


def _extract_release_dates(
    response: PyPIFullResponseSchema,
) -> tuple[str | None, str | None]:
    """Extract first and latest release dates from PyPI response.

    Args:
        response: Full PyPI API response schema.

    Returns:
        Tuple of (first_release_date, latest_release_date).
    """
    dates: list[str] = []
    for files in response.releases.values():
        for f in files:
            if f.upload_time_iso_8601:
                dates.append(f.upload_time_iso_8601)

    if not dates:
        return None, None

    dates.sort()
    return dates[0], dates[-1]


def _extract_all_release_dates(response: PyPIFullResponseSchema) -> list[str]:
    """Extract all unique release dates from PyPI response.

    Returns one date per release version (the earliest upload for that version).

    Args:
        response: Full PyPI API response schema.

    Returns:
        List of ISO timestamps sorted oldest first.
    """
    version_dates: dict[str, str] = {}
    for version, files in response.releases.items():
        # Get earliest upload date for this version
        dates_for_version = [f.upload_time_iso_8601 for f in files if f.upload_time_iso_8601]
        if dates_for_version:
            dates_for_version.sort()
            version_dates[version] = dates_for_version[0]

    # Sort by date and return
    sorted_dates = sorted(version_dates.values())
    return sorted_dates


def _compute_version_metrics(release_dates: list[str]) -> VersionMetrics:
    """Compute version metrics from release dates.

    Args:
        release_dates: List of ISO timestamps sorted oldest first.

    Returns:
        Computed VersionMetrics.
    """
    from datetime import datetime, timezone

    if not release_dates:
        return VersionMetrics(release_count=0, release_dates=[])

    now = datetime.now(timezone.utc)
    release_count = len(release_dates)

    # Parse dates
    parsed_dates: list[datetime] = []
    for date_str in release_dates:
        try:
            # Handle ISO format with optional timezone
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            parsed_dates.append(dt)
        except (ValueError, TypeError):
            continue

    if not parsed_dates:
        return VersionMetrics(release_count=release_count, release_dates=release_dates)

    # Calculate ages
    latest_date = parsed_dates[-1]
    first_date = parsed_dates[0]
    latest_release_age_days = (now - latest_date).days
    first_release_age_days = (now - first_date).days

    # Calculate gaps between releases
    gaps_days: list[int] = []
    for i in range(1, len(parsed_dates)):
        gap = (parsed_dates[i] - parsed_dates[i - 1]).days
        gaps_days.append(gap)

    avg_days: float | None = None
    min_days: int | None = None
    max_days: int | None = None
    if gaps_days:
        avg_days = round(sum(gaps_days) / len(gaps_days), 1)
        min_days = min(gaps_days)
        max_days = max(gaps_days)

    # Count releases in last year
    one_year_ago = now.replace(year=now.year - 1)
    releases_last_year = sum(1 for dt in parsed_dates if dt >= one_year_ago)

    return VersionMetrics(
        release_count=release_count,
        latest_release_age_days=latest_release_age_days,
        first_release_age_days=first_release_age_days,
        avg_days_between_releases=avg_days,
        min_days_between_releases=min_days,
        max_days_between_releases=max_days,
        releases_last_year=releases_last_year,
        release_dates=release_dates,
    )


@lru_cache(maxsize=1000)
def resolve_pypi_version_cached(package_name: str) -> VersionResult:
    """Cached synchronous PyPI version lookup.

    Args:
        package_name: The normalized package name.

    Returns:
        Result containing the latest version or error.
    """
    resolver = VersionResolver()
    return asyncio.run(resolver.resolve_pypi_async(package_name))


__all__ = [
    "VersionResolver",
    "VersionResult",
    "resolve_pypi_version_cached",
]
