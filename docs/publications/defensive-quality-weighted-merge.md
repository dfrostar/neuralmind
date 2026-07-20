# Quality-Weighted Merge with Conflict-Driven Decay: A Method for Forcing Convergence in Distributed Edge-Weight Graphs

**Author:** Darren Frost (dfrostar)  
**Date:** 2026-07-22  
**Repo:** https://github.com/dfrostar/neuralmind (commit `3fe5a61`)

---

## Abstract

A method for resolving conflicting assertions in a distributed edge-weight graph, wherein each edge carries a quality score computed from reinforcement frequency, recency of activation, and historical conflict rate, and wherein the loser of a conflict undergoes multiplicative decay proportional to its conflict rate, forcing the graph toward consensus without central coordination. The algorithm is local-first, stdlib-only, and operates over a committed JSON bundle that propagates through version control.

---

## Background

Existing distributed knowledge graphs (Google Knowledge Graph, Wikidata, enterprise graph databases) rely on central curation or voting mechanisms to resolve conflicting assertions. These approaches fail in local-first, edge-compute scenarios:

- **Last-write-wins** (default Git merge): discards contributor quality signal, rewards recency over accuracy.
- **MAX-merge** (naive synaptic import): allows a single over-eager contributor to permanently distort shared recall.
- **Consensus voting** (Raft/Paxos): requires online coordination — unusable in disconnected, git-clone-and-fork workflows.

Our approach: each edge carries its own quality signal, and conflict resolution is purely local — no coordinator, no quorum, no round-trips. The loser of each conflict decays, and chronic losers decay faster, so the system converges to the highest-quality assertions without any node having global authority.

---

## Core Algorithm

### 1. Edge Quality Scoring

Each edge `e` in namespace `ns` is scored by a composite quality function:

```
score(e) = w_r × reinforcement(e) + w_t × recency(e) - w_c × conflict_rate(e)
```

where:

- `reinforcement(e) = log1p(activation_count) / log1p(30)` — saturates at ~1.0 after 30 activations
- `recency(e) = exp(-0.693 × days_since_last_activation / 30.0)` — 30-day half-life
- `conflict_rate(e) = conflict_count / max(1, total_comparisons)` — [0.0, 1.0]

Default weights: `w_r = 0.4`, `w_t = 0.35`, `w_c = 0.25`. Theoretical maximum is 0.75 (achievable when `activation_count ≥ 30` and edge was just activated). In practice, most edges score below 0.70.

Classification bands:

| Score | Action |
|-------|--------|
| ≥ 0.70 | Auto-promote to `shared` namespace |
| [0.30, 0.70) | Retain as neutral (survives import, but doesn't win conflicts against ≥0.70 edges) |
| < 0.30 | Reject (excluded from `shared`) |

**Peer review:** Edges in the [0.30, 0.70) range are evaluated by `PeerReviewGate` (E3) — a secondary gating mechanism that can auto-promote, reject, or queue for operator review based on additional heuristics. This is a separate concern from the scoring classifier.

### 2. Conflict Resolution

When two bundles contain edges for the same `(source, target)` pair:

```
resolve(existing, incoming):
    if |existing.score - incoming.score| < 0.05 AND max(existing.score, incoming.score) < 0.30:
        return CONTEST  → escalate to review
    else:
        winner = argmax(existing.score, incoming.score)
        loser  = min(existing.score, incoming.score)
        decay(loser, conflict_rate=loser.conflict_rate)
        return winner
```

### 3. Decay-on-Conflict

The loser's weight is multiplicatively degraded:

```
decay_weight(loser):
    adjusted = max(0.1, 0.5 - loser.conflict_rate × 0.3)
    return max(0.01, loser.score × adjusted)
```

Properties:

- **Range:** [0.01, 0.5 × score] (floor at 0.01, ceiling at half the score)
- **Conflict-rate sensitivity:** A loser with `conflict_rate=0` decays to 0.5×. A loser with `conflict_rate=1.0` decays to 0.2×. Chronic losers fade faster.
- **Total ordering:** Since `adjusted` is monotonic decreasing in `conflict_rate`, and `loser.score` is fixed at conflict time, total ordering is preserved.

### 4. Namespace-Specific Staleness

Edges inactive past a namespace-specific threshold undergo accelerated decay:

| Namespace | Stale after | Decay factor per pass |
|-----------|-------------|----------------------|
| `shared`  | 30 days     | `2^(-5/30) ≈ 0.891` (5× normal) |
| `branch:*`| 14 days     | `2^(-5/14) ≈ 0.787` (faster)     |
| `personal`| 60 days     | `2^(-5/60) ≈ 0.943` (slower)     |

Fast decay is applied as a **constant per-pass factor** (not a cumulative formula):

```
decay_factor = 2^(-fast_decay / half_life)
            = 2^(-5 / 30)
            ≈ 0.891 per pass
```

After 30 daily passes: `0.891^30 = 2^(-5) = 1/32` — exactly 5x normal decay, no compounding explosion.

> **Note:** A naive cumulative formula `2^(-fast_decay × days_past / half_life)` compounds multiplicatively across passes and would zero edges in ~5 days. The constant per-pass factor avoids this.

---

## Example Walkthrough

Two contributors, Alice and Bob, publish bundles containing overlapping edges.

**Alice's bundle:**
```
(source="auth/jwt.py", target="auth/handlers.py", weight=8.0,
 activation_count=40, created_at=now, last_activated=now,
 conflicts=0, comparisons=1)
```
Score: `0.4×0.983 + 0.35×1.0 - 0.25×0.0 = 0.743` (reinforcement = ln(41)/ln(31) ≈ 0.983)

**Bob's bundle:**
```
(source="auth/jwt.py", target="auth/handlers.py", weight=2.0,
 activation_count=3, created_at=now, last_activated=now,
 conflicts=1, comparisons=2)
```
Score: `0.4×0.404 + 0.35×1.0 - 0.25×0.5 = 0.162 + 0.35 - 0.125 = 0.387`

**Conflict resolution:**
- Difference: `0.743 - 0.387 = 0.356` (> 0.05, no contest)
- Winner: Alice's edge (score 0.743)
- Bob's edge is excluded from the `shared` namespace (the loser is dropped, not decayed).

---

## Properties

### Convergence

Conflict resolution excludes the loser from the `shared` namespace — the winner survives, the loser is dropped. This forces the graph toward consensus: each conflict eliminates one conflicting assertion, monotonically reducing the set of competing edges. The system converges because `|shared|` is bounded by the total unique `(source, target)` pairs across all bundles, and each conflict removes one candidate from that set.

For stale edges (inactive past the namespace threshold), the `TeamStalenessDetector` applies accelerated decay, reducing their weight by a constant factor of `2^(-5/30) ≈ 0.891` per sleep pass. After 30 daily passes: `0.891³⁰ = 2⁻⁵ = 1/32` — exactly 5× normal decay, with no compounding explosion (the constant per-pass factor avoids the `2^(-5/30 × Σdays)` trap that would zero edges in ~5 days).

### Eventual Consistency

Bundle import is idempotent (tracked by content hash in `meta.team_bundle_imported_hash`). Given the **same set** of bundles, all replicas converge to the same state.

**Order-dependence:** When two bundles contain conflicting edges with equal scores, `merge_bundles` breaks ties by activation count (higher wins). If activation counts are also tied, the first argument wins. This means that importing bundle A then B may produce a different `shared` state than B then A — but only in the tiebreak case. In practice, score ties are rare (continuous-valued scores), so replicas converge to near-identical states.

### Complexity

- **Scoring:** O(|bundle|) — single pass over edges
- **Conflict detection:** O(|A| + |B|) — dict-indexed overlap lookup, not cross-product
- **Decay application:** O(|stale|) — one UPDATE per stale edge per sleep pass

---

## Reference Implementation

- **Language:** Python 3.10+ (stdlib-only, no heavy dependencies)
- **Repo:** https://github.com/dfrostar/neuralmind
- **Commit:** `3fe5a61` (2026-07-22)
- **Files:**
  - `neuralmind/contribution_scoring.py` — `ContributionQualityScorer.score_edge()`, `ContributionQualityScorer.classify_bundle()`
  - `neuralmind/merge_semantics.py` — `QualityWeightedMerger.resolve_conflict()`, `QualityWeightedMerger.merge_bundles()`
  - `neuralmind/team_staleness.py` — `TeamStalenessDetector.run_staleness_pass()`
  - `tests/test_contribution_scoring.py` — 4 unit tests
  - `tests/test_merge_semantics.py` — 11 unit tests
  - `tests/test_team_memory_integration.py` — 10 integration tests

---

## Prior Art Statement

To the best of our knowledge, the specific combination of:

1. Per-edge composite quality scoring (reinforcement × recency - conflict penalty)
2. Conflict-rate-weighted multiplicative loser decay
3. Constant per-pass staleness decay (avoiding compounding explosion)
4. Integration with git-committed bundle propagation

— has not been previously published in the context of local-first code intelligence systems. Related work includes:

- **Hebbian learning** (Hebb, 1949) — general co-activation principle, not edge-weight graphs with conflict resolution
- **Gossip protocols** (Demers et al., 1987) — epidemic broadcast, not quality-weighted convergence
- **Federated learning** (McMahan et al., 2017) — model averaging, not conflict-driven decay
- **Wikidata** (Vrandečić, 2013) — manual curation, not automated convergence

---

*This publication establishes prior art for the techniques described herein. It is provided for defensive purposes and as technical documentation for the NeuralMind open-source project.*
