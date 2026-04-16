<div align="center">

# 🧠 NeuralMind

### **Stop Wasting Tokens. Start Understanding Code.**

[![CI](https://github.com/dfrostar/neuralmind/actions/workflows/ci.yml/badge.svg)](https://github.com/dfrostar/neuralmind/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**NeuralMind gives AI assistants 40-70x more efficient access to your codebase.**

[Why NeuralMind?](#-why-neuralmind) •
[Install in 2 Minutes](#-installation) •
[Quick Start](#-quick-start) •
[How It Works](#-how-it-works) •
[Wiki](https://github.com/dfrostar/neuralmind/wiki)

</div>

---

## 🎯 Why NeuralMind?

### The Problem

When you ask Claude, GPT-4, or Cursor about your codebase:

| Traditional Approach | Tokens Used | Result |
|---------------------|-------------|--------|
| Load entire codebase | **50,000+** | ❌ Hits context limits, expensive, slow |
| Load a few files manually | **5,000** | ❌ Misses important context |
| Hope the AI figures it out | **0** | ❌ Wrong answers, hallucinations |

### The Solution

**NeuralMind loads only what's relevant to your question:**

| NeuralMind Approach | Tokens Used | Result |
|--------------------|-------------|--------|
| Wake-up context | **~400** | ✅ AI understands project structure |
| Query context | **~800-1,100** | ✅ AI gets relevant code clusters |
| **Total** | **~1,500** | ✅ **40-70x fewer tokens!** |

### Real Benchmarks

| Project | Codebase Size | NeuralMind Tokens | Reduction |
|---------|---------------|-------------------|----------|
| cmmc20 (full-stack app) | 241 code entities | 765 avg | **65.6x** |
| mempalace (Python lib) | 1,626 code entities | 1,089 avg | **46.0x** |

---

## 📦 Installation

### Step 1: Install NeuralMind

```bash
# From GitHub (available now)
pip install git+https://github.com/dfrostar/neuralmind.git

# From PyPI (coming soon)
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
### Cluster 1 (relevance: 2.45)
Contains: 5 codes
- AuthService (code) — authService.ts
- hashPassword() (code) — authService.ts
- verifyToken() (code) — authService.ts
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

## 🔧 How It Works

### 4-Layer Progressive Disclosure

NeuralMind uses a smart layering system to minimize tokens:

```
┌─────────────────────────────────────────────────────┐
│  L0: Identity (~100 tokens)                         │
│  "Project name, description, graph stats"           │
│  └── Always loaded                                  │
├─────────────────────────────────────────────────────┤
│  L1: Summary (~300 tokens)                          │
│  "Architecture overview, main code clusters"        │
│  └── Always loaded                                  │
├─────────────────────────────────────────────────────┤
│  L2: On-Demand (~200-400 tokens)                    │
│  "Relevant modules based on your query"             │
│  └── Loaded per query                               │
├─────────────────────────────────────────────────────┤
│  L3: Search Results (~200-400 tokens)               │
│  "Semantic search matches"                          │
│  └── Loaded per query                               │
└─────────────────────────────────────────────────────┘

Total: ~800-1,100 tokens vs 50,000+ for full codebase
```

### Data Flow

```
Your Code → Graphify → graph.json → NeuralMind → ChromaDB
                                         ↓
                              Smart Context for AI
```

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

## 📊 Why This Matters

| Benefit | Impact |
|---------|--------|
| **Cost Savings** | 40-70x fewer tokens = 40-70x lower API costs |
| **Faster Responses** | Less to process = faster AI responses |
| **Better Answers** | Relevant context = more accurate answers |
| **Longer Conversations** | More room for back-and-forth |
| **Works Everywhere** | CLI, Python API, MCP server |

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

</div>
