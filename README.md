# pyproj_dep_analyse

<!-- Badges -->
[![CI](https://github.com/bitranox/pyproj_dep_analyse/actions/workflows/ci.yml/badge.svg)](https://github.com/bitranox/pyproj_dep_analyse/actions/workflows/ci.yml)
[![CodeQL](https://github.com/bitranox/pyproj_dep_analyse/actions/workflows/codeql.yml/badge.svg)](https://github.com/bitranox/pyproj_dep_analyse/actions/workflows/codeql.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Open in Codespaces](https://img.shields.io/badge/Codespaces-Open-blue?logo=github&logoColor=white&style=flat-square)](https://codespaces.new/bitranox/pyproj_dep_analyse?quickstart=1)
[![PyPI](https://img.shields.io/pypi/v/pyproj_dep_analyse.svg)](https://pypi.org/project/pyproj_dep_analyse/)
[![PyPI - Downloads](https://img.shields.io/pypi/dm/pyproj_dep_analyse.svg)](https://pypi.org/project/pyproj_dep_analyse/)
[![Code Style: Ruff](https://img.shields.io/badge/Code%20Style-Ruff-46A3FF?logo=ruff&labelColor=000)](https://docs.astral.sh/ruff/)
[![codecov](https://codecov.io/gh/bitranox/pyproj_dep_analyse/graph/badge.svg?token=UFBaUDIgRk)](https://codecov.io/gh/bitranox/pyproj_dep_analyse)
[![Maintainability](https://qlty.sh/badges/041ba2c1-37d6-40bb-85a0-ec5a8a0aca0c/maintainability.svg)](https://qlty.sh/gh/bitranox/projects/pyproj_dep_analyse)
[![Known Vulnerabilities](https://snyk.io/test/github/bitranox/pyproj_dep_analyse/badge.svg)](https://snyk.io/test/github/bitranox/pyproj_dep_analyse)
[![security: bandit](https://img.shields.io/badge/security-bandit-yellow.svg)](https://github.com/PyCQA/bandit)

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

- **Actionable Output**: For each dependency, recommends one of:
  - `update` - A newer compatible version exists
  - `delete` - Dependency should be removed for this Python version
  - `none` - Dependency is up to date
  - `check manually` - Manual verification required (e.g., GitHub packages without releases)

## Install

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
uv pip install pyproj_dep_analyse
```

### Alternative: Install via pip

```bash
pip install pyproj_dep_analyse
```

For additional installation methods (pipx, source builds, etc.), see [INSTALL.md](INSTALL.md).

Both `pyproj_dep_analyse` and `pyproj-dep-analyse` commands are registered on your PATH.

### Python 3.13+ Baseline

This project targets **Python 3.13 and newer only**.

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
pyproj-dep-analyse analyze [PYPROJECT_PATH] [OPTIONS]
```

#### Arguments

| Argument | Description | Default |
|----------|-------------|---------|
| `PYPROJECT_PATH` | Path to pyproject.toml file | `pyproject.toml` |

#### Options

| Option | Description | Env Variable | Default |
|--------|-------------|--------------|---------|
| `-o`, `--output PATH` | Output file path for JSON results | - | `outdated.json` |
| `--github-token TEXT` | GitHub token for API authentication | `PYPROJ_DEP_ANALYSE_GITHUB_TOKEN` | `None` |
| `--timeout FLOAT` | Request timeout in seconds for API calls | `PYPROJ_DEP_ANALYSE_TIMEOUT` | `30.0` |
| `--concurrency INTEGER` | Maximum concurrent API requests | `PYPROJ_DEP_ANALYSE_CONCURRENCY` | `10` |
| `--format TEXT` | Output format for display | - | `table` |

#### Output Formats

- **`table`** (default): Shows summary statistics plus lists of updates and manual checks
- **`summary`**: Shows only summary statistics (counts of updates, deletions, etc.)
- **`json`**: Outputs the full analysis as JSON to stdout

#### Examples

```bash
# Analyze pyproject.toml in current directory
pyproj-dep-analyse analyze

# Analyze a specific file
pyproj-dep-analyse analyze path/to/pyproject.toml

# Save results to custom file
pyproj-dep-analyse analyze -o my-results.json

# Use GitHub token for better rate limits
pyproj-dep-analyse analyze --github-token ghp_xxxxx
# Or via environment variable:
GITHUB_TOKEN=ghp_xxxxx pyproj-dep-analyse analyze

# Show only summary
pyproj-dep-analyse analyze --format summary

# Output as JSON
pyproj-dep-analyse analyze --format json

# Increase timeout for slow connections
pyproj-dep-analyse analyze --timeout 60

# Reduce concurrency to avoid rate limits
pyproj-dep-analyse analyze --concurrency 5
```

#### Output File Format (`outdated.json`)

The output file contains an array of entries, one per dependency per Python version:

```json
[
  {
    "package": "requests",
    "python_version": "3.11",
    "current_version": "2.28.0",
    "latest_version": "2.32.0",
    "action": "update"
  },
  {
    "package": "tomli",
    "python_version": "3.11",
    "current_version": "2.0.0",
    "latest_version": "2.0.0",
    "action": "delete"
  },
  {
    "package": "internal-tool",
    "python_version": "3.11",
    "current_version": null,
    "latest_version": "unknown",
    "action": "check manually"
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

### `config` - View Configuration

Display the current merged configuration from all sources.

```bash
pyproj-dep-analyse config [OPTIONS]
```

#### Options

| Option | Description | Values | Default |
|--------|-------------|--------|---------|
| `--format TEXT` | Output format | `human`, `json` | `human` |
| `--section TEXT` | Show only a specific configuration section | Any section name (e.g., `lib_log_rich`) | `None` (show all) |

#### Examples

```bash
# Show all configuration
pyproj-dep-analyse config

# Show as JSON for scripting
pyproj-dep-analyse config --format json

# Show only logging configuration
pyproj-dep-analyse config --section lib_log_rich
```

---

### `config-deploy` - Deploy Configuration Files

Deploy default configuration files to system or user directories.

```bash
pyproj-dep-analyse config-deploy --target TARGET [OPTIONS]
```

#### Options

| Option | Description | Values | Default |
|--------|-------------|--------|---------|
| `--target TARGET` | Target configuration layer(s). Can be specified multiple times. **Required.** | `app`, `host`, `user` | - |
| `--force` | Overwrite existing configuration files | Flag | `False` |

#### Target Locations

| Target | Linux | macOS | Windows |
|--------|-------|-------|---------|
| `user` | `~/.config/pyproj-dep-analyse/config.toml` | `~/Library/Application Support/bitranox/Pyproj Dep Analyse/config.toml` | `%APPDATA%\bitranox\Pyproj Dep Analyse\config.toml` |
| `app` | `/etc/xdg/pyproj-dep-analyse/config.toml` | `/Library/Application Support/bitranox/Pyproj Dep Analyse/config.toml` | `%PROGRAMDATA%\bitranox\Pyproj Dep Analyse\config.toml` |
| `host` | `/etc/pyproj-dep-analyse/hosts/{hostname}.toml` | Same as app | Same as app |

#### Examples

```bash
# Deploy to user config directory
pyproj-dep-analyse config-deploy --target user

# Deploy to system-wide location (requires privileges)
sudo pyproj-dep-analyse config-deploy --target app

# Deploy to multiple locations
pyproj-dep-analyse config-deploy --target user --target host

# Force overwrite existing config
pyproj-dep-analyse config-deploy --target user --force
```

---

### `info` - Show Package Information

Display package metadata including version, author, and installation details.

```bash
pyproj-dep-analyse info
```

---

### `hello` - Test Success Path

Emit a canonical greeting message. Used for testing and verification.

```bash
pyproj-dep-analyse hello
```

---

### `fail` - Test Failure Path

Trigger an intentional failure to test error handling and traceback display.

```bash
pyproj-dep-analyse fail
pyproj-dep-analyse --traceback fail  # Show full traceback
```

---

## Python API

The package can also be used as a library:

```python
from pyproj_dep_analyse import analyze_pyproject, OutdatedEntry, Action

# Analyze a pyproject.toml file
entries = analyze_pyproject("path/to/pyproject.toml")

# Filter by action
updates = [e for e in entries if e.action == Action.UPDATE.value]
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

### Available Classes and Functions

```python
from pyproj_dep_analyse import (
    # Main API
    analyze_pyproject,     # Analyze a pyproject.toml, returns list[OutdatedEntry]
    write_outdated_json,   # Write entries to JSON file
    Analyzer,              # Stateful analyzer with caching

    # Data classes
    OutdatedEntry,         # Analysis result for one dependency + Python version
    DependencyInfo,        # Parsed dependency information
    PythonVersion,         # Python version representation
    AnalysisResult,        # Complete analysis result with statistics
    Action,                # Enum: UPDATE, DELETE, NONE, CHECK_MANUALLY
)
```

---

## Configuration

The application uses [lib_layered_config](https://github.com/bitranox/lib_layered_config) for hierarchical configuration:

**Precedence (lowest to highest):** defaults → app → host → user → .env → environment variables

### Environment Variables

#### Analyzer Settings

| Variable | Description | Default |
|----------|-------------|---------|
| `PYPROJ_DEP_ANALYSE_GITHUB_TOKEN` | GitHub API token for authentication | `""` (unauthenticated) |
| `PYPROJ_DEP_ANALYSE_TIMEOUT` | API request timeout in seconds | `30.0` |
| `PYPROJ_DEP_ANALYSE_CONCURRENCY` | Maximum concurrent API requests | `10` |

**Why use a GitHub token?**
- Unauthenticated: 60 requests/hour (easily exhausted)
- Authenticated: 5,000 requests/hour
- Required for private repositories

```bash
# Set analyzer settings via environment
PYPROJ_DEP_ANALYSE_GITHUB_TOKEN=ghp_xxxxx pyproj-dep-analyse analyze
PYPROJ_DEP_ANALYSE_TIMEOUT=60 pyproj-dep-analyse analyze
PYPROJ_DEP_ANALYSE_CONCURRENCY=20 pyproj-dep-analyse analyze
```

#### Logging Settings (lib_log_rich)

| Variable | Description | Default |
|----------|-------------|---------|
| `LOG_CONSOLE_LEVEL` | Console log level | `INFO` |
| `LOG_CONSOLE_FORMAT_PRESET` | Console format | `full` |
| `LOG_ENABLE_GRAYLOG` | Enable Graylog output | `false` |

```bash
# Set logging level
LOG_CONSOLE_LEVEL=DEBUG pyproj-dep-analyse analyze
```

#### Alternative: lib_layered_config Format

Settings can also use the `SLUG___SECTION__KEY` format:

```bash
# Analyzer settings
PYPROJ_DEP_ANALYSE___ANALYZER__GITHUB_TOKEN=ghp_xxxxx
PYPROJ_DEP_ANALYSE___ANALYZER__TIMEOUT=60.0

# Logging settings
PYPROJ_DEP_ANALYSE___LIB_LOG_RICH__CONSOLE_LEVEL=DEBUG
```

### .env File Support

Create a `.env` file in your project directory:

```bash
# .env
# Analyzer settings
PYPROJ_DEP_ANALYSE_GITHUB_TOKEN=ghp_xxxxx
PYPROJ_DEP_ANALYSE_TIMEOUT=60.0
PYPROJ_DEP_ANALYSE_CONCURRENCY=20

# Logging settings
LOG_CONSOLE_LEVEL=DEBUG
```

**Note:** Never commit `.env` files containing tokens to version control!

---

## Further Documentation

- [Install Guide](INSTALL.md)
- [Development Handbook](DEVELOPMENT.md)
- [Contributor Guide](CONTRIBUTING.md)
- [Changelog](CHANGELOG.md)
- [Module Reference](docs/systemdesign/module_reference.md)
- [License](LICENSE)
