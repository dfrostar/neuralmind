# Installation Guide

This guide covers all installation methods for NeuralMind, including system requirements, dependencies, and platform-specific instructions.

NeuralMind is a local, offline Python package — no SaaS, no accounts, no outbound calls. Once installed, it works from the CLI, via its MCP server, and (for Claude Code) as a PostToolUse compression layer. See the [Setup Guide](Setup-Guide) for post-install configuration or [Use Cases](Use-Cases) to pick a workflow first.

## Table of Contents

- [Install — pick your path](#install--pick-your-path) *(new in v0.6.1)*
- [System Requirements](#system-requirements)
- [Quick Install](#quick-install)
- [Installation Methods](#installation-methods)
  - [From PyPI](#from-pypi)
  - [pipx](#pipx)
  - [uv](#uv)
  - [Docker](#docker)
  - [From Source](#from-source)
  - [Development Installation](#development-installation)
- [Dependencies](#dependencies)
- [Platform-Specific Instructions](#platform-specific-instructions)
- [Verification](#verification)
- [Troubleshooting](#troubleshooting)

---

## Install — pick your path

*New in [v0.6.1](../../blob/main/RELEASE_NOTES_v0.6.1.md).* NeuralMind installs five ways. All paths deliver the same package — the `neuralmind` CLI, the `neuralmind-mcp` server, and the Python module.

| Method | Command | When to pick |
|---|---|---|
| **pip** | `pip install neuralmind graphifyy` | Default. Drops it in your active env. |
| **pipx** | `pipx install neuralmind && pipx inject neuralmind graphifyy` | Global CLI, no env pollution. |
| **uv** | `uv pip install neuralmind graphifyy` | Modern, fast Python tooling. |
| **Docker** | `docker build -t neuralmind:dev . && docker run --rm -v "$PWD:/project:ro" neuralmind:dev neuralmind --help` | Containerized — no Python on the host. **Build locally for now**; GHCR auto-publish (`ghcr.io/dfrostar/neuralmind`) lands in a later release. |
| **From source** | `git clone https://github.com/dfrostar/neuralmind && pip install -e .` | Hacking on NeuralMind itself. |

**Verify any install:**

```bash
neuralmind --help     # works for every path

# For pip / uv / source (a Python env where neuralmind is importable):
python -c "import neuralmind; print(neuralmind.__version__)"
```

Full walkthrough with pros and cons of each path: [Install paths](../../blob/main/docs/use-cases/install-paths.md).

The sections below remain the deep reference — system requirements, dependency tables, platform-specific notes, and troubleshooting.

---

## System Requirements

### Minimum Requirements

| Component | Requirement |
|-----------|-------------|
| Python | 3.10 or higher |
| Memory | 2GB RAM (4GB+ recommended for large codebases) |
| Storage | 500MB for base install + space for embeddings |
| OS | Linux, macOS, Windows 10+ |

### Software Prerequisites

1. **Python 3.10+**: Download from [python.org](https://www.python.org/downloads/)
2. **pip** (or [pipx](https://pipx.pypa.io/) / [uv](https://docs.astral.sh/uv/)): Usually included with Python
3. **git** (optional): For source installation
4. **graphify**: For generating knowledge graphs from codebases (installed alongside NeuralMind in every path above)

---

## Quick Install

For most users, the quickest path:

```bash
# Install NeuralMind
pip install neuralmind

# Install graphify for knowledge graph generation
pip install graphifyy

# Verify installation
neuralmind --help
```

> **Prefer one of the other four install paths?** See the [install matrix](#install--pick-your-path) above.

---

## Installation Methods

### From PyPI

The default installation method.

#### Default Installation

```bash
pip install neuralmind
```

This includes everything most users need: the CLI, the semantic
indexing layer, and the MCP server (`neuralmind-mcp`) for Claude
Desktop, Claude Code, Cursor, Cline, Continue, Hermes-Agent,
OpenClaw, and any other MCP-compatible client.

> **Note for users upgrading from v0.4.x or earlier:** the MCP
> server used to be gated behind an `[mcp]` extra. From v0.5.0
> onward it ships in the base package. Existing
> `pip install "neuralmind[mcp]"` commands still work — the `mcp`
> extra is preserved as an empty no-op for backwards compatibility.

#### With Development Tools

For contributors or those who want testing/linting tools:

```bash
pip install neuralmind[dev]
```

#### Full Installation

All extras (equivalent to `[dev]` since v0.5.0):

```bash
pip install neuralmind[all]
```

### pipx

[pipx](https://pipx.pypa.io/) installs each Python application in its own dedicated venv and exposes the entry points on your PATH globally. `neuralmind` and `neuralmind-mcp` are then available from any directory without activating anything.

```bash
pipx install neuralmind
pipx inject neuralmind graphifyy
```

**Trade-off:** because pipx isolates the package, `import neuralmind` from your project's own Python won't work. If you also script against the Python API, use `pip` in a project venv instead.

### uv

[uv](https://docs.astral.sh/uv/) is Astral's Rust-based Python package manager — significantly faster installs, drop-in for pip, compatible venvs.

```bash
uv pip install neuralmind graphifyy
```

For a `uv`-managed project:

```bash
uv add neuralmind graphifyy
```

### Docker

The repo ships a multi-stage `Dockerfile` in the root. Build it locally for now — the GHCR auto-publish (`ghcr.io/dfrostar/neuralmind`) lands in a later release.

```bash
# Build
docker build -t neuralmind:dev .

# Run the MCP server against the current directory (read-only mount)
docker run --rm -i \
  -v "$PWD:/project:ro" \
  neuralmind:dev neuralmind-mcp /project

# Run the graph view on http://localhost:8765
docker run --rm -p 8765:8765 \
  -v "$PWD:/project:ro" \
  neuralmind:dev \
  neuralmind serve /project --host 0.0.0.0 --no-auth
```

To persist the index between runs, mount the project directory read-write so `.neuralmind/` and `graphify-out/` land on the host:

```bash
docker run --rm -v "$PWD:/project" neuralmind:dev neuralmind build /project
```

### From Source

For the latest development version or contributors:

```bash
# Clone the repository
git clone https://github.com/dfrostar/neuralmind.git
cd neuralmind

# Install in editable mode
pip install -e .

# Or with dev tools
pip install -e ".[dev]"
```

### Development Installation

Recommended setup for contributors:

```bash
# Clone and enter directory
git clone https://github.com/dfrostar/neuralmind.git
cd neuralmind

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/macOS
# or: venv\Scripts\activate  # Windows

# Install with dev dependencies
pip install -e ".[dev]"

# Install pre-commit hooks (optional)
pre-commit install
```

---

## Dependencies

### Core Dependencies (Automatically Installed)

| Package | Version | Purpose |
|---------|---------|----------|
| chromadb | ≥0.4.0 | Vector database for embeddings |
| pyyaml | ≥6.0 | Configuration file parsing |
| toml | ≥0.10 | TOML configuration file support |
| mcp | ≥1.23.0 | Model Context Protocol server (since v0.5.0) |

### Optional Dependencies

#### Dev Extra (`pip install neuralmind[dev]`)

| Package | Version | Purpose |
|---------|---------|----------|
| pytest | ≥7.0 | Testing framework |
| pytest-asyncio | ≥0.21.0 | Async test support |
| black | ≥23.0 | Code formatting |
| ruff | ≥0.1.0 | Fast linting |

#### Legacy `[mcp]` extra

`pip install "neuralmind[mcp]"` still resolves cleanly — the extra
is preserved as an empty no-op so existing install commands in user
docs, blog posts, and CI configs keep working. No reason to use it
in new commands; `pip install neuralmind` already includes the MCP
server.

### External Tools

| Tool | Installation | Purpose |
|------|--------------|----------|
| graphify | `pip install graphifyy` | Knowledge graph generation |

---

## Platform-Specific Instructions

### Linux (Ubuntu/Debian)

```bash
# Ensure Python 3.10+ is installed
sudo apt update
sudo apt install python3.10 python3.10-venv python3-pip

# Create virtual environment (recommended)
python3.10 -m venv neuralmind-env
source neuralmind-env/bin/activate

# Install NeuralMind
pip install neuralmind
```

### macOS

```bash
# Using Homebrew
brew install python@3.11

# Create virtual environment
python3.11 -m venv neuralmind-env
source neuralmind-env/bin/activate

# Install NeuralMind
pip install neuralmind
```

### Windows

```powershell
# Ensure Python 3.10+ is installed from python.org
# Open PowerShell as Administrator

# Create virtual environment
python -m venv neuralmind-env
.\neuralmind-env\Scripts\Activate.ps1

# Install NeuralMind
pip install neuralmind
```

### Docker

Use the repo's [`Dockerfile`](../../blob/main/Dockerfile) — multi-stage, non-root, transitive deps pre-wheeled in the builder stage so the runtime image doesn't need a C toolchain. See the [Docker section above](#docker) for the build and run commands, or the [install-paths walkthrough](../../blob/main/docs/use-cases/install-paths.md#4-docker--no-python-on-the-host) for persistence and security notes.

If you want a minimal app-style Dockerfile for embedding NeuralMind inside another image:

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install NeuralMind (MCP server is bundled by default) + graph builder
RUN pip install --no-cache-dir neuralmind graphifyy

# Your project files
COPY . .

CMD ["neuralmind-mcp"]
```

---

## Verification

### Check Installation

```bash
# Check CLI is available — works for every install path
neuralmind --help

# Check version — pip / uv / source paths only
# (pipx isolates the package in its own venv; Docker runs in-container)
python -c "import neuralmind; print(neuralmind.__version__)"
```

### Verify Dependencies

```bash
# Check ChromaDB
python -c "import chromadb; print(f'ChromaDB version: {chromadb.__version__}')"

# Check graphify (if installed)
graphify --help
```

### Test with Sample Project

```bash
# Create a test directory
mkdir test-neuralmind
cd test-neuralmind

# Create a simple Python file
echo 'def hello(): return "world"' > hello.py

# Generate knowledge graph (requires graphify)
graphify update .

# Build neural index
neuralmind build .

# Test query
neuralmind wakeup .
```

---

## Troubleshooting

### Common Issues

#### "Command not found: neuralmind"

**Cause**: Python scripts directory not in PATH.

**Solution**:
```bash
# Linux/macOS
export PATH="$HOME/.local/bin:$PATH"

# Then retry
neuralmind --help
```

#### "No module named 'chromadb'"

**Cause**: Dependencies not installed properly.

**Solution**:
```bash
pip install --upgrade neuralmind
# or
pip install chromadb>=0.4.0
```

#### "graph.json not found"

**Cause**: Knowledge graph not generated.

**Solution**:
```bash
# Install graphify if not present
pip install graphifyy

# Generate knowledge graph
graphify update /path/to/your/project

# Then build neural index
neuralmind build /path/to/your/project
```

#### Memory Error on Large Codebases

**Cause**: Insufficient RAM for embedding generation.

**Solution**:
- Close other applications
- Process in batches using `--force` flag to rebuild incrementally
- Consider using a machine with more RAM

#### SSL Certificate Errors

**Cause**: Corporate proxy or certificate issues.

**Solution**:
```bash
pip install --trusted-host pypi.org --trusted-host pypi.python.org neuralmind
```

### Getting Help

- **GitHub Issues**: [Report bugs](https://github.com/dfrostar/neuralmind/issues)
- **Discussions**: [Ask questions](https://github.com/dfrostar/neuralmind/discussions)

---

## Next Steps

After installation:

1. [Generate a knowledge graph](Integration-Guide.md#graphify-integration) for your project
2. [Build the neural index](CLI-Reference.md#build) using `neuralmind build`
3. [Query your codebase](CLI-Reference.md#query) with natural language
4. [Set up MCP integration](Integration-Guide.md#mcp-integration) for Claude Desktop
