# 🧠 NeuralMind Wiki

**Reduce Claude, GPT, and Gemini token costs 40–70× on code questions.** Local semantic codebase index + MCP server + PostToolUse compression hooks for Claude Code, Cursor, Cline, Continue, and any LLM.

Welcome — this wiki is the in-depth reference. For the fastest orientation, use the two pages at the top of Quick Links.

## What's New

**v0.4.0 — Brain-like synapse layer.** NeuralMind now runs as a second
brain alongside the LLM: a persistent SQLite-backed weighted graph that
learns associations between code nodes from co-activation, decays unused
edges, and answers via spreading activation. Includes the `neuralmind watch`
daemon, three new Claude Code lifecycle hooks (SessionStart, UserPromptSubmit,
PreCompact), and a memory exporter that surfaces learned associations to
Claude Code's auto-memory system. See the [release notes](../blob/main/RELEASE_NOTES_v0.4.0.md)
or the [Architecture](Architecture#synapse-layer-v04) and [Learning Guide](Learning-Guide#v04-synapse-layer)
sections.

## Quick Links

### Start here

| Page | When to read it |
|------|-----------------|
| **[Setup Guide](Setup-Guide)** | First-time setup for Claude Code, Cursor, Claude Desktop, or any MCP client |
| **[Use Cases](Use-Cases)** | Step-by-step walkthroughs by persona: Claude Code user, cost optimization, any-LLM, offline/regulated, growing monorepo |
| **[Comparisons](Comparisons)** | Honest "NeuralMind vs X" pages: Cursor, Copilot, Cody, Aider, Claude Projects, LangChain, long context, prompt caching, RAG, tree-sitter |
| **[Version Strategy](../docs/VERSION-STRATEGY.md)** | Versioning policy, breaking changes, release schedule, deprecation timeline |
| **[Compatibility Matrix](../docs/COMPATIBILITY.md)** | Version compatibility, Python support, known issues, upgrade paths |
| **[Benchmarks](../blob/main/README.md#-benchmarks)** | CI-measured reduction ratios, per-model breakdown, community submissions, and how to run it on your own code |

### Enterprise & Deployment

| Page | For... |
|------|--------|
| **[Deployment Guide](../docs/DEPLOYMENT-GUIDE.md)** | DevOps/Infrastructure: Architecture patterns, Docker, Kubernetes, PostgreSQL backend, scaling, monitoring |
| **[Security Guide](../docs/SECURITY-GUIDE.md)** | Security teams: RBAC, encryption, secrets management, NIST AI RMF, SOC 2, threat models |
| **[Upgrading Guide](../docs/UPGRADING.md)** | Everyone: How to upgrade between versions, breaking changes, rollback procedures |

### Reference

| Page | Contents |
|------|----------|
| [Installation](Installation) | Install from PyPI; the default install includes the MCP server |
| [Usage Guide](Usage-Guide) | End-to-end examples for every command |
| [CLI Reference](CLI-Reference) | All CLI commands, flags, and output shapes |
| [API Reference](API-Reference) | Python API (`NeuralMind`, `ContextResult`, `TokenBudget`) |
| [Architecture](Architecture) | How the 4-layer progressive disclosure system works |
| [Integration Guide](Integration-Guide) | MCP, CI/CD, VS Code, JetBrains, any-LLM piping |
| [Scheduling Guide](Scheduling-Guide) | Automate audits with Windows Task Scheduler, GitHub Actions, or cron |
| [Learning Guide](Learning-Guide) | Opt-in memory + cooccurrence reranking (v0.3.2) and brain-like synapses (v0.4.0) |
| [Brain-Like Learning](../blob/main/docs/brain_like_learning.md) | Design rationale for the v0.3.x learning system |
| [v0.4.0 Release Notes](../blob/main/RELEASE_NOTES_v0.4.0.md) | Brain-like synapse layer: continuous co-activation, spreading activation, lifecycle hooks |
| [Troubleshooting](Troubleshooting) | Common issues and fixes |
| [FAQ](FAQ) | 30+ frequently asked questions answered |

## What is NeuralMind?

A two-phase token optimizer for AI coding agents.

- **Phase 1 — Retrieval.** A 4-layer progressive-disclosure index surfaces ~800 tokens of structured context for any code question, instead of loading 50,000+ tokens of raw source.
- **Phase 2 — Consumption.** PostToolUse hooks (Claude Code) compress `Read`, `Bash`, and `Grep` output **before the agent sees it** — typically 88–91% smaller.

Combined effect: **5–10× total reduction** vs baseline agent usage, offline and model-agnostic.

### The core problem

```
You: "How does authentication work in my codebase?"

❌ Traditional: Load entire codebase → 50,000 tokens → $0.15-$3.75/query
✅ NeuralMind: Smart context → ~800 tokens → $0.002-$0.06/query
```

### When do I reach for it?

Short answer: if any of these describe you, start with the [Use Cases](Use-Cases) page.

- My Claude Code session hits context limits mid-task
- My monthly LLM bill is climbing
- I start every session re-pasting project structure
- The agent reads a 2,000-line file to answer one question
- I want to query my codebase from ChatGPT / Gemini / a local model
- I need AI coding help but code can't leave my machine

Full symptom-and-goal matrix in the main [README](../blob/main/README.md#-when-do-i-reach-for-neuralmind).

## Quick Start

```bash
# Install
pip install neuralmind graphifyy

# Setup
cd your-project
graphify update .
neuralmind build .

# Use
neuralmind wakeup .
neuralmind query . "How does authentication work?"
neuralmind skeleton src/auth/handlers.py
```

Claude Code users, install the lifecycle hooks (PostToolUse compression
plus the v0.4.0 brain-like synapse hooks: SessionStart, UserPromptSubmit,
PreCompact):

```bash
neuralmind install-hooks .
neuralmind init-hook .        # auto-rebuild on every git commit (optional)
neuralmind watch &            # always-on synapse learning from file edits (optional)
```

## Compare to alternatives

| Compared against | Short verdict |
|---|---|
| [Cursor `@codebase`](Comparisons#cursor-codebase) | Works only in Cursor; NeuralMind works anywhere |
| [GitHub Copilot](Comparisons#github-copilot) | Copilot is hosted completions; NeuralMind is local context |
| [Claude Projects](Comparisons#claude-projects) | Projects reload all files every turn; NeuralMind retrieves only what the query needs |
| [Long context windows](Comparisons#long-context) | Possible ≠ cheap — NeuralMind drops per-query cost ~60× |
| [Prompt caching](Comparisons#prompt-caching) | Caching amortizes big prompts; NeuralMind makes them small |

Full list: [Comparisons](Comparisons).

## Prove it on your code

Don't trust fixture numbers — measure it on your own repo:

```bash
pip install neuralmind graphifyy
graphify update . && neuralmind build .
neuralmind benchmark . --contribute
```

This outputs your reduction ratio, tokens per query, and an estimated monthly savings figure at Claude 3.5 Sonnet pricing. The `--contribute` flag produces a ready-to-share JSON blob you can paste into a PR (or a [benchmark submission issue](https://github.com/dfrostar/neuralmind/issues/new?template=community-benchmark.yml)) to add to the public leaderboard.

Full walkthrough: [Does NeuralMind work on *your* codebase?](../blob/main/docs/use-cases/benchmark-your-repo.md)

## Support

- [GitHub Issues](https://github.com/dfrostar/neuralmind/issues) — bug reports, feature requests
- [GitHub Discussions](https://github.com/dfrostar/neuralmind/discussions) — questions and ideas
- [Main README](../blob/main/README.md) — always the most current overview
