"""Configuration display functionality for CLI config command.

Purpose
-------
Provides the business logic for displaying merged configuration from all
sources in human-readable or JSON format. Keeps CLI layer thin by handling
all formatting and display logic here.

Contents
--------
* :func:`display_config` – displays configuration in requested format

System Role
-----------
Lives in the behaviors layer. The CLI command delegates to this module for
all configuration display logic, keeping presentation concerns separate from
command-line argument parsing.

Architecture Notes
------------------
This module acts as an adapter layer between our typed codebase and the
external lib_layered_config library. The lib_layered_config.Config class
is Mapping-like by design, returning dict-like structures. This is an
acceptable boundary where dict handling is pragmatic and contained.

The dict usage here does NOT violate data architecture principles because:
1. This is at the external library boundary (adapter pattern)
2. Config is a well-typed Mapping from lib_layered_config
3. The dict handling is contained to this module only
4. No untyped dicts leak to the rest of the codebase
"""

from __future__ import annotations

import json
from typing import Any, Mapping, Protocol

import click

from .config import get_config
from .models import ConfigFormat

# Type alias for configuration values returned by lib_layered_config
# This represents the external library's data format at the boundary
ConfigValue = str | int | float | bool | list[Any] | dict[str, Any] | None


class ConfigMapping(Protocol):
    """Protocol for lib_layered_config.Config Mapping interface.

    Defines the minimal interface we need from the external Config class.
    This protocol isolates us from implementation details of lib_layered_config.
    """

    def to_json(self, *, indent: int | None = None) -> str:
        """Export config as JSON string."""
        ...

    def get(self, key: str, default: Any = None) -> Any:
        """Get a config value by key."""
        ...

    def __getitem__(self, key: str) -> Any:
        """Get a config value by key using subscript notation."""
        ...

    def __iter__(self) -> Any:
        """Iterate over config keys."""
        ...


def _format_value(value: ConfigValue) -> str:
    """Format a configuration value for human-readable display.

    Args:
        value: Configuration value from lib_layered_config.

    Returns:
        Formatted string representation.
    """
    if isinstance(value, (list, dict)):
        return json.dumps(value)
    if isinstance(value, str):
        return f'"{value}"'
    return str(value)


def _echo_section_items(section_data: Mapping[str, Any]) -> None:
    """Echo key-value pairs from a configuration section.

    Args:
        section_data: Mapping of configuration keys to values.

    Side Effects:
        Writes formatted key-value pairs to stdout via click.echo().
    """
    for key, value in section_data.items():
        click.echo(f"  {key} = {_format_value(value)}")


def _display_section_human(section_name: str, section_data: ConfigValue) -> None:
    """Display a single configuration section in human-readable format.

    Args:
        section_name: Name of the configuration section.
        section_data: Section value (typically a dict/Mapping or scalar).

    Side Effects:
        Writes formatted section to stdout via click.echo().

    Note:
        Accepts ConfigValue (which includes Mapping types) from the external
        lib_layered_config library. This boundary handling is intentional.
    """
    click.echo(f"\n[{section_name}]")
    if isinstance(section_data, Mapping):
        _echo_section_items(section_data)
    else:
        click.echo(f"  {section_data}")


def _display_json_output(config: ConfigMapping, section: str | None) -> None:
    """Display configuration in JSON format.

    Args:
        config: Configuration mapping from lib_layered_config.
        section: Optional section name to filter output.

    Side Effects:
        Writes JSON to stdout via click.echo().
        Raises SystemExit(1) if requested section doesn't exist.

    Note:
        Uses the external library's to_json() method when displaying all
        configuration, ensuring proper serialization of internal structures.
    """
    if section:
        section_data = config.get(section, default={})
        if section_data:
            click.echo(json.dumps({section: section_data}, indent=2))
        else:
            click.echo(f"Section '{section}' not found or empty", err=True)
            raise SystemExit(1)
    else:
        click.echo(config.to_json(indent=2))


def _display_human_output(config: ConfigMapping, section: str | None) -> None:
    """Display configuration in human-readable format.

    Args:
        config: Configuration mapping from lib_layered_config.
        section: Optional section name to filter output.

    Side Effects:
        Writes formatted configuration to stdout via click.echo().
        Raises SystemExit(1) if requested section doesn't exist.

    Note:
        Iterates over the Mapping interface provided by lib_layered_config.
        This is the appropriate way to traverse external Mapping-like objects.
    """
    if section:
        section_data = config.get(section, default={})
        if not section_data:
            click.echo(f"Section '{section}' not found or empty", err=True)
            raise SystemExit(1)
        _display_section_human(section, section_data)
    else:
        for section_name in config:
            _display_section_human(section_name, config[section_name])


def display_config(*, format: ConfigFormat = ConfigFormat.HUMAN, section: str | None = None) -> None:
    """Display the current merged configuration from all sources.

    Users need visibility into the effective configuration loaded from
    defaults, app configs, host configs, user configs, .env files, and
    environment variables.

    Loads configuration via get_config() and outputs it in the requested
    format. Supports filtering to a specific section and both human-readable
    and JSON output formats.

    Args:
        format: Output format enum value. Defaults to ConfigFormat.HUMAN.
        section: Optional section name to display only that section. When None,
            displays all configuration.

    Side Effects:
        Writes formatted configuration to stdout via click.echo().
        Raises SystemExit(1) if requested section doesn't exist.

    Note:
        The human-readable format mimics TOML syntax for consistency with the
        configuration file format. JSON format provides machine-readable output
        suitable for parsing by other tools.

    Example:
        >>> display_config()  # doctest: +SKIP
        [lib_log_rich]
          service = "pyproj_dep_analyze"
          environment = "prod"

        >>> display_config(format=ConfigFormat.JSON)  # doctest: +SKIP
        {
          "lib_log_rich": {
            "service": "pyproj_dep_analyze",
            "environment": "prod"
          }
        }
    """
    config = get_config()

    if format == ConfigFormat.JSON:
        _display_json_output(config, section)
    else:
        _display_human_output(config, section)


__all__ = [
    "ConfigFormat",
    "display_config",
]
