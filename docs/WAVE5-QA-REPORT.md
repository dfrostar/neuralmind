# Wave 5 DeepSeek QA Report

**Date:** 2026-07-18
**Submitted by:** DeepSeek v4 Pro (deleg_780567ef)
**Scope:** T1 (tuner.py) + T2 (graphgen.py incremental wiring) — both shipped in v0.49.0

---

## T1 — Tuner Faithfulness Gap (neuralmind/tuner.py)

### Summary

4 CRITICAL findings, 2 WARNING issues, 1 overclaim. The refactor fixed the "trace proxy" limitation but introduced new bugs and left structural weaknesses.

---

### CRITICAL Findings

#### C1. NaN/Inf Guard Missing

**Location:** `neuralmind/fitness.py:134-140` (`_clamp()`)

`_clamp()` does not defend against NaN:
```python
def _clamp(value, lo=0.0, hi=None):
    if value < lo: return lo      # NaN < 0.0 → False → passes through
    if hi is not None and value > hi: return hi  # NaN > 1.0 → False
    return value                  # returns NaN
```

**Propagation path:**
1. `_fitness_from_traces()`: `success_total = sum(t.success_signal ...)` unconstrained
2. `retrieval_quality = success_total / len(traces)` → NaN
3. `_clamp(NaN, 0.0, 1.0)` → NaN passes through
4. `min(NaN, 10.0)` → NaN (Python semantics)
5. `math.log(NaN)` → NaN
6. `total = NaN`

**Impact:** NaN fitness is "safe" for promotion (`NaN > x` is always False → never promoted) but silently breaks the tuner: once incumbent is NaN, ALL subsequent comparisons are False → tuner stops promoting permanently.

**Entry point:** `traces.py:38` — `success_signal FLOAT` unconstrained. Test fixtures can seed NaN.

**Patch:** Add `math.isnan/math.isfinite` guard at `_clamp()` and sanitize `success_signal` at trust boundary.

---

#### C2. `hash()` Non-Deterministic

**Location:** `neuralmind/tuner.py:310`

```python
query_fp = hash(fq.query) % 10000
```

Python's `hash()` for strings is randomized per-process (PYTHONHASHSEED, enabled by default since Python 3.3). So `session_health` differs between runs for the same candidate + fixtures. TRD §3.4 (determinism) violated.

**Patch:** Replace with `hashlib.sha256(fq.query.encode()).hexdigest()`.

---

#### C3. `_fitness_from_live_eval` Defined Twice

**Location:** `neuralmind/tuner.py:209` AND `tuner.py:262`

The second definition silently overrides the first. The first (lines 209-260) is orphaned dead code. Confirmed by docstring mismatch (first claims "all three axes vary", second omits claim).

**Patch:** Remove the second definition header + body (lines 262-288) — the working version is at the second site.

---

#### C4. Denominator Bias on Search Failure

**Location:** `neuralmind/tuner.py:315-317`

```python
retrieval_quality = successes / len(fixture_queries)  # FULL denominator
```

If `embedder.search()` raises mid-loop, the query is skipped (`continue`) but the denominator stays at 20. If 10/20 queries error, remaining 10 successes are divided by 20 → biased down.

**Patch:** Track `queries_attempted` (only increment on successful search), divide by that.

---

### WARNING Findings

#### W1. Dead `store` Parameter

`evaluate_candidate(params, store=None)` and `_fitness_from_traces(params, store)` both accept `store` but never use it — `TraceStore` is created internally.

**Patch:** Remove `store` parameter from both signatures.

---

#### W2. ThreadPoolExecutor Overclaim — Confirmed False

TRD §3.6: *"ThreadPoolExecutor for parallel eval across candidates (max_workers=4)"*
BRD §3: *"run evals in parallel via ThreadPoolExecutor"*

**Not implemented.** `tuner.py:456-462` is a purely sequential `for` loop. No `concurrent.futures` anywhere.

**Resolution:** Remove overclaim from TRD/BRD. Sequential eval is acceptable for v1 (15 candidates × 20 queries × embedder.search ~ 30s total). Parallelism is a v2 optimization.

---

### Axis Independence — DeepSeek Assessment

DeepSeek claims: *"retrieval_quality is **identical** across all candidates — If expected node X is in the top-10, it's also in the top-50. If it's NOT in the top-10, it won't be in the top-50."*

**Verdict:** Partially correct, misses edge cases.

- **If the expected node is ranked 1-10:** True, all candidates retrieve it → equal retrieval_quality.
- **If the expected node is ranked 11-50:** Only candidates with `search_n >= rank` retrieve it → retrieval_quality differs.
- **If the expected node is ranked >50:** No candidate retrieves it → equal retrieval_quality.

**The effect depends on fixture query design.** If fixtures are calibrated so expected nodes span ranks 10-50, the axis varies. If all fixtures have expected nodes in top-10, the axis collapses.

**Honest state:** The improvement is **incremental, not transformative**. We went from "single-variable budget optimizer" to "single-variable + weak retrieval depth signal." Real multi-objective eval requires `GraphEmbedder` to accept per-candidate configuration (different seed_k weights, different boost weights).

**Resolution:** Ship incremental improvement now. Flag "per-candidate embedder config" as v0.50 work.

---

## T2 — Incremental Extraction Wiring (neuralmind/graphgen.py)

### Summary

2 CRITICAL + 4 WARNING. Core logic correct for sequential single-user builds. Main gaps: concurrency, community ID stability, cache pollution.

---

### CRITICAL Findings

#### C1. No Concurrent Build Locking

**Location:** `graphgen.py:build_graph()` — three files read/written with no locking:
- `.neuralmind/extraction_cache.json`
- `.neuralmind/importer_index.json`
- `graphify-out/graph.json`

Two simultaneous builds (CI + local, or `watch --reindex` + manual `build`):
- Read stale cache → re-extract already-processed files
- Truncate `graph.json` mid-write → corrupt JSON
- Write `importer_index` from stale graph → lose edge info

`fcntl` already used in `recent_queries.py:154` — same pattern needed.

**Patch:** Add `fcntl.flock()` or `FileLock` around the critical section (cache read → build → cache write).

---

#### C2. `_assign_communities()` Recomputes ALL Community IDs

**Location:** `graphgen.py:731`

`build_graph()` calls `_assign_communities(b)` unconditionally:
```python
files_sorted = sorted({n["source_file"] for n in b.nodes.values()})
comm_of_file = {f: i for i, f, in enumerate(files_sorted)}
```

**Adding one new file shifts every existing file's community number.** Docstring at line 600-604 claims: *"Unchanged files keep their nodes, edges, and community ids byte-for-byte."* **False.**

**Impact:** If embedder uses community ID in content hashing (it does — `node["community"]` is part of hash input), every incremental `build_graph` re-embeds ALL nodes, defeating the purpose.

**Patch:** Carry over community IDs from existing graph (same pattern as `update_files()`). New files get fresh IDs; existing files keep their numbers.

---

### WARNING Findings

#### W1. `scan_files()` Ignores `_DEFAULT_IGNORES`

**Location:** `incremental_extract.py:118-129`

`scan_files()` uses `root.rglob("*")` and only filters `p.startswith(".") or p.startswith("__")`. Does NOT honor `_DEFAULT_IGNORES`:

| Path | `_iter_source_files` | `scan_files` |
|------|---------------------|--------------|
| `node_modules/` | ✅ skipped | ❌ picked up |
| `target/` | ✅ skipped | ❌ picked up |
| `graphify-out/` | ✅ skipped | ❌ picked up |

**Impact:** `node_modules/pkg/index.py` enters `re_extract_set` → `update_cache` writes its hash → cache pollution. Self-healing but untidy memory leak.

**Patch:** Import `_DEFAULT_IGNORES` in `scan_files()` and apply to path parts.

---

#### W2. Empty `source_file` Nodes Always Retained

```python
if not (root / sf).exists() if sf else False:
```

When `sf == ""`, ternary evaluates to `False`, so nodes with empty `source_file` bypass existence check and are always appended to `unchanged_nodes`. Nonsensical nodes (no source file) should be dropped.

**Patch:** Explicit `if not sf: continue` check.

---

#### W3. `update_cache()` Writes Unextracted Files

`build_graph()` calls `extractor.update_cache(list(re_extract_set), root)`. Since `re_extract_set` can include `node_modules/`, `target/`, `graphify-out/` files (W1), cache entries are written for files that were never parsed.

**Patch:** Filter `re_extract_set` through `_iter_source_files` before cache update.

---

#### W4. Dangling Edge Handling — Correct

Verified: edges from unchanged files that point to now-deleted symbols are correctly pruned because changed file's nodes are excluded from `unchanged_nodes`, and the edge is never re-resolved.

---

## Patch Plan (v0.49.1)

### T1 Patches (tuner.py + fitness.py)

| # | Finding | File | Change |
|---|---------|------|--------|
| 1 | C1 NaN/Inf | `fitness.py` | Add `math.isnan/isfinite` guard in `_clamp()` |
| 2 | C1 NaN/Inf | `tuner.py` | Filter non-finite `success_signal` in `_fitness_from_traces()` |
| 3 | C2 hash() | `tuner.py` | Replace `hash()` with `hashlib.sha256` |
| 4 | C3 duplicate | `tuner.py` | Remove entire second `_fitness_from_live_eval` definition |
| 5 | C4 denominator | `tuner.py` | Track `queries_attempted`, divide by that |
| 6 | W1 store param | `tuner.py` | Remove `store` parameter from both signatures |

### T2 Patches (graphgen.py + incremental_extract.py)

| # | Finding | File | Change |
|---|---------|------|--------|
| 7 | C1 locking | `graphgen.py` | Add `fcntl.flock()` around cache + graph writes |
| 8 | C2 communities | `graphgen.py` | Carry over community IDs from existing graph |
| 9 | W1 ignores | `incremental_extract.py` | Honor `_DEFAULT_IGNORES` in `scan_files()` |
| 10 | W2 empty sf | `graphgen.py` | Explicit `if not sf: continue` check |
| 11 | W3 unextracted | `graphgen.py` | Filter `re_extract_set` before cache update |

### BRD/TRD Updates

- Remove ThreadPoolExecutor overclaim (T1 W2)
- Flag per-candidate embedder config as v0.50
- Document community ID carry-over as a requirement

---

*Report by Hermes QA. DeepSeek findings verified against v0.49.0 (commit 0467588).*
