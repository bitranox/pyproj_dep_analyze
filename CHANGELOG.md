# Changelog

All notable changes to this project will be documented in this file following
the [Keep a Changelog](https://keepachangelog.com/) format.


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
