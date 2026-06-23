"""Logging setup stories: runtime configuration speaks clearly.

The logging_setup module initializes lib_log_rich with layered configuration.
These tests verify the initialization logic, idempotency, and configuration
bridging.
"""

from __future__ import annotations

from typing import Any

import pytest

from pyproj_dep_analyze import logging_setup as setup_mod
from pyproj_dep_analyze.logging_setup import init_logging


# ════════════════════════════════════════════════════════════════════════════
# init_logging: The idempotent initializer
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.os_agnostic
def test_init_logging_exists() -> None:
    assert callable(init_logging)


@pytest.mark.os_agnostic
def test_init_logging_returns_none() -> None:
    result = init_logging()

    assert result is None


@pytest.mark.os_agnostic
def test_init_logging_is_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    """Second call to init_logging should have no effect."""
    init_count = [0]

    def counting_init(*args: Any, **kwargs: Any) -> None:
        init_count[0] += 1

    def mock_is_initialised() -> bool:
        # Return True after first call
        return init_count[0] > 0

    monkeypatch.setattr(setup_mod.lib_log_rich.runtime, "init", counting_init)
    monkeypatch.setattr(setup_mod.lib_log_rich.runtime, "is_initialised", mock_is_initialised)

    init_logging()
    init_logging()

    assert init_count[0] == 1


@pytest.mark.os_agnostic
def test_init_logging_checks_initialization_state(monkeypatch: pytest.MonkeyPatch) -> None:
    """init_logging should check if already initialized."""
    check_calls = [0]

    def tracking_is_initialised() -> bool:
        check_calls[0] += 1
        return True

    monkeypatch.setattr(setup_mod.lib_log_rich.runtime, "is_initialised", tracking_is_initialised)

    init_logging()

    assert check_calls[0] >= 1


@pytest.mark.os_agnostic
def test_init_logging_skips_when_already_initialized(monkeypatch: pytest.MonkeyPatch) -> None:
    """init_logging should not re-initialize if already done."""
    init_calls = [0]

    def fake_init(*args: Any, **kwargs: Any) -> None:
        init_calls[0] += 1

    def always_initialised() -> bool:
        return True

    monkeypatch.setattr(setup_mod.lib_log_rich.runtime, "is_initialised", always_initialised)
    monkeypatch.setattr(setup_mod.lib_log_rich.runtime, "init", fake_init)

    init_logging()

    assert init_calls[0] == 0


# ════════════════════════════════════════════════════════════════════════════
# _build_runtime_config: The configuration builder
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.os_agnostic
def test_build_runtime_config_returns_runtime_config() -> None:
    import lib_log_rich.runtime

    # Clear config cache to ensure fresh config
    setup_mod.get_config.cache_clear()

    result = setup_mod._build_runtime_config()  # pyright: ignore[reportPrivateUsage]

    assert isinstance(result, lib_log_rich.runtime.RuntimeConfig)


@pytest.mark.os_agnostic
def test_build_runtime_config_sets_default_service_name() -> None:
    setup_mod.get_config.cache_clear()

    result = setup_mod._build_runtime_config()  # pyright: ignore[reportPrivateUsage]

    # Service should be set (either from config or default)
    assert result.service is not None


@pytest.mark.os_agnostic
def test_build_runtime_config_sets_default_environment() -> None:
    setup_mod.get_config.cache_clear()

    result = setup_mod._build_runtime_config()  # pyright: ignore[reportPrivateUsage]

    # Environment should be set (either from config or default)
    assert result.environment is not None


@pytest.mark.os_agnostic
def test_build_runtime_config_reads_from_layered_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeConfig:
        def get(self, key: str, default: Any = None) -> Any:
            if key == "lib_log_rich":
                return {"service": "custom-service", "environment": "staging"}
            return default

    def fake_get_config(**kwargs: Any) -> FakeConfig:
        return FakeConfig()

    monkeypatch.setattr(setup_mod, "get_config", fake_get_config)

    result = setup_mod._build_runtime_config()  # pyright: ignore[reportPrivateUsage]

    assert result.service == "custom-service"
    assert result.environment == "staging"


@pytest.mark.os_agnostic
def test_build_runtime_config_provides_defaults_when_config_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pyproj_dep_analyze import __init__conf__

    class FakeConfig:
        def get(self, key: str, default: Any = None) -> Any:
            return default

    def fake_get_config(**kwargs: Any) -> FakeConfig:
        return FakeConfig()

    monkeypatch.setattr(setup_mod, "get_config", fake_get_config)

    result = setup_mod._build_runtime_config()  # pyright: ignore[reportPrivateUsage]

    assert result.service == __init__conf__.name
    assert result.environment == "prod"


# ════════════════════════════════════════════════════════════════════════════
# Module Exports: __all__ completeness
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.os_agnostic
def test_module_exports_init_logging() -> None:
    assert "init_logging" in setup_mod.__all__


# ════════════════════════════════════════════════════════════════════════════
# Module-level state
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.os_agnostic
def test_module_has_runtime_config_storage() -> None:
    assert hasattr(setup_mod, "_runtime_config")
