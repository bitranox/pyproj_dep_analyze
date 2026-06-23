"""Configuration display stories: settings become visible.

The config_show module displays merged configuration in human-readable
or JSON format. These tests verify the formatting and output behavior
using real configuration data where possible.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from pyproj_dep_analyze import config_show as show_mod
from pyproj_dep_analyze.config_show import display_config
from pyproj_dep_analyze.models import ConfigFormat


# ════════════════════════════════════════════════════════════════════════════
# _format_value: The value formatter
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.os_agnostic
def test_format_value_quotes_strings() -> None:
    result = show_mod._format_value("hello")  # pyright: ignore[reportPrivateUsage]

    assert result == '"hello"'


@pytest.mark.os_agnostic
def test_format_value_serializes_lists_as_json() -> None:
    result = show_mod._format_value([1, 2, 3])  # pyright: ignore[reportPrivateUsage]

    assert result == "[1, 2, 3]"


@pytest.mark.os_agnostic
def test_format_value_serializes_dicts_as_json() -> None:
    result = show_mod._format_value({"key": "value"})  # pyright: ignore[reportPrivateUsage]

    assert result == '{"key": "value"}'


@pytest.mark.os_agnostic
def test_format_value_converts_numbers_to_string() -> None:
    result = show_mod._format_value(42)  # pyright: ignore[reportPrivateUsage]

    assert result == "42"


@pytest.mark.os_agnostic
def test_format_value_converts_floats_to_string() -> None:
    result = show_mod._format_value(3.14)  # pyright: ignore[reportPrivateUsage]

    assert result == "3.14"


@pytest.mark.os_agnostic
def test_format_value_converts_booleans_to_string() -> None:
    assert show_mod._format_value(True) == "True"  # pyright: ignore[reportPrivateUsage]
    assert show_mod._format_value(False) == "False"  # pyright: ignore[reportPrivateUsage]


# ════════════════════════════════════════════════════════════════════════════
# display_config: The main display function
# ════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def mock_config(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Provide a mock configuration with predictable data."""
    test_data = {
        "lib_log_rich": {
            "service": "test-service",
            "environment": "test",
        },
        "analyzer": {
            "timeout": 30.0,
            "concurrency": 10,
        },
    }

    class FakeConfig:
        def as_dict(self) -> dict[str, Any]:
            return test_data

        def to_json(self, *, indent: int | None = None) -> str:
            return json.dumps(test_data, indent=indent)

        def get(self, key: str, default: Any = None) -> Any:
            return test_data.get(key, default)

        def __iter__(self):
            return iter(test_data)

        def __getitem__(self, key: str) -> Any:
            return test_data[key]

    def fake_get_config(**kwargs: Any) -> FakeConfig:
        return FakeConfig()

    monkeypatch.setattr(show_mod, "get_config", fake_get_config)

    return test_data


@pytest.mark.os_agnostic
def test_display_config_exists() -> None:
    assert callable(display_config)


@pytest.mark.os_agnostic
def test_display_config_human_format_shows_sections(
    mock_config: dict[str, Any],
    capsys: pytest.CaptureFixture[str],
) -> None:
    display_config(format=ConfigFormat.HUMAN)

    captured = capsys.readouterr()

    assert "[lib_log_rich]" in captured.out
    assert "[analyzer]" in captured.out


@pytest.mark.os_agnostic
def test_display_config_human_format_shows_values(
    mock_config: dict[str, Any],
    capsys: pytest.CaptureFixture[str],
) -> None:
    display_config(format=ConfigFormat.HUMAN)

    captured = capsys.readouterr()

    assert "test-service" in captured.out
    assert "30.0" in captured.out


@pytest.mark.os_agnostic
def test_display_config_json_format_outputs_valid_json(
    mock_config: dict[str, Any],
    capsys: pytest.CaptureFixture[str],
) -> None:
    display_config(format=ConfigFormat.JSON)

    captured = capsys.readouterr()
    parsed = json.loads(captured.out)

    assert isinstance(parsed, dict)


@pytest.mark.os_agnostic
def test_display_config_json_format_includes_all_sections(
    mock_config: dict[str, Any],
    capsys: pytest.CaptureFixture[str],
) -> None:
    display_config(format=ConfigFormat.JSON)

    captured = capsys.readouterr()
    parsed = json.loads(captured.out)

    assert "lib_log_rich" in parsed
    assert "analyzer" in parsed


@pytest.mark.os_agnostic
def test_display_config_with_section_filter_shows_only_that_section(
    mock_config: dict[str, Any],
    capsys: pytest.CaptureFixture[str],
) -> None:
    display_config(format=ConfigFormat.HUMAN, section="lib_log_rich")

    captured = capsys.readouterr()

    assert "[lib_log_rich]" in captured.out
    assert "[analyzer]" not in captured.out


@pytest.mark.os_agnostic
def test_display_config_json_with_section_filter(
    mock_config: dict[str, Any],
    capsys: pytest.CaptureFixture[str],
) -> None:
    display_config(format=ConfigFormat.JSON, section="analyzer")

    captured = capsys.readouterr()
    parsed = json.loads(captured.out)

    assert "analyzer" in parsed
    assert "lib_log_rich" not in parsed


@pytest.mark.os_agnostic
def test_display_config_with_missing_section_raises_system_exit(
    mock_config: dict[str, Any],
) -> None:
    with pytest.raises(SystemExit) as exc:
        display_config(format=ConfigFormat.HUMAN, section="nonexistent")

    assert exc.value.code == 1


@pytest.mark.os_agnostic
def test_display_config_with_missing_section_prints_error(
    mock_config: dict[str, Any],
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit):
        display_config(format=ConfigFormat.HUMAN, section="nonexistent")

    captured = capsys.readouterr()

    assert "not found or empty" in captured.err


@pytest.mark.os_agnostic
def test_display_config_json_with_missing_section_raises_system_exit(
    mock_config: dict[str, Any],
) -> None:
    with pytest.raises(SystemExit) as exc:
        display_config(format=ConfigFormat.JSON, section="nonexistent")

    assert exc.value.code == 1


@pytest.mark.os_agnostic
def test_display_config_defaults_to_human_format(
    mock_config: dict[str, Any],
    capsys: pytest.CaptureFixture[str],
) -> None:
    display_config()

    captured = capsys.readouterr()

    assert "[" in captured.out  # Section headers have brackets


@pytest.mark.os_agnostic
def test_display_config_accepts_config_format_enum(
    mock_config: dict[str, Any],
    capsys: pytest.CaptureFixture[str],
) -> None:
    display_config(format=ConfigFormat.JSON)

    captured = capsys.readouterr()
    parsed = json.loads(captured.out)

    assert isinstance(parsed, dict)


# ════════════════════════════════════════════════════════════════════════════
# Module Exports: __all__ completeness
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.os_agnostic
def test_module_exports_display_config() -> None:
    assert "display_config" in show_mod.__all__
