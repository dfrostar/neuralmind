# SPEC: NeuralMind v3.12.0 — Performance Improvements

**Date:** 2026-09-15
**Version:** v3.12.0
**Target:** Fix cold-start latency, improve precision@5, improve recall@1

---

## Problem Statement

Current benchmark (v3.11.3, 14 queries, peptide book):

| Metric | Value | Issue |
|--------|-------|-------|
| P95 Latency | 14,894ms | First query triggers ONNX model load (~15s) |
| Precision@5 | 45% | Same chapter appears 3-5 times, wasting token budget |
| Recall@1 | 57% | Top node ≠ top chapter; chapter with best single match loses to chapter with N marginal matches |
| Recall@5 | 97.6% | ✅ At ceiling |
| Hit Rate | 100% | ✅ All queries return ≥1 relevant chapter |

## Root Causes

### 1. Cold-Start Latency (P95: 15s → <500ms)

**Cause:** `NeuralMind.__init__` does not load the ONNX embedding model. First `query()` call triggers lazy init inside `_ensure_built()` → `build()` → embedder init → ONNX Runtime session creation (~15s).

**Fix:** Pre-load the embedding model in `NeuralMind.__init__` after the selector is built. Move ONNX Runtime init to construction time.

**Files:** `neuralmind/core.py`

### 2. Precision@5 (45% → 65%+)

**Cause:** `_assemble_prose_context()` emits one block per node. When the same chapter has multiple matching nodes, it appears 3-5 times in context. These duplicates push out diverse relevant chapters.

**Fix:** In `_assemble_prose_context()`, merge consecutive same-chapter nodes into a single block with combined text. Score = max(node scores). Factor = 1.2× for merged blocks (rewards chapters with multiple relevant sections).

**Files:** `neuralmind/context_selector.py`

### 3. Recall@1 (57% → 70%)

**Cause:** `_fetch_search()` returns top-N nodes globally. A chapter with one strong match (score 0.9) loses to a chapter with 3 marginal matches (scores 0.5, 0.4, 0.3). But the single strong match is more relevant.

**Fix:** Add chapter-level scoring in `_weighted_hybrid_score()`. For each chapter, take the max-scoring node. Then apply a chapter diversity bonus: chapters with ≥1 strong match (>0.7) get 1.5× boost.

**Files:** `neuralmind/context_selector.py`

### 4. Medical Terminology Routing

**Cause:** "semaglutide" is a GLP-1 receptor agonist, but vector similarity doesn't always surface chapters mentioning "GLP-1" when the query uses "semaglutide". BM25 helps because exact term matches, but semantic cross-matching is missing.

**Fix:** Add a lightweight medical terminology table (drug name → drug class → chapter mapping). Before query, expand query with known synonyms from the table. This is a targeted enrichment, not a general embedding change.

**Files:** `neuralmind/context_selector.py`, `neuralmind/terminology.py` (new)

---

## Implementation Details

### Fix 1: Cold-Start Pre-Load (core.py)

After `_ensure_built()`, if the selector exists and has an embedder, call `self.selector.embedder._load_model()` (or equivalent) to force ONNX session creation at init time, not at first query.

**Expected impact:** P95 latency 15s → <500ms (model already loaded)

### Fix 2: Chapter Deduplication (context_selector.py)

In `_assemble_prose_context()`:
1. Group consecutive nodes by (chapter, section)
2. For each group, emit one header + combined text (truncated to fit token budget)
3. Score = max(node scores in group) × 1.2 merge bonus
4. Track which chapters have been emitted; skip subsequent same-chapter nodes

**Expected impact:** Precision@5 45% → 65%+ (fewer duplicate chapters, more diverse content)

### Fix 3: Chapter-Level Scoring (context_selector.py)

After `_weighted_hybrid_score()`, before returning:
1. Group nodes by source_file prefix (chapter)
2. For each chapter, find max node score
3. Apply 1.5× boost to chapters with max score > 0.7
4. Re-sort by boosted score

**Expected impact:** Recall@1 57% → 70% (chapters with one strong match rank above chapters with many marginal matches)

### Fix 4: Medical Terminology Expansion (terminology.py)

Create a small medical terminology table:
```python
DRUG_TO_CLASS = {
    "semaglutide": "GLP-1 receptor agonist",
    "tirzepatide": "GLP-1/GIP dual agonist",
    "retatrutide": "GLP-1/GIP/glucagon triple agonist",
    "bpc-157": "gastric peptide",
    "cjc-1295": "GHRH analog",
    "sermorelin": "GHRH analog",
    "epitalon": "telomerase activator",
    "mots-c": "mitochondrial peptide",
    "ziconotide": "calcium channel blocker",
    "ipamorelin": "GH secretagogue",
    "tb-500": "synthetic peptide",
    "glp-1": "GLP-1 receptor agonist",
    "gip": "glucose-dependent insulinotropic polypeptide",
    "ghrh": "growth hormone-releasing hormone",
}
```

Before query, expand query with known synonyms. E.g., "How does semaglutide work?" → "How does semaglutide GLP-1 receptor agonist work?"

**Expected impact:** Cross-term matching for medical queries

---

## Implementation Order

1. Fix 1 (cold-start) — highest user impact
2. Fix 2 (chapter dedup) — biggest precision gain
3. Fix 3 (chapter-level scoring) — biggest recall@1 gain
4. Fix 4 (terminology expansion) — targeted medical cross-matching
5. Re-run benchmark
6. Verify all improvements
7. Commit + tag v3.12.0

---

## Success Criteria

| Metric | Current (v3.11.3) | Target (v3.12.0) |
|--------|-------------------|-------------------|
| P95 Latency | 14,894ms | < 500ms |
| Precision@5 | 45% | ≥ 65% |
| Recall@1 | 57% | ≥ 70% |
| Recall@5 | 97.6% | ≥ 95% (don't regress) |
| Hit Rate | 100% | 100% |
| Tests | 211 passed | 211+ passed (no regressions) |

---

## Test Plan

1. `python3 -m pytest tests/test_document_ingestion.py tests/test_book_indexing.py tests/test_turbovec_backend.py tests/test_graphgen.py tests/test_ingest_content.py -q` — all pass
2. `python3 tests/benchmark/peptide_benchmark.py` — verify improvements
3. `python3 -m tests.benchmark.run` — verify CI regression gate passes
4. Manual query test: `nm.query("How does semaglutide work?")` — first query < 500ms
5. Commit + tag v3.12.0
