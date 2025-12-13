"""Package index detection and resolution.

Purpose
-------
Detect configured package indexes from environment variables, pip configuration,
and pyproject.toml, then track which index each package was resolved from.

Contents
--------
* :func:`detect_configured_indexes` - Find all configured package indexes
* :func:`identify_index` - Identify index type from URL
* :class:`IndexResolver` - Resolver that queries multiple indexes

System Role
-----------
Provides package index tracking for the enriched analysis output. Detects
which PyPI-compatible index serves each package.
"""

from __future__ import annotations

import asyncio
import configparser
import logging
import os
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

import httpx

from .models import IndexInfo, IndexType, KNOWN_INDEX_PATTERNS, PackageIndexResolutions
from .schemas import PyprojectSchema, UVConfigSchema

logger = logging.getLogger(__name__)


class PipConfigKey(str, Enum):
    """Pip configuration file keys and sections.

    These enums represent the standard pip configuration options
    used for specifying package indexes.
    """

    GLOBAL_SECTION = "global"
    INDEX_URL = "index-url"
    EXTRA_INDEX_URL = "extra-index-url"


class PipEnvVar(str, Enum):
    """Pip environment variable names.

    These enums represent the standard pip environment variables
    used for specifying package indexes.
    """

    INDEX_URL = "PIP_INDEX_URL"
    EXTRA_INDEX_URL = "PIP_EXTRA_INDEX_URL"


# Default PyPI index URL constants (templates, not identifiers)
DEFAULT_PYPI_INDEX = "https://pypi.org/simple"
DEFAULT_PYPI_JSON_API = "https://pypi.org/pypi/{package}/json"

# Regex patterns for index URL normalization
_RE_TRAILING_SLASH = re.compile(r"/+$")
_RE_SIMPLE_SUFFIX = re.compile(r"/simple/?$")


def identify_index(url: str) -> IndexInfo:
    """Identify index type from URL.

    Args:
        url: The index URL.

    Returns:
        IndexInfo with detected index type and privacy status.
    """
    url_lower = url.lower()

    for mapping in KNOWN_INDEX_PATTERNS:
        if mapping.pattern in url_lower:
            return IndexInfo(url=url, index_type=mapping.index_type, is_private=mapping.is_private)

    # Unknown index - assume private
    return IndexInfo(url=url, index_type=IndexType.CUSTOM, is_private=True)


def _get_pip_config_paths() -> list[Path]:
    """Get platform-specific pip configuration file paths."""
    paths: list[Path] = []

    # User pip config
    if os.name == "nt":
        appdata = os.environ.get("APPDATA", "")
        if appdata:
            paths.append(Path(appdata) / "pip" / "pip.ini")
    else:
        paths.append(Path.home() / ".pip" / "pip.conf")
        paths.append(Path.home() / ".config" / "pip" / "pip.conf")

    # Global pip config
    if os.name != "nt":
        paths.append(Path("/etc/pip.conf"))

    # Virtual environment pip config
    venv = os.environ.get("VIRTUAL_ENV")
    if venv:
        paths.append(Path(venv) / "pip.conf")

    return paths


def _parse_pip_config(config_path: Path) -> list[str]:
    """Parse index URLs from a pip config file."""
    indexes: list[str] = []

    if not config_path.exists():
        return indexes

    try:
        config = configparser.ConfigParser()
        config.read(config_path)

        if config.has_option(PipConfigKey.GLOBAL_SECTION.value, PipConfigKey.INDEX_URL.value):
            indexes.append(config.get(PipConfigKey.GLOBAL_SECTION.value, PipConfigKey.INDEX_URL.value))

        if config.has_option(PipConfigKey.GLOBAL_SECTION.value, PipConfigKey.EXTRA_INDEX_URL.value):
            extra = config.get(PipConfigKey.GLOBAL_SECTION.value, PipConfigKey.EXTRA_INDEX_URL.value)
            # Can be newline-separated
            indexes.extend(line.strip() for line in extra.splitlines() if line.strip())

    except Exception as e:
        logger.debug("Error parsing pip config %s: %s", config_path, e)

    return indexes


def _get_env_indexes() -> list[str]:
    """Get index URLs from environment variables."""
    indexes: list[str] = []

    pip_index = os.environ.get(PipEnvVar.INDEX_URL.value)
    if pip_index:
        indexes.append(pip_index)

    pip_extra = os.environ.get(PipEnvVar.EXTRA_INDEX_URL.value)
    if pip_extra:
        # Can be space-separated
        indexes.extend(url.strip() for url in pip_extra.split() if url.strip())

    return indexes


def _get_poetry_sources_from_schema(pyproject_data: PyprojectSchema) -> list[str]:
    """Extract index URLs from Poetry source configuration.

    Args:
        pyproject_data: Validated pyproject schema.

    Returns:
        List of source URLs from Poetry config.
    """
    return [source.url for source in pyproject_data.tool.poetry.source if source.url]


def _get_pdm_sources_from_schema(pyproject_data: PyprojectSchema) -> list[str]:
    """Extract index URLs from PDM source configuration.

    Args:
        pyproject_data: Validated pyproject schema.

    Returns:
        List of source URLs from PDM config.
    """
    return [source.url for source in pyproject_data.tool.pdm.source if source.url]


def _get_uv_indexes(project_dir: Path) -> list[str]:
    """Extract index URLs from uv.toml configuration."""
    indexes: list[str] = []

    uv_toml = project_dir / "uv.toml"
    if not uv_toml.exists():
        return indexes

    try:
        import rtoml

        data = rtoml.load(uv_toml)

        config = UVConfigSchema.model_validate(data)

        if config.index_url:
            indexes.append(config.index_url)

        indexes.extend(config.extra_index_url)

    except Exception as e:
        logger.debug("Error parsing uv.toml: %s", e)

    return indexes


def detect_configured_indexes(
    pyproject_data: PyprojectSchema | None = None,
    project_dir: Path | None = None,
) -> list[IndexInfo]:
    """Detect all configured package indexes.

    Checks in order (later sources override earlier):
    1. Default PyPI
    2. pip config files
    3. Environment variables
    4. pyproject.toml (Poetry/PDM sources)
    5. uv.toml

    Args:
        pyproject_data: Validated pyproject schema.
        project_dir: Project directory for config file discovery.

    Returns:
        List of IndexInfo objects for all detected indexes.
    """
    seen_urls: set[str] = set()
    indexes: list[IndexInfo] = []

    def add_index(url: str) -> None:
        """Add index if not already seen."""
        normalized = _RE_TRAILING_SLASH.sub("", url)
        if normalized not in seen_urls:
            seen_urls.add(normalized)
            indexes.append(identify_index(normalized))

    # 1. Default PyPI (always available as fallback)
    add_index(DEFAULT_PYPI_INDEX)

    # 2. pip config files
    for config_path in _get_pip_config_paths():
        for url in _parse_pip_config(config_path):
            add_index(url)

    # 3. Environment variables
    for url in _get_env_indexes():
        add_index(url)

    # 4. pyproject.toml sources
    if pyproject_data:
        for url in _get_poetry_sources_from_schema(pyproject_data):
            add_index(url)
        for url in _get_pdm_sources_from_schema(pyproject_data):
            add_index(url)

    # 5. uv.toml
    if project_dir:
        for url in _get_uv_indexes(project_dir):
            add_index(url)

    return indexes


def _empty_index_cache() -> dict[str, IndexInfo]:
    """Return empty cache dict for dataclass default."""
    return {}


def _empty_index_list() -> list[IndexInfo]:
    """Return empty index list for dataclass default."""
    return []


@dataclass
class IndexResolver:
    """Resolver that tracks which index each package comes from.

    Attributes:
        indexes: List of configured indexes to check.
        timeout: Request timeout in seconds.
        cache: Cache mapping package names (dynamic strings) to their source index.
               This dict usage is acceptable because:
               - Keys are package names (user-provided, not fixed identifiers)
               - Values are typed IndexInfo models
               - Pattern follows typed cache accessor pattern
    """

    indexes: list[IndexInfo] = field(default_factory=_empty_index_list)
    timeout: float = 30.0
    cache: dict[str, IndexInfo] = field(default_factory=_empty_index_cache)

    def __post_init__(self) -> None:
        """Ensure at least PyPI is configured."""
        if not self.indexes:
            self.indexes = [IndexInfo(url=DEFAULT_PYPI_INDEX, index_type=IndexType.PYPI, is_private=False)]

    def _get_json_api_url(self, index: IndexInfo, package: str) -> str:
        """Convert simple index URL to JSON API URL."""
        base_url = _RE_SIMPLE_SUFFIX.sub("", index.url)

        # PyPI-specific JSON API
        if "pypi.org" in index.url:
            return f"https://pypi.org/pypi/{package}/json"

        # Generic: try /pypi/{package}/json pattern
        return f"{base_url}/pypi/{package}/json"

    async def resolve_package_index_async(self, package: str) -> IndexInfo | None:
        """Determine which index a package comes from.

        Queries each configured index in order until the package is found.

        Args:
            package: The package name to look up.

        Returns:
            IndexInfo for the index that has the package, or None if not found.
        """
        if package in self.cache:
            return self.cache[package]

        for index in self.indexes:
            if await self._package_exists_on_index(package, index):
                self.cache[package] = index
                return index

        return None

    async def _package_exists_on_index(self, package: str, index: IndexInfo) -> bool:
        """Check if a package exists on the given index."""
        url = self._get_json_api_url(index, package)

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.head(url)
                return response.status_code == 200
        except Exception:
            return False

    async def resolve_many_async(
        self,
        packages: list[str],
        concurrency: int = 10,
    ) -> PackageIndexResolutions:
        """Resolve index sources for multiple packages.

        Args:
            packages: List of package names.
            concurrency: Maximum concurrent requests.

        Returns:
            PackageIndexResolutions containing dict mapping package names to their source IndexInfo.
        """
        semaphore = asyncio.Semaphore(concurrency)

        async def resolve_one(pkg: str) -> tuple[str, IndexInfo | None]:
            async with semaphore:
                return pkg, await self.resolve_package_index_async(pkg)

        tasks = [resolve_one(pkg) for pkg in packages]
        results = await asyncio.gather(*tasks)
        return PackageIndexResolutions(packages=dict(results))


__all__ = [
    "IndexResolver",
    "detect_configured_indexes",
    "identify_index",
]
