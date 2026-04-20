# 🧠 NeuralMind Wiki

Welcome to the NeuralMind documentation!

## Quick Links

| Page | Description |
|------|-------------|
| **[Setup Guide](Setup-Guide)** | **First-time setup for any platform (Claude Code, Copilot, Cursor, VSCode)** |
| **[Learning Guide](Learning-Guide)** | **NEW: How your project learns and improves (v0.3.2+)** |
| **[Brain-Like Learning](../brain_like_learning.md)** | **Design rationale: Why learning matters (v0.3.0+)** |
| [Installation](Installation) | How to install NeuralMind |
| [Usage Guide](Usage-Guide) | Complete usage guide with examples |
| [CLI Reference](CLI-Reference) | All CLI commands |
| [API Reference](API-Reference) | Python API documentation |
| [Architecture](Architecture) | How the 4-layer system works |
| [Integration Guide](Integration-Guide) | MCP, CI/CD, IDE setup |
| [Troubleshooting](Troubleshooting) | Common issues and fixes |

## What is NeuralMind?

NeuralMind is an intelligent context system that dramatically reduces the tokens needed when working with AI coding assistants like Claude, GPT-4, and Cursor.

### The Core Problem

```
You: "How does authentication work in my codebase?"

❌ Traditional: Load entire codebase → 50,000 tokens → $0.15-$3.75/query
✅ NeuralMind: Smart context → 766 tokens → $0.002-$0.06/query
```

### Key Benefits

- **40-70x token reduction** — Only loads relevant context
- **98% cost savings** — $450/month → $7/month
- **Query-aware** — Different questions get different context
- **Easy to use** — Simple CLI commands

## Quick Start

```bash
# Install
pip install neuralmind graphifyy

# Setup
cd your-project
graphify update .
neuralmind build .

# Use
neuralmind query . "How does authentication work?"
```

## Use Cases

1. **Daily Development** — Get context for AI coding questions
2. **Onboarding** — Generate project overviews for new team members
3. **Code Review** — Understand related code quickly
4. **Documentation** — AI-assisted docs from actual code
5. **CI/CD** — Auto-update context files
6. **IDE Integration** — MCP server for Claude/Cursor

👉 **[See full use cases in Usage Guide](Usage-Guide)**

## Support

- **[GitHub Issues](https://github.com/dfrostar/neuralmind/issues)** — Bug reports
- **[GitHub Discussions](https://github.com/dfrostar/neuralmind/discussions)** — Questions & ideas
