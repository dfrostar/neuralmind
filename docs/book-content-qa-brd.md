# Book Content QA System — Business Requirements Document (BRD)

> **Project:** Book Content QA Engine  
> **Version:** 1.0-draft  
> **Date:** 2026-07-29  
> **Status:** Draft for review  
> **Audience:** Business stakeholders, investors, product managers

---

## 1. Business Case

### 1.1 The Problem

The ai-agent-playbook-v2 book engine produces high-quality, evidence-tiered books (*The Peptide Patient's Guide*, ~27,000 words, 96 claims). But the current workflow has three critical gaps:

1. **No content-level search.** An author revising Chapter 5 (Safety & Side Effects) cannot quickly ask "what did we say about pancreatitis risk?" and get a synthesized answer. They must re-read or grep manually.
2. **No cross-chapter visibility.** When a medical reviewer checks a claim about semaglutide's cardiovascular benefits (Claim C-003, SELECT trial), they cannot automatically discover that the same topic appears in Chapters 2, 5, 6, and 7.
3. **No claim-level orchestration.** The 96 claims live in a flat markdown table. There is no way to query "show all RCT-level claims in Chapter 5" or "find all claims updated before 2025."

These gaps compound as more books are added to the engine. What takes minutes today will take hours with 5+ books and 500+ claims.

### 1.2 The Opportunity

| Opportunity | Value |
|-------------|-------|
| **Faster editorial cycles** | Reduce cross-chapter consistency review from hours to seconds |
| **Higher content quality** | Automated gap detection, readability regression alerts, cross-reference consistency |
| **Multi-book scalability** | One QA system serves all book instances created by the engine |
| **Competitive differentiator** | Most self-publishing toolchains have no content QA; this is a distinguishing feature |
| **Reusable infrastructure** | Same QA engine can serve future books in the pipeline (AI Agent Playbook v3, etc.) |

### 1.3 Market Context

The book engine currently produces one title (*The Peptide Patient's Guide*). The roadmap includes multiple titles across health, technology, and reference categories. Without a content QA layer, each new book increases editorial overhead linearly. With the QA system, editorial effort scales sub-linearly because cross-referencing and claim tracking are automated.

**Self-publishing market (2026):**
- 3.5+ million books self-published annually via KDP alone
- Average time from draft to publication: 4-8 months for quality titles
- Key bottleneck: cross-chapter consistency and fact-checking
- Differentiator: evidence-tiered, auditable content (regulatory and medical contexts)

---

## 2. Stakeholder Analysis

| Stakeholder | Interest | Influence | Engagement Strategy |
|-------------|----------|-----------|---------------------|
| **Darren Frost** (Author / Developer) | Direct user of QA system during drafting | High | Co-design CLI queries; prioritize author workflows |
| **Rye Estepp, MD** (Co-Author / SME) | Cross-chapter claim verification | High | Focus on claim-level query precision; must trust 100% |
| **Editors** (future hires) | Consistency checking, gap detection | Medium | Fast query latency (<500 ms); readable results |
| **Engineering Team** | Maintenance burden, integration cost | Medium | Reuse existing patterns (SQLite, Python CLI); clean architecture |
| **KDP Reviewers** (indirect) | Content compliance | Low (indirect) | Every query result carries publication-as-of dates; no hallucinated claims |
| **Readers** (end-users) | Higher quality books | Indirect | No direct interaction; benefit from fewer inconsistencies |

---

## 3. Success Metrics

### 3.1 Primary KPIs

| Metric | Baseline | Target | Measurement Method |
|--------|----------|--------|-------------------|
| **Top-3 Retrieval Recall** | 0% (no system exists) | ≥90% | Ground-truth query set from editorial review sessions |
| **Cross-chapter consistency errors** | Manual detection only | 80% reduction | Compare pre/post QA system error counts across test queries |
| **Cross-reference discovery time** | 15-30 min per 3-way reference | <10 s | Timed trials with author |
| **Full-index rebuild time** | ~5 min (NeuralMind) | <2 min | `time` command on rebuild |
| **Query latency (p95)** | N/A | <500 ms | Instrumented benchmark suite |
| **Claim query precision** | N/A | 100% | Claim queries return exact matches only |
| **Editorial review cycle time** | ~4 hours per full-book consistency pass | <1 hour | Time-to-complete for defined consistency review tasks |

### 3.2 Secondary Metrics

| Metric | Target | Notes |
|--------|--------|-------|
| Author satisfaction (1-5) | ≥4.0 | Survey after first use |
| Index corruption recovery rate | 100% | Full rebuild is always a valid fallback |
| Incremental build adoption | First-time rebuild + incremental for edits | Tracked in build logs |
| System uptime (availability of query) | 100% | Local artifact — always available once built |

---

## 4. Risk Analysis

### 4.1 Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| **R-1: Hallucinated content** — QA system fabricates a claim that doesn't exist | Low | Critical | Every result carries provenance; structured claim queries return exact matches only; never synthesize new claims |
| **R-2: Embedding model drift** — Model update changes retrieval quality | Medium | High | Pin embedding model version; benchmark before upgrades; store model metadata in index |
| **R-3: KDP compliance violation** — Query result contains fabricated or misattributed evidence | Low | Critical | All results reference published claims with "as of" dates; structured data prevents fabrication |
| **R-4: Poor retrieval quality** — Vector search fails on domain-specific terms (peptide nomenclature) | Medium | High | Hybrid search (vector + TF-IDF/BM25); domain-specific embedding fine-tuning if needed |
| **R-5: Integration friction** — QA system conflicts with existing bookctl.py workflow | Low | Medium | Phase integration; CLI parity with bookctl.py conventions |
| **R-6: Index corruption** — Partial write or concurrent access corrupts the index | Low | Medium | SQLite WAL mode; content-addressed chunks; full rebuild fallback |
| **R-7: Scope creep** — Feature requests expand beyond content QA | High | Medium | Strict MoSCoW prioritization; v1.0 freeze on P0 features |

### 4.2 Risk Matrix

```
High │                    R-2    R-4
     │
 Med  │ R-6    R-7               R-1, R-3
     │
 Low  │ R-5
     │
     └──────────────────────────
       Low     Med     High
              Impact
```

---

## 5. Timeline and Milestones

### 5.1 Phase Plan

| Phase | Duration | Deliverable | Gates |
|-------|----------|-------------|-------|
| **Phase 0: Design** | 2 weeks | Architecture doc, data models, API spec | Design review with author + engineering |
| **Phase 1: Core Indexing** | 3 weeks | Content chunker + vector/TF-IDF indexer + CLI rebuild command | Indexes the peptide book correctly; spot-check 10 queries |
| **Phase 2: Query Engine** | 2 weeks | Natural-language query, claim queries, cross-reference lookup | Ground-truth benchmark: ≥90% top-3 recall |
| **Phase 3: Readability QA** | 1 week | Per-chunk readability + regression detection + gate integration | Matches readability_sota.py output |
| **Phase 4: Integration** | 1 week | bookctl.py index subcommand, draft_gate.py extension, NeuralMind hybrid routing | End-to-end workflow passes |
| **Phase 5: Validation** | 1 week | Full editorial review with QA system; bug fixes | Author & SME sign-off |
| **Phase 6: Documentation** | 0.5 week | User docs, API reference, maintenance guide | Review by engineering |

**Total: ~10.5 weeks**

### 5.2 Milestones

| Milestone | Date (Estimated) | Criteria |
|-----------|-----------------|----------|
| M1 — Design freeze | Week 2 | Architecture and data models signed off |
| M2 — Content indexed | Week 5 | Full peptide book indexed; chunk count matches expected sections |
| M3 — Query working | Week 7 | Author can run sample queries live |
| M4 — Gate integrated | Week 8 | `bookctl.py index` works end-to-end |
| M5 — Validation pass | Week 9 | ≥90% recall on ground-truth set |
| M6 — Ship | Week 10.5 | Documentation complete; merged to main |

---

## 6. Resource Requirements

### 6.1 Development Resources

| Resource | Quantity | Duration | Notes |
|----------|----------|----------|-------|
| Python Engineer | 1 FTE | 10.5 weeks | CLI and indexing development |
| Domain Expert (Author) | 0.2 FTE | 3 weeks intermittent | Ground-truth query creation, validation |
| Medical Reviewer | 0.1 FTE | 1 week | End-to-end validation on peptide book |

### 6.2 Computing Resources

| Resource | Specification | Purpose |
|----------|---------------|---------|
| Development Machine | Any modern x86/ARM | Development and testing |
| Embedding Model | <2 GB RAM, <500 MB disk | Local inference (e.g., sentence-transformers/all-MiniLM-L6-v2) |
| Storage | <100 MB per book index | SQLite + vector storage |

### 6.3 Software Stack

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Language | Python 3.12+ | Existing engine standard |
| Vector Storage | SQLite + sqlite-vec or ChromaDB | Local, no server process |
| Embedding | sentence-transformers (MiniLM or instructor) | Good quality/speed trade-off |
| TF-IDF | scikit-learn TfidfVectorizer | Proven, lightweight |
| Data Validation | pydantic | Structured claim/chunk models |
| Readability | textstat (already in engine) | Reuse existing dependency |

### 6.4 Budget Estimate

| Category | Estimate | Notes |
|----------|----------|-------|
| Development | ~10.5 weeks × 1 FTE | Internal resource cost |
| Embedding Model Inference | $0 (local) | No API costs at query time |
| Storage | Negligible | ~100 MB per indexed book |
| Third-party libraries | $0 | All open-source |
| **Total Direct Cost** | **Development time only** | No external spend |

---

## 7. Go-To-Market / Adoption

### 7.1 Rollout Strategy

1. **Internal dogfood** — Author uses QA system during final stages of *The Peptide Patient's Guide* editing
2. **Template extraction** — Separate QA configuration into reusable book-engine module
3. **Documentation** — Add to engine README and template docs
4. **Future books** — QA system enabled by default for all scaffolded books

### 7.2 Adoption Criteria

| Criterion | How Measured |
|-----------|-------------|
| Author uses QA system in daily workflow | Session logs show ≥3 queries per editing session |
| Medical reviewer uses claim queries for verification | ≥1 full claim audit performed via QA system |
| New scaffolded book has QA enabled | QA build step in default book.yaml |

---

## 8. Competitive Landscape

| Competitor / Alternative | How It Addresses Content QA | Gap |
|--------------------------|----------------------------|-----|
| **Grep / Manual Search** | Full-text search across .md files | No semantic understanding, no structured claim queries, no cross-references |
| **NeuralMind (current)** | Code-graph index, file-level retrieval | Returns file pointers only; no content synthesis; can't answer "what does the book say about X?" |
| **Scrivener** | Corkboard + keyword search | Proprietary format; not scriptable; no evidence-tiered claims |
| **Obsidian / Roam** | Graph view + backlinks | Manual linking; no automated claim extraction; no readability QA |
| **Notion AI** | Q&A over workspace | Requires online access; no local deployment; no evidence tiering |
| **AI-powered writing tools (Grammarly, ProWritingAid)** | Style and grammar checking | No domain-specific content QA; no claim-level indexing |
| **Book Content QA System (THIS)** | Semantic retrieval + claim indexing + cross-references + readability regression | All capabilities in one local CLI tool, integrated with existing book engine |

---

## 9. Assumptions

| Assumption | Impact if Wrong |
|------------|-----------------|
| The embedding model (sentence-transformers) provides adequate semantic quality for medical/nomenclature-heavy text | May need domain-adapted model or fine-tuning |
| Authors and editors are comfortable with CLI | Would need a web/UI layer |
| The current book engine's Python 3.12+ constraint holds | No platform constraint issues |
| SQLite is sufficient for multi-book vector storage | May need PostgreSQL/pgvector at 20+ books |
| Local-only deployment is acceptable | No compliance or data sensitivity issues |

---

## 10. Decision Log

| Decision | Rationale | Date |
|----------|-----------|------|
| Local embedding inference over API | Query-time latency, offline capability | 2026-07-29 |
| Hybrid search (vector + TF-IDF) over pure vector | Domain-specific terminology degrades pure vector search | 2026-07-29 |
| SQLite-based storage over external vector DB | Zero-dependency, matches engine conventions | 2026-07-29 |
| CLI-first, API second | Current engine is CLI-driven; UI can come later | 2026-07-29 |

---

*End of Business Requirements Document*
