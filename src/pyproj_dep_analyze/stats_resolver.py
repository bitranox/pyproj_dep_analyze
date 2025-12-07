"""Download statistics resolver for PyPI packages.

Purpose
-------
Fetch download statistics from pypistats.org API to provide insight into
package popularity and adoption.

Contents
--------
* :func:`fetch_download_stats` - Get download stats for a package
* :class:`StatsResolver` - Async resolver with caching

System Role
-----------
Handles external API calls to pypistats.org for download metrics.
Uses caching to minimize API requests and respects rate limits.

Note
----
pypistats.org data comes from PyPI BigQuery dataset and has a 1-2 day delay.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

import httpx
from pydantic import BaseModel, ConfigDict

from .models import DownloadStats

logger = logging.getLogger(__name__)

# pypistats.org API endpoints
PYPISTATS_RECENT_URL = "https://pypistats.org/api/packages/{package}/recent"

# Default timeout for API requests
DEFAULT_TIMEOUT = 15.0


class PyPIStatsRecentSchema(BaseModel):
    """Schema for pypistats.org recent downloads response."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    # The data field contains download counts
    data: dict[str, int] = {}
    package: str = ""
    type: str = ""


def _empty_stats_cache() -> dict[str, DownloadStats]:
    """Return an empty cache dict for dataclass defaults."""
    return {}


@dataclass
class StatsResolver:
    """Async download statistics resolver with caching.

    Attributes:
        timeout: Request timeout in seconds.
        cache: In-memory cache of resolved stats.
    """

    timeout: float = DEFAULT_TIMEOUT
    cache: dict[str, DownloadStats] = field(default_factory=_empty_stats_cache)
    _pending: dict[str, asyncio.Future[DownloadStats | None]] = field(default_factory=lambda: {}, repr=False)

    async def fetch_stats_async(self, package_name: str) -> DownloadStats | None:
        """Fetch download statistics for a package from pypistats.org.

        Args:
            package_name: The normalized package name.

        Returns:
            DownloadStats if successful, None if failed.
        """
        cache_key = f"stats:{package_name}"
        if cache_key in self.cache:
            return self.cache[cache_key]

        # Check if another task is already fetching this package
        if cache_key in self._pending:
            return await self._pending[cache_key]

        # Create a future for this fetch to prevent duplicate requests
        loop = asyncio.get_running_loop()
        future: asyncio.Future[DownloadStats | None] = loop.create_future()
        self._pending[cache_key] = future

        try:
            result = await self._fetch_from_pypistats(package_name)
            if result:
                self.cache[cache_key] = result
            future.set_result(result)
            return result
        except Exception as exc:
            future.set_exception(exc)
            raise
        finally:
            self._pending.pop(cache_key, None)

    async def _fetch_from_pypistats(self, package_name: str) -> DownloadStats | None:
        """Fetch stats from pypistats.org API."""
        url = PYPISTATS_RECENT_URL.format(package=package_name)
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url, headers={"Accept": "application/json", "User-Agent": "pyproj-dep-analyze/1.0"})

            if response.status_code == 404:
                logger.debug("Package %s not found on pypistats.org", package_name)
                return None

            if response.status_code != 200:
                logger.debug("pypistats.org returned %d for %s", response.status_code, package_name)
                return None

            return self._parse_pypistats_response(response)
        except httpx.TimeoutException:
            logger.debug("Timeout fetching stats for %s", package_name)
            return None
        except httpx.HTTPError as e:
            logger.debug("HTTP error fetching stats for %s: %s", package_name, e)
            return None
        except Exception as e:
            logger.debug("Error fetching stats for %s: %s", package_name, e)
            return None

    def _parse_pypistats_response(self, response: httpx.Response) -> DownloadStats | None:
        """Parse pypistats.org API response into DownloadStats."""
        try:
            data = response.json()
            parsed = PyPIStatsRecentSchema.model_validate(data)

            # pypistats.org returns data like:
            # {"data": {"last_day": 1234, "last_week": 5678, "last_month": 12345}, ...}
            stats_data = parsed.data

            return DownloadStats(
                last_day_downloads=stats_data.get("last_day"),
                last_week_downloads=stats_data.get("last_week"),
                last_month_downloads=stats_data.get("last_month"),
                fetched_at=datetime.now(timezone.utc).isoformat(),
            )
        except Exception as e:
            logger.debug("Failed to parse pypistats response: %s", e)
            return None

    async def fetch_many_async(
        self,
        package_names: list[str],
        concurrency: int = 5,
    ) -> dict[str, DownloadStats | None]:
        """Fetch download stats for multiple packages concurrently.

        Args:
            package_names: List of package names.
            concurrency: Maximum number of concurrent requests.

        Returns:
            Map of package names to download stats (or None if fetch failed).
        """
        semaphore = asyncio.Semaphore(concurrency)

        async def fetch_with_limit(name: str) -> tuple[str, DownloadStats | None]:
            async with semaphore:
                result = await self.fetch_stats_async(name)
                return name, result

        tasks = [fetch_with_limit(name) for name in package_names]
        results = await asyncio.gather(*tasks)
        return dict(results)


__all__ = [
    "DownloadStats",
    "StatsResolver",
]
