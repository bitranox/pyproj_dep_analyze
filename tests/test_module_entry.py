"""Module entry stories: `python -m pyproj_dep_analyze` mirrors the CLI.

The __main__.py module enables execution via `python -m`. These tests
verify that module execution behaves identically to the console script,
using real execution paths where possible.
"""

from __future__ import annotations

import runpy
import sys
from collections.abc import Callable
from dataclasses import dataclass
from typing import TextIO

import pytest

import lib_cli_exit_tools

from pyproj_dep_analyze import __init__conf__, cli as cli_mod


# ════════════════════════════════════════════════════════════════════════════
# Helpers for traceback capture
# ════════════════════════════════════════════════════════════════════════════


@dataclass(slots=True)
class PrintedTraceback:
    """Capture of a traceback rendering invoked by lib_cli_exit_tools."""

    trace_back: bool
    length_limit: int
    stream_present: bool


def _make_traceback_printer(target: list[PrintedTraceback]) -> Callable[..., None]:
    """Return an exception printer that records each invocation."""

    def printer(
        *,
        trace_back: bool = False,
        length_limit: int = 500,
        stream: TextIO | None = None,
    ) -> None:
        target.append(
            PrintedTraceback(
                trace_back=trace_back,
                length_limit=length_limit,
                stream_present=stream is not None,
            )
        )

    return printer


# ════════════════════════════════════════════════════════════════════════════
# Module Entry: Success Path
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.os_agnostic
def test_module_entry_invokes_cli_with_correct_prog_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorded: dict[str, object] = {}

    def capture_run_cli(
        command: object,
        argv: list[str] | None = None,
        *,
        prog_name: str | None = None,
        **_: object,
    ) -> int:
        recorded["command"] = command
        recorded["argv"] = argv
        recorded["prog_name"] = prog_name
        return 0

    monkeypatch.setattr(sys, "argv", ["pyproj_dep_analyze"])
    monkeypatch.setattr(lib_cli_exit_tools, "run_cli", capture_run_cli)
    monkeypatch.setattr("lib_cli_exit_tools.application.runner.run_cli", capture_run_cli)

    with pytest.raises(SystemExit) as exc:
        runpy.run_module("pyproj_dep_analyze.__main__", run_name="__main__")

    assert exc.value.code == 0
    assert recorded["command"] is cli_mod.cli
    assert recorded["prog_name"] == __init__conf__.shell_command


@pytest.mark.os_agnostic
def test_module_entry_exits_with_zero_on_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_run_cli(*_: object, **__: object) -> int:
        return 0

    monkeypatch.setattr(sys, "argv", ["pyproj_dep_analyze"])
    monkeypatch.setattr(lib_cli_exit_tools, "run_cli", fake_run_cli)
    monkeypatch.setattr("lib_cli_exit_tools.application.runner.run_cli", fake_run_cli)

    with pytest.raises(SystemExit) as exc:
        runpy.run_module("pyproj_dep_analyze.__main__", run_name="__main__")

    assert exc.value.code == 0


# ════════════════════════════════════════════════════════════════════════════
# Module Entry: Error Handling
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.os_agnostic
def test_module_entry_formats_exception_via_exit_tools(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    printed: list[PrintedTraceback] = []
    exit_codes: list[str] = []

    monkeypatch.setattr(sys, "argv", ["pyproj_dep_analyze"])
    monkeypatch.setattr(lib_cli_exit_tools.config, "traceback", False, raising=False)
    monkeypatch.setattr(lib_cli_exit_tools.config, "traceback_force_color", False, raising=False)

    def compute_exit_code(exc: BaseException) -> int:
        exit_codes.append(f"code:{exc}")
        return 88

    def exploding_cli(
        *_args: object,
        exception_handler: Callable[[BaseException], int] | None = None,
        **_kwargs: object,
    ) -> int:
        def default_handler(exc: BaseException) -> int:
            return 1

        handler: Callable[[BaseException], int] = exception_handler or default_handler
        return handler(RuntimeError("boom"))

    printer = _make_traceback_printer(printed)

    monkeypatch.setattr(lib_cli_exit_tools, "print_exception_message", printer)
    monkeypatch.setattr(lib_cli_exit_tools, "get_system_exit_code", compute_exit_code)
    monkeypatch.setattr("lib_cli_exit_tools.application.runner.print_exception_message", printer)
    monkeypatch.setattr("lib_cli_exit_tools.application.runner.get_system_exit_code", compute_exit_code)
    monkeypatch.setattr(lib_cli_exit_tools, "run_cli", exploding_cli)
    monkeypatch.setattr("lib_cli_exit_tools.application.runner.run_cli", exploding_cli)

    with pytest.raises(SystemExit) as exc:
        runpy.run_module("pyproj_dep_analyze.__main__", run_name="__main__")

    assert exc.value.code == 88
    assert printed == [PrintedTraceback(trace_back=False, length_limit=500, stream_present=False)]
    assert exit_codes == ["code:boom"]


@pytest.mark.os_agnostic
def test_module_entry_returns_exit_code_from_cli(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def return_custom_code(*_: object, **__: object) -> int:
        return 42

    monkeypatch.setattr(sys, "argv", ["pyproj_dep_analyze"])
    monkeypatch.setattr(lib_cli_exit_tools, "run_cli", return_custom_code)
    monkeypatch.setattr("lib_cli_exit_tools.application.runner.run_cli", return_custom_code)

    with pytest.raises(SystemExit) as exc:
        runpy.run_module("pyproj_dep_analyze.__main__", run_name="__main__")

    assert exc.value.code == 42


# ════════════════════════════════════════════════════════════════════════════
# Module Entry: Traceback Flag
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.os_agnostic
def test_module_entry_with_traceback_flag_prints_full_traceback(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    strip_ansi: Callable[[str], str],
) -> None:
    monkeypatch.setattr(sys, "argv", ["pyproj_dep_analyze", "--traceback", "fail"])
    monkeypatch.setattr(lib_cli_exit_tools.config, "traceback", False, raising=False)
    monkeypatch.setattr(lib_cli_exit_tools.config, "traceback_force_color", False, raising=False)

    with pytest.raises(SystemExit) as exc:
        runpy.run_module("pyproj_dep_analyze.__main__", run_name="__main__")

    plain_err = strip_ansi(capsys.readouterr().err)

    assert exc.value.code != 0
    assert "Traceback (most recent call last)" in plain_err
    assert "RuntimeError: I should fail" in plain_err


@pytest.mark.os_agnostic
def test_module_entry_restores_traceback_config_after_execution(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    preserve_traceback_state: None,
) -> None:
    monkeypatch.setattr(sys, "argv", ["pyproj_dep_analyze", "--traceback", "fail"])
    monkeypatch.setattr(lib_cli_exit_tools.config, "traceback", False, raising=False)
    monkeypatch.setattr(lib_cli_exit_tools.config, "traceback_force_color", False, raising=False)

    with pytest.raises(SystemExit):
        runpy.run_module("pyproj_dep_analyze.__main__", run_name="__main__")

    assert lib_cli_exit_tools.config.traceback is False
    assert lib_cli_exit_tools.config.traceback_force_color is False


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
