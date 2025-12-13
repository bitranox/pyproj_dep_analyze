# pyproj_dep_analyze

<!-- Badges -->
[![CI](https://github.com/bitranox/pyproj_dep_analyze/actions/workflows/ci.yml/badge.svg)](https://github.com/bitranox/pyproj_dep_analyze/actions/workflows/ci.yml)
[![CodeQL](https://github.com/bitranox/pyproj_dep_analyze/actions/workflows/codeql.yml/badge.svg)](https://github.com/bitranox/pyproj_dep_analyze/actions/workflows/codeql.yml)
[![codecov](https://codecov.io/gh/bitranox/pyproj_dep_analyze/graph/badge.svg?token=UFBaUDIgRk)](https://codecov.io/gh/bitranox/pyproj_dep_analyze)
[![PyPI](https://img.shields.io/pypi/v/pyproj_dep_analyze.svg)](https://pypi.org/project/pyproj_dep_analyze/)
[![PyPI - Downloads](https://img.shields.io/pypi/dm/pyproj_dep_analyze.svg)](https://pypi.org/project/pyproj_dep_analyze/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Open in Codespaces](https://img.shields.io/badge/Codespaces-Open-blue?logo=github&logoColor=white&style=flat-square)](https://codespaces.new/bitranox/pyproj_dep_analyze?quickstart=1)
[![Code Style: Ruff](https://img.shields.io/badge/Code%20Style-Ruff-46A3FF?logo=ruff&labelColor=000)](https://docs.astral.sh/ruff/)
[![Maintainability](https://qlty.sh/badges/041ba2c1-37d6-40bb-85a0-ec5a8a0aca0c/maintainability.svg)](https://qlty.sh/gh/bitranox/projects/pyproj_dep_analyze)
[![Known Vulnerabilities](https://snyk.io/test/github/bitranox/pyproj_dep_analyze/badge.svg)](https://snyk.io/test/github/bitranox/pyproj_dep_analyze)
[![security: bandit](https://img.shields.io/badge/security-bandit-yellow.svg)](https://github.com/PyCQA/bandit)

**Parses `pyproject.toml` to generate actionable dependency data for security audits, update automation, and LLM-powered code review.**

---

## Why pyproj_dep_analyze?

**AI-assisted "vibe coding" creates apps fast, but dependencies are often unvetted.**

When developers build applications rapidly with AI assistance, the focus is on functionality, not supply chain security. Dependencies get added without scrutiny, creating blind spots that attackers exploit:

| Attack Vector | Description |
|--------------|-------------|
| **Typosquatting** | Malicious packages with names similar to popular ones (`reqeusts` vs `requests`) |
| **Dependency Confusion** | Private package names hijacked on public PyPI |
| **Malicious Updates** | Legitimate packages compromised via maintainer account takeover |
| **Abandoned Package Takeover** | Unmaintained packages acquired by bad actors |
| **Protestware / Sabotage** | Maintainers intentionally breaking their own packages |
| **Hidden Malware** | Obfuscated code in install scripts or deep dependencies |

`pyproj_dep_analyze` provides **visibility into your dependency landscape**, generating structured data that feeds into security workflows:

```
pyproj_dep_analyze  →  pyproj_dep_security  →  pyproj_dep_update
     (analyze)            (scan & audit)         (remediate)
```

- **`pyproj_dep_analyze`** - Extracts and enriches dependency metadata from `pyproject.toml`
- **`pyproj_dep_security`** - Scans installed environments for vulnerabilities and supply chain risks
- **`pyproj_dep_update`** - Applies fixes by updating `pyproject.toml` based on security findings

> **Know your dependencies before they become your vulnerabilities.**

---

## Table of Contents

- [Why pyproj_dep_analyze?](#why-pyproj_dep_analyze)
- [Overview](#overview)
- [Scope & Boundaries](#scope--boundaries)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [CLI Reference](#cli-reference)
- [Python API](#python-api)
- [Data Models](#data-models)
- [Configuration](#configuration)
- [Output Examples](#output-examples)
- [Further Documentation](#further-documentation)

---

## Overview

`pyproj_dep_analyze` analyzes Python project dependencies declared in `pyproject.toml` files:

- **Parses** dependencies from PEP 621, Poetry, PDM, and Hatch formats
- **Checks** for newer versions on PyPI and GitHub
- **Enriches** with metadata: license, stars, release dates, download stats
- **Outputs** structured JSON with human/LLM-readable recommendations

---

## Scope & Boundaries

### What `pyproj_dep_analyze` Does

| Capability               | Description                                                    |
|--------------------------|----------------------------------------------------------------|
| **Parse pyproject.toml** | Extract dependencies from PEP 621, Poetry, PDM, Hatch formats  |
| **Check for updates**    | Query PyPI/GitHub for latest compatible versions               |
| **Enrich with metadata** | License, stars, forks, release dates, maintainers              |
| **Version metrics**      | Release frequency, project age, abandonment indicators         |
| **Download statistics**  | Popularity metrics from pypistats.org                          |
| **Index detection**      | Identify which package index serves each dependency            |
| **Direct dependencies**  | Extract immediate dependencies from `requires_dist`            |

### What Belongs in `pyproj_dep_security` (Separate Project)

| Capability                          | Reason                                               |
|-------------------------------------|------------------------------------------------------|
| **Full transitive dependency tree** | Requires installed environment (pipdeptree)          |
| **Vulnerability scanning**          | Security-specific (OSV, Safety DB, Snyk integration) |
| **License compliance checking**     | Policy enforcement, not metadata                     |
| **Dependency confusion detection**  | Active security scanning                             |
| **Supply chain risk scoring**       | Requires vulnerability data + heuristics             |
| **Typosquatting detection**         | Requires name similarity analysis                    |

### What Belongs in `pyproj_dep_update` (Separate Project)

| Capability                    | Reason                                                |
|-------------------------------|-------------------------------------------------------|
| **Update pyproject.toml**     | Modifies project files (write operation)              |
| **Pin indirect dependencies** | Add transitive deps with CVEs to explicit deps        |
| **CVE-driven version bumps**  | Requires vulnerability scan results (Bandit/OSV)      |
| **Generate constraints.txt**  | Create pip constraints for indirect deps              |
| **Batch update operations**   | Update all / security-only / major/minor/patch        |
| **Lock file regeneration**    | Update poetry.lock, pdm.lock, uv.lock after changes   |
| **Update local libraries**    | Bump versions of local/workspace dependencies         |

> **Design Principle:**
> - `pyproj_dep_analyze` analyzes *declared* dependencies from project files
> - `pyproj_dep_security` analyzes *installed* environments (in a venv) for security issues
> - `pyproj_dep_update` *modifies* pyproject.toml based on analysis and security scan results

---

## Installation

### Via UV (Recommended)

```bash
uv pip install pyproj_dep_analyze
```

### Via pip

```bash
pip install pyproj_dep_analyze
```

**Requirements:** Python 3.10+

Both `pyproj_dep_analyze` and `pyproj-dep-analyze` commands are available after installation.

---

## Quick Start

```bash
# Basic analysis
pyproj-dep-analyze analyze

# Enriched analysis with full metadata
pyproj-dep-analyze analyze-enriched

# View configuration
pyproj-dep-analyze config

# Show package info
pyproj-dep-analyze info
```

---

## CLI Reference

### Global Options

| Option                        | Description                         | Default           |
|-------------------------------|-------------------------------------|-------------------|
| `--traceback / --no-traceback`| Show full Python traceback on errors| `--no-traceback`  |
| `-h, --help`                  | Show help message                   | -                 |
| `--version`                   | Show version and exit               | -                 |

---

### `analyze` - Analyze Dependencies

Analyze `pyproject.toml` and determine outdated dependencies for each Python version.

```bash
pyproj-dep-analyze analyze [PYPROJECT_PATH] [OPTIONS]
```

#### Arguments

| Argument         | Description                  | Default           |
|------------------|------------------------------|-------------------|
| `PYPROJECT_PATH` | Path to pyproject.toml file  | `pyproject.toml`  |

#### Options

| Option              | Description                        | Env Variable                                           | Default          |
|---------------------|------------------------------------|--------------------------------------------------------|------------------|
| `-o, --output`      | Output file path                   | -                                                      | `outdated.json`  |
| `--github-token`    | GitHub API token                   | `GITHUB_TOKEN`, `PYPROJ_DEP_ANALYZE_GITHUB_TOKEN`      | `None`           |
| `--timeout`         | Request timeout (seconds)          | `PYPROJ_DEP_ANALYZE_TIMEOUT`                           | `30.0`           |
| `--concurrency`     | Max concurrent API requests        | `PYPROJ_DEP_ANALYZE_CONCURRENCY`                       | `10`             |
| `--format`          | Output format                      | -                                                      | `table`          |

**Format Options:**

| Format    | Description                                              |
|-----------|----------------------------------------------------------|
| `table`   | Summary statistics + lists of updates and manual checks  |
| `summary` | Only summary statistics                                  |
| `json`    | Full analysis as JSON to stdout                          |

#### Examples

```bash
# Analyze current directory
pyproj-dep-analyze analyze

# Analyze specific file
pyproj-dep-analyze analyze path/to/pyproject.toml

# Custom output file
pyproj-dep-analyze analyze -o results.json

# With GitHub token (for better rate limits)
pyproj-dep-analyze analyze --github-token ghp_xxxxx
GITHUB_TOKEN=ghp_xxxxx pyproj-dep-analyze analyze

# Output formats
pyproj-dep-analyze analyze --format summary
pyproj-dep-analyze analyze --format json

# Custom timeout and concurrency
pyproj-dep-analyze analyze --timeout 60 --concurrency 5
```

---

### `analyze-enriched` - Enriched Analysis

Analyze with full metadata enrichment including PyPI info, repository data, and dependency graphs.

```bash
pyproj-dep-analyze analyze-enriched [PYPROJECT_PATH] [OPTIONS]
```

#### Arguments

| Argument         | Description                  | Default           |
|------------------|------------------------------|-------------------|
| `PYPROJECT_PATH` | Path to pyproject.toml file  | `pyproject.toml`  |

#### Options

| Option              | Description                        | Env Variable                                           | Default              |
|---------------------|------------------------------------|--------------------------------------------------------|----------------------|
| `-o, --output`      | Output file path                   | -                                                      | `deps_enriched.json` |
| `--github-token`    | GitHub API token                   | `GITHUB_TOKEN`, `PYPROJ_DEP_ANALYZE_GITHUB_TOKEN`      | `None`               |
| `--timeout`         | Request timeout (seconds)          | `PYPROJ_DEP_ANALYZE_TIMEOUT`                           | `30.0`               |
| `--concurrency`     | Max concurrent API requests        | `PYPROJ_DEP_ANALYZE_CONCURRENCY`                       | `10`                 |

#### Examples

```bash
# Enriched analysis
pyproj-dep-analyze analyze-enriched

# Custom output file
pyproj-dep-analyze analyze-enriched -o analysis.json

# With GitHub token for repository metadata
GITHUB_TOKEN=ghp_xxx pyproj-dep-analyze analyze-enriched
```

---

### `config` - View Configuration

Display the current merged configuration from all sources.

```bash
pyproj-dep-analyze config [OPTIONS]
```

#### Options

| Option      | Description                    | Values              | Default  |
|-------------|--------------------------------|---------------------|----------|
| `--format`  | Output format                  | `human`, `json`     | `human`  |
| `--section` | Show specific section only     | e.g., `analyzer`    | `None`   |

#### Examples

```bash
pyproj-dep-analyze config
pyproj-dep-analyze config --format json
pyproj-dep-analyze config --section analyzer
```

---

### `config-deploy` - Deploy Configuration

Deploy default configuration files to system or user directories.

```bash
pyproj-dep-analyze config-deploy --target TARGET [OPTIONS]
```

#### Options

| Option     | Description                              | Values                | Default  |
|------------|------------------------------------------|-----------------------|----------|
| `--target` | Target layer(s) - can be repeated        | `app`, `host`, `user` | Required |
| `--force`  | Overwrite existing files                 | Flag                  | `False`  |

#### Target Locations

| Target | Linux                                        | macOS / Windows                      |
|--------|----------------------------------------------|--------------------------------------|
| `user` | `~/.config/pyproj-dep-analyze/config.toml`   | Platform-specific user config        |
| `app`  | `/etc/xdg/pyproj-dep-analyze/config.toml`    | Platform-specific system config      |
| `host` | `/etc/pyproj-dep-analyze/hosts/{hostname}.toml` | Same as app                       |

#### Examples

```bash
pyproj-dep-analyze config-deploy --target user
pyproj-dep-analyze config-deploy --target user --force
sudo pyproj-dep-analyze config-deploy --target app
```

---

### `info` - Package Information

Display package metadata including version and installation details.

```bash
pyproj-dep-analyze info
```

---

### `hello` / `fail` - Test Commands

Commands for testing CLI success and failure paths.

```bash
pyproj-dep-analyze hello                    # Success path
pyproj-dep-analyze fail                     # Failure path
pyproj-dep-analyze --traceback fail         # With full traceback
```

---

## Python API

### Main Functions

#### `analyze_pyproject()`

Analyze a pyproject.toml file and return outdated entries.

```python
from pyproj_dep_analyze import analyze_pyproject, OutdatedEntry, Action

entries: list[OutdatedEntry] = analyze_pyproject(
    "pyproject.toml",           # Path to pyproject.toml (required)
    github_token=None,          # GitHub API token (default: None)
    timeout=30.0,               # Request timeout in seconds (default: 30.0)
    concurrency=10,             # Max concurrent requests (default: 10)
)

# Filter results
updates = [e for e in entries if e.action == Action.UPDATE]
for entry in updates:
    print(f"{entry.package}: {entry.current_version} -> {entry.latest_version}")
```

#### `run_enriched_analysis()`

Analyze with full metadata enrichment.

```python
from pyproj_dep_analyze import run_enriched_analysis, write_enriched_json

result = run_enriched_analysis(
    "pyproject.toml",           # Path to pyproject.toml (required)
    github_token=None,          # GitHub API token (default: None)
    timeout=30.0,               # Request timeout in seconds (default: 30.0)
    concurrency=10,             # Max concurrent requests (default: 10)
)

# Access results
print(f"Total: {result.summary.total_packages}")
print(f"Updates: {result.summary.updates_available}")

for pkg in result.packages:
    print(f"{pkg.name}: {pkg.action.value}")
    if pkg.pypi_metadata:
        print(f"  License: {pkg.pypi_metadata.license}")
    if pkg.repo_metadata:
        print(f"  Stars: {pkg.repo_metadata.stars}")

# Save to file
write_enriched_json(result, "analysis.json")
```

#### `write_outdated_json()` / `write_enriched_json()`

Write analysis results to JSON files.

```python
from pyproj_dep_analyze import (
    analyze_pyproject,
    run_enriched_analysis,
    write_outdated_json,
    write_enriched_json,
)

# Basic analysis
entries = analyze_pyproject("pyproject.toml")
write_outdated_json(entries, "outdated.json")

# Enriched analysis
result = run_enriched_analysis("pyproject.toml")
write_enriched_json(result, "deps_enriched.json")
```

---

### Analyzer Class

For more control, use the `Analyzer` class directly.

```python
from pyproj_dep_analyze import Analyzer
from pathlib import Path

analyzer = Analyzer(
    github_token="ghp_xxxxx",   # GitHub API token (default: None)
    timeout=60.0,               # Request timeout in seconds (default: 30.0)
    concurrency=20,             # Max concurrent requests (default: 10)
)

# Basic analysis
result = analyzer.analyze(Path("pyproject.toml"))
for entry in result.entries:
    print(f"{entry.package}: {entry.action.value}")

# Enriched analysis
enriched = analyzer.analyze_enriched(Path("pyproject.toml"))
```

---

### Index Resolution

Detect and resolve package indexes.

```python
from pyproj_dep_analyze import (
    IndexResolver,
    detect_configured_indexes,
    identify_index,
)

# Detect all configured indexes
indexes = detect_configured_indexes()
for idx in indexes:
    print(f"{idx.url} ({idx.index_type.value}, private={idx.is_private})")

# Identify index type from URL
info = identify_index("https://pypi.org/simple")
print(info.index_type)  # IndexType.PYPI

# Resolve which index serves a package (async)
resolver = IndexResolver(indexes=indexes, timeout=30.0)
index_info = await resolver.resolve("requests")
```

---

### Repository Resolution

Resolve repository metadata from URLs.

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

# Fetch repository metadata (async)
resolver = RepoResolver(github_token="ghp_xxx", timeout=30.0)
metadata = await resolver.resolve("psf", "requests")
print(f"Stars: {metadata.stars}")
```

---

### Download Statistics

Fetch download statistics from pypistats.org.

```python
from pyproj_dep_analyze import StatsResolver

resolver = StatsResolver(timeout=15.0)

# Fetch stats for a single package (async)
stats = await resolver.fetch_stats_async("requests")
if stats:
    print(f"Last month: {stats.last_month_downloads}")
    print(f"Last week: {stats.last_week_downloads}")

# Fetch stats for multiple packages (async)
results = await resolver.fetch_many_async(
    ["requests", "httpx", "pydantic"],
    concurrency=5,
)
```

---

## Data Models

### Enums

#### `Action`

```python
from pyproj_dep_analyze import Action

Action.UPDATE          # "update" - newer version exists
Action.DELETE          # "delete" - remove for this Python version
Action.NONE            # "none" - up to date
Action.CHECK_MANUALLY  # "check manually" - needs manual verification
```

---

### Analysis Results

#### `OutdatedEntry`

Basic analysis entry for a single dependency.

| Field             | Type             | Description                        |
|-------------------|------------------|------------------------------------|
| `package`         | `str`            | Package name                       |
| `python_version`  | `str`            | Python version (e.g., "3.11")      |
| `current_version` | `str \| None`    | Currently specified version        |
| `latest_version`  | `str \| None`    | Latest available version           |
| `action`          | `Action`         | Recommended action                 |
| `note`            | `str`            | Human/LLM-readable explanation     |

#### `AnalysisResult`

Complete result from basic analysis.

| Field                  | Type                  | Description                    |
|------------------------|-----------------------|--------------------------------|
| `entries`              | `list[OutdatedEntry]` | All analysis entries           |
| `python_versions`      | `list[str]`           | Python versions analyzed       |
| `total_dependencies`   | `int`                 | Total unique dependencies      |
| `update_count`         | `int`                 | Dependencies needing updates   |
| `delete_count`         | `int`                 | Dependencies to delete         |
| `check_manually_count` | `int`                 | Needs manual check             |

#### `EnrichedAnalysisResult`

Complete result from enriched analysis.

| Field                | Type                        | Description                   |
|----------------------|-----------------------------|-------------------------------|
| `analyzed_at`        | `str`                       | ISO timestamp                 |
| `pyproject_path`     | `str`                       | Analyzed file path            |
| `python_versions`    | `list[str]`                 | Python versions               |
| `indexes_configured` | `list[IndexInfo]`           | Package indexes               |
| `packages`           | `list[EnrichedEntry]`       | Enriched entries              |
| `dependency_graph`   | `dict[str, list[str]]`      | Dependencies                  |
| `summary`            | `EnrichedSummary`           | Statistics                    |

#### `EnrichedEntry`

Enriched package entry with full metadata.

| Field                  | Type                                   | Description                 |
|------------------------|----------------------------------------|-----------------------------|
| `name`                 | `str`                                  | Package name                |
| `requested_version`    | `str \| None`                          | Version constraint          |
| `resolved_version`     | `str \| None`                          | Resolved version            |
| `latest_version`       | `str \| None`                          | Latest version              |
| `action`               | `Action`                               | Recommended action          |
| `source`               | `str`                                  | Where declared              |
| `index_info`           | `IndexInfo \| None`                    | Package index               |
| `python_compatibility` | `dict[str, CompatibilityStatus]`       | Per-version compatibility   |
| `pypi_metadata`        | `PyPIMetadata \| None`                 | PyPI data                   |
| `repo_metadata`        | `RepoMetadata \| None`                 | Repository data             |
| `direct_dependencies`  | `list[str]`                            | Direct deps                 |

---

### Metadata Models

#### `PyPIMetadata`

| Field                 | Type                        | Description                    |
|-----------------------|-----------------------------|--------------------------------|
| `summary`             | `str \| None`               | One-line description           |
| `license`             | `str \| None`               | SPDX license                   |
| `home_page`           | `str \| None`               | Project URL                    |
| `project_urls`        | `dict[str, str]`            | Labeled URLs                   |
| `author`              | `str \| None`               | Author name                    |
| `author_email`        | `str \| None`               | Author email                   |
| `maintainer`          | `str \| None`               | Maintainer name                |
| `maintainer_email`    | `str \| None`               | Maintainer email               |
| `available_versions`  | `list[str]`                 | All versions                   |
| `first_release_date`  | `str \| None`               | First release ISO date         |
| `latest_release_date` | `str \| None`               | Latest release ISO date        |
| `requires_python`     | `str \| None`               | Python constraint              |
| `requires_dist`       | `list[str]`                 | Dependency specs               |
| `version_metrics`     | `VersionMetrics \| None`    | Release pattern metrics        |
| `download_stats`      | `DownloadStats \| None`     | Download statistics            |

#### `VersionMetrics`

Computed metrics from version history for quality assessment.

| Field                       | Type            | Description                           |
|-----------------------------|-----------------|---------------------------------------|
| `release_count`             | `int`           | Total number of releases              |
| `latest_release_age_days`   | `int \| None`   | Days since latest release             |
| `first_release_age_days`    | `int \| None`   | Project age in days                   |
| `avg_days_between_releases` | `float \| None` | Average release frequency             |
| `min_days_between_releases` | `int \| None`   | Shortest gap (detect rapid releases)  |
| `max_days_between_releases` | `int \| None`   | Longest gap (detect abandonment)      |
| `releases_last_year`        | `int`           | Recent activity indicator             |
| `release_dates`             | `list[str]`     | All release timestamps                |

#### `DownloadStats`

Download statistics from pypistats.org.

| Field                  | Type           | Description              |
|------------------------|----------------|--------------------------|
| `total_downloads`      | `int \| None`  | Lifetime downloads       |
| `last_month_downloads` | `int \| None`  | Last 30 days             |
| `last_week_downloads`  | `int \| None`  | Last 7 days              |
| `last_day_downloads`   | `int \| None`  | Last 24 hours            |
| `fetched_at`           | `str \| None`  | When stats were retrieved|

#### `RepoMetadata`

| Field              | Type           | Description              |
|--------------------|----------------|--------------------------|
| `repo_type`        | `RepoType`     | github, gitlab, etc.     |
| `url`              | `str \| None`  | Repository URL           |
| `owner`            | `str \| None`  | Owner/organization       |
| `name`             | `str \| None`  | Repository name          |
| `stars`            | `int \| None`  | Star count               |
| `forks`            | `int \| None`  | Fork count               |
| `open_issues`      | `int \| None`  | Open issue count         |
| `default_branch`   | `str \| None`  | Default branch           |
| `last_commit_date` | `str \| None`  | Last commit ISO date     |
| `created_at`       | `str \| None`  | Creation ISO date        |
| `description`      | `str \| None`  | Repository description   |

#### `IndexInfo`

| Field        | Type        | Description                          |
|--------------|-------------|--------------------------------------|
| `url`        | `str`       | Index URL                            |
| `index_type` | `IndexType` | pypi, testpypi, artifactory, etc.    |
| `is_private` | `bool`      | Whether private/internal             |

---

### Utility Models

#### `DependencyInfo`

Parsed dependency information.

| Field                 | Type           | Description                |
|-----------------------|----------------|----------------------------|
| `name`                | `str`          | Normalized package name    |
| `raw_spec`            | `str`          | Original specification     |
| `version_constraints` | `str`          | Version constraints        |
| `python_markers`      | `str \| None`  | Python version markers     |
| `extras`              | `list[str]`    | Requested extras           |
| `source`              | `str`          | Source location            |
| `is_git_dependency`   | `bool`         | Is git dependency          |
| `git_url`             | `str \| None`  | Git URL                    |
| `git_ref`             | `str \| None`  | Git ref (tag/branch/commit)|

#### `PythonVersion`

```python
from pyproj_dep_analyze import PythonVersion

pv = PythonVersion.from_string("3.11")
pv.major  # 3
pv.minor  # 11
str(pv)   # "3.11"

# Comparisons
pv < PythonVersion(3, 12)   # True
pv >= PythonVersion(3, 10)  # True
```

---

## Configuration

### Configuration Precedence (lowest to highest)

1. Default config (bundled)
2. Application config (`/etc/xdg/pyproj-dep-analyze/config.toml`)
3. Host config (`/etc/pyproj-dep-analyze/hosts/{hostname}.toml`)
4. User config (`~/.config/pyproj-dep-analyze/config.toml`)
5. `.env` files
6. Environment variables (`PYPROJ_DEP_ANALYZE_*`)
7. CLI options

### Analyzer Settings

| Setting        | Type    | Default | Environment Variable                 |
|----------------|---------|---------|--------------------------------------|
| `github_token` | string  | `""`    | `PYPROJ_DEP_ANALYZE_GITHUB_TOKEN`    |
| `timeout`      | float   | `30.0`  | `PYPROJ_DEP_ANALYZE_TIMEOUT`         |
| `concurrency`  | integer | `10`    | `PYPROJ_DEP_ANALYZE_CONCURRENCY`     |

### GitHub Token

| Mode              | Rate Limit         | Notes                            |
|-------------------|--------------------|----------------------------------|
| Unauthenticated   | 60 requests/hour   | Easily exhausted                 |
| Authenticated     | 5,000 requests/hour| Recommended for regular use      |

### Sample Config File

```toml
# ~/.config/pyproj-dep-analyze/config.toml

[analyzer]
timeout = 30.0
concurrency = 10
# github_token = ""  # Use env var instead
```

### Sample .env File

```bash
PYPROJ_DEP_ANALYZE_GITHUB_TOKEN=ghp_xxxxx
PYPROJ_DEP_ANALYZE_TIMEOUT=60.0
PYPROJ_DEP_ANALYZE_CONCURRENCY=20
LOG_CONSOLE_LEVEL=DEBUG
```

---

## Output Examples

### `outdated.json`

```json
[
  {
    "package": "requests",
    "python_version": "3.11",
    "current_version": "2.28.0",
    "latest_version": "2.32.0",
    "action": "update",
    "note": "Package 'requests' can be updated from 2.28.0 to 2.32.0."
  },
  {
    "package": "tomli",
    "python_version": "3.11",
    "current_version": "2.0.0",
    "latest_version": null,
    "action": "delete",
    "note": "Package 'tomli' has a Python version marker that excludes Python 3.11."
  }
]
```

### `deps_enriched.json`

```json
{
  "analyzed_at": "2025-12-04T10:30:00Z",
  "pyproject_path": "pyproject.toml",
  "python_versions": ["3.11", "3.12", "3.13"],
  "indexes_configured": [
    {"url": "https://pypi.org/simple", "index_type": "pypi", "is_private": false}
  ],
  "summary": {
    "total_packages": 25,
    "updates_available": 5,
    "up_to_date": 18,
    "check_manually": 2,
    "from_pypi": 23,
    "from_private_index": 2
  },
  "packages": [
    {
      "name": "requests",
      "requested_version": ">=2.28.0",
      "latest_version": "2.32.0",
      "action": "update",
      "pypi_metadata": {
        "license": "Apache-2.0",
        "latest_release_date": "2024-05-29T...",
        "version_metrics": {
          "release_count": 150,
          "latest_release_age_days": 180,
          "releases_last_year": 5
        }
      },
      "repo_metadata": {
        "stars": 52345,
        "forks": 9234
      }
    }
  ]
}
```

---

## Further Documentation

- [Install Guide](INSTALL.md)
- [Development Handbook](DEVELOPMENT.md)
- [Contributor Guide](CONTRIBUTING.md)
- [Changelog](CHANGELOG.md)
- [License](LICENSE) - MIT
