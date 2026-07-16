# Use Case: Auditing Retrievals Over MCP

## What you're solving for

An agent asks `neuralmind_query` a question and gets back context that's
surprising — a file you didn't expect, or a hit you expected that's missing.
You're integrating NeuralMind into another agent framework and need
machine-readable attribution for what it returned, not just the CLI's `--trace`
output on your terminal. Or you're comparing NeuralMind against a competing
code-intelligence MCP server that advertises "auditability" and want to show
the same thing.

## Step 1 — Ask for a trace

`neuralmind_query` takes two new optional parameters, both `false` by default:

```json
{"tool": "neuralmind_query", "arguments": {
  "project_path": ".",
  "question": "how does auth work?",
  "trace": true
}}
```

The response gains a `trace` key on top of the usual `context`/`tokens`/`layers`
fields — no other part of the response shape changes.

## Step 2 — Read the trace

```json
"trace": {
  "query": "how does auth work?",
  "verbose": false,
  "events": [
    {"layer": "candidates", "kind": "search", "summary": "8 vector candidates", "data": {"candidates": [...]}},
    {"layer": "L2", "kind": "cluster_scores", "summary": "selected 3 of 6 clusters (budget 3)", "data": {"clusters": [...], "selected": [0, 2, 4]}},
    {"layer": "synapse", "kind": "hit_synapse_boost", "summary": "handlers/auth.py boosted +0.30 from co-activation", "data": {"seeds": [...], "node_id": "...", "energy": 1.0, "weighted_boost": 0.3, "recalled": false}},
    {"layer": "L3", "kind": "hits", "summary": "4 final hits (1 synapse-recalled)", "data": {"hits": [...]}},
    {"layer": "compose", "kind": "budget", "summary": "4 layers, 1180 tokens, 42.0x reduction", "data": {"tokens": {...}, "reduction_ratio": 42.0}}
  ]
}
```

Each event maps to a retrieval layer: `candidates` (raw vector search before
selection), `L2` (which clusters were selected and why), `synapse` (which hits
got boosted by learned co-activation and how much), `L3` (the final ranked
hits), `compose` (token budget and reduction ratio). If a result is surprising,
walk the events in order — the layer that introduced or dropped the node you
care about is usually obvious.

## Step 3 — Distinguish boosted from pulled-in hits

The `synapse` events carry a `recalled` field:

- `recalled: false` — a hit vector search already found, re-ranked upward by
  co-activation.
- `recalled: true` — a hit vector search *missed*, pulled in purely because
  the synapse graph co-activates it strongly with your top hits. This is
  usually the more interesting case: it's NeuralMind surfacing something your
  query didn't literally match but your usage pattern says belongs.

## Step 4 — Get everything, not the trimmed default

```json
{"tool": "neuralmind_query", "arguments": {
  "project_path": ".", "question": "...", "trace": true, "trace_verbose": true
}}
```

Non-verbose trims the candidate list to the top 10 to keep the payload small;
verbose keeps everything up to the 25-item cap.

## Equivalent CLI

The same trace has been available on the command line since PRD 3 Phase 1 —
useful for local debugging without going through MCP:

```bash
neuralmind query "how does auth work?" --trace          # summary view
neuralmind query "how does auth work?" --trace-verbose   # full candidate/hit lists
neuralmind query "how does auth work?" --explain          # human-readable narrative
```

## What this doesn't do

- **No persistent history.** A trace lives for one query call. There's no
  "show me every past retrieval that surfaced file X" store — if you need
  that, log the `trace` payloads yourself on the client side.
- **No graph UI replay yet.** `neuralmind serve` visualizes live activity, but
  trace-driven replay of a specific past query is a later phase.
- **Bounded, not exhaustive.** Lists cap at 25 items even in verbose mode, so
  a trace stays small enough to ride along in a normal MCP response.

---

[← Back to use-case index](./README.md) · [Main README](../../README.md)
