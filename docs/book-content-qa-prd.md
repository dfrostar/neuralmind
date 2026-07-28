# Book Content QA System — Product Requirements Document (PRD)

> **Project:** Book Content QA Engine  
> **Version:** 1.0-draft  
> **Date:** 2026-07-29  
> **Status:** Draft for review  
> **Audience:** Product managers, developers, designers, QA engineers

---

## 1. Product Vision

**For authors, editors, and medical reviewers working with evidence-tiered book content, the Book Content QA System is a local CLI tool that enables semantic search, claim-level querying, and cross-reference discovery across book content — eliminating the need to manually re-read chapters or grep markdown files for fact-checking and consistency review.**

The system sits alongside NeuralMind's code-graph index, extending retrieval from *file-level pointers* to *content-level answers*. It transforms a book from a collection of markdown files into a queryable knowledge base — without any online dependencies, without vendor lock-in, and without fabricating claims.

---

## 2. Product Positioning

| Attribute | Description |
|-----------|-------------|
| **Product Name** | Book Content QA System |
| **Tagline** | *Ask your book what it says.* |
| **Positioning** | Complementary content-level indexing layer for the ai-agent-playbook-v2 book engine |
| **Primary Value** | From "find the file" to "answer the question" |
| **Key Differentiator** | Claim-level precision (100% exact match) + semantic chunk retrieval (≥90% recall) |
| **Deployment** | CLI tool, integrated with `bookctl.py`, no server needed |
| **License** | MIT (same as book engine) |

---

## 3. User Personas

### P1: Author (Darren Frost)

| Attribute | Detail |
|-----------|--------|
| **Role** | Primary content creator and developer of the book engine |
| **Technical Level** | High — comfortable with CLI, Python, markdown |
| **Primary Workflow** | Drafting, editing, and restructuring chapters |
| **Pain Points** | Can't ask "what does the book say about X?"; must grep or re-read |
| **Needs** | Fast semantic search with provenance; cross-chapter reference discovery |
| **Frequency of Use** | Multiple times per editing session (3-10+ queries) |

**Example queries an author would ask:**
- "What does the book say about the SELECT trial?"
- "Show me all places where BPC-157 is mentioned."
- "Which chapters discuss GLP-1 mechanism of action?"
- "Find the section about semaglutide's 14.9% weight loss claim."

### P2: Medical Reviewer / SME (Rye Estepp, MD)

| Attribute | Detail |
|-----------|--------|
| **Role** | Subject-matter expert verifying clinical accuracy |
| **Technical Level** | Moderate — comfortable with CLI but prefers focused workflows |
| **Primary Workflow** | Verifying claims against evidence, checking cross-chapter consistency |
| **Pain Points** | Must verify each claim individually across chapters; no way to query "all RCT claims in Chapter 5" |
| **Needs** | Claim-level precision; faceted claim queries by tier, topic, status; 100% accuracy |
| **Frequency of Use** | Batch use during review cycles |

**Example queries a medical reviewer would ask:**
- "Show all RCT-tier claims in Chapter 5."
- "Which claims reference PMID 33567185?"
- "Are there any claims with status 'pending' that should be caught pre-publication?"
- "List all claims about tirzepatide."

### P3: Editor

| Attribute | Detail |
|-----------|--------|
| **Role** | Copy and content editor ensuring consistency |
| **Technical Level** | Low-Moderate — may need simplified interface |
| **Primary Workflow** | Checking cross-references, voice consistency, terminology |
| **Pain Points** | Manual cross-reference checking is tedious and error-prone |
| **Needs** | Readable results, cross-reference maps, readability regression alerts |
| **Frequency of Use** | Once per editorial cycle |

**Example queries an editor would ask:**
- "Which chapters use 'semaglutide' versus 'Ozempic'?"
- "Show readability drift for Chapter 4 compared to last build."
- "List all forward references (e.g., 'as discussed in Chapter 6')."

### P4: Future Book Author / Template Consumer

| Attribute | Detail |
|-----------|--------|
| **Role** | Author using the book engine template for a new title |
| **Technical Level** | Varies |
| **Primary Workflow** | Scaffolding a new book, adding chapters, building EPUB |
| **Pain Points** | Doesn't know the QA system exists or how to use it |
| **Needs** | QA enabled by default; clear documentation; "it just works" |
| **Frequency of Use** | Intermittent during book development |

---

## 4. User Stories

### 4.1 Content Querying

| ID | User Story | Acceptance Criteria | Priority |
|----|-----------|---------------------|----------|
| US-001 | As an **author**, I want to query a book with a natural-language question so that I can find relevant passages without re-reading entire chapters. | 1. CLI command: `bookctl.py query <book> "natural language question"` returns top-5 chunks with similarity scores, chapter, section, and line range. 2. Response time <500 ms. 3. ≥90% top-3 recall on ground-truth set. | P0 |
| US-002 | As an **author**, I want each query result to show provenance (chapter, section heading, line range) so that I can verify the source. | 1. Every result includes `chapter`, `section`, `lines`, and `file_path`. 2. Claim-bearing results include `claim_id`, `tier`, and `status`. | P0 |
| US-003 | As an **author**, I want to limit queries to specific chapters so that I can focus my search. | 1. `--chapter 05` flag filters results to that chapter. 2. Combined filter: `--chapter 05 --tier rct`. | P1 |

### 4.2 Claim Querying

| ID | User Story | Acceptance Criteria | Priority |
|----|-----------|---------------------|----------|
| US-004 | As a **medical reviewer**, I want to query claims by evidence tier so that I can focus verification on RCT-level claims. | 1. `bookctl.py query <book> --claim-tier rct` returns all RCT claims. 2. Results are grouped by chapter. 3. Precision: 100% (exact match only). | P0 |
| US-005 | As a **medical reviewer**, I want to query claims by status so that I can catch unverified claims before publication. | 1. `bookctl.py query <book> --claim-status pending` returns all unverified claims. 2. Status values: confirmed, plausible, pending, refuted. | P0 |
| US-006 | As a **medical reviewer**, I want to find all claims citing a specific source (PMID/URL) so that I can verify source integrity. | 1. `bookctl.py query <book> --source "PMID 33567185"` returns all claims citing that source. | P1 |
| US-007 | As a **medical reviewer**, I want to see the full claim record (claim text, tier, source, as-of date) directly in query results so that I don't need to open claims-register.md separately. | 1. Claim query results include full structured record. 2. `--verbose` flag shows all fields. | P1 |

### 4.3 Cross-Reference Discovery

| ID | User Story | Acceptance Criteria | Priority |
|----|-----------|---------------------|----------|
| US-008 | As an **editor**, I want to find all chapters that mention a specific entity (drug, condition, term) so that I can verify cross-reference consistency. | 1. `bookctl.py xref <book> "semaglutide"` returns `{ch2: [sections...], ch5: [sections...], ch6: [sections...]}`. 2. Results show section heading and mention count per chapter. | P1 |
| US-009 | As an **author**, I want to discover implicit cross-references (topics related across chapters) automatically so that I can add explicit cross-reference links. | 1. `bookctl.py xref <book> --related` returns entity co-occurrence map. 2. Configurable co-occurrence threshold. | P2 |

### 4.4 Readability QA

| ID | User Story | Acceptance Criteria | Priority |
|----|-----------|---------------------|----------|
| US-010 | As an **editor**, I want readability metrics per content chunk (not just per chapter) so that I can identify difficult passages at a finer granularity. | 1. `bookctl.py readability <book>` shows per-chunk FK, FRE, SMOG, CL, ARI, DC, LW. 2. Chunks outside FK 8.4 ± 1.7 are flagged. | P1 |
| US-011 | As an **editor**, I want readability regression alerts when a chunk's FK grade changes significantly between builds. | 1. `bookctl.py readability <book> --regression` compares against last build. 2. Alerts on changes >1.0 FK grade. | P2 |

### 4.5 Indexing & Rebuild

| ID | User Story | Acceptance Criteria | Priority |
|----|-----------|---------------------|----------|
| US-012 | As an **author**, I want to rebuild the index after editing content so that queries reflect my latest changes. | 1. `bookctl.py index <book> --rebuild` performs full rebuild in <2 min. 2. `bookctl.py index <book>` (incremental) detects changed files and updates in <30 s. | P0 |
| US-013 | As an **engineering maintainer**, I want the index to include metadata (build time, model version, chunk count) so that I can debug issues. | 1. `bookctl.py index <book> --status` shows index metadata. 2. Chunk count matches expected sections. | P2 |

### 4.6 Hybrid Retrieval

| ID | User Story | Acceptance Criteria | Priority |
|----|-----------|---------------------|----------|
| US-014 | As an **author**, I want hybrid search (vector + keyword) by default so that I get relevant results even for domain-specific terms. | 1. Default query mode blends vector similarity with TF-IDF/BM25. 2. Configurable α weight parameter. | P1 |
| US-015 | As an **author**, I want to force keyword-only search when I need exact term matching. | 1. `--mode keyword` flag disables vector search. 2. Useful for drug names and PMIDs. | P2 |

---

## 5. Feature Prioritization (MoSCoW)

| MoSCoW | Feature | User Stories | Effort Estimate |
|--------|---------|-------------|-----------------|
| **MUST** | Natural-language semantic query | US-001, US-002 | 3 weeks |
| **MUST** | Claim-level indexing + query by tier/status | US-004, US-005 | 2 weeks |
| **MUST** | Full index rebuild | US-012 (rebuild) | 1 week |
| **MUST** | Provenance in results | US-002 | 0.5 week (part of query) |
| **MUST** | Chunking: parse markdown into semantic segments | FR-1, FR-2 | 1 week |
| **SHOULD** | Hybrid search (vector + keyword) | US-014 | 1 week |
| **SHOULD** | Incremental index rebuild | US-012 (incremental) | 1.5 weeks |
| **SHOULD** | Cross-reference entity discovery | US-008 | 1.5 weeks |
| **SHOULD** | Claim query by source (PMID) | US-006 | 0.5 week |
| **SHOULD** | Per-chunk readability metrics | US-010 | 0.5 week |
| **COULD** | Cross-reference: related topics | US-009 | 1 week |
| **COULD** | Readability regression alerts | US-011 | 0.5 week |
| **COULD** | Keyword-only mode flag | US-015 | 0.5 week |
| **COULD** | Verbose claim records | US-007 | 0.25 week (part of claim query) |
| **WON'T (v1.0)** | Web UI / dashboard | — | Deferred to v2.0 |
| **WON'T (v1.0)** | API server mode | — | Deferred to v2.0 |
| **WON'T (v1.0)** | Multi-user access control | — | Deferred to v2.0 |
| **WON'T (v1.0)** | Auto-generated cross-reference links in EPUB | — | Deferred to v2.0 |

### Effort Summary
| Category | Effort |
|----------|--------|
| MUST | ~6.5 weeks |
| SHOULD | ~5 weeks |
| COULD | ~2.25 weeks |
| **Total (MUST + SHOULD)** | **~11.5 weeks** |

---

## 6. UI/UX Requirements

### 6.1 CLI Interface

The QA system is primarily CLI-driven, consistent with the existing book engine (`bookctl.py`).

```
# Query book content
bookctl.py query <book-slug> "What does the book say about semaglutide's cardiovascular benefits?"
bookctl.py query <book-slug> --chapter 05 "pancreatitis risk"
bookctl.py query <book-slug> --claim-tier rct
bookctl.py query <book-slug> --claim-status pending

# Cross-reference lookup
bookctl.py xref <book-slug> "semaglutide"
bookctl.py xref <book-slug> --related

# Readability report
bookctl.py readability <book-slug>
bookctl.py readability <book-slug> --regression

# Index management
bookctl.py index <book-slug>           # incremental rebuild
bookctl.py index <book-slug> --rebuild  # full rebuild
bookctl.py index <book-slug> --status   # index metadata

# Hybrid search tuning
bookctl.py query <book-slug> --alpha 0.3 "my query"
bookctl.py query <book-slug> --mode keyword "PMID 33567185"
```

### 6.2 Results Display

**Natural-language query results:**
```
┌────────────────────────────────────────────────────────────────┐
│  Query: "what does the book say about semaglutide's            │
│           cardiovascular benefits?"                            │
├────────────────────────────────────────────────────────────────┤
│  1. [0.92] Ch 2: FDA-Approved Peptides                        │
│     Section: Cardiovascular Outcomes                         │
│     Lines: 142-148                                            │
│     ─────────────────────────────────────────────────────      │
│     "Semaglutide reduced major adverse cardiovascular          │
│      events (MACE) by 20% vs placebo in adults..."             │
│     └ Claim C-003 (rct / confirmed / PMID 37952131)           │
│                                                               │
│  2. [0.78] Ch 5: Safety & Side Effects                        │
│     Section: Cardiovascular Safety                          │
│     Lines: 34-40                                              │
│     ─────────────────────────────────────────────────────      │
│     "The SELECT trial followed 17,604 patients for..."         │
│     └ Claim C-090 (rct / confirmed / PMID 37952131)           │
│                                                               │
│  3. [0.65] Ch 6: Regulatory Landscape                         │
│     Section: Insurance Coverage                              │
│     Lines: 89-93                                              │
│     ─────────────────────────────────────────────────────      │
│     "GLP-1 agonists with demonstrated cardiovascular..."       │
│     └ Claim C-085 (other / confirmed)                         │
│                                                               │
│  Results: 5 total | 2.5s | α=0.5 hybrid                       │
└────────────────────────────────────────────────────────────────┘
```

**Claim query results (table format):**
```
┌────────┬────────────────────────────────┬──────┬───────────┬──────────────────┐
│ ID     │ Claim                          │ Tier │ Status    │ Chapter          │
├────────┼────────────────────────────────┼──────┼───────────┼──────────────────┤
│ C-003  │ Semaglutide reduced MACE...    │ rct  │ confirmed │ Ch 2             │
│ C-090  │ SELECT trial...                │ rct  │ confirmed │ Ch 5             │
│ C-019  │ Pancreatitis risk...           │ meta │ confirmed │ Ch 5             │
└────────┴────────────────────────────────┴──────┴───────────┴──────────────────┘
3 results filtered by: tier=rct
```

**Cross-reference result:**
```
Entity: "semaglutide"
Found in 4 chapters, 6 sections:

  Ch 2: FDA-Approved Peptides
    ├── 2.3 Cardiovascular Outcomes (3 mentions)
    └── 2.1 GLP-1 Agonists (2 mentions)
  Ch 5: Safety & Side Effects
    ├── 5.2 GLP-1 Safety Profile (4 mentions)
    └── 5.4 Drug Interactions (1 mention)
  Ch 6: Regulatory Landscape
    └── 6.1 Insurance Coverage (2 mentions)
  Ch 7: Future of Peptide Therapy
    └── 7.1 Next-Generation Therapies (1 mention)
```

---

## 7. Integration Requirements

### 7.1 NeuralMind Integration

| Requirement | Detail |
|-------------|--------|
| **Pattern** | Complementary indexing — NeuralMind indexes code structure; QA system indexes book content |
| **Hybrid Routing Workflow** | 1. NeuralMind query returns relevant file paths → 2. QA system performs content-level search within those files → 3. Combined result: file pointer + content chunk |
| **Data Flow** | NeuralMind writes to `.neuralmind/` directory; QA system writes to `.bookqa/` directory. No shared state. |
| **Activation** | Author chooses which engine to query (`bookctl.py nm-query` vs `bookctl.py query`), or combined (`bookctl.py query --hybrid`) |

### 7.2 Claims Register Integration

| Requirement | Detail |
|-------------|--------|
| **Input** | Parse `reports/research/claims-register.md` — structured markdown table with `ID`, `Claim`, `Tier`, `Status`, `Source`, `As of` |
| **Linkage** | Chapter-level `<!-- claim: C-NNN -->` markers map content chunks to claim records |
| **Validation** | Ensure every claim referenced in chapter text exists in the register; flag orphaned claim markers |
| **Output** | Claim records indexed in structured DB (pydantic models → SQLite) for facet queries |

### 7.3 Readability Tools Integration

| Requirement | Detail |
|-------------|--------|
| **Library** | Reuse `textstat` (already in `readability_sota.py`) |
| **Granularity** | Compute readability at chunk level (not just chapter level) |
| **Metrics** | FK Grade, FRE, SMOG, CL Index, ARI, DC Score, Linsear Write — same 7 metrics as readability_sota.py |
| **Baseline** | Store per-chunk readability baseline; flag regression on rebuild |

### 7.4 bookctl.py Integration

| Requirement | Detail |
|-------------|--------|
| **New Subcommands** | `bookctl.py index`, `bookctl.py query`, `bookctl.py xref`, `bookctl.py readability` |
| **Pipeline Hook** | QA rebuild automatically triggered on `bookctl.py build` (configurable in book.yaml) |
| **Gate Extension** | `draft_gate.py` extended to include content-QA checks (optional, enabled via flag) |

---

## 8. Non-Functional Product Requirements

| Requirement | Specification | Rationale |
|-------------|--------------|-----------|
| **Offline Capability** | All operations work without internet | Development often occurs offline; no API dependencies |
| **Startup Time** | CLI initializes in <1 second | Embedding model loaded on first query, not at startup |
| **Memory Footprint** | <2 GB RAM (peak during indexing) | Embedding model loaded/unloaded; vector storage is disk-backed |
| **Disk Usage** | <100 MB per indexed book | Local SQLite + vector index |
| **Failure Mode** | Informative error messages, not stack traces | Target audience includes non-developers |
| **Graceful Degradation** | If embedding model missing, fall back to TF-IDF-only | Never refuse to query |

---

## 9. Release Criteria

| Criterion | Gate |
|-----------|------|
| All P0 (MUST) user stories passing acceptance criteria | Release gate 1 |
| ≥90% top-3 recall on ground-truth query set (20 queries) | Release gate 2 |
| 100% precision on claim queries (all 96 claims returned correctly) | Release gate 3 |
| Full rebuild <2 min, incremental <30 s on peptide book | Release gate 4 |
| Query latency p95 <500 ms | Release gate 5 |
| All P1 (SHOULD) user stories implemented | Release gate 6 (v1.0) |
| Documentation complete (user guide + API reference) | Release gate 7 |
| Author and SME sign-off | Release gate 8 |

---

*End of Product Requirements Document*
