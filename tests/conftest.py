"""Shared pytest fixtures and configuration for all tests.

This module provides:
- OS markers registration (os_agnostic, posix_only, windows_only, macos_only)
- CLI runner fixtures
- Configuration state management fixtures
- Testdata path fixture
"""

from __future__ import annotations

import re
import sys
from collections.abc import Callable, Iterator
from dataclasses import fields
from pathlib import Path

import pytest
from click.testing import CliRunner

import lib_cli_exit_tools

# ════════════════════════════════════════════════════════════════════════════
# Paths
# ════════════════════════════════════════════════════════════════════════════

TESTDATA_DIR = Path(__file__).parent / "testdata"
ANSI_ESCAPE_PATTERN = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")
CONFIG_FIELDS: tuple[str, ...] = tuple(field.name for field in fields(type(lib_cli_exit_tools.config)))


# ════════════════════════════════════════════════════════════════════════════
# OS Markers Registration
# ════════════════════════════════════════════════════════════════════════════


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers for OS-specific and E2E tests."""
    config.addinivalue_line(
        "markers",
        "os_agnostic: marks test as OS-agnostic (runs on all platforms)",
    )
    config.addinivalue_line(
        "markers",
        "posix_only: marks test to run only on POSIX systems (Linux/macOS)",
    )
    config.addinivalue_line(
        "markers",
        "windows_only: marks test to run only on Windows",
    )
    config.addinivalue_line(
        "markers",
        "macos_only: marks test to run only on macOS",
    )
    config.addinivalue_line(
        "markers",
        "linux_only: marks test to run only on Linux",
    )
    config.addinivalue_line(
        "markers",
        "e2e: marks test as end-to-end integration test (requires network)",
    )
    config.addinivalue_line(
        "markers",
        "network: marks test as requiring network access to PyPI/GitHub APIs",
    )


def pytest_collection_modifyitems(
    config: pytest.Config,
    items: list[pytest.Item],
) -> None:
    """Skip tests based on OS markers."""
    is_windows = sys.platform == "win32"
    is_macos = sys.platform == "darwin"
    is_linux = sys.platform.startswith("linux")
    is_posix = not is_windows

    for item in items:
        if item.get_closest_marker("windows_only"):
            if not is_windows:
                item.add_marker(pytest.mark.skip(reason="Windows-only test"))

        if item.get_closest_marker("posix_only"):
            if not is_posix:
                item.add_marker(pytest.mark.skip(reason="POSIX-only test"))

        if item.get_closest_marker("macos_only"):
            if not is_macos:
                item.add_marker(pytest.mark.skip(reason="macOS-only test"))

        if item.get_closest_marker("linux_only"):
            if not is_linux:
                item.add_marker(pytest.mark.skip(reason="Linux-only test"))


# ════════════════════════════════════════════════════════════════════════════
# ANSI Stripping Utilities
# ════════════════════════════════════════════════════════════════════════════


def _remove_ansi_codes(text: str) -> str:
    """Return text stripped of ANSI escape sequences.

    Tests compare human-readable CLI output; stripping colour codes keeps
    assertions stable across environments.
    """
    return ANSI_ESCAPE_PATTERN.sub("", text)


# ════════════════════════════════════════════════════════════════════════════
# CLI Configuration State Management
# ════════════════════════════════════════════════════════════════════════════


def _snapshot_cli_config() -> dict[str, object]:
    """Capture every attribute from lib_cli_exit_tools.config.

    Tests toggle traceback behaviour; keeping a snapshot lets fixtures
    restore the configuration after each run.
    """
    return {name: getattr(lib_cli_exit_tools.config, name) for name in CONFIG_FIELDS}


def _restore_cli_config(snapshot: dict[str, object]) -> None:
    """Reapply the previously captured CLI configuration.

    Ensures global state looks untouched to subsequent tests.
    """
    for name, value in snapshot.items():
        setattr(lib_cli_exit_tools.config, name, value)


# ════════════════════════════════════════════════════════════════════════════
# Shared Fixtures
# ════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def cli_runner() -> CliRunner:
    """Provide a fresh CliRunner per test."""
    return CliRunner()


@pytest.fixture
def strip_ansi() -> Callable[[str], str]:
    """Return a helper that strips ANSI escape sequences from a string."""
    return _remove_ansi_codes


@pytest.fixture
def preserve_traceback_state() -> Iterator[None]:
    """Snapshot and restore the entire lib_cli_exit_tools configuration."""
    snapshot = _snapshot_cli_config()
    try:
        yield
    finally:
        _restore_cli_config(snapshot)


@pytest.fixture
def isolated_traceback_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """Reset traceback flags to a known baseline before each test."""
    lib_cli_exit_tools.reset_config()
    monkeypatch.setattr(lib_cli_exit_tools.config, "traceback", False, raising=False)
    monkeypatch.setattr(lib_cli_exit_tools.config, "traceback_force_color", False, raising=False)


@pytest.fixture
def testdata_dir() -> Path:
    """Provide the path to the testdata directory."""
    return TESTDATA_DIR


@pytest.fixture
def pyproject_files(testdata_dir: Path) -> list[Path]:
    """Provide all pyproject.toml test files from all subdirectories."""
    return list(testdata_dir.glob("*/pyproject_*.toml"))
