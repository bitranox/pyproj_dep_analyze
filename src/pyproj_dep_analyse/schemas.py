"""Pydantic schemas for external data boundaries.

Purpose
-------
Define Pydantic models for data that crosses system boundaries:
- Input: Parsing pyproject.toml structures
- Output: JSON serialization of analysis results

These models handle validation, coercion, and serialization at the edges
while internal business logic uses lightweight dataclasses.

Data Flow Pattern
-----------------
External Input → Pydantic (validate) → Dataclass (domain) → Pydantic (serialize) → External Output
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from .models import Action


class OutdatedEntrySchema(BaseModel):
    """Pydantic schema for serializing analysis results to JSON.

    Used at the output boundary when writing outdated.json or
    returning JSON from the API.
    """

    model_config = ConfigDict(frozen=True, use_enum_values=True)

    package: str = Field(description="The name of the package")
    python_version: str = Field(description="The Python version this applies to")
    current_version: str | None = Field(description="Currently specified version")
    latest_version: str | None = Field(description="Latest available version")
    action: Action = Field(description="Recommended action")


def _empty_entry_list() -> list[OutdatedEntrySchema]:
    """Return empty list for default factory."""
    return []


def _empty_str_list() -> list[str]:
    """Return empty string list for default factory."""
    return []


class AnalysisResultSchema(BaseModel):
    """Pydantic schema for complete analysis result serialization."""

    model_config = ConfigDict(frozen=True)

    entries: list[OutdatedEntrySchema] = Field(default_factory=_empty_entry_list)
    python_versions: list[str] = Field(default_factory=_empty_str_list)
    total_dependencies: int = 0
    update_count: int = 0
    delete_count: int = 0
    check_manually_count: int = 0


class PyPIInfoSchema(BaseModel):
    """Schema for PyPI package info response."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    version: str | None = None


class PyPIResponseSchema(BaseModel):
    """Schema for PyPI API response."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    info: PyPIInfoSchema = Field(default_factory=PyPIInfoSchema)


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


__all__ = [
    "AnalysisResultSchema",
    "GitHubReleaseSchema",
    "GitHubTagSchema",
    "OutdatedEntrySchema",
    "PoetryDependencySpec",
    "PyPIInfoSchema",
    "PyPIResponseSchema",
]
