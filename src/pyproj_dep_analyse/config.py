"""Configuration management using lib_layered_config.

Purpose
-------
Provides a centralized configuration loader that merges defaults, application
configs, host configs, user configs, .env files, and environment variables
following a deterministic precedence order.

Contents
--------
* :func:`get_config` – loads configuration with lib_layered_config
* :func:`get_default_config_path` – returns path to bundled default config
* :func:`get_analyzer_settings` – returns analyzer-specific settings

Configuration identifiers (vendor, app, slug) are imported from
:mod:`pyproj_dep_analyse.__init__conf__` as LAYEREDCONF_* constants.

System Role
-----------
Acts as the configuration adapter layer, bridging lib_layered_config with the
application's runtime needs while keeping domain logic decoupled from
configuration mechanics.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from lib_layered_config import Config, read_config

from . import __init__conf__

# Environment variable prefix for native (short) env vars
_ENV_PREFIX = "PYPROJ_DEP_ANALYSE_"


def get_default_config_path() -> Path:
    """Return the path to the bundled default configuration file.

    The default configuration ships with the package and needs to be
    locatable at runtime regardless of how the package is installed.
    Uses ``__file__`` to locate the defaultconfig.toml file relative to
    this module.

    Returns:
        Absolute path to defaultconfig.toml.

    Example:
        >>> path = get_default_config_path()
        >>> path.name
        'defaultconfig.toml'
        >>> path.exists()
        True
    """
    return Path(__file__).parent / "defaultconfig.toml"


# Cache configuration to avoid redundant file I/O and parsing.
# Trade-offs:
#   ✅ Future-proof if config is read from multiple places
#   ✅ Near-zero overhead (single cache entry)
#   ❌ Prevents dynamic config reloading (if ever needed)
#   ❌ start_dir parameter variations would bypass cache
@lru_cache(maxsize=1)
def get_config(*, start_dir: str | None = None) -> Config:
    """Load layered configuration with application defaults.

    Centralizes configuration loading so all entry points use the same
    precedence rules and default values without duplicating the discovery
    logic. Uses lru_cache to avoid redundant file reads when called from
    multiple modules.

    Loads configuration from multiple sources in precedence order:
    defaults → app → host → user → dotenv → env

    The vendor, app, and slug identifiers determine platform-specific paths:
    - Linux: Uses XDG directories with slug
    - macOS: Uses Library/Application Support with vendor/app
    - Windows: Uses ProgramData/AppData with vendor/app

    Args:
        start_dir: Optional directory that seeds .env discovery. Defaults to
            current working directory when None.

    Returns:
        Immutable configuration object with provenance tracking.

    Note:
        This function is cached (maxsize=1). The first call loads and parses
        all configuration files; subsequent calls with the same start_dir
        return the cached Config instance immediately.

    Example:
        >>> config = get_config()
        >>> isinstance(config.as_dict(), dict)
        True
        >>> config.get("nonexistent", default="fallback")
        'fallback'
    """
    return read_config(
        vendor=__init__conf__.LAYEREDCONF_VENDOR,
        app=__init__conf__.LAYEREDCONF_APP,
        slug=__init__conf__.LAYEREDCONF_SLUG,
        default_file=get_default_config_path(),
        start_dir=start_dir,
    )


@dataclass(frozen=True, slots=True)
class AnalyzerSettings:
    """Immutable settings for the dependency analyzer.

    Attributes:
        github_token: GitHub API token for authentication (empty = unauthenticated).
        timeout: Maximum seconds to wait for API responses.
        concurrency: Maximum number of simultaneous API requests.
    """

    github_token: str
    timeout: float
    concurrency: int


def get_analyzer_settings() -> AnalyzerSettings:
    """Get analyzer settings from configuration with environment variable overrides.

    Settings are resolved in the following precedence order (highest wins):
    1. Native environment variables (PYPROJ_DEP_ANALYSE_GITHUB_TOKEN, etc.)
    2. lib_layered_config environment variables (PYPROJ_DEP_ANALYSE___ANALYZER__*, etc.)
    3. User config file (~/.config/pyproj-dep-analyse/config.toml)
    4. Host config file
    5. Application config file
    6. Default config (bundled defaultconfig.toml)

    Returns:
        AnalyzerSettings with resolved values.

    Example:
        >>> settings = get_analyzer_settings()
        >>> settings.timeout
        30.0
        >>> settings.concurrency
        10
    """
    config = get_config()

    # Get values from config (includes lib_layered_config env var overrides)
    analyzer_section = config.get("analyzer", default={})

    # Default values
    github_token = analyzer_section.get("github_token", "")
    timeout = analyzer_section.get("timeout", 30.0)
    concurrency = analyzer_section.get("concurrency", 10)

    # Native environment variables have highest precedence
    if env_token := os.environ.get(f"{_ENV_PREFIX}GITHUB_TOKEN"):
        github_token = env_token

    if env_timeout := os.environ.get(f"{_ENV_PREFIX}TIMEOUT"):
        try:
            timeout = float(env_timeout)
        except ValueError:
            pass  # Keep config value if env var is invalid

    if env_concurrency := os.environ.get(f"{_ENV_PREFIX}CONCURRENCY"):
        try:
            concurrency = int(env_concurrency)
        except ValueError:
            pass  # Keep config value if env var is invalid

    # Treat empty string as None for github_token
    resolved_token = github_token if github_token else ""

    return AnalyzerSettings(
        github_token=resolved_token,
        timeout=float(timeout),
        concurrency=int(concurrency),
    )


__all__ = [
    "AnalyzerSettings",
    "get_analyzer_settings",
    "get_config",
    "get_default_config_path",
]
