"""Public package surface for dependency analysis and configuration.

This package provides tools for analyzing Python project dependencies
from pyproject.toml files, determining version compatibility across
Python versions, and generating update recommendations.

Main API
--------
* :func:`analyze_pyproject` - Analyze a pyproject.toml and return outdated entries
* :class:`OutdatedEntry` - Data class for analysis results
* :class:`Analyzer` - Stateful analyzer with caching
"""

from __future__ import annotations

from .__init__conf__ import print_info
from .analyzer import Analyzer, analyze_pyproject, write_outdated_json
from .behaviors import (
    CANONICAL_GREETING,
    emit_greeting,
    noop_main,
    raise_intentional_failure,
)
from .config import get_config
from .models import (
    Action,
    AnalysisResult,
    DependencyInfo,
    OutdatedEntry,
    PythonVersion,
)

__all__ = [
    "Action",
    "Analyzer",
    "AnalysisResult",
    "CANONICAL_GREETING",
    "DependencyInfo",
    "OutdatedEntry",
    "PythonVersion",
    "analyze_pyproject",
    "emit_greeting",
    "get_config",
    "noop_main",
    "print_info",
    "raise_intentional_failure",
    "write_outdated_json",
]
