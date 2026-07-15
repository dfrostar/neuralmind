# Plan — Code → Behavior: the next-evolution roadmap

**Created:** 2026-07-15
**Status:** Design / decision-pending (positioning fork must be resolved before Phase 2)
**Relates to:** PR #339 (cohesion-outlier prototype, already shipped on
`claude/neuralmind-evaluation-mth2d3`) — this doc is the roadmap that prototype
anchors.
**Owner seams:** `neuralmind/structural.py` (`StructuralIndex`),
`neuralmind/cohesion.py` (new), `neuralmind/synapses.py`,
`neuralmind/quality.py`, `neuralmind/cli.py`.

Origin: a multi-model evaluation of NeuralMind after a real debugging session
(the "handler #11" / Prisma `P2003` incident). The through-line every reviewer
reached independently:

> NeuralMind indexes **what is written**. The recurring pain is detecting
> **what is about to fail** — patterns that cross from code into runtime
> behavior. Three of the four highest-value asks are not yet first-class
> citizens of the product.

This plan sequences that evolution, names the strategic fork it forces, and
records the pre-implementation review so we build the scoped version, not the
scope-exploded one.

---

## TL;DR — the decision

1. **Do not ship one mega-release.** The four asks have very different risk
   profiles; bundling them hides a scope-explosion feature behind three cheap
   wins.
2. **Resolve the positioning fork first** (below). Two of the asks quietly
   convert NeuralMind from a *memory/retrieval* product into a *static
   analyzer*, which changes who we compete with.
3. **Ship "Surface what you can't see" as v-next** — three low-risk features
   that share one thesis. Defer data-flow to v-after and gate schema-aware
   analysis behind a measured spike.

---

## The positioning fork (decide before Phase 2)

Features that reason about *whether code is correct* (schema-aware analysis;
the precise end of data-flow) move NeuralMind across a line:

| Lane | Competes with | Judged on | Maintenance |
|------|---------------|-----------|-------------|
| **Memory / retrieval** (today) | context tools, RAG stacks | tokens saved, recall | bounded — the graph + synapses we already own |
| **Static analyzer** (where #1-precise and #2 lead) | CodeQL, Semgrep, SonarQube, WALA/Soot, Pyre/Infer | false-positive rate | unbounded — every framework, schema dialect, dispatch pattern forever |

Both are legitimate. But the analyzer lane is a *product identity change*, not
a feature, and the DeepSeek review flagged the exact tell: **we have not
justified why the incumbents are insufficient.** Until we can answer "why not
just run Semgrep with a custom rule?", schema-aware analysis stays a spike, not
a roadmap commitment.

**Recommendation:** stay in the memory lane as the anchor identity; borrow
analyzer techniques *only* where they make retrieval more complete (data-flow
as a smarter graph traversal), and treat true correctness-checking (#2) as an
opt-in adjacent product, spike-proven before it earns headline space.

---

## Phased plan

| Phase | Feature | Value | Lift | Risk | Gate |
|------:|---------|:-----:|:----:|:----:|------|
| **v-next** | Cohesion outlier (shipped, PR #339) | 🟡 | done | low | promote `feat:` + docs |
| **v-next** | `neuralmind gaps` — test/endpoint coverage | 🔴 | low | low | ship |
| **v-next** | Decision provenance — `Decision:` trailer | 🟡 | low | low | ship |
| **v-after** | Data-flow queries (structural, TS-first) | 🔴 | med | med | build to spec below |
| **spike** | Schema-aware analysis (Prisma-FK) | 🔴 | 🔴 | 🔴 | measure FP rate, then decide lane |
| **deferred** | Acceptance-criteria autofind | 🟢 | low | — | speculative |
| **won't** | Cross-repo trust boundary | 🟢 | — | — | keep the boundary (security property) |

**Why this ordering, not the reviewers':** the source doc calls schema-aware
"the killer / the big one." It is the highest *value* — and the highest
*risk*, and the one that changes our lane. `neuralmind gaps` is the sleeper:
it would have caught the actual `P2003` before the live smoke, and it is mostly
*join logic over data we already index*, not a new engine. Highest
value-to-lift ratio wins the front of the queue.

---

## v-next — "Surface what you can't see"

Three features, one thesis: the graph surfacing the thing a flat list hides —
the **outlier**, the **coverage gap**, the **lost rationale**. A release with a
narrative, and the direct sequel to the cohesion prototype.

### A. Cohesion outlier — *shipped, promote*

Already built in PR #339: `neuralmind/cohesion.py` finds the associate most of
a co-activation cluster links to and flags the members that skip it (the
"handler #11" node a flat recall list cannot distinguish from its peers). Wired
into `UserPromptSubmit` behind `NEURALMIND_SYNAPSE_OUTLIERS=1`, fails open,
off by default, 7 stdlib-only tests.

**To promote:** flip commit type to `feat:`, document
`NEURALMIND_SYNAPSE_OUTLIERS` in `docs/wiki/CLI-Reference.md`, run the standard
docs + SEO checklist per `CLAUDE.md`.

### B. `neuralmind gaps` — test/endpoint coverage cross-reference

**Problem it solves:** an endpoint can pass tests that only run in mock mode
(`MemorySessionStore` accepts any string; Postgres FK rejects non-UUIDs), so
"green" hides a live-only failure. This is the class of the `P2003` incident.

**Deliverable:** a CLI command that joins already-indexed symbols with test
references:

```
$ neuralmind gaps
POST /api/sessions          — 3 tests (all SKIP_PG=1) — ❌ no live-Postgres coverage
GET  /.well-known/jwks.json — 1 test (SKIP_PG=1)      — ❌ no live-Postgres coverage
GET  /health                — 0 tests                  — ⚠️  untested
```

**Seam:** new join over the existing graph — endpoints (route-registration call
sites: `app.get`/`app.post`/decorator routes) × test files (already indexed) ×
skip markers (env-gated `skip`/`SKIP_PG`). No new index; reuse `structural.py`
call edges + the embedder's node set.

**Acceptance criteria:**
- Detects route registrations for Express/Fastify/decorator styles (TS/Py Phase 1).
- Classifies each endpoint: `untested` / `mock-only` / `live-covered`.
- Route-string matching normalizes template literals and separated path
  constants (DeepSeek HIGH-6) — no false "untested" from `` `/api/${x}` ``.
- Zero false "untested" on this repo's own suite (ground-truth check in CI).

### C. Decision provenance — indexed rationale

**Problem it solves:** the "why is `resolveOrgId` per-handler?" question whose
answer lived in a human's head, not in any artifact NeuralMind indexes.

**Deliverable:** an agreed `Decision:` commit trailer (one sentence), indexed as
a first-class node type, surfaced on `browse`/recall:

```
Decision: resolveOrgId is per-handler, not middleware — avoids Prisma on
          /health, /metrics, /token; keeps tests simple.
```

**Seam:** post-commit git hook (we already install one via
`neuralmind init-hook`) parses the trailer; new `decision` node kind in the
graph; recall surfaces it when its subject nodes activate.

**Acceptance criteria:**
- `Decision:` trailer parsed on commit; malformed trailers ignored, never crash.
- Decision nodes appear in `synaptic_neighbors` recall for their subject symbols.
- Zero behavior change when no trailer is present (fail-open, like every hook).

**Why this is the most on-brand of the four:** NeuralMind is framed as
associative *memory*. Remembering *why* a decision was made is memory in its
purest form — this feature is closer to the product's identity than any
analyzer feature.

---

## v-after — Data-flow queries (structural, TS-first)

**Ask:** "show me everywhere `req.auth.orgId` flows in N hops," surfacing every
handler that reads the claim — not just the ones you already knew about.

**What already exists:** `StructuralIndex.blast_radius(node, depth)` gives
directional reachability along the call graph. Data-flow is that traversal made
*value-aware* (argument position / def-use), not a new subsystem.

### Pre-implementation review — integrated (DeepSeek v4 Pro)

The review approved the concept with Phase-1 scope tightening. Its findings are
now scope constraints, not open questions:

**CRITICAL — accepted:**
- **Phase 1 is TypeScript only.** Java Spring DI and Go structural interfaces
  defeat naive AST traversal; do not claim them.
- **Dynamic dispatch is explicitly excluded and documented.** Virtual calls,
  interface impls, and strategy patterns are out of scope for the static pass;
  the output must *say so* rather than silently miss them.
- **Cross-repo flows are out of scope** (and see the trust-boundary decision
  below — this is deliberate, not a gap to close).

**HIGH — accepted as requirements:**
- **`async`/`await`, Promise chains, and event emitters are first-class** in the
  TS model, or the traversal is useless on real Express code.
- **Evaluate LSP before writing a custom AST walker.** `typescript-language-server`
  already resolves types, references, and call hierarchy — likely cheaper and
  more correct than hand-rolled parsing. Spike LSP-backed traversal first.
- **Justify vs. incumbents.** The spec must state why CodeQL/Semgrep/WALA are
  insufficient here (answer likely: "we already hold the graph + synapse
  context; this is retrieval-completeness, not a new scanner install"). If we
  can't justify it, we don't build it — we emit a Semgrep rule.
- **No unverifiable targets.** Drop "finds 11+ paths"; replace with a
  ground-truth fixture and a measured recall number.
- **Set a false-positive-rate target up front.** A data-flow view with a 60% FP
  rate is untrusted and worse than nothing. Target ≤ published threshold on the
  fixture before shipping.

**Useful alternatives to fold in:**
- LSP-as-backend (above).
- Hybrid static + dynamic: instrument the test run to *capture* actual flow
  rather than guess it — turns tests into a data-flow oracle.
- LLM-as-augmenter: static traversal as the hint, the agent bridges uncertain
  (polymorphic) edges. Fits NeuralMind's "cortex + hippocampus" architecture
  exactly — the graph proposes, the agent disposes.

**Acceptance criteria (v-after):**
- TS-only; async/await modeled; dynamic dispatch labeled `unresolved`, never
  dropped silently.
- Ground-truth fixture with known flow paths; measured recall + FP rate
  reported in CI, both meeting a stated threshold.
- Justification-vs-incumbents section present, or the feature is cut.

---

## Spike (not a commitment) — Schema-aware analysis

**Ask:** flag a literal (`'default'`) flowing into an FK/UUID-constrained column
as a `P2003` risk, bridging application code × Prisma schema × Postgres type —
without needing live data.

This is the highest-value, highest-risk, lane-changing ask. **Do not roadmap it
as a feature yet.** Build a narrow proof:

- Scope: Prisma `schema.prisma` FK relations + literal arguments at the matching
  call sites. One stack, one bug class.
- Measure: false-positive rate on a real fixture (`tests/fixtures/`).
- Decide: only if FP rate is trustworthy *and* we can answer "why not a Semgrep
  rule / Prisma typegen?" does this earn roadmap space — and if it does, it
  likely ships as an **opt-in adjacent product**, not folded into the memory
  core (see positioning fork).

---

## Explicitly out of scope

- **Cross-repo / multi-repo flows** (e.g. a shared schema with a private
  enterprise repo). The per-project boundary is a **deliberate security
  property**, not a missing feature. If it is ever crossed it must be an
  opt-in, audited `--cross-project` flag — never the default. Keep the boundary.
- **Acceptance-criteria autofind** — deferred; speculative until a concrete
  invariant source exists.
- **Not asked for, confirmed:** build performance (fine), AI code generation
  (out of scope — the product *finds* what exists), new languages/frameworks
  (TS/Py coverage is enough for the driving use case).

---

## Open decisions for the owner

1. **Positioning:** confirm memory-lane-as-anchor, analyzer-as-opt-in-adjacent?
   This gates whether #2 ever leaves the spike.
2. **v-next contents:** confirm the three-feature "Surface what you can't see"
   release (cohesion promote + `gaps` + provenance)?
3. **Data-flow backend:** approve spiking LSP-backed traversal *before* any
   custom AST work?

Once (1) and (2) are settled, `neuralmind gaps` is the first build — highest
ROI, and it closes the exact hole that started this whole thread.
