# Claude Code Guidelines for pyproj_dep_analyze

## Session Initialization

When starting a new session, read and apply the following system prompt files from `/media/srv-main-softdev/projects/softwarestack/systemprompts`:

### Core Guidelines (Always Apply)
- `core_programming_solid.md`

### Bash-Specific Guidelines
When working with Bash scripts:
- `core_programming_solid.md`
- `bash_clean_architecture.md`
- `bash_clean_code.md`
- `bash_small_functions.md`

### Python-Specific Guidelines
When working with Python code:
- `core_programming_solid.md`
- `python_solid_architecture_enforcer.md`
- `python_clean_architecture.md`
- `python_clean_code.md`
- `python_small_functions_style.md`
- `python_libraries_to_use.md`
- `python_structure_template.md`

### Additional Guidelines
- `self_documenting.md`
- `self_documenting_template.md`
- `python_jupyter_notebooks.md`
- `python_testing.md`

## Project Structure

```
pyproj_dep_analyze/
├── .github/
│   └── workflows/              # GitHub Actions CI/CD workflows
├── .devcontainer/              # Dev container configuration
├── docs/                       # Project documentation
│   ├── dataflow.md             # Data flow documentation
│   └── systemdesign/           # System design documents
│       └── module_reference.md # Module reference documentation
├── notebooks/                  # Jupyter notebooks for experiments
├── scripts/                    # Build and automation scripts
│   ├── build.py               # Build wheel/sdist
│   ├── bump.py                # Version bump (generic)
│   ├── bump_major.py          # Bump major version
│   ├── bump_minor.py          # Bump minor version
│   ├── bump_patch.py          # Bump patch version
│   ├── bump_version.py        # Version bump utilities
│   ├── clean.py               # Clean build artifacts
│   ├── cli.py                 # CLI for scripts
│   ├── dependencies.py        # Dependency management
│   ├── dev.py                 # Development install
│   ├── help.py                # Show help
│   ├── install.py             # Install package
│   ├── menu.py                # Interactive TUI menu
│   ├── push.py                # Git push
│   ├── release.py             # Create releases
│   ├── run_cli.py             # Run CLI
│   ├── target_metadata.py     # Metadata generation
│   ├── test.py                # Run tests with coverage
│   ├── toml_config.py         # TOML configuration utilities
│   ├── version_current.py     # Print current version
│   └── _utils.py              # Shared utilities
├── src/
│   └── pyproj_dep_analyze/    # Main Python package
│       ├── __init__.py        # Package initialization
│       ├── __init__conf__.py  # Configuration constants
│       ├── __main__.py        # CLI entry point
│       ├── analyzer.py        # Core dependency analysis orchestration
│       ├── behaviors.py       # Behavior definitions
│       ├── cli.py             # CLI implementation (rich-click)
│       ├── cli_display.py     # CLI display/output formatting
│       ├── config.py          # Configuration management
│       ├── config_deploy.py   # Configuration deployment
│       ├── config_show.py     # Configuration display
│       ├── defaultconfig.toml # Default configuration file
│       ├── dependency_extractor.py  # Extract dependencies from pyproject.toml
│       ├── index_resolver.py  # Resolve package info from PyPI
│       ├── logging_setup.py   # Logging configuration
│       ├── models.py          # Data models (Pydantic)
│       ├── py.typed           # PEP 561 marker
│       ├── python_version_parser.py  # Python version requirement parsing
│       ├── repo_resolver.py   # Resolve repository info from PyPI
│       ├── schemas.py         # Schema definitions
│       ├── stats_resolver.py  # Statistics resolution
│       └── version_resolver.py  # Version comparison and resolution
├── tests/                     # Test suite
│   ├── conftest.py            # Pytest fixtures
│   ├── test_analyzer.py       # Analyzer tests
│   ├── test_behaviors.py      # Behavior tests
│   ├── test_cli.py            # CLI tests
│   ├── test_config.py         # Configuration tests
│   ├── test_config_deploy.py  # Config deployment tests
│   ├── test_config_show.py    # Config show tests
│   ├── test_e2e_analysis.py   # End-to-end tests
│   ├── test_index_resolver.py # Index resolver tests
│   ├── test_integration.py    # Integration tests
│   ├── test_logging_setup.py  # Logging setup tests
│   ├── test_metadata.py       # Metadata tests
│   ├── test_module_entry.py   # Module entry tests
│   ├── test_repo_resolver.py  # Repo resolver tests
│   ├── test_scripts.py        # Scripts tests
│   └── test_version_resolver.py  # Version resolver tests
├── .env.example               # Example environment variables
├── CLAUDE.md                  # Claude Code guidelines (this file)
├── CHANGELOG.md               # Version history
├── CONTRIBUTING.md            # Contribution guidelines
├── DEVELOPMENT.md             # Development setup guide
├── INSTALL.md                 # Installation instructions
├── LICENSE                    # MIT License
├── Makefile                   # Make targets for common tasks
├── PRD.md                     # Product requirements document
├── pyproject.toml             # Project metadata & dependencies
├── codecov.yml                # Codecov configuration
└── README.md                  # Project overview
```

## Versioning & Releases

- **Single Source of Truth**: Package version is in `pyproject.toml` (`[project].version`)
- **Version Bumps**: update `pyproject.toml`, `CHANGELOG.md` and update the constants in `src/pyproj_dep_analyze/__init__conf__.py` according to `pyproject.toml`
    - Automation rewrites `src/pyproj_dep_analyze/__init__conf__.py` from `pyproject.toml`, so runtime code imports generated constants instead of querying `importlib.metadata`.
    - After updating project metadata (version, summary, URLs, authors) run `make test` (or `python -m scripts.test`) to regenerate the metadata module before committing.
- **Release Tags**: Format is `vX.Y.Z` (push tags for CI to build and publish)

## Common Make Targets

| Target                | Description                                                                    |
|-----------------------|--------------------------------------------------------------------------------|
| `build`               | Build wheel/sdist artifacts                                                    |
| `bump`                | Bump version (VERSION=X.Y.Z or PART=major\|minor\|patch) and update changelog |
| `bump-major`          | Increment major version ((X+1).0.0)                                           |
| `bump-minor`          | Increment minor version (X.Y.Z → X.(Y+1).0)                                   |
| `bump-patch`          | Increment patch version (X.Y.Z → X.Y.(Z+1))                                   |
| `clean`               | Remove caches, coverage, and build artifacts (includes `dist/` and `build/`)  |
| `coverage`            | Run coverage report                                                           |
| `dependencies`        | Show project dependencies                                                     |
| `dependencies-update` | Update project dependencies                                                   |
| `dev`                 | Install package with dev extras                                               |
| `help`                | Show make targets                                                             |
| `install`             | Editable install                                                              |
| `menu`                | Interactive TUI menu                                                          |
| `push`                | Commit changes and push to GitHub (no CI monitoring)                          |
| `release`             | Tag vX.Y.Z, push, sync packaging, run gh release if available                 |
| `run`                 | Run module entry (`python -m ... --help`)                                     |
| `test`                | Lint, format, type-check, run tests with coverage, upload to Codecov          |
| `version-current`     | Print current version from `pyproject.toml`                                   |

## Coding Style & Naming Conventions

Follow the guidelines in `python_clean_code.md` for all Python code.

## Architecture Overview

This project follows a layered architecture with clear separation of concerns:

### Layer Structure (enforced by import-linter)

```
cli (top layer)
    ↓
analyzer
    ↓
index_resolver, repo_resolver, version_resolver
    ↓
dependency_extractor
    ↓
models (bottom layer)
```

### Core Independent Modules
- `models.py`: Data models using Pydantic (no dependencies on other modules)
- `python_version_parser.py`: Python version requirement parsing (independent)

### Import Rules (enforced by import-linter)
- `models` and `python_version_parser` are independent modules
- Lower layers cannot import from higher layers
- `cli` is the top-most layer

### Module Responsibilities
- **cli.py**: Command-line interface using rich-click
- **analyzer.py**: Orchestrates dependency analysis
- **index_resolver.py**: Queries PyPI for package metadata
- **repo_resolver.py**: Resolves repository information from PyPI
- **version_resolver.py**: Compares and resolves version requirements
- **dependency_extractor.py**: Extracts dependencies from pyproject.toml files
- **models.py**: Pydantic data models for type-safe data handling

## Security & Configuration

- `.env` files are for local tooling only (CodeCov tokens, etc.)
- **NEVER** commit secrets to version control
- Rich logging should sanitize payloads before rendering

## Documentation & Translations

### Web Documentation
- Update only English docs under `/website/docs`
- Other languages are translated automatically
- When in doubt, ask before modifying non-English documentation

### App UI Strings (i18n)
- Update only `sources/_locales/en` for string changes
- Other languages are translated automatically
- When in doubt, ask before modifying non-English locales

## Commit & Push Policy

### Pre-Push Requirements
- **Always run `make test` before pushing** to avoid lint/test breakage
- Ensure all tests pass and code is properly formatted

### Post-Push Monitoring
- Monitor GitHub Actions for errors after pushing
- Attempt to correct any CI/CD errors that appear

## Python Version & Dependencies

- **Python 3.10+** - supports Python 3.10, 3.11, 3.12, and 3.13
- **TOML parsing** - uses `rtoml` (Rust-based) for consistent cross-version support
- **Type hints** - uses `from __future__ import annotations` in all files for modern syntax compatibility
- **CI matrix** - tests against all supported Python versions on Ubuntu, macOS, and Windows

### Key Runtime Dependencies
- `rich-click` - CLI framework
- `httpx` - async HTTP client for PyPI/GitHub API calls
- `pydantic` - data validation and models
- `rtoml` - TOML parsing (replaces stdlib `tomllib` for Python 3.10 compatibility)
- `lib_layered_config` - layered configuration management
- `lib_log_rich` - structured logging with Rich
- `lib_cli_exit_tools` - CLI exit handling

## Claude Code Workflow

When working on this project:
1. Read relevant system prompts at session start
2. Apply appropriate coding guidelines based on file type
3. Run `make test` before commits
4. Follow versioning guidelines for releases
5. Monitor CI after pushing changes
