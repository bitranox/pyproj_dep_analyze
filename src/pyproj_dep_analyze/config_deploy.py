"""Configuration deployment functionality for CLI config-deploy command.

Purpose
-------
Provides the business logic for deploying default configuration to application,
host, or user configuration locations. Uses lib_layered_config's deploy_config
function to copy the bundled defaultconfig.toml to requested target layers.

Contents
--------
* :func:`deploy_configuration` – deploys configuration to specified targets

System Role
-----------
Lives in the behaviors layer. The CLI command delegates to this module for
all configuration deployment logic, keeping the CLI layer focused on argument
parsing and user interaction.
"""

from __future__ import annotations

from collections.abc import Sequence

from lib_layered_config import deploy_config
from lib_layered_config.examples.deploy import DeployResult

from . import __init__conf__
from .config import get_default_config_path
from .models import DeploymentTarget


def deploy_configuration(
    *,
    targets: Sequence[DeploymentTarget],
    force: bool = False,
) -> list[DeployResult]:
    r"""Deploy default configuration to specified target layers.

    Users need to initialize configuration files in standard locations
    (application, host, or user config directories) without manually
    copying files or knowing platform-specific paths.

    Uses lib_layered_config.deploy_config() to copy the bundled
    defaultconfig.toml to requested target layers (app, host, user).
    Returns a list of DeployResult objects describing what was done.

    Args:
        targets: Sequence of target layers to deploy to. Valid values:
            "app", "host", "user". Multiple targets can be specified to
            deploy to several locations at once.
        force: If True, overwrite existing configuration files. If False
            (default), skip files that already exist.

    Returns:
        List of DeployResult objects describing what was done for each
        destination. Each result contains: destination path, action taken,
        backup_path (if backed up), and ucf_path (if using batch mode).
        Empty list if all target files already exist and force=False.

    Raises:
        PermissionError: When deploying to app/host without sufficient privileges.
        ValueError: When invalid target names are provided.

    Note:
        Creates configuration files in platform-specific directories:

        - app: System-wide application config (requires privileges)
        - host: System-wide host config (requires privileges)
        - user: User-specific config (current user's home directory)

        Platform-specific paths:

        - Linux (app): /etc/xdg/{slug}/config.toml
        - Linux (host): /etc/xdg/{slug}/config.toml
        - Linux (user): ~/.config/{slug}/config.toml
        - macOS (app): /Library/Application Support/{vendor}/{app}/config.toml
        - macOS (user): ~/Library/Application Support/{vendor}/{app}/config.toml
        - Windows (app): C:\ProgramData\{vendor}\{app}\config.toml
        - Windows (user): %APPDATA%\{vendor}\{app}\config.toml

    Example:
        >>> results = deploy_configuration(targets=["user"])  # doctest: +SKIP
        >>> len(results) > 0  # doctest: +SKIP
        True
        >>> results[0].destination.exists()  # doctest: +SKIP
        True
    """
    source = get_default_config_path()

    # Convert enum values to strings for the underlying library
    target_strings = [t.value for t in targets]

    deployed_paths = deploy_config(
        source=source,
        vendor=__init__conf__.LAYEREDCONF_VENDOR,
        app=__init__conf__.LAYEREDCONF_APP,
        slug=__init__conf__.LAYEREDCONF_SLUG,
        targets=target_strings,
        force=force,
    )

    return deployed_paths


__all__ = [
    "deploy_configuration",
]
