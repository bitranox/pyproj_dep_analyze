# pyproj_dep_analyze

<!-- Badges -->
[![CI](https://github.com/bitranox/pyproj_dep_analyze/actions/workflows/ci.yml/badge.svg)](https://github.com/bitranox/pyproj_dep_analyze/actions/workflows/ci.yml)
[![CodeQL](https://github.com/bitranox/pyproj_dep_analyze/actions/workflows/codeql.yml/badge.svg)](https://github.com/bitranox/pyproj_dep_analyze/actions/workflows/codeql.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Open in Codespaces](https://img.shields.io/badge/Codespaces-Open-blue?logo=github&logoColor=white&style=flat-square)](https://codespaces.new/bitranox/pyproj_dep_analyze?quickstart=1)
[![PyPI](https://img.shields.io/pypi/v/pyproj_dep_analyze.svg)](https://pypi.org/project/pyproj_dep_analyze/)
[![PyPI - Downloads](https://img.shields.io/pypi/dm/pyproj_dep_analyze.svg)](https://pypi.org/project/pyproj_dep_analyze/)
[![Code Style: Ruff](https://img.shields.io/badge/Code%20Style-Ruff-46A3FF?logo=ruff&labelColor=000)](https://docs.astral.sh/ruff/)
[![codecov](https://codecov.io/gh/bitranox/pyproj_dep_analyze/graph/badge.svg?token=UFBaUDIgRk)](https://codecov.io/gh/bitranox/pyproj_dep_analyze)
[![Maintainability](https://qlty.sh/badges/041ba2c1-37d6-40bb-85a0-ec5a8a0aca0c/maintainability.svg)](https://qlty.sh/gh/bitranox/projects/pyproj_dep_analyze)
[![Known Vulnerabilities](https://snyk.io/test/github/bitranox/pyproj_dep_analyze/badge.svg)](https://snyk.io/test/github/bitranox/pyproj_dep_analyze)
[![security: bandit](https://img.shields.io/badge/security-bandit-yellow.svg)](https://github.com/PyCQA/bandit)

## What is pyproj_dep_analyze?

**Parses `pyproject.toml` to generate actionable dependency data for security audits, update automation, and LLM-powered code review.**

- Parses `pyproject.toml` to identify which dependencies can be **updated** or **deleted** per Python version
- Provides **structured JSON output** for integration with security audits and CI pipelines
- Includes **human/LLM-readable notes** explaining each result - ideal for AI-assisted dependency review and automated security analysis
- Output can be consumed by security tools or LLMs to detect attack vectors like **dependency confusion** and **typosquatting** - especially critical for vibe-coded projects where dependencies may be added without thorough vetting

### Quick Usage

```bash
# Basic analysis - check dependency health
pyproj-dep-analyze analyze

# Enriched analysis - full metadata including PyPI info and repo stats
pyproj-dep-analyze analyze-enriched
```

### Output Files

| Command | Output File | Description |
|---------|-------------|-------------|
| `analyze` | `outdated.json` | Per-dependency actions: update, delete, none, check manually |
| `analyze-enriched` | `deps_enriched.json` | Full metadata: PyPI info, repo stats, dependency graph, index sources |

#### `outdated.json` example

```json
[
  {
    "package": "requests",
    "python_version": "3.11",
    "current_version": "2.28.0",
    "latest_version": "2.32.0",
    "action": "update",
    "note": "Package 'requests' can be updated from 2.28.0 to 2.32.0. Review the changelog for breaking changes before updating."
  }
]
```

#### `deps_enriched.json` example

```json
{
  "analyzed_at": "2025-12-04T10:30:00Z",
  "pyproject_path": "pyproject.toml",
  "python_versions": ["3.11", "3.12", "3.13"],
  "indexes_configured": [
    {"url": "https://pypi.org/simple", "index_type": "pypi", "is_private": false},
    {"url": "https://private.jfrog.io/simple", "index_type": "artifactory", "is_private": true}
  ],
  "summary": {
    "total_packages": 25,
    "updates_available": 5,
    "up_to_date": 18,
    "check_manually": 2,
    "note": "Analyzed 25 dependencies. 5 can be updated. 18 are up to date. 2 require manual verification - SECURITY: Review these for potential dependency confusion or typosquatting. WARNING: PyPI is configured before private index - this may expose you to dependency confusion attacks."
  },
  "packages": [
    {
      "name": "requests",
      "requested_version": ">=2.28.0",
      "latest_version": "2.32.0",
      "action": "update",
      "note": "Package 'requests' can be updated from 2.28.0 to 2.32.0. Review the changelog for breaking changes before updating. [License: Apache-2.0 | 52,345 stars | 9,234 forks | last release: 2024-05-29]",
      "direct_dependencies": ["urllib3", "certifi", "charset-normalizer", "idna"],
      "required_by": ["httpx", "my-app"],
      "pypi_metadata": { "license": "Apache-2.0", "latest_release_date": "2024-05-29T..." },
      "repo_metadata": { "stars": 52345, "forks": 9234 }
    }
  ]
}
```

---

A Python project dependency analyzer that processes `pyproject.toml` files to analyze dependencies and Python version requirements. For each dependency and Python version, it determines both the currently defined version and the latest compatible version, producing actionable recommendations.

## Features

- **Comprehensive Dependency Extraction**: Reads dependencies from all common sources:
  - `[project.dependencies]` (PEP 621)
  - `[project.optional-dependencies]`
  - `[build-system.requires]`
  - `[tool.poetry.dependencies]` / `[tool.poetry.dev-dependencies]`
  - `[tool.poetry.group.<name>.dependencies]`
  - `[tool.pdm.dependencies]` / `[tool.pdm.dev-dependencies]`
  - `[tool.hatch.envs.<name>.dependencies]`
  - `[dependency-groups]` (PEP 735)

- **Python Version Analysis**: Interprets `requires-python` and analyzes dependencies for each valid Python version

- **Version Resolution**:
  - Queries PyPI for latest package versions
  - Queries GitHub releases/tags for git dependencies
  - Handles version markers and constraints

- **Enriched Analysis Mode**: Full metadata enrichment including:
  - PyPI metadata (license, author, release dates, requires_dist)
  - Repository info (GitHub stars, last activity, forks)
  - Package index detection (PyPI, private indexes)
  - Dependency graph extraction

- **Actionable Output**: For each dependency, recommends one of:
  - `update` - A newer compatible version exists
  - `delete` - Dependency should be removed for this Python version
  - `none` - Dependency is up to date
  - `check manually` - Manual verification required (e.g., GitHub packages without releases)

---

## Table of Contents

- [Installation](#installation)
- [Quick Start](#quick-start)
- [CLI Reference](#cli-reference)
  - [Global Options](#global-options)
  - [analyze](#analyze---analyze-dependencies)
  - [analyze-enriched](#analyze-enriched---enriched-analysis)
  - [config](#config---view-configuration)
  - [config-deploy](#config-deploy---deploy-configuration-files)
  - [info](#info---show-package-information)
  - [hello / fail](#hello--fail---test-commands)
- [Python API](#python-api)
  - [Basic Analysis](#basic-analysis)
  - [Enriched Analysis](#enriched-analysis)
  - [Analyzer Class](#analyzer-class)
  - [Data Models](#data-models)
  - [Index Resolution](#index-resolution)
  - [Repository Resolution](#repository-resolution)
- [Configuration](#configuration)
  - [Configuration Precedence](#configuration-precedence)
  - [Analyzer Settings](#analyzer-settings)
  - [Logging Settings](#logging-settings)
  - [Config File Locations](#config-file-locations)
- [Output Formats](#output-formats)
- [Further Documentation](#further-documentation)

---

## Installation

### Recommended: Install via UV

UV is an ultrafast Python package installer written in Rust (10-20x faster than pip/poetry).

```bash
# Install UV
pip install --upgrade uv

# Create and activate a virtual environment (optional but recommended)
uv venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\Activate.ps1  # Windows PowerShell

# Install from PyPI
uv pip install pyproj_dep_analyze
```

### Alternative: Install via pip

```bash
pip install pyproj_dep_analyze
```

For additional installation methods (pipx, source builds, etc.), see [INSTALL.md](INSTALL.md).

Both `pyproj_dep_analyze` and `pyproj-dep-analyze` commands are registered on your PATH.

### Python 3.13+ Baseline

This project targets **Python 3.13 and newer only**.

---

## Quick Start

```bash
# Basic analysis - analyze pyproject.toml in current directory
pyproj-dep-analyze analyze

# Enriched analysis with full metadata
pyproj-dep-analyze analyze-enriched

# View current configuration
pyproj-dep-analyze config

# Show package info
pyproj-dep-analyze info
```

---

## CLI Reference

The CLI uses [rich-click](https://github.com/ewels/rich-click) for styled help output and familiar click ergonomics.

### Global Options

These options are available for all commands:

| Option | Description | Default |
|--------|-------------|---------|
| `--traceback` / `--no-traceback` | Show full Python traceback on errors | `--no-traceback` |
| `-h`, `--help` | Show help message and exit | - |
| `--version` | Show version and exit | - |

---

### `analyze` - Analyze Dependencies

Analyze a `pyproject.toml` file and determine outdated dependencies for each Python version.

```bash
pyproj-dep-analyze analyze [PYPROJECT_PATH] [OPTIONS]
```

#### Arguments

| Argument | Description | Default |
|----------|-------------|---------|
| `PYPROJECT_PATH` | Path to pyproject.toml file | `pyproject.toml` |

#### Options

| Option | Description | Env Variable | Default |
|--------|-------------|--------------|---------|
| `-o`, `--output PATH` | Output file path for JSON results | - | `outdated.json` |
| `--github-token TEXT` | GitHub token for API authentication | `GITHUB_TOKEN`, `PYPROJ_DEP_ANALYZE_GITHUB_TOKEN` | `None` |
| `--timeout FLOAT` | Request timeout in seconds for API calls | `PYPROJ_DEP_ANALYZE_TIMEOUT` | `30.0` |
| `--concurrency INTEGER` | Maximum concurrent API requests | `PYPROJ_DEP_ANALYZE_CONCURRENCY` | `10` |
| `--format [table\|summary\|json]` | Output format for display | - | `table` |

#### Output Formats

| Format | Description |
|--------|-------------|
| `table` | Summary statistics plus lists of updates and manual checks (default) |
| `summary` | Only summary statistics (counts of updates, deletions, etc.) |
| `json` | Full analysis as JSON to stdout |

#### Examples

```bash
# Analyze pyproject.toml in current directory
pyproj-dep-analyze analyze

# Analyze a specific file
pyproj-dep-analyze analyze path/to/pyproject.toml

# Save results to custom file
pyproj-dep-analyze analyze -o my-results.json

# Use GitHub token for better rate limits
pyproj-dep-analyze analyze --github-token ghp_xxxxx
# Or via environment variable:
GITHUB_TOKEN=ghp_xxxxx pyproj-dep-analyze analyze

# Show only summary
pyproj-dep-analyze analyze --format summary

# Output as JSON
pyproj-dep-analyze analyze --format json

# Increase timeout for slow connections
pyproj-dep-analyze analyze --timeout 60

# Reduce concurrency to avoid rate limits
pyproj-dep-analyze analyze --concurrency 5
```

#### Output File Format (`outdated.json`)

The output file contains an array of entries, one per dependency per Python version. Each entry includes a `note` field with a human/LLM-readable explanation:

```json
[
  {
    "package": "requests",
    "python_version": "3.11",
    "current_version": "2.28.0",
    "latest_version": "2.32.0",
    "action": "update",
    "note": "Package 'requests' can be updated from 2.28.0 to 2.32.0. Review the changelog for breaking changes before updating."
  },
  {
    "package": "tomli",
    "python_version": "3.11",
    "current_version": "2.0.0",
    "latest_version": null,
    "action": "delete",
    "note": "Package 'tomli' has a Python version marker that excludes Python 3.11. This dependency should be removed from configurations targeting Python 3.11, or the marker is intentional (e.g., backport packages like 'tomli' for Python <3.11)."
  },
  {
    "package": "internal-tool",
    "python_version": "3.11",
    "current_version": null,
    "latest_version": "unknown",
    "action": "check manually",
    "note": "Package 'internal-tool' requires manual verification. Could not determine latest version from PyPI. This may be a private/internal package, or PyPI API was unavailable. SECURITY: Verify this is a legitimate package and not a dependency confusion attack."
  }
]
```

#### Actions Explained

| Action | Meaning |
|--------|---------|
| `update` | A newer compatible version exists on PyPI/GitHub |
| `delete` | The dependency should be removed for this Python version (e.g., `tomli` for Python 3.11+ where `tomllib` is built-in) |
| `none` | The dependency is up to date |
| `check manually` | Version could not be determined automatically (e.g., private packages, GitHub repos without releases) |

---

### `analyze-enriched` - Enriched Analysis

Analyze dependencies with full metadata enrichment including PyPI info, repository data, and dependency graphs.

```bash
pyproj-dep-analyze analyze-enriched [PYPROJECT_PATH] [OPTIONS]
```

#### Arguments

| Argument | Description | Default |
|----------|-------------|---------|
| `PYPROJECT_PATH` | Path to pyproject.toml file | `pyproject.toml` |

#### Options

| Option | Description | Env Variable | Default |
|--------|-------------|--------------|---------|
| `-o`, `--output PATH` | Output file path | - | `deps_enriched.json` |
| `--github-token TEXT` | GitHub token for API authentication | `GITHUB_TOKEN`, `PYPROJ_DEP_ANALYZE_GITHUB_TOKEN` | `None` |
| `--timeout FLOAT` | Request timeout in seconds | `PYPROJ_DEP_ANALYZE_TIMEOUT` | `30.0` |
| `--concurrency INTEGER` | Maximum concurrent API requests | `PYPROJ_DEP_ANALYZE_CONCURRENCY` | `10` |

#### Examples

```bash
# Enriched analysis with default output
pyproj-dep-analyze analyze-enriched

# Custom output file
pyproj-dep-analyze analyze-enriched -o analysis.json

# With GitHub token for repository metadata
GITHUB_TOKEN=ghp_xxx pyproj-dep-analyze analyze-enriched
```

#### Enriched Output Format (`deps_enriched.json`)

```json
{
  "analyzed_at": "2025-12-04T10:30:00Z",
  "pyproject_path": "pyproject.toml",
  "python_versions": ["3.11", "3.12", "3.13"],
  "indexes_configured": [
    {"url": "https://pypi.org/simple", "index_type": "pypi", "is_private": false}
  ],
  "packages": [
    {
      "name": "requests",
      "requested_version": ">=2.28.0",
      "resolved_version": "2.28.0",
      "latest_version": "2.32.0",
      "action": "update",
      "source": "project.dependencies",
      "index": {"url": "https://pypi.org/simple", "index_type": "pypi", "is_private": false},
      "python_compatibility": {
        "3.11": "compatible",
        "3.12": "compatible",
        "3.13": "compatible"
      },
      "pypi": {
        "summary": "Python HTTP for Humans.",
        "license": "Apache-2.0",
        "author": "Kenneth Reitz",
        "requires_python": ">=3.8",
        "available_versions": ["2.32.0", "2.31.0", "..."],
        "first_release_date": "2011-02-13T...",
        "latest_release_date": "2024-05-29T...",
        "requires_dist": ["charset_normalizer>=2,<4", "idna>=2.5,<4", "..."]
      },
      "repository": {
        "repo_type": "github",
        "url": "https://github.com/psf/requests",
        "owner": "psf",
        "name": "requests",
        "stars": 51234,
        "forks": 9234,
        "open_issues": 123,
        "last_commit_date": "2024-11-15T..."
      },
      "dependencies": ["charset-normalizer", "idna", "urllib3", "certifi"]
    }
  ],
  "dependency_graph": {
    "requests": ["charset-normalizer", "idna", "urllib3", "certifi"],
    "httpx": ["anyio", "certifi", "httpcore", "idna", "sniffio"]
  },
  "summary": {
    "total_packages": 25,
    "updates_available": 5,
    "up_to_date": 18,
    "check_manually": 2,
    "from_pypi": 23,
    "from_private_index": 2
  }
}
```

---

### `config` - View Configuration

Display the current merged configuration from all sources.

```bash
pyproj-dep-analyze config [OPTIONS]
```

#### Options

| Option | Description | Values | Default |
|--------|-------------|--------|---------|
| `--format [human\|json]` | Output format | `human`, `json` | `human` |
| `--section TEXT` | Show only a specific configuration section | e.g., `analyzer`, `lib_log_rich` | `None` (all) |

#### Examples

```bash
# Show all configuration
pyproj-dep-analyze config

# Show as JSON for scripting
pyproj-dep-analyze config --format json

# Show only analyzer configuration
pyproj-dep-analyze config --section analyzer

# Show only logging configuration
pyproj-dep-analyze config --section lib_log_rich
```

---

### `config-deploy` - Deploy Configuration Files

Deploy default configuration files to system or user directories.

```bash
pyproj-dep-analyze config-deploy --target TARGET [OPTIONS]
```

#### Options

| Option | Description | Values | Default |
|--------|-------------|--------|---------|
| `--target TARGET` | Target configuration layer(s). Can be specified multiple times. **Required.** | `app`, `host`, `user` | - |
| `--force` | Overwrite existing configuration files | Flag | `False` |

#### Target Locations

| Target | Linux | macOS | Windows |
|--------|-------|-------|---------|
| `user` | `~/.config/pyproj-dep-analyze/config.toml` | `~/Library/Application Support/bitranox/Pyproj Dep Analyse/config.toml` | `%APPDATA%\bitranox\Pyproj Dep Analyse\config.toml` |
| `app` | `/etc/xdg/pyproj-dep-analyze/config.toml` | `/Library/Application Support/bitranox/Pyproj Dep Analyse/config.toml` | `%PROGRAMDATA%\bitranox\Pyproj Dep Analyse\config.toml` |
| `host` | `/etc/pyproj-dep-analyze/hosts/{hostname}.toml` | Same as app | Same as app |

#### Examples

```bash
# Deploy to user config directory
pyproj-dep-analyze config-deploy --target user

# Deploy to system-wide location (requires privileges)
sudo pyproj-dep-analyze config-deploy --target app

# Deploy to multiple locations
pyproj-dep-analyze config-deploy --target user --target host

# Force overwrite existing config
pyproj-dep-analyze config-deploy --target user --force
```

---

### `info` - Show Package Information

Display package metadata including version, author, and installation details.

```bash
pyproj-dep-analyze info
```

---

### `hello` / `fail` - Test Commands

Commands for testing and verification.

```bash
# Test success path - emit canonical greeting
pyproj-dep-analyze hello

# Test failure path - trigger intentional error
pyproj-dep-analyze fail
pyproj-dep-analyze --traceback fail  # Show full traceback
```

---

## Python API

The package can be used as a library for programmatic dependency analysis.

### Basic Analysis

```python
from pyproj_dep_analyze import analyze_pyproject, OutdatedEntry, Action

# Analyze a pyproject.toml file
entries: list[OutdatedEntry] = analyze_pyproject("path/to/pyproject.toml")

# Filter by action
updates = [e for e in entries if e.action == Action.UPDATE]
for entry in updates:
    print(f"{entry.package}: {entry.current_version} -> {entry.latest_version}")

# With options
entries = analyze_pyproject(
    "pyproject.toml",
    github_token="ghp_xxxxx",  # Optional GitHub token
    timeout=60.0,              # Request timeout in seconds
    concurrency=5,             # Max concurrent requests
)
```

### Enriched Analysis

```python
from pyproj_dep_analyze import run_enriched_analysis, write_enriched_json

# Run enriched analysis
result = run_enriched_analysis(
    "pyproject.toml",
    github_token="ghp_xxxxx",
    timeout=60.0,
    concurrency=10,
)

# Access summary
print(f"Total packages: {result.summary.total_packages}")
print(f"Updates available: {result.summary.updates_available}")
print(f"From private index: {result.summary.from_private_index}")

# Access individual packages
for pkg in result.packages:
    print(f"{pkg.name}: {pkg.action.value}")
    if pkg.pypi_metadata:
        print(f"  License: {pkg.pypi_metadata.license}")
        print(f"  Author: {pkg.pypi_metadata.author}")
    if pkg.repo_metadata:
        print(f"  Stars: {pkg.repo_metadata.stars}")

# Access dependency graph
for pkg_name, deps in result.dependency_graph.items():
    print(f"{pkg_name} depends on: {', '.join(deps)}")

# Write to file
write_enriched_json(result, "analysis.json")
```

### Analyzer Class

For more control, use the `Analyzer` class directly:

```python
from pyproj_dep_analyze import Analyzer
from pathlib import Path

# Create analyzer with custom settings
analyzer = Analyzer(
    github_token="ghp_xxxxx",
    timeout=60.0,
    concurrency=20,
)

# Run analysis
result = analyzer.analyze(Path("pyproject.toml"))

# Access results
for entry in result.entries:
    print(f"{entry.package} ({entry.python_version}): {entry.action.value}")

# Run enriched analysis
enriched = analyzer.analyze_enriched(Path("pyproject.toml"))
```

### Data Models

#### Action (Enum)

```python
from pyproj_dep_analyze import Action

Action.UPDATE        # "update" - newer version exists
Action.DELETE        # "delete" - remove for this Python version
Action.NONE          # "none" - up to date
Action.CHECK_MANUALLY  # "check manually" - needs manual verification
```

#### OutdatedEntry (Pydantic Model)

```python
from pyproj_dep_analyze import OutdatedEntry

# Fields
entry.package: str           # Package name
entry.python_version: str    # Python version (e.g., "3.11")
entry.current_version: str | None  # Currently specified version
entry.latest_version: str | None   # Latest available version
entry.action: Action         # Recommended action
entry.note: str              # Human/LLM-readable explanation

# Serialization
entry.model_dump()           # -> dict
entry.model_dump_json()      # -> JSON string
```

#### AnalysisResult (Pydantic Model)

```python
from pyproj_dep_analyze import AnalysisResult

result.entries: list[OutdatedEntry]  # All analysis entries
result.python_versions: list[str]    # Python versions analyzed
result.total_dependencies: int       # Total unique dependencies
result.update_count: int             # Dependencies needing updates
result.delete_count: int             # Dependencies to delete
result.check_manually_count: int     # Needs manual check
```

#### EnrichedAnalysisResult (Pydantic Model)

```python
from pyproj_dep_analyze import EnrichedAnalysisResult, EnrichedEntry

result.analyzed_at: str                    # ISO timestamp
result.pyproject_path: str                 # Analyzed file path
result.python_versions: list[str]          # Python versions
result.indexes_configured: list[IndexInfo] # Package indexes
result.packages: list[EnrichedEntry]       # Enriched entries
result.dependency_graph: dict[str, list[str]]  # Dependencies
result.summary: EnrichedSummary            # Statistics
```

#### EnrichedEntry (Pydantic Model)

```python
from pyproj_dep_analyze import EnrichedEntry

entry.name: str                                # Package name
entry.requested_version: str | None            # Version constraint
entry.resolved_version: str | None             # Resolved version
entry.latest_version: str | None               # Latest version
entry.action: Action                           # Recommended action
entry.source: str                              # Where declared
entry.index_info: IndexInfo | None             # Package index
entry.python_compatibility: dict[str, CompatibilityStatus]
entry.pypi_metadata: PyPIMetadata | None       # PyPI data
entry.repo_metadata: RepoMetadata | None       # Repo data
entry.direct_dependencies: list[str]           # Direct deps
```

#### PyPIMetadata (Pydantic Model)

```python
from pyproj_dep_analyze import PyPIMetadata

meta.summary: str | None           # One-line description
meta.license: str | None           # SPDX license
meta.home_page: str | None         # Project URL
meta.project_urls: dict[str, str]  # Labeled URLs
meta.author: str | None            # Author name
meta.author_email: str | None      # Author email
meta.maintainer: str | None        # Maintainer name
meta.maintainer_email: str | None  # Maintainer email
meta.available_versions: list[str] # All versions
meta.first_release_date: str | None  # First release ISO date
meta.latest_release_date: str | None # Latest release ISO date
meta.requires_python: str | None   # Python constraint
meta.requires_dist: list[str]      # Dependency specs
```

#### RepoMetadata (Pydantic Model)

```python
from pyproj_dep_analyze import RepoMetadata, RepoType

meta.repo_type: RepoType       # github, gitlab, bitbucket, unknown
meta.url: str | None           # Repository URL
meta.owner: str | None         # Owner/organization
meta.name: str | None          # Repository name
meta.stars: int | None         # Star count
meta.forks: int | None         # Fork count
meta.open_issues: int | None   # Open issue count
meta.default_branch: str | None  # Default branch
meta.last_commit_date: str | None  # Last commit ISO date
meta.created_at: str | None    # Creation ISO date
meta.description: str | None   # Repository description
```

#### IndexInfo (Pydantic Model)

```python
from pyproj_dep_analyze import IndexInfo, IndexType

info.url: str              # Index URL
info.index_type: IndexType # pypi, testpypi, artifactory, etc.
info.is_private: bool      # Whether private/internal
```

#### DependencyInfo (Dataclass)

```python
from pyproj_dep_analyze import DependencyInfo

dep.name: str                    # Normalized package name
dep.raw_spec: str                # Original specification
dep.version_constraints: str     # Version constraints
dep.python_markers: str | None   # Python version markers
dep.extras: list[str]            # Requested extras
dep.source: str                  # Source location
dep.is_git_dependency: bool      # Is git dependency
dep.git_url: str | None          # Git URL
dep.git_ref: str | None          # Git ref (tag/branch/commit)
```

#### PythonVersion (Dataclass)

```python
from pyproj_dep_analyze import PythonVersion

# Create from string
pv = PythonVersion.from_string("3.11")

# Access components
pv.major  # 3
pv.minor  # 11

# Comparisons
pv < PythonVersion(3, 12)   # True
pv >= PythonVersion(3, 10)  # True

# String representation
str(pv)  # "3.11"
```

### Index Resolution

```python
from pyproj_dep_analyze import (
    IndexResolver,
    detect_configured_indexes,
    identify_index,
    IndexInfo,
    IndexType,
)

# Detect all configured indexes
indexes = detect_configured_indexes()
for idx in indexes:
    print(f"{idx.url} ({idx.index_type.value}, private={idx.is_private})")

# Identify index type from URL
info = identify_index("https://pypi.org/simple")
print(info.index_type)  # IndexType.PYPI

# Resolve which index serves a package
resolver = IndexResolver(indexes=indexes, timeout=30.0)
index_info = await resolver.resolve("requests")
```

### Repository Resolution

```python
from pyproj_dep_analyze import (
    RepoResolver,
    detect_repo_url,
    parse_repo_url,
    PyPIUrlMetadata,
)

# Parse repository URL
parsed = parse_repo_url("https://github.com/psf/requests")
print(f"{parsed.owner}/{parsed.name}")  # psf/requests

# Detect repo URL from PyPI metadata
urls = PyPIUrlMetadata(project_urls={"Source": "https://github.com/psf/requests"})
repo_url = detect_repo_url(urls)

# Fetch repository metadata
resolver = RepoResolver(github_token="ghp_xxx", timeout=30.0)
metadata = await resolver.resolve("psf", "requests")
print(f"Stars: {metadata.stars}")
```

### Complete API Reference

```python
from pyproj_dep_analyze import (
    # Main API Functions
    analyze_pyproject,       # Analyze pyproject.toml -> list[OutdatedEntry]
    run_enriched_analysis,   # Enriched analysis -> EnrichedAnalysisResult
    write_outdated_json,     # Write entries to JSON file
    write_enriched_json,     # Write enriched result to JSON file

    # Core Classes
    Analyzer,                # Stateful analyzer with caching
    IndexResolver,           # Package index resolver
    RepoResolver,            # Repository metadata resolver

    # Data Models (Pydantic)
    OutdatedEntry,           # Basic analysis entry
    AnalysisResult,          # Basic analysis result
    EnrichedAnalysisResult,  # Enriched analysis result
    EnrichedEntry,           # Enriched package entry
    PyPIMetadata,            # PyPI package metadata
    RepoMetadata,            # Repository metadata
    IndexInfo,               # Package index info

    # Data Models (Dataclass)
    DependencyInfo,          # Parsed dependency info
    PythonVersion,           # Python version representation

    # Enums
    Action,                  # update, delete, none, check_manually
    IndexType,               # pypi, testpypi, artifactory, etc.
    RepoType,                # github, gitlab, bitbucket, unknown
    CompatibilityStatus,     # compatible, excluded, unknown

    # Utility Functions
    detect_configured_indexes,  # Find all configured package indexes
    identify_index,            # Identify index type from URL
    detect_repo_url,           # Extract repo URL from PyPI metadata
    parse_repo_url,            # Parse owner/repo from URL
    get_config,                # Get layered configuration

    # Constants
    KNOWN_INDEX_PATTERNS,    # List of known index URL patterns
)
```

---

## Configuration

The application uses [lib_layered_config](https://github.com/bitranox/lib_layered_config) for hierarchical configuration.

### Configuration Precedence

From lowest to highest priority:

1. **Default config** (bundled `defaultconfig.toml`)
2. **Application config** (`/etc/xdg/pyproj-dep-analyze/config.toml`)
3. **Host config** (`/etc/pyproj-dep-analyze/hosts/{hostname}.toml`)
4. **User config** (`~/.config/pyproj-dep-analyze/config.toml`)
5. **`.env` files** (in current or parent directories)
6. **Environment variables** (`PYPROJ_DEP_ANALYZE_*`)
7. **CLI options** (highest priority)

### Analyzer Settings

| Setting | Description | Type | Default | Environment Variable |
|---------|-------------|------|---------|---------------------|
| `github_token` | GitHub API token for authentication | string | `""` (empty) | `PYPROJ_DEP_ANALYZE_GITHUB_TOKEN` |
| `timeout` | API request timeout in seconds | float | `30.0` | `PYPROJ_DEP_ANALYZE_TIMEOUT` |
| `concurrency` | Maximum concurrent API requests | integer | `10` | `PYPROJ_DEP_ANALYZE_CONCURRENCY` |

#### Why use a GitHub token?

| Mode | Rate Limit | Notes |
|------|------------|-------|
| Unauthenticated | 60 requests/hour | Easily exhausted with large projects |
| Authenticated | 5,000 requests/hour | Recommended for regular use |
| Required for | Private repositories | Token with `repo` scope needed |

#### Creating a GitHub Token

1. Go to https://github.com/settings/tokens
2. Click "Generate new token (classic)"
3. Select scope:
   - `public_repo` for public repositories only
   - `repo` for private repositories
4. Copy the token (starts with `ghp_`)

#### Examples

```bash
# Via environment variable (recommended)
PYPROJ_DEP_ANALYZE_GITHUB_TOKEN=ghp_xxx pyproj-dep-analyze analyze

# Via .env file
echo "PYPROJ_DEP_ANALYZE_GITHUB_TOKEN=ghp_xxx" >> .env
pyproj-dep-analyze analyze

# Via CLI option
pyproj-dep-analyze analyze --github-token ghp_xxx

# Other settings
PYPROJ_DEP_ANALYZE_TIMEOUT=60 pyproj-dep-analyze analyze
PYPROJ_DEP_ANALYZE_CONCURRENCY=20 pyproj-dep-analyze analyze
```

#### Alternative: lib_layered_config Format

Settings can also use the `SLUG___SECTION__KEY` format:

```bash
PYPROJ_DEP_ANALYZE___ANALYZER__GITHUB_TOKEN=ghp_xxxxx
PYPROJ_DEP_ANALYZE___ANALYZER__TIMEOUT=60.0
PYPROJ_DEP_ANALYZE___ANALYZER__CONCURRENCY=20
```

### Logging Settings

The application uses [lib_log_rich](https://github.com/bitranox/lib_log_rich) for structured logging.

#### Common Logging Variables

| Variable | Description | Values | Default |
|----------|-------------|--------|---------|
| `LOG_CONSOLE_LEVEL` | Console log level | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` | `INFO` |
| `LOG_CONSOLE_FORMAT_PRESET` | Console format | `full`, `short`, `full_loc`, `short_loc` | `full` |
| `LOG_CONSOLE_STREAM` | Output stream | `stdout`, `stderr`, `both`, `none` | `stderr` |
| `LOG_FORCE_COLOR` | Force ANSI colors | `true`, `false` | `false` |
| `LOG_NO_COLOR` | Disable colors | `true`, `false` | `false` |

#### Backend Logging (journald, Windows Event Log)

| Variable | Description | Default |
|----------|-------------|---------|
| `LOG_BACKEND_LEVEL` | Minimum level for system logging | `WARNING` |
| `LOG_ENABLE_JOURNALD` | Enable systemd journald (Linux) | `false` |
| `LOG_ENABLE_EVENTLOG` | Enable Windows Event Log | `false` |

#### Graylog / GELF

| Variable | Description | Default |
|----------|-------------|---------|
| `LOG_ENABLE_GRAYLOG` | Enable Graylog output | `false` |
| `LOG_GRAYLOG_ENDPOINT` | Graylog server (`host:port`) | - |
| `LOG_GRAYLOG_PROTOCOL` | Transport protocol | `tcp` |
| `LOG_GRAYLOG_TLS` | Use TLS for TCP | `false` |
| `LOG_GRAYLOG_LEVEL` | Minimum level for Graylog | `WARNING` |

#### Examples

```bash
# Debug logging
LOG_CONSOLE_LEVEL=DEBUG pyproj-dep-analyze analyze

# Minimal output
LOG_CONSOLE_FORMAT_PRESET=short pyproj-dep-analyze analyze

# Enable system logging (Linux)
LOG_ENABLE_JOURNALD=true pyproj-dep-analyze analyze
```

### Config File Locations

#### Linux (XDG)

```
User:  ~/.config/pyproj-dep-analyze/config.toml
App:   /etc/xdg/pyproj-dep-analyze/config.toml
Host:  /etc/pyproj-dep-analyze/hosts/{hostname}.toml
```

#### macOS

```
User:  ~/Library/Application Support/bitranox/Pyproj Dep Analyse/config.toml
App:   /Library/Application Support/bitranox/Pyproj Dep Analyse/config.toml
```

#### Windows

```
User:  %APPDATA%\bitranox\Pyproj Dep Analyse\config.toml
App:   %PROGRAMDATA%\bitranox\Pyproj Dep Analyse\config.toml
```

### .env File Support

Create a `.env` file in your project directory:

```bash
# .env
# Analyzer settings
PYPROJ_DEP_ANALYZE_GITHUB_TOKEN=ghp_xxxxx
PYPROJ_DEP_ANALYZE_TIMEOUT=60.0
PYPROJ_DEP_ANALYZE_CONCURRENCY=20

# Logging settings
LOG_CONSOLE_LEVEL=DEBUG
```

**Security Note:** Never commit `.env` files containing tokens to version control!

### Sample Configuration File

```toml
# ~/.config/pyproj-dep-analyze/config.toml

[analyzer]
# GitHub token (better to use env var for security)
# github_token = ""

# API request timeout in seconds
timeout = 30.0

# Maximum concurrent requests
concurrency = 10

# Logging configuration (optional)
# [lib_log_rich]
# console_level = "INFO"
# console_format_preset = "full"
```

---

## Output Formats

### Basic Analysis (`outdated.json`)

Array of `OutdatedEntry` objects:

```json
[
  {
    "package": "requests",
    "python_version": "3.11",
    "current_version": "2.28.0",
    "latest_version": "2.32.0",
    "action": "update",
    "note": "Package 'requests' can be updated from 2.28.0 to 2.32.0. Review the changelog for breaking changes before updating."
  }
]
```

### Enriched Analysis (`deps_enriched.json`)

Complete `EnrichedAnalysisResult` object with:
- Analysis metadata (timestamp, path, Python versions)
- Configured package indexes
- Enriched package entries with PyPI and repository metadata
- Dependency graph
- Summary statistics

See [analyze-enriched](#analyze-enriched---enriched-analysis) for full schema.

---

## Further Documentation

- [Install Guide](INSTALL.md) - Installation methods and requirements
- [Development Handbook](DEVELOPMENT.md) - Development setup and workflow
- [Contributor Guide](CONTRIBUTING.md) - How to contribute
- [Changelog](CHANGELOG.md) - Version history and changes
- [Module Reference](docs/systemdesign/module_reference.md) - Internal architecture
- [License](LICENSE) - MIT License
