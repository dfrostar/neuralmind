# NeuralMind — Kanban Board (CANONICAL — `dfrostar/neuralmind`)

**Last updated:** 2026-09-17 16:30:00
**Repo:** `neuralmind` (dfrostar/neuralmind)
**Version:** 3.13.0
**Branch:** main
**Last commit:** `bea01ac` — chore: update NeuralMind team memory snapshot [skip ci] (2026-09-17)

---

## Status

### What Works (Verified)

| Component | Status | Tests |
|-----------|--------|-------|
| MedicalRetriever (standalone) | ✅ Built & tested | 22/22 pass |
| ChapterIndexer (standalone) | ✅ Built & tested | 12/12 pass |
| Pipeline integration (prose path) | ✅ Wired & tested | 12/12 pass |
| BM25 prose tokenizer fix (P0) | ✅ Fixed | Verified |
| Benchmark parser (new format) | ✅ Fixed | 14 queries run |

### Benchmark Results (peptide book, 14 queries)

| Metric | Before (v3.12) | After (v3.13) | Change |
|--------|----------------|---------------|--------|
| **Recall@1** | 64.3% | 78.6% | **+14 pts** |
| **Fact Recall** | 47% | 84% | **+37 pts** |
| MRR | 0.79 | 0.83 | +0.04 |
| Avg Latency | 1418ms | 921ms | 1.5x faster |
| Precision@5 | 38.6% | 37.3% | -1.3 pts (acceptable) |

### Architecture

```
NeuralMind.query()
  ├── if project_kind in ("prose", "mixed"):
  │     └── MedicalRetriever.query() → ContextResult
  │           ├── ChapterIndexer (BM25 + embedding + heading match)
  │           ├── ConfidenceFlagger (HIGH/MEDIUM/LOW)
  │           └── Negative query fallback
  └── else (code):
        └── ContextSelector.get_query_context() (unchanged)
```

---

## Decisions Made

### MedicalRetriever Design

| Decision | Rationale |
|----------|-----------|
| Chapter-level indexing (one doc per chapter) | Eliminates duplicate chapter entries from 61 fragmented nodes |
| Hybrid scoring: 0.30 BM25 + 0.45 embedding + 0.25 heading match | Embedding carries most weight for semantic queries; heading match catches exact phrases |
| Claims Register downweight (0.4×) | Reference tables hijack BM25 with dense term repetition |
| Back-matter downweight (0.3×) | Glossary is lookup table, not clinical content |
| Confidence gating (HIGH≥0.70, MEDIUM≥0.40, LOW<0.40) | No silent low-confidence results for medical content |
| Lazy initialization | MedicalRetriever only builds on first prose query |

### Context Mode Comparison

| Dimension | NeuralMind | Context Mode |
|-----------|-----------|------------|
| Scope | Persistent (your library) | Session-scoped (this conversation) |
| Input | Pre-existing documents | Tool output during session |
| Value | Surfaces relevant content from your knowledge base | Prevents context flooding |
| Semantic search | ✅ Embeddings (ONNX) | ❌ FTS5 keyword only |
| Prose/books | ✅ Chapter-level + medical terminology | ❌ Code-only |
| Session continuity | ❌ Not built | ✅ SQLite FTS5 |
| MCP integration | ❌ Not yet | ✅ 17+ agents |

**Verdict:** They're layers, not competitors. Context Mode manages the present; NeuralMind retrieves from the past.

---

## Pending Work

### Next Sprint
- [ ] Context Mode MCP integration for session continuity
- [ ] e5-large embedding upgrade (network blocked)
- [ ] Strip unused code paths (if any remain)
- [ ] Publish v3.13.0 to PyPI

### Known Limitations
- MiniLM-L6-v2 (384-dim) is the embedding ceiling (~67% recall@1)
- e5-large upgrade path documented but not yet available (network blocked)
- P95 latency 7.6s (first query cold start); subsequent queries <400ms
- Synapse layer unused for prose (only code projects)

---

## Action Items

1. Monitor for network availability to download e5-large ONNX model
2. Consider Context Mode integration as companion tool for session management
3. Evaluate competitive positioning: "Context Mode for personal knowledge"

---

## 📊 Repo State (2026-09-17)

| Field | Value |
|-------|-------|
| Branch | main |
| Last commit | `bea01ac` — chore: update NeuralMind team memory snapshot [skip ci] (2026-09-17) |
| Uncommitted | 3 files (KANBAN.md, Features.tsx, evals/public/card.py) |
| New work | `Features.tsx` — 30 lines added (uncommitted) |
| Stale days | 0 days (last commit today) |