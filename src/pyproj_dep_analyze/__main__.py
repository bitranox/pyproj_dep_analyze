"""Provide the ``python -m pyproj_dep_analyze`` entry point.

Runs :func:`pyproj_dep_analyze.cli.main`, the function the console scripts
run, so exit codes, traceback handling and log runtime shutdown are identical
however the CLI is started.
"""

from __future__ import annotations

from . import cli

if __name__ == "__main__":
    raise SystemExit(cli.main())
