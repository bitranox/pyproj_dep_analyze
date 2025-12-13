# Data Flow Architecture

## Overview

This document shows the data flow through pyproj_dep_analyze, from input (pyproject.toml) to output (JSON analysis results).

## High-Level Data Flow

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                              INPUT BOUNDARY                                  │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  pyproject.toml ───► rtoml.load() ───► PyprojectSchema (Pydantic)            │
│                            │                      │                          │
│                            ▼                      ▼                          │
│                       Raw dict            Validated TOML data                │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                           DOMAIN PROCESSING                                  │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  PyprojectSchema ───► extract_dependencies() ───► list[DependencyInfo]       │
│        │                                                 │                   │
│        │                                                 ▼                   │
│        │                 ┌───────────────────────────────────────┐           │
│        │                 │            Analyzer                   │           │
│        │                 │  ┌─────────────────────────────────┐  │           │
│        ▼                 │  │ VersionResolver ─► VersionResult│  │           │
│  get_requires_python()   │  │ IndexResolver   ─► IndexInfo    │  │           │
│        │                 │  │ RepoResolver    ─► RepoMetadata │  │           │
│        ▼                 │  └─────────────────────────────────┘  │           │
│  list[PythonVersion]     │                  │                    │           │
│                          │                  ▼                    │           │
│                          │  determine_action() ─► Action (Enum)  │           │
│                          └───────────────────────────────────────┘           │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                            OUTPUT BOUNDARY                                   │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  Basic Analysis:                                                             │
│  ───────────────                                                             │
│  list[OutdatedEntry] ─► AnalysisResult ─► model_dump() ─► outdated.json      │
│                                                                              │
│  Enriched Analysis:                                                          │
│  ──────────────────                                                          │
│  list[EnrichedEntry] ─► EnrichedAnalysisResult ─► model_dump() ─► deps.json  │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

## Class Relationships

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                              ENUMS (str, Enum)                               │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌───────────────┐  ┌──────────────────┐  ┌────────────────────┐             │
│  │    Action     │  │    IndexType     │  │ CompatibilityStatus│             │
│  ├───────────────┤  ├──────────────────┤  ├────────────────────┤             │
│  │ UPDATE        │  │ PYPI             │  │ COMPATIBLE         │             │
│  │ DELETE        │  │ TESTPYPI         │  │ EXCLUDED           │             │
│  │ NONE          │  │ ARTIFACTORY      │  │ UNKNOWN            │             │
│  │ CHECK_MANUALLY│  │ DEVPI            │  └────────────────────┘             │
│  └───────────────┘  │ AZURE_ARTIFACTS  │                                     │
│                     │ CLOUDSMITH       │  ┌──────────────┐                   │
│  ┌──────────────┐   │ GEMFURY          │  │   RepoType   │                   │
│  │VersionStatus │   │ ANACONDA         │  ├──────────────┤                   │
│  ├──────────────┤   │ CUSTOM           │  │ GITHUB       │                   │
│  │ UNKNOWN      │   └──────────────────┘  │ GITLAB       │                   │
│  └──────────────┘                         │ BITBUCKET    │                   │
│                     ┌──────────────────┐  │ UNKNOWN      │                   │
│  ┌──────────────┐   │ DeploymentTarget │  └──────────────┘                   │
│  │ OutputFormat │   ├──────────────────┤                                     │
│  ├──────────────┤   │ APP              │                                     │
│  │ JSON         │   │ HOST             │                                     │
│  │ TABLE        │   │ USER             │                                     │
│  │ SUMMARY      │   └──────────────────┘                                     │
│  └──────────────┘                                                            │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│                         PYDANTIC MODELS (BaseModel)                          │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │                        BASIC ANALYSIS OUTPUT                           │  │
│  │                                                                        │  │
│  │   ┌────────────────┐         ┌─────────────────────┐                   │  │
│  │   │ OutdatedEntry  │ ◄────── │   AnalysisResult    │                   │  │
│  │   ├────────────────┤  0..*   ├─────────────────────┤                   │  │
│  │   │ package: str   │         │ entries: list[...]  │                   │  │
│  │   │ python_version │         │ python_versions     │                   │  │
│  │   │ current_version│         │ total_dependencies  │                   │  │
│  │   │ latest_version │         │ update_count        │                   │  │
│  │   │ action: Action │         │ delete_count        │                   │  │
│  │   └────────────────┘         │ check_manually_count│                   │  │
│  │                              └─────────────────────┘                   │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │                       ENRICHED ANALYSIS OUTPUT                         │  │
│  │                                                                        │  │
│  │   ┌─────────────────────────────────────────────────────────────────┐  │  │
│  │   │                  EnrichedAnalysisResult                         │  │  │
│  │   ├─────────────────────────────────────────────────────────────────┤  │  │
│  │   │ analyzed_at: str                                                │  │  │
│  │   │ pyproject_path: str                                             │  │  │
│  │   │ python_versions: list[str]                                      │  │  │
│  │   │ indexes_configured: list[IndexInfo]                             │  │  │
│  │   │ packages: list[EnrichedEntry]                                   │  │  │
│  │   │ dependency_graph: dict[str, list[str]]                          │  │  │
│  │   │ summary: EnrichedSummary                                        │  │  │
│  │   └─────────────────────────────────────────────────────────────────┘  │  │
│  │                                                                        │  │
│  │   ┌──────────────────────┐    ┌──────────────────────────────────┐     │  │
│  │   │   EnrichedSummary    │    │        EnrichedEntry             │     │  │
│  │   ├──────────────────────┤    ├──────────────────────────────────┤     │  │
│  │   │ total_packages: int  │    │ name: str                        │     │  │
│  │   │ updates_available    │    │ requested_version: str | None    │     │  │
│  │   │ up_to_date           │    │ resolved_version: str | None     │     │  │
│  │   │ check_manually       │    │ latest_version: str | None       │     │  │
│  │   │ from_pypi            │    │ action: Action                   │     │  │
│  │   │ from_private_index   │    │ source: str                      │     │  │
│  │   └──────────────────────┘    │ index_info: IndexInfo | None     │     │  │
│  │                               │ python_compatibility: dict       │     │  │
│  │                               │ pypi_metadata: PyPIMetadata|None │     │  │
│  │                               │ repo_metadata: RepoMetadata|None │     │  │
│  │                               │ direct_dependencies: list[str]   │     │  │
│  │                               └──────────────────────────────────┘     │  │
│  │                                                                        │  │
│  │   ┌──────────────────────┐    ┌──────────────────────┐                 │  │
│  │   │    RepoMetadata      │    │    PyPIMetadata      │                 │  │
│  │   ├──────────────────────┤    ├──────────────────────┤                 │  │
│  │   │ repo_type: RepoType  │    │ summary: str | None  │                 │  │
│  │   │ url: str | None      │    │ license: str | None  │                 │  │
│  │   │ owner: str | None    │    │ home_page            │                 │  │
│  │   │ name: str | None     │    │ project_urls: dict   │                 │  │
│  │   │ stars: int | None    │    │ author               │                 │  │
│  │   │ forks: int | None    │    │ author_email         │                 │  │
│  │   │ open_issues          │    │ maintainer           │                 │  │
│  │   │ default_branch       │    │ maintainer_email     │                 │  │
│  │   │ last_commit_date     │    │ available_versions   │                 │  │
│  │   │ created_at           │    │ first_release_date   │                 │  │
│  │   │ description          │    │ latest_release_date  │                 │  │
│  │   └──────────────────────┘    │ requires_python      │                 │  │
│  │                               │ requires_dist: list  │                 │  │
│  │   ┌──────────────────────┐    └──────────────────────┘                 │  │
│  │   │      IndexInfo       │                                             │  │
│  │   ├──────────────────────┤                                             │  │
│  │   │ url: str             │                                             │  │
│  │   │ index_type: IndexType│                                             │  │
│  │   │ is_private: bool     │                                             │  │
│  │   └──────────────────────┘                                             │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────────────┐
│                         DATACLASSES (Internal Logic)                         │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌──────────────────────────┐          ┌──────────────────────────┐         │
│   │     DependencyInfo       │          │     PythonVersion        │         │
│   ├──────────────────────────┤          ├──────────────────────────┤         │
│   │ name: str                │          │ major: int               │         │
│   │ raw_spec: str            │          │ minor: int               │         │
│   │ version_constraints: str │          ├──────────────────────────┤         │
│   │ python_markers: str|None │          │ __lt__, __le__, __gt__,  │         │
│   │ extras: list[str]        │          │ __ge__, __eq__, __str__  │         │
│   │ source: str              │          │ from_string(cls, str)    │         │
│   │ is_git_dependency: bool  │          └──────────────────────────┘         │
│   │ git_url: str | None      │                                               │
│   │ git_ref: str | None      │                                               │
│   └──────────────────────────┘                                               │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

## Resolver Classes

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                              RESOLVERS                                       │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │                          VersionResolver                               │  │
│  ├────────────────────────────────────────────────────────────────────────┤  │
│  │ Attributes:                                                            │  │
│  │   github_token: str | None                                             │  │
│  │   timeout: float = 30.0                                                │  │
│  │   concurrency: int = 10                                                │  │
│  │   cache: dict[str, VersionResult]      ◄── In-memory cache             │  │
│  ├────────────────────────────────────────────────────────────────────────┤  │
│  │ Methods:                                                               │  │
│  │   resolve_async(package) ──────────► VersionResult                     │  │
│  │   resolve_many_async(packages) ────► dict[str, VersionResult]          │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                          │                                                   │
│                          ▼                                                   │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │                          VersionResult                                 │  │
│  ├────────────────────────────────────────────────────────────────────────┤  │
│  │ latest_version: str | None                                             │  │
│  │ pypi_metadata: PyPIMetadata | None    ◄── Optional enrichment          │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │                          IndexResolver                                 │  │
│  ├────────────────────────────────────────────────────────────────────────┤  │
│  │ Attributes:                                                            │  │
│  │   indexes: list[IndexInfo]                                             │  │
│  │   timeout: float = 30.0                                                │  │
│  │   cache: dict[str, IndexInfo]          ◄── In-memory cache             │  │
│  ├────────────────────────────────────────────────────────────────────────┤  │
│  │ Methods:                                                               │  │
│  │   resolve_async(package) ──────────► IndexInfo | None                  │  │
│  │   resolve_many_async(packages) ────► PackageIndexResolutions           │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │                          RepoResolver                                  │  │
│  ├────────────────────────────────────────────────────────────────────────┤  │
│  │ Attributes:                                                            │  │
│  │   github_token: str | None                                             │  │
│  │   timeout: float = 30.0                                                │  │
│  │   cache: dict[str, RepoMetadata]       ◄── In-memory cache             │  │
│  ├────────────────────────────────────────────────────────────────────────┤  │
│  │ Methods:                                                               │  │
│  │   resolve_async(owner, repo) ─────► RepoMetadata | None                │  │
│  │   resolve_from_url_async(url) ────► RepoMetadata | None                │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

## API Entry Points

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                            PUBLIC API                                        │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │                    FUNCTIONS                                           │  │
│  ├────────────────────────────────────────────────────────────────────────┤  │
│  │                                                                        │  │
│  │  analyze_pyproject(path, **kwargs) ────────► list[OutdatedEntry]       │  │
│  │       │                                                                │  │
│  │       └── Synchronous wrapper, creates Analyzer internally             │  │
│  │                                                                        │  │
│  │  run_enriched_analysis(path, **kwargs) ────► EnrichedAnalysisResult    │  │
│  │       │                                                                │  │
│  │       └── Synchronous wrapper, creates Analyzer internally             │  │
│  │                                                                        │  │
│  │  write_outdated_json(entries, path) ───────► None                      │  │
│  │       │                                                                │  │
│  │       └── Writes list[OutdatedEntry] to JSON file                      │  │
│  │                                                                        │  │
│  │  write_enriched_json(result, path) ────────► None                      │  │
│  │       │                                                                │  │
│  │       └── Writes EnrichedAnalysisResult to JSON file                   │  │
│  │                                                                        │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐  │
│  │                      Analyzer CLASS                                    │  │
│  ├────────────────────────────────────────────────────────────────────────┤  │
│  │                                                                        │  │
│  │  Analyzer(github_token, timeout, concurrency)                          │  │
│  │       │                                                                │  │
│  │       ├── analyze(path) ───────────────────► AnalysisResult            │  │
│  │       │        │                                                       │  │
│  │       │        └── Uses VersionResolver for version lookups            │  │
│  │       │                                                                │  │
│  │       └── analyze_enriched(path) ──────────► EnrichedAnalysisResult    │  │
│  │                │                                                       │  │
│  │                ├── Uses VersionResolver (with metadata)                │  │
│  │                ├── Uses IndexResolver (index detection)                │  │
│  │                └── Uses RepoResolver (repository metadata)             │  │
│  │                                                                        │  │
│  └────────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

## External API Boundaries

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                        EXTERNAL API BOUNDARIES                               │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌──────────────────┐                                                       │
│   │    PyPI API      │                                                       │
│   ├──────────────────┤                                                       │
│   │                  │                                                       │
│   │  GET /pypi/{pkg}/json                                                    │
│   │       │                                                                  │
│   │       ▼                                                                  │
│   │  PyPIFullResponseSchema (Pydantic)                                       │
│   │       │                                                                  │
│   │       ├──► latest_version: str                                           │
│   │       └──► PyPIMetadata (enrichment)                                     │
│   │                                                                          │
│   └──────────────────┘                                                       │
│                                                                              │
│   ┌──────────────────┐                                                       │
│   │   GitHub API     │                                                       │
│   ├──────────────────┤                                                       │
│   │                  │                                                       │
│   │  GET /repos/{owner}/{repo}                                               │
│   │       │                                                                  │
│   │       ▼                                                                  │
│   │  GitHubRepoResponseSchema (Pydantic)                                     │
│   │       │                                                                  │
│   │       └──► RepoMetadata                                                  │
│   │                                                                          │
│   │  GET /repos/{owner}/{repo}/releases                                      │
│   │  GET /repos/{owner}/{repo}/tags                                          │
│   │       │                                                                  │
│   │       └──► latest_version (for git dependencies)                         │
│   │                                                                          │
│   └──────────────────┘                                                       │
│                                                                              │
│   ┌──────────────────┐                                                       │
│   │  Package Indexes │                                                       │
│   ├──────────────────┤                                                       │
│   │                  │                                                       │
│   │  HEAD /{package}/ (Simple API)                                           │
│   │       │                                                                  │
│   │       └──► IndexInfo (which index serves package)                        │
│   │                                                                          │
│   │  Sources:                                                                │
│   │    - pip.conf / pip.ini                                                  │
│   │    - PIP_INDEX_URL / PIP_EXTRA_INDEX_URL                                 │
│   │    - pyproject.toml [tool.uv.index] / [tool.poetry.source]               │
│   │                                                                          │
│   └──────────────────┘                                                       │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

## Complete Processing Pipeline

```
pyproject.toml
      │
      ▼
┌─────────────────────┐
│ load_pyproject()    │ ──► PyprojectSchema
└─────────────────────┘
      │
      ├───────────────────────────────────────────────┐
      │                                               │
      ▼                                               ▼
┌─────────────────────┐                    ┌─────────────────────┐
│extract_dependencies │                    │get_requires_python()│
└─────────────────────┘                    └─────────────────────┘
      │                                               │
      ▼                                               ▼
list[DependencyInfo]                        list[PythonVersion]
      │                                               │
      └────────────────────┬──────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│                        Analyzer                                  │
│                                                                  │
│  For each (dependency, python_version) pair:                     │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ 1. VersionResolver.resolve_async(package)                  │  │
│  │         │                                                  │  │
│  │         ▼                                                  │  │
│  │    VersionResult { latest_version, pypi_metadata }         │  │
│  └────────────────────────────────────────────────────────────┘  │
│                           │                                      │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ 2. determine_action(dependency, version_result, py_ver)    │  │
│  │         │                                                  │  │
│  │         ▼                                                  │  │
│  │    Action (UPDATE | DELETE | NONE | CHECK_MANUALLY)        │  │
│  └────────────────────────────────────────────────────────────┘  │
│                           │                                      │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ 3. (Enriched only) IndexResolver.resolve_async(package)    │  │
│  │         │                                                  │  │
│  │         ▼                                                  │  │
│  │    IndexInfo { url, index_type, is_private }               │  │
│  └────────────────────────────────────────────────────────────┘  │
│                           │                                      │
│  ┌────────────────────────────────────────────────────────────┐  │
│  │ 4. (Enriched only) RepoResolver.resolve_from_url_async()   │  │
│  │         │                                                  │  │
│  │         ▼                                                  │  │
│  │    RepoMetadata { stars, forks, last_commit, ... }         │  │
│  └────────────────────────────────────────────────────────────┘  │
│                           │                                      │
└───────────────────────────│──────────────────────────────────────┘
                            │
                            ▼
              ┌─────────────────────────────────┐
              │   Basic Analysis:               │
              │   AnalysisResult                │
              │     └── list[OutdatedEntry]     │
              │                                 │
              │   Enriched Analysis:            │
              │   EnrichedAnalysisResult        │
              │     ├── list[EnrichedEntry]     │
              │     ├── dependency_graph        │
              │     └── summary stats           │
              └─────────────────────────────────┘
                            │
                            ▼
              ┌─────────────────────────────────┐
              │ write_*_json()                  │
              │     │                           │
              │     ▼                           │
              │ model_dump(mode="json")         │
              │     │                           │
              │     ▼                           │
              │ JSON file output                │
              └─────────────────────────────────┘
```
