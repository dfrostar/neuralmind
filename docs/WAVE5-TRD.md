# Wave 5 — Technical Requirements Document (TRD)

**Date:** 2026-07-18
**Approved by:** dfrostar
**Source:** `docs/PHASE3-PLAN.md` 🔴 HIGH priorities, `docs/WAVE5-BRD.md`
**Previous TRDs:** WAVE2-TRD.md, WAVE3-TRD.md, WAVE4-TRD.md
**Prerequisite:** v2.0 complete (4 waves, 1374 tests)

---

## 1. Scope

Wave 5 implements two workstreams from PHASE3-PLAN.md's 🔴 HIGH tier:

- **T1 — Tuner faithfulness gap:** Make `PopulationTuner.evaluate_candidate()` produce different retrieval_quality and session_health values for different candidates via live retrieval evaluation.
- **T2 — Incremental extraction wiring:** Make `build_graph()` use `IncrementalExtractor` to skip unchanged files and invalidate transitive importers.

Both workstreams are independent — T1 touches tuner/fitness/fixture infrastructure, T2 touches graphgen/incremental_extract. DeepSeek QA runs in parallel per module.

---

## 2. Shared Architecture Rules

| Rule | Rationale |
|------|-----------|
| Local-first | No cloud dependency for tuner eval |
| Fail-open | Any failure in eval/build falls back to incumbent/full-extraction |
| Stdlib-only for core eval | Live eval uses embedder (may be API-backed) but fixture queries run locally |
| Public commands byte-compatible | `neuralmind build` output shape unchanged |
| Backpressure integration | T2 build calls check backpressure before mutating graph |
| Version-stamp schema changes | If fitness metadata schema evolves, version-stamp |

---

## 3. T1 — Close the Tuner Faithfulness Gap

### 3.1 Problem Statement

`_fitness_from_traces()` (tuner.py:204-256) derives:
- `retrieval_quality` = `mean(t.success_signal)` — fixed across candidates
- `session_health` = `1 - collision_rate(query_fingerprint)` — fixed across candidates
- `efficiency` = token budget ratio — the only axis that varies

`compute_fitness()` (fitness.py:143-188) uses weighted product: if two of three axes are fixed, the product collapses to a single-variable function. The tuner claims multi-objective search but is effectively a token-budget minimizer.

### 3.2 Fix: Live Retrieval Eval per Candidate

**Approach:** For each candidate, temporarily configure the embedder with the candidate's retrieval parameters, run N fixture queries against the local vector store, measure real retrieval_quality (success-rate@k or nDCG@5) and session_health (re-query-rate over the N queries). Expensive but faithful.

**Implementation sketch (`neuralmind/tuner.py`):**

```python
def evaluate_candidate(
    self,
    params: dict[str, float],
    store: Any | None = None,
) -> float:
    """Evaluate a candidate via live retrieval eval when possible.

    Falls back to _fitness_from_traces() if live eval cannot complete
    (fail-open: candidate scores 0.0, never promoted over valid incumbent).
    """
    try:
        return self._fitness_from_live_eval(params)
    except Exception as exc:
        log.warning("live eval failed, falling back to traces: %s", exc)
        try:
            return self._fitness_from_traces(params, store)
        except Exception as exc2:
            log.warning("trace fallback also failed: %s", exc2)
            return 0.0

def _fitness_from_live_eval(self, params: dict[str, float]) -> float:
    """Faithful multi-objective eval: run retrieval with candidate params.

    Measures real retrieval_quality (success-rate@5) and session_health
    (re-query-rate) by running fixture queries through the embedder with
    the candidate's retrieval parameters applied.
    """
    from .fixtures import load_fixture_queries  # new helper
    from .embedder import temporary_config  # context manager

    fixture_queries = load_fixture_queries(self.project_path, n=20)
    if not fixture_queries:
        return 0.0  # fail-open: no fixtures = no promotion

    with temporary_config(params):
        results = []
        re_queries = 0
        for query in fixture_queries:
            retrieved = self._run_retrieval(query)
            success = self._measure_success(query, retrieved)
            results.append(success)
            if self._is_re_query(query, retrieved):
                re_queries += 1

    retrieval_quality = sum(results) / len(results) if results else 0.0
    session_health = max(0.0, min(1.0, 1.0 - re_queries / len(fixture_queries)))
    efficiency = self._efficiency_ratio(params)

    inputs = FitnessInputs(
        retrieval_quality=retrieval_quality,
        efficiency=efficiency,
        session_health=session_health,
    )
    return compute_fitness(inputs).total
```

### 3.3 Required New Code

**`neuralmind/fixtures.py` (new module):**
- `load_fixture_queries(project_path, n=20) → list[FixtureQuery]`
  - Reads from `<project>/.neuralmind/fixture_queries.json` if present
  - Falls back to synthetic queries generated from graph node labels
  - Returns empty list if neither source available
- `FixtureQuery(query: str, expected_node_ids: list[str])`

**`neuralmind/embedder.py` (new context manager):**
- `temporary_config(params: dict[str, float]) → contextmanager`
  - Saves current embedder config, applies params, yields, restores on exit
  - Uses `resolve_effective()` / `apply_effective()` pattern from `tuning.py`

### 3.4 Determinism Requirements

- Same candidate params + same fixture queries → same fitness (within float tolerance)
- Fixture query order is deterministically sorted (by query string)
- Success measurement is deterministic for a given retrieval result set

### 3.5 Fail-Open Rules

- No fixtures available → return 0.0 (no promotion)
- Embedder raises during eval → return 0.0 (no promotion)
- Retrieval returns empty results → retrieval_quality = 0.0 (candidate scores 0.0, never promoted)
- All exceptions are caught and logged; incumbent always stands on error

### 3.6 Performance

- N = 20 fixture queries per candidate (configurable via `NEURALMIND_TUNER_EVAL_QUERIES`)
- ThreadPoolExecutor for parallel eval across candidates (max_workers=4)
- Cache embedder outputs per candidate to avoid redundant retrieval
- Expected overhead per generation: ~30s for pop=15, N=20

### 3.7 Tests (`tests/test_tuner_faithfulness.py`)

| Test | What it verifies |
|------|-----------------|
| `test_same_candidate_deterministic` | Same params → same fitness (float tolerance 1e-6) |
| `test_different_retrieval_params_differ` | Different L2 recall K → different retrieval_quality |
| `test_different_budget_params_differ` | Different L0-L3 budgets → different session_health |
| `test_fail_open_no_fixtures` | No fixtures → 0.0 |
| `test_fail_open_embedder_error` | Embedder raises → 0.0, no crash |
| `test_fail_open_retrieval_empty` | Empty retrieval → 0.0 |
| `test_tuner_beats_random_within_5_gen` | Integration: tuner > random on fixture |
| `test_efficiency_axis_still_varies` | Pure efficiency difference still produces gradient |
| `test_concurrent_eval_safe` | ThreadPoolExecutor doesn't corrupt shared state |
| `test_temporary_config_restores` | Context manager restores original config |
| `test_fixture_queries_fallback` | Falls back to synthetic queries when no fixture file |
| `test_fitness_score_components_exposed` | FitnessScore.components dict has all three axes |

---

## 4. T2 — Wire Incremental Extraction into Build Pipeline

### 4.1 Problem Statement

`build_graph()` (graphgen.py:580-664) re-parses every source file on every build. For a 10K-line repo with one modified line, the user pays 100% of full-build cost.

`IncrementalExtractor` (incremental_extract.py:50-205) is built and unit-tested:
- `scan_files(root, suffixes) → (added, modified, deleted)` via SHA-256 + mtime
- `get_changed_with_dependents(root, suffixes, importer_index) → list[str]` via reverse-edge traversal
- `update_cache(file_paths, root)` + `remove_from_cache(file_paths)` for persistence

But nothing calls it from `build_graph()`.

### 4.2 Fix: Integrate IncrementalExtractor into build_graph()

**Implementation sketch (`neuralmind/graphgen.py`):**

```python
def build_graph(project_path: str | Path, *, commit: str = "") -> dict[str, Any]:
    """Parse project_path and return a graphify-compatible graph dict.

    When an extraction cache exists, skips unchanged files and only
    re-extracts changed files + their transitive importers.
    """
    if not is_available():
        raise RuntimeError(...)

    root = Path(project_path).resolve()
    b = _GraphBuilder()

    # --- Incremental extraction setup ------------------------------------
    extractor = IncrementalExtractor(root)
    importer_index = _build_importer_index(root)  # from existing cache or empty
    re_extract_set = set()

    all_files = _iter_source_files(root, _DEFAULT_IGNORES)
    suffixes = frozenset(_SUFFIX_LANG.keys())
    changed_files = extractor.get_changed_with_dependents(root, suffixes, importer_index)
    re_extract_set = set(changed_files)

    # If first build (cache empty), all files are "added"
    if not extractor._cache:
        re_extract_set = {f.relative_to(root).as_posix() for f in all_files}

    # --- Process files: unchanged retained, changed re-extracted ------------
    by_lang: dict[str, list[Path]] = {}
    for fpath in all_files:
        rel = fpath.relative_to(root).as_posix()
        lang = _SUFFIX_LANG.get(fpath.suffix)
        if lang:
            by_lang.setdefault(lang, []).append(fpath)

    # ... (rest of build_graph iterates only files in re_extract_set,
    #      retains existing nodes/edges for unchanged files)

    # --- Post-build cache update -----------------------------------------
    extractor.update_cache(list(re_extract_set - {deleted}), root)
    extractor.remove_from_cache(list(deleted))

    return { ... }
```

### 4.3 Required New Code

**`neuralmind/graphgen.py` additions:**
- `_build_importer_index(root: Path) → dict[str, list[str]]`
  - Reads from `<project>/.neuralmind/importer_index.json` if present
  - Otherwise, reads existing graph's structural_edges and inverts them
  - Returns empty dict if no prior graph exists (first build)
- `_load_existing_graph(root: Path) → dict[str, Any] | None`
  - Loads `<project>/.neuralmind/graph.json` to reuse existing nodes/edges for unchanged files
- `_retain_unchanged_nodes(b: _GraphBuilder, existing_graph: dict, unchanged_files: set[str])`
  - Copies node entries from existing_graph for unchanged files to the new builder
- `_invalidate_changed_edges(b: _GraphBuilder, changed_files: set[str])`
  - Removes edges pointing to/from changed files before re-extraction

**`neuralmind/incremental_extract.py` additions:**
- `build_importer_index_from_graph(graph: dict[str, Any]) → dict[str, list[str]]`
  - Utility: invert structural_edges (source→target becomes target→source)
- `save_importer_index(root: Path, index: dict[str, list[str]])`
- `load_importer_index(root: Path) → dict[str, list[str]]`

### 4.4 Determinism Requirements

- Same file set + same content → same graph (modulo `built_at_commit` timestamp)
- Re-running build with no changes produces byte-identical graph.json (except `built_at_commit`)
- First build (no cache) produces identical output to pre-T2 behavior

### 4.5 Fail-Open Rules

- Cache corrupted/unreadable → full extraction, no crash
- Existing graph missing → full extraction, no crash
- Importer index missing → treat as empty (only changed files re-extracted, no transitive invalidation)
- `update_cache` / `remove_from_cache` failures are logged but don't fail the build

### 4.6 Performance Targets

| Scenario | Target |
|----------|--------|
| 10K-line repo, 1 file changed, 3 importers | <10% of full-build wall-clock |
| Cache read + importer_index load | <100ms overhead |
| Full extraction (no cache) | Same as pre-T2 |

### 4.7 Tests (`tests/test_incremental_wiring.py`)

| Test | What it verifies |
|------|-----------------|
| `test_first_build_full_extraction` | No cache → all files extracted, cache written |
| `test_second_build_no_changes` | No changes → zero files re-extracted |
| `test_touch_one_file` | Only that file re-extracted |
| `test_touch_file_with_importers` | File + transitive importers re-extracted |
| `test_delete_file` | Nodes + edges removed from graph |
| `test_cache_corrupted_fallback` | Corrupted cache → full extraction, no crash |
| `test_missing_graph_fallback` | No existing graph → full extraction, no crash |
| `test_importer_transitivity` | Change grandparent → parent + child re-extracted |
| `test_performance_ten_k_one_change` | 10K-line fixture, 1 change → <10% of full-build time |
| `test_graph_deterministic_on_no_change` | No changes → byte-identical graph.json (except timestamp) |
| `test_cache_persists_across_invocations` | `.neuralmind/extraction_cache.json` survives restart |
| `test_importer_index_persists` | importer_index persists for next build |

---

## 5. Key Dependencies Between Workstreams

```
T1 (tuner faithfulness)  ←→  T2 (incremental wiring)
    │                           │
    │ (independent — no shared code paths)
    │                           ├── incremental_extract.py (G4)
    │                           ├── graphgen.py (G1)
    │                           ├── embedder.py (existing)
    │
    ├── tuner.py (C3)
    ├── fitness.py (C1)
    ├── fixtures.py (NEW)
    └── embedder.py (new context manager)
```

T1 and T2 are fully independent. Can be developed, tested, and reviewed in parallel.

---

## 6. Key Risks & Mitigations

1. **Live eval latency:** 15 candidates × 20 queries × 8 generations = 2,400 evals.
   - Mitigation: Bound N=20, parallelize via ThreadPoolExecutor, cache embedder outputs.

2. **Importer index cold-start:** First wired build has no prior index.
   - Mitigation: Read existing graph's structural_edges; if no graph, treat as empty (still correct — just less precise on first run).

3. **Fixture query coverage:** Small N may produce noisy faithfulness estimates.
   - Mitigation: Use nDCG@5 or success-rate@k that is robust to small N; document limitation.

4. **Cache staleness across git operations:** SHA-256 content hash is authoritative; mtime is only a pre-filter. Cache handles git checkout/stash correctly.

5. **Transitive importer resolution misses dynamic imports:** Static analysis is the limit. Document as known limitation.

---

Signed-off-by: Hermes (TRD)
