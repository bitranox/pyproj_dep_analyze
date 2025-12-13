"""CLI stories: each invocation speaks one truth.

The CLI module adapts domain behaviors to the command line. These tests
verify real command execution with actual outputs, avoiding stubs except
where necessary for state isolation.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner, Result
from lib_layered_config.examples.deploy import DeployAction, DeployResult

import lib_cli_exit_tools

from pyproj_dep_analyze import cli as cli_mod
from pyproj_dep_analyze import cli_display as cli_display_mod
from pyproj_dep_analyze import __init__conf__


# ════════════════════════════════════════════════════════════════════════════
# Traceback State Management: snapshot, apply, restore
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.os_agnostic
def test_snapshot_traceback_state_captures_false_when_disabled(
    isolated_traceback_config: None,
) -> None:
    result = cli_mod.snapshot_traceback_state()

    assert result.enabled is False
    assert result.force_color is False


@pytest.mark.os_agnostic
def test_snapshot_traceback_state_captures_true_when_enabled(
    isolated_traceback_config: None,
) -> None:
    cli_mod.apply_traceback_preferences(True)

    result = cli_mod.snapshot_traceback_state()

    assert result.enabled is True
    assert result.force_color is True


@pytest.mark.os_agnostic
def test_apply_traceback_preferences_enables_both_flags(
    isolated_traceback_config: None,
) -> None:
    cli_mod.apply_traceback_preferences(True)

    assert lib_cli_exit_tools.config.traceback is True
    assert lib_cli_exit_tools.config.traceback_force_color is True


@pytest.mark.os_agnostic
def test_apply_traceback_preferences_disables_both_flags(
    isolated_traceback_config: None,
) -> None:
    cli_mod.apply_traceback_preferences(True)
    cli_mod.apply_traceback_preferences(False)

    assert lib_cli_exit_tools.config.traceback is False
    assert lib_cli_exit_tools.config.traceback_force_color is False


@pytest.mark.os_agnostic
def test_restore_traceback_state_resets_to_previous_values(
    isolated_traceback_config: None,
) -> None:
    previous = cli_mod.snapshot_traceback_state()
    cli_mod.apply_traceback_preferences(True)

    cli_mod.restore_traceback_state(previous)

    assert lib_cli_exit_tools.config.traceback is False
    assert lib_cli_exit_tools.config.traceback_force_color is False


# ════════════════════════════════════════════════════════════════════════════
# CLI Root Group: help and default behavior
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.os_agnostic
def test_cli_without_arguments_shows_help(cli_runner: CliRunner) -> None:
    result: Result = cli_runner.invoke(cli_mod.cli, [])

    assert result.exit_code == 0
    assert "Usage:" in result.output


@pytest.mark.os_agnostic
def test_cli_with_help_flag_shows_help(cli_runner: CliRunner) -> None:
    result: Result = cli_runner.invoke(cli_mod.cli, ["--help"])

    assert result.exit_code == 0
    assert "Usage:" in result.output
    assert "--traceback" in result.output


@pytest.mark.os_agnostic
def test_cli_with_short_help_flag_shows_help(cli_runner: CliRunner) -> None:
    result: Result = cli_runner.invoke(cli_mod.cli, ["-h"])

    assert result.exit_code == 0
    assert "Usage:" in result.output


@pytest.mark.os_agnostic
def test_cli_with_version_flag_shows_version(cli_runner: CliRunner) -> None:
    result: Result = cli_runner.invoke(cli_mod.cli, ["--version"])

    assert result.exit_code == 0
    assert __init__conf__.version in result.output


@pytest.mark.os_agnostic
def test_cli_with_traceback_flag_runs_default_action(
    cli_runner: CliRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def track_call() -> None:
        calls.append("noop_main called")

    monkeypatch.setattr(cli_mod, "noop_main", track_call)

    result: Result = cli_runner.invoke(cli_mod.cli, ["--traceback"])

    assert result.exit_code == 0
    assert calls == ["noop_main called"]


@pytest.mark.os_agnostic
def test_cli_with_unknown_command_shows_error(cli_runner: CliRunner) -> None:
    result: Result = cli_runner.invoke(cli_mod.cli, ["nonexistent-command"])

    assert result.exit_code != 0
    assert "No such command" in result.output


# ════════════════════════════════════════════════════════════════════════════
# hello Command: the success path
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.os_agnostic
def test_hello_command_prints_greeting(cli_runner: CliRunner) -> None:
    result: Result = cli_runner.invoke(cli_mod.cli, ["hello"])

    assert result.exit_code == 0
    assert "Hello World" in result.output


@pytest.mark.os_agnostic
def test_hello_command_has_zero_exit_code(cli_runner: CliRunner) -> None:
    result: Result = cli_runner.invoke(cli_mod.cli, ["hello"])

    assert result.exit_code == 0


# ════════════════════════════════════════════════════════════════════════════
# fail Command: the error path
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.os_agnostic
def test_fail_command_raises_runtime_error(cli_runner: CliRunner) -> None:
    result: Result = cli_runner.invoke(cli_mod.cli, ["fail"])

    assert result.exit_code != 0
    assert isinstance(result.exception, RuntimeError)


@pytest.mark.os_agnostic
def test_fail_command_includes_expected_message(cli_runner: CliRunner) -> None:
    result: Result = cli_runner.invoke(cli_mod.cli, ["fail"])

    assert result.exception is not None
    assert "I should fail" in str(result.exception)


# ════════════════════════════════════════════════════════════════════════════
# info Command: metadata display
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.os_agnostic
def test_info_command_shows_package_name(cli_runner: CliRunner) -> None:
    result: Result = cli_runner.invoke(cli_mod.cli, ["info"])

    assert result.exit_code == 0
    assert f"Info for {__init__conf__.name}:" in result.output


@pytest.mark.os_agnostic
def test_info_command_shows_version(cli_runner: CliRunner) -> None:
    result: Result = cli_runner.invoke(cli_mod.cli, ["info"])

    assert result.exit_code == 0
    assert __init__conf__.version in result.output


@pytest.mark.os_agnostic
def test_info_command_respects_traceback_flag(
    monkeypatch: pytest.MonkeyPatch,
    isolated_traceback_config: None,
    preserve_traceback_state: None,
) -> None:
    states: list[tuple[bool, bool]] = []

    def capture_state() -> None:
        states.append(
            (
                lib_cli_exit_tools.config.traceback,
                lib_cli_exit_tools.config.traceback_force_color,
            )
        )

    monkeypatch.setattr(cli_mod.__init__conf__, "print_info", capture_state)

    cli_mod.main(["--traceback", "info"])

    assert states == [(True, True)]


# ════════════════════════════════════════════════════════════════════════════
# config Command: configuration display
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.os_agnostic
def test_config_command_runs_without_error(cli_runner: CliRunner) -> None:
    result: Result = cli_runner.invoke(cli_mod.cli, ["config"])

    assert result.exit_code == 0


@pytest.mark.os_agnostic
def test_config_command_with_json_format_outputs_json(cli_runner: CliRunner) -> None:
    result: Result = cli_runner.invoke(cli_mod.cli, ["config", "--format", "json"])

    assert result.exit_code == 0
    assert "{" in result.output


@pytest.mark.os_agnostic
def test_config_command_with_invalid_section_fails(cli_runner: CliRunner) -> None:
    result: Result = cli_runner.invoke(
        cli_mod.cli,
        ["config", "--section", "nonexistent_section_xyz"],
    )

    assert result.exit_code != 0
    assert "not found or empty" in result.output


@pytest.mark.os_agnostic
def test_config_command_with_mocked_config_shows_sections(
    cli_runner: CliRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from lib_layered_config import Config
    from pyproj_dep_analyze import config as config_mod
    from pyproj_dep_analyze import config_show

    test_data = {
        "test_section": {
            "key1": "value1",
            "key2": 42,
        }
    }

    class FakeConfig(Config):
        def __init__(self) -> None:
            pass

        def as_dict(self) -> dict[str, Any]:
            return test_data

        def to_json(self, *, indent: int | None = None) -> str:
            import json

            return json.dumps(test_data, indent=indent)

        def get(self, key: str, default: Any = None) -> Any:
            return test_data.get(key, default)

        def __iter__(self):
            return iter(test_data)

        def __getitem__(self, key: str) -> Any:
            return test_data[key]

    config_mod.get_config.cache_clear()

    def fake_get_config(**kwargs: Any) -> Config:
        return FakeConfig()

    monkeypatch.setattr(config_mod, "get_config", fake_get_config)
    monkeypatch.setattr(config_show, "get_config", fake_get_config)

    result: Result = cli_runner.invoke(cli_mod.cli, ["config"])

    assert result.exit_code == 0
    assert "test_section" in result.output


# ════════════════════════════════════════════════════════════════════════════
# config-deploy Command: configuration deployment
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.os_agnostic
def test_config_deploy_without_target_fails(cli_runner: CliRunner) -> None:
    result: Result = cli_runner.invoke(cli_mod.cli, ["config-deploy"])

    assert result.exit_code != 0
    assert "Missing option" in result.output or "required" in result.output.lower()


@pytest.mark.os_agnostic
def test_config_deploy_with_target_invokes_deploy(
    cli_runner: CliRunner,
    tmp_path: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    deployed_path = tmp_path / "deployed.toml"
    deployed_path.touch()

    def fake_deploy(*, targets: Any, force: bool = False) -> list[DeployResult]:
        return [
            DeployResult(
                destination=deployed_path,
                action=DeployAction.CREATED,
                backup_path=None,
                ucf_path=None,
            )
        ]

    monkeypatch.setattr(cli_mod, "deploy_configuration", fake_deploy)

    result: Result = cli_runner.invoke(cli_mod.cli, ["config-deploy", "--target", "user"])

    assert result.exit_code == 0
    assert "Configuration deployed successfully" in result.output


@pytest.mark.os_agnostic
def test_config_deploy_reports_when_no_files_created(
    cli_runner: CliRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_deploy(*, targets: Any, force: bool = False) -> list[DeployResult]:
        return []

    monkeypatch.setattr(cli_mod, "deploy_configuration", fake_deploy)

    result: Result = cli_runner.invoke(cli_mod.cli, ["config-deploy", "--target", "user"])

    assert result.exit_code == 0
    assert "No files were created" in result.output
    assert "--force" in result.output


@pytest.mark.os_agnostic
def test_config_deploy_handles_permission_error(
    cli_runner: CliRunner,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_deploy(*, targets: Any, force: bool = False) -> list[Any]:
        raise PermissionError("Access denied")

    monkeypatch.setattr(cli_mod, "deploy_configuration", fake_deploy)

    result: Result = cli_runner.invoke(cli_mod.cli, ["config-deploy", "--target", "app"])

    assert result.exit_code != 0
    assert "Permission denied" in result.output


@pytest.mark.os_agnostic
def test_config_deploy_accepts_multiple_targets(
    cli_runner: CliRunner,
    tmp_path: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path1 = tmp_path / "config1.toml"
    path2 = tmp_path / "config2.toml"
    path1.touch()
    path2.touch()
    captured_targets: list[Any] = []

    def fake_deploy(*, targets: Any, force: bool = False) -> list[DeployResult]:
        captured_targets.extend(targets)
        return [
            DeployResult(
                destination=path1,
                action=DeployAction.CREATED,
                backup_path=None,
                ucf_path=None,
            ),
            DeployResult(
                destination=path2,
                action=DeployAction.CREATED,
                backup_path=None,
                ucf_path=None,
            ),
        ]

    monkeypatch.setattr(cli_mod, "deploy_configuration", fake_deploy)

    result: Result = cli_runner.invoke(
        cli_mod.cli,
        ["config-deploy", "--target", "user", "--target", "host"],
    )

    assert result.exit_code == 0
    assert "user" in captured_targets
    assert "host" in captured_targets


# ════════════════════════════════════════════════════════════════════════════
# main() Function: entry point orchestration
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.os_agnostic
def test_main_with_info_returns_zero(
    isolated_traceback_config: None,
    preserve_traceback_state: None,
) -> None:
    exit_code = cli_mod.main(["info"])

    assert exit_code == 0


@pytest.mark.os_agnostic
def test_main_with_hello_returns_zero(
    isolated_traceback_config: None,
    preserve_traceback_state: None,
) -> None:
    exit_code = cli_mod.main(["hello"])

    assert exit_code == 0


@pytest.mark.os_agnostic
def test_main_with_fail_and_traceback_prints_full_traceback(
    isolated_traceback_config: None,
    preserve_traceback_state: None,
    capsys: pytest.CaptureFixture[str],
    strip_ansi: Callable[[str], str],
) -> None:
    exit_code = cli_mod.main(["--traceback", "fail"])

    plain_err = strip_ansi(capsys.readouterr().err)

    assert exit_code != 0
    assert "Traceback (most recent call last)" in plain_err
    assert "RuntimeError: I should fail" in plain_err


@pytest.mark.os_agnostic
def test_main_restores_traceback_state_by_default(
    isolated_traceback_config: None,
    preserve_traceback_state: None,
) -> None:
    cli_mod.main(["--traceback", "hello"])

    assert lib_cli_exit_tools.config.traceback is False
    assert lib_cli_exit_tools.config.traceback_force_color is False


@pytest.mark.os_agnostic
def test_main_preserves_traceback_when_restore_disabled(
    isolated_traceback_config: None,
    preserve_traceback_state: None,
) -> None:
    cli_mod.apply_traceback_preferences(False)

    cli_mod.main(["--traceback", "hello"], restore_traceback=False)

    assert lib_cli_exit_tools.config.traceback is True
    assert lib_cli_exit_tools.config.traceback_force_color is True


@pytest.mark.os_agnostic
def test_main_delegates_to_lib_cli_exit_tools(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from dataclasses import dataclass

    @dataclass
    class CapturedCall:
        command: Any
        argv: list[str] | None
        prog_name: str | None

    captured: list[CapturedCall] = []

    def fake_run_cli(
        command: Any,
        argv: Any = None,
        *,
        prog_name: str | None = None,
        **kwargs: Any,
    ) -> int:
        captured.append(CapturedCall(command, argv, prog_name))
        return 42

    monkeypatch.setattr(lib_cli_exit_tools, "run_cli", fake_run_cli)

    result = cli_mod.main(["info"])

    assert result == 42
    assert len(captured) == 1
    assert captured[0].command is cli_mod.cli
    assert captured[0].prog_name == __init__conf__.shell_command


# ════════════════════════════════════════════════════════════════════════════
# Internal Helpers
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.os_agnostic
def test_traceback_limit_returns_verbose_when_enabled() -> None:
    result = cli_mod._traceback_limit(  # pyright: ignore[reportPrivateUsage]
        tracebacks_enabled=True,
        summary_limit=500,
        verbose_limit=10000,
    )

    assert result == 10000


@pytest.mark.os_agnostic
def test_traceback_limit_returns_summary_when_disabled() -> None:
    result = cli_mod._traceback_limit(  # pyright: ignore[reportPrivateUsage]
        tracebacks_enabled=False,
        summary_limit=500,
        verbose_limit=10000,
    )

    assert result == 500


@pytest.mark.os_agnostic
def test_current_traceback_mode_reflects_config(
    isolated_traceback_config: None,
) -> None:
    assert cli_mod._current_traceback_mode() is False  # pyright: ignore[reportPrivateUsage]

    cli_mod.apply_traceback_preferences(True)

    assert cli_mod._current_traceback_mode() is True  # pyright: ignore[reportPrivateUsage]


# ════════════════════════════════════════════════════════════════════════════
# analyze Command: dependency analysis
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.os_agnostic
def test_analyze_command_exists() -> None:
    assert "analyze" in [cmd.name for cmd in cli_mod.cli.commands.values()]


@pytest.mark.os_agnostic
def test_analyze_command_requires_valid_pyproject_path(cli_runner: CliRunner) -> None:
    result: Result = cli_runner.invoke(
        cli_mod.cli,
        ["analyze", "/nonexistent/path/pyproject.toml"],
    )

    assert result.exit_code != 0


@pytest.mark.os_agnostic
def test_analyze_command_with_mocked_analysis(
    cli_runner: CliRunner,
    tmp_path: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pyproj_dep_analyze.models import Action, AnalysisResult, OutdatedEntry

    # Create a minimal pyproject.toml
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nname = "test"')

    # Create a mock analysis result
    mock_result = AnalysisResult(
        entries=[
            OutdatedEntry(
                package="requests",
                python_version="3.11",
                current_version="2.28.0",
                latest_version="2.31.0",
                action=Action.UPDATE,
            )
        ],
        python_versions=["3.11"],
    )

    def fake_run_analysis(*args: Any, **kwargs: Any) -> AnalysisResult:
        return mock_result

    def fake_write_json(*args: Any, **kwargs: Any) -> None:
        pass

    monkeypatch.setattr(cli_mod, "run_analysis", fake_run_analysis)
    monkeypatch.setattr(cli_mod, "write_outdated_json", fake_write_json)

    result: Result = cli_runner.invoke(
        cli_mod.cli,
        ["analyze", str(pyproject)],
    )

    assert result.exit_code == 0
    assert "Wrote" in result.output


@pytest.mark.os_agnostic
def test_analyze_command_writes_to_output_file(
    cli_runner: CliRunner,
    tmp_path: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pyproj_dep_analyze.models import AnalysisResult

    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nname = "test"')
    output_file = tmp_path / "custom_output.json"

    captured_args: dict[str, Any] = {}

    def fake_run_analysis(*args: Any, **kwargs: Any) -> AnalysisResult:
        return AnalysisResult(entries=[], python_versions=[])

    def fake_write_json(entries: Any, output_path: Path) -> None:
        captured_args["output_path"] = output_path

    monkeypatch.setattr(cli_mod, "run_analysis", fake_run_analysis)
    monkeypatch.setattr(cli_mod, "write_outdated_json", fake_write_json)

    result: Result = cli_runner.invoke(
        cli_mod.cli,
        ["analyze", str(pyproject), "-o", str(output_file)],
    )

    assert result.exit_code == 0
    assert captured_args["output_path"] == output_file


@pytest.mark.os_agnostic
def test_analyze_command_with_summary_format(
    cli_runner: CliRunner,
    tmp_path: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pyproj_dep_analyze.models import AnalysisResult

    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nname = "test"')

    def fake_run_analysis(*args: Any, **kwargs: Any) -> AnalysisResult:
        return AnalysisResult(entries=[], python_versions=["3.11"])

    def fake_write_json(*args: Any, **kwargs: Any) -> None:
        pass

    monkeypatch.setattr(cli_mod, "run_analysis", fake_run_analysis)
    monkeypatch.setattr(cli_mod, "write_outdated_json", fake_write_json)

    result: Result = cli_runner.invoke(
        cli_mod.cli,
        ["analyze", str(pyproject), "--format", "summary"],
    )

    assert result.exit_code == 0
    assert "SUMMARY" in result.output


@pytest.mark.os_agnostic
def test_analyze_command_with_json_format(
    cli_runner: CliRunner,
    tmp_path: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pyproj_dep_analyze.models import AnalysisResult

    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nname = "test"')

    def fake_run_analysis(*args: Any, **kwargs: Any) -> AnalysisResult:
        return AnalysisResult(entries=[], python_versions=["3.11"])

    def fake_write_json(*args: Any, **kwargs: Any) -> None:
        pass

    monkeypatch.setattr(cli_mod, "run_analysis", fake_run_analysis)
    monkeypatch.setattr(cli_mod, "write_outdated_json", fake_write_json)

    result: Result = cli_runner.invoke(
        cli_mod.cli,
        ["analyze", str(pyproject), "--format", "json"],
    )

    assert result.exit_code == 0
    assert "[" in result.output  # JSON array output


# ════════════════════════════════════════════════════════════════════════════
# Display Functions: analysis output formatting
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.os_agnostic
def test_display_summary_shows_python_versions(
    capsys: pytest.CaptureFixture[str],
) -> None:
    from pyproj_dep_analyze.models import AnalysisResult

    result = AnalysisResult(entries=[], python_versions=["3.10", "3.11"])

    cli_display_mod.display_summary(result)

    captured = capsys.readouterr()
    assert "3.10" in captured.out
    assert "3.11" in captured.out


@pytest.mark.os_agnostic
def test_display_summary_shows_total_dependencies(
    capsys: pytest.CaptureFixture[str],
) -> None:
    from pyproj_dep_analyze.models import Action, AnalysisResult, OutdatedEntry

    result = AnalysisResult(
        entries=[
            OutdatedEntry(package="pkg1", python_version="3.11", current_version="1.0", latest_version="1.1", action=Action.UPDATE),
            OutdatedEntry(package="pkg2", python_version="3.11", current_version="2.0", latest_version="2.1", action=Action.UPDATE),
        ],
        python_versions=["3.11"],
        total_dependencies=2,  # Must be explicitly set
    )

    cli_display_mod.display_summary(result)

    captured = capsys.readouterr()
    assert "Total unique dependencies: 2" in captured.out


@pytest.mark.os_agnostic
def test_display_updates_section_shows_updates(
    capsys: pytest.CaptureFixture[str],
) -> None:
    from pyproj_dep_analyze.models import Action, OutdatedEntry

    updates = [
        OutdatedEntry(package="requests", python_version="3.11", current_version="2.28.0", latest_version="2.31.0", action=Action.UPDATE),
    ]

    cli_display_mod._display_updates_section(updates)  # pyright: ignore[reportPrivateUsage]

    captured = capsys.readouterr()
    assert "UPDATES AVAILABLE" in captured.out
    assert "requests" in captured.out
    assert "2.28.0" in captured.out
    assert "2.31.0" in captured.out


@pytest.mark.os_agnostic
def test_display_updates_section_truncates_at_twenty(
    capsys: pytest.CaptureFixture[str],
) -> None:
    from pyproj_dep_analyze.models import Action, OutdatedEntry

    updates = [OutdatedEntry(package=f"pkg{i}", python_version="3.11", current_version="1.0", latest_version="2.0", action=Action.UPDATE) for i in range(25)]

    cli_display_mod._display_updates_section(updates)  # pyright: ignore[reportPrivateUsage]

    captured = capsys.readouterr()
    assert "... and 5 more" in captured.out


@pytest.mark.os_agnostic
def test_display_updates_section_does_nothing_for_empty_list(
    capsys: pytest.CaptureFixture[str],
) -> None:
    cli_display_mod._display_updates_section([])  # pyright: ignore[reportPrivateUsage]

    captured = capsys.readouterr()
    assert captured.out == ""


@pytest.mark.os_agnostic
def test_display_manual_section_shows_manual_checks(
    capsys: pytest.CaptureFixture[str],
) -> None:
    from pyproj_dep_analyze.models import Action, OutdatedEntry

    manual = [
        OutdatedEntry(package="custom-pkg", python_version="3.11", current_version="unknown", latest_version="unknown", action=Action.CHECK_MANUALLY),
    ]

    cli_display_mod._display_manual_section(manual)  # pyright: ignore[reportPrivateUsage]

    captured = capsys.readouterr()
    assert "MANUAL CHECK REQUIRED" in captured.out
    assert "custom-pkg" in captured.out


@pytest.mark.os_agnostic
def test_display_manual_section_truncates_at_ten(
    capsys: pytest.CaptureFixture[str],
) -> None:
    from pyproj_dep_analyze.models import Action, OutdatedEntry

    manual = [
        OutdatedEntry(package=f"pkg{i}", python_version="3.11", current_version="1.0", latest_version="?", action=Action.CHECK_MANUALLY) for i in range(15)
    ]

    cli_display_mod._display_manual_section(manual)  # pyright: ignore[reportPrivateUsage]

    captured = capsys.readouterr()
    assert "... and 5 more" in captured.out


@pytest.mark.os_agnostic
def test_display_manual_section_does_nothing_for_empty_list(
    capsys: pytest.CaptureFixture[str],
) -> None:
    cli_display_mod._display_manual_section([])  # pyright: ignore[reportPrivateUsage]

    captured = capsys.readouterr()
    assert captured.out == ""


@pytest.mark.os_agnostic
def test_display_json_outputs_valid_json(
    capsys: pytest.CaptureFixture[str],
) -> None:
    import json
    from pyproj_dep_analyze.models import Action, AnalysisResult, OutdatedEntry

    result = AnalysisResult(
        entries=[
            OutdatedEntry(package="requests", python_version="3.11", current_version="2.28.0", latest_version="2.31.0", action=Action.UPDATE),
        ],
        python_versions=["3.11"],
    )

    cli_display_mod.display_json(result)

    captured = capsys.readouterr()
    parsed = json.loads(captured.out)
    assert isinstance(parsed, list)
    assert parsed[0]["package"] == "requests"


@pytest.mark.os_agnostic
def test_display_table_includes_summary_and_sections(
    capsys: pytest.CaptureFixture[str],
) -> None:
    from pyproj_dep_analyze.models import Action, AnalysisResult, OutdatedEntry

    result = AnalysisResult(
        entries=[
            OutdatedEntry(package="requests", python_version="3.11", current_version="2.28.0", latest_version="2.31.0", action=Action.UPDATE),
            OutdatedEntry(package="custom", python_version="3.11", current_version="?", latest_version="?", action=Action.CHECK_MANUALLY),
        ],
        python_versions=["3.11"],
    )

    cli_display_mod.display_table(result)

    captured = capsys.readouterr()
    assert "SUMMARY" in captured.out
    assert "UPDATES AVAILABLE" in captured.out
    assert "MANUAL CHECK REQUIRED" in captured.out


# ════════════════════════════════════════════════════════════════════════════
# Deploy Reporting Helpers
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.os_agnostic
def test_report_deploy_results_shows_paths(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Any,
) -> None:
    results = [
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

    cli_mod._report_deploy_results(results)  # pyright: ignore[reportPrivateUsage]

    captured = capsys.readouterr()
    assert "Configuration deployed successfully" in captured.out
    assert "config1.toml" in captured.out
    assert "config2.toml" in captured.out


@pytest.mark.os_agnostic
def test_report_deploy_results_suggests_force_when_empty(
    capsys: pytest.CaptureFixture[str],
) -> None:
    cli_mod._report_deploy_results([])  # pyright: ignore[reportPrivateUsage]

    captured = capsys.readouterr()
    assert "No files were created" in captured.out
    assert "--force" in captured.out


@pytest.mark.os_agnostic
def test_handle_deploy_error_for_permission_error(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exc = PermissionError("Access denied to /etc/config")

    with pytest.raises(SystemExit) as exit_info:
        cli_mod._handle_deploy_error(exc)  # pyright: ignore[reportPrivateUsage]

    assert exit_info.value.code == 1
    captured = capsys.readouterr()
    assert "Permission denied" in captured.err


@pytest.mark.os_agnostic
def test_handle_deploy_error_for_generic_exception(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exc = RuntimeError("Something went wrong")

    with pytest.raises(SystemExit) as exit_info:
        cli_mod._handle_deploy_error(exc)  # pyright: ignore[reportPrivateUsage]

    assert exit_info.value.code == 1
    captured = capsys.readouterr()
    assert "Failed to deploy configuration" in captured.err
