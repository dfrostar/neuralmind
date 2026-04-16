# Welcome to NeuralMind Wiki

<div align="center">

🧠 **Adaptive Neural Knowledge System for AI Code Understanding**

*Achieve 40-70x token reduction when working with AI coding assistants*

</div>

---

## What is NeuralMind?

NeuralMind is a Python library that creates intelligent, query-aware context from your codebase knowledge graphs. When working with AI coding assistants like Claude, GPT-4, or Cursor, context window limits are a fundamental challenge. Loading an entire codebase consumes 50,000+ tokens, leaving little room for meaningful conversation.

NeuralMind solves this by implementing a **4-layer progressive disclosure architecture** that loads only what's relevant to your query—achieving massive token savings while maintaining deep understanding of your code.

## Quick Links

| Page | Description |
|------|-------------|
| [Installation](Installation.md) | Detailed setup instructions for all platforms |
| [CLI Reference](CLI-Reference.md) | Complete command-line interface documentation |
| [API Reference](API-Reference.md) | Python API documentation with examples |
| [Architecture](Architecture.md) | Deep dive into the 4-layer system |
| [Integration Guide](Integration-Guide.md) | MCP, graphify, and tool integrations |
| [Troubleshooting](Troubleshooting.md) | Common issues and solutions |

## Key Features

### 🚀 Massive Token Reduction
40-70x fewer tokens than loading full codebases. Turn 50,000+ token contexts into ~1,000 tokens.

### 📊 4-Layer Progressive Disclosure
Intelligent layering system that loads context progressively:
- **L0: Identity** (~100 tokens) - Project name, description
- **L1: Summary** (~500 tokens) - Architecture overview
- **L2: On-Demand** (~200-500 tokens) - Query-relevant modules
- **L3: Search** (~200-500 tokens) - Semantic search results

### 🔍 Semantic Search
Find code entities by meaning, not just keywords. Powered by ChromaDB embeddings.

### 🏘️ Community Awareness
Understands logical code clusters and their relationships through graph-based analysis.

### 🔌 MCP Integration
Model Context Protocol server for seamless integration with Claude Desktop, Cursor, and other MCP-compatible tools.

### ⚡ Incremental Updates
Only re-embed changed nodes for fast rebuilds when your code changes.

## Quick Start

```bash
# Install NeuralMind
pip install neuralmind

# Generate knowledge graph (requires graphify)
pip install graphifyy
graphify update /path/to/project

# Build neural index
neuralmind build /path/to/project

# Query your codebase
neuralmind query /path/to/project "How does authentication work?"
```

## Benchmarks

| Project | Nodes | Communities | Avg Tokens | Reduction |
|---------|-------|-------------|------------|------------|
| cmmc20 | 241 | 93 | 765 | **65.6x** |
| mempalace | 1,626 | 34 | 1,089 | **46.0x** |

## Getting Help

- **GitHub Issues**: [Report bugs or request features](https://github.com/dfrostar/neuralmind/issues)
- **Discussions**: [Ask questions and share ideas](https://github.com/dfrostar/neuralmind/discussions)
- **Contributing**: See our [Contributing Guide](https://github.com/dfrostar/neuralmind/blob/main/CONTRIBUTING.md)

## License

NeuralMind is released under the MIT License. See [LICENSE](https://github.com/dfrostar/neuralmind/blob/main/LICENSE) for details.
