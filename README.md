# 🧠 NeuralMind

[![PyPI version](https://badge.fury.io/py/neuralmind.svg)](https://pypi.org/project/neuralmind/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

**Adaptive Neural Knowledge System — 40-70x token reduction for AI code understanding**

> Stop paying $450/month for AI coding queries. NeuralMind reduces it to $7/month.

## 🎯 The Problem

```
You: "How does authentication work in my codebase?"

❌ Traditional: Load entire codebase → 50,000 tokens → $0.15-$3.75/query
✅ NeuralMind: Smart context → 766 tokens → $0.002-$0.06/query
```

## 💰 Real Savings

| Model | Without NeuralMind | With NeuralMind | Monthly Savings |
|-------|-------------------|-----------------|----------------|
| Claude 3.5 Sonnet | $450/month | $7/month | **$443** |
| GPT-4o | $750/month | $12/month | **$738** |
| GPT-4.5 | $11,250/month | $180/month | **$11,070** |
| Claude Opus | $2,250/month | $36/month | **$2,214** |

*Based on 100 queries/day. [Pricing sources](https://openrouter.ai/models)*

## 🚀 Quick Start

```bash
# Install
pip install neuralmind graphifyy

# Generate knowledge graph
cd your-project
graphify update .

# Build neural index
neuralmind build .

# Query your codebase
neuralmind query . "How does authentication work?"
```

## ✨ Key Features

| Feature | Description |
|---------|-------------|
| **4-Layer Context** | Progressive disclosure — only loads what's relevant |
| **Semantic Search** | Finds code by meaning, not just keywords |
| **Query-Aware** | Different questions get different context |
| **CLI Tool** | Simple commands: `build`, `query`, `wakeup`, `search` |
| **MCP Server** | Direct integration with Claude Desktop & Cursor |
| **Auto-Updates** | Git hooks and scheduled maintenance |

## 📊 Benchmarks

| Project | Nodes | Avg Token Reduction |
|---------|-------|--------------------|
| cmmc20 (React/Node) | 241 | **65.6x** |
| mempalace (Python) | 1,626 | **46.0x** |

## 🔧 How It Works

```
┌─────────────────────────────────────────────────────────────┐
│ Layer 0: Project Identity (~100 tokens) - ALWAYS LOADED     │
├─────────────────────────────────────────────────────────────┤
│ Layer 1: Architecture Summary (~300 tokens) - ALWAYS LOADED │
├─────────────────────────────────────────────────────────────┤
│ Layer 2: Relevant Modules (~300 tokens) - QUERY-SPECIFIC    │
├─────────────────────────────────────────────────────────────┤
│ Layer 3: Semantic Search (~300 tokens) - QUERY-SPECIFIC     │
└─────────────────────────────────────────────────────────────┘

Total: ~800-1,100 tokens vs 50,000+ for full codebase
```

## 📋 Use Cases

1. **Daily Development** — Get context for AI coding questions
2. **New Developer Onboarding** — Generate project overviews
3. **Code Review** — Understand related code quickly
4. **Documentation** — AI-assisted docs from actual code
5. **CI/CD Integration** — Auto-update context files
6. **IDE Integration** — MCP server for Claude/Cursor

👉 **[See full use cases and examples in USAGE.md](USAGE.md)**

## 🖥️ CLI Commands

| Command | Purpose |
|---------|--------|
| `neuralmind build .` | Build/rebuild neural index |
| `neuralmind query . "..."` | Query with natural language |
| `neuralmind wakeup .` | Get project overview |
| `neuralmind search . "..."` | Direct semantic search |
| `neuralmind benchmark .` | Measure token reduction |
| `neuralmind stats .` | Show index statistics |

## ⏰ Scheduling Updates

### Git Hook (Recommended)
```bash
# .git/hooks/post-commit
#!/bin/bash
graphify update . --quiet
neuralmind build . --quiet
```

### Cron Job
```bash
# Daily at 6 AM
0 6 * * * cd /project && graphify update . && neuralmind build .
```

### CI/CD
```yaml
- run: pip install neuralmind graphifyy
- run: graphify update . && neuralmind build .
- run: neuralmind wakeup . > AI_CONTEXT.md
```

👉 **[See full scheduling guide in USAGE.md](USAGE.md#scheduling-routines)**

## 🔌 MCP Server Integration

For Claude Desktop or Cursor:

```json
{
  "mcpServers": {
    "neuralmind": {
      "command": "neuralmind-mcp",
      "args": ["/path/to/project"]
    }
  }
}
```

## 📚 Documentation

- **[USAGE.md](USAGE.md)** — Complete usage guide with examples
- **[Wiki](https://github.com/dfrostar/neuralmind/wiki)** — Full documentation
- **[API Reference](https://github.com/dfrostar/neuralmind/wiki/API-Reference)** — Python API docs

## 🤝 Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

<p align="center">
  <b>⭐ Star this repo if NeuralMind saves you money!</b>
</p>
