"""Behavior layer stories: each function speaks one truth.

The behaviors module houses domain functions that define what the
application does. These tests verify each behavior's contract in
isolation, using real streams and actual outputs.
"""

from __future__ import annotations

from dataclasses import dataclass
from io import StringIO

import pytest

from pyproj_dep_analyze import behaviors


# ════════════════════════════════════════════════════════════════════════════
# emit_greeting: The canonical Hello World
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.os_agnostic
def test_emit_greeting_writes_hello_world_to_stream() -> None:
    buffer = StringIO()

    behaviors.emit_greeting(stream=buffer)

    assert buffer.getvalue() == "Hello World\n"


@pytest.mark.os_agnostic
def test_emit_greeting_defaults_to_stdout(capsys: pytest.CaptureFixture[str]) -> None:
    behaviors.emit_greeting()

    captured = capsys.readouterr()

    assert captured.out == "Hello World\n"


@pytest.mark.os_agnostic
def test_emit_greeting_does_not_write_to_stderr(capsys: pytest.CaptureFixture[str]) -> None:
    behaviors.emit_greeting()

    captured = capsys.readouterr()

    assert captured.err == ""


@pytest.mark.os_agnostic
def test_emit_greeting_flushes_stream_when_flush_is_available() -> None:
    @dataclass
    class TrackingStream:
        lines: list[str]
        flushed: bool = False

        def write(self, text: str) -> None:
            self.lines.append(text)

        def flush(self) -> None:
            self.flushed = True

    stream = TrackingStream(lines=[])

    behaviors.emit_greeting(stream=stream)  # type: ignore[arg-type]

    assert stream.flushed is True


@pytest.mark.os_agnostic
def test_emit_greeting_writes_exactly_one_line() -> None:
    @dataclass
    class CountingStream:
        write_count: int = 0

        def write(self, text: str) -> None:
            self.write_count += 1

        def flush(self) -> None:
            pass

    stream = CountingStream()

    behaviors.emit_greeting(stream=stream)  # type: ignore[arg-type]

    assert stream.write_count == 1


# ════════════════════════════════════════════════════════════════════════════
# raise_intentional_failure: The controlled explosion
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.os_agnostic
def test_raise_intentional_failure_raises_runtime_error() -> None:
    with pytest.raises(RuntimeError):
        behaviors.raise_intentional_failure()


@pytest.mark.os_agnostic
def test_raise_intentional_failure_includes_expected_message() -> None:
    with pytest.raises(RuntimeError, match="I should fail"):
        behaviors.raise_intentional_failure()


# ════════════════════════════════════════════════════════════════════════════
# noop_main: The silent placeholder
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.os_agnostic
def test_noop_main_returns_none() -> None:
    result = behaviors.noop_main()

    assert result is None


@pytest.mark.os_agnostic
def test_noop_main_has_no_side_effects(capsys: pytest.CaptureFixture[str]) -> None:
    behaviors.noop_main()

    captured = capsys.readouterr()

    assert captured.out == ""
    assert captured.err == ""
