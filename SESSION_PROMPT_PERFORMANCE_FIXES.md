# NeuralMind Performance Fixes — Session Prompt

> **Updated:** v2.5-Hermes.3 (2026-09-14) — ROOT CAUSE IDENTIFIED
> **Previous version:** v2.5-Hermes.2 (same day)

---

## Root Cause Summary (2026-09-14 Investigation)

The peptide book has **two separate indexes** built from different data:

| Index | Source | Count | ID Scheme |
|-------|--------|-------|-----------|
| **Vector** | graph.json headings | 77 nodes | `chapters_03_fda_approved_peptides_md__h1` |
| **BM25** | content chunks (paragraphs) | 315 docs | `doc:03_fda-approved-peptides.md.378c2e65:chunk1` |

**The hybrid merge silently fails because IDs don't match.** When the merge finds no overlapping IDs, BM25-only results are capped at 0.3 weight and can never outrank vector results. The system returns Back Matter glossary for "semaglutide" because the vector index only contains heading-level text.

**Fix requires:** Rebuild vector index from same 315 content chunks as BM25, OR map BM25 results back to vector nodes by source_file, OR use source_file as merge key.

---

## Context

NeuralMind v3.10.0 benchmarked against The Peptide Patient's Guide (17,000 words, 13 chapters, 315 content chunks). Results:

| Metric | Current (Actual) | Target |
|--------|-----------------|--------|
| P95 Latency | 3,527ms | <500ms |
| Precision@5 | 26.3% | >70% |
| Fact Recall | 42% | >75% |
| Recall@1 | 57.9% | >75% |
| Recall@5 | 86.4% | >85% |

**Critical failures:**
- `semaglutide` query → returns Back Matter glossary, NOT FDA-Approved chapter
- First query re-embeds 77 nodes despite existing index (3.5s)
- BM25 index exists (315 docs) but is silently dropped by hybrid merge due to ID mismatch
- Context is Back Matter, not relevant chapter

---

## Task 1: Fix Cold-Start Latency (P0)

**Problem:** First query re-embeds all nodes despite existing index.

**Root cause:** `NeuralMind.__init__` doesn't call `_ensure_built()` or load existing embeddings.

**Fix:** Add `_ensure_built()` to `NeuralMind.__init__`, add mtime-based stale detection.

**Files:** `neuralmind/core.py`, `neuralmind/embedder.py`

---

## Task 2: Fix Vector-BM25 Hybrid Merge (P0) — ROOT CAUSE FIX

**Problem:** Vector index has 77 heading nodes, BM25 has 315 content chunks. IDs don't match → hybrid merge silently drops BM25 results.

**Expected behavior:** Both indexes built from same 315 content chunks, merge by source_file.

**Fix approach:**
1. Rebuild vector index from same content chunks as BM25 (315 docs)
2. OR: Change merge key from `id` to `source_file` (fallback when IDs don't match)
3. OR: Add BM25 chunk-to-vector-node mapping

**Recommended:** Option 1 (rebuild vector index from chunks) — cleanest, ensures both signals operate on same semantic units.

**Files:** `neuralmind/embedder.py` (embed_content flow), `neuralmind/context_selector.py` (merge logic)

---

## Task 3: BM25 + Embedding Hybrid Retrieval (P0)

**Problem:** Precision@5 is 26%. Medical exact terms need BM25 boost.

**Depends on:** Task 2 (same chunk granularity)

**Fix approach:**
1. Ensure both indexes use same 315 content chunks
2. **Adaptive weights:**
   - Base: 0.4 embedding / 0.6 BM25
   - If query term appears in ≤3 docs → bump BM25 to 0.8
   - If query term appears in only 1 doc → BM25 = 0.9
   - Hard rule: exact match >2x next candidate wins regardless
3. **Normalization:** BM25 scores normalized via min-max over result set

**Files:** `neuralmind/context_selector.py`, `neuralmind/embedder.py`

---

## Task 4: Context Cleanup for Prose Mode (P0)

**Problem:** Context is Back Matter/glossary instead of relevant chapter text.

**Fix approach:**
1. Content mode detection (prose vs code) — already works (`project_kind: prose`)
2. Prose context template: chapter title + section heading + matched text
3. Suppress "Knowledge Graph," "Code Clusters," "Architecture Overview"

**Files:** `neuralmind/context_selector.py`

---

## Task 5: Confidence Calibration (P0)

**Problem:** System returns wrong chapters with false confidence.

**Fix approach:**
- Confidence formula: `confidence = (top1_score - top2_score) * (1 + exact_term_boost)`
- Exact-term boost: +0.2 if term in ≤3 docs, +0.5 if term in only 1 doc
- Thresholds: HIGH (margin >0.3), MEDIUM (0.1-0.3), LOW (<0.1)

---

## Task 6: Ambiguity Handling (P0)

**Fix approach:**
- Return top-1 with visible `[Confidence: HIGH/MEDIUM/LOW]` flag
- MEDIUM: "Additional chapters may be relevant — verify with other sources"
- LOW: "This result may not fully address your question — consult a healthcare provider"

---

## Task 7: Negative Query Fallback (P0)

**Fix approach:**
- If best match confidence <50%, return empty with professional referral
- No "did you mean..." hints — low-confidence suggestions could be treated as answers

---

## Task 8: Adversarial QA (Mandatory)

**Test cases:**

1. **Exact term queries:**
   - "PCAC recommendation" → Ch 4, not Ch 3
   - "503A Bulks List" → Ch 4, not Back Matter
   - "semaglutide" → Ch 3 (FDA-Approved), not Ch 5 or Back Matter
   - "BPC-157" → Ch 4, not Ch 5

2. **Semantic queries:**
   - "peptide that helps you lose weight" → Ch 3
   - "danger of buying online" → Ch 4
   - "why do I need a needle" → Ch 2

3. **Negative queries:**
   - "how to synthesize peptides at home" → no good match
   - "peptide therapy for cancer" → acknowledge limited evidence

**Strict requirement:** Exact-term queries must have correct chapter as top-1.

---

## Task 9: Re-run Benchmark and Compare

```bash
cd /home/dtfrost5/ai-agent-playbook-v2/books/peptide-patient-guide
python3 /home/dtfrost5/neuralmind/tests/benchmark/peptide_benchmark.py 2>&1
```

---

## Implementation Order

1. **T1 (Cold-start)** — foundation
2. **T2 (Vector-BM25 merge fix)** — ROOT CAUSE, enables T3
3. **T3 (BM25 hybrid scoring)** — depends on T2
4. **T4 (Prose context)** — depends on T2/T3 returning correct chapters
5. **T5 (Confidence)** — depends on T2/T3 for meaningful scores
6. **T6 (Ambiguity)** — depends on T5
7. **T7 (Negative fallback)** — depends on T5
8. **T8 (Adversarial QA)** — validates all above
9. **T9 (Benchmark)** — final verification

---

## Environment

- **Repo:** `/home/dtfrost5/neuralmind` (v3.10.0, main)
- **Peptide book:** `/home/dtfrost5/ai-agent-playbook-v2/books/peptide-patient-guide`
- **BM25 index:** `/home/dtfrost5/ai-agent-playbook-v2/books/peptide-patient-guide/graphify-out/neuralmind_turbovec/bm25_index.json` (315 docs)
- **Vector index:** `/home/dtfrost5/ai-agent-playbook-v2/books/peptide-patient-guide/graphify-out/neuralmind_turbovec/store.sqlite` (77 heading nodes)
- **Key files:** `neuralmind/core.py`, `neuralmind/embedder.py`, `neuralmind/context_selector.py`, `neuralmind/turbovec_backend.py`

---

## Standing Rules

1. **Never break existing tests.** Run `python3 -m pytest tests/ -x` before and after changes.
2. **Commit each fix separately** with clear commit messages.
3. **Re-run the benchmark after each fix** to measure improvement.
4. **Do NOT modify the peptide book content** — only NeuralMind code.
5. **Do NOT change the query interface** — `nm.query(question)` must keep the same signature.
6. **Adversarial QA is mandatory** — don't claim the fix works until adversarial queries pass.
7. **Rollback protocol:** If a fix causes any metric to revert vs baseline, revert that commit before proceeding.
