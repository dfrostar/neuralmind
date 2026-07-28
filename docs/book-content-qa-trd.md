# Book Content QA System — Technical Requirements Document (TRD)

> **Project:** Book Content QA Engine  
> **Version:** 1.0-draft  
> **Date:** 2026-07-29  
> **Status:** Draft for review  
> **Audience:** Engineering team, architects, maintainers

---

## 1. System Architecture

### 1.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                      BOOK CONTENT QA SYSTEM                          │
│                                                                      │
│  ┌───────────────────┐    ┌──────────────────┐                     │
│  │   Content Chunker  │───▶│   Vector Index   │                     │
│  │   (semantic split) │    │   (embeddings)   │                     │
│  └───────────────────┘    └────────┬─────────┘                     │
│                                     │                               │
│  ┌───────────────────┐    ┌────────▼─────────┐    ┌──────────────┐ │
│  │  Structured Indexer │───▶│   Query Engine   │◀───│   CLI Layer  │ │
│  │  (claims, xrefs)   │    │   (rank + merge) │    │  (bookctl.py) │ │
│  └───────────────────┘    └────────┬─────────┘    └──────────────┘ │
│                                     │                               │
│  ┌───────────────────┐    ┌────────▼─────────┐                     │
│  │  Readability QA    │◀───│   Storage Layer  │                     │
│  │  (per-chunk stats) │    │   (SQLite + vec)  │                     │
│  └───────────────────┘    └──────────────────┘                     │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  NeuralMind Integration Layer (file routing → content QA)    │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.2 Component Descriptions

| Component | Responsibility | Key Classes / Modules |
|-----------|---------------|----------------------|
| **Content Chunker** | Parse markdown chapters into semantic chunks; extract claim markers | `Chunker`, `Chunk`, `ChunkMetadata` |
| **Structured Indexer** | Parse claims register; index structured claims and cross-references | `ClaimIndexer`, `CrossReferenceIndexer` |
| **Vector Index** | Compute and store embeddings for each chunk; similarity search | Embedding model + vector store |
| **TF-IDF Index** | Build and query TF-IDF matrix for keyword-level fallback | `scikit-learn.TfidfVectorizer` |
| **Query Engine** | Accept queries, route to appropriate index(es), rank, merge, return | `QueryEngine`, `Ranker`, `Result` |
| **Readability QA** | Compute per-chunk readability; compare against baseline | `ReadabilityAnalyzer` (wraps textstat) |
| **CLI Layer** | Parse `bookctl.py` subcommands; format output | Integrated into `bookctl.py` |
| **Storage Layer** | SQLite database for claims, chunks, cross-references, metadata; vector store plugin | `sqlite-vec` or ChromaDB |

---

## 2. Data Models

### 2.1 Content Chunk

```python
@dataclass
class ContentChunk:
    """A semantic unit of book content with full provenance."""
    chunk_id: str              # e.g., "peptide-patient-guide/02/003"
    book_slug: str             # e.g., "peptide-patient-guide"
    chapter_id: str            # e.g., "02"
    chapter_title: str         # e.g., "FDA-Approved Peptides"
    section_heading: str       # e.g., "Cardiovascular Outcomes"
    heading_level: int         # e.g., 2 (## heading)
    content: str               # The chunk's text content
    start_line: int            # Line number in source file (1-indexed)
    end_line: int              # Line number in source file (inclusive)
    word_count: int            # Word count of chunk
    claim_ids: list[str]       # Associated claims, e.g., ["C-003", "C-090"]
    embedding: list[float] | None  # Vector embedding (None before indexing)
    content_hash: str          # SHA-256 of content for change detection
    created_at: datetime
    updated_at: datetime
```

### 2.2 Claim Record

```python
@dataclass
class ClaimRecord:
    """A structured, evidence-tiered claim from claims-register.md."""
    claim_id: str              # e.g., "C-003"
    book_slug: str
    chapter_id: str            # Chapter where claim is asserted
    claim_text: str            # Full claim text
    tier: str                  # Evidence tier: rct, preclinical, clinical, meta-analysis, regulatory, observational, other
    status: str                # confirmed, plausible, pending, refuted
    source: str                # Source citation (may include PMID)
    as_of_date: str            # "YYYY-MM" format
    chapter_chunk_ids: list[str]  # Content chunks that reference this claim
```

### 2.3 Cross-Reference

```python
@dataclass
class CrossReference:
    """An entity mention across multiple book locations."""
    entity_id: str             # Normalized entity name, e.g., "semaglutide"
    entity_type: str           # drug, condition, concept, claim
    mentions: list[EntityMention]
    
@dataclass
class EntityMention:
    """A single mention of an entity in a specific location."""
    chunk_id: str
    chapter_id: str
    section: str
    offset: int                # Character offset in chunk
    context: str               # Surrounding text window
```

### 2.4 Readability Record

```python
@dataclass
class ReadabilityRecord:
    """Readability metrics for a single content chunk."""
    chunk_id: str
    book_slug: str
    flesch_reading_ease: float
    flesch_kincaid_grade: float
    smog_index: float
    coleman_liau_index: float
    automated_readability_index: float
    dale_chall_readability_score: float
    linsear_write_formula: float
    word_count: int
    baseline_fk: float | None   # Previous build's FK for regression detection
```

### 2.5 Index Metadata

```python
@dataclass
class IndexMetadata:
    """Metadata about the index build."""
    book_slug: str
    build_version: str           # Semantic version of QA system
    embedding_model: str         # Model name, e.g., "all-MiniLM-L6-v2"
    chunk_count: int
    claim_count: int
    build_time_seconds: float
    build_timestamp: datetime
    content_hash: str            # Aggregate hash of indexed content
    is_full_rebuild: bool
```

### 2.6 ER Diagram

```
┌─────────────────┐       ┌──────────────────┐
│   ContentChunk   │       │   ClaimRecord    │
├─────────────────┤       ├──────────────────┤
│ chunk_id (PK)   │◄──────│ claim_id (PK)    │
│ book_slug       │       │ chunk_ids (FK)   │──┐
│ chapter_id      │       │ tier             │  │
│ content         │       │ status           │  │
│ claim_ids (FK)  │──┐    │ source           │  │
│ embedding       │  │    └──────────────────┘  │
│ content_hash    │  │                          │
└─────────────────┘  │    ┌──────────────────┐  │
                     ├────│ CrossReference   │  │
                     │    ├──────────────────┤  │
                     └───▶│ entity_id (PK)   │  │
                          │ chunk_ids (FK)   │◄─┘
                          │ entity_type      │
                          └──────────────────┘
                                │
                          ┌─────▼────────┐
                          │ReadabilityRec│
                          ├──────────────┤
                          │ chunk_id (PK)│
                          │ fk_grade     │
                          │ baseline_fk  │
                          └──────────────┘
```

---

## 3. API Specifications

### 3.1 CLI Commands (bookctl.py integration)

| Command | Parameters | Description | Response |
|---------|-----------|-------------|----------|
| `bookctl.py index <book>` | `--rebuild` (full), `--force` | Build or update content index | Build summary JSON |
| `bookctl.py query <book> <query>` | `--chapter`, `--top-k` (default 5), `--alpha` (0-1 hybrid weight), `--mode` (hybrid/vector/keyword), `--claim-tier`, `--claim-status`, `--verbose` | Query book content | Ranked results list |
| `bookctl.py xref <book> <entity>` | `--related`, `--min-mentions` (default 2) | Cross-reference lookup | Entity mention map |
| `bookctl.py readability <book>` | `--regression`, `--threshold` (default 1.7) | Readability report | Per-chunk metrics table |
| `bookctl.py index <book> --status` | none | Index metadata | Build metadata |

### 3.2 Internal Python API

```python
class BookContentQA:
    """Main entry point for the QA system."""
    
    def __init__(self, book_dir: Path, config: QaConfig):
        ...
    
    # Indexing
    def index(self, rebuild: bool = False) -> IndexMetadata: ...
    def increment_index(self, changed_files: list[Path]) -> IndexMetadata: ...
    
    # Querying
    def query(
        self, 
        text: str,
        chapter_filter: str | None = None,
        top_k: int = 5,
        alpha: float = 0.5,       # 0 = pure keyword, 1 = pure vector
        mode: str = "hybrid",
        claim_tier: str | None = None,
        claim_status: str | None = None,
    ) -> QueryResult: ...
    
    def query_claims(
        self,
        tier: str | None = None,
        status: str | None = None,
        chapter: str | None = None,
        source: str | None = None,
    ) -> list[ClaimRecord]: ...
    
    # Cross-references
    def cross_reference(self, entity: str) -> CrossRefResult: ...
    def related_entities(self, min_cooccurrence: int = 2) -> list[RelatedEntity]: ...
    
    # Readability
    def readability_report(
        self,
        detect_regression: bool = False,
        fk_threshold: float = 1.7,
    ) -> ReadabilityReport: ...
    
    # Status
    def index_status(self) -> IndexMetadata: ...
```

### 3.3 QueryResult Data Structure

```python
@dataclass
class QueryResult:
    query: str
    mode: str                # hybrid, vector, keyword
    alpha: float | None
    results: list[RankedChunk]
    total_results: int
    query_time_ms: float
    token_reduction_ratio: float | None  # Source tokens / retrieved tokens

@dataclass 
class RankedChunk:
    rank: int
    score: float
    chunk: ContentChunk
    highlighted_text: str          # Query-relevant excerpt
    claims: list[ClaimRecord]      # Associated claims, if any
```

### 3.4 Configuration (book.yaml extension)

```yaml
# Existing book.yaml fields...
# New QA configuration:
qa:
  enabled: true
  embedding_model: all-MiniLM-L6-v2
  chunking:
    strategy: heading          # heading, paragraph, fixed
    min_chunk_words: 50
    max_chunk_words: 500
  query:
    default_mode: hybrid
    default_alpha: 0.5
    top_k: 5
  readability:
    target_fk: 8.4
    fk_tolerance: 1.7
    detect_regression: true
    regression_threshold: 1.0
  storage:
    backend: sqlite            # sqlite (initial), chroma (future)
    path: .bookqa/
```

---

## 4. Component Design

### 4.1 Content Chunker

**Input:** List of markdown files (chapters, front matter, back matter)

**Chunking Strategy:** Heading-based semantic segmentation

```
Algorithm: HEADING_CHUNK
  Input: markdown content, heading level threshold (default: H2)
  
  1. Parse markdown AST or use regex for heading detection
  2. For each heading >= threshold:
     a. Create a new chunk starting at this heading
     b. Include all content until the next heading at same or higher level
  3. For orphan content before first heading → assign to chapter-level intro chunk
  4. Extract <!-- claim: C-NNN --> markers → map to claim_ids
  5. Compute content_hash (SHA-256)
  6. Return list of ContentChunk objects
```

**Example:** Chapter 2 — FDA-Approved Peptides (~3,022 words)
```
Chunk 2-001: Heading "FDA-Approved Peptides" (intro, lines 1-20)
Chunk 2-002: Heading "GLP-1 Receptor Agonists" (lines 21-85) → claims C-001, C-002, C-042
Chunk 2-003: Heading "Cardiovascular Outcomes" (lines 86-110) → claims C-003, C-090
Chunk 2-004: Heading "Weight Management" (lines 111-150) → claims C-002, C-004
Chunk 2-005: Heading "Comparison of Agents" (lines 151-200) → claims C-005, C-006, C-043
Chunk 2-006: Heading "Emerging Therapies" (lines 201-240) → claims C-007, C-008, C-044
Chunk 2-007: Heading "Safety Considerations" (lines 241-280) → claims C-009, C-010
Chunk 2-008: Heading "Beyond GLP-1" (lines 281-320) → claims C-046, C-047, C-048
```

### 4.2 Vector Index

| Property | Specification |
|----------|--------------|
| **Embedding Model** | `sentence-transformers/all-MiniLM-L6-v2` (384-dim, ~80 MB) |
| **Fallback Model** | `sentence-transformers/all-mpnet-base-v2` (768-dim, ~420 MB) |
| **Similarity Metric** | Cosine similarity |
| **Storage Backend** | `sqlite-vec` (v0.1+) — SQLite extension for vector storage |
| **Index Type** | IVF (Inverted File) for approximate nearest neighbor |
| **Chunk Embedding** | Mean-pooled token embeddings of chunk content |
| **Normalization** | L2-normalized before storage |

**Storage Schema (sqlite-vec):**
```sql
CREATE TABLE vector_chunks (
    chunk_id TEXT PRIMARY KEY,
    embedding BLOB,           -- numpy array serialized as bytes
    model TEXT,               -- embedding model name
    dim INTEGER               -- embedding dimension
);

-- Virtual table for KNN search
CREATE VIRTUAL TABLE vec_knn USING vec0(
    chunk_id TEXT PRIMARY KEY,
    embedding FLOAT[384] distance_metric=cosine
);
```

### 4.3 TF-IDF Index

| Property | Specification |
|----------|--------------|
| **Library** | `scikit-learn.TfidfVectorizer` |
| **n-gram range** | (1, 2) — unigrams + bigrams |
| **Max features** | 10,000 |
| **Stop words** | English (custom list including markdown syntax words) |
| **Similarity** | Cosine similarity |

### 4.4 Hybrid Ranker

```python
def hybrid_score(
    vector_score: float,
    keyword_score: float,
    alpha: float = 0.5
) -> float:
    """
    Weighted combination of vector and keyword scores.
    
    alpha=0.0 → pure keyword (TF-IDF/BM25)
    alpha=0.5 → equal blend
    alpha=1.0 → pure vector
    
    Scores are normalized to [0, 1] before blending.
    """
    return alpha * vector_score + (1 - alpha) * keyword_score
```

### 4.5 Cross-Reference Indexer

**Entity Extraction Strategy:**

1. **Named Entity Recognition:** Use `spaCy` or regex-based extraction for drug names, conditions, and chapter references
2. **Known Entity List:** Extract known entities from claims register (drug names: semaglutide, tirzepatide, etc.)
3. **Chapter Reference Detection:** Regex for patterns like "as discussed in Chapter 5", "see Chapter 3"
4. **Co-occurrence Matrix:** Track entities that co-occur in the same chunk

**Entity Normalization:**
```
semaglutide → semaglutide
Ozempic    → semaglutide        # brand name normalization
Wegovy     → semaglutide        # brand name normalization
GLP-1      → glp-1_agonist      # class normalization
```

### 4.6 Readability QA

Reuses `textstat` (already integrated via `readability_sota.py`). The key extension is per-chunk granularity:

```python
class ReadabilityAnalyzer:
    def analyze_chunk(self, chunk: ContentChunk) -> ReadabilityRecord:
        prose = self._extract_prose(chunk.content)
        return ReadabilityRecord(
            chunk_id=chunk.chunk_id,
            book_slug=chunk.book_slug,
            flesch_reading_ease=textstat.flesch_reading_ease(prose),
            flesch_kincaid_grade=textstat.flesch_kincaid_grade(prose),
            # ... other metrics
        )
    
    def detect_regression(
        self, current: list[ReadabilityRecord], baseline: list[ReadabilityRecord]
    ) -> list[ReadabilityRegression]:
        # Compare current vs baseline FK grades
        # Flag chunks where |current_fk - baseline_fk| > threshold
```

---

## 5. Performance Requirements

| Metric | Target | Measurement | Degradation Path |
|--------|--------|-------------|------------------|
| **Query Latency (p50)** | <200 ms | Timed benchmark suite; 100 queries | Reduce top_k; disable vector search |
| **Query Latency (p95)** | <500 ms | Timed benchmark suite; 100 queries | Enable embedding cache; pre-filter |
| **Full Rebuild Time** | <2 min (27K words, 10 files) | `time bookctl.py index --rebuild` | Skip embedding (TF-IDF only) |
| **Incremental Rebuild** | <30 s single-chapter edit | `time bookctl.py index` after edit | Fall back to full rebuild |
| **Embedding Throughput** | >50 chunks/s | Local benchmark | Downgrade to smaller model |
| **Chunking Speed** | <5 s for 10 files | Timed chunker | Skip chunk validation |
| **Memory (Peak)** | <2 GB RAM | `memory_profiler` | Use streaming embeddings |
| **Disk (Index)** | <100 MB per book | `du -sh .bookqa/` | Prune old index versions |

### 5.1 Projected Index Sizes (Peptide Book)

| Index Component | Estimated Size | Notes |
|-----------------|---------------|-------|
| Content chunks | ~80 chunks (10 files × ~8 sections each) | — |
| Chunk embeddings | ~80 × 384 × 4 bytes ≈ 123 KB | sqlite-vec storage |
| TF-IDF matrix | ~10K features × 80 docs = sparse ~800 KB | scikit-learn sparse matrix |
| Claim records | ~96 records | Negligible (<10 KB) |
| Cross-references | ~50-100 entities, ~200 mentions | Negligible (<10 KB) |
| Readability records | ~80 records | Negligible (<5 KB) |
| **Total** | **~1-2 MB** | **Well under 100 MB budget** |

---

## 6. Scalability Requirements

| Scale Target | Chapters | Words | Claims | Chunks | Query Latency | Rebuild Time |
|-------------|----------|-------|--------|--------|---------------|-------------|
| Current (v1.0) | 10 files | ~27K | 96 | ~80 | <200 ms | <2 min |
| Medium | 30 files | ~100K | 300 | ~300 | <300 ms | <5 min |
| Target (v2.0+) | 50+ files | ~200K | 500+ | ~500+ | <500 ms | <10 min |

### 6.1 Bottlenecks and Mitigations

| Bottleneck | Identification | Mitigation |
|------------|---------------|------------|
| Embedding generation | O(n × model_time) per chunk | Batch embedding; single-sentence-transformers call |
| Vector KNN search | O(d × n) per query | IVF index (sqlite-vec); optional HNSW |
| Full rebuild | Chunking + embedding + indexing | Incremental rebuild for changed files only |
| TF-IDF fit | O(n × vocab) per full rebuild | Persist fitted vectorizer; incremental update |

---

## 7. Security and Access Control

### 7.1 Threat Model

| Threat | Severity | Mitigation |
|--------|----------|------------|
| **Index manipulation** — unauthorized modification of index files | Low | Index files are local artifacts owned by the user |
| **Privilege escalation** — QA system used to read arbitrary files | Low | Only reads files within the book directory tree |
| **Supply chain** — compromised dependency (sentence-transformers, etc.) | Medium | Pin versions in pyproject.toml; regular dependency audit |
| **Information disclosure** — query results expose sensitive content | Low | Book content is intended for publication |

### 7.2 Access Control

| Operation | Access | Notes |
|-----------|--------|-------|
| Index rebuild | Local file write | Standard filesystem permissions |
| Query | Local read | No authentication for CLI use |
| Configuration | Local file write | book.yaml QA section |

### 7.3 Security by Design

- **No network calls at query time** — embedding model runs locally
- **Noeval() or dynamic execution** — all parsing uses AST or regex
- **Filesystem scope** — QA system only reads/writes within the book directory (`.bookqa/`)
- **Dependency isolation** — Python virtualenv as per existing engine convention

---

## 8. Testing Strategy

### 8.1 Unit Tests

| Component | Test Area | Example |
|-----------|-----------|---------|
| Content Chunker | Heading detection | Chunk correctly splits at H2 boundaries |
| Content Chunker | Claim marker extraction | `<!-- claim: C-003 -->` correctly maps to chunk |
| Content Chunker | Edge cases | Empty sections, orphan text, fenced code blocks |
| Structured Indexer | Claims register parsing | Parse 96 rows correctly; handle malformed rows |
| Structured Indexer | Entity extraction | Extract "semaglutide", "tirzepatide" from known texts |
| TF-IDF Indexer | Fit and query | Query returns correct document ranking |
| Hybrid Ranker | Weighted score | α=0 → pure keyword, α=1 → pure vector |
| Readability QA | Per-chunk metrics | Matches readability_sota.py output |
| Data Models | Validation | Bad tier values rejected; required fields enforced |

### 8.2 Integration Tests

| Test | Setup | Expected |
|------|-------|----------|
| Full indexing pipeline | Run `index --rebuild` on peptide book | 80±10 chunks, 96 claims indexed |
| Incremental rebuild | Modify one chapter, run `index` | Only changed chunks updated; metadata updated |
| Natural-language query | "What does the book say about semaglutide?" | Top result from Ch 2 or Ch 5 |
| Claim query by tier | `--claim-tier rct` | 20+ results; all have tier=rct |
| Claim query by status | `--claim-status pending` | 0 results (all confirmed) or accurate count |
| Cross-reference | `xref "semaglutide"` | Mentions in Ch 2, 5, 6, 7 |
| Readability report | `readability` | Matches readability_sota.py per-chapter, plus per-chunk |
| Hybrid query | `--alpha 0.3` | Results weighted toward keyword |
| Index status | `index --status` | Accurate chunk/claim counts |

### 8.3 Accuracy Benchmarks

**Ground-Truth Query Set (20 queries):**

| ID | Query | Expected Top Chunk | Tier Filter |
|----|-------|--------------------|-------------|
| GQ-01 | "What did the SELECT trial find about semaglutide?" | Ch 2: Cardiovascular Outcomes | — |
| GQ-02 | "How much weight loss does semaglutide achieve?" | Ch 2: Weight Management | — |
| GQ-03 | "Is BPC-157 FDA-approved?" | Ch 3: Regulatory Status | — |
| GQ-04 | "What are the GI side effects of GLP-1 agonists?" | Ch 5: GLP-1 Safety | — |
| GQ-05 | "How does tirzepatide compare to semaglutide?" | Ch 2: Comparison of Agents | — |
| GQ-06 | "What is the future of oral peptide delivery?" | Ch 7: Oral Peptide Delivery | — |
| GQ-07 | "Show all RCT claims" | — | tier=rct |
| GQ-08 | "Show claims about retatrutide" | — | — |
| GQ-09 | "What compounding regulations apply to peptides?" | Ch 6: 503A/503B | — |
| GQ-10 | "Is semaglutide safe during pregnancy?" | Ch 5: Special Populations | — |

**Benchmark Criteria:**
- Top-3 recall: ≥90% (18/20 queries return correct top chunk in top 3)
- Top-1 precision: ≥70% (14/20 queries return correct top chunk as #1)
- Claim query precision: 100% (no incorrect claims returned)
- Cross-reference accuracy: ≥95% (no false entity detections)

### 8.4 Performance Benchmarks

| Benchmark | Method | Target |
|-----------|--------|--------|
| Query latency | `time` 100 queries, report p50/p95 | <200 ms / <500 ms |
| Full rebuild | `time bookctl.py index --rebuild` | <2 min |
| Incremental rebuild | `time bookctl.py index` after single-chapter edit | <30 s |
| Memory (peak) | `memory_profiler` during rebuild | <2 GB |
| Disk usage | `du -sh .bookqa/` | <100 MB |

### 8.5 Edge Cases

| Edge Case | Expected Handling |
|-----------|------------------|
| Empty book (no chapters) | `index` reports 0 chunks; `query` returns no results |
| Chapter with no headings | Entire chapter treated as single chunk |
| Malformed claims register | Graceful error with line number; skip malformed row |
| Very long chunk (>1000 words) | Sub-chunk at H3 or paragraph level |
| Query with no matches | Return empty result set; suggest broadening the query |
| Corrupted index file | Detect on load; recommend `--rebuild` |
| Concurrent index build | Reject; single-writer pattern (CLI is single-user) |

---

## 9. Configuration

### 9.1 Default Configuration

```yaml
# book.yaml QA section (defaults)
qa:
  enabled: true
  embedding_model: all-MiniLM-L6-v2
  chunking:
    strategy: heading
    min_chunk_words: 50
    max_chunk_words: 500
  query:
    default_mode: hybrid
    default_alpha: 0.5
    top_k: 5
  readability:
    target_fk: 8.4
    fk_tolerance: 1.7
    detect_regression: true
    regression_threshold: 1.0
  storage:
    backend: sqlite
    path: .bookqa/
```

### 9.2 Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `BOOK_QA_MODEL` | Override embedding model path | (uses config) |
| `BOOK_QA_DISABLE_VECTOR` | Force TF-IDF only | false |
| `BOOK_QA_LOG_LEVEL` | Logging verbosity | WARNING |
| `BOOK_QA_CACHE_DIR` | Model cache directory | ~/.cache/book-qa/ |

---

## 10. Project Structure

```
engine/
├── bookqa/                          # QA system package
│   ├── __init__.py
│   ├── config.py                    # QaConfig, defaults, env var loading
│   ├── chunker.py                   # ContentChunker, heading-based segmentation
│   ├── models.py                    # All pydantic dataclasses
│   ├── embedding.py                 # EmbeddingModel wrapper (sentence-transformers)
│   ├── vector_index.py              # sqlite-vec vector store operations
│   ├── tfidf_index.py               # scikit-learn TF-IDF index
│   ├── claim_indexer.py             # Claims register parser and indexer
│   ├── cross_reference.py           # Entity extraction and cross-reference index
│   ├── query_engine.py              # Query routing, hybrid ranking, result formatting
│   ├── readability.py               # Per-chunk readability analysis
│   ├── rebuild.py                   # Full and incremental rebuild orchestration
│   ├── storage.py                   # SQLite connection, schema, migrations
│   ├── cli.py                       # CLI commands (invoked by bookctl.py)
│   └── exceptions.py                # Custom exceptions
├── tests/
│   ├── test_chunker.py
│   ├── test_models.py
│   ├── test_tfidf_index.py
│   ├── test_vector_index.py
│   ├── test_query_engine.py
│   ├── test_claim_indexer.py
│   ├── test_readability.py
│   ├── test_integration.py
│   └── fixtures/
│       ├── sample_chapter.md
│       ├── sample_claims.md
│       └── ground_truth_queries.json
├── bookctl.py                       # Extended with index/query/xref/readability
└── requirements-qa.txt              # Additional dependencies for QA system
```

---

## 11. Dependencies

### 11.1 New Dependencies

| Package | Version | Purpose | Size |
|---------|---------|---------|------|
| `sentence-transformers` | ≥2.2 | Text embedding | ~80 MB (model) |
| `sqlite-vec` | ≥0.1 | Vector storage in SQLite | ~2 MB (extension) |
| `scikit-learn` | ≥1.3 | TfidfVectorizer, cosine_similarity | ~10 MB |
| `pydantic` | ≥2.0 | Data model validation | ~2 MB |

### 11.2 Reused Dependencies

| Package | Already Used In | Purpose |
|---------|----------------|---------|
| `textstat` | readability_sota.py | Readability metrics |
| `numpy` | engine (implied via scikit-learn) | Array operations |
| `sqlite3` | stdlib | Structured data storage |

### 11.3 Optional Dependencies

| Package | Purpose | Version |
|---------|---------|---------|
| `spaCy` (en_core_web_sm) | NER for cross-reference extraction | ≥3.7 |
| `tiktoken` | Token counting for reduction ratio | ≥0.5 |

---

## 12. Error Handling

| Condition | Error | User Message | Recovery |
|-----------|-------|-------------|----------|
| Book directory not found | `BookNotFoundError` | "Book '<slug>' not found" | Check path |
| No index found | `IndexNotFoundError` | "No index found. Run 'bookctl.py index' first." | Run index |
| Corrupt index | `IndexCorruptError` | "Index appears corrupt. Run --rebuild." | Rebuild |
| Embedding model not loaded | `ModelLoadError` | "Could not load embedding model. Check model path." | Check config; fall back to TF-IDF |
| Malformed claims register | `ClaimsParseError` | "Claims register parse error at line N." | Fix register |
| Empty query | `InvalidQueryError` | "Query cannot be empty." | Provide non-empty query |
| Index build in progress | `IndexBusyError` | "Index build already in progress." | Wait and retry |

---

## 13. Migration Guide

### 13.1 From Current System (No QA)

1. Add QA dependencies (`sentence-transformers`, `sqlite-vec`, `scikit-learn`, `pydantic`)
2. Add `qa:` section to `book.yaml` (defaults work out of box)
3. Run `bookctl.py index <book> --rebuild` to build initial index
4. Start using `bookctl.py query`, `bookctl.py xref`, `bookctl.py readability`

### 13.2 From v0.x to v1.0

- `--rebuild` automatically handled; old index detected and migrated
- Config schema changes tracked via version in IndexMetadata
- Any breaking changes flagged by migration script

---

## 14. Release Checklist

| Step | Details | Owner |
|------|---------|-------|
| 1 | All P0 features implemented and unit-tested | Engineering |
| 2 | Ground-truth benchmark ≥90% top-3 recall | Engineering |
| 3 | Performance benchmarks meet targets (query <500ms, rebuild <2min) | Engineering |
| 4 | Integration test suite passes | Engineering |
| 5 | Edge case tests pass | Engineering |
| 6 | Documentation written (README, user guide, API reference) | Engineering |
| 7 | Author validates with real query workflow | Author |
| 8 | Medical reviewer validates claim queries | SME |
| 9 | `bookctl.py query` integrated and tested end-to-end | Engineering |
| 10 | README updated (new subcommands, QA section) | Engineering |

---

*End of Technical Requirements Document*
