"""Module entry stories: `python -m pyproj_dep_analyze` mirrors the CLI.

The __main__.py module runs ``cli.main()``, the function the console scripts
run. These tests verify that module execution gives the same exit codes and
output as that function.
"""

from __future__ import annotations

import importlib
import runpy
import sys
from typing import TYPE_CHECKING

import lib_cli_exit_tools
import pytest

from pyproj_dep_analyze import cli as cli_mod

if TYPE_CHECKING:
    from collections.abc import Callable

# ════════════════════════════════════════════════════════════════════════════
# Module Entry: parity with cli.main
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.os_agnostic
@pytest.mark.parametrize(
    "argv",
    [["--bogus-flag"], ["no-such-command"], ["--help"], ["hello"], ["info"]],
    ids=["bad-flag", "unknown-command", "help", "hello", "info"],
)
def test_module_entry_exits_with_the_code_the_console_script_gives(
    monkeypatch: pytest.MonkeyPatch,
    isolated_traceback_config: None,
    argv: list[str],
) -> None:
    script_code = cli_mod.main(argv)
    monkeypatch.setattr(sys, "argv", ["pyproj_dep_analyze", *argv])

    with pytest.raises(SystemExit) as exc:
        runpy.run_module("pyproj_dep_analyze.__main__", run_name="__main__")

    assert exc.value.code == script_code


@pytest.mark.os_agnostic
def test_module_entry_reports_a_usage_error_with_the_click_usage_code(
    monkeypatch: pytest.MonkeyPatch,
    isolated_traceback_config: None,
) -> None:
    monkeypatch.setattr(sys, "argv", ["pyproj_dep_analyze", "--bogus-flag"])

    with pytest.raises(SystemExit) as exc:
        runpy.run_module("pyproj_dep_analyze.__main__", run_name="__main__")

    assert exc.value.code == 2


# ════════════════════════════════════════════════════════════════════════════
# Module Entry: Traceback Flag
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.os_agnostic
def test_module_entry_with_traceback_flag_prints_full_traceback(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    strip_ansi: Callable[[str], str],
    isolated_traceback_config: None,
) -> None:
    monkeypatch.setattr(sys, "argv", ["pyproj_dep_analyze", "--traceback", "fail"])

    with pytest.raises(SystemExit) as exc:
        runpy.run_module("pyproj_dep_analyze.__main__", run_name="__main__")

    plain_err = strip_ansi(capsys.readouterr().err)

    assert exc.value.code != 0
    assert "Traceback (most recent call last)" in plain_err
    assert "RuntimeError: I should fail" in plain_err
    assert "[TRUNCATED" not in plain_err


@pytest.mark.os_agnostic
def test_module_entry_restores_traceback_config_after_execution(
    monkeypatch: pytest.MonkeyPatch,
    isolated_traceback_config: None,
    preserve_traceback_state: None,
) -> None:
    monkeypatch.setattr(sys, "argv", ["pyproj_dep_analyze", "--traceback", "fail"])

    with pytest.raises(SystemExit):
        runpy.run_module("pyproj_dep_analyze.__main__", run_name="__main__")

    assert lib_cli_exit_tools.config.traceback is False
    assert lib_cli_exit_tools.config.traceback_force_color is False


@pytest.mark.os_agnostic
def test_when_the_module_is_imported_it_runs_nothing() -> None:
    # Left imported, every later runpy of the module warns that it is already loaded.
    previous = sys.modules.pop("pyproj_dep_analyze.__main__", None)
    try:
        module = importlib.import_module("pyproj_dep_analyze.__main__")

        assert module.cli is cli_mod
    finally:
        sys.modules.pop("pyproj_dep_analyze.__main__", None)
        if previous is not None:
            sys.modules["pyproj_dep_analyze.__main__"] = previous


# ════════════════════════════════════════════════════════════════════════════
# CLI Module Import: Sanity checks
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.os_agnostic
def test_cli_module_defines_cli_group() -> None:
    assert hasattr(cli_mod, "cli")


@pytest.mark.os_agnostic
def test_cli_module_cli_is_click_command() -> None:
    import click

    assert isinstance(cli_mod.cli, click.core.Command)


@pytest.mark.os_agnostic
def test_cli_module_cli_has_expected_name() -> None:
    assert cli_mod.cli.name == "cli"


@pytest.mark.os_agnostic
def test_cli_module_defines_main_function() -> None:
    assert hasattr(cli_mod, "main")
    assert callable(cli_mod.main)
