# 🧠 NeuralMind

[![PyPI version](https://badge.fury.io/py/neuralmind.svg)](https://pypi.org/project/neuralmind/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

**Two-phase token optimization for Claude Code — smart retrieval + tool-output compression in one package.**

> Most tools save tokens on what you *fetch* OR on what Claude *sees back* — never both.
> NeuralMind v0.2.0 does both in one `pip install`.

## ⚡ Two-phase optimization

```
┌─────────────────────────────────────────────────────────────┐
│ Phase 1: Retrieval — what to fetch                          │
│   neuralmind wakeup .    →  ~365 tokens (vs 50K raw)        │
│   neuralmind query "?"   →  ~800 tokens (vs 2,700 raw)      │
│   mcp: neuralmind_skeleton  →  graph-backed file view       │
├─────────────────────────────────────────────────────────────┤
│ Phase 2: Consumption — what Claude actually sees            │
│   PostToolUse hooks compress Read/Bash/Grep output          │
│   File reads → graph skeleton (~88% reduction)              │
│   Bash output → errors + summary (~91% reduction)           │
│   Search results → capped at 25 matches                     │
└─────────────────────────────────────────────────────────────┘
```

**Combined effect: 5-10× total reduction vs baseline Claude Code.**

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

# (v0.2.0) Install PostToolUse hooks — compresses Read/Bash/Grep
neuralmind install-hooks .

# Query your codebase
neuralmind query . "How does authentication work?"

# (v0.2.0) Skeleton view of a file without loading source
neuralmind skeleton tools/voiceover.py
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
| `neuralmind skeleton <file>` | **v0.2.0** Compact graph-backed file view |
| `neuralmind install-hooks .` | **v0.2.0** Install PostToolUse compression hooks (project) |
| `neuralmind install-hooks --global` | **v0.2.0** Install hooks globally for all projects |
| `neuralmind install-hooks --uninstall` | **v0.2.0** Remove hooks (preserves other tools' hooks) |
| `neuralmind init-hook .` | Install git post-commit hook (auto-rebuild on commit) |

## 🪝 PostToolUse Compression (v0.2.0)

NeuralMind ships with Claude Code hooks that compress tool outputs **before** the model sees them:

| Tool | Compression | Typical savings |
|------|-------------|----------------|
| **Read** | Replaces raw source with graph skeleton (functions, rationales, call graph) | ~88% |
| **Bash** | Keeps errors + last 3 lines + summary; drops routine output | ~91% |
| **Grep** | Caps at 25 matches + "N more hidden" pointer | varies |

**Install per-project (recommended):**
```bash
cd my-project
neuralmind install-hooks .    # writes .claude/settings.json
```

**Install globally (all projects):**
```bash
neuralmind install-hooks --global    # writes ~/.claude/settings.json
```

**Bypass temporarily** (for debugging):
```bash
NEURALMIND_BYPASS=1 claude-code ...
```

**Uninstall cleanly** (preserves other hooks):
```bash
neuralmind install-hooks --uninstall    # project
neuralmind install-hooks --uninstall --global    # global
```

The hook installer is **idempotent** and **non-destructive** — existing hooks from other tools (Prettier, Black, etc.) are preserved.

### Coming from Pith?

NeuralMind v0.2.0 provides full Pith-parity compression plus graph-backed retrieval — both in one package. Migration:
```bash
# Remove Pith global hooks, then:
pip install neuralmind
neuralmind install-hooks --global
```
Unlike Pith's regex-based skeletonization, NeuralMind uses the semantic graph you've already built, so skeletons include rationales, call graphs, and cross-file edges that regex can't extract.

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

**Exposed MCP tools (v0.2.0):**

| Tool | Purpose |
|------|---------|
| `mcp__neuralmind__wakeup` | Minimal project overview (~365 tokens) |
| `mcp__neuralmind__query` | Natural language code query (~800 tokens) |
| `mcp__neuralmind__search` | Direct semantic search with scores |
| `mcp__neuralmind__skeleton` | **v0.2.0** Compact file view (functions, rationales, calls) |
| `mcp__neuralmind__stats` | Index health |
| `mcp__neuralmind__benchmark` | Measure token reduction |
| `mcp__neuralmind__build` | Rebuild index |

**Project-scoped auto-registration**: drop a `.mcp.json` at your project root and Claude Code loads it on open:

```json
{
  "mcpServers": {
    "neuralmind": {
      "command": "neuralmind-mcp",
      "args": ["."]
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
