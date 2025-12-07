"""Package metadata stories: each value speaks its purpose.

The __init__conf__ module defines the package's identity: version, name,
commands, and URLs. These tests verify that metadata is accessible and
correctly structured.
"""

from __future__ import annotations

import pytest

from pyproj_dep_analyze import __init__conf__


# ════════════════════════════════════════════════════════════════════════════
# Version: The semantic identifier
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.os_agnostic
def test_version_exists() -> None:
    assert hasattr(__init__conf__, "version")


@pytest.mark.os_agnostic
def test_version_is_string() -> None:
    assert isinstance(__init__conf__.version, str)


@pytest.mark.os_agnostic
def test_version_follows_semver_structure() -> None:
    parts = __init__conf__.version.split(".")

    assert len(parts) >= 2
    assert parts[0].isdigit()
    assert parts[1].isdigit()


@pytest.mark.os_agnostic
def test_version_is_not_empty() -> None:
    assert len(__init__conf__.version) > 0


# ════════════════════════════════════════════════════════════════════════════
# Name: The package identifier
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.os_agnostic
def test_name_exists() -> None:
    assert hasattr(__init__conf__, "name")


@pytest.mark.os_agnostic
def test_name_is_string() -> None:
    assert isinstance(__init__conf__.name, str)


@pytest.mark.os_agnostic
def test_name_is_not_empty() -> None:
    assert len(__init__conf__.name) > 0


@pytest.mark.os_agnostic
def test_name_is_expected_value() -> None:
    assert __init__conf__.name == "pyproj_dep_analyze"


# ════════════════════════════════════════════════════════════════════════════
# Shell Command: The CLI entry point name
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.os_agnostic
def test_shell_command_exists() -> None:
    assert hasattr(__init__conf__, "shell_command")


@pytest.mark.os_agnostic
def test_shell_command_is_string() -> None:
    assert isinstance(__init__conf__.shell_command, str)


@pytest.mark.os_agnostic
def test_shell_command_is_not_empty() -> None:
    assert len(__init__conf__.shell_command) > 0


@pytest.mark.os_agnostic
def test_shell_command_is_expected_value() -> None:
    assert __init__conf__.shell_command == "pyproj-dep-analyze"


# ════════════════════════════════════════════════════════════════════════════
# Title: The human-readable name
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.os_agnostic
def test_title_exists() -> None:
    assert hasattr(__init__conf__, "title")


@pytest.mark.os_agnostic
def test_title_is_string() -> None:
    assert isinstance(__init__conf__.title, str)


@pytest.mark.os_agnostic
def test_title_is_not_empty() -> None:
    assert len(__init__conf__.title) > 0


# ════════════════════════════════════════════════════════════════════════════
# Homepage: The project URL
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.os_agnostic
def test_homepage_exists() -> None:
    assert hasattr(__init__conf__, "homepage")


@pytest.mark.os_agnostic
def test_homepage_is_string() -> None:
    assert isinstance(__init__conf__.homepage, str)


@pytest.mark.os_agnostic
def test_homepage_starts_with_https() -> None:
    assert __init__conf__.homepage.startswith("https://")


@pytest.mark.os_agnostic
def test_homepage_contains_github() -> None:
    assert "github" in __init__conf__.homepage.lower()


# ════════════════════════════════════════════════════════════════════════════
# Author: The package maintainer
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.os_agnostic
def test_author_exists() -> None:
    assert hasattr(__init__conf__, "author")


@pytest.mark.os_agnostic
def test_author_is_string() -> None:
    assert isinstance(__init__conf__.author, str)


@pytest.mark.os_agnostic
def test_author_is_not_empty() -> None:
    assert len(__init__conf__.author) > 0


# ════════════════════════════════════════════════════════════════════════════
# Author Email: Contact information
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.os_agnostic
def test_author_email_exists() -> None:
    assert hasattr(__init__conf__, "author_email")


@pytest.mark.os_agnostic
def test_author_email_is_string() -> None:
    assert isinstance(__init__conf__.author_email, str)


@pytest.mark.os_agnostic
def test_author_email_contains_at_symbol() -> None:
    assert "@" in __init__conf__.author_email


# ════════════════════════════════════════════════════════════════════════════
# Layered Config Identifiers
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.os_agnostic
def test_layeredconf_vendor_exists() -> None:
    assert hasattr(__init__conf__, "LAYEREDCONF_VENDOR")


@pytest.mark.os_agnostic
def test_layeredconf_app_exists() -> None:
    assert hasattr(__init__conf__, "LAYEREDCONF_APP")


@pytest.mark.os_agnostic
def test_layeredconf_slug_exists() -> None:
    assert hasattr(__init__conf__, "LAYEREDCONF_SLUG")


@pytest.mark.os_agnostic
def test_layeredconf_slug_matches_shell_command() -> None:
    assert __init__conf__.LAYEREDCONF_SLUG == __init__conf__.shell_command


# ════════════════════════════════════════════════════════════════════════════
# print_info: The metadata display function
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.os_agnostic
def test_print_info_exists() -> None:
    assert hasattr(__init__conf__, "print_info")


@pytest.mark.os_agnostic
def test_print_info_is_callable() -> None:
    assert callable(__init__conf__.print_info)


@pytest.mark.os_agnostic
def test_print_info_outputs_package_name(capsys: pytest.CaptureFixture[str]) -> None:
    __init__conf__.print_info()

    captured = capsys.readouterr()

    assert __init__conf__.name in captured.out


@pytest.mark.os_agnostic
def test_print_info_outputs_version(capsys: pytest.CaptureFixture[str]) -> None:
    __init__conf__.print_info()

    captured = capsys.readouterr()

    assert __init__conf__.version in captured.out


@pytest.mark.os_agnostic
def test_print_info_outputs_author(capsys: pytest.CaptureFixture[str]) -> None:
    __init__conf__.print_info()

    captured = capsys.readouterr()

    assert __init__conf__.author in captured.out


@pytest.mark.os_agnostic
def test_print_info_outputs_homepage(capsys: pytest.CaptureFixture[str]) -> None:
    __init__conf__.print_info()

    captured = capsys.readouterr()

    assert __init__conf__.homepage in captured.out


@pytest.mark.os_agnostic
def test_print_info_outputs_shell_command(capsys: pytest.CaptureFixture[str]) -> None:
    __init__conf__.print_info()

    captured = capsys.readouterr()

    assert __init__conf__.shell_command in captured.out


@pytest.mark.os_agnostic
def test_print_info_returns_none() -> None:
    result = __init__conf__.print_info()

    assert result is None
