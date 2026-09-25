# NeuralMind — Kanban Board (CANONICAL — `dfrostar/neuralmind`)

**Last updated:** 2026-09-25 14:00:00 UTC
**Repo:** `neuralmind` (dfrostar/neuralmind)
**Version:** 4.2.0+ (post-v4.2.0 consolidation)
**Branch:** main
**Last commit:** `aaa2c5d` — fix: two consolidation stragglers in tests — structural fixture + server guard (2026-09-25)
**Uncommitted:** 11 files (retrieval_results.json, 10 test fixture extraction_cache.json files)

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

---

## Pending Work

### Next Sprint
- [x] **Output directory consolidation** ✅ DONE (`62a44e8` — `graphify-out/` → `.neuralmind/` with legacy fallback)
- [x] **Auto-regenerate public benchmark on drift** ✅ DONE (`78f9299` — `bench-public-drift.yml`)
- [ ] Context Mode MCP integration for session continuity
- [ ] e5-large embedding upgrade (network blocked)
- [ ] Strip unused code paths (if any remain)
- [x] **Publish v4.2.0 to PyPI** ✅ DONE (`f1502dd`, 2026-09-18)
- [x] **Memory system — decision memory layer** ✅ DONE (commit-level invalidation, `e14ddfa`)
- [x] **Memory system — eval harness + MCP tools** ✅ DONE (MaintenanceEval, query_decisions, audit_decisions, record_decision, invalidate_decision)
- [x] **Memory system — PreToolUse stale-decision guard** ✅ DONE (`605b036`)
- [x] **Stale-decision guard across all public surfaces** ✅ DONE (`cf2ce08`, v4.2.0 prep)
- [ ] Memory system — integrate with synapse layer for cross-session persistence
- [x] **Stale-guard Windows path normalization** ✅ DONE (5 commits — 2026-09-19)
- [x] **Cost Attribution Dashboard** ✅ DONE (`09318d5` — `neuralmind cost` command)
- [x] **Synapse-prose integration** — extend Hebbian learning to prose/book content ✅ DONE (`ad51f53`, 2026-09-21)
- [x] **QA review findings (7 of 8)** ✅ DONE (`8f58d68` — deadlock, cap, docs, migration)
- [x] **Wheel fix — ship exactly demo graph** ✅ DONE (`e4ab5b1`)
- [x] **Ruff/black cleanup on QA-fix files** ✅ DONE (`3fd895d`)
- [x] **Test fixture consolidation stragglers** ✅ DONE (`aaa2c5d`, 2026-09-25)

### Known Limitations
- MiniLM-L6-v2 (384-dim) is the embedding ceiling (~67% recall@1)
- e5-large upgrade path documented but not yet available (network blocked)
- P95 latency 7.6s (first query cold start); subsequent queries <400ms

---

## Action Items

1. Monitor for network availability to download e5-large ONNX model
2. Consider Context Mode integration as companion tool for session management
3. **Push 23 commits to origin** — all consolidation + QA fixes ready
4. **Clean uncommitted test fixture artifacts** — `retrieval_results.json` + 10 `extraction_cache.json` files

---

## 📊 Repo State (2026-09-25 14:00 UTC)

| Field | Value |
|-------|-------|
| Branch | main |
| Last commit | `aaa2c5d` — fix: two consolidation stragglers in tests (2026-09-25) |
| Uncommitted | 11 files (retrieval_results.json, 10 test fixture extraction_cache.json) |
| Stale days | 0 days (commit today) |
| Sync | **23 commits AHEAD of origin/main** — needs `git push origin main` |