# Installation Guide

This guide covers all installation methods for NeuralMind, including system requirements, dependencies, and platform-specific instructions.

NeuralMind is a local, offline Python package — no SaaS, no accounts, no outbound calls. Once installed, it works from the CLI, via its MCP server, and (for Claude Code) as a PostToolUse compression layer. See the [Setup Guide](Setup-Guide) for post-install configuration or [Use Cases](Use-Cases) to pick a workflow first.

## Table of Contents

- [System Requirements](#system-requirements)
- [Quick Install](#quick-install)
- [Installation Methods](#installation-methods)
  - [From PyPI](#from-pypi)
  - [From Source](#from-source)
  - [Development Installation](#development-installation)
- [Dependencies](#dependencies)
- [Platform-Specific Instructions](#platform-specific-instructions)
- [Verification](#verification)
- [Troubleshooting](#troubleshooting)

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
2. **pip**: Usually included with Python
3. **git** (optional): For source installation
4. **graphify**: For generating knowledge graphs from codebases

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

---

## Installation Methods

### From PyPI

The recommended installation method for most users.

#### Basic Installation

```bash
pip install neuralmind
```

#### With MCP Server Support

For integration with Claude Desktop, Cursor, and other MCP-compatible tools:

```bash
pip install neuralmind[mcp]
```

#### With Development Tools

For contributors or those who want testing/linting tools:

```bash
pip install neuralmind[dev]
```

#### Full Installation

All optional dependencies:

```bash
pip install neuralmind[mcp,dev]
```

### From Source

For the latest development version or contributors:

```bash
# Clone the repository
git clone https://github.com/dfrostar/neuralmind.git
cd neuralmind

# Install in editable mode
pip install -e .

# Or with all extras
pip install -e ".[mcp,dev]"
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

### Optional Dependencies

#### MCP Extra (`pip install neuralmind[mcp]`)

| Package | Version | Purpose |
|---------|---------|----------|
| mcp | ≥0.1.0 | Model Context Protocol server |

#### Dev Extra (`pip install neuralmind[dev]`)

| Package | Version | Purpose |
|---------|---------|----------|
| pytest | ≥7.0 | Testing framework |
| pytest-asyncio | ≥0.21.0 | Async test support |
| black | ≥23.0 | Code formatting |
| ruff | ≥0.1.0 | Fast linting |

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

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install NeuralMind
RUN pip install neuralmind[mcp]

# Your project files
COPY . .

CMD ["neuralmind-mcp"]
```

---

## Verification

### Check Installation

```bash
# Check CLI is available
neuralmind --help

# Check version
python -c "import neuralmind; print('NeuralMind installed successfully')"
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
