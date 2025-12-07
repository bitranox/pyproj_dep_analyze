"""Configuration module stories: layered config speaks truth.

The config module provides centralized configuration loading with layered
sources. These tests verify the configuration loading, default paths, and
analyzer settings resolution.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from pyproj_dep_analyze import config as config_mod
from pyproj_dep_analyze.config import (
    AnalyzerSettings,
    get_analyzer_settings,
    get_config,
    get_default_config_path,
)


# ════════════════════════════════════════════════════════════════════════════
# get_default_config_path: The bundled config locator
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.os_agnostic
def test_get_default_config_path_returns_path_object() -> None:
    result = get_default_config_path()

    assert isinstance(result, Path)


@pytest.mark.os_agnostic
def test_get_default_config_path_points_to_defaultconfig_toml() -> None:
    result = get_default_config_path()

    assert result.name == "defaultconfig.toml"


@pytest.mark.os_agnostic
def test_get_default_config_path_file_exists() -> None:
    result = get_default_config_path()

    assert result.exists()


@pytest.mark.os_agnostic
def test_get_default_config_path_file_is_readable() -> None:
    result = get_default_config_path()

    content = result.read_text(encoding="utf-8")

    assert len(content) > 0


@pytest.mark.os_agnostic
def test_get_default_config_path_is_absolute() -> None:
    result = get_default_config_path()

    assert result.is_absolute()


# ════════════════════════════════════════════════════════════════════════════
# get_config: The layered configuration loader
# ════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def clear_config_cache() -> None:
    """Clear the LRU cache before each test."""
    get_config.cache_clear()


@pytest.mark.os_agnostic
def test_get_config_returns_config_instance(clear_config_cache: None) -> None:
    from lib_layered_config import Config

    result = get_config()

    assert isinstance(result, Config)


@pytest.mark.os_agnostic
def test_get_config_as_dict_returns_dictionary(clear_config_cache: None) -> None:
    config = get_config()

    result = config.as_dict()

    assert isinstance(result, dict)


@pytest.mark.os_agnostic
def test_get_config_get_returns_default_for_missing_key(clear_config_cache: None) -> None:
    config = get_config()

    result = config.get("nonexistent_key_xyz", default="fallback")

    assert result == "fallback"


@pytest.mark.os_agnostic
def test_get_config_is_cached(clear_config_cache: None) -> None:
    config1 = get_config()
    config2 = get_config()

    assert config1 is config2


@pytest.mark.os_agnostic
def test_get_config_cache_info_shows_hit_after_second_call(clear_config_cache: None) -> None:
    get_config()
    get_config()

    cache_info = get_config.cache_info()

    assert cache_info.hits >= 1


# ════════════════════════════════════════════════════════════════════════════
# AnalyzerSettings: The immutable settings container
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.os_agnostic
def test_analyzer_settings_stores_github_token() -> None:
    settings = AnalyzerSettings(
        github_token="test-token",
        timeout=30.0,
        concurrency=10,
    )

    assert settings.github_token == "test-token"


@pytest.mark.os_agnostic
def test_analyzer_settings_stores_timeout() -> None:
    settings = AnalyzerSettings(
        github_token="",
        timeout=45.0,
        concurrency=10,
    )

    assert settings.timeout == 45.0


@pytest.mark.os_agnostic
def test_analyzer_settings_stores_concurrency() -> None:
    settings = AnalyzerSettings(
        github_token="",
        timeout=30.0,
        concurrency=20,
    )

    assert settings.concurrency == 20


@pytest.mark.os_agnostic
def test_analyzer_settings_is_frozen() -> None:
    settings = AnalyzerSettings(
        github_token="",
        timeout=30.0,
        concurrency=10,
    )

    # Pydantic frozen models raise ValidationError, not AttributeError
    with pytest.raises(ValidationError):
        settings.github_token = "new"  # type: ignore[misc]


@pytest.mark.os_agnostic
def test_analyzer_settings_is_hashable() -> None:
    settings = AnalyzerSettings(
        github_token="",
        timeout=30.0,
        concurrency=10,
    )

    assert hash(settings) is not None


@pytest.mark.os_agnostic
def test_analyzer_settings_equality() -> None:
    settings1 = AnalyzerSettings(github_token="", timeout=30.0, concurrency=10)
    settings2 = AnalyzerSettings(github_token="", timeout=30.0, concurrency=10)

    assert settings1 == settings2


# ════════════════════════════════════════════════════════════════════════════
# get_analyzer_settings: The settings resolver
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.os_agnostic
def test_get_analyzer_settings_returns_analyzer_settings(clear_config_cache: None) -> None:
    result = get_analyzer_settings()

    assert isinstance(result, AnalyzerSettings)


@pytest.mark.os_agnostic
def test_get_analyzer_settings_has_default_timeout(clear_config_cache: None) -> None:
    result = get_analyzer_settings()

    assert result.timeout == 30.0


@pytest.mark.os_agnostic
def test_get_analyzer_settings_has_default_concurrency(clear_config_cache: None) -> None:
    result = get_analyzer_settings()

    assert result.concurrency == 10


@pytest.mark.os_agnostic
def test_get_analyzer_settings_respects_github_token_env_var(
    clear_config_cache: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PYPROJ_DEP_ANALYZE_GITHUB_TOKEN", "env-token")

    result = get_analyzer_settings()

    assert result.github_token == "env-token"


@pytest.mark.os_agnostic
def test_get_analyzer_settings_respects_timeout_env_var(
    clear_config_cache: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PYPROJ_DEP_ANALYZE_TIMEOUT", "60.5")

    result = get_analyzer_settings()

    assert result.timeout == 60.5


@pytest.mark.os_agnostic
def test_get_analyzer_settings_respects_concurrency_env_var(
    clear_config_cache: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PYPROJ_DEP_ANALYZE_CONCURRENCY", "25")

    result = get_analyzer_settings()

    assert result.concurrency == 25


@pytest.mark.os_agnostic
def test_get_analyzer_settings_ignores_invalid_timeout_env_var(
    clear_config_cache: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PYPROJ_DEP_ANALYZE_TIMEOUT", "not-a-number")

    result = get_analyzer_settings()

    assert result.timeout == 30.0


@pytest.mark.os_agnostic
def test_get_analyzer_settings_ignores_invalid_concurrency_env_var(
    clear_config_cache: None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PYPROJ_DEP_ANALYZE_CONCURRENCY", "not-a-number")

    result = get_analyzer_settings()

    assert result.concurrency == 10


@pytest.mark.os_agnostic
def test_get_analyzer_settings_treats_empty_token_as_empty_string(
    clear_config_cache: None,
) -> None:
    result = get_analyzer_settings()

    assert result.github_token == ""


# ════════════════════════════════════════════════════════════════════════════
# Module Exports: __all__ completeness
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.os_agnostic
def test_module_exports_get_config() -> None:
    assert "get_config" in config_mod.__all__


@pytest.mark.os_agnostic
def test_module_exports_get_default_config_path() -> None:
    assert "get_default_config_path" in config_mod.__all__


@pytest.mark.os_agnostic
def test_module_exports_analyzer_settings() -> None:
    assert "AnalyzerSettings" in config_mod.__all__


@pytest.mark.os_agnostic
def test_module_exports_get_analyzer_settings() -> None:
    assert "get_analyzer_settings" in config_mod.__all__
