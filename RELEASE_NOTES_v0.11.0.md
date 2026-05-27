# NeuralMind v0.11.0 — directional synapses

**Release Date:** May 2026

## TL;DR

The synapse layer learns *what comes next*, not just *what goes
together*. The Hebbian co-activation signal that's powered NeuralMind
since v0.4.0 has always been symmetric: nodes that fire together wire
together, no ordering. v0.11.0 adds a parallel directional signal:
after touching A, you typically touch B with probability p. The
existing undirected graph keeps doing its job; the new
`synapse_transitions` table is additive.

- **Directional transitions.** New `synapse_transitions(from_node,
  to_node, weight, count)` table tracks ordered observations. Same
  Hebbian + decay machinery as the undirected synapses, separate
  semantics. Recorded automatically every time the file watcher
  flushes a batch of edits.
- **`next_likely(node)` API.** Returns the probability distribution
  over what typically follows a given file or node. Probabilities
  normalize to 1.0 across all outgoing transitions.
- **`neuralmind next <node>` CLI.** Surface the prediction from the
  shell. Example: `neuralmind next . src/auth/handlers.py` prints the
  files most often edited after that one, ranked by probability.
- **`neuralmind_next_likely` MCP tool.** Same capability via MCP so
  Cursor / Cline / Continue / any MCP client can prefetch context
  the agent is likely to ask about next.
- **Auto-memory surface.** The `SYNAPSE_MEMORY.md` file that Claude
  Code loads on every session start now includes a "What typically
  comes next" section with the top transitions. The directional signal
  is in the agent's context *without anyone asking* — no MCP tool
  call, no CLI invocation, just primed knowledge the model can act on.

No migration. The new table is created on first connection; existing
`synapses.db` files keep working untouched. Disable the new signal by
ignoring the new API — the watcher still records it in the background,
but if nothing reads it, it just sits there decaying like any other
edge.

---

## What the agent actually sees, post-install

Pre-v0.11.0, an agent asking "what's related to `auth/handlers.py`?"
got back the undirected synapse spread — files that have been touched
in the same batch as `handlers.py`, with no sense of which came first.

Post-v0.11.0, the same agent can ask `neuralmind_next_likely` and get:

```json
{
  "from_node": "src/auth/handlers.py",
  "next": [
    {"to_node": "tests/test_auth.py",     "probability": 0.45},
    {"to_node": "src/auth/middleware.py", "probability": 0.28},
    {"to_node": "docs/auth.md",           "probability": 0.12}
  ]
}
```

That's a *directional* recall surface. The agent learns: "when this
human edits `handlers.py`, they edit the test file ~half the time
next." Useful for: prefetching the next file's skeleton into context,
prompting the agent to keep the test file open, surfacing "you usually
touch the docs too — want me to update them?" as a suggestion.

### Per-agent expectations

| Agent | What it sees | What it can do |
|-------|--------------|----------------|
| **Claude Code** | New MCP tool `neuralmind_next_likely` + new CLI `neuralmind next`. The file watcher records transitions automatically; the existing PostToolUse and SessionStart hooks are unchanged. | Call the MCP tool after editing a file to predict what file to open next; pipe `neuralmind next` into a status line. |
| **Cursor / Cline / Continue** | Same `neuralmind_next_likely` tool through the MCP server. The file watcher only runs when `neuralmind watch` is up — see the [always-on guide](docs/use-cases/always-on.md). | Same recall path. Transitions accumulate as long as the watcher is running. |
| **Any other MCP client** | Same MCP tool. The directional signal is also queryable from Python: `mind.synapses.next_likely(node)` returns `[(node, prob), ...]`. | Same. |

---

## Why a directional signal

The existing undirected synapse graph answers *association*: "given
this file, what other files belong to the same thought?" That's a
useful question — it powers the spreading-activation recall behind
`neuralmind_synaptic_neighbors`. But it's symmetric. It can't
distinguish "the test file I touched right before the implementation"
from "the test file I touched right after." Those are different
signals with different uses:

- *Before* → "prefetch this file's skeleton when the implementation file is loaded."
- *After* → "remind the agent to update this when the implementation changes."

Directional transitions split the signal. The transition recorder runs
alongside the existing co-activation recorder — every `activate_files`
call writes to both. Same source data, two views.

### Why not just look at file mtimes

The watcher already uses mtimes to detect when a file was last
touched. What the synapse layer adds is *aggregation across sessions*.
A single edit doesn't mean anything; the watcher sees thousands of
sequences over weeks of work, and transitions with consistent A→B
patterns rise to the top while one-off transitions decay.

The decay rate for transitions is intentionally slower than for
undirected edges (`TRANSITION_DECAY_RATE = 0.01` vs `DECAY_RATE = 0.02`):
sequential signals are rarer per session — you might edit ten files
together but only have nine ordered pairs between them — so they need
to accumulate for longer before being trusted.

---

## API surface

### `SynapseStore.record_sequence(ordered_ids, strength=1.0)`

```python
from neuralmind import SynapseStore, default_db_path

store = SynapseStore(default_db_path("/path/to/repo"))
store.record_sequence([
    "src/auth/handlers.py",
    "tests/test_auth.py",
    "src/auth/middleware.py",
])
# Records: handlers.py -> test_auth.py, test_auth.py -> middleware.py
```

Takes any list of strings. The store doesn't care whether you pass
file paths, node ids, or arbitrary tokens — callers pick the
granularity. The file watcher records at file-path granularity.

### `SynapseStore.next_likely(from_node, top_k=5)`

```python
ranked = store.next_likely("src/auth/handlers.py")
# [("tests/test_auth.py", 0.45), ("src/auth/middleware.py", 0.28), ...]
```

Returns `(to_node, probability)` pairs with probabilities normalized
over all outgoing transitions. Returns an empty list when the node
has no recorded transitions yet.

### `SynapseStore.transitions(from_node=None, min_weight=0.0, limit=2000)`

Raw read-only listing of `(from, to, weight, count)` rows. Strongest
first. Filter by `from_node` for a single source, omit for the full
table. Used by the graph-view UI to overlay directional edges.

### `neuralmind next` CLI

```bash
$ neuralmind next . src/auth/handlers.py
After src/auth/handlers.py:
   45.2%  tests/test_auth.py
   28.4%  src/auth/middleware.py
   12.1%  docs/auth.md
    8.3%  src/auth/__init__.py
    6.0%  src/main.py
```

Pass `--json` for machine-readable output, `--n` to change top-K.

### `neuralmind_next_likely` MCP tool

```json
{
  "name": "neuralmind_next_likely",
  "arguments": {
    "project_path": "/path/to/repo",
    "from_node": "src/auth/handlers.py",
    "top_k": 5
  }
}
```

Same output shape as the CLI, JSON-encoded.

---

## Configuration knobs

All in `neuralmind/synapses.py`. Same shape as the existing
co-activation knobs; tune if you want different sensitivity.

| Constant | Default | Effect |
|----------|---------|--------|
| `TRANSITION_LEARNING_RATE` | `1.0` | Weight added per observed transition. |
| `TRANSITION_WEIGHT_CAP` | `100.0` | Maximum weight (cap to bound runaway accumulators). |
| `TRANSITION_DECAY_RATE` | `0.01` | Multiplicative decay per `decay()` tick. Slower than `DECAY_RATE` for the undirected edges (0.02). |
| `TRANSITION_PRUNE_THRESHOLD` | `0.5` | Transitions with weight below this are pruned during decay. |
| `DEFAULT_NEXT_TOP_K` | `5` | Default top-K for `next_likely`. |

---

## What's not in this release

Each of these would deserve its own ship:

- **Multi-step prediction.** Raise the transition matrix to the
  k-th power for k-hop forecasts. The existing spreading-activation
  recall on the undirected graph already covers most of this need;
  the directional analogue would let you ask "what file will I touch
  in 3 hops?"
- **Regime detection via HMM.** Hidden-state inference over the
  transition stream could discover "modes" (debugging vs feature-add
  vs refactor) without labels, then condition L0/L1/L2/L3 context
  selection on inferred mode. Speculative but interesting.

---

## Upgrade

```bash
pip install --upgrade neuralmind
# or
pipx upgrade neuralmind
# or
uv pip install --upgrade neuralmind
# or
docker pull ghcr.io/dfrostar/neuralmind:latest
```

No graph rebuild needed. No synapse-store migration — the new table
is created on first connection. Existing co-activation edges in
`synapses.db` are untouched. The directional table populates from
fresh watcher activity post-upgrade; older sessions can't be
retroactively turned into transitions because the temporal ordering
wasn't preserved at write time.
