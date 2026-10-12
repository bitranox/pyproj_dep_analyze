"""Digit-only .env values reach every text setting as the text the operator wrote.

lib_layered_config's dotenv and environment layers turn an unquoted value into an int whenever
that number reads back as the same text (``123456`` stays ``123456``). A text setting must
therefore accept such a number and keep its digits; otherwise a numeric token or service name in
an ordinary ``.env`` line stops the program.

These tests load a real ``.env`` through the real loader, so a change in the library's coercion
shows up here rather than on a deployment.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from pydantic import ValidationError

from pyproj_dep_analyze.config import get_analyzer_settings, get_config
from pyproj_dep_analyze.logging_setup import (
    _build_runtime_config,  # pyright: ignore[reportPrivateUsage]
)

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path


@pytest.fixture
def dotenv_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    """A working directory whose ``.env`` the loader discovers, with a fresh config cache."""
    for name in ("GITHUB_TOKEN", "TIMEOUT", "CONCURRENCY"):
        monkeypatch.delenv(f"PYPROJ_DEP_ANALYZE_{name}", raising=False)
    monkeypatch.chdir(tmp_path)
    get_config.cache_clear()
    yield tmp_path
    get_config.cache_clear()


def _write_dotenv(directory: Path, *lines: str) -> None:
    (directory / ".env").write_text("\n".join(lines) + "\n", encoding="utf-8")


@pytest.mark.os_agnostic
def test_digit_only_github_token_reaches_the_analyzer_settings_as_its_text(dotenv_dir: Path) -> None:
    _write_dotenv(dotenv_dir, "ANALYZER__GITHUB_TOKEN=123456")
    # Premise: the library hands the value over as a number. Without it the test proves nothing.
    assert isinstance(get_config().get("analyzer", {})["github_token"], int)

    assert get_analyzer_settings().github_token == "123456"


@pytest.mark.os_agnostic
@pytest.mark.parametrize("attr", ["service", "environment"])
def test_digit_only_logging_value_reaches_the_runtime_config_as_its_text(dotenv_dir: Path, attr: str) -> None:
    _write_dotenv(dotenv_dir, f"LIB_LOG_RICH__{attr.upper()}=4711")
    assert isinstance(get_config().get("lib_log_rich", {})[attr], int)

    assert getattr(_build_runtime_config(), attr) == "4711"


@pytest.mark.os_agnostic
def test_numeric_settings_still_read_as_numbers(dotenv_dir: Path) -> None:
    _write_dotenv(dotenv_dir, "ANALYZER__TIMEOUT=45.5", "ANALYZER__CONCURRENCY=7")

    settings = get_analyzer_settings()

    assert (settings.timeout, settings.concurrency) == (45.5, 7)


@pytest.mark.os_agnostic
def test_a_non_numeric_concurrency_is_still_refused(dotenv_dir: Path) -> None:
    _write_dotenv(dotenv_dir, "ANALYZER__CONCURRENCY=abc")

    with pytest.raises(ValidationError):
        get_analyzer_settings()
