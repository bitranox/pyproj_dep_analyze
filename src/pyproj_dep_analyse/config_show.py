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
"""

from __future__ import annotations

import json
from typing import Any, cast

import click

from .config import get_config


def _format_value(value: Any) -> str:
    """Format a configuration value for human-readable display."""
    if isinstance(value, (list, dict)):
        return json.dumps(value)
    if isinstance(value, str):
        return f'"{value}"'
    return str(value)


def _echo_section_items(section_data: dict[str, Any]) -> None:
    """Echo key-value pairs from a configuration section."""
    for key, value in section_data.items():
        click.echo(f"  {key} = {_format_value(value)}")


def _display_section_human(section_name: str, section_data: Any) -> None:
    """Display a single configuration section in human-readable format."""
    click.echo(f"\n[{section_name}]")
    if isinstance(section_data, dict):
        dict_data = cast(dict[str, Any], section_data)
        _echo_section_items(dict_data)
    else:
        click.echo(f"  {section_data}")


def _display_json_output(config: Any, section: str | None) -> None:
    """Display configuration in JSON format."""
    if section:
        section_data = config.get(section, default={})
        if section_data:
            click.echo(json.dumps({section: section_data}, indent=2))
        else:
            click.echo(f"Section '{section}' not found or empty", err=True)
            raise SystemExit(1)
    else:
        click.echo(config.to_json(indent=2))


def _display_human_output(config: Any, section: str | None) -> None:
    """Display configuration in human-readable format."""
    if section:
        section_data = config.get(section, default={})
        if not section_data:
            click.echo(f"Section '{section}' not found or empty", err=True)
            raise SystemExit(1)
        _display_section_human(section, section_data)
    else:
        data: dict[str, Any] = config.as_dict()
        for section_name in data:
            _display_section_human(section_name, data[section_name])


def display_config(*, format: str = "human", section: str | None = None) -> None:
    """Display the current merged configuration from all sources.

    Users need visibility into the effective configuration loaded from
    defaults, app configs, host configs, user configs, .env files, and
    environment variables.

    Loads configuration via get_config() and outputs it in the requested
    format. Supports filtering to a specific section and both human-readable
    and JSON output formats.

    Args:
        format: Output format: "human" for TOML-like display or "json" for JSON.
            Defaults to "human".
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
          service = "pyproj_dep_analyse"
          environment = "prod"

        >>> display_config(format="json")  # doctest: +SKIP
        {
          "lib_log_rich": {
            "service": "pyproj_dep_analyse",
            "environment": "prod"
          }
        }
    """
    config = get_config()

    if format.lower() == "json":
        _display_json_output(config, section)
    else:
        _display_human_output(config, section)


__all__ = [
    "display_config",
]
