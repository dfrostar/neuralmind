# 🧠 NeuralMind

[![PyPI version](https://badge.fury.io/py/neuralmind.svg)](https://pypi.org/project/neuralmind/)
[![Downloads](https://static.pepy.tech/badge/neuralmind/month)](https://pepy.tech/project/neuralmind)
[![CI](https://github.com/dfrostar/neuralmind/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/dfrostar/neuralmind/actions/workflows/ci.yml)
[![Self-benchmark](https://github.com/dfrostar/neuralmind/actions/workflows/ci-benchmark.yml/badge.svg?branch=main)](https://github.com/dfrostar/neuralmind/actions/workflows/ci-benchmark.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![tier2 + agent_os: source-available](https://img.shields.io/badge/tier2%20%2B%20agent__os-source--available-blue.svg)](LICENSING.md)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Local-First](https://img.shields.io/badge/Local--First-No%20Telemetry-brightgreen.svg)](#-security--compliance)

**Persistent memory and context compression for AI coding agents.**
Your agent learns your codebase the way a senior engineer would — what goes
together, what you usually touch next — and remembers it across sessions.
100% local, no telemetry. Side effect: **12–50× cheaper code questions**,
measured in CI on every commit.

> After install, your agent:
> - Boots with `SYNAPSE_MEMORY.md` (learned associations, strongest hub files)
> - Receives PostToolUse compression automatically (Bash output → errors + signals)
> - Queries your codebase in ~800 tokens instead of ~50,000
>
> Works out of the box with Claude Code, Codex, Cursor, and Cline.
> Any other MCP agent: `neuralmind install-mcp --all`

**Website:** [neuralmind.uk](https://neuralmind.uk) · **Docs:** [docs.neuralmind.uk](https://docs.neuralmind.uk/wiki/Home) · **Changelog:** [CHANGELOG.md](CHANGELOG.md) · **Release notes:** [docs/releases/](docs/releases/)

![Graph view — force-directed code graph with the Hebbian synapse overlay](docs/images/graph-view.png)

---

## ⚡ 30-second proof — see the memory work

The clearest evidence the memory is working is the measurable side effect:
the agent stops re-loading context it already understood. Reproduce it on a
fresh clone:

```bash
git clone https://github.com/dfrostar/neuralmind && cd neuralmind
bash scripts/demo.sh
```

The script creates an isolated venv, installs the deps, builds the index for
the bundled fixture project, and runs three real questions. Output looks like:

```
  Q: How does authentication work in this codebase?
     naive = 4,736 tok   neuralmind =  829 tok   reduction =   5.7×

  Average reduction:   5.5×  across 3 queries
  Avg context size:    859 tokens  (vs 4,736 naive)
```

The fixture is intentionally tiny (~500 lines) — it runs in CI as a
regression gate. Real repos measure **12–50×** on the same pipeline
([benchmarks](#-benchmarks) · [measured production results](https://neuralmind.uk/effectiveness/)).
Then get your own number:

```bash
pip install neuralmind
cd /path/to/your-repo
neuralmind build .
neuralmind benchmark .
```

---

## 🚀 Quick start

| Method | Command |
|---|---|
| **pip** | `pip install neuralmind` |
| **pipx** | `pipx install neuralmind` (global CLI, no env pollution) |
| **uv** | `uv pip install neuralmind` |
| **Docker** | `docker pull ghcr.io/dfrostar/neuralmind:latest` (multi-arch, published on every release) |
| **Source** | `git clone https://github.com/dfrostar/neuralmind && pip install -e .` |

No external tools required — a built-in **tree-sitter** backend indexes
**Python, TypeScript, Go, Rust, Java, C, C++, C#, Ruby, and PHP** out of the
box, and the default index is ChromaDB-free (smaller deps, 8–16× smaller
index, same answer quality). Full path-by-path walkthrough:
[install paths](docs/use-cases/install-paths.md).

```bash
cd your-project
neuralmind build .          # index the codebase (tree-sitter, ~seconds to minutes)

neuralmind wakeup .         # what the agent sees at session start
neuralmind query . "How does authentication work?"
neuralmind impact MyClass --depth 2   # blast radius: callers, importers, subclasses

neuralmind install-hooks .  # Claude Code: automatic PostToolUse compression
neuralmind serve .          # Obsidian-style graph view in your browser
neuralmind savings . --cost # measured token savings, priced for your model
neuralmind doctor           # verify the install end to end
```

---

## 🧠 What you get

- **Progressive context disclosure (L0–L3).** A question costs ~800 tokens,
  not your whole repo. The agent asks for more depth only where it needs it.
- **A synapse layer that learns.** Hebbian co-activation strengthens edges
  between code that's used together; unused edges decay. Recall is spreading
  activation over that graph — your agent's context gets *better* the more
  you work.
- **Session memory.** `SYNAPSE_MEMORY.md` is exported for Claude Code so
  every session boots already knowing the hub files and learned associations.
- **Tool-output compression + recovery.** PostToolUse hooks compress noisy
  Bash output to errors + signals, and a recovery cache brings back tool
  output the context window dropped.
- **Team memory.** `neuralmind memory publish` commits a learned-weights
  bundle (no source code) that teammates' agents inherit on their next
  session — a fresh clone starts with the team's earned intuition.
- **MCP server for any agent.** Claude Code, Codex, Cursor, Cline, Continue,
  or anything MCP-compatible: `neuralmind install-mcp --all`.
- **Graph view.** `neuralmind serve` renders the index as a force-directed,
  community-coloured graph with the synapse overlay — backlinks, semantic
  quick-switcher, clickable neighbours. There's also a
  [VS Code extension](editors/vscode/).
- **Team tier ($29/user/mo).** Governance, append-only hash-chained audit
  log, seat management, self-hosted deployment. MIT core stays MIT — the
  Team tier only activates with a license; tier2 and Agent OS are
  source-available, not MIT — see [LICENSING.md](LICENSING.md). See [pricing](https://neuralmind.uk/pricing/).

How it works under the hood: [Architecture](docs/wiki/Architecture.md) ·
[brain-like learning](docs/brain_like_learning.md).

---

## 📊 Benchmarks

Measured, not marketed — the numbers are produced by CI on every commit
(every merged PR carries a sticky benchmark comment) and reproduce locally
with `python -m tests.benchmark.run`:

- **100% gold-file recall at 38–85× fewer tokens** on the public benchmark.
- **Synapse recall A/B:** +11 points top-k hit rate at ±0 token cost.
- **Real production rebuild:** 48.8× average reduction, 1,033 tokens/query
  ([full field report](https://neuralmind.uk/effectiveness/)).
- Backend parity gate: the built-in tree-sitter backend is held within
  tolerance of the legacy graphify backend on every PR.

![Benchmark chart](docs/images/benchmark_chart.png)

Methodology, gold sets, and community submissions:
[benchmarks/](benchmarks/) · [public methodology](docs/prd/public-benchmark.md) ·
[honest assessment (when NOT to use this)](docs/HONEST-ASSESSMENT.md).

---

## 🔒 Security & Compliance

- **100% local engine.** NeuralMind makes zero network calls of its own and
  ships no telemetry. Only the minimal relevant slice of code ever reaches
  your AI tool.
- **CycloneDX SBOM per release**, hash-chained audit log (Team tier), signed
  licenses (Ed25519), tarball integrity instructions on every release.
- Live posture page: [neuralmind.uk/security](https://neuralmind.uk/security/) ·
  Policy: [SECURITY.md](SECURITY.md) ·
  [Compliance summary](docs/COMPLIANCE-SUMMARY.md) ·
  [SDLC policy](docs/compliance/SDLC_POLICY.md)

Behavior toggles: `NEURALMIND_BYPASS=1` (skip compression),
`NEURALMIND_SYNAPSE_INJECT=0` (skip prompt-time recall),
`NEURALMIND_SYNAPSE_EXPORT=0` (skip memory export),
`NEURALMIND_TEAM_MEMORY=0` (skip team-bundle import). All fail-open.

---

## 📚 Documentation

| I want to… | Read |
|---|---|
| Install and set up | [Setup guide](docs/wiki/Setup-Guide.md) · [Installation](docs/wiki/Installation.md) |
| See every command | [CLI reference](docs/wiki/CLI-Reference.md) |
| Wire up my agent (MCP) | [Usage](USAGE.md) · [wiki Home](https://docs.neuralmind.uk/wiki/Home) |
| Understand the design | [Architecture](docs/wiki/Architecture.md) · [Limits & failure modes](docs/wiki/Limits-and-Failure-Modes.md) |
| Follow real workflows | [Use-case walkthroughs](docs/use-cases/) (20+) |
| Compare with alternatives | [Comparisons](docs/comparisons/) |
|| Evaluate for a team | [Business case](docs/BUSINESS-CASE.md) · [Enterprise](docs/ENTERPRISE.md) · [Team tier operator guide](docs/wiki/Tier2-Operator-Guide.md) |
|| Run on multiple codebases | [Multi-project scoping](docs/wiki/Multi-Project-Scoping.md) |
|| Upgrade safely | [Upgrade guide](docs/wiki/Upgrade-Guide.md) · [UPGRADING](docs/UPGRADING.md) |
| See what changed | [CHANGELOG](CHANGELOG.md) · [release notes](docs/releases/) · [ROADMAP](ROADMAP.md) |

---

## ❓ FAQ

**How is this different from RAG?** RAG retrieves similar text. NeuralMind
maintains a weighted graph of your code and *learns from use* — retrieval is
spreading activation over structural edges plus Hebbian synapses, disclosed
progressively so the agent pays only for the depth it needs.

**Does my code leave my machine?** No. The engine is fully local. Your agent
still talks to its own model — NeuralMind just makes what it sends smaller.

**What if it doesn't help on my repo?** Run `neuralmind benchmark .` and
read the number. If it's not worth it, uninstall — and see the
[honest assessment](docs/HONEST-ASSESSMENT.md) for when that's the right call.

**Is the paid tier required?** No. The core is MIT and complete. The Team
tier adds governance, audit, and seat management for organizations.

---

## 🤝 Contributing

Contributions welcome — see [CONTRIBUTING.md](CONTRIBUTING.md),
[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md), and [SUPPORT.md](SUPPORT.md).
Tests live in `tests/`; `pytest tests/` must pass (the synapse layer's tests
are stdlib-only). Security reports: see [SECURITY.md](SECURITY.md).

## 📄 License

MIT for the core — see [LICENSE](LICENSE). The optional Team tier is
licensed separately — see [LICENSE-COMMERCIAL.md](LICENSE-COMMERCIAL.md).
