"""Public package surface for dependency analysis and configuration.

This package provides tools for analyzing Python project dependencies
from pyproject.toml files, determining version compatibility across
Python versions, and generating update recommendations.

Main API
--------
* :func:`analyze_pyproject` - Analyze a pyproject.toml and return outdated entries
* :func:`run_enriched_analysis` - Analyze with full metadata enrichment
* :class:`OutdatedEntry` - Data class for analysis results
* :class:`EnrichedAnalysisResult` - Enriched analysis with metadata
* :class:`Analyzer` - Stateful analyzer with caching
"""

from __future__ import annotations

from .__init__conf__ import print_info
from .analyzer import (
    Analyzer,
    analyze_pyproject,
    run_enriched_analysis,
    write_enriched_json,
    write_outdated_json,
)
from .behaviors import (
    CANONICAL_GREETING,
    emit_greeting,
    noop_main,
    raise_intentional_failure,
)
from .config import get_config
from .index_resolver import IndexResolver, detect_configured_indexes, identify_index
from .models import (
    KNOWN_INDEX_PATTERNS,
    Action,
    AnalysisResult,
    DependencyInfo,
    DownloadStats,
    EnrichedAnalysisResult,
    EnrichedEntry,
    IndexInfo,
    OutdatedEntry,
    PyPIMetadata,
    PythonVersion,
    RepoMetadata,
    VersionMetrics,
)
from .repo_resolver import (
    ParsedRepoUrl,
    ProjectUrlKey,
    PyPIUrlMetadata,
    RepoResolver,
    detect_repo_url,
    parse_repo_url,
)
from .stats_resolver import StatsResolver

__all__ = [
    "CANONICAL_GREETING",
    "KNOWN_INDEX_PATTERNS",
    "Action",
    "AnalysisResult",
    "Analyzer",
    "DependencyInfo",
    "DownloadStats",
    "EnrichedAnalysisResult",
    "EnrichedEntry",
    "IndexInfo",
    "IndexResolver",
    "OutdatedEntry",
    "ParsedRepoUrl",
    "ProjectUrlKey",
    "PyPIMetadata",
    "PyPIUrlMetadata",
    "PythonVersion",
    "RepoMetadata",
    "RepoResolver",
    "StatsResolver",
    "VersionMetrics",
    "analyze_pyproject",
    "detect_configured_indexes",
    "detect_repo_url",
    "emit_greeting",
    "get_config",
    "identify_index",
    "noop_main",
    "parse_repo_url",
    "print_info",
    "raise_intentional_failure",
    "run_enriched_analysis",
    "write_enriched_json",
    "write_outdated_json",
]
