# SPEC: NeuralMind v3.13.0 — MedicalRetriever Pipeline Integration

**Date:** 2026-09-15
**Version:** v3.13.0
**Target:** Wire MedicalRetriever into NeuralMind.query() for prose projects
**Status:** In Progress

---

## Problem Statement

The MedicalRetriever module exists and is fully tested (22 tests passing), but it lives
alongside the main pipeline. The benchmark still measures the old ContextSelector prose
branch on 61 fragmented nodes. Result: no movement on precision/recall despite a superior
retriever being available.

**This SPEC defines the wiring.** Every change is tested before commit.

---

## Scope

### In Scope
- Wire MedicalRetriever into `NeuralMind.query()` for prose/mixed projects
- Preserve code path (tree-sitter, synapses, progressive disclosure) unchanged
- Confidence flags in output context
- Fallback message for negative queries
- Full test suite must pass (zero regressions)

### Out of Scope
- Context Mode MCP integration (separate sprint)
- e5-large embedding upgrade (separate, network-dependent)
- Synapse layer changes (keep as-is for code)
- Book index format changes

---

## Architecture

### Current Flow (unchanged for code)
```
NeuralMind.query() → ContextSelector.get_query_context() → L0-L3 → ContextResult
```

### New Flow (prose/mixed projects)
```
NeuralMind.query()
  ├── if project_kind == "prose": → MedicalRetriever.query() → ContextResult
  └── else: → ContextSelector.get_query_context() (unchanged for code)
```

### Key Decision Points

1. **Project Detection**: Use `self.project_kind` (already populated from graph.json)
   - "prose" → MedicalRetriever path
   - "code" → ContextSelector path (unchanged)
   - "mixed" → MedicalRetriever path (prose-first, code as fallback)

2. **ContextResult Compatibility**: MedicalRetriever returns a compatible object:
   - `context: str` — formatted with confidence flags
   - `budget: TokenBudget` — reuse existing dataclass
   - `search_hits: int` — number of chapters returned
   - `reduction_ratio: float` — tokens reduced vs raw
   - `top_search_hits: list[dict]` — chapter metadata for trace
   - `trace: list[dict]` — retrieval trace for debugging

3. **Confidence Flags**: Appear at top of each chapter block
   - `[Confidence: HIGH]` — score >= 0.70
   - `[Confidence: MEDIUM — verify]` — 0.40 <= score < 0.70
   - LOW results replaced with fallback message (no silent low-confidence)

4. **Negative Query Handling**: If all results are LOW confidence or no results:
   - Return ContextResult with `fallback_used=True`
   - Context contains: "No reliable match found in your knowledge base. Consult a healthcare provider."
   - `search_hits=0`

5. **Build Lifecycle**: MedicalRetriever builds lazily on first prose query
   - `NeuralMind.__init__` does NOT build MedicalRetriever
   - First `query()` call detects prose project and builds if needed
   - Subsequent queries reuse the built indexer

---

## Files Changed

### `/home/dtfrost5/neuralmind/neuralmind/core.py`
- Add `_medical_retriever` attribute (lazy init)
- Add `_get_medical_retriever()` method
- Modify `query()` to branch on `self.project_kind`
- Add `_build_medical_context_result()` adapter

### `/home/dtfrost5/neuralmind/neuralmind/medical_retriever.py`
- Add `to_context_result()` method to MedicalRetriever.query() return
- Ensure ContextResult compatibility

### `/home/dtfrost5/neuralmind/tests/test_pipeline_integration.py` (NEW)
- 8 tests covering the new prose path
- Each test fails before implementation (TDD)

---

## Test Plan (TDD Order)

### Step 1: Write Failing Tests

| Test | What It Verifies |
|------|------------------|
| `test_prose_project_uses_medical_retriever` | project_kind="prose" routes to MedicalRetriever |
| `test_code_project_uses_context_selector` | project_kind="code" routes to ContextSelector (unchanged) |
| `test_medical_retriever_lazy_init` | Not built until first prose query |
| `test_context_result_compatibility` | MedicalRetriever result has all ContextResult fields |
| `test_confidence_flags_in_context` | Output contains [Confidence: HIGH/MEDIUM] |
| `test_negative_query_fallback` | No results → fallback message, fallback_used=True |
| `test_peptide_book_semaglutide_query` | End-to-end: semaglutide query returns Ch2 or Ch3 |
| `test_full_test_suite_no_regression` | All existing tests still pass |

### Step 2: Run Tests (Verify RED)
```bash
python3 -m pytest tests/test_pipeline_intrieval.py -v  # expect 8 failures
```

### Step 3: Implement Wiring (GREEN)
- Modify `core.py` query() method
- Add adapter methods
- Ensure compatibility

### Step 4: Run Tests (Verify GREEN)
```bash
python3 -m pytest tests/test_pipeline_integration.py -v  # expect 8 pass
```

### Step 5: Full Regression
```bash
python3 -m pytest tests/ -q  # expect all pass, zero regressions
```

### Step 6: Benchmark
```bash
python3 tests/benchmark/peptide_benchmark.py  # expect P@5 > 38.6%
```

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Existing code-path tests break | Run full suite after every change; code path is untouched |
| MedicalRetriever build is slow | Lazy init; only builds on first prose query |
| ContextResult field mismatch | Adapter method converts MedicalRetriever result → ContextResult |
| project_kind detection wrong | Default to code path (existing behavior); only override for explicit prose |
| TokenBudget mismatch | Reuse existing TokenBudget dataclass; populate from MedicalRetriever metrics |

---

## Success Criteria

| Metric | Target |
|--------|--------|
| All existing tests pass | 100% (zero regressions) |
| Pipeline integration tests pass | 8/8 |
| Precision@5 (peptide book) | >= 50% (up from 38.6%) |
| Recall@1 (peptide book) | >= 70% (up from 64.3%) |
| Confidence flags in output | Every result has [Confidence: HIGH/MEDIUM/LOW] |
| Negative query fallback | Returns "consult professional" message |

---

## Post-Integration (Next Sprint)

- Context Mode MCP integration for session continuity
- e5-large embedding upgrade (when network allows)
- Strip unused code paths (if any remain)
- Publish v3.13.0 to PyPI

---

*Drafted by Hermes Agent. Approved for execution.*
