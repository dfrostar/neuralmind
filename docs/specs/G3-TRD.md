# G3 — Modularity Clustering, Technical Requirements Document (TRD)

**Date:** 2026-07-23
**Module:** `neuralmind/modularity.py` + `neuralmind/graphgen.py`
**Spec type:** Feature technical spec
**Commit:** `f49b535`
**Claim tier:** B

---

## 1. Scope

Replace `graphgen.py:_assign_communities` balanced-per-file grouping with Louvain modularity clustering over structural code dependency edges. Implementation in `neuralmind/modularity.py` is pure Python (stdlib-only, no external deps).

Cross-references:
- WAVE4-TRD §2.4 (graph precision — G3 placeholder)
- `docs/research/f4-g3-research-backlog.md` — full research backing

---

## 2. Architecture

```
build_graph(project_path):
  ↓
  _GraphBuilder + IncrementalExtractor
  ↓ (unchanged) — two-pass extraction per file
  ↓
_communities (NEW — replaces per-file grouping)
  ↓
  _assign_communities(b, existing_graph):
    1. Build per-file adjacency from b.edges (calls/imports_from/inherits/contains)
    2. weights = confidence_score per edge
    3. Call louvain_clustering(adj, resolution=1.0)
    4. Carry over community IDs from existing_graph (source_file → community)
    5. If Louvain collapses to ≤1 community → fall back to per-file grouping
    6. New-file IDs: next_comm = max(carried) + 1
    7. Write n["community"] = comm_of_file[n["source_file"]]
```

### Algorithm: Louvain Phase 1 (O(n·k))

```
Input:  adj: {src: {tgt: weight}}      # undirected, sparse
Init:   each node in own community
        community_weights[c] = Σ_{n ∈ c} Σ_{tgt} weight(n, tgt)
        node_degree[n] = Σ_{tgt} weight(n, tgt)
        total_weight = Σ_c community_weights[c] / 2

Repeat until convergence or max_iterations:
  For each node (sorted order):
    For each neighbor community c of node:
      Compute ΔQ = gain(node→c) - loss(node→→current_community)
        gain  = (w_to_c - γ·σ_c·k_i / (2m)) / m
        loss  = (w_to_cur - γ·(σ_cur - k_i)·k_i / (2m)) / m
    If best_gain > 0:
      Move node to best_community
      Update community_weights[current_c] -= k_i
      Update community_weights[best_c] += k_i

Phase 2 (single collapse pass):
  For each community c, create super-node c'
  Intra-community edges → self-loop on c' (preserves total_weight)
  Inter-community edges → edges between super-nodes (weighted)
  Recurse: louvain_clustering(coarse_adj)
  Map coarse result back to original nodes
```

Key invariants:
- ΔQ formula includes `γ` (resolution). Default γ=1.0 → standard modularity.
- `community_weights[c]` tracks Σ of node degrees in community c.
- When node moves out: `community_weights[c_old] -= k_i`.
- When node moves in: community_weights[c_new] += k_i.
- Phase 2 self-loop: intra-community edges become self-loops to preserve total_weight.

---

## 3. API

```python
def louvain_clustering(
    adj: dict[str, dict[str, float]],
    *,
    resolution: float = 1.0,
    max_iterations: int = 10,
) -> dict[str, int]:
    """Returns contiguous-integer community IDs."""

def detect_structural_communities(
    graph: dict[str, Any],
    *,
    min_edge_weight: float = 0.0,
) -> dict[str, int]:
    """Consumes graphify-compatible dict. Fail-open on parse error."""
```

`adj` must be undirected (both directions populated). Callers (`_assign_communities`) build adjacency from graph edges.

---

## 4. Community ID Stability on Incremental Builds

`_assign_communities(b, existing_graph)` carries community IDs from `existing_graph`:
1. `comm_of_file = {n["source_file"]: n["community"] for n in existing_graph["nodes"] if sf exists}`
2. After Louvain, renumber: new-file IDs start at `max(comm_of_file.values(), default=-1) + 1`
3. Output: contiguous integers starting at 0 (sorted by source_file for determinism)

**Guarantee:** If `existing_graph` has 5 files with communities {0..4}, and one new file arrives, new file gets community 5. Existing communities are byte-for-byte preserved.

**Open question:** If a file is renamed (old deleted + new added), the community ID is not carried over. Acceptable for v1 (rename = semantic change).

---

## 5. Correctness Properties

| Property | Proof |
|----------|-------|
| Determinism | Sorted iteration order; no hash/random; deterministic tiebreak (first-seen wins since gain > best_gain is strict) |
| O(n·k) complexity | Each pass: n nodes × O(k) neighbor communities per node. Sorted outer loop doesn't affect complexity. |
| Phase 2 preserves total_weight | Self-loop: intra-community edges summed as self-loop weight; inter-community edges preserved between super-nodes. |
| Fail-open | All exceptions caught; `detect_structural_communities` returns all-community-0 on parse error. |

---

## 6. Complexity Analysis

| Component | Complexity | Notes |
|-----------|-----------|-------|
| `_build_adjacency` | O(m) | m = edges |
| `louvain_clustering` Phase 1 (single pass) | O(n·k) | n nodes, k avg degree |
| `louvain_clustering` Phase 1 (convergence) | O(n·k·I) | I = iterations to converge (typically <10) |
| `_assign_communities` | O(n + m) | Builds adjacency, 1 louvain call |
| Total per `build_graph` | O(n·k·I + m) | n files (not symbols — per-file adjacency) |

v1 expected input size: n ~ 10..1000 files (per-file graph, not per-symbol).

---

## 7. Test Matrix

| Test | Input | Expected |
|------|-------|----------|
| Empty graph | `{}` | `{}` |
| Single node | `{"A": {}}` | `{"A": 0}` |
| Two connected | `A-B` | A and B same community |
| Triangle | `A-B-C-A` | All 3 same community |
| Disconnected | `A, B, C` isolated | All community 0 |
| Resolution γ=2.0 vs 0.5 | Weakly-coupled pairs | Higher γ → more communities |
| Star topology | Center + 4 leaves | All same community |
| Determinism | 3 consecutive calls | Identical output |
| Phase 2 path | <n new_nodes after Phase 1 | Recursive call executes |
| Perf bound | 200-node ring | <1s wall-clock |
| Fail-open | Malformed graph dict | All-community-0 |

---

## 8. Future Work (Out of Scope)

- Leiden algorithm (connectivity guarantees; requires python-igraph C dep)
- Multilevel Phase 2 (repeat until Q stops improving)
- Community quality metric Q returned alongside partition
- Optional python-louvain / leidenalg imports for larger graphs

---

*Generated by Hermes. G3-TRD — v1.0.*
