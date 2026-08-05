# 🧠 NeuralMind Wiki

**Reduce Claude, GPT, and Gemini token costs 12–50× on code questions.** Local semantic codebase index + MCP server + PostToolUse compression hooks for Claude Code, Cursor, Cline, Continue, and any LLM.

Welcome — this wiki is the in-depth reference. For the fastest orientation, use the two pages at the top of Quick Links.

## Why NeuralMind — four data-backed benefits

NeuralMind is more than token reduction. Every claim below ships with a
committed eval. The first two run on **real, pinned OSS repos** (`requests`,
`click`) and are fully reproducible — `python -m evals.public.run`. The last
two are measured A/Bs on the bundled **reference fixture**, so they're real but
smaller-scope.

| | Benefit | Measured result | Where it's measured |
|---|---|---|---|
| 💸 | **Cheaper context** | **100% gold-file recall at 38–85× fewer tokens** than pasting files — and beats `ripgrep` on *both* recall and cost | Public benchmark, **real OSS repos** (`requests`, `click`) |
| 🎯 | **Finds the *right* code, not just less of it** | **100% gold-file recall, MRR 0.96** — ranks the correct file at the top; beats the incumbent `codebase-memory-mcp` on retrieval ranking (0.96 vs 0.23) | Same public benchmark, **real repos** |
| 🧠 | **Learns how you work** | A Hebbian *synapse* layer that learns co-edited files lifts top-k retrieval hit-rate **+11.7 points (71.7%→83.3%)**, **budget-neutral** (no extra tokens) | Synapse A/B eval (**reference fixture** — smaller scope) |
| 🔬 | **Better-grounded answers** | At a *matched* token budget, its context carries more of the gold facts than naive truncation: **faithfulness +0.143, grounding 1.00** | Faithfulness/parity gate (**reference fixture** — smaller scope) |

*Honest scope:* the **cost** and **accuracy** rows run on real, pinned OSS repos
(fully reproducible — see [methodology](https://github.com/dfrostar/neuralmind/blob/main/docs/benchmarks/public.md)); the **learning** and **grounding** rows are
committed A/Bs on the bundled reference fixture, so they're real but
smaller-scope. We report where NeuralMind *doesn't* win too — a well-tuned
vector RAG ties it on pure findability and is cheaper on raw tokens; that's in
the benchmark table. The competitor comparison is *pure retrieval ranking*, not
their LLM-agent loop. Full numbers and reproduction commands on the
**[Benchmarks](Benchmarks)** page.

## What's New

### v3.0.2 — Post-Extraction Cleanup (August 2026)

The self-improving loop (signal→insight→experiment→promote) was extracted to a private repo (`dfrostar/agencyOS`). NeuralMind is now pure code intelligence — the public package ships only what your agent needs.

- **Agent OS extracted.** 12 modules moved to `dfrostar/agencyOS`. The public repo is leaner.
- **Dashboard rebranded.** Agent/Agency OS references removed from ROADMAP and tests.
- **v3.0.0, v3.0.1** — SBOM publishing, license cleanup, extraction follow-through.

### v2.0.0 — Compliance Engine + `neuralmind init` (August 2026)

> **12–50× typical savings** — updated from the 12-50× estimate with founder-benchmarked results on local production repos. The original number was real vs a naive "dump all files" baseline (~30K tokens); 12–50× is the realistic range against a 10K-token human baseline. Up to 50×+ for targeted queries.

New compliance capabilities for regulated teams, plus a one-command project init.

| Feature | What |
|---------|------|
| `neuralmind init` | One-command project setup — auto-detects structure, installs hooks, builds index, all at once |
| Compliance annotation detection | Scans code for `# Compliance:` / `// Compliance:` annotations — flags each against CMMC 2.0 / NIST SP 800-53 controls |
| CMMC content ingestion | `neuralmind ingest-cmmc` imports CMMC 2.0 assessment guides + POA&M templates into the doc index |
| Audit export | `neuralmind export --audit` produces flat compliance reports (CSV/JSON) for evidence submission |
| CI/CD compliance check | `neuralmind ci-check` gates builds on compliance annotation health |
| MCP tool | `neuralmind_compliance_report` — live compliance stance via any MCP-compatible agent |
| Savings recalibration | 12–50× typical (44× avg vs 30K naive baseline; 12–25× vs realistic 10K human baseline) |

**Claim tiering:**
- 44× avg vs 30K naive baseline — **Tier C** (self-measured, reproducible via `neuralmind benchmark .`)
- 12–25× vs realistic 10K human baseline — **Tier C** (self-measured, same pipeline)
- "Up to 50×+" for targeted queries — **Tier D** (hypothesized, depends on query shape)

### v1.7.1 — Schema hotfix + autopilot integration (July 2026)

Synapse schema fix adds `half_life_days` + `learned_at` columns before `CREATE TABLE` to fix `sqlite3.OperationalError` on existing databases. Autopilot v0.10.1 ships with self-improving loop (15-min systemd tick). Path migration from `/home/dtfrost/` to `/home/dtfrost5/`.

### v1.7.0 — Free tier auto-provision + upgrade funnel (July 2026)

Free tier now auto-provisions on first `wakeup`. `pip install neuralmind && neuralmind wakeup .` writes the license on first run — zero signup wall, zero "team" default breaking free onboarding.

- **Free tier auto-provision:** `cmd_wakeup` checks for `~/.config/neuralmind/license.json`; if missing, calls `issue_free_license()` and prints activation message
- **Default tier changed:** `Tier2Config.tier` default flipped from `"team"` to `"free"` — fresh `tier2.yaml` no longer triggers downgrade guard
- **Upgrade CTA:** Counter fires one-liner Team CTA at call 10 (NeuralMind Team: $29/user/mo — shared memory, governance, seat management)
- **Tests:** 21/21 tier2 tests pass, 191/191 total across tier2 + config + license-validator suites

Acceptance: free license created on first `wakeup`, idempotent on repeat calls, CTA fires exactly once at call 10.

### v1.4.0 — Louvain modularity clustering

`build_graph` now assigns communities via Louvain modularity over structural code-dependency edges. Previous versions assigned one community per file — every file in `src/auth/` was its own community even if it imported heavily from `src/users/`. v1.4.0 groups them: files with many inter-edges collapse into one community, isolated files (docs, configs) stay separate.

Stdlib-only pure-Python Louvain, O(n·k), deterministic output. 

Acceptance: 1582+ tests pass, `bench/` repos verify expected community counts.

### v1.0.0 — Team tier ships

NeuralMind Team is the paid tier for engineering teams of 5-50 seats: $29/user/mo, annual contract. Adds team memory governance, immutable audit log (SHA-256 hash-chained append-only), self-hosted deployment (docker-compose, one-command install), and seat management on top of the MIT core. Ed25519-signed license validation with 30-day offline grace. Acceptance: 46 unit + integration tests.

Full details: [RELEASE_NOTES_v1.0.0.md](https://github.com/dfrostar/neuralmind/blob/main/docs/releases/RELEASE_NOTES_v1.0.0.md)

### v0.52.0 — Impact: blast radius under a name you'd actually reach for

A Reddit comparison against GitNexus flagged "no `impact` tool" as a gap. Not quite right — `neuralmind structural --blast-radius` has answered "what depends on this?" since v0.42.0 — but the naming critique landed. v0.52.0 gives the same capability a name an agent (or a human) would actually reach for, plus richer output. Each dependent row now carries its **hop** and its **relation** (`calls`/`inherits`/`imports_from`/`implements`). The MCP tool is `neuralmind_impact()`. `structural --blast-radius` stays byte-identical — now a one-line wrapper over the same `blast_radius_detail()`. Honest scope: naming + discoverability, no new capability.

Full details: [v0.52.0 release notes](RELEASE_NOTES_v0.52.0.md) · [docs/use-cases/blast-radius-before-a-rename.md](https://github.com/dfrostar/neuralmind/blob/main/docs/use-cases/blast-radius-before-a-rename.md)

### v0.51.3 — Shipped

CI green, GitHub Release published, GHCR published, PyPI verified at 0.51.3.

Full details: [v0.51.3 release notes](RELEASE_NOTES_v0.51.3.md)

### v0.50.0 — Metrics Dashboard + Team Memory Integration

`neuralmind metrics --summary`, `--days`, `--json`, plus `/api/metrics` HTTP endpoint. Full team memory integration test (E1→E2→E3→E4 chain). Autopilot engine orchestrator + bug fixes (signals Page-Hinkley, self_play IDs, experiment_runner docstring).

Full details: [v0.50.0 release notes](RELEASE_NOTES_v0.50.0.md)

### v0.49.5 — DeepSeek Patches

Applied DeepSeek QA patches: prune dangling edges, remove dead code, fix axis independence in tuner faithfulness.

### v0.49.4 — DeepSeek QA

DeepSeek code review of incremental wiring, tuner, and autopilot modules. One CRITICAL finding (concurrent build locking — needs `fcntl.flock()`), two WARNING findings patched.

### v0.49.3 — Incremental Extraction Wiring

Wired `IncrementalExtractor` into `build_graph()` — scope re-extraction to changed files + importers. Acceptance: 10K-line repo, 1 file changed → <10% of full-build wall-clock.

### v0.49.2 — DeepSeek Wave 5 QA

DeepSeek review of tuner v0.49.0 and graphgen incremental wiring. CRITICAL: NaN/Inf guard, `_clamp()` does NOT defend against NaN. WARNING: inverted time filter in `_get_param_changes`. Patched.

### v0.49.0 — Tuner Faithfulness Gap

Live A/B eval: configure the embedder per candidate, run ~20 fixture queries, measure real retrieval_quality (nDCG@5) and session_health (re-query-rate).

### v0.48.0 — v2.0 Complete

All four waves of the v2.0 future-proofing plan complete (26 workstreams, 7 buckets).

### v0.47.0 — Impact Tool (original)

Original impact tool release. Superseded by v0.52.0.

### v0.21.0 — ChromaDB-free retrieval

The opt-in `turbovec` backend can now **embed *and* search with zero ChromaDB**: Google Research's **TurboQuant** compressed index (8–16× smaller vectors) plus a bundled `OnnxMiniLMEmbedder` that produces vectors **byte-identical** to ChromaDB's (`all-MiniLM-L6-v2`; verified cosine 1.0). Retrieval stays at/above parity (fact recall 0.744 → 0.800). Enable with `backend: turbovec` in `neuralmind-backend.yaml` — see the [ChromaDB-free local](https://github.com/dfrostar/neuralmind/blob/main/docs/use-cases/chromadb-free-local.md) walkthrough. This retires the dependency behind the recurring **CVE-2026-45829** advisory; flipping the default is the staged next step. Full details: [v0.21.0 release notes](https://github.com/dfrostar/neuralmind/blob/main/docs/releases/RELEASE_NOTES_v0.21.0.md).

### v0.20.0 — Measure the onboarding lift

`neuralmind eval --onboarding` turns NeuralMind's differentiator into a number: does an agent that inherits a **committed team memory** retrieve better on its *first* queries than a cold agent? The headline is the **top-k module hit-rate lift** (a measured **+6.5 points** on the reference fixture), with fact-recall + grounding as honest secondaries; budget-neutral, gated in CI at lift ≥ 0. Full details: [v0.20.0 release notes](https://github.com/dfrostar/neuralmind/blob/main/docs/releases/RELEASE_NOTES_v0.20.0.md).

> 📊 New: a single **[Benchmarks & Results](Benchmarks)** page collects every measured, CI-gated number (token reduction, faithfulness delta, synapse +12 pts, onboarding +11.6 pts, ChromaDB-free parity) with reproduction commands.

### v0.14.0 — Measure faithfulness

`neuralmind eval` turns "does the memory make answers *better*, not just shorter?" into a number: it scores whether NeuralMind's selected context contains more of the facts a correct answer needs than a matched-budget naive baseline (a **faithfulness delta**), plus grounding and contradiction checks. 100% local by default (`--json` and `--selfcheck` too); the LLM-as-judge is opt-in. It's a contributor/CI quality gate — run it from a **source checkout** (the `evals/` gold set isn't bundled in the pip wheel; from an installed wheel the command points you at the repo). The first release where you can measure *answer quality*, not just token reduction. Full details: [v0.14.0 release notes](https://github.com/dfrostar/neuralmind/blob/main/docs/releases/RELEASE_NOTES_v0.14.0.md).

### v0.13.0 — Measurement foundation

The scaffolding to *prove* the memory helps, not just claim it: a 100%-local **faithfulness eval** (a versioned query + gold-fact dataset and an offline expected-fact-recall scorer), **polyglot retrieval fixtures (TypeScript + Go)** so quality is measured beyond Python, and a written documentation process. No runtime change to your install — this is the fitness function the eval-first roadmap (v0.13→v0.16) builds on. The full `neuralmind eval` report is the next increment. Full details: [v0.13.0 release notes](https://github.com/dfrostar/neuralmind/blob/main/docs/releases/RELEASE_NOTES_v0.13.0.md).

### v0.12.0 — Install Doctor

`neuralmind doctor` inspects an install (code graph, semantic index, synapse memory, MCP server, Claude Code hooks, query memory) and reports each piece with a status and the exact fix; `--json` for agents, non-zero exit to gate CI. Full details: [v0.12.0 release notes](https://github.com/dfrostar/neuralmind/blob/main/docs/releases/RELEASE_NOTES_v0.12.0.md).

### v0.11.0 — Directional Synapses

The synapse layer now learns *what comes next*, not just *what goes together*: a `synapse_transitions` table, a `next_likely()` API, the `neuralmind next` CLI, and the `neuralmind_next_likely` MCP tool. Full details: [v0.11.0 release notes](https://github.com/dfrostar/neuralmind/blob/main/docs/releases/RELEASE_NOTES_v0.11.0.md).

### v0.10.0 — Agent Ergonomics

A content-aware PostToolUse compression footer (categorized line counts + repeated-line detection) and `neuralmind last` to recover dropped middle output without re-running the command. Full details: [v0.10.0 release notes](https://github.com/dfrostar/neuralmind/blob/main/docs/releases/RELEASE_NOTES_v0.10.0.md).

### v0.9.0 — Enterprise-Ready

Phase 3 of the release arc. Every tagged release now auto-publishes a multi-platform container image to GHCR (`ghcr.io/dfrostar/neuralmind:vX.Y.Z` and `:latest`, `linux/amd64` + `linux/arm64`) and attaches a CycloneDX JSON SBOM to the GitHub Release. New [`docs/use-cases/air-gapped.md`](https://github.com/dfrostar/neuralmind/blob/main/docs/use-cases/air-gapped.md) walkthrough covers the strictest deployment posture — no outbound network at install, build, runtime, or query. New [`docs/COMPLIANCE-SUMMARY.md`](https://github.com/dfrostar/neuralmind/blob/main/docs/COMPLIANCE-SUMMARY.md) consolidates NIST AI RMF + SOC 2 + GDPR claims previously scattered across `SECURITY-GUIDE.md` and the now-extracted enterprise docs, with a "how to verify yourself" command for every claim.

No production code changes — pure CI + docs. Full details: [v0.9.0 release notes](https://github.com/dfrostar/neuralmind/blob/main/docs/releases/RELEASE_NOTES_v0.9.0.md).

### v0.8.0 — Always-On

`neuralmind watch` and `neuralmind serve` are first-class production processes now. Committed [systemd](https://github.com/dfrostar/neuralmind/blob/main/scripts/systemd/) and [launchd](https://github.com/dfrostar/neuralmind/blob/main/scripts/launchd/) templates, plus a Windows Task Scheduler walkthrough in the [Scheduling Guide](Scheduling-Guide#always-on-neuralmind-watch--neuralmind-serve-v08), keep both running across reboots and crashes. `neuralmind serve` exposes a `/healthz` endpoint (unauthenticated, returns `{"status":"ok","version":"…"}`) for Docker `HEALTHCHECK` and systemd `ExecStartPost` probes. Cross-platform walkthrough at [`docs/use-cases/always-on.md`](https://github.com/dfrostar/neuralmind/blob/main/docs/use-cases/always-on.md).

Distribution (v0.7.0) made NeuralMind reachable. Always-on (v0.8.0) makes it persistent — the synapse store accumulates 24/7 whether you're at the keyboard or not. Full details: [v0.8.0 release notes](https://github.com/dfrostar/neuralmind/blob/main/docs/releases/RELEASE_NOTES_v0.8.0.md).

### v0.7.0 — Install anywhere

NeuralMind now installs five ways: `pip`, `pipx`, `uv`, Docker, and source. Same package, same CLI, same MCP server, same graph view — every path. The Quick Start matrix lives at the top of the [Installation](Installation) page and the [README](https://github.com/dfrostar/neuralmind/blob/main/README.md#install--pick-your-path); the repo's root [`Dockerfile`](https://github.com/dfrostar/neuralmind/blob/main/Dockerfile) is multi-stage, non-root, and pre-wheels every transitive dep so the runtime image doesn't need a C toolchain. PyPI keywords got a long-overdue refresh too, so search ranking for `graph-view`, `hebbian-learning`, and friends finally matches the v0.6.0 product copy.

Also in v0.7.0: a P2 fix in the JSONL bridge (rotation race that could drop events under logrotate/copytruncate) and a test-coverage gap on `/api/queries`. Full details: [v0.7.0 release notes](https://github.com/dfrostar/neuralmind/blob/main/docs/releases/RELEASE_NOTES_v0.7.0.md) · [Install paths walkthrough](https://github.com/dfrostar/neuralmind/blob/main/docs/use-cases/install-paths.md).

### v0.6.0 — Graph view + live activity feed

`neuralmind serve` now streams synapse + file events to the canvas in
real time over SSE. Affected nodes pulse as the brain works; a
sidebar log keeps the most recent ~80 events. A cross-process JSONL
bridge means a separate `neuralmind watch` daemon, a Claude Code
session, or any other process feeds the same live feed via
`<project>/.neuralmind/events.jsonl`. Pin UX (visible glyph,
Pin/Unpin button, Unpin-all), Cmd/Ctrl-K quick-switch, a 1–3-hop
depth slider, replay-last-query overlay, edge tooltips, and a
min-weight synapse slider round out the release.

The pitch flipped: v0.5.4 made the brain inspectable; v0.6.0 makes
it legible. You can sit there and **watch the hippocampus learn
your codebase, live**.

Multi-tool unlock: every agent (Claude Code, Cursor, OpenClaw,
Hermes-Agent) talking to the same project reinforces the same
synapse store, and the v0.6.0 canvas now shows the **union** of
their activity. See [docs/use-cases/multi-agent.md](https://github.com/dfrostar/neuralmind/blob/main/docs/use-cases/multi-agent.md).

Full details: [v0.6.0 release notes](https://github.com/dfrostar/neuralmind/blob/main/docs/releases/RELEASE_NOTES_v0.6.0.md) ·
[Architecture: event bus + JSONL bridge](Architecture#event-bus-and-jsonl-bridge-v06) ·
[CLI Reference: `neuralmind serve`](CLI-Reference#serve)

### v0.5.4 — Graph view foundation

The Obsidian-style force-directed graph that v0.6.0 made live first
shipped in v0.5.4. Code nodes coloured by community; structural edges
and Hebbian synapses drawn together; backlinks, synaptic neighbours,
semantic quick-switch, and one-click open-in-editor. Per-session
access token bound to 127.0.0.1 by default. Builds on v0.5.0's
bundled MCP server.

### v0.4.0 — Brain-like synapse layer

NeuralMind runs as a second brain alongside the LLM: a persistent
SQLite-backed weighted graph that learns associations between code
nodes from co-activation, decays unused edges, and answers via
spreading activation. Includes the `neuralmind watch` daemon, three
Claude Code lifecycle hooks (SessionStart, UserPromptSubmit,
PreCompact), and a memory exporter that surfaces learned
associations to Claude Code's auto-memory system. See the
[release notes](https://github.com/dfrostar/neuralmind/blob/main/docs/releases/RELEASE_NOTES_v0.4.0.md) or the
[Architecture](Architecture#synapse-layer-v04) and [Learning Guide](Learning-Guide#v04-synapse-layer)
sections.

## Quick Links

### Start here

| Page | When to read it |
|------|-----------------|
| **[Setup Guide](Setup-Guide)** | First-time setup for Claude Code, Cursor, Claude Desktop, or any MCP client |
| **[Use Cases](Use-Cases)** | Step-by-step walkthroughs by persona: Claude Code user, cost optimization, any-LLM, offline/regulated, growing monorepo |
| **[Comparisons](Comparisons)** | Honest "NeuralMind vs X" pages: Cursor, Copilot, Cody, Aider, Claude Projects, LangChain, long context, prompt caching, RAG, tree-sitter |
|| **[Tier2-Operator-Guide](Tier2-Operator-Guide.md)** | Team tier commands, honest scope, troubleshooting |
|| **[Multi-Project-Scoping](Multi-Project-Scoping.md)** | Working across multiple codebases — isolation rules for NeuralMind, memU, and agent memory |
|| **[Upgrade-Guide](Upgrade-Guide.md)** | Free → Team flow, downgrade, troubleshooting |
| **[Compatibility Matrix](../COMPATIBILITY.md)** | Version compatibility, Python support, known issues, upgrade paths |
| **[Benchmarks & Results](Benchmarks)** | Every measured, CI-gated number — token reduction, faithfulness delta, synapse +12 pts, onboarding +11.6 pts, ChromaDB-free parity — with reproduction commands |

### Enterprise & Deployment

| Page | For... |
|------|--------|
| **[Deployment Guide](../DEPLOYMENT-GUIDE.md)** | DevOps/Infrastructure: Architecture patterns, Docker, Kubernetes, PostgreSQL backend, scaling, monitoring |
| **[Security Guide](../SECURITY-GUIDE.md)** | Security teams: RBAC, encryption, secrets management, NIST AI RMF, SOC 2, threat models |
| **[Upgrading Guide](../UPGRADING.md)** | Everyone: How to upgrade between versions, breaking changes, rollback procedures |

### Reference

| Page | Contents |
|------|----------|
| [Installation](Installation) | `pip` / `pipx` / `uv` / Docker / source — pick your path (v0.7.0) |
| [Usage Guide](Usage-Guide) | End-to-end examples for every command |
| [CLI Reference](CLI-Reference) | All CLI commands, flags, and output shapes |
| [API Reference](API-Reference) | Python API (`NeuralMind`, `ContextResult`, `TokenBudget`) |
| [Architecture](Architecture) | How the 4-layer progressive disclosure system works — incl. the embedding-model spec + index inspection/debugging reference |
| [Limits & Failure Modes](Limits-and-Failure-Modes) | Where it stops working: when one query isn't enough, the repo-size envelope, and the per-language support matrix |
| [Integration Guide](Integration-Guide) | MCP, CI/CD, VS Code, JetBrains, any-LLM piping |
| [Scheduling Guide](Scheduling-Guide) | Automate audits with Windows Task Scheduler, GitHub Actions, or cron |
| [Learning Guide](Learning-Guide) | Opt-in memory + the brain-like synapse layer that learns associations from how you use the codebase (Hebbian co-activation with decay), the single learning system since v0.25.0 |
| [Brain-Like Learning](https://github.com/dfrostar/neuralmind/blob/main/docs/brain_like_learning.md) | Design rationale for the v0.3.x learning system |
| [v0.4.0 Release Notes](https://github.com/dfrostar/neuralmind/blob/main/docs/releases/RELEASE_NOTES_v0.4.0.md) | Brain-like synapse layer: continuous co-activation, spreading activation, lifecycle hooks |
| [Troubleshooting](Troubleshooting) | Common issues and fixes |
| [FAQ](FAQ) | 30+ frequently asked questions answered |

## What is NeuralMind?

A two-phase token optimizer for AI coding agents.

- **Phase 1 — Retrieval.** A 4-layer progressive-disclosure index surfaces ~800 tokens of structured context for any code question, instead of loading 50,000+ tokens of raw source.
- **Phase 2 — Consumption.** PostToolUse hooks (Claude Code) compress `Read`, `Bash`, and `Grep` output **before the agent sees it** — typically 88–91% smaller.

Combined effect: **12–50× retrieval token reduction** (6.2× measured in CI on the fixture), offline and model-agnostic.

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

Full symptom-and-goal matrix in the main [README](https://github.com/dfrostar/neuralmind/blob/main/README.md#-when-do-i-reach-for-neuralmind).

## Quick Start

```bash
# Install
pip install neuralmind

# Setup
cd your-project
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
pip install neuralmind
neuralmind build .
neuralmind benchmark . --contribute
```

This outputs your reduction ratio, tokens per query, and an estimated monthly savings figure at Claude 3.5 Sonnet pricing. The `--contribute` flag produces a ready-to-share JSON blob you can paste into a PR (or a [benchmark submission issue](https://github.com/dfrostar/neuralmind/issues/new?template=community-benchmark.yml)) to add to the public leaderboard.

Full walkthrough: [Does NeuralMind work on *your* codebase?](https://github.com/dfrostar/neuralmind/blob/main/docs/use-cases/benchmark-your-repo.md)

## Support

- [GitHub Issues](https://github.com/dfrostar/neuralmind/issues) — bug reports, feature requests
- [GitHub Discussions](https://github.com/dfrostar/neuralmind/discussions) — questions and ideas
- [Main README](https://github.com/dfrostar/neuralmind/blob/main/README.md) — always the most current overview
