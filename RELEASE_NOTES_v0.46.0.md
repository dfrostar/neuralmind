# NeuralMind v0.46.0 — Audit trace over MCP

CLI users have been able to ask *"why did NeuralMind give me this?"* since PRD 3
shipped `--trace`/`--trace-verbose`/`--explain`. Agents talking to NeuralMind over
MCP — the primary integration surface — couldn't. v0.46.0 closes that gap.

```json
{"tool": "neuralmind_query", "arguments": {
  "project_path": ".", "question": "how does auth work?", "trace": true
}}
```

## What you get

`trace: true` attaches the same structured `RetrievalTrace` the CLI has always
produced — candidate pool, L2 cluster scoring, synapse-boost attribution, final L3
hits, token budget — as a JSON object on the response, keyed `trace`. `trace_verbose:
true` keeps the full candidate/hit lists instead of the trimmed default. Both are
opt-in and default `false`, so existing callers see no change.

```json
"trace": {
  "query": "how does auth work?",
  "verbose": false,
  "events": [
    {"layer": "candidates", "kind": "search", "summary": "8 vector candidates", "data": {...}},
    {"layer": "L2", "kind": "cluster_scores", "summary": "selected 3 of 6 clusters (budget 3)", "data": {...}},
    {"layer": "synapse", "kind": "hit_synapse_boost", "summary": "node_low boosted +0.30 from co-activation", "data": {...}},
    {"layer": "L3", "kind": "hits", "summary": "4 final hits (1 synapse-recalled)", "data": {...}},
    {"layer": "compose", "kind": "budget", "summary": "4 layers, 1180 tokens, 42.0x reduction", "data": {...}}
  ]
}
```

## What changed under the hood

Most of this machinery already existed and was already tested — this release is
deliberately thin:

- **`neuralmind_query` now accepts `trace`/`trace_verbose`.** Previously the MCP
  tool silently dropped these even though `NeuralMind.query()` supported them
  end-to-end since PRD 3 Phase 1.
- **L3 synapse boosts are now traced, not just recorded.** A boosted or
  co-activation-recalled hit already carried a `_synapse_boost` score delta; it
  now also produces a `hit_synapse_boost` trace event showing which seed(s) and
  how much energy produced it — closing the one asymmetry between L2 cluster
  boosts (already traced) and L3 hit boosts (previously untraced).

## Honest scope

- No new storage. A trace lives only for the duration of one query — there is no
  persistent, cross-session audit log. "Show me every past retrieval that
  surfaced file X" is a future feature, not this one.
- No new CLI surface — `--trace`/`--explain` already existed. This is the MCP
  side catching up to the CLI, not new capability.
- Bounded and redactable, same as the CLI: capped at 25 items per list, and
  `render_text()`/CLI rendering is unaffected — the MCP payload is structured
  JSON by design, since a downstream agent needs to reason over it, not read it.

This is `docs/plans/2026-06-10-future-proofing-prd-pack.md`'s PRD 3 Phase 2 exactly
as scoped ("MCP trace metadata"). See [docs/BRD-SYNAPSE-AUDIT-TRACE.md](docs/BRD-SYNAPSE-AUDIT-TRACE.md)
and [docs/TRD-SYNAPSE-AUDIT-TRACE.md](docs/TRD-SYNAPSE-AUDIT-TRACE.md) for the full
requirements and design rationale.
