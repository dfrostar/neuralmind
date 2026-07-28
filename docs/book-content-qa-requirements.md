# Book Content QA System — Requirements Document

> **Project:** Book Content QA Engine  
> **Version:** 1.0-draft  
> **Date:** 2026-07-29  
> **Status:** Draft for review  
> **Audience:** Technical team, stakeholders, future maintainers  
> **Book Instance:** *The Peptide Patient's Guide* (~27,000 words, 8 chapters, 96 claims)

---

## 1. Executive Summary

The ai-agent-playbook-v2 book engine currently produces well-formed EPUBs with validated claims and accessibility — but it has **no content-level query capability**. An author, editor, or reviewer cannot ask "what does the book say about semaglutide's cardiovascular benefits?" and get a synthesized, section-level answer. The current NeuralMind code-graph index returns file pointers (55–57× token reduction on code repos of ~2,886 nodes / 132 communities), but it models *code structure*, not *book content*.

This document defines the requirements for a **Book Content QA System** — a complementary indexing and retrieval layer that enables semantic queries over book content at the section, claim, and cross-reference level.

---

## 2. High-Level Needs and Goals

| Need | Current State | Desired State |
|------|---------------|---------------|
| Section-level retrieval | NeuralMind returns file pointers only | Semantic chunk retrieval with ranked results |
| Content synthesis | None — manual re-reading required | Synthesized answers with provenance |
| Claim-level querying | Claims live in a flat markdown table | Query by tier, topic, status, chapter |
| Cross-chapter references | Manual search only | Automated cross-reference discovery |
| Readability QA | Per-chapter aggregate stats only | Section-level readability with regression alerts |
| Incremental rebuilds | Full NeuralMind rebuild takes ~5 min | Sub-2-min incremental index updates |

### 2.1 Primary Goals

1. **G1 — Semantic Content Retrieval:** Answer natural-language questions about book content with ranked, cited passages.
2. **G2 — Claim-Level Indexing:** Enable queries over 96 (and growing) evidence-tiered claims by topic, tier, status, and chapter.
3. **G3 — Cross-Reference Discovery:** Automatically detect and index mentions of topics, drugs, and claims across chapters.
4. **G4 — Query Latency:** Return results in <500 ms for interactive workflows.
5. **G5 — Incremental Indexing:** Support sub-2-minute incremental rebuilds as content changes.
6. **G6 — Readability Regression:** Alert on section-level readability drift away from FK 8.4 ± 1.7 target.

---

## 3. Stakeholders

| Stakeholder | Role | Key Concern |
|-------------|------|-------------|
| **Author** (Darren Frost) | Primary content creator | Fast retrieval of what the book says during drafting/editing |
| **Co-Author / SME** (Rye Estepp, MD) | Medical reviewer | Verify claim accuracy across chapters without re-reading whole book |
| **Editor** | Copy and content editor | Cross-reference consistency, gap detection |
| **Reader** (end-user) | Book consumer | Indirect — system produces better, more consistent books |
| **Publisher** (KDP) | Distribution platform | Compliance with AI disclosure and content policies |
| **Engineering Team** | Maintainers of the book engine | Integration cost, operational burden, maintainability |
| **Future Book Authors** | Users of the book engine template | Reusable QA infrastructure |

---

## 4. Functional Requirements

### 4.1 Content Ingestion

| ID | Requirement | Priority | Notes |
|----|-------------|----------|-------|
| FR-1 | Parse markdown chapters into semantic chunks (sections, subsections, claim blocks) | P0 | Each chunk must preserve provenance (chapter, section, line range) |
| FR-2 | Extract embedded claim markers (`<!-- claim: C-NNN -->`) from chapter text | P0 | Must link chapters back to claims-register.md rows |
| FR-3 | Parse claims-register.md into structured records (ID, claim text, tier, status, source, as_of) | P0 | Support the 96 existing claims and any additions |
| FR-4 | Extract cross-reference candidates (drug names, condition names, chapter references) | P1 | e.g., "Semaglutide" appears in chapters 2, 5, 6, 7 |
| FR-5 | Support multiple book instances within the same index | P2 | Book engine is multi-book |

### 4.2 Indexing

| ID | Requirement | Priority | Notes |
|----|-------------|----------|-------|
| FR-6 | Build a vector index over content chunks for semantic search | P0 | Embedding model TBD (minimum 768-dim) |
| FR-7 | Build a TF-IDF index as a fallback / hybrid ranker | P1 | For exact matches and interpretable results |
| FR-8 | Build a structured index over claims (tier, topic, chapter, status) | P0 | For faceted claim queries |
| FR-9 | Build a cross-reference index mapping entities → chapter locations | P1 | entity → [{chapter, section, offset}] |
| FR-10 | Support incremental index updates (add/modify/delete chunks) | P0 | Must not require full rebuild for single-chapter edit |
| FR-11 | Store index metadata (build timestamp, chunk count, embedding model, hash) | P2 | For reproducibility |

### 4.3 Querying

| ID | Requirement | Priority | Notes |
|----|-------------|----------|-------|
| FR-12 | Accept natural-language queries and return ranked chunks with similarity scores | P0 | e.g., "What does the book say about semaglutide's cardiovascular benefits?" |
| FR-13 | Support claim queries by tier, topic, chapter, status | P0 | e.g., "Show all RCT claims in Chapter 5" |
| FR-14 | Support entity cross-reference lookups | P1 | e.g., "Where does the book mention tirzepatide?" |
| FR-15 | Support hybrid search (vector + keyword) with weighted merging | P1 | Configurable α parameter for vector vs BM25 weighting |
| FR-16 | Return provenance for every result (chapter, section, line range, claim ID if applicable) | P0 | Critical for fact-checking workflow |
| FR-17 | Support query-level token reduction reporting | P2 | Mirror NeuralMind's 55-57× reduction metric |

### 4.4 Readability QA

| ID | Requirement | Priority | Notes |
|----|-------------|----------|-------|
| FR-18 | Compute readability metrics per content chunk (FK, FRE, SMOG, CL, ARI, DC, LW) | P1 | Reuse textstat from readability_sota.py |
| FR-19 | Flag chunks that drift outside FK 8.4 ± 1.7 target band | P1 | With configurable threshold |
| FR-20 | Report readability regression compared to previous index build | P2 | Store per-chunk baseline |

### 4.5 Rebuild & Maintenance

| ID | Requirement | Priority | Notes |
|----|-------------|----------|-------|
| FR-21 | Full rebuild in <2 minutes for current book size (~27K words, 10 files) | P0 | Current NeuralMind full rebuild: ~5 min — target improvement |
| FR-22 | Incremental rebuild in <30 seconds for single-chapter edit | P1 | Detect changed files via content hash |
| FR-23 | CLI command to trigger rebuild | P0 | Integrate with bookctl.py workflow |
| FR-24 | Health check endpoint / status command | P2 | Index freshness, chunk count, model version |

---

## 5. Non-Functional Requirements

### 5.1 Performance

| ID | Requirement | Target | Notes |
|----|-------------|--------|-------|
| NFR-1 | Query latency (p50) | <200 ms | Interactive author/editor experience |
| NFR-2 | Query latency (p95) | <500 ms | Acceptable upper bound |
| NFR-3 | Index build time (full) | <2 min | From ~27K words, 10 files |
| NFR-4 | Incremental build time | <30 s | Single-chapter edit |
| NFR-5 | Embedding throughput | >50 chunks/s | Local embedding model preferred |
| NFR-6 | Concurrent queries | 5 simultaneous | CLI is single-user; API may have more |

### 5.2 Scalability

| ID | Requirement | Target | Notes |
|----|-------------|--------|-------|
| NFR-7 | Max book size | 50+ chapters, 100K+ words | Future-proofing |
| NFR-8 | Max claims | 500+ | Current: 96. Expected to grow with multi-book |
| NFR-9 | Vector index capacity | 10,000+ chunks | ~200-300 chunks per book at current sizes |
| NFR-10 | Multi-book support | 5+ simultaneous books | Different books indexed independently |

### 5.3 Accuracy

| ID | Requirement | Target | Notes |
|----|-------------|--------|-------|
| NFR-11 | Top-3 retrieval recall | ≥90% | Ground-truth queries from editorial review |
| NFR-12 | Claim query precision | 100% | Claims are structured data, not fuzzy |
| NFR-13 | Cross-reference accuracy | ≥95% | Entity extraction must avoid false positives |
| NFR-14 | Hallucination guard | Zero hallucinated claims | Never synthesize a claim that doesn't exist |

### 5.4 Availability & Resilience

| ID | Requirement | Notes |
|----|-------------|-------|
| NFR-15 | The index is a local artifact — no online dependency for query | Works offline; embedding model loaded once at build |
| NFR-16 | Index corruption recovery via full rebuild | Full rebuild is a safe fallback |
| NFR-17 | Graceful degradation if embedding model unavailable | Fall back to TF-IDF-only search |

---

## 6. Constraints

| Constraint | Source | Impact |
|------------|--------|--------|
| **KDP Content Compliance** | Amazon KDP terms | No fabricated citations; every result must link to real claim rows with published-as-of dates |
| **Evidence Standards** | Editorial policy (Stage 0) | Only `confirmed`-tier claims asserted; system must surface tier metadata in every result |
| **Voice Conventions** | Editorial policy | Patient-facing tone (FK ~8.4); readability QA must not produce false alarms on intentionally simple prose |
| **Offline Operation** | Development workflow | No mandatory API calls at query time — embedding models run locally |
| **Python 3.12+ Toolchain** | Existing engine | Must integrate with existing Python toolchain; no new language runtimes |
| **Local SQLite Storage** | Book engine convention | Index storage should use SQLite (existing pattern in book engine) |
| **EPUB Build Pipeline** | bookctl.py | Index operations must not interfere with EPUB production |

---

## 7. Assumptions

| Assumption | Rationale |
|------------|-----------|
| A-1 | Embedding model fits in <2 GB RAM | Local deployment constraint |
| A-2 | Chapters are well-formed markdown with consistent heading hierarchy | Already enforced by heading_check gate |
| A-3 | Claims register format is stable | Already version-controlled with fixed schema |
| A-4 | The target audience (authors/editors) understands CLI tools | Current book engine is CLI-driven |
| A-5 | NeuralMind integration is via file-system convention | Not a direct API dependency — NeuralMind indexes the repo; QA system indexes the book's content directory |

---

## 8. Dependencies

| Dependency | Why | Version Constraint |
|------------|-----|--------------------|
| `sentence-transformers` | Text embedding for vector search | ≥ 2.2 | 
| `chromadb` or `sqlite-vec` | Vector index storage | TBD |
| `scikit-learn` | TF-IDF vectorizer (TfidfVectorizer) | ≥ 1.3 |
| `textstat` | Readability metrics (already used) | ≥ 0.7 |
| `pydantic` | Structured data models for claims and chunks | ≥ 2.0 |
| `numpy` | Vector similarity computations | ≥ 1.24 |

---

## 9. System Context Diagram

```
┌─────────────────────────────────────────────────────────┐
│                  Book Content QA System                   │
│                                                          │
│  ┌──────────┐   ┌───────────┐   ┌───────────────────┐   │
│  │ Chapters │──▶│  Content  │──▶│  Vector Index      │   │
│  │ (*.md)   │   │  Chunker  │   │  (embeddings)      │   │
│  └──────────┘   └───────────┘   └────────┬──────────┘   │
│                                          │              │
│  ┌──────────────────┐   ┌───────────┐   ┌───────────┐   │
│  │ Claims Register  │──▶│ Structured│──▶│ Query     │   │
│  │ (claims-*.md)    │   │ Indexer   │   │ Engine    │   │
│  └──────────────────┘   └───────────┘   └─────┬─────┘   │
│                                                │        │
│  ┌──────────────────┐   ┌───────────┐         │        │
│  │ NeuralMind       │◀──│ File      │◀────────┘        │
│  │ (code graph)     │   │ Router    │                   │
│  └──────────────────┘   └───────────┘                   │
└─────────────────────────────────────────────────────────┘
                            │
                            ▼
                  CLI / API Interface
                  (author queries, 
                   batch validation)
```

---

## 10. Integration Points

| Integration | Direction | Purpose |
|-------------|-----------|---------|
| **NeuralMind** | Read | File-level routing; QA system returns content within files NeuralMind identifies |
| **bookctl.py** | Command | Rebuild trigger (`bookctl.py index`) added to book engine workflow |
| **claims_check.py** | Read | Import claim validation logic; QA system respects evidence tiers |
| **readability_sota.py** | Read | Reuse `textstat` metrics per chunk (not just per chapter) |
| **draft_gate.py** | Extended | Add content-QA checks to the batch gate pipeline |

---

## 11. Glossary

| Term | Definition |
|------|------------|
| **Chunk** | A semantic unit of book content (section, subsection, or claim block) with provenance metadata |
| **Claim** | A structured, evidence-tiered assertion from claims-register.md |
| **Cross-reference** | An entity mention across two or more chapters (e.g., "semaglutide" in Ch 2, 5, 6, 7) |
| **Hybrid Search** | Combination of vector (semantic) and keyword (TF-IDF/BM25) retrieval with weighted merging |
| **Incremental Rebuild** | Updating only the index entries for changed files, not the entire index |
| **Token Reduction** | Ratio of source tokens to retrieved tokens (NeuralMind benchmark: 55-57×) |
| **Provenance** | The exact source location of a retrieved passage (chapter, section, line range) |
| **FK** | Flesch-Kincaid Grade Level — target 8.4 ± 1.7 (middle school) |
