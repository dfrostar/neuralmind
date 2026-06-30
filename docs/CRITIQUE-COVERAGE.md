# Critique coverage scorecard

NeuralMind gets a recurring, fair external critique: "the repo sells the happy
path — where's the *here's where it sucks* section, the independent benchmarks,
the security specifics, the power-user internals?" This page is the durable answer:
the critique's points mapped to **where each is addressed**, what's **partial**,
and what's **honestly deferred** (and why).

Legend: ✅ closed · ◐ partial · ⏸ deferred (measurement/data work, not docs — we
don't fabricate numbers, case studies, or audits).

## 1. Independent / third-party benchmarks

| Point | Status | Where |
|---|:--:|---|
| Reproducible benchmark on real repos (not vendor fixtures) | ✅ | Public benchmark on pinned `requests`/`click` — [`docs/benchmarks/public.md`](benchmarks/public.md), traces in [`bench/public/`](../bench/public/) |
| Runnable `benchmarks/` folder | ✅ | [`benchmarks/README.md`](../benchmarks/README.md) + `run_all.sh` |
| SWE-bench accuracy | ◐ | **Retrieval** measured ([`evals/swe_bench/`](../evals/swe_bench/README.md)); end-to-end **solve-rate** ⏸ scaffolded (needs an agent loop + API key) |
| Aider polyglot agent accuracy | ⏸ | Feature comparison exists ([`vs-aider-repomap`](comparisons/vs-aider-repomap.md)); no agent-loop solve-rate |
| Head-to-head vs competitors | ◐ | One scored live (`codebase-memory-mcp`); the rest with exact blockers in [`evals/public/COMPETITORS.md`](../evals/public/COMPETITORS.md) |
| Independent (non-maintainer) runs | ⏸ | Reproducible + invited (`neuralmind benchmark . --contribute`); outside runs still accumulating |

## 2. Failure modes & limits

| Point | Status | Where |
|---|:--:|---|
| When compressed context fails / when to bypass | ✅ | [Limits & Failure Modes §1](wiki/Limits-and-Failure-Modes.md#1-when-the-compressed-context-is-enough--and-when-it-isnt) |
| Repo-size / index-time / memory / disk envelope | ✅ | [Limits & Failure Modes §2](wiki/Limits-and-Failure-Modes.md#2-repo-size-index-time-memory--disk-envelope) |
| Language coverage (what's indexed *and not*) | ✅ | [Limits & Failure Modes §3](wiki/Limits-and-Failure-Modes.md#3-language-support-matrix) |

## 3. Real-world usage data

| Point | Status | Where |
|---|:--:|---|
| Staleness / incremental re-index behaviour | ◐ | Explained ([Limits §2](wiki/Limits-and-Failure-Modes.md#2-repo-size-index-time-memory--disk-envelope)); no published latency SLA |
| MCP / IDE integration setup | ✅ | [Integration Guide](wiki/Integration-Guide.md) + `neuralmind install-mcp --all` |
| MCP / IDE latency numbers + UX | ⏸ | Not yet benchmarked |
| Customer case studies | ⏸ | None published — we won't fabricate dashboard screenshots |

## 4. Security & privacy

| Point | Status | Where |
|---|:--:|---|
| Supply chain / what's in the package | ✅ | [`SECURITY.md`](../SECURITY.md) + `pyproject.toml` deps |
| Telemetry | ✅ | Zero, actively suppressed — [`SECURITY.md`](../SECURITY.md), `neuralmind/__init__.py` |
| SBOM | ✅ | CycloneDX per release — `.github/workflows/sbom.yml` |
| Cloud vs local embeddings | ✅ | 100% local ONNX — [Architecture: Embedding model](wiki/Architecture.md#embedding-strategy), [`SECURITY.md`](../SECURITY.md) |
| Env-var / off-switch inventory | ✅ | [`SECURITY.md` → privacy/behaviour controls](../SECURITY.md) |
| Third-party security audit | ⏸ | None exists — disclosed honestly, not implied |

## 5. Engineering internals for power users

| Point | Status | Where |
|---|:--:|---|
| Chunking / L0–L3 progressive disclosure | ✅ | [Architecture: 4-Layer Progressive Disclosure](wiki/Architecture.md) |
| Embedding model spec + swappability | ✅ | [Architecture: Embedding model](wiki/Architecture.md#embedding-strategy) |
| Index format + inspect/export | ✅ | [Architecture: Index format & debugging](wiki/Architecture.md) |
| Debug "why did a query miss?" | ✅ | `query --trace/--explain/--relevance`, `probe`, `doctor` — [Architecture](wiki/Architecture.md) |

## The honest bottom line

The **documentation-shaped** gaps are closed; the **measurement/data-shaped** ones
(⏸) are real but require running evals with API keys, building agent loops, or data
we don't have — so they're tracked openly on [`ROADMAP.md`](../ROADMAP.md) and
listed in [`benchmarks/README.md`](../benchmarks/README.md) rather than papered over
with invented numbers. That honesty *is* the position — see
[`HONEST-ASSESSMENT.md`](HONEST-ASSESSMENT.md).
