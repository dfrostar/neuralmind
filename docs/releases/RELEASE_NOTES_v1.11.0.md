# Release Notes — NeuralMind v1.11.0

> **Status:** Released 2026-07-31
> **DeepSeek QA:** Completed 2026-08-02 — 3 claims corrected below
> **Tests:** 17/17 document ingestion tests green

---

## What's New in v1.11.0

### General Non-Code Ingestion

`neuralmind learn <file>` ingests PDFs, Markdown, and plain text into the knowledge graph — extending the deprecated no-op into a first-class feature.

```bash
neuralmind learn document.pdf          # ingest single file
neuralmind learn specs/                # ingest directory
neuralmind learn --type markdown guide.md
```

**What it does:**
- Parses PDF/Markdown/text into `ContentNode` objects
- Chunks large documents (500-char window, 50-char overlap)
- Embeds chunks into the same vector space as code
- Deduplicates on re-ingestion via `content_hash` in the embedder (existing content is not re-embedded)
- Links to existing code graph via semantic similarity

**Security guards:**
- Path canonicalization + symlink rejection
- File magic sniffing (rejects binary content with .md/.txt extension)
- Directory depth cap (10)
- Size cap (10MB per file)

### TurboVec Embedder

`embed_content()` method added to `TurboVecEmbedder` for embedding non-code content nodes alongside code.

### Agent Impact

| Agent | What changes |
|-------|-------------|
| Claude Code | `neuralmind learn` ingests documents; query returns results alongside code |
| Cursor | Same |
| Cline | Same |
| Generic MCP | Same |

---

## DeepSeek QA Corrections (2026-08-02)

The original release notes claimed three features that were **not** shipped in v1.11.0:

| Original Claim | Status | Reality |
|---------------|--------|---------|
| **Fact Dedup** (fact_hash, SHA-256, 64-char, domain-prefixed) | ⚠️ Partially accurate | Dedup exists via `content_hash` in `embedder.py` (lines 225-242, 327-344), but uses SHA-256 of text content, not a separate "fact_hash" field. Re-ingestion of identical content produces 0 new nodes. |
| **Recency Factor** (`score = sim × synapse_boost × recency_factor`) | ❌ Not shipped | Zero matches for "recency_factor" in v1.11.0 codebase. Implemented in a later branch but not present in this release. |
| **Prompt-injection hardening in extraction prompt** | ❌ Not applicable | Document ingestion is **parsing-based** (PDF/Markdown/text), not LLM-extracted. No extraction prompt exists. No injection surface. |

---

## Known Limitations

- PDF parsing requires `pdfplumber` (optional dependency)
- Audio/video ingestion out of scope (future wave)
- `neuralmind learn` requires a build first (`neuralmind build .`)

## Verification

```bash
# Build
python3 -m neuralmind build .

# Ingest a document
python3 -m neuralmind learn README.md
# Expected: "Learning from: README.md" + node count

# Re-ingest same file (dedup check)
python3 -m neuralmind learn README.md
# Expected: 0 new nodes (identical content_hash)

# Verify document is queryable
python3 -m neuralmind query . "README"

# Run document ingestion tests
python3 -m pytest tests/test_document_ingestion.py -q
# Expected: 17 passed
```

## Upgrade

```bash
pip install --upgrade neuralmind
```

Backward compatible: Yes. Existing code graphs unchanged.
