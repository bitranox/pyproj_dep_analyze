"""CLI adapter wiring the behavior helpers into a rich-click interface.

Purpose
-------
Expose a stable command-line surface so tooling, documentation, and packaging
automation can be exercised while the richer logging helpers are being built.
By delegating to :mod:`pyproj_dep_analyze.behaviors` the transport stays
aligned with the Clean Code rules captured in
``docs/systemdesign/module_reference.md``.

Contents
--------
* :data:`CLICK_CONTEXT_SETTINGS` – shared Click settings ensuring consistent
  ``--help`` behavior across commands.
* :func:`apply_traceback_preferences` – helper that synchronises the shared
  traceback configuration flags.
* :func:`snapshot_traceback_state` / :func:`restore_traceback_state` – utilities
  for preserving and reapplying the global traceback preference.
* :func:`cli` – root command group wiring the global options.
* :func:`cli_main` – default action when no subcommand is provided.
* :func:`cli_info`, :func:`cli_hello`, :func:`cli_fail` – subcommands covering
  metadata printing, success path, and failure path.
* :func:`_record_traceback_choice`, :func:`_announce_traceback_choice` – persist
  traceback preferences across context and shared tooling.
* :func:`_invoke_cli`, :func:`_current_traceback_mode`, :func:`_traceback_limit`,
  :func:`_print_exception`, :func:`_run_cli_via_exit_tools` – isolate the error
  handling and delegation path.
* :func:`_restore_when_requested` – restores tracebacks when ``main`` finishes.
* :func:`main` – composition helper delegating to ``lib_cli_exit_tools`` while
  honouring the shared traceback preferences.

System Role
-----------
The CLI is the primary adapter for local development workflows; packaging
targets register the console script defined in :mod:`pyproj_dep_analyze.__init__conf__`.
Other transports (including ``python -m`` execution) reuse the same helpers so
behaviour remains consistent regardless of entry point.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from enum import Enum
from pathlib import Path
from typing import Any, Final

import lib_cli_exit_tools
import lib_log_rich.runtime
import rich_click as click
from click.core import ParameterSource
from pydantic import BaseModel, ConfigDict

from lib_layered_config.examples.deploy import DeployResult

from . import __init__conf__
from .analyzer import run_analysis, run_enriched_analysis, write_enriched_json, write_outdated_json
from .behaviors import emit_greeting, noop_main, raise_intentional_failure
from .cli_display import display_analysis_results, report_output_written
from .config import get_analyzer_settings
from .config_deploy import deploy_configuration
from .config_show import display_config
from .logging_setup import init_logging
from .models import ConfigFormat, DeploymentTarget, OutputFormat


class CliCommand(str, Enum):
    """CLI command identifiers for logging and tracing.

    Attributes:
        INFO: Display package metadata.
        HELLO: Success path demonstration.
        FAIL: Intentional failure test.
        CONFIG: Display configuration.
        ANALYZE: Analyze dependencies.
        ANALYZE_ENRICHED: Analyze with full metadata enrichment.
        CONFIG_DEPLOY: Deploy configuration files.
    """

    INFO = "cli-info"
    HELLO = "cli-hello"
    FAIL = "cli-fail"
    CONFIG = "cli-config"
    ANALYZE = "cli-analyze"
    ANALYZE_ENRICHED = "cli-analyze-enriched"
    CONFIG_DEPLOY = "cli-config-deploy"


#: Shared Click context flags so help output stays consistent across commands.
CLICK_CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}  # noqa: C408
#: Character budget used when printing truncated tracebacks.
TRACEBACK_SUMMARY_LIMIT: Final[int] = 500
#: Character budget used when verbose tracebacks are enabled.
TRACEBACK_VERBOSE_LIMIT: Final[int] = 10_000

logger = logging.getLogger(__name__)


class EnumChoice(click.ParamType):
    """Click parameter type that converts string choices to typed Enums.

    This type enforces data architecture by performing string-to-Enum conversion
    at the input boundary (CLI decorator level) rather than in function bodies.

    Attributes:
        name: Parameter type name for Click.
        enum_class: The Enum class to convert values to.

    Example:
        >>> from pyproj_dep_analyze.models import OutputFormat
        >>> param_type = EnumChoice(OutputFormat)
        >>> @click.option("--format", type=param_type, default=OutputFormat.TABLE.value)
        ... def cmd(format: OutputFormat):
        ...     # format is already an Enum, no conversion needed
        ...     pass
    """

    name = "enum_choice"

    def __init__(self, enum_class: type[Enum]) -> None:
        """Initialize the EnumChoice with a specific Enum class.

        Args:
            enum_class: The Enum class to convert string values to.
        """
        self.enum_class = enum_class
        self._choices = [e.value for e in enum_class]

    def get_metavar(self, param: click.Parameter, ctx: click.Context) -> str | None:
        """Return metavar string showing available choices.

        Args:
            param: Click parameter being processed.
            ctx: Click context for processing.

        Returns:
            Metavar string in format [choice1|choice2|...].
        """
        return f"[{'|'.join(self._choices)}]"

    def convert(
        self,
        value: Any,
        param: click.Parameter | None,
        ctx: click.Context | None,
    ) -> Enum:
        """Convert a string value to the target Enum.

        Args:
            value: Input value (string or already-converted Enum).
            param: Click parameter being processed.
            ctx: Click context for error reporting.

        Returns:
            Enum instance of the target class.

        Raises:
            click.BadParameter: If value cannot be converted to the Enum.
        """
        if isinstance(value, self.enum_class):
            return value
        try:
            normalized = value.lower() if isinstance(value, str) else value
            return self.enum_class(normalized)
        except ValueError:
            self.fail(
                f"Invalid choice: {value}. Choose from {', '.join(self._choices)}",
                param,
                ctx,
            )


class TracebackState(BaseModel):
    """Model for traceback configuration state.

    Attributes:
        enabled: Whether verbose tracebacks are enabled.
        force_color: Whether color output should be forced in tracebacks.
    """

    model_config = ConfigDict(frozen=True)

    enabled: bool = False
    force_color: bool = False


class ClickContextState(BaseModel):
    """Typed state for Click context object.

    Attributes:
        traceback: Whether verbose tracebacks were requested.
    """

    model_config = ConfigDict(frozen=True)

    traceback: bool = False


def apply_traceback_preferences(enabled: bool) -> None:
    """Synchronise shared traceback flags with the requested preference.

    ``lib_cli_exit_tools`` inspects global flags to decide whether tracebacks
    should be truncated and whether colour should be forced. Updating both
    attributes together ensures the ``--traceback`` flag behaves the same for
    console scripts and ``python -m`` execution.

    Args:
        enabled: ``True`` enables full tracebacks with colour. ``False`` restores
            the compact summary mode.

    Example:
        >>> apply_traceback_preferences(True)
        >>> bool(lib_cli_exit_tools.config.traceback)
        True
        >>> bool(lib_cli_exit_tools.config.traceback_force_color)
        True
    """
    lib_cli_exit_tools.config.traceback = bool(enabled)
    lib_cli_exit_tools.config.traceback_force_color = bool(enabled)


def snapshot_traceback_state() -> TracebackState:
    """Capture the current traceback configuration for later restoration.

    Returns:
        TracebackState model with current traceback configuration.

    Example:
        >>> snapshot = snapshot_traceback_state()
        >>> isinstance(snapshot, TracebackState)
        True
    """
    # Document: Using getattr with string literals is acceptable here as this is a
    # boundary with the external lib_cli_exit_tools library. We cannot control its
    # internal structure and must access its config attributes dynamically.
    return TracebackState(
        enabled=bool(getattr(lib_cli_exit_tools.config, "traceback", False)),
        force_color=bool(getattr(lib_cli_exit_tools.config, "traceback_force_color", False)),
    )


def restore_traceback_state(state: TracebackState) -> None:
    """Reapply a previously captured traceback configuration.

    Args:
        state: TracebackState model returned by :func:`snapshot_traceback_state`.

    Example:
        >>> prev = snapshot_traceback_state()
        >>> apply_traceback_preferences(True)
        >>> restore_traceback_state(prev)
        >>> snapshot_traceback_state() == prev
        True
    """
    lib_cli_exit_tools.config.traceback = bool(state.enabled)
    lib_cli_exit_tools.config.traceback_force_color = bool(state.force_color)


def _record_traceback_choice(ctx: click.Context, *, enabled: bool) -> None:
    """Remember the chosen traceback mode inside the Click context.

    Downstream commands need to know whether verbose tracebacks were
    requested so they can honour the user's preference without re-parsing
    flags. Ensures the context has a dict backing store and persists a
    typed ClickContextState model.

    Args:
        ctx: Click context associated with the current invocation.
        enabled: ``True`` when verbose tracebacks were requested; ``False`` otherwise.

    Side Effects:
        Mutates ``ctx.obj``.

    Note:
        Document: Click framework requires dict-based context storage via ctx.obj.
        We wrap the actual state in a typed ClickContextState model to maintain
        type safety while respecting the framework's API contract. This is an
        acceptable boundary pattern between framework requirements and type-safe code.
    """
    ctx.ensure_object(dict)
    ctx.obj["state"] = ClickContextState(traceback=enabled)


def _announce_traceback_choice(enabled: bool) -> None:
    """Keep ``lib_cli_exit_tools`` in sync with the selected traceback mode.

    ``lib_cli_exit_tools`` reads global configuration to decide how to print
    tracebacks; we mirror the user's choice into that configuration.

    Args:
        enabled: ``True`` when verbose tracebacks should be shown; ``False`` when
            the summary view is desired.

    Side Effects:
        Mutates ``lib_cli_exit_tools.config``.
    """
    apply_traceback_preferences(enabled)


def _no_subcommand_requested(ctx: click.Context) -> bool:
    """Return ``True`` when the invocation did not name a subcommand.

    The CLI defaults to calling ``noop_main`` when no subcommand appears; we
    need a readable predicate to capture that intent.

    Args:
        ctx: Click context describing the current CLI invocation.

    Returns:
        ``True`` when no subcommand was invoked; ``False`` otherwise.
    """
    return ctx.invoked_subcommand is None


def _invoke_cli(argv: Sequence[str] | None) -> int:
    """Ask ``lib_cli_exit_tools`` to execute the Click command.

    ``lib_cli_exit_tools`` normalises exit codes and exception handling; we
    centralise the call so tests can stub it cleanly.

    Args:
        argv: Optional sequence of command-line arguments. ``None`` delegates to
            ``sys.argv`` inside ``lib_cli_exit_tools``.

    Returns:
        Exit code returned by the CLI execution.
    """
    return lib_cli_exit_tools.run_cli(
        cli,
        argv=list(argv) if argv is not None else None,
        prog_name=__init__conf__.shell_command,
    )


def _current_traceback_mode() -> bool:
    """Return the global traceback preference as a boolean.

    Error handling logic needs to know whether verbose tracebacks are active
    so it can pick the right character budget and ensure colouring is
    consistent.

    Returns:
        ``True`` when verbose tracebacks are enabled; ``False`` otherwise.
    """
    # Document: Using getattr with string literals is acceptable here as this is a
    # boundary with the external lib_cli_exit_tools library.
    return bool(getattr(lib_cli_exit_tools.config, "traceback", False))


def _traceback_limit(tracebacks_enabled: bool, *, summary_limit: int, verbose_limit: int) -> int:
    """Return the character budget that matches the current traceback mode.

    Verbose tracebacks should show the full story while compact ones keep the
    terminal tidy. This helper makes that decision explicit.

    Args:
        tracebacks_enabled: ``True`` when verbose tracebacks are active.
        summary_limit: Character budget for truncated output.
        verbose_limit: Character budget for the full traceback.

    Returns:
        The applicable character limit.
    """
    return verbose_limit if tracebacks_enabled else summary_limit


def _print_exception(exc: BaseException, *, tracebacks_enabled: bool, length_limit: int) -> int:
    """Render the exception through ``lib_cli_exit_tools`` and return its exit code.

    All transports funnel errors through ``lib_cli_exit_tools`` so that exit
    codes and formatting stay consistent; this helper keeps the plumbing in
    one place.

    Args:
        exc: Exception raised by the CLI.
        tracebacks_enabled: ``True`` when verbose tracebacks should be shown.
        length_limit: Maximum number of characters to print.

    Returns:
        Exit code to surface to the shell.

    Side Effects:
        Writes the formatted exception to stderr via ``lib_cli_exit_tools``.
    """
    lib_cli_exit_tools.print_exception_message(
        trace_back=tracebacks_enabled,
        length_limit=length_limit,
    )
    return lib_cli_exit_tools.get_system_exit_code(exc)


def _traceback_option_requested(ctx: click.Context) -> bool:
    """Return ``True`` when the user explicitly requested ``--traceback``.

    Determines whether a no-command invocation should run the default
    behaviour or display the help screen.

    Args:
        ctx: Click context associated with the current invocation.

    Returns:
        ``True`` when the user provided ``--traceback`` or ``--no-traceback``;
        ``False`` when the default value is in effect.
    """
    # Document: Using string literal "traceback" is required here as it's the
    # parameter name registered with Click. This is the Click framework API contract.
    source = ctx.get_parameter_source("traceback")
    return source not in (ParameterSource.DEFAULT, None)


def _show_help(ctx: click.Context) -> None:
    """Render the command help to stdout."""
    click.echo(ctx.get_help())


def _run_cli_via_exit_tools(
    argv: Sequence[str] | None,
    *,
    summary_limit: int,
    verbose_limit: int,
) -> int:
    """Run the command while narrating the failure path with care.

    Consolidates the call to ``lib_cli_exit_tools`` so happy paths and error
    handling remain consistent across the application and tests.

    Args:
        argv: Optional sequence of CLI arguments.
        summary_limit: Character budget for truncated output.
        verbose_limit: Character budget for the full traceback.

    Returns:
        Exit code produced by the command.

    Side Effects:
        Delegates to ``lib_cli_exit_tools`` which may write to stderr.
    """
    try:
        return _invoke_cli(argv)
    except BaseException as exc:  # noqa: BLE001 - handled by shared printers
        tracebacks_enabled = _current_traceback_mode()
        apply_traceback_preferences(tracebacks_enabled)
        return _print_exception(
            exc,
            tracebacks_enabled=tracebacks_enabled,
            length_limit=_traceback_limit(
                tracebacks_enabled,
                summary_limit=summary_limit,
                verbose_limit=verbose_limit,
            ),
        )


@click.group(
    help=__init__conf__.title,
    context_settings=CLICK_CONTEXT_SETTINGS,
    invoke_without_command=True,
)
@click.version_option(
    version=__init__conf__.version,
    prog_name=__init__conf__.shell_command,
    message=f"{__init__conf__.shell_command} version {__init__conf__.version}",
)
@click.option(
    "--traceback/--no-traceback",
    is_flag=True,
    default=False,
    help="Show full Python traceback on errors",
)
@click.pass_context
def cli(ctx: click.Context, traceback: bool) -> None:
    """Root command storing global flags and syncing shared traceback state.

    The CLI must provide a switch for verbose tracebacks so developers can
    toggle diagnostic depth without editing configuration files.

    Ensures a dict-based context, stores the ``traceback`` flag, and mirrors
    the value into ``lib_cli_exit_tools.config`` so downstream helpers observe
    the preference. When no subcommand (or options) are provided, the command
    prints help instead of running the domain stub; otherwise the default
    action delegates to :func:`cli_main`.

    Note:
        Mutates :mod:`lib_cli_exit_tools.config` to reflect the requested
        traceback mode, including ``traceback_force_color`` when tracebacks are
        enabled. Initializes lib_log_rich runtime if needed.

    Example:
        >>> from click.testing import CliRunner
        >>> runner = CliRunner()
        >>> result = runner.invoke(cli, ["hello"])
        >>> result.exit_code
        0
        >>> "Hello World" in result.output
        True
    """
    # Initialize logging before any commands execute
    init_logging()

    _record_traceback_choice(ctx, enabled=traceback)
    _announce_traceback_choice(traceback)
    if _no_subcommand_requested(ctx):
        if _traceback_option_requested(ctx):
            cli_main()
        else:
            _show_help(ctx)


def cli_main() -> None:
    """Run the placeholder domain entry when callers opt into execution.

    Maintains compatibility with tooling that expects the original
    "do-nothing" behaviour by explicitly opting in via options (e.g.
    ``--traceback`` without subcommands).

    Side Effects:
        Delegates to :func:`noop_main`.

    Example:
        >>> cli_main()
    """
    noop_main()


@cli.command("info", context_settings=CLICK_CONTEXT_SETTINGS)
def cli_info() -> None:
    """Print resolved metadata so users can inspect installation details."""
    with lib_log_rich.runtime.bind(job_id=CliCommand.INFO.value, extra={"command": CliCommand.INFO.value}):
        logger.info("Displaying package information")
        __init__conf__.print_info()


@cli.command("hello", context_settings=CLICK_CONTEXT_SETTINGS)
def cli_hello() -> None:
    """Demonstrate the success path by emitting the canonical greeting."""
    with lib_log_rich.runtime.bind(job_id=CliCommand.HELLO.value, extra={"command": CliCommand.HELLO.value}):
        logger.info("Executing hello command")
        emit_greeting()


@cli.command("fail", context_settings=CLICK_CONTEXT_SETTINGS)
def cli_fail() -> None:
    """Trigger the intentional failure helper to test error handling."""
    with lib_log_rich.runtime.bind(job_id=CliCommand.FAIL.value, extra={"command": CliCommand.FAIL.value}):
        logger.warning("Executing intentional failure command")
        raise_intentional_failure()


@cli.command("config", context_settings=CLICK_CONTEXT_SETTINGS)
@click.option(
    "--format",
    type=EnumChoice(ConfigFormat),
    default=ConfigFormat.HUMAN.value,
    help="Output format (human-readable or JSON)",
)
@click.option(
    "--section",
    type=str,
    default=None,
    help="Show only a specific configuration section (e.g., 'lib_log_rich')",
)
def cli_config(format: ConfigFormat, section: str | None) -> None:
    """Display the current merged configuration from all sources.

    Shows configuration loaded from:
    - Default config (built-in)
    - Application config (/etc/xdg/pyproj-dep-analyze/config.toml)
    - User config (~/.config/pyproj-dep-analyze/config.toml)
    - .env files
    - Environment variables (PYPROJ_DEP_ANALYZE_*)

    Precedence: defaults → app → host → user → dotenv → env
    """
    with lib_log_rich.runtime.bind(job_id=CliCommand.CONFIG.value, extra={"command": CliCommand.CONFIG.value, "format": format.value}):
        logger.info("Displaying configuration", extra={"format": format.value, "section": section})
        display_config(format=format, section=section)


@cli.command("analyze", context_settings=CLICK_CONTEXT_SETTINGS)
@click.argument("pyproject_path", type=click.Path(exists=True, path_type=Path), default="pyproject.toml")
@click.option(
    "-o",
    "--output",
    type=click.Path(path_type=Path),
    default="outdated.json",
    help="Output file path (default: outdated.json)",
)
@click.option(
    "--github-token",
    type=str,
    envvar="GITHUB_TOKEN",
    default=None,
    help="GitHub token for API authentication. Can also be set via PYPROJ_DEP_ANALYZE_GITHUB_TOKEN env var or config file.",
)
@click.option(
    "--timeout",
    type=float,
    default=None,
    help="Request timeout in seconds. Default from config (30.0). Can also be set via PYPROJ_DEP_ANALYZE_TIMEOUT env var.",
)
@click.option(
    "--concurrency",
    type=int,
    default=None,
    help="Maximum concurrent API requests. Default from config (10). Can also be set via PYPROJ_DEP_ANALYZE_CONCURRENCY env var.",
)
@click.option(
    "--format",
    "output_format",
    type=EnumChoice(OutputFormat),
    default=OutputFormat.TABLE.value,
    help="Output format (default: table)",
)
def cli_analyze(
    pyproject_path: Path,
    output: Path,
    github_token: str | None,
    timeout: float | None,
    concurrency: int | None,
    output_format: OutputFormat,
) -> None:
    r"""Analyze dependencies in a pyproject.toml file.

    Examines all dependencies and determines for each Python version:
    - Current version specified
    - Latest available version
    - Recommended action (update, delete, none, check manually)

    Results are written to outdated.json and displayed.

    Settings can be configured via:
    - Command line options (highest precedence)
    - Environment variables (PYPROJ_DEP_ANALYZE_*)
    - Config files (~/.config/pyproj-dep-analyze/config.toml)
    - Default config (bundled with package)

    \b
    Examples:
        # Analyze current directory's pyproject.toml
        $ pyproj-dep-analyze analyze

        # Analyze specific file with custom output
        $ pyproj-dep-analyze analyze path/to/pyproject.toml -o results.json

        # Show summary only
        $ pyproj-dep-analyze analyze --format summary

        # Use environment variables for settings
        $ PYPROJ_DEP_ANALYZE_GITHUB_TOKEN=ghp_xxx pyproj-dep-analyze analyze
    """
    # Load settings from config (with env var overrides)
    settings = get_analyzer_settings()

    # CLI options override config settings
    resolved_token = github_token if github_token is not None else settings.github_token
    resolved_timeout = timeout if timeout is not None else settings.timeout
    resolved_concurrency = concurrency if concurrency is not None else settings.concurrency

    # Treat empty token as None
    final_token = resolved_token if resolved_token else None

    with lib_log_rich.runtime.bind(job_id=CliCommand.ANALYZE.value, extra={"command": CliCommand.ANALYZE.value}):
        logger.info("Analyzing dependencies", extra={"path": str(pyproject_path)})

        result = run_analysis(
            pyproject_path,
            github_token=final_token,
            timeout=resolved_timeout,
            concurrency=resolved_concurrency,
        )

        write_outdated_json(result.entries, output)
        report_output_written(len(result.entries), output)
        display_analysis_results(result, output_format)


@cli.command("analyze-enriched", context_settings=CLICK_CONTEXT_SETTINGS)
@click.argument("pyproject_path", type=click.Path(exists=True, path_type=Path), default="pyproject.toml")
@click.option(
    "-o",
    "--output",
    type=click.Path(path_type=Path),
    default="deps_enriched.json",
    help="Output file path (default: deps_enriched.json)",
)
@click.option(
    "--github-token",
    type=str,
    envvar="GITHUB_TOKEN",
    default=None,
    help="GitHub token for API authentication.",
)
@click.option(
    "--timeout",
    type=float,
    default=None,
    help="Request timeout in seconds.",
)
@click.option(
    "--concurrency",
    type=int,
    default=None,
    help="Maximum concurrent API requests.",
)
def cli_analyze_enriched(
    pyproject_path: Path,
    output: Path,
    github_token: str | None,
    timeout: float | None,
    concurrency: int | None,
) -> None:
    r"""Analyze dependencies with full metadata enrichment.

    Produces deps_enriched.json with:
    - PyPI metadata (license, author, release dates)
    - Repository info (GitHub stars, last activity)
    - Dependency graph
    - Package index source tracking

    \b
    Examples:
        # Analyze with enriched output
        $ pyproj-dep-analyze analyze-enriched

        # Custom output file
        $ pyproj-dep-analyze analyze-enriched -o analysis.json
    """
    settings = get_analyzer_settings()

    resolved_token = github_token if github_token is not None else settings.github_token
    resolved_timeout = timeout if timeout is not None else settings.timeout
    resolved_concurrency = concurrency if concurrency is not None else settings.concurrency
    final_token = resolved_token if resolved_token else None

    with lib_log_rich.runtime.bind(job_id=CliCommand.ANALYZE_ENRICHED.value, extra={"command": CliCommand.ANALYZE_ENRICHED.value}):
        logger.info("Analyzing dependencies (enriched)", extra={"path": str(pyproject_path)})

        result = run_enriched_analysis(
            pyproject_path,
            github_token=final_token,
            timeout=resolved_timeout,
            concurrency=resolved_concurrency,
        )

        write_enriched_json(result, output)

        click.echo(f"\nEnriched analysis written to: {output}")
        click.echo(f"Total packages: {result.summary.total_packages}")
        click.echo(f"Updates available: {result.summary.updates_available}")
        click.echo(f"Check manually: {result.summary.check_manually}")
        click.echo(f"From PyPI: {result.summary.from_pypi}")
        click.echo(f"From private index: {result.summary.from_private_index}")


def _report_deploy_results(results: list[DeployResult]) -> None:
    """Report deployment results to the user."""
    if results:
        click.echo("\nConfiguration deployed successfully:")
        for result in results:
            click.echo(f"  ✓ {result.destination}")
    else:
        click.echo("\nNo files were created (all target files already exist).")
        click.echo("Use --force to overwrite existing configuration files.")


def _handle_deploy_error(exc: Exception) -> None:
    """Handle and report deployment errors.

    Note:
        Document: The logging 'extra' dict is required by the lib_log_rich library
        for structured logging. This is a framework requirement at the logging boundary.
    """
    if isinstance(exc, PermissionError):
        logger.error("Permission denied when deploying configuration", extra={"error": str(exc)})
        click.echo(f"\nError: Permission denied. {exc}", err=True)
        click.echo("Hint: System-wide deployment (--target app/host) may require sudo.", err=True)
    else:
        logger.error("Failed to deploy configuration", extra={"error": str(exc), "error_type": type(exc).__name__})
        click.echo(f"\nError: Failed to deploy configuration: {exc}", err=True)
    raise SystemExit(1) from None


@cli.command("config-deploy", context_settings=CLICK_CONTEXT_SETTINGS)
@click.option(
    "--target",
    "targets",
    type=EnumChoice(DeploymentTarget),
    multiple=True,
    required=True,
    help="Target configuration layer(s) to deploy to (can specify multiple)",
)
@click.option(
    "--force",
    is_flag=True,
    default=False,
    help="Overwrite existing configuration files",
)
def cli_config_deploy(targets: tuple[DeploymentTarget, ...], force: bool) -> None:
    r"""Deploy default configuration to system or user directories.

    Creates configuration files in platform-specific locations:

    \b
    - app:  System-wide application config (requires privileges)
    - host: System-wide host config (requires privileges)
    - user: User-specific config (~/.config on Linux)

    By default, existing files are not overwritten. Use --force to overwrite.

    Examples:
        \b
        # Deploy to user config directory
        $ pyproj-dep-analyze config-deploy --target user

        \b
        # Deploy to both app and user directories
        $ pyproj-dep-analyze config-deploy --target app --target user

        \b
        # Force overwrite existing config
        $ pyproj-dep-analyze config-deploy --target user --force
    """
    target_values = [t.value for t in targets]
    with lib_log_rich.runtime.bind(
        job_id=CliCommand.CONFIG_DEPLOY.value, extra={"command": CliCommand.CONFIG_DEPLOY.value, "targets": target_values, "force": force}
    ):
        logger.info("Deploying configuration", extra={"targets": target_values, "force": force})

        try:
            deployed_paths = deploy_configuration(targets=list(targets), force=force)
            _report_deploy_results(deployed_paths)
        except Exception as exc:
            _handle_deploy_error(exc)


def main(
    argv: Sequence[str] | None = None,
    *,
    restore_traceback: bool = True,
    summary_limit: int = TRACEBACK_SUMMARY_LIMIT,
    verbose_limit: int = TRACEBACK_VERBOSE_LIMIT,
) -> int:
    """Execute the CLI with deliberate error handling and return the exit code.

    Provides the single entry point used by console scripts and
    ``python -m`` execution so that behaviour stays identical across
    transports.

    Args:
        argv: Optional sequence of CLI arguments. ``None`` lets Click consume
            ``sys.argv`` directly.
        restore_traceback: ``True`` to restore the prior ``lib_cli_exit_tools``
            traceback configuration after execution.
        summary_limit: Character budget used when formatting exceptions in
            summary mode.
        verbose_limit: Character budget used when formatting exceptions in
            verbose mode.

    Returns:
        Exit code reported by the CLI run.

    Note:
        Mutates the global traceback configuration while the CLI runs.
        Initializes and shuts down the lib_log_rich runtime.
    """
    init_logging()
    previous_state = snapshot_traceback_state()
    try:
        return _run_cli_via_exit_tools(
            argv,
            summary_limit=summary_limit,
            verbose_limit=verbose_limit,
        )
    finally:
        _restore_when_requested(previous_state, restore_traceback)
        lib_log_rich.runtime.shutdown()


def _restore_when_requested(state: TracebackState, should_restore: bool) -> None:
    """Restore the prior traceback configuration when requested.

    CLI execution may toggle verbose tracebacks for the duration of the run.
    Once the command ends we restore the previous configuration so other
    code paths continue with their expected defaults.

    Args:
        state: TracebackState model captured by :func:`snapshot_traceback_state`
            describing the prior configuration.
        should_restore: ``True`` to reapply the stored configuration; ``False``
            to keep the current settings.

    Note:
        May mutate ``lib_cli_exit_tools.config``.
    """
    if should_restore:
        restore_traceback_state(state)
