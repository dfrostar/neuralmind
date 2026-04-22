# 🧠 NeuralMind

[![PyPI version](https://badge.fury.io/py/neuralmind.svg)](https://pypi.org/project/neuralmind/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Self-benchmark](https://github.com/dfrostar/neuralmind/actions/workflows/ci-benchmark.yml/badge.svg?branch=main)](https://github.com/dfrostar/neuralmind/actions/workflows/ci-benchmark.yml)
[![Local-First](https://img.shields.io/badge/Local--First-No%20Exfiltration-brightgreen.svg)](#-security--compliance)
[![Offline](https://img.shields.io/badge/Offline-100%25-blue.svg)](#-security--compliance)

**Local-first semantic code intelligence for AI agents — designed for offline compliance, cost optimization at scale, and large monorepos.**

> NeuralMind turns a code repository into a queryable semantic index. Instead of loading 50,000+ tokens of raw source, AI agents retrieve ~800 tokens of smart context — reducing token usage and costs.

> **🌐 [Visit the landing page](https://dfrostar.github.io/neuralmind/) • 📖 [Read the About page](https://dfrostar.github.io/neuralmind/about.html) • ⚖️ Not affiliated with NeuralMind.ai**

---

## 🎯 When NeuralMind Is the Right Choice

**Primary use cases (strong fit):**

1. **Regulated Industries (Healthcare, Finance, Legal)**
   - Code cannot leave your machine
   - Need NIST AI RMF audit trail and compliance reporting
   - Value: Eliminates custom RAG development + audit costs
   - ROI: Breaks even in first month for large teams

2. **Teams with High Query Volume (10+ code questions/day)**
   - LLM bills exceed $100/month on code-related usage
   - Want to optimize costs without hiring more engineers
   - Token reduction: 40-70× on codebases >50K LOC = $450→$7/year per developer

3. **Large Monorepos (500K+ LOC across teams)**
   - Onboarding devs: Reduce from 4-hour manual read → 15-min query
   - Context switching: Skeletons replace full file reads (88% smaller)
   - Team learning: Cooccurrence patterns improve after ~2-3 weeks
   - Value: ~3 hours saved per developer per week × team size

4. **Offline-First Development**
   - Cannot use cloud APIs (air-gapped networks, military, critical infrastructure)
   - Need semantic code search without external dependencies
   - Value: Only tool offering offline + semantic search combo

---

## ⚠️ When NeuralMind Is NOT Recommended

- **Small projects (<50K LOC, 1-5 developers)** — CLAUDE.md + git history is simpler and cheaper
- **One-off code questions** — Setup overhead not worth it for occasional queries
- **Mixed knowledge bases** — NeuralMind indexes code only, not docs/PDFs/design files
- **Beginners needing code explanations** — Cursor's @codebase is more integrated
- **Solo developers on tight budget** — Free context window is sufficient for most use cases

---

## 🔒 Security & Compliance

**For enterprises and regulated industries:**

- **100% Local Processing** – Your code never leaves your machine. All embeddings generated and stored locally using ChromaDB.
- **No External APIs** – NeuralMind runs completely offline. No cloud services, no telemetry, no data exfiltration.
- **Explainable AI** – Every context decision is auditable. Know exactly which code was retrieved vs. inferred by the model.
- **Open-Source & MIT Licensed** – Full transparency. No hidden clauses, no vendor lock-in. Audit the code yourself.
- **Compliance Mapping** – Full NIST AI RMF audit trail, SOC 2 ready, GDPR/HIPAA-friendly.

**For CTOs & Security Teams:**
- ✅ Zero external dependencies for code storage
- ✅ Runs behind your firewall or on-premise
- ✅ No collection of usage metrics or code patterns
- ✅ Predictable, reproducible results (not a black box)
- ✅ Works with proprietary and sensitive code

[See full security policy](docs/SECURITY-GUIDE.md)

---

## 📊 Realistic Token Reduction Metrics

**Measured data (April 2026):**

| Codebase Size | Tokens (Full) | Tokens (NeuralMind) | Reduction Ratio | Annual Savings @ $3/1M |
|---------------|--------------|-------------------|-----------------|----------------------|
| 5K LOC | 2,000 | 800 | 2.5× | $18/dev |
| 50K LOC | 20,000 | 1,200 | 16.7× | $57/dev |
| 100K LOC | 40,000 | 1,400 | 28.6× | $117/dev |
| 500K LOC | 200,000 | 1,600 | 125× | $597/dev |

**Important:** These assume:
- Repeated code queries (10+ per day)
- Your codebase is actually 50K+ tokens (verify with `neuralmind stats`)
- You're running Claude Sonnet pricing ($3/1M input)
- Larger codebases see exponential benefits (complexity stays fixed at ~1,600 tokens)

**One-shot queries:** Much smaller savings (~2-5×) because setup costs aren't amortized.

---

## 📌 For AI Coding Agents

> **If you are Claude Code, Cline, Continue, Cursor, or any AI agent with NeuralMind installed, start here.**

### Check if NeuralMind is active

```bash
neuralmind stats .
```

Expected output when ready:
```
Project: your-project
Built: True
Nodes: 241
```

If `Built: False`, run `graphify update . && neuralmind build .` first.

---

### Startup workflow

**Every new session:**

```bash
neuralmind wakeup .
```

This returns ~600 tokens of structured project context:
- Project name and description
- Architecture overview: top 10 code clusters
- Community structure and entity types

**Use this before writing any code.** It replaces reading the entire repository.

---

### Decision tree — which tool to call

```
Need project overview?
  └─► neuralmind wakeup .               ~400 tokens

Answering a code question?
  └─► neuralmind query . "question"     ~800-1100 tokens

About to read a source file?
  └─► neuralmind skeleton <file>        ~5-15× cheaper than full Read
      → Use skeleton first
      → Only use full Read when you need implementation details

Searching for a function/class?
  └─► neuralmind search . "term"        ranked by semantic relevance

After code changes?
  └─► neuralmind build .                incremental rebuild
```

---

### Understanding the output

**Reduction ratio = estimated codebase tokens / query tokens**

Example:
```
Tokens: 847 | 59.0× reduction | Layers: L0, L1, L2, L3
```

This means:
- You got 847 tokens of context
- Your full codebase (estimated) = 847 × 59 ≈ 50,000 tokens
- Cost difference: $0.15 (traditional) vs $0.002 (NeuralMind)

**What each layer contains:**

| Layer | Always loaded? | Content |
|-------|---|---------|
| L0 | ✅ | Project identity + graph stats |
| L1 | ✅ | Architecture + top clusters |
| L2 | query only | On-demand semantic search results |
| L3 | query only | Specific code entities |

---

### PostToolUse hooks (Claude Code only)

If `neuralmind install-hooks` has been run, Claude Code automatically compresses tool outputs:

| Tool | What happens | Typical savings |
|------|-------------|----------------|
| **Read** | Raw file → skeleton (functions + call graph) | ~88% |
| **Bash** | Verbose output → errors + summary | ~91% |
| **Grep** | All matches → top 25 + count | varies |

This is fully automatic and requires zero extra work.

---

## 🚀 Quick Start

```bash
# 1. Install
pip install neuralmind

# 2. Prerequisites: Install graphify
git clone https://github.com/safishamshi/graphify.git
cd graphify && pip install -e .

# 3. Go to your project
cd /path/to/your-project

# 4. Build the graph and index
graphify update .
neuralmind build .

# 5. Test it
neuralmind stats .
neuralmind wakeup .
```

[Full Setup Guide](docs/wiki/Setup-Guide.md) — Choose your integration path (Claude Code, MCP, CLI)

---

## 💡 Architecture & Design

**Two-phase optimization:**

1. **Smart Retrieval**: A 4-layer semantic index surfaces ~800 tokens of relevant code instead of loading 50K+ raw source.
2. **Output Compression**: PostToolUse hooks compress Read/Bash/Grep output 88-91% smaller before agents see it.

**Technical stack:**
- **Embeddings**: ChromaDB local (no external API calls)
- **Graph source**: graphify (prerequisite tool)
- **Backends**: ChromaDB (local), PostgreSQL pgvector (enterprise), LanceDB (fast)
- **Learning**: Optional cooccurrence-based reranking (v0.3.2+)

[Architecture Guide](docs/wiki/Architecture.md) — Deep dive into the 4-layer design

---

## 📚 Documentation

**Quick Start:**
- [Setup Guide](docs/wiki/Setup-Guide.md) — Install and first-time setup
- [Usage Guide](docs/wiki/Usage-Guide.md) — All commands explained
- [CLI Reference](docs/wiki/CLI-Reference.md) — Full command list

**Enterprise & Scaling:**
- [Deployment Guide](docs/DEPLOYMENT-GUIDE.md) — Docker, Kubernetes, PostgreSQL
- [Security Guide](docs/SECURITY-GUIDE.md) — RBAC, encryption, compliance mapping
- [Upgrading Guide](docs/UPGRADING.md) — Version upgrades and migrations

**Reference:**
- [Version Strategy](docs/VERSION-STRATEGY.md) — Versioning, support timeline
- [Compatibility Matrix](docs/COMPATIBILITY.md) — Python/platform support
- [FAQ](docs/wiki/FAQ.md) — 30+ common questions answered
- [Troubleshooting](docs/wiki/Troubleshooting.md) — Common issues and fixes

---

## 🤝 Comparisons

**vs Cursor @codebase:**
- NeuralMind: Works with any LLM, local-first, NIST AI RMF
- Cursor: Better IDE integration, Cursor-only

**vs Claude Projects:**
- NeuralMind: Retrieves only relevant code (~800 tokens), learns from queries
- Projects: Loads all files (~50K tokens), no learning

**vs Long Context Windows:**
- NeuralMind: Reduces prompt size 40-70×, cheaper even with bulk pricing
- Long context: Possible but pays for all 100K tokens every query

**vs Prompt Caching:**
- NeuralMind: Makes prompts small (orthogonal to caching)
- Caching: Caches big prompts (complements NeuralMind)

[Full Comparisons](docs/wiki/Comparisons.md) — Detailed matrix

---

## 🔄 Version & Support

| Version | Status | Python | Support Until |
|---------|--------|--------|---|
| **v1.0.0** | (Q1 2027) | 3.10-3.13+ | 2029-01 |
| **v0.5.0** | Q3 2026 | 3.10-3.13 | 2026-10 |
| **v0.4.x** | Current (LTS) | 3.10-3.13 | 2026-10 |
| **v0.3.x** | Maintained | 3.10-3.12 | 2026-04 |

[Version Strategy](docs/VERSION-STRATEGY.md) — Release schedule, breaking changes, upgrade paths

---

## 📄 License & Contributing

MIT Licensed. Open source, fully transparent.

- [Contributing Guide](CONTRIBUTING.md)
- [GitHub Issues](https://github.com/dfrostar/neuralmind/issues) — Bug reports, feature requests
- [GitHub Discussions](https://github.com/dfrostar/neuralmind/discussions) — Questions and ideas

---

## 🙏 Acknowledgments

Built with:
- [ChromaDB](https://www.trychroma.com/) — Vector embedding & search
- [graphify](https://github.com/safishamshi/graphify) — Code graph generation
- [Claude](https://www.anthropic.com/) — AI agent reasoning
- Open-source community contributions

---

**NeuralMind is not affiliated with NeuralMind.ai**
