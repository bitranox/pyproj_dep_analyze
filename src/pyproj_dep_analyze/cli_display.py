"""CLI display helpers for formatting and presenting analysis results.

Purpose
-------
Encapsulate all output formatting logic for the CLI analyze command.
Separates presentation concerns from command orchestration in cli.py.

Contents
--------
* :func:`display_summary` - Display analysis summary statistics
* :func:`display_table` - Display results as formatted table with summary
* :func:`display_json` - Display results as JSON output
* :func:`display_analysis_results` - Main dispatcher for result display

System Role
-----------
Presentation layer for CLI output. Called by cli.py command handlers
to format and display analysis results in various formats.
"""

from __future__ import annotations

import json
from pathlib import Path

import click

from .models import Action, AnalysisResult, OutdatedEntry, OutputFormat


def display_summary(result: AnalysisResult) -> None:
    """Display a summary of analysis results.

    Args:
        result: The analysis result to summarize.
    """
    separator = "=" * 60
    click.echo(f"\n{separator}")
    click.echo("DEPENDENCY ANALYSIS SUMMARY")
    click.echo(separator)
    click.echo(f"Python versions analyzed: {', '.join(result.python_versions)}")
    click.echo(f"Total unique dependencies: {result.total_dependencies}")
    click.echo(f"Total entries (deps × versions): {len(result.entries)}")
    click.echo("-" * 60)
    click.echo(f"  Updates available: {result.update_count}")
    click.echo(f"  Deletions recommended: {result.delete_count}")
    click.echo(f"  Manual check required: {result.check_manually_count}")
    click.echo(separator)


def _display_updates_section(updates: list[OutdatedEntry]) -> None:
    """Display the updates available section.

    Args:
        updates: List of entries with UPDATE action.
    """
    if not updates:
        return
    click.echo("\nUPDATES AVAILABLE:")
    click.echo("-" * 60)
    for entry in updates[:20]:
        click.echo(f"  {entry.package} (py{entry.python_version}): {entry.current_version} -> {entry.latest_version}")
    if len(updates) > 20:
        click.echo(f"  ... and {len(updates) - 20} more")


def _display_manual_section(manual: list[OutdatedEntry]) -> None:
    """Display the manual check required section.

    Args:
        manual: List of entries with CHECK_MANUALLY action.
    """
    if not manual:
        return
    click.echo("\nMANUAL CHECK REQUIRED:")
    click.echo("-" * 60)
    for entry in manual[:10]:
        click.echo(f"  {entry.package} (py{entry.python_version})")
    if len(manual) > 10:
        click.echo(f"  ... and {len(manual) - 10} more")


def display_table(result: AnalysisResult) -> None:
    """Display results as a formatted table with summary.

    Args:
        result: The analysis result to display.
    """
    display_summary(result)

    updates = [e for e in result.entries if e.action == Action.UPDATE]
    manual = [e for e in result.entries if e.action == Action.CHECK_MANUALLY]

    _display_updates_section(updates)
    _display_manual_section(manual)


def display_json(result: AnalysisResult) -> None:
    """Display results as JSON to stdout.

    Args:
        result: The analysis result to display as JSON.
    """
    data = [entry.model_dump() for entry in result.entries]
    click.echo(json.dumps(data, indent=2))


def display_analysis_results(result: AnalysisResult, output_format: OutputFormat) -> None:
    """Display analysis results in the specified format.

    Args:
        result: The analysis result to display.
        output_format: Output format enum value.

    Raises:
        ValueError: If output_format is not a recognized OutputFormat value.
    """
    if output_format == OutputFormat.SUMMARY:
        display_summary(result)
    elif output_format == OutputFormat.TABLE:
        display_table(result)
    elif output_format == OutputFormat.JSON:
        display_json(result)
    else:
        # Exhaustive check - should never reach here
        raise ValueError(f"Unknown output format: {output_format}")


def report_output_written(entries_count: int, output_path: Path) -> None:
    """Report that output was written to a file.

    Args:
        entries_count: Number of entries written.
        output_path: Path where the file was written.
    """
    click.echo(f"\nWrote {entries_count} entries to {output_path}")


__all__ = [
    "OutputFormat",
    "display_analysis_results",
    "display_json",
    "display_summary",
    "display_table",
    "report_output_written",
]
