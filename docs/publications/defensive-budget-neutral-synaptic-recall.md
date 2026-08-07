# Budget-Neutral Synaptic Recall: Hub-Normalized Spreading Activation with Learned Per-Edge Decay for AI Agent Context Retrieval

**Author:** Darren Frost (dfrostar)
**Date:** 2026-08-07
**Repo:** https://github.com/dfrostar/neuralmind (implementation as of commit `89eff6c`)

---

## Abstract

A method for injecting learned associative recall into an AI coding agent's context window without increasing its token cost. Code nodes co-activated by agent tool activity are linked by Hebbian reinforcement into a weighted undirected graph. Each edge decays along an exponential half-life that is itself learned per edge from reinforcement frequency and recency, bounded by tuner-owned limits. At retrieval time, spreading activation propagates energy outward from the top vector-search hits across namespace-merged edge weights, with square-root hub normalization preventing high-degree utility nodes from dominating recall. The resulting activation energies are folded into the vector result set budget-neutrally: nodes already present are boosted and re-ranked, and the weakest vector hits are *displaced* by strongly co-activated neighbors that vector search missed — the result count, and therefore the token budget, never grows. When the graph is cold, output is byte-identical to a build without the associative layer. The method is local-first and stdlib-only.

---

## Background

Retrieval for AI coding agents is dominated by flat top-k vector search (RAG). This fails in a specific, recurring way: the files an agent *actually uses together* are often lexically and semantically unrelated — a JWT verifier and the key-loading helper it depends on share no vocabulary — so vector search never co-surfaces them, and the agent re-discovers the association by trial and error in every session. Existing remedies each have a structural flaw in the agent setting:

- **Growing the context** (append related files): every added node costs tokens; associative recall that grows the prompt competes with the very budget it is meant to protect.
- **Static code graphs** (call/import edges): capture compile-time structure but not usage — test fixtures, config files, and docs co-used with code are invisible to them.
- **Fixed-rate memory decay** (uniform forgetting curve): treats a load-bearing association reinforced daily the same as a one-off co-occurrence, so either hot edges fade too fast or noise lingers too long.
- **Naive spreading activation**: without degree normalization, one high-degree utility node (a logger, a base class) floods every recall with itself and its neighbors.

Our approach learns associations from the agent's own tool telemetry, forgets them at a per-edge learned rate, recalls them by hub-normalized spreading activation, and injects them by *displacement* rather than *addition* — so recall quality improves while the token budget stays fixed.

---

## Core Algorithm

### 1. Hebbian Co-Activation Reinforcement

Agent activity events (file reads, edits, tool calls within an activity window) yield a set of co-activated node ids. Every pairwise combination is reinforced as an undirected edge stored under canonical ordering (`node_a < node_b`); self-pairs and duplicates are ignored:

```
reinforce(node_ids, strength):
    Δw = LEARNING_RATE × clamp(strength, 0.0, 2.0)
    for each canonical pair (a, b) in node_ids:
        weight(a,b) = min(WEIGHT_CAP, weight(a,b) + Δw)
        activation_count(a,b) += 1
```

with `LEARNING_RATE = 0.30` and `WEIGHT_CAP = 1.0`. Edge upserts and per-node activation counters commit in one transaction — a partial commit would leave counters ahead of the edges they belong to, permanently skewing long-term-potentiation gating (§2).

### 2. Learned Per-Edge Half-Life Decay

Weights decay by wall-clock exponential half-life, not by tick:

```
w(t) = w₀ × exp(−λ × age_days),   λ = ln(2) / half_life_days
```

Namespace defaults: `personal`/`branch:*` 30 days, `shared` 60 days (sticky team baseline), `ephemeral` 1 day. The half-life is then **learned per edge** from reinforcement history, recomputed inside the same transaction as each reinforcement:

```
freq               = activation_count / age_days
recency_confidence = exp(−ln(2) × days_since_last / ns_default)
ratio              = log1p(freq × age_days / 10)        # ≡ log1p(activation_count / 10)
learned            = lo + (hi − lo) × ratio / (1 + ratio)
half_life          = (1 − recency_confidence) × ns_default + recency_confidence × learned
```

bounded to `[lo, hi] = [3.0, 120.0]` days (tuner-owned bounds): a rarely-used edge never decays slower than 3 days of half-life, a heavily-used one never faster than 120. Edges younger than 1 day fall back to the namespace default; `shared` edges are floored at their namespace default so the team baseline never decays faster than promised.

**Long-term potentiation:** edges whose lifetime `activation_count ≥ 5` (`LTP_THRESHOLD`) are floored at weight `0.20` (`LTP_FLOOR`) during decay — proven associations can fade but never vanish. `ephemeral` has no LTP exemption. Weights below `0.01` (`PRUNE_THRESHOLD`) are deleted.

### 3. Hub-Normalized Spreading Activation over Namespace-Merged Weights

Recall seeds energy at query-relevant nodes and propagates it outward for `depth = 2` hops. Edge weights merge across memory namespaces with fixed multipliers before propagation:

```
merged_weight(a,b) = Σ_ns  w_ns(a,b) × M_ns
    M_active = 1.0    (current branch's working memory wins)
    M_personal = 0.8  (long-term priors, slightly behind)
    M_shared = 0.5    (imported team baseline, never louder than your own)
```

Propagation per hop, per neighbor:

```
hub_factor(n) = sqrt(HUB_DEGREE / degree(n))  if degree(n) > HUB_DEGREE else 1.0
propagated    = energy(n) × merged_weight × SPREAD_DECAY × hub_factor(n)
```

with `SPREAD_DECAY = 0.6` and `HUB_DEGREE = 50`. The square-root form is deliberate: a linear `HUB_DEGREE / degree` penalty would mute hubs so hard they stop routing energy at all; `sqrt` keeps them useful as conduits while preventing dominance (a degree-200 node propagates at exactly 0.5×). Accumulated activation is ranked, seeds are excluded, and the top `12` nodes are returned with their energies.

### 4. Budget-Neutral Injection: Boost + Displacement

The activation energies fold into the vector-search result list under a hard invariant — **the result count never grows**:

```
inject(results, energy):
    seeds = top SEED_K results                     # SEED_K = 3
    (a) BOOST: for each result r already in the list with energy[r] > 0:
            r.score += BOOST_WEIGHT × energy[r]    # BOOST_WEIGHT = 0.3
        re-sort results by score
    (b) DISPLACE: candidates = absent nodes with energy ≥ MIN_ENERGY,   # 0.15
                  strongest first, at most PULL_IN_MAX                  # 2
        swap them in for the weakest vector hits, one-for-one,
        always keeping ≥ 1 original vector hit
```

Because injection is one-for-one displacement, the context assembled downstream (progressive disclosure layers L0–L3) spends exactly the same token budget with or without the associative layer. When recall is unwired, killed by env switch (`NEURALMIND_SYNAPSE_INJECT=0`), or the graph is cold, the output is byte-identical to a build without a synapse store — cold-start safety is a hard guarantee, not a tendency. Injection operates on shallow copies of cached result rows so repeated calls are idempotent.

---

## Example Walkthrough

An agent asks about authentication. Vector search returns 8 hits; the top 3 seed spreading activation with energy 1.0: `auth/jwt.py::verify_token`, `auth/handlers.py::login`, `auth/models.py::User`.

**Hop 1 from `verify_token`:**

```
edge → config/secrets.py::load_keys
  personal weight 0.9 × M_active 1.0 = 0.9 merged
  degree(verify_token) = 6 ≤ 50 → hub_factor 1.0
  propagated = 1.0 × 0.9 × 0.6 × 1.0 = 0.54
```

`load_keys` shares no vocabulary with "authentication" — vector search missed it — but the agent has opened it alongside `verify_token` in session after session, so the learned edge is strong. Energy 0.54 ≥ 0.15 → displacement candidate.

**Hop 1 from `login`:**

```
edge → middleware/session.py::refresh
  shared weight 0.5 × M_shared 0.5 = 0.25 merged
  propagated = 1.0 × 0.25 × 0.6 × 1.0 = 0.15
```

`refresh` is already in the result list at position 7 → boosted by `0.3 × 0.15 = 0.045` and re-ranked upward.

**Injection:** 8 hits in, 8 hits out. `load_keys` displaces the weakest vector hit (a docstring stub that matched on the word "auth"); `refresh` moves up. The context now contains the file the agent would otherwise have found by trial and error — at zero additional token cost.

**Decay over time:** the `verify_token ↔ load_keys` edge, activated 40 times over 20 days and used today, earns a learned half-life of `3 + 117 × (ln(5)/(1+ln(5))) ≈ 75` days at full recency confidence. A noise edge activated twice in 30 days and untouched for 25 blends to `≈ 25` days and, having only 2 lifetime activations, carries no LTP floor — it decays to pruning.

---

## Properties

### Budget Neutrality

Injection is one-for-one displacement with a fixed result count, so total context tokens are invariant to the associative layer. Recall quality and token cost are decoupled: the graph learning more never makes the prompt bigger.

### Cold-Start Identity

Every stage no-ops to the identity function when its input signal is absent (no store wired, kill switch set, zero energy returned). A fresh clone produces byte-identical retrievals to a build without the layer; the graph earns influence only through observed usage.

### Hub Resistance

With `hub_factor = sqrt(50/degree)`, a degree-5000 god-node propagates at 0.1× while a degree-50 node propagates at 1.0×. Utility nodes remain traversable conduits but cannot flood the top-k.

### Stability of Learned Decay

The learned half-life is bounded (`[3, 120]` days), monotonic and saturating in reinforcement (`ratio/(1+ratio)` form), and blended toward the namespace default as recency confidence fades — a stale edge's learned rate reverts rather than compounds. LTP-floored edges cannot be pruned by decay alone.

### Complexity

- **Reinforcement:** O(k²) edge upserts for a k-node activity window (k is small; windows are per-tool-call), batched in one transaction
- **Spread:** O(E_frontier) per hop with dict-indexed neighbor merge, depth fixed at 2
- **Injection:** O(n log n) for the re-sort of n results; displacement is O(PULL_IN_MAX)

---

## Reference Implementation

- **Language:** Python 3.10+ (stdlib-only synapse layer; SQLite storage)
- **Repo:** https://github.com/dfrostar/neuralmind
- **Commit:** `89eff6c` (2026-08-07)
- **Files:**
  - `neuralmind/synapses.py` — `SynapseStore.reinforce()`, `SynapseStore.decay()`, `SynapseStore._spread()`
  - `neuralmind/learned_decay.py` — `compute_edge_half_life()`, `update_learned_half_life()`
  - `neuralmind/context_selector.py` — `ContextSelector._apply_synapse_boost()`
  - `neuralmind/watcher.py` — file activity → co-activation windows
  - `tests/test_synapses.py` — 56 unit tests
  - `tests/test_learned_decay.py` — 14 unit tests
  - `tests/test_context_selector.py` — 68 unit tests

---

## Prior Art Statement

To the best of our knowledge, the specific combination of:

1. Hebbian edge learning driven by AI-agent tool telemetry (not user clicks, not document co-citation)
2. Per-edge learned exponential half-life, blended by recency confidence toward a namespace default and bounded by tuner-owned limits
3. Square-root hub-normalized spreading activation over namespace-merged edge weights
4. Budget-neutral injection into a fixed retrieval budget via score boost plus one-for-one displacement, with a byte-identical cold-start guarantee

— has not been previously published in the context of local-first code intelligence systems. Related work includes:

- **Hebbian learning** (Hebb, 1949) — the co-activation principle, without decay learning or budgeted retrieval
- **Spreading activation in semantic memory** (Collins & Loftus, 1975; Anderson's ACT-R, 1983) — cognitive models; no hub normalization for code graphs, no token budgets
- **Spreading activation in information retrieval** (Crestani, 1997) — survey of IR applications; result sets grow with activation rather than displacing
- **Forgetting curves** (Ebbinghaus, 1885) — fixed-rate exponential forgetting, not per-edge learned rates
- **Retrieval-augmented generation** (Lewis et al., 2020) — flat top-k vector retrieval, no learned associative layer
- **LLM memory hierarchies** (MemGPT, Packer et al., 2023) — model-managed context paging, not graph-learned recall with budget-neutral injection

---

*This publication establishes prior art for the techniques described herein. It is provided for defensive purposes and as technical documentation for the NeuralMind open-source project.*
