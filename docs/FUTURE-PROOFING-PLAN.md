# NeuralMind Future-Proofing Plan — v2.0

**Status:** Approved · **Date:** 2026-07-17 · **Author:** Hermes (architecture review) · **Approved by:** dfrostar
**Reads alongside:** `ROADMAP.md`, `docs/HONEST-ASSESSMENT.md`, `docs/BUSINESS-CASE.md`
**Supersedes:** `docs/FUTURE-PROOFING-PLAN.md` (v1.0, April 2026), `docs/plans/2026-06-10-future-proofing-prd-pack.md`

---

## 0. How to read this document

Section 1 is the honest architecture audit — what's working, what's theater, and where
the structural gaps are. Sections 2-8 are the seven build buckets, each with a current
state, the gap, and the concrete build plan. Section 9 is the dependency-ordered
sequence. Section 10 is the "why these decisions" rationale for the calls made on
behalf of the maintainer.

This plan is written at the same altitude as the public material: no overclaims, no
dead code paths, no compliance theater. Anything deferred behind a decision gate is
flagged. Anything recommended to *not* build is flagged too.

---

## 1. Honest architecture audit

### What's genuinely working

- **Synapse layer (associative memory).** Hebbian reinforcement + LTP + directional
  transitions + half-life decay + hub normalization, namespace-isolated
  (personal/shared/branch/ephemeral), SQLite-backed for zero-dependency installs.
  Structural edge seeding gives day-one signal. This is differentiated — no open-source
  code-memory tool has it. The code comment in `self_improve.py` is right: *"the
  synapse layer is the product; the vector-RAG half is commodity."*

- **Ten-language tree-sitter extraction.** Python, TypeScript, Go, Rust, Java, C, C++,
  C#, Ruby, PHP behind one seam. `pip install neuralmind && neuralmind build` works
  with no graphify install. Measured parity with graphify on Python, structural
  symbol-coverage check on the others.

- **Local-first posture.** MIT-licensed, stdlib daemon, token-guarded loopback HTTP,
  no phone-home, optional memory logging behind a consent sentinel. Air-gapped
  install walkthrough. This is the moat vs. Copilot/Cursor native memory.

- **Honesty infrastructure.** `HONEST-ASSESSMENT.md` documents where it isn't worth
  installing. Public benchmark vs. `codebase-memory-mcp`. Privacy-claims CI guard.
  This protects trust — a competitive advantage.

- **Audit trail.** Tamper-evident hash chain, per-actor, SIEM-exportable. Shipped.

### What's theater (structure without function)

- **IR (Intermediate Representation).** PRD 1 built a versioned canonical IR with
  migration seams, round-trip-faithful adapters, and a 4-shipit rollout. Phase 1 shipped
  (hidden adapter, legacy default — `ir.py` exists, `.neuralmind/index_ir.json` is
  written on every build). Phases 2-4 never happened. Nothing in the retrieval stack
  *reads* the IR. The embedder still consumes `graph.json` directly. The IR is archival
  output, not a live contract. Verdict: architectural swagger without migration.

- **Self-improvement engine.** `self_improve.py` tunes one parameter (`l2_recall_k`)
  via a hand-tuned hysteretic dead band reading `re_query_rate`. Line 66-68 of that file
  flags its own weakness: *"Provisional thresholds...unvalidated guesses. Phase 3
  (eval-driven tuning) will replace this with a real fitness function."* Phase 3 never
  happened. The tuner is a thermostat with no thermometer.

- **Empty quality harness.** `neuralmind benchmark --judge` shipped in v0.34. The
  `bench/public/judge/` directory is still empty. Token reduction is the only CI-gated
  metric. No faithfulness measurement, no nDCG, no MRR, no per-language eval.

### Hard gaps (structural, not incremental)

1. **Retrieval is single-vector + BM25 RRF.** The field moved to late-interaction
   models (ColBERTv2, SPLADE, Wholembed v3) and cross-encoder reranking. RRF is a good
   first-stage approximation; the reranking stage is absent.

2. **No reasoning trace memory.** The synapse layer records *that* nodes co-activated,
   not *why*, *what strategy worked*, or *what failed*. The 2026 state of practice
   (Cognee graph-native memory, Mem0 v3 reasoning traces, the "immutable
   run-log-as-RL-at-the-database-layer" pattern from the agent-memory landscape) is
   structured memory with outcome tracking. You have co-activation without outcome.

3. **Team memory is a static one-way bundle.** No merge semantics when contributors
   disagree, no contribution-quality scoring, no decay-on-conflict, no peer-review
   gate. The onboarding-lift eval (E1.5) that was supposed to *gate* the shared-memory
   build was measured, then the shared-memory build shipped as a one-way import, not
   the two-layer model the eval was designed to validate. The E1.5 loop is open.

4. **Tree-sitter-only precision.** No SCIP/LSP for compiler-accurate edges. Dynamic
   imports (Python `importlib`, JS `require(variable)`) produce no structural edges.
   Communities are balanced-per-file, not real architectural modularity.

5. **MCP transport is stdio only.** The 2026 MCP standard is Streamable HTTP with OAuth
   2.1 session management. stdio locks you to single-client local usage.

6. **No tool-use metrics pipeline.** Query latency, retrieval reuse rate, tool-call
  success rate, per-query cost — none are logged continuously. The daemon has a health
  endpoint but no observability feed.

---

## 2. Bucket A — Memory Layer Deepening (the product)

> The synapse layer is differentiated. Invest here first and deepest.

### Current state
- Hebbian synapses + directional transitions in SQLite (`synapses.db`)
- Half-life decay: fixed per-namespace constants (30d personal, 60d shared, 1d ephemeral)
- Hub normalization, LTP threshold, structural edge seeding
- Namespaces: personal, shared, branch:<name>, ephemeral
- Self-improvement: 1-param tuner

### Gap
- No reasoning trace memory (outcome signals)
- No entity resolution (team memory can't merge)
- Decay rates are not learned per-edge
- No offline consolidation ("sleep") phase

### Build plan

**A1. Reasoning trace store.** Add an immutable `reasoning_traces` table to
`synapses.db`: (session_id, timestamp, query_fingerprint, strategy, tools_used,
outcome, success_signal). Powers "the agent learned what works." Queryable by
the synapse recall path so retrieval can favor nodes from successful past strategies.
Schema-versioned alongside the existing meta table. Fail-open: traces are observational,
never load-bearing.

**A2. Entity resolution layer.** When merging team memory or importing bundles,
resolve synapse node identity by structural-anchor + normalized-label, not exact
ID match (the existing `normalize_namespace` + `norm_label` seam is the start).
Required for any real merge semantics. Thresholds: >=0.95 cosine auto-merge,
>0.85 human-review flag (the "Apple company vs. Apple fruit" disambiguation the
agent-memory literature flags as the #1 graph-corruption source).

**A3. Learned per-edge decay.** Replace fixed `HALF_LIFE_DAYS` with a scalar adapted
per edge from its reinforcement frequency and recency distribution. Edges that
survive repeated reinforcement get longer half-lives; edges that are rarely
reinforced decay faster. Bounded to [HALF_LIFE_MIN, HALF_LIFE_MAX] to prevent
pathology. The tuner (Bucket C) learns the bounds, not the individual rates.

**A4. Sleep consolidation.** A scheduled daemon pass (weekly, configurable) that:
prunes redundant edges, promotes LTP edges that survived decay, emits a consolidated
team-baseline bundle, detects stale team edges (no reinforcement in N days).
This is the "offline memory reorganization" that the agent-memory literature shows
reduces retrieval noise by 30-50% in long-running knowledge graphs.

---

## 3. Bucket B — Retrieval Quality Upgrade (the commodity, with a moat)

> Single-vector + BM25 RRF was state of the art in 2024. Close the gap to 2026.

### Current state
- TurboVec/ONNX (default) + ChromaDB fallback, single-vector dense retrieval
- RRF merge with BM25 when the backend supports it
- L0-L3 manual progressive disclosure, hardcoded layer budgets
- Synapse-boosted L2, structural L3 expansion

### Gap
- No learned sparse / late-interaction retrieval
- No cross-encoder reranking
- IR written but not consumed
- Layer budgets are hand-tuned constants

### Build plan

**B1. IR-as-primary-contract migration (finish PRD 1).** Make the embedder read
`.neuralmind/index_ir.json` instead of `graphify-out/graph.json`. The IR adapter
(`ir.py`, already round-trip-faithful) becomes the canonical path. Legacy
`graph.json` loading retained for one minor release, then deprecated. Closes the
ghost-contract gap.

**B2. Learned sparse retrieval.** SPLADE-style expansion over the existing BM25
index. A lightweight expansion model (distilled from MiniLM, ONNX-compatible) maps
each chunk to a sparse weighted token vector. Queried via the same RRF path.
Approximation cost: one extra forward pass per chunk at index time, ~5% storage
uplift. Skip full ColBERT (per-token embeddings for thousands of code chunks are
too storage-heavy for local-first; learned sparse is the right trade).

**B3. Cross-encoder reranking.** A distilled cross-encoder (ms-marco-MiniLM,
ONNX-compatible) reranks the top-20 candidates from the RRF+learned-sparse first
stage before L2/L3 fusion. Typically a 5-15% precision lift for a weekend build.
Optional via `NEURALMIND_RERANK=1`, with a latency budget cap
(`NEURALMIND_RERANK_MAX_MS`) to keep it off the hot path on slow machines.

**B4. Hierarchical summarization for L0-L3.** RAPTOR-style recursive summarization
at each layer, replacing the hand-tuned `L0_MAX_TOKENS`/`L1_MAX_TOKENS`/etc.
constants with a learned depth selector. Couples with B1 (IR is the contract for
stored summaries). Deferred in the sequence (needs B1 + D to validate).

---

## 4. Bucket C — Self-Improvement Engine v2 (autonomous local evolution)

> The moat. No open-source code-memory tool tunes itself against a real fitness
> function. Population-based evolutionary optimization in the daemon is the
> differentiator that keeps the product current without a research team.

### Current state
- `self_improve.py`: tunes `l2_recall_k` only (one parameter)
- Signal: `re_query_rate` (weak, noisy — acknowledged in code)
- Hand-tuned hysteretic dead band, no eval feedback
- Gated behind `NEURALMIND_SELECTOR_AUTOTUNE=1`

### Gap
- One parameter is a thermostat, not an engine
- No fitness function (can't optimize what you don't measure)
- No population search (2026 research: evolutionary optimization 2-3x gains)
- No online learning loop

### Build plan

**C1. Multi-objective fitness function.** The tuner's North Star. Three axes,
combined via a weighted product (so a zero on any axis dominates):
- *Retrieval quality*: faithfulness delta (from D, the quality harness) — the
  "does the agent answer better" signal.
- *Efficiency*: token-cost reduction — the "does it cost less" signal.
- *Session health*: re-query-rate + transition-margin — the "does the agent stop
  repeating itself" signal.
Weights are operator-configurable (`NEURALMIND_FITNESS_WEIGHTS="0.5,0.3,0.2"`),
persisted in the synapse meta table, tunable per project.

**C2. Expanded parameter space.** Move beyond l2_recall_k. Candidates:
`SYNAPSE_BOOST_WEIGHT`, `STRUCTURAL_BOOST_WEIGHT`, `SPREAD_DEPTH`,
`L0/L1/L2/L3_MAX_TOKENS`, `STRUCTURAL_HUB_DEGREE`, `decay rate bounds`,
community sensitivity. ~8-12 knobs. Each bounded per the existing clamp constants
in `context_selector.py` and `synapses.py`. The tuner never proposes values the
components would reject.

**C3. Population-based search (evolutionary).** Local-first, runs in the daemon.
Population size 10-20 candidate configs. Each generation:
- Sample candidate configs from a bounded space (Gaussian perturbation around
  the current best, with uniform-exploration probability 0.15).
- Evaluate each against (C1) fitness on the project's real query traces from
  the last N sessions (the `reasoning_traces` table from A1 feeds this).
- Select top-k, mutate, repeat for a bounded number of generations.
- Promote the winner if fitness exceeds the incumbent by a hysteresis margin.
Cost: the daemon runs this offline (weekly, configurable), not on the query hot
path. No cloud dependency. Evaluation data is the user's own query history.

**C4. CI-gated promotion.** Tuned configs are validated against the eval harness
(D) before promotion. Rollback on regression. The daemon proposes; the harness
disposes. Prevents the "tuner degrades real quality while optimizing a proxy"
pathology that the current `re_query_rate`-only signal is vulnerable to.

---

## 5. Bucket D — Quality Harness Completion (measure what matters)

> You can't improve what you don't measure. The `--judge` arm has shipped with an
> empty directory for three months. Close this loop.

### Current state
- Token reduction benchmark: CI-gated, regression-tracked. Working.
- Retrieval quality: top-k hit rate on Python fixture only.
- `--judge` harness: shipped (v0.34), `bench/public/judge/` empty.
- `probe`: label-free self-test, works but limited signal.

### Gap
- No faithfulness, context-precision, answer-relevance measurement
- No nDCG / MRR / hit-rate@k
- No per-language eval beyond Python
- Empty judge directory reduces the feature to a stub

### Build plan

**D1. RAGAS-axis offline judge (zero LLM cost).** Following the v0.13 eval design
principle ("ship a real offline heuristic judge as the default; make the API judge
strictly opt-in"):
- *Context precision*: embedding-cosine between retrieved chunks and query.
- *Context recall*: embedding-cosine between gold facts and retrieved chunks.
- *Faithfulness*: token-overlap + contradiction heuristic (negation detection,
  entity consistency) between the generated answer and the retrieved context.
- *Answer relevance*: embedding-cosine between the answer and the query.
All four run with zero network. Reported per-query, aggregated per-build, CI-gated
against regression.

**D2. Retrieval metrics.** MRR, nDCG@k, hit-rate@k, precision@k over the fixture
query set. Fixed k values per benchmark (5, 10, 20). CI-gated. Visible in
`neuralmind benchmark --quality` output.

**D3. Populate bench/public/judge/.** Run the opt-in LLM-judged arm
(`neuralmind benchmark --public --judge`, requires `ANTHROPIC_API_KEY`) on the
maintainer's projects, commit the transcripts. This removes the single biggest
credibility gap in the public eval story. Deferred behind D1 (offline judge runs
in CI with no cost; the LLM-judged arm is opt-in and costs tokens).

**D4. Per-language fixtures.** TypeScript, Go, Rust, Java fixtures with real
query + gold-fact sets, mirroring the Python one (which already exists). Required
to make "Python-strong, polyglot-weaker" visible and tracked (the current
`HONEST-ASSESSMENT.md` caveat becomes a tracked metric instead of a disclosure).

---

## 6. Bucket E — Team Memory as Product (enterprise wedge)

> The onboarding-lift story is the highest-value enterprise pitch. Close the E1.5
> loop honestly: measure lift, score contributions, gate on review.

### Current state
- Committed team bundle (`.neuralmind-team-memory.json`)
- One-way import into `shared` namespace on first build or SessionStart
- No merge semantics, no quality scoring, no decay-on-conflict

### Gap
- Static bundle, not a living merge
- No contribution-quality signal
- E1.5 eval shipped but its findings weren't fed back into the merge design
- No peer review, no staleness detection

### Build plan

**E1. Contribution-quality scoring.** Weight team-memory contributions by the
contributor's measured onboarding lift: did their bundle actually improve
new-agent faithfulness/recall in the E1.5 eval? High contributors' edges get
higher initial weight in `shared`; low contributors' edges start low and rely
on their own reinforcement to persist. Closes the E1.5 loop honestly.

**E2. Merge semantics with decay-on-conflict.** When two contributors' bundles
disagree on the same edge, weight by contribution-quality score, decay the loser.
Required: entity resolution (A2). Without it, same edge from different ID schemes
isn't recognized as conflict. This is the difference between "team brain" and
"muddy average."

**E3. Peer review gate.** Team-baseline contributions require human review before
commit. Simple mechanism: GitHub PR on the bundle file, with the E1.5 eval delta
in the PR comment (generated by D). Not a new tool — existing GitHub workflow.

**E4. Staleness detection.** Flag team-baseline edges that haven't been reinforced
by any team member's actual usage in N days (configurable, default 60). Couples
with A4 (sleep consolidation prushes stale team edges during the weekly pass).

---

## 7. Bucket F — Daemon + MCP Production Hardening

> Infrastructure. Not glamorous, but required for multi-client usage and the
> self-improvement engine's continuous operation.

### Current state
- stdlib HTTP daemon (PRD 5 Phase 1 — experimental)
- Per-project locking, JobManager, discovery file, token auth
- MCP server over stdio only
- `/healthz` endpoint, systemd/launchd/Windows Task Scheduler templates

### Gap
- MCP transport is stdio (single-client local only)
- Experimental daemon, no shared memory model across MCP clients
- No tool-use metrics pipeline
- No backpressure / circuit breakers

### Build plan

**F1. Streamable HTTP transport for MCP.** Follow the 2026 MCP spec
(Streamable HTTP sessions, OAuth 2.1). Enables remote usage, multi-client
sessions, web-based clients. Stdio retained as fallback for local CLI.

**F2. Shared daemon memory model.** MCP clients connect to the daemon, share
the warm `NeuralMind` instance + synapse store + selector cache. Eliminates
cold-start per client. Required: per-client access scoping (a client project
can't read another client's synapse data unless explicitly shared).

**F3. Tool-use metrics pipeline.** Continuous logging: per-query latency,
retrieval reuse rate, tool-call success rate, per-query token cost, synapse
activation counts. Feeds the fitness function (C1) and the team-memory quality
scoring (E1). Structured JSONL to `.neuralmind/metrics/`, bounded retention.

**F4. Backpressure + circuit breakers.** Concurrent build/query/watch on the
same project degrades gracefully: queue with bounded depth, fail fast on
overload, recover automatically. The existing `ProjectRegistry` + per-project
lock is the start; add queue depth signaling and a circuit-breaker state
machine (closed → open → half-open) on the daemon.

---

## 8. Bucket G — Graph Generation Precision

> The commodity half. Raise it to the 2026 state of practice without turning it
> into the product.

### Current state
- 10 languages via tree-sitter
- Graphify-compatible `graph.json` output
- Balanced per-file communities (stand-in for modularity)
- Incremental re-embedding (unchanged files skipped)

### Gap
- No SCIP/LSP for compiler-accurate edges
- Dynamic imports (Python `importlib`, JS `require(variable)`) produce no edges
- No real modularity clustering
- No incremental re-extraction (only re-embedding)

### Build plan

**G1. Cross-file import resolution for dynamic languages.** Static analysis over
the AST + string-literal heuristic (resolve `importlib.import_module("foo")` and
`require(variable)` when the argument is a string literal or a bounded set of
literals). Closes the "phantom edge" gap. For literals: deterministic. For
variables: flagged as low-confidence (`confidence_score < 0.5`), surfaced but
down-weighted in retrieval.

**G2. SCIP precision pass (the v0.17 stretch that never happened).** For
languages with SCIP support (Go, Rust, Java, C/C++), use `scip-index` at build
time for compiler-accurate edges. Falls back to tree-sitter where SCIP is
unavailable. Gated behind `NEURALMIND_SCIP=1` (opt-in until measured parity).

**G3. Real modularity clustering.** Replace balanced-per-file communities with
a graph modularity algorithm (Louvain/Leiden) over the structural edge set.
Communities match architectural boundaries, not file boundaries. This is the
difference between "cluster 3 is utils.py" and "cluster 3 is the auth module."
Required: the structural edge set must be good enough (G1 + G2 first).

**G4. Incremental re-extraction.** Currently only re-embedding is incremental.
Re-extract symbols from changed files + their dependents (using the structural
index's reverse edges — `structural.py` already indexes `callers`/`importers`)
on each build. Skips the full-tree reparse that makes large-repo builds slow.

---

## 9. Sequence & dependency order

```
            ┌─────────────────────────────────────┐
            │           WAVE 1 (parallel)         │
            │  D  Quality harness (RAGAS + MRR)   │
            │  B1 IR-as-primary-contract          │
            │  G1 Dynamic import resolution       │
            └──────────┬──────────────┬───────────┘
                       │              │
            ┌──────────▼──────┐  ┌───▼──────────────┐
            │   WAVE 2        │  │   WAVE 2         │
            │ A1 Reasoning    │  │ G2 SCIP precision │
            │   traces        │  │                  │
            │ A2 Entity       │  │                  │
            │   resolution    │  │                  │
            │ B2 Learned       │  │                  │
            │   sparse         │  │                  │
            │ B3 Cross-encoder │  │                  │
            │   reranking      │  │                  │
            │ C1 Fitness fn    │  │                  │
            │   (needs D)      │  │                  │
            └──────────┬──────┘  └───┬──────────────┘
                       │              │
            ┌──────────▼──────────────▼───────────┐
            │           WAVE 3                     │
            │  C2 Expanded parameter space          │
            │  C3 Population-based search (evo)     │
            │  A3 Learned per-edge decay             │
            │  A4 Sleep consolidation                │
            │  B4 Hierarchical summarization (needs  │
            │     B1 + D)                            │
            │  F1 Streamable HTTP MCP                │
            │  F2 Shared daemon memory               │
            └──────────────┬───────────────────────┘
                           │
            ┌──────────────▼───────────────────────┐
            │           WAVE 4                      │
            │  C4 CI-gated tuner promotion           │
            │  G3 Modularity clustering (needs G1+2)│
            │  G4 Incremental re-extraction          │
            │  E1 Contribution-quality scoring       │
            │  E2 Merge semantics (needs A2)         │
            │  E3 Peer review gate                   │
            │  E4 Staleness detection (needs A4)     │
            │  F3 Tool-use metrics pipeline          │
            │  F4 Backpressure + circuit breakers    │
            │  D3 Populate judge transcripts         │
            │  D4 Per-language fixtures              │
            └───────────────────────────────────────┘
```

Critical path: **D → C1 → C2/C3 → A3/A4 → E1/E2/E4**. The quality harness feeds the
fitness function; the fitness function drives the tuner; the tuner learns decay
and consolidation; the consolidation feeds team-memory quality. Everything that
*makes the product smarter* flows through this path. The retrieval upgrades
(B2/B3/B4) and graph precision (G1-G4) are force multipliers — they make the
tuner's job easier — but the critical path is the learning loop.

Parallelizable in Wave 1: D, B1, G1 can all start concurrently (different modules,
no cross-deps). Staff D first because it unlocks C1 which unlocks everything
that makes the product adaptive.

---

## 10. Decisions made on behalf of the maintainer (with rationale)

These are the calls that shape the plan. Push back on any of them.

### C — Self-improvement is deep, not narrow

The maintainer said they need "a level of self improvement and evolution at the
local level to keep it current." Full population-based evolutionary optimization
is recommended, not a fixed-point tuner with a real fitness function.
Rationale: a single-point tuner with a real fitness function is just a better
thermostat. The 2026 research consensus (Microsoft Copilot Tuning Research, Imbue's
Darwinian Evolver at 2-3x, OpenAI self-evolving agents, Amazon constrained policy
optimization) is that *searching the population* of configs — not hill-climbing one
— is what produces genuine capability gains. The daemon runs this offline on the
user's own query traces, so it's local-first and private. The risk is search cost;
I'm bounding population (10-20) and generations (5-10) and requiring CI-gated
promotion (C4) to prevent regression. This is the moat.

### B — Learned sparse + cross-encoder, not full ColBERT

Full ColBERT (per-token embeddings for every chunk) is storage-prohibitive for
local-first. Learned sparse (SPLADE-style expansion) approximates the late-
interaction signal at ~5% storage cost. Cross-encoder reranking on the top-20
candidates captures 80% of the late-interaction benefit for a weekend build. IR
migration (B1) is the prerequisite — no point reranking against a ghost contract.

### G — SCIP only where it's supported, Louvain/Leiden modularity

SCIP precision for Go/Rust/Java/C++ is real; SCIP for Python/TS/Ruby is not, so
tree-sitter stays the default there. Modularity clustering (Louvain/Leiden)
over the structural edge set produces architecturally-meaningful communities
(the auth module, the data layer), which is what L2 is *supposed* to surface.
This replaces the current balanced-per-file clustering, which is a workaround, not
a solution.

### F — Streamable HTTP, shared memory, bounded metrics

Streamable HTTP is the 2026 MCP standard. Not adopting it locks the product into
single-client local usage. Shared memory in the daemon is required for the
self-improvement engine to observe cross-client query patterns. Metrics pipeline
(log-structured, bounded retention) is the cheap observability that feeds every
other bucket.

### NOT building (and why)

- **Hosted SaaS.** Explicitly out of scope per ROADMAP. The moat is local-first.
- **Cross-repo / org-wide search.** That's Sourcegraph Cody's niche.
- **Inline completion.** Copilot's niche.
- **ColBERT full multi-vector.** Storage-prohibitive for local-first; learned
  sparse approximates most of the benefit.
- **LLM-judged offline judge.** The v0.13 principle holds: zero-cost offline
  judge is the default, LLM judge is opt-in. The empty `--judge` directory is
  filled last (D3), after D1/D2 provide the CI gate at zero cost.

---

## 11. Success criteria

| Criterion | Target | Measurement |
|---|---|---|
| Retrieval quality (with-synapse vs without) | Faithfulness delta >= +10pts | `neuralmind eval --quality` (D1) |
| Retrieval discrimination | MRR >= 0.65 on fixture query set | `neuralmind benchmark --quality` (D2) |
| Token cost | Maintain <= current reduction ratio | Existing CI benchmark gate |
| Self-improvement efficacy | Tuner improves fitness >= 15% over default in 4 weeks | `neuralmind savings --tuner` (C3) |
| Team onboarding lift | New-agent faithfulness + >= 15% with team baseline | E1.5 eval, rerun post-E1 (E1) |
| Graph precision | Structural edge recall + >= 20% with SCIP (G languages) | `evals/parity` per-language check |
| MCP transport | Streamable HTTP serves >= 3 concurrent clients | `neuralmind serve --http` integration test |

---

## 12. What this plan explicitly does NOT assume

- It does not assume headcount. Every bucket is scoped for a solo maintainer.
- It does not assume a hosted backend. All fitness evaluation, tuner search,
  sleep consolidation, and team-memory merge are local-first.
- It does not assume the IR migration succeeds. B1 is plan A; the legacy
  `graph.json` path is retained for one minor release regardless.
- It does not assume SCIP is available everywhere. Tree-sitter stays the default
  for languages without SCIP support.

---

*This plan is a living document. Open an issue to propose a new bucket, re-sequence,
or argue for re-prioritization. The superseded plans
(`docs/FUTURE-PROOFING-PLAN.md` v1.0, `docs/plans/2026-06-10-future-proofing-prd-pack.md`)
are archived to `docs/archive/`.*
