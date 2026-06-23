# Installation Guide

> The CLI stack uses `rich-click`, which bundles `rich` styling on top of click-style ergonomics.

This guide collects every supported method to install `pyproj_dep_analyze`, including
isolated environments and system package managers. Pick the option that matches your workflow.

## Requirements

- **Python 3.10 or higher** (tested on 3.10, 3.11, 3.12, 3.13)
- Works on Linux, macOS, and Windows


## We recommend `uv` to install the package 

### 🔹 `uv` = Ultra-fast Python package manager

→ lightning-fast replacement for `pip`, `venv`, `pip-tools`, and `poetry`
written in Rust, compatible with PEP 621 (`pyproject.toml`)

### 🔹 `uvx` = On-demand tool runner

→ runs tools temporarily in isolated environments without installing them globally


## ⚙️ Installation

```bash
# recommended on linux
curl -LsSf https://astral.sh/uv/install.sh | sh
# alternative
pip install uv
# alternative
python -m pip install uv
```

---

## 🧠 Core Principle

`uv` combines the capabilities of:

* **pip** (package installation)
* **venv** (virtual environments)
* **pip-tools** (Lockfiles)
* **poetry** (project management)
* **pipx** (tool execution)

All via a single command suite.

---

## 🧭 Comparison with Alternatives

| Tool         | Speed        | Lockfile | Tool execution | pyproject support |
| ------------ | ------------ | -------- | -------------- | ----------------- |
| pip          | medium       | ❌        | ❌              | partial           |
| poetry       | slow         | ✅        | ❌              | ✅                 |
| pipx         | medium       | ❌        | ✅              | ❌                 |
| **uv + uvx** | ⚡ very fast | ✅        | ✅              | ✅                 |

---

## 🪶 Key Features

| Feature                     | Description                                                |
| --------------------------- | ---------------------------------------------------------- |
| **Very fast**               | written in Rust (10–20× faster than pip/poetry)            |
| **Deterministic builds**    | via `uv.lock`                                              |
| **Isolated tools (`uvx`)**  | no global installations required                           |
| **PEP-compatible**          | supports `pyproject.toml`, PEP 621                         |
| **Cache sharing**           | reuses packages from the global cache                      |
| **Compatible**              | works with existing virtual environments and Pipfiles      |


---

## 📚 Further Resources

* 🔗 [https://docs.astral.sh/uv](https://docs.astral.sh/uv)
* 🔗 [https://astral.sh/blog/uv](https://astral.sh/blog/uv)
* 🔗 [https://github.com/astral-sh/uv](https://github.com/astral-sh/uv)

---


## 1. Installation via uv

```bash
# Create and activate a virtual environment (optional but recommended)
uv venv
# macOS/Linux
source .venv/bin/activate
# Windows (PowerShell)
.venv\Scripts\Activate.ps1

# install via uv from PyPI
uv pip install pyproj_dep_analyze
# optional install from GitHub
uv pip install "git+https://github.com/bitranox/pyproj_dep_analyze"
# upgrade
uv tool upgrade --all
```

## 2.  One Time run via uvx

One-off/ad-hoc usage lets you run the tool without adding it to the project.
Multiple projects with different tool versions stay isolated so each can use "its" uvx version without conflicts.

```bash
# run from PyPI
uvx pyproj_dep_analyze
# run from GitHub
uvx --from git+https://github.com/bitranox/pyproj_dep_analyze.git pyproj_dep_analyze

```

---

## 3. Installation via pip

```bash
# optional, install in a venv (recommended)
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
# install from PyPI
pip install pyproj_dep_analyze 
# optional install from GitHub
pip install "git+https://github.com/bitranox/pyproj_dep_analyze"
# optional development install from local
pip install -e .[dev]
# optional install from local runtime only:
pip install .
```

## 4. Per-User Installation (No Virtualenv) - from local

```bash
# install from PyPI
pip install --user pyproj_dep_analyze 
# optional install from GitHub
pip install --user "git+https://github.com/bitranox/pyproj_dep_analyze"
# optional install from local
pip install --user .
```

> Note: This respects PEP 668. Avoid using it on system Python builds marked as
> "externally managed". Ensure `~/.local/bin` (POSIX) is on your PATH so the CLI is available.

## 5. pipx (Isolated CLI-Friendly Environment)

```bash
# install pipx via pip
python -m pip install pipx
# optional install pipx via apt
sudo apt install python-pipx
# install via pipx from PyPI
pipx install pyproj_dep_analyze
# optional install via pipx from GitHub
pipx install "git+https://github.com/bitranox/pyproj_dep_analyze"
# optional install from local
pipx install .
pipx upgrade pyproj_dep_analyze
# From Git tag/commit:
```

## 6. From Build Artifacts

```bash
python -m build
pip install dist/pyproj_dep_analyze-*.whl
pip install dist/pyproj_dep_analyze-*.tar.gz   # sdist
```

## 7. Poetry or PDM Managed Environments

```bash
# Poetry
poetry add pyproj_dep_analyze     # as dependency
poetry install                          # for local dev

# PDM
pdm add pyproj_dep_analyze
pdm install
```

## 8. Install Directly from Git

```bash
pip install "git+https://github.com/bitranox/pyproj_dep_analyze#egg=pyproj_dep_analyze"
```

## 9. System Package Managers (Optional Distribution Channels)

- Deb/RPM: Package with `fpm` for OS-native delivery

All methods register both the `pyproj_dep_analyze` and
`pyproj-dep-analyze` commands on your PATH.
