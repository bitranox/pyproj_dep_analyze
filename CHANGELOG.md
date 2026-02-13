# Changelog

All notable changes to this project will be documented in this file following
the [Keep a Changelog](https://keepachangelog.com/) format.


## [Unreleased]

## [4.0.1] - 2026-02-13

### Changed
- Replaced `scripts/` directory with external `bmk` build tool
- Restructured CI/CD workflows (`default_cicd_public.yml`, `default_release_public.yml`)
- Added `extract-metadata` composite GitHub Action
- Rewrote Makefile to use `bmk` for all build tasks
- Updated import-linter architecture contracts to properly layer `python_version_parser`
- Updated 10 dependencies to latest versions

### Fixed
- Fixed litestar test data TOML parsing error (duplicate `lint` key under `tool.ruff`)
- Fixed `FakeConfig` test compatibility with `lib_layered_config` `redact` parameter
- Fixed shell script formatting and shellcheck warnings in `reset_git_history.sh`

### Removed
- Removed `scripts/` directory (replaced by `bmk` tool)
- Removed `tests/test_scripts.py`

## [4.0.0] - 2025-12-13

### Breaking Changes
- **`direct_dependencies`** now only includes runtime dependencies (previously included all dependencies including optional extras)

### Added
- **`optional_dependencies`** field in `EnrichedEntry` - dict mapping extra name to list of package names
  - Groups optional dependencies by their extra (e.g., `"dev"`, `"test"`, `"docs"`)
  - Example: `{"dev": ["pytest", "ruff"], "docs": ["sphinx", "myst_parser"]}`
- `_extract_optional_dependency_names()` function to extract and group optional dependencies
- `_extract_extra_name()` helper function to parse extra names from requirement markers

### Changed
- `_extract_dependency_names()` now filters out dependencies with `extra ==` markers by default
- Added `include_optional` parameter to `_extract_dependency_names()` for backwards compatibility

## [3.1.0] - 2025-12-13

### Changed
- **Python 3.10+ compatibility** - lowered minimum Python version from 3.13 to 3.10
- Switched from `tomllib`/`tomli` to `rtoml` (Rust-based TOML parser) for consistent cross-version support
- Updated CI matrix to test Python 3.10, 3.11, 3.12, and 3.13
- Updated Ruff target version from `py313` to `py310`

### Added
- **"Why pyproj_dep_analyze?"** section in README explaining security motivation for dependency analysis in AI-assisted "vibe coded" applications
- Documented common supply chain attack vectors: typosquatting, dependency confusion, malicious updates, abandoned package takeover, protestware, hidden malware
- Added `rtoml>=0.11.0` as runtime dependency (replaces conditional `tomli` backport)
- Python version classifiers for 3.10, 3.11, 3.12, 3.13 in package metadata

### Removed
- Removed conditional `tomli` dependency (no longer needed with `rtoml`)

## [3.0.0] - 2025-12-07

### Added
- **Version metrics** (`VersionMetrics` model) - computed release pattern metrics for quality assessment:
  - `release_count`, `latest_release_age_days`, `first_release_age_days`
  - `avg_days_between_releases`, `min_days_between_releases`, `max_days_between_releases`
  - `releases_last_year`, `release_dates`
- **Download statistics** (`DownloadStats` model) - popularity metrics from pypistats.org:
  - `total_downloads`, `last_month_downloads`, `last_week_downloads`, `last_day_downloads`
- **Stats resolver** (`StatsResolver` class) - async fetcher for pypistats.org API with caching
- New fields in `PyPIMetadata`: `version_metrics`, `download_stats`
- Exported new models: `VersionMetrics`, `DownloadStats`, `StatsResolver`

### Changed
- Restructured README with comprehensive CLI reference, Python API documentation, and data model tables
- Added clear project scope boundaries documenting `pyproj_dep_scan` and `pyproj_dep_update` as separate projects

### Performance
- Added `@lru_cache` to `parse_requires_python` (maxsize=256) - ~100x faster on repeated calls
- Added `@lru_cache` to `_extract_version_from_tag` (maxsize=512)
- Added `@lru_cache` to `_parse_github_url` (maxsize=256)

### Tests
- 640 tests (up from 505)

## [2.0.0] - 2025-12-04

### Added
- **Enriched analysis mode** with `run_enriched_analysis()` and `write_enriched_json()` for comprehensive metadata
- **Package index detection** (`IndexResolver`) - detects configured indexes from pip config, environment, pyproject.toml
- **Repository metadata resolution** (`RepoResolver`) - fetches GitHub/GitLab repository information
- **PyPI metadata enrichment** - extracts author, license, release dates, requires_dist from PyPI API
- New domain models: `EnrichedAnalysisResult`, `EnrichedEntry`, `EnrichedSummary`, `PyPIMetadata`, `RepoMetadata`, `IndexInfo`
- New enums: `IndexType`, `RepoType`, `CompatibilityStatus`, `VersionStatus`, `ConfigFormat`, `DeploymentTarget`
- CLI command `analyze --enriched` for enriched JSON output with full metadata
- Support for uv tool configuration (`[tool.uv]` index sources)
- Python compatibility tracking per dependency across all target Python versions
- Dependency graph extraction from `requires_dist` metadata
- 505 tests (up from 384)

### Changed
- Unified data architecture using Pydantic models throughout (eliminated dataclass-to-Pydantic conversions)
- `OutdatedEntry`, `AnalysisResult` converted from dataclasses to Pydantic models for consistent serialization
- `VersionResult` now includes optional `pypi_metadata` field for enrichment
- Extended `PyprojectSchema` to support PDM, Hatch, and dependency-groups (PEP 735)
- Improved dependency extraction with better marker parsing and git URL handling
- `config show` command now supports `--format json` option

### Fixed
- Proper enum serialization in JSON output using `model_dump(mode="json")`

## [1.1.0] - 2025-12-03

### Changed
- Simplified logging initialization by using `lib_log_rich` default settings for `attach_std_logging()`

## [1.0.0] - 2025-12-02

### Added
- Core dependency analysis functionality for pyproject.toml files
- `Analyzer` class with async support and configurable concurrency
- PyPI and GitHub version resolution with caching
- Python version compatibility checking via `requires-python` parsing
- CLI commands: `analyze`, `config`, `config-deploy`, `info`, `hello`, `fail`
- Layered configuration system (defaults → app → host → user → env)
- JSON output format for analysis results
- Comprehensive test suite with 384 tests
