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
from dataclasses import fields
from pathlib import Path
from typing import TYPE_CHECKING

import lib_cli_exit_tools
import pytest
from click.testing import CliRunner

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

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
        if item.get_closest_marker("windows_only") and not is_windows:
            item.add_marker(pytest.mark.skip(reason="Windows-only test"))

        if item.get_closest_marker("posix_only") and not is_posix:
            item.add_marker(pytest.mark.skip(reason="POSIX-only test"))

        if item.get_closest_marker("macos_only") and not is_macos:
            item.add_marker(pytest.mark.skip(reason="macOS-only test"))

        if item.get_closest_marker("linux_only") and not is_linux:
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


def _layer_config_file(target: str, redirected_root: Path) -> Path:
    """Return where ``target``'s ``config.toml`` lives under ``redirected_root``, its directory created.

    The location is asked of lib_layered_config, which shares it between its deploy and its reader,
    because the layout under the root differs per OS.
    """
    from lib_layered_config import deploy_config_paths

    from pyproj_dep_analyze import __init__conf__
    from pyproj_dep_analyze.config import get_default_config_path

    paths = deploy_config_paths(
        get_default_config_path(),
        vendor=__init__conf__.LAYEREDCONF_VENDOR,
        app=__init__conf__.LAYEREDCONF_APP,
        slug=__init__conf__.LAYEREDCONF_SLUG,
        targets=[target],
    )
    config_file = next(path for path in paths if path.name == "config.toml")
    # Refuse before anything writes: without the redirect this is a real system or user directory,
    # and the elevated Windows runner would let a write through.
    assert config_file.is_relative_to(redirected_root.resolve()), config_file
    config_file.parent.mkdir(parents=True)
    return config_file


@pytest.fixture
def app_layer_config_file(system_layers_in_tmp_path: Path) -> Path:
    """Return where the app layer's ``config.toml`` lives under the redirect, its directory created."""
    return _layer_config_file("app", system_layers_in_tmp_path)


@pytest.fixture
def user_layer_config_file(user_layer_in_tmp_path: Path) -> Path:
    """Return where the user layer's ``config.toml`` lives under the redirect, its directory created."""
    return _layer_config_file("user", user_layer_in_tmp_path)


@pytest.fixture
def testdata_dir() -> Path:
    """Provide the path to the testdata directory."""
    return TESTDATA_DIR


@pytest.fixture
def pyproject_files(testdata_dir: Path) -> list[Path]:
    """Provide all pyproject.toml test files from all subdirectories."""
    return list(testdata_dir.glob("*/pyproject_*.toml"))


#: Which platforms each ``os_*`` marker lets a test run on. Registering a marker in pyproject only
#: silences pytest's unknown-marker warning; without this table a marked test runs everywhere.
_PLATFORM_MARKERS: dict[str, Callable[[str], bool]] = {
    "os_windows": lambda platform: platform == "win32",
    "os_macos": lambda platform: platform == "darwin",
    "os_linux": lambda platform: platform.startswith("linux"),
    "os_posix": lambda platform: platform != "win32",
}


def pytest_runtest_setup(item: pytest.Item) -> None:
    """Skip a test whose ``os_*`` marker names a platform other than the running one."""
    for name, runs_on in _PLATFORM_MARKERS.items():
        if item.get_closest_marker(name) is not None and not runs_on(sys.platform):
            pytest.skip(f"marked {name}; this is {sys.platform}")
