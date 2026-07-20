# G3 Modularity Clustering QA Report

**Date:** 2026-07-23
**Commit:** `f49b535`
**Wave:** 4
**Previous version:** v11.0 (C4/D3/D4/E1-E4/F3/F4 complete)
**New version:** v10.0 (G3 complete, dispatchating G4)

---

## Summary

G3 ships Louvain modularity clustering into `build_graph`, replacing
balanced-per-file communities with structural-edge-driven clustering.
Three fixes: resolution parameter bug, O(n²)→O(n·k) optimization, and
incremental community ID stability via carry-over.

### Bugs Fixed

| # | Severity | File | Finding |
|---|----------|------|---------|
| 1 | CRITICAL | `modularity.py:_modularity_gain` | `resolution` param ignored — γ=1.0 hardcoded |
| 2 | HIGH | `modularity.py:louvain_clustering` | O(n²) nested loop — `community_weights` recomputed per node |
| 3 | MEDIUM | `graphgen.py:_assign_communities` | Per-file clustering replaces modularity; no integration with new `modularity` module |

### Patches Applied

#### Patch 1: `_modularity_gain` — resolution now applied
File: `neuralmind/modularity.py`

```python
# BEFORE: σ_target·k_i/(2m)  (no resolution)
gain_from_target = k_i_in_target - sigma_tot_target * k_i / (2.0 * m)

# AFTER:  γ·σ_target·k_i/(2m)
two_m = 2.0 * m
gain_from_target = (k_i_in_target - resolution * sigma_tot_target * k_i / two_m) / m
```

#### Patch 2: O(n·k) — incremental community weight updates
File: `neuralmind/modularity.py`

```python
# BEFORE (per node, O(n)): recompute ALL community weights
community_weights = defaultdict(float)
for n in nodes:
    if n == node: continue
    community_weights[c] += sum(adj.get(n, {}).values())

# ONCE before loop (O(n)): pre-compute
community_weights: dict[str, float] = defaultdict(float)
node_degree: dict[str, float] = {n: sum(adj.get(n, {}).values()) for n in nodes}

# AFTER per move (O(1)): incrementally update
community_weights[current_c] -= k_val
community_weights[best_community] += k_val
```

#### Patch 3: Wire Louvain into `build_graph`
File: `neuralmind/graphgen.py`

- `_assign_communities(b, existing_graph)` rebuilds community assignment using
  Louvain over per-file edges (`calls`/`imports_from`/`inherits`/`contains`).
- `_load_existing_graph` supplies prior `community` IDs; new files get
  fresh IDs from `next_comm = max(carried) + 1`.
- Fail-open: if Louvain collapses to ≤1 community, fall back to per-file
  grouping.

### Test Results

| Suite | Tests | Status |
|-------|-------|--------|
| `tests/test_modularity.py` | 11 | ✅ all pass (was 5, +6 new) |
| `tests/test_graphgen*.py` | 24 | ✅ all pass |
| `tests/test_incremental_extract.py` | 10 | ✅ all pass |
| **Full suite** | **1582** | ✅ **all pass** |

New tests added:
- `test_resolution_param_affects_result` — γ=2.0 ≥ γ=0.5 community count
- `test_resolution_1_matches_pure_adjacency` — γ=1.0 groups star topology
- `test_deterministic_output` — 3 consecutive calls yield identical results
- `test_perf_bound` — 200-node ring < 1s (was O(n²) → now O(n·k))

### Acceptance Checklist

- [x] `resolution` parameter actually affects `_modularity_gain` result
- [x] Phase 1 runs in O(n·k) or better (not O(n²))
- [x] Deterministic output (sorted tiebreaking)
- [x] Communities validated against known architecture (star, ring, two-pair)
- [x] All existing modularity tests pass
- [x] ruff clean
- [ ] DeepSeek QA dispatched (DEFERRED — QA after G4 ships both together)

### Known Limitations (Honest)

- Single-collapse Phase 2 (not full multilevel). Acceptable for v1 dense code graphs.
- Leiden deferred (requires `python-igraph` C dep). Future optional upgrade.
- Carry-over community ID mapping may reorder new-file IDs vs old; semantically
  equivalent to graphify's approach (first-build numbering).
