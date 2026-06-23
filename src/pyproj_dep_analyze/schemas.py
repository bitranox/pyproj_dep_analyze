"""Pydantic schemas for external data boundaries (input parsing).

Purpose
-------
Define Pydantic models for parsing external input data:
- Input: Parsing pyproject.toml structures
- API Responses: Parsing PyPI and GitHub API responses

Domain models (OutdatedEntry, AnalysisResult, etc.) are now in models.py
as Pydantic models, eliminating unnecessary dataclass-to-schema conversions.

Data Flow Pattern
-----------------
External Input → Pydantic Schema (validate) → Pydantic Model (domain + serialize) → Output
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


# --- PyPI API Response Schemas ---


class PyPIInfoSchema(BaseModel):
    """Schema for PyPI package info response (minimal)."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    version: str | None = None


class PyPIResponseSchema(BaseModel):
    """Schema for PyPI API response (minimal)."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    info: PyPIInfoSchema = Field(default_factory=PyPIInfoSchema)


class PyPIFullInfoSchema(BaseModel):
    """Full PyPI info section schema with all metadata fields."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    name: str = ""
    version: str = ""
    summary: str | None = None
    license: str | None = None
    home_page: str | None = None
    project_urls: dict[str, str] | None = None
    author: str | None = None
    author_email: str | None = None
    maintainer: str | None = None
    maintainer_email: str | None = None
    requires_python: str | None = None
    requires_dist: list[str] | None = None


class PyPIReleaseFileSchema(BaseModel):
    """Single file within a PyPI release."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    upload_time_iso_8601: str | None = None
    requires_python: str | None = None


def _empty_releases_dict() -> dict[str, list[PyPIReleaseFileSchema]]:
    """Return empty releases dict for default factory."""
    return {}


class PyPIFullResponseSchema(BaseModel):
    """Complete PyPI JSON API response with releases."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    info: PyPIFullInfoSchema = Field(default_factory=PyPIFullInfoSchema)
    releases: dict[str, list[PyPIReleaseFileSchema]] = Field(default_factory=_empty_releases_dict)


# --- GitHub API Response Schemas ---


class GitHubReleaseSchema(BaseModel):
    """Schema for GitHub release API response."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    tag_name: str = ""
    prerelease: bool = False
    draft: bool = False


class GitHubTagSchema(BaseModel):
    """Schema for GitHub tag API response."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    name: str = ""


class GitHubRepoResponseSchema(BaseModel):
    """Schema for GitHub repository API response.

    Used to parse repository metadata from:
    https://api.github.com/repos/{owner}/{repo}
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    html_url: str | None = None
    description: str | None = None
    stargazers_count: int | None = None
    forks_count: int | None = None
    open_issues_count: int | None = None
    default_branch: str | None = None
    pushed_at: str | None = None
    created_at: str | None = None


# --- Pyproject.toml Input Schemas ---


class PoetryDependencySpec(BaseModel):
    """Schema for Poetry dependency specification in dict form.

    Handles complex Poetry dependencies like:
    requests = {version = ">=2.0", python = "^3.8", extras = ["security"]}
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    version: str = ""
    python: str | None = None
    extras: list[str] = Field(default_factory=list)
    git: str | None = None
    rev: str | None = None
    tag: str | None = None
    branch: str | None = None


class BuildSystemSchema(BaseModel):
    """Schema for [build-system] section."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    requires: list[str] = Field(default_factory=list)
    build_backend: str | None = Field(default=None, alias="build-backend")


class ProjectSchema(BaseModel):
    """Schema for [project] section (PEP 621)."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    name: str = ""
    version: str = ""
    dependencies: list[str] = Field(default_factory=list)
    optional_dependencies: dict[str, list[str]] = Field(default_factory=dict, alias="optional-dependencies")
    requires_python: str | None = Field(default=None, alias="requires-python")


# Type alias for Poetry dependency specification values
# Can be: "^1.0" or {version = "^1.0"} or [{version = "^1.0", python = "..."}, {...}]
PoetryDepSpec = str | dict[str, str | list[str] | bool | None] | list[dict[str, str | list[str] | bool | None]]


class PoetryGroupSchema(BaseModel):
    """Schema for a Poetry group like [tool.poetry.group.dev]."""

    model_config = ConfigDict(frozen=True, extra="allow")

    dependencies: dict[str, PoetryDepSpec] = Field(default_factory=dict)
    optional: bool = False


class SourceSchema(BaseModel):
    """Schema for package index source configuration.

    Used by both Poetry and PDM tool configurations.
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    name: str | None = None
    url: str
    default: bool = False
    secondary: bool = False


def _empty_source_list() -> list[SourceSchema]:
    """Return empty source list for dataclass default."""
    return []


class PoetryToolSchema(BaseModel):
    """Schema for [tool.poetry] section."""

    model_config = ConfigDict(frozen=True, extra="allow")

    dependencies: dict[str, PoetryDepSpec] = Field(default_factory=dict)
    dev_dependencies: dict[str, PoetryDepSpec] = Field(default_factory=dict, alias="dev-dependencies")
    group: dict[str, PoetryGroupSchema] = Field(default_factory=dict)
    source: list[SourceSchema] = Field(default_factory=_empty_source_list)


class PDMToolSchema(BaseModel):
    """Schema for [tool.pdm] section."""

    model_config = ConfigDict(frozen=True, extra="allow")

    dependencies: dict[str, str | dict[str, str | list[str] | bool | None]] = Field(default_factory=dict)
    # PDM dev-dependencies can be either:
    # - dict of name: spec pairs (older style)
    # - dict of group: list[str] pairs (newer style)
    dev_dependencies: dict[str, str | list[str] | dict[str, str | list[str] | bool | None]] = Field(default_factory=dict, alias="dev-dependencies")
    source: list[SourceSchema] = Field(default_factory=_empty_source_list)


class HatchEnvSchema(BaseModel):
    """Schema for hatch environment configuration."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    dependencies: list[str] = Field(default_factory=list)


class HatchMetadataSchema(BaseModel):
    """Schema for [tool.hatch.metadata] section."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    dependencies: list[str] = Field(default_factory=list)


class HatchToolSchema(BaseModel):
    """Schema for [tool.hatch] section."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    metadata: HatchMetadataSchema = Field(default_factory=HatchMetadataSchema)
    envs: dict[str, HatchEnvSchema] = Field(default_factory=dict)


class ToolSectionSchema(BaseModel):
    """Schema for [tool] section containing various build tool configs."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    poetry: PoetryToolSchema = Field(default_factory=PoetryToolSchema)
    pdm: PDMToolSchema = Field(default_factory=PDMToolSchema)
    hatch: HatchToolSchema = Field(default_factory=HatchToolSchema)


class IncludeGroupSchema(BaseModel):
    """Schema for include-group entries in dependency-groups (PEP 735)."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    include_group: str = Field(alias="include-group")


# Type for dependency group items: either a string or an include-group reference
DependencyGroupItem = str | IncludeGroupSchema


class UVConfigSchema(BaseModel):
    """Schema for uv.toml configuration file.

    Validates UV package manager configuration including custom index URLs.
    Supports both primary and additional package indexes as per UV conventions.
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    index_url: str | None = Field(default=None, alias="index-url")
    extra_index_url: list[str] = Field(default_factory=list, alias="extra-index-url")


class PyprojectSchema(BaseModel):
    """Schema for complete pyproject.toml file.

    Validates and structures the entire pyproject.toml input at the system boundary.
    Internal code should work with this typed model instead of raw dicts.
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    build_system: BuildSystemSchema = Field(default_factory=BuildSystemSchema, alias="build-system")
    project: ProjectSchema = Field(default_factory=ProjectSchema)
    tool: ToolSectionSchema = Field(default_factory=ToolSectionSchema)
    dependency_groups: dict[str, list[DependencyGroupItem]] = Field(default_factory=dict, alias="dependency-groups")


# --- Configuration Schemas ---


class AnalyzerConfigSchema(BaseModel):
    """Schema for [analyzer] configuration section.

    Validates analyzer settings loaded from config files or environment.
    """

    model_config = ConfigDict(frozen=True, extra="ignore")

    github_token: str = ""
    timeout: float = 30.0
    concurrency: int = 10


__all__ = [
    "AnalyzerConfigSchema",
    "BuildSystemSchema",
    "DependencyGroupItem",
    "GitHubReleaseSchema",
    "GitHubRepoResponseSchema",
    "GitHubTagSchema",
    "HatchEnvSchema",
    "HatchMetadataSchema",
    "HatchToolSchema",
    "IncludeGroupSchema",
    "PDMToolSchema",
    "PoetryDependencySpec",
    "PoetryGroupSchema",
    "PoetryToolSchema",
    "ProjectSchema",
    "PyPIFullInfoSchema",
    "PyPIFullResponseSchema",
    "PyPIInfoSchema",
    "PyPIReleaseFileSchema",
    "PyPIResponseSchema",
    "PyprojectSchema",
    "SourceSchema",
    "ToolSectionSchema",
    "UVConfigSchema",
]
