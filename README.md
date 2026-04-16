<div align="center">

# 🧠 NeuralMind

### **Stop Wasting Tokens. Start Understanding Code.**

[![CI](https://github.com/dfrostar/neuralmind/actions/workflows/ci.yml/badge.svg)](https://github.com/dfrostar/neuralmind/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**NeuralMind gives AI assistants 40-70x more efficient access to your codebase.**

[Why NeuralMind?](#-the-problem-youre-facing) •
[How It Works](#-how-neuralmind-solves-this) •
[Installation](#-installation) •
[Quick Start](#-quick-start) •
[Use Cases](#-use-cases) •
[Wiki](https://github.com/dfrostar/neuralmind/wiki)

</div>

---

## 🎯 The Problem You're Facing

Every time you ask an AI assistant (Claude, GPT-4, Cursor, Copilot) about your codebase, you face a fundamental trade-off:

### The Context Window Dilemma

| Approach | What You Do | Tokens Used | The Problem |
|----------|------------|-------------|-------------|
| **Full Codebase** | Load everything | 50,000+ | ❌ Hits context limits, costs $$$, slow |
| **Manual Selection** | Pick a few files | 2,000-5,000 | ❌ Miss important dependencies & context |
| **No Context** | Just ask | 0 | ❌ AI guesses, hallucinates, gives wrong answers |

### Real Cost Impact

```
With Claude 3.5 Sonnet (2024 pricing):
- Full codebase context: ~$0.15 per query
- 100 queries/day = $15/day = $450/month

With NeuralMind:
- Smart context: ~$0.003 per query (50x less)
- 100 queries/day = $0.30/day = $9/month
```

---

## 💡 How NeuralMind Solves This

NeuralMind creates an **intelligent, query-aware context system** that loads only what's relevant:

### The 4-Layer Progressive Disclosure System

```
┌─────────────────────────────────────────────────────────────────┐
│  L0: IDENTITY (~100 tokens)                                     │
│  • Project name, purpose, tech stack                            │
│  • "This is a React/Node.js e-commerce platform"                │
│  └── Always loaded - tells AI what it's working with            │
├─────────────────────────────────────────────────────────────────┤
│  L1: ARCHITECTURE (~300 tokens)                                 │
│  • Code clusters: auth, api, database, frontend                 │
│  • Main modules and their relationships                         │
│  └── Always loaded - gives AI the big picture                   │
├─────────────────────────────────────────────────────────────────┤
│  L2: RELEVANT MODULES (~200-400 tokens)                         │
│  • Specific code areas related to your query                    │
│  • "auth" cluster when asking about login                       │
│  └── Query-specific - loaded based on your question             │
├─────────────────────────────────────────────────────────────────┤
│  L3: SEMANTIC SEARCH (~200-400 tokens)                          │
│  • Exact code entities matching your query                      │
│  • Function names, classes, files                               │
│  └── Query-specific - precise semantic matching                 │
└─────────────────────────────────────────────────────────────────┘

                    Total: ~800-1,100 tokens
                    vs. 50,000+ tokens for full codebase
                    = 40-70x REDUCTION
```

### Proven Benchmarks

| Project | Type | Code Entities | Full Context | NeuralMind | Reduction |
|---------|------|---------------|--------------|------------|----------|
| **cmmc20** | Full-stack React/Node | 241 | ~50,000 | 765 avg | **65.6x** |
| **mempalace** | Python library | 1,626 | ~200,000+ | 1,089 avg | **46.0x** |

---

## 🚀 Use Cases

### 1. Daily Development with AI Assistants

**Before NeuralMind:**
```
You: "How does authentication work in this project?"
AI: "I don't have enough context. Can you share the relevant files?"
*You manually search for and paste 5-10 files*
*Hits context limit, loses conversation history*
```

**With NeuralMind:**
```bash
$ neuralmind query . "How does authentication work?"
# Outputs 739 tokens of precisely relevant context
# Paste into AI conversation - instant, accurate answers
```

### 2. Onboarding New Team Members

```bash
# Generate a project overview for new developers
$ neuralmind wakeup .
# ~400 tokens covering project structure, main modules, tech stack
# Perfect for "start of conversation" context
```

### 3. Code Review Context

```bash
# Get context for reviewing a specific feature
$ neuralmind query . "What are all the database migrations and schema?"
# Returns relevant entities: models, migrations, schemas
```

### 4. Documentation Generation

```bash
# Export context for documentation
$ neuralmind query . "What are the main API endpoints?" --json
# Structured output perfect for docs generation
```

### 5. CI/CD Integration

```yaml
# In your GitHub Actions workflow
- name: Generate AI Context
  run: |
    neuralmind build .
    neuralmind query . "What changed in this PR?" > ai_context.md
```

### 6. MCP Server for IDE Integration

```bash
# Run as MCP server for Claude Desktop, Cursor, etc.
$ neuralmind-mcp
# Your AI assistant automatically gets smart context
```

---

## 📦 Installation

### Step 1: Install NeuralMind

```bash
# From GitHub (available now)
pip install git+https://github.com/dfrostar/neuralmind.git

# From PyPI (after release)
pip install neuralmind
```

### Step 2: Install Graphify (creates the knowledge graph)

```bash
pip install graphifyy
```

### Step 3: Verify Installation

```bash
neuralmind --help
graphify --help
```

**That's it!** You're ready to use NeuralMind.

---

## 🚀 Quick Start

### 1. Generate Knowledge Graph (one-time per project)

```bash
cd /path/to/your/project
graphify update .
```

This creates `graphify-out/graph.json` with your codebase structure.

### 2. Build Neural Index

```bash
neuralmind build .
```

**Output:**
```
Building NeuralMind index for: .
Build successful!
   Project: my-project
   Nodes: 241
   Communities: 93
   Duration: 16.65s
```

### 3. Query Your Codebase

```bash
# Get compact context for any question
neuralmind query . "How does authentication work?"
```

**Output:**
```
Query: How does authentication work?
Tokens: 739 (67.7x reduction)
============================================================
## Project: my-project
Knowledge Graph: 241 entities, 93 clusters

## Relevant Code Areas
### Cluster: Authentication (relevance: 2.45)
Contains: 5 entities
- AuthService (class) — src/services/authService.ts
- hashPassword (function) — src/services/authService.ts
- verifyToken (function) — src/middleware/auth.ts
- User (model) — src/models/User.ts
- login (endpoint) — src/routes/auth.ts
...
============================================================
```

### 4. Use with AI Assistants

Copy the output and paste it into your AI conversation for instant, relevant context!

---

## 📖 All Commands

| Command | What It Does | Example |
|---------|--------------|--------|
| `build` | Create neural index from graph.json | `neuralmind build .` |
| `query` | Get context for a question | `neuralmind query . "How does X work?"` |
| `wakeup` | Get minimal startup context | `neuralmind wakeup .` |
| `search` | Semantic search for code | `neuralmind search . "authentication"` |
| `benchmark` | Measure token reduction | `neuralmind benchmark .` |
| `stats` | Show index statistics | `neuralmind stats .` |

### JSON Output (for automation)

```bash
neuralmind query . "How does auth work?" --json
```

---

## 📊 Token Reduction Comparison

### Why This Matters

| Scenario | Without NeuralMind | With NeuralMind | Savings |
|----------|-------------------|-----------------|--------|
| Single query | 50,000 tokens | 800 tokens | **98.4%** |
| 10 queries/day | 500,000 tokens | 8,000 tokens | $14.70/day saved |
| 100 queries/day | 5,000,000 tokens | 80,000 tokens | $147/day saved |
| Monthly (100/day) | 150M tokens | 2.4M tokens | **$4,410/month saved** |

*Based on Claude 3.5 Sonnet pricing: $3/1M input tokens*

### Quality Comparison

| Metric | Full Context | Manual Selection | NeuralMind |
|--------|-------------|------------------|------------|
| Token Usage | ❌ Very High | ⚠️ Medium | ✅ Low |
| Relevance | ⚠️ Includes noise | ⚠️ May miss deps | ✅ Query-aware |
| Consistency | ✅ Complete | ❌ Human error | ✅ Automated |
| Speed | ❌ Slow to load | ❌ Slow to select | ✅ Instant |
| Conversation Length | ❌ Limited | ⚠️ Limited | ✅ Extended |

---

## 🔌 MCP Integration (Claude Desktop, Cursor)

NeuralMind includes an MCP server for direct integration:

```bash
# Install with MCP support
pip install "neuralmind[mcp]"

# Run the server
neuralmind-mcp
```

Add to your Claude Desktop config (`~/.config/claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "neuralmind": {
      "command": "neuralmind-mcp"
    }
  }
}
```

---

## 🐍 Python API

```python
from neuralmind import NeuralMind

# Initialize for your project
mind = NeuralMind('/path/to/project')
mind.build()

# Get wake-up context (for starting conversations)
wakeup = mind.wakeup()
print(f"Tokens: {wakeup.budget.total}")  # ~400

# Get query context (for specific questions)
result = mind.query("How does authentication work?")
print(f"Tokens: {result.budget.total}")  # ~800
print(f"Reduction: {result.reduction_ratio:.1f}x")  # ~65x
print(result.context)  # The actual context to use
```

---

## 📚 Documentation

- **[Wiki Home](https://github.com/dfrostar/neuralmind/wiki)** — Full documentation
- **[Installation Guide](https://github.com/dfrostar/neuralmind/wiki/Installation)** — Detailed setup
- **[CLI Reference](https://github.com/dfrostar/neuralmind/wiki/CLI-Reference)** — All commands
- **[API Reference](https://github.com/dfrostar/neuralmind/wiki/API-Reference)** — Python API
- **[Architecture](https://github.com/dfrostar/neuralmind/wiki/Architecture)** — How it works
- **[Troubleshooting](https://github.com/dfrostar/neuralmind/wiki/Troubleshooting)** — Common issues

---

## 🤝 Contributing

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

```bash
# Clone and install for development
git clone https://github.com/dfrostar/neuralmind.git
cd neuralmind
pip install -e ".[dev]"

# Run tests
pytest
```

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

## 🙏 Acknowledgments

- **[ChromaDB](https://www.trychroma.com/)** — Vector storage
- **[Graphify](https://github.com/safishamsi/graphify)** — Knowledge graph generation
- **[code-review-graph](https://github.com/tirth8205/code-review-graph)** — Inspiration

---

<div align="center">

**Made with 🧠 by [Agent Zero](https://github.com/frdel/agent-zero)**

*Stop wasting tokens. Start understanding code.*

⭐ **Star this repo if NeuralMind helps you save tokens!** ⭐

</div>
