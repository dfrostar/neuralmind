# Wave 5 — Business Requirements Document (BRD)

**Date:** 2026-07-18
**Source:** `docs/PHASE3-PLAN.md` 🔴 HIGH priorities
**Previous waves:** 1 (D/B1/G1), 2 (C1/A1/A2/B2/B3/G2), 3 (C2/C3/A3/A4/B4/F1/F2), 4 (C4/G3/G4/E1-E4/F3/F4/D3/D4)
**Prerequisite:** v2.0 complete (4 waves, 1374 tests, all public-facing pages updated)

---

## 1. Business Problem

Wave 4 wired incremental extraction, quality scoring, merge semantics, peer review, staleness detection, metrics, and backpressure. The moat — the self-improving parameter tuner — still has its original Phase 2 limitation baked in:

**The tuner is a single-variable budget optimizer masquerading as a multi-objective evolutionary search.**

`PopulationTuner._fitness_from_traces()` (tuner.py:204-256) derives `retrieval_quality` from historical `success_signal` values and `session_health` from query-fingerprint collision counts. Both are computed from a fixed set of traces that do NOT change between candidates. The only axis that actually varies across candidates is `efficiency` — the L0-L3 token budget sum. A tuner that only minimizes tokens while ignoring actual retrieval faithfulness cannot claim to be "the moat."

TRD §4.2 (WAVE3-TRD.md:216-223) specified the intended evaluation flow: faithfulness_delta must be computed by **re-running retrieval with each candidate's parameters**. That wiring was never built. The gap was documented; Phase 3 closes it.

**Incremental extraction is built but dormant.** G4's `IncrementalExtractor` (incremental_extract.py:50-205) correctly detects added/modified/deleted files via SHA-256 + mtime and resolves transitive importers via reverse edges. But `build_graph()` (graphgen.py:580-664) still re-parses every file on every build. For large repos, this is pure waste — the user pays full price for a one-line change.

Wave 5 tightens the two highest-leverage threads: the tuner's credibility and the build's cost profile.

---

## 2. Business Objectives

| # | Objective | Success Metric |
|---|-----------|---------------|
| O1 | Tuner fitness varies ≥2 axes per candidate | Integration test: tuner's best config differs from random search's best on the Python fixture within 5 generations |
| O2 | Faithfulness delta is measured, not assumed | `evaluate_candidate()` produces different `retrieval_quality` values for candidates with different retrieval params |
| O3 | Large-repo builds skip unchanged files | `neuralmind build` on a 10K-line repo with 1 file changed completes in <10% of full-rebuild wall-clock time |
| O4 | Transitive importers are invalidated | Changing a leaf file triggers re-extraction of its importers (verified via structural_edges reverse traversal) |
| O5 | Cache survives restarts | `.neuralmind/extraction_cache.json` persists across `neuralmind build` invocations; second run is incremental |

---

## 3. Non-Goals

- ColBERT multi-vector retrieval quantification (deferred to Wave 7 per PHASE3-PLAN.md)
- Metrics dashboard CLI surface (deferred to Wave 6)
- Team memory end-to-end integration test (deferred to Wave 6)
- Concurrency stress test (deferred to Wave 7)
- Shadow-eval mode for all candidates (deferred — can be added after live eval proves valuable)
- Multi-language incremental extraction beyond Python (other languages already degrade gracefully)

---

## 4. Workstreams

### T1 — Close the tuner faithfulness gap

**Problem:** `_fitness_from_traces()` computes `retrieval_quality` as `mean(t.success_signal)` over a fixed trace set and `session_health` as `1 - collision_rate(query_fingerprint)`. Both are invariant across candidates. The weighted-product fitness (fitness.py:143-188) therefore collapses to a function of `efficiency` alone — total token budget. The tuner minimizes tokens, not cost-weighted faithfulness.

**Fix:** Implement real multi-objective evaluation that varies at least two axes per candidate. PHASE3-PLAN.md §19-28 lists three approaches:

1. **A/B candidate eval against live retrieval.** For each candidate, temporarily configure the embedder, run N fixture queries, measure real retrieval_quality (nDCG@5 or success-rate@k) and session_health (re-query-rate over the N queries). Expensive but faithful. **← Recommended primary path.**
2. Shadow-eval mode (deferred — can layer on after live eval proves the wiring).
3. Learned proxy (deferred — requires historical runs as training data).

**Acceptance:**
- `evaluate_candidate()` produces different `retrieval_quality` values for candidates with different retrieval parameters
- `evaluate_candidate()` produces different `session_health` values for candidates with different layer budgets (smaller budgets → more re-queries under fixed query load)
- Integration test: tuner's best config differs from random-search baseline on the Python fixture within 5 generations
- Fail-open preserved: if live eval fails, candidate scores 0.0 (never promoted over valid incumbent)
- Local-first: no cloud dependency for eval; fixture queries run against the local embedder

**Test:**
- `tests/test_tuner_faithfulness.py`: ≥12 tests covering:
  - Same candidate, same params → same fitness (determinism)
  - Different retrieval params → different retrieval_quality (axis varies)
  - Different layer budgets → different session_health (axis varies)
  - Fail-open on eval exception (returns 0.0)
  - Integration: tuner beats random search within 5 generations on fixture

---

### T2 — Wire incremental extraction into the build pipeline

**Problem:** `build_graph()` (graphgen.py:580-664) iterates every source file, reads bytes, parses via tree-sitter, runs `extract_symbols` + `resolve_edges` — regardless of whether the file changed. For a 10K-line repo with one modified line, the user pays 100% of the full-build cost.

`IncrementalExtractor` (incremental_extract.py:50-205) is fully built and unit-tested. `scan_files()` returns `(added, modified, deleted)` vs the SHA-256 cache. `get_changed_with_dependents()` adds transitive importers via `importer_index`. But nothing calls it from `build_graph()`.

**Fix:** Integrate `IncrementalExtractor` into `build_graph()`:

1. Instantiate `IncrementalExtractor(project_path)` at the top of `build_graph()`
2. Build (or load) `importer_index` — maps file → list of files that import it
   - Source: the existing graph's structural edges (already stored in `links`)
   - On first build (no cache), index is empty; all files are "added"
3. Call `get_changed_with_dependents(root, suffixes, importer_index)` to get the re-extract set
4. For deleted files: remove their nodes + edges from the graph
5. For unchanged + non-importer files: retain existing nodes + edges
6. For files in re-extract set: re-parse + re-extract symbols + re-resolve edges (current behavior, scoped to changed set)
7. After build: `update_cache(changed_files, root)`; `remove_from_cache(deleted_files)`
8. Persist `importer_index` for the next build (can be regenerated from graph's structural_edges on load)

**Acceptance:**
- `neuralmind build` on the Python fixture with 1 file touched re-extracts only that file + its transitive importers
- `neuralmind build` on a 10K-line repo with 1 file changed completes in <10% of full-rebuild wall-clock time
- Deleted files have their nodes + edges removed from the graph
- Cache persists across `neuralmind build` invocations (`.neuralmind/extraction_cache.json`)
- First run (no cache) behaves identically to current behavior (full extraction)
- Fail-open: if cache is corrupted/missing, fall back to full extraction

**Test:**
- `tests/test_incremental_wiring.py`: ≥12 tests covering:
  - First build: full extraction, cache written
  - Second build with no changes: zero files re-extracted
  - Touch one file: only that file + importers re-extracted
  - Delete a file: nodes + edges removed from graph
  - Cache corrupted → full extraction, no crash
  - Performance: 10K-line fixture, 1 change → <10% of full-build time
  - Importer transitivity: change grandparent → parent + child re-extracted

---

## 5. Stakeholders & Users

| Persona | Need | Pain Today |
|---------|------|------------|
| Individual developer | Parameter config that actually improves retrieval quality | Tuner minimizes tokens, not faithfulness; answers get cheaper but not better |
| Engineer at scale | Fast, cheap local builds on large repos | Every `neuralmind build` is a full reparse even for trivial changes |
| Maker (dfrostar) | Moat that earns its claims | "Self-improving" is marketing unless the tuner measures real faithfulness |

---

## 6. Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Live eval is too slow for population search (15 candidates × N queries × 8 generations) | Medium | Medium | Bound N (fixture query count) to ~20; run evals in parallel via ThreadPoolExecutor; cache embedder outputs per candidate |
| `importer_index` regeneration from graph edges is expensive on first wiring | Low | Low | Build incrementally; structural_edges already indexed; O(E) scan of existing links |
| Faithfulness delta is noisy on small fixture sets | Medium | Medium | Use nDCG@5 or AUC-style metric that is robust to small N; repeat eval 3× and average |
| Cache staleness across git operations (checkout, stash) | Low | Low | SHA-256 content hash is authoritative; mtime is only a pre-filter |
| Transitive importer resolution misses dynamically-imported files | Low | Medium | Static analysis already the limit of tree-sitter; document as known limitation |

---

## 7. Release Criteria

- [ ] T1: `evaluate_candidate()` produces different `retrieval_quality` for different retrieval params
- [ ] T1: `evaluate_candidate()` produces different `session_health` for different layer budgets
- [ ] T1: Tuner beats random search within 5 generations on Python fixture
- [ ] T1: `tests/test_tuner_faithfulness.py` ≥12 tests, all passing
- [ ] T2: `neuralmind build` on 10K-line repo with 1 change completes in <10% of full-rebuild time
- [ ] T2: Transitive importers are re-extracted when a dependency changes
- [ ] T2: Deleted file nodes + edges are removed from graph
- [ ] T2: Cache corrupted → full extraction, no crash
- [ ] T2: `tests/test_incremental_wiring.py` ≥12 tests, all passing
- [ ] All existing tests still pass (regression check)
- [ ] `docs/WAVE5-TRD.md` drafted alongside implementation

---

Signed-off-by: Hermes (product strategy)
