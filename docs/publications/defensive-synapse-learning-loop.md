# Hebbian Co-Activation with Long-Term Potentiation and Hub-Normalized Spreading Activation: A Learning Loop for Local-First Code Intelligence

**Author:** Darren Frost (dfrostar)
**Date:** 2026-08-06
**Repo:** https://github.com/dfrostar/neuralmind (commit `4256418`)

---

## Abstract

A method for learning and recalling associations between code entities from ambient developer activity, wherein file edits occurring in close temporal proximity are coalesced into co-activation batches that strengthen weighted edges between the touched entities (Hebbian reinforcement), wherein edge weights undergo wall-clock exponential half-life decay with per-namespace and per-edge learned rates, wherein frequently reinforced edges acquire long-term potentiation (a decay floor and prune immunity), and wherein recall is performed by hub-normalized spreading activation over the merged multi-namespace graph. The loop runs entirely locally over a SQLite store, requires no telemetry or central service, and supplies an AI coding agent with associative context the static call graph cannot express.

---

## Background

AI coding agents retrieve context by embedding similarity or static program analysis (call graphs, import graphs). Both miss the associations that only usage reveals:

- **Embedding retrieval** surfaces textually similar code, not code that *changes together* — a config file and the handler that consumes it share no vocabulary.
- **Static graphs** capture declared relations (calls, imports) but not workflow relations — the test fixture you always edit alongside a parser, the migration that accompanies a model change.
- **Mining version histories** (co-change analysis of commits) captures coupled changes only at commit granularity, offline, and without decay — stale couplings persist forever.

Our approach observes the working session itself: edits within a debounce window co-activate; co-activation strengthens edges; disuse decays them; habitual pairs become durable via long-term potentiation; and recall spreads activation outward from query-relevant seed nodes across the learned graph.

---

## Core Algorithm

### 1. Co-Activation Capture

A file-activity watcher coalesces filesystem edits into batches. Edits arriving within a debounce window (default **0.75 s**) of one another are grouped; a batch is flushed when the window goes quiet and delivered as a single co-activation event over the entities in the touched files. Generated artifacts (build output, type declarations) are excluded to prevent phantom edges. File deletions bypass the debounce entirely and trigger *targeted accelerated decay* on the dead file's edges — stale memory pointing at refactored-away code is worse than no memory.

Explicit signals (agent queries, tool calls, hook events) feed the same reinforcement path with a caller-supplied strength.

### 2. Hebbian Reinforcement

For a co-activation batch of nodes `{n₁ … nₖ}`, every unordered pair receives a weight bump:

```
Δw = LEARNING_RATE × clamp(strength, 0, 2)      # LEARNING_RATE = 0.30
w  ← min(WEIGHT_CAP, w + Δw)                    # WEIGHT_CAP = 1.0
```

Edges are stored canonically (`node_a < node_b`) in the active *namespace* (see §5). Each node's activation counter increments in the **same transaction** as the edge upserts — a partial commit would leave counters ahead of their edges and permanently skew LTP gating (§4).

A separate **directed transition** signal records sequential order ("A was active, then B"): learning rate 1.0, cap 100, prune threshold 0.5. Transitions power next-action prediction and decay under the same policy as undirected edges but more slowly by construction (higher cap, coarser prune).

### 3. Wall-Clock Half-Life Decay

Weights decay by elapsed time since last activation — not by how many times a decay pass runs:

```
w(t) = w₀ · exp(−λ · age_days),   λ = ln 2 / H
```

where `H` is the half-life in days, resolved per namespace: **30 d** (personal, branch-scoped, custom), **60 d** (shared team baseline — sticky), **1 d** (ephemeral session scratch). A per-edge *learned* half-life, adapted from the edge's own reinforcement history, overrides the namespace default when present. Edges whose weight falls below the prune threshold (**0.01**) are deleted. Because age derives from the stored `last_activated` timestamp, replaying decay passes is idempotent: a 60-day-old edge has exactly half the weight of a 30-day-old edge with the same history, regardless of pass frequency.

### 4. Long-Term Potentiation (LTP)

Edges reinforced at least **LTP_THRESHOLD = 5** times acquire durability:

- decay is floored at **LTP_FLOOR = 0.20** — the edge can weaken but never vanish by disuse alone;
- pruning skips LTP edges.

The ephemeral namespace is exempt (session scratch must die). LTP balances plasticity against stability: one-off coincidences fade completely, while habitual associations survive vacations.

### 5. Namespaced Storage with Merged Read

Edges live in isolated namespaces: `personal` (long-term priors), `branch:<name>` (feature-branch context), `shared` (imported team baseline), `ephemeral` (session scratch). The default read merges the active namespace with `personal` and `shared`, scaling each by a fixed multiplier and summing per edge:

```
merged_weight = 1.0·w_active + 0.8·w_personal + 0.5·w_shared
```

Recent branch-local context always wins; the imported team baseline is never louder than the developer's own memory.

### 6. Hub-Normalized Spreading Activation (Recall)

Recall seeds the graph with query-relevant nodes carrying energy (default 1.0) and propagates outward for `depth` hops (default **2**):

```
for each frontier node with energy e:
    merge neighbor edge weights across namespaces (§5)
    hub_factor = sqrt(HUB_DEGREE / degree) if degree > HUB_DEGREE else 1.0     # HUB_DEGREE = 50
    propagated(neighbor) = e × merged_weight × SPREAD_DECAY × hub_factor       # SPREAD_DECAY = 0.6
```

Energies accumulate additively across paths; seeds are excluded from results; the top-K nodes by accumulated activation (default **12**) become recall output. The `sqrt(HUB_DEGREE/degree)` term suppresses runaway central nodes — a utility module touched by everything would otherwise dominate every recall. An attribution variant tracks per-namespace energy shares, explaining exactly which namespace's edges produced each recalled node.

---

## Properties

### Stability–Plasticity Balance

New associations form after a single co-activation (Δw = 0.30 is immediately recallable) yet vanish within weeks if never repeated (30-day half-life, prune at 0.01). Habitual associations (≥5 reinforcements) are permanent-but-quiet at worst (floor 0.20). The system neither fossilizes nor forgets everything.

### Bounded and Convergent

Weights are capped at 1.0, so repeated reinforcement saturates rather than explodes. Hub normalization bounds per-hop amplification: for degree d > 50, total propagated energy grows as √d rather than d. With SPREAD_DECAY = 0.6 and depth 2, activation strictly attenuates with distance.

### Deterministic Decay

Decay is a pure function of wall-clock age — running the pass hourly or weekly yields identical weights for identical timestamps. This survives laptops that sleep, CI that runs sporadically, and clones that sit idle.

### Complexity

- **Reinforcement:** O(k²) pairs for a k-file batch (k is small — a debounce window of human editing), executed as two batched statements in one transaction.
- **Decay:** O(edges) via set-based SQL UPDATEs, chunked per namespace.
- **Spread:** O(frontier × avg-degree) per hop, depth-bounded at 2 by default.

---

## Reference Implementation

- **Language:** Python 3.10+ (stdlib-only for the synapse layer)
- **Repo:** https://github.com/dfrostar/neuralmind
- **Commit:** `4256418` (2026-08-06)
- **Files:**
  - `neuralmind/synapses.py` — `SynapseStore.reinforce()`, `SynapseStore.decay()`, `SynapseStore._spread()`, `SynapseStore.record_sequence()`, namespace merge weighting
  - `neuralmind/watcher.py` — `FileActivityWatcher` debounced co-activation batching, deletion-triggered targeted decay
  - `neuralmind/learned_decay.py` — per-edge learned half-life adaptation
  - `tests/test_synapses.py`, `tests/test_synapse_namespaces.py`, `tests/test_watcher.py`, `tests/test_learned_decay.py` — unit coverage of every mechanism above

---

## Prior Art Statement

To the best of our knowledge, the specific combination of:

1. Debounce-windowed filesystem co-activation as the reinforcement signal (ambient, no explicit feedback)
2. Hebbian pairwise strengthening with a hard weight cap and transactional activation counting
3. Wall-clock exponential half-life decay with per-namespace policy and per-edge learned overrides
4. Activation-count-gated long-term potentiation (decay floor + prune immunity)
5. Hub-normalized (√-degree) spreading activation over a multiplier-merged multi-namespace graph
6. Deletion-triggered targeted decay for refactored-away entities

— applied to context retrieval for AI coding agents in a local-first, telemetry-free system, has not been previously published. Related work includes:

- **Hebbian learning** (Hebb, 1949) — the co-activation principle, without decay policy, LTP gating, or code-entity application
- **Long-term potentiation** (Bliss & Lømo, 1973) — biological analogue of the durability mechanism
- **Spreading activation** (Collins & Loftus, 1975) — semantic-network recall, without hub normalization or namespace merging
- **ACT-R declarative memory** (Anderson & Lebiere, 1998) — base-level activation with time decay, applied to cognitive modeling rather than code graphs learned from editor activity
- **Mining version histories** (Zimmermann et al., 2004) — co-change coupling at commit granularity, offline, without decay or recall-time spread

---

*This publication establishes prior art for the techniques described herein. It is provided for defensive purposes and as technical documentation for the NeuralMind open-source project.*
