# Release Notes — NeuralMind v1.11.0

**Release date:** 2026-07-31  
**Type:** Minor (new feature)  
**DeepSeek QA:** Pending  
**Tests:** 22/22 green (targeted), ruff clean

---

## What's New

### General Non-Code Ingestion

`neuralmind learn <file>` now ingests PDFs, Markdown, and plain text into the knowledge graph — extending the deprecated no-op into a first-class feature.

```bash
neuralmind learn document.pdf          # ingest single file
neuralmind learn specs/                # ingest directory
neuralmind learn --type cmmc guide.pdf # tag with type
```

**What it does:**
- Parses PDF/Markdown/text into `ContentNode` objects
- Chunks large documents (500-char window, 50-char overlap)
- Embeds chunks into the same vector space as code
- Links to existing code graph via semantic similarity
- Deduplicates on re-ingestion (0 new nodes)

**Security guards:**
- Path canonicalization + symlink rejection
- File magic sniffing (rejects binary with .md/.txt extension)
- Directory depth cap (10)
- Size cap (10MB per file)
- Prompt-injection hardening in extraction prompt

### Fact Dedup

Every extracted fact gets a `fact_hash` (SHA-256, 64-char, domain-prefixed). Duplicate facts increment reinforcement rather than creating parallel paths.

### Recency Factor

Retrieval ranking now incorporates recency: `score = sim × synapse_boost × recency_factor`. Edges used within the last 7 days get full weight; edges unused for >30 days get weight <0.5.

---

## Agent Impact

| Agent | What changes |
|-------|-------------|
| Claude Code | `neuralmind learn` now ingests docs; query returns document content |
| Cursor | Same |
| Cline | Same |
| Generic MCP | Same |

---

## Known Limitations

- PDF parsing requires `pdfplumber` (optional dependency)
- Audio/video ingestion out of scope (future wave)
- `neuralmind learn` requires a build first (`neuralmind build .`)

---

## Upgrade

```bash
pip install --upgrade neuralmind
```

**Backward compatible:** Yes. Existing code graphs unchanged.
