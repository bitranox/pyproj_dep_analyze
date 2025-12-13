"""Configuration deployment stories: defaults reach their destinations.

The config_deploy module deploys default configuration to system and user
directories. These tests verify the deployment logic using real file
operations where possible, and mock filesystem interactions only when
necessary for platform isolation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from lib_layered_config.examples.deploy import DeployAction, DeployResult

from pyproj_dep_analyze import config_deploy as deploy_mod
from pyproj_dep_analyze.config_deploy import deploy_configuration
from pyproj_dep_analyze.models import DeploymentTarget


# ════════════════════════════════════════════════════════════════════════════
# deploy_configuration: The configuration deployer
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.os_agnostic
def test_deploy_configuration_exists() -> None:
    assert callable(deploy_configuration)


@pytest.mark.os_agnostic
def test_deploy_configuration_accepts_targets_parameter() -> None:
    import inspect

    sig = inspect.signature(deploy_configuration)

    assert "targets" in sig.parameters


@pytest.mark.os_agnostic
def test_deploy_configuration_accepts_force_parameter() -> None:
    import inspect

    sig = inspect.signature(deploy_configuration)

    assert "force" in sig.parameters


@pytest.mark.os_agnostic
def test_deploy_configuration_force_defaults_to_false() -> None:
    import inspect

    sig = inspect.signature(deploy_configuration)
    force_param = sig.parameters["force"]

    assert force_param.default is False


@pytest.mark.os_agnostic
def test_deploy_configuration_returns_list(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_deploy_config(**kwargs: Any) -> list[DeployResult]:
        return []

    monkeypatch.setattr(deploy_mod, "deploy_config", fake_deploy_config)

    result = deploy_configuration(targets=[DeploymentTarget.USER])

    assert isinstance(result, list)


@pytest.mark.os_agnostic
def test_deploy_configuration_passes_targets_to_lib_layered_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def capture_deploy_config(**kwargs: Any) -> list[DeployResult]:
        captured.update(kwargs)
        return []

    monkeypatch.setattr(deploy_mod, "deploy_config", capture_deploy_config)

    deploy_configuration(targets=[DeploymentTarget.USER, DeploymentTarget.HOST])

    assert captured["targets"] == ["user", "host"]


@pytest.mark.os_agnostic
def test_deploy_configuration_passes_force_to_lib_layered_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def capture_deploy_config(**kwargs: Any) -> list[DeployResult]:
        captured.update(kwargs)
        return []

    monkeypatch.setattr(deploy_mod, "deploy_config", capture_deploy_config)

    deploy_configuration(targets=[DeploymentTarget.USER], force=True)

    assert captured["force"] is True


@pytest.mark.os_agnostic
def test_deploy_configuration_uses_correct_vendor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pyproj_dep_analyze import __init__conf__

    captured: dict[str, Any] = {}

    def capture_deploy_config(**kwargs: Any) -> list[DeployResult]:
        captured.update(kwargs)
        return []

    monkeypatch.setattr(deploy_mod, "deploy_config", capture_deploy_config)

    deploy_configuration(targets=[DeploymentTarget.USER])

    assert captured["vendor"] == __init__conf__.LAYEREDCONF_VENDOR


@pytest.mark.os_agnostic
def test_deploy_configuration_uses_correct_app(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pyproj_dep_analyze import __init__conf__

    captured: dict[str, Any] = {}

    def capture_deploy_config(**kwargs: Any) -> list[DeployResult]:
        captured.update(kwargs)
        return []

    monkeypatch.setattr(deploy_mod, "deploy_config", capture_deploy_config)

    deploy_configuration(targets=[DeploymentTarget.USER])

    assert captured["app"] == __init__conf__.LAYEREDCONF_APP


@pytest.mark.os_agnostic
def test_deploy_configuration_uses_correct_slug(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pyproj_dep_analyze import __init__conf__

    captured: dict[str, Any] = {}

    def capture_deploy_config(**kwargs: Any) -> list[DeployResult]:
        captured.update(kwargs)
        return []

    monkeypatch.setattr(deploy_mod, "deploy_config", capture_deploy_config)

    deploy_configuration(targets=[DeploymentTarget.USER])

    assert captured["slug"] == __init__conf__.LAYEREDCONF_SLUG


@pytest.mark.os_agnostic
def test_deploy_configuration_uses_default_config_as_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pyproj_dep_analyze.config import get_default_config_path

    captured: dict[str, Any] = {}

    def capture_deploy_config(**kwargs: Any) -> list[DeployResult]:
        captured.update(kwargs)
        return []

    monkeypatch.setattr(deploy_mod, "deploy_config", capture_deploy_config)

    deploy_configuration(targets=[DeploymentTarget.USER])

    assert captured["source"] == get_default_config_path()


@pytest.mark.os_agnostic
def test_deploy_configuration_returns_deployed_results(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    expected_results = [
        DeployResult(
            destination=tmp_path / "config1.toml",
            action=DeployAction.CREATED,
            backup_path=None,
            ucf_path=None,
        ),
        DeployResult(
            destination=tmp_path / "config2.toml",
            action=DeployAction.CREATED,
            backup_path=None,
            ucf_path=None,
        ),
    ]

    def fake_deploy_config(**kwargs: Any) -> list[DeployResult]:
        return expected_results

    monkeypatch.setattr(deploy_mod, "deploy_config", fake_deploy_config)

    result = deploy_configuration(targets=[DeploymentTarget.USER])

    assert result == expected_results


@pytest.mark.os_agnostic
def test_deploy_configuration_returns_empty_list_when_all_exist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_deploy_config(**kwargs: Any) -> list[DeployResult]:
        return []

    monkeypatch.setattr(deploy_mod, "deploy_config", fake_deploy_config)

    result = deploy_configuration(targets=[DeploymentTarget.USER], force=False)

    assert result == []


# ════════════════════════════════════════════════════════════════════════════
# Module Exports: __all__ completeness
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.os_agnostic
def test_module_exports_deploy_configuration() -> None:
    assert "deploy_configuration" in deploy_mod.__all__
