# NeuralMind v0.41.0 — the feedback loop closes, and the relevance signal goes on the wire

**Release Date:** June 2026

## What's in this release

Two features that make NeuralMind's half of a *modular* agent stack real —
the retrieval layer now **learns from what the agent did** and **emits the
relevance signal it already computes** as structured data a downstream tool
can consume:

| Change | What | Surface |
|---|---|---|
| **Reuse-vs-rewrite feedback** | a new **Edit/Write** PostToolUse hook detects whether new code *reached for existing graph symbols* (reuse) and feeds that back into the synapse layer, so future retrieval prefers what was actually reused | `edit-activity` hook · `NEURALMIND_REUSE_FEEDBACK` |
| **Structured relevance sidecar** | retrieval can now attach a machine-readable `relevance` block (per-file, per-node vector score / synapse boost / recall flag + line spans) so a downstream compressor can protect the load-bearing spans instead of shrinking them away | `neuralmind_query(include_relevance=true)` · `neuralmind query --relevance` |

Both are **opt-in / off-by-default on the wire** (the feedback hook can be
disabled with one env var; the sidecar is only attached when requested), so
nothing about default retrieval changes.

> **Implicit vs. explicit feedback.** v0.38.0 shipped `neuralmind_feedback`,
> an **explicit** MCP tool the agent calls to up-/down-weight a node. This
> release adds the **implicit** half: the agent doesn't have to say anything —
> NeuralMind observes what it *reused* from the Edit/Write it already made and
> learns from that. The two are complementary; explicit feedback is a deliberate
> correction, reuse feedback is a passive signal from normal work.

---

## Why this release matters

NeuralMind is the **retrieval** layer of a stack where compression and
generation guardrails are separate tools. The standard critique of a modular
split is that the layers can't see each other: a compressor downstream shrinks
spans without knowing *why* they were retrieved, and nothing feeds *what the
agent reused vs. rewrote* back into memory. v0.41.0 closes NeuralMind's half of
both seams.

### 1. The feedback loop — reuse vs. rewrite

NeuralMind's synapse layer already learns *what code goes with what* from
co-activation. Until now it never learned from the **outcome** of an edit. The
new **`edit-activity`** PostToolUse hook fires on every `Edit`/`Write`:

- It resolves the edited file to its graph nodes, then scans the new code for
  identifiers that name a symbol **defined elsewhere in the graph**.
- Those references are a **reuse** signal — the edited file and the reused
  definitions fired together in one thought — so their **synapse edges are
  reinforced**. The existing L2/L3 synapse boost then surfaces the reused nodes
  more readily on future queries.
- Symbols the new code *defines* whose name already exists elsewhere are
  reported as **possible duplication** (surfaced, not yet acted on).

It's **language-agnostic** by construction — it operates on graph nodes and
identifier tokens, never on source syntax, and normalizes labels (so a graph
label like `login_endpoint()` matches the bare `login_endpoint` token in code).
A **pure side effect**: it never triggers a build (only the cheap graph load),
fails open, and emits nothing to the agent. Off-switch:
`NEURALMIND_REUSE_FEEDBACK=0`.

### 2. The relevance signal, on the wire

Every retrieved node already carries three relevance signals — a vector
similarity **score**, a learned **synapse boost**, and a **recall flag**. The
ranked context *string* renders these as prose ("score: 0.87 (+0.15 synapse)
[recalled]"), which is fine for the model but opaque to a tool. v0.41.0 exposes
them as a **structured, parseable sidecar** keyed by source file — built from
the **post-boost** L3 hits, so it reports the same `synapse_boost` / `recalled`
signals (and any recall-swapped-in nodes) the visible context used:

```json
{
  "relevance": {
    "version": 1,
    "files": {
      "auth/handlers.py": {
        "max_score": 1.02,
        "nodes": [
          {"node_id": "…", "label": "authenticate", "score": 0.87,
           "synapse_boost": 0.15, "recalled": true, "lines": [42, 68]}
        ]
      }
    }
  }
}
```

A downstream compression proxy can read this and **protect the load-bearing
spans** instead of compressing them away. Because the signal travels *alongside*
the payload as versioned, stably-keyed metadata, a tool running **after**
NeuralMind can re-associate it regardless of pipeline order — the sidecar is
order-independent by design.

## What the agent actually sees post-install

- **Nothing changes in default retrieval.** The `relevance` block is attached
  only when a caller passes `include_relevance` (MCP) or `--relevance` (CLI);
  default `neuralmind_query` responses are unchanged.
- After `neuralmind install-hooks` (or an upgrade — the hook version bumped, so
  the managed block is rewritten), **Edit and Write now register a PostToolUse
  hook**. The agent sees no extra output from it; it strengthens learned
  associations in the background.
- Over a few sessions, queries start surfacing the helpers and modules the agent
  has actually been **reusing**, not just the ones that score well semantically.

## Per-agent expectations

| Agent | What changes in v0.41.0 |
|-------|--------------------------|
| **Claude Code** | `install-hooks` adds `Edit`/`Write` PostToolUse matchers feeding reuse-vs-rewrite back into the synapse store. Re-run `neuralmind install-hooks` (or just start a session — the version bump rewrites the managed block). Disable with `NEURALMIND_REUSE_FEEDBACK=0`. |
| **Cursor / Cline / generic MCP** | Call `neuralmind_query` with `include_relevance: true` to get the structured `relevance` sidecar alongside the context. No change unless you opt in. |
| **A coordinating / compression layer (e.g. Headroom)** | Consume the `relevance.files[].nodes[]` block — `score`, `synapse_boost`, `recalled`, `lines` — to decide which spans are load-bearing and must survive compression. The `version` field guards the wire shape. |

## New surfaces

- **CLI:** `neuralmind query <q> --relevance --json` attaches the sidecar.
- **MCP:** `neuralmind_query` gains an optional `include_relevance` boolean.
- **Hook:** `neuralmind _hook edit-activity` (registered automatically by
  `install-hooks`).
- **Env var:** `NEURALMIND_REUSE_FEEDBACK` (default `1`; set `0` to disable the
  feedback loop).

## What ships

- **`neuralmind/relevance.py`** — `build_relevance_sidecar()`, the single shared
  builder consumed by the MCP and CLI surfaces.
- **`neuralmind/core.py`** — `NeuralMind.record_edit_activity()`, the
  language-agnostic reuse detector (cached, normalized symbol index; no build in
  the hot path) that reinforces synapse edges via the existing `activate` path.
- **`neuralmind/context_selector.py`** — `top_search_hits` now carries the
  post-boost L3 hits so the sidecar reflects the live synapse signals.
- **`neuralmind/hooks.py`** — the `edit-activity` runtime branch + `Edit`/`Write`
  matchers in the managed hook block (hook version bumped).
- **`neuralmind/mcp_server.py`**, **`neuralmind/cli.py`** — the `include_relevance`
  / `--relevance` surfaces.
- Tests: `tests/test_relevance.py`, `tests/test_reuse_feedback.py`, plus
  coverage in `tests/test_hooks.py` / `tests/test_mcp_server.py` /
  `tests/test_cli.py`.

## Honestly out of scope (disclosed, not hidden)

- **Reuse detection is heuristic** — identifier-token cross-reference against
  normalized graph labels, not full static resolution. False positives are
  possible, but the signal is a *soft* Hebbian weight that decays, so they wash
  out; tune or disable via `NEURALMIND_REUSE_FEEDBACK`.
- **Possible-duplication is reported, not penalized** — the rewrite/duplication
  side is surfaced in the return value but does not yet adjust weights.
- **The sidecar is a contract, not a guarantee** — NeuralMind *emits* the
  relevance signal; a downstream tool still has to *consume* it to realize the
  benefit. This release makes NeuralMind's half of that contract real and
  documents the wire format.

## Upgrade

```bash
pip install --upgrade neuralmind
neuralmind install-hooks    # picks up the new Edit/Write matchers
```

No migration. Default retrieval is unchanged; the new behavior is opt-in.
