````markdown
# Product Requirements Document

## Goal
Develop a tool that processes a `pyproject.toml`. The tool analyzes dependencies and Python version requirements. It determines, for each dependency and each Python version, both the version currently defined and the latest compatible version. The tool produces exactly one file, `outdated.json`. Additionally, it provides a data class, and its API returns a list of instances of this data class.

---

# Inputs

## 1. pyproject.toml

### 1.1 Python version requirement
Example:
```toml
requires-python = ">=3.9"
````

The system derives all relevant Python versions from this expression.

### 1.2 All dependency sources

The tool reads dependencies from the following sections:

* `[project.dependencies]`
* `[project.optional-dependencies]`
* `[tool.poetry.dependencies]`
* `[tool.poetry.dev-dependencies]`
* `[tool.poetry.group.<name>.dependencies]`
* `[tool.pdm.dependencies]`
* `[tool.pdm.dev-dependencies]`
* `[tool.hatch.metadata.dependencies]`
* `[tool.hatch.envs.<name>.dependencies]`
* `[tool.setuptools.dynamic.dependencies]`
* `[build-system.requires]` when relevant

Generic rule.
Any section counts as a possible dependency source if it contains keys such as `dependencies`, `dev-dependencies`, `optional-dependencies`, `requires`, `build-dependencies`, or similar. It may also qualify if it contains strings that syntactically represent dependencies.

---

# Requirements

## 2. Deriving all valid Python versions

The tool interprets `requires-python` and produces a list of Python versions that fall within the required range.

Examples:

* `>=3.9` → 3.9, 3.10, 3.11, 3.12, 3.13, 3.14
* `>=3.13` → 3.13, 3.14, 3.15
* `>=3.10,<3.12` → 3.10, 3.11

---

## 3. Processing dependencies for each Python version

For each dependency and each Python version the system determines:

* `current_version`
* `latest_version`
* an action indicating whether something needs to be changed

The tool understands:

* inline markers
* arrays of marker strings
* multiple definitions for the same package
* version constraints such as `>=1.0,<2.0`
* mixed syntax variants

---

## 4. Actions per Python version

Each dependency is evaluated separately for each Python version.

### 4.1 action = "update"

When a newer compatible version exists.
`latest_version` is greater than `current_version`.

### 4.2 action = "delete"

This action applies to individual Python versions.

A case for `delete` arises when:

* a rule applies only to old Python versions outside the valid `requires-python` range
* no valid rule exists for a specific Python version
* a defined version is technically incompatible with that Python version

### 4.3 action = "none"

The dependency is correct and up to date for this Python version.

### 4.4 action = "check manually"

A special case applies for GitHub packages.
See section 3.1.

---

# 3.1 Determining `latest_version` depending on package source

The system detects whether a package is from PyPI or GitHub.

### A. PyPI packages

The determination of the latest valid version uses the same resolver logic as `pip`.

* queries PyPI or a configured package index
* considers Python version and constraints
* result is the highest compatible version

### B. GitHub packages

A package is considered a GitHub package if it contains a git URL, for example:

* `git+https://github.com/...`
* `git+ssh://git@github.com/...`
* `git+https://github.com/...@v1.2.3`

Procedure.

1. Extract the repository URL
2. Query the GitHub Release API

   * `https://api.github.com/repos/<owner>/<repo>/releases`
3. The last valid version is the newest release tag
4. If no releases exist but tags exist

   * the system uses the newest git tag
5. **New rule**
   If neither releases nor tags exist or the version cannot be determined

   * `latest_version = "unknown"`
   * `action = "check manually"`

Examples:

#### Example 1. GitHub package with releases

```
Tags: v1.0.0, v2.0.0
→ latest_version = "2.0.0"
→ action = update or none
```

#### Example 2. GitHub package without releases but with tags

```
Tags: 0.1.0, 0.3.0
→ latest_version = "0.3.0"
```

#### Example 3. GitHub package without releases and without tags

```
→ latest_version = "unknown"
→ action = check manually
```

---

# outdated.json

The tool generates a single file: `outdated.json`.
Each entry describes a dependency for one specific Python version.

Example:

```json
[
  {
    "package": "lib_layered_config",
    "python_version": "3.9",
    "current_version": "3.0.0",
    "latest_version": "4.0.0",
    "action": "update"
  },
  {
    "package": "lib_layered_config",
    "python_version": "3.14",
    "current_version": "5.0.0",
    "latest_version": "5.0.0",
    "action": "none"
  },
  {
    "package": "internaltool",
    "python_version": "3.11",
    "current_version": null,
    "latest_version": "unknown",
    "action": "check manually"
  }
]
```

---

# Data class for API output

The tool defines the following data class:

```python
@dataclass
class OutdatedEntry:
    package: str
    python_version: str
    current_version: str | None
    latest_version: str | None
    action: str  # update, delete, none, check manually
```

The API returns a list of these data class instances.

Example:

```python
def analyze_pyproject(...) -> list[OutdatedEntry]:
    ...
```

---

# Parser requirements

The tool must be able to:

* recognize inline markers
* understand array markers
* merge multiple blocks per package
* accept various syntax forms
* identify non-standard sections if they logically contain dependencies
* interpret constraints correctly

---

# Result

A universal tool.
It recognizes all dependency structures.
It analyzes all relevant Python versions.
It evaluates each dependency per Python version.
It determines PyPI versions using pip’s resolver logic.
It determines GitHub versions using releases or tags.
It marks unclear cases as `check manually`.
It produces a file `outdated.json` and returns the same data as a list of structured data class instances.

```
```
