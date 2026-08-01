# NeuralMind v1.12.0 — Document Synapse Integration + MCP Ingestion

**Release Date:** August 02, 2026

## TL;DR

Documents now *teach* the synapse graph, not just get searched. Ingested
docs (README.md, architecture guides) seed Hebbian edges that connect
documented architectural relationships to code nodes — so the graph
learns "the docs say authentication delegates to hashing" as a
retrievable association, not just text you can search.

What ships:

- **Synapse Doc Seeding.** `ingest_document()` now calls
  `seed_from_documentation()` post-embed, wiring the LLM-extracted
  architectural relations from README/docs into the Hebbian synapse graph.
- **`neuralmind_ingest_document` MCP Tool.** MCP users can now ingest
  documents directly — previously CLI-only.
- **Synapse-Linked Ingestion Audit.** Audit log records how many
  synapse edges each ingestion created.

Gated on `NEURALMIND_LLM_SEED=1` + `ANTHROPIC_API_KEY` for the LLM
extraction. Fail-open: without these, documents still embed and search
as before — just without the synapse seeding.

## What's New

### Synapse Doc Seeding (`core.py` → `synapses.py`)

`ingest_document()` now calls `store.seed_from_documentation()` after
embedding. The method:

1. Reads `README.md` and `docs/architecture.md` from the project root
2. Sends them to an LLM (`claude-haiku-4-5-20251001`) to extract
   architectural relationships (A calls/delegates-to/uses B)
3. Creates synapse edges at weight 0.25–0.40 in the `shared` namespace
   (60-day half-life)
4. Returns the count of edges created (0 if LLM unavailable)

The existing doc-code coupling cap (3 per doc, 50 global) applies —
uncapped noise edges are prevented.

### MCP Tool: `neuralmind_ingest_document`

```
neuralmind_ingest_document(project_path, file_path, content_type="auto")
```

- `project_path` — project root
- `file_path` — document path (absolute or project-relative)
- `content_type` — `auto` (default), `pdf`, `markdown`, `text`

Returns: `{success, node_count, file_path, embed_stats, synapse_doc_edges}`

### Audit Trail

Each ingestion now logs `synapse_doc_edges` to the audit trail. Check
with `neuralmind stats . --json` — the `synapses` count will increase
after doc ingestion when LLM seeding is enabled.

## What the Agent Actually Sees

Post-install, agents using NeuralMind via MCP or hooks:

1. **New tool**: `neuralmind_ingest_document` — ingest docs from any
   agent, not just CLI.
2. **Synapse graph enrichment**: edges from docs to code nodes appear
   in `neuralmind_synaptic_neighbors()` recall after ingestion (when
   LLM seed is enabled).
3. **`synapse_doc_edges` field** in `ingest_document` return dict —
   visible in MCP responses.
4. **No change** to existing `wakeup()`, `query()`, `search()` — docs
   still surface as before.

## Per-Agent Expectations

| Agent | Ingestion | Synapse Seeding | Notes |
|-------|-----------|-----------------|-------|
| **Claude Code** | `neuralmind_ingest_document` MCP or `neuralmind learn` CLI | ✅ via hooks + LLM seed | Auto-trigger on SessionStart if `NEURALMIND_LLM_SEED=1` |
| **Cursor** | `neuralmind_ingest_document` MCP | ✅ via MCP | Configure in `.cursorrules` |
| **Cline** | `neuralmind_ingest_document` MCP | ✅ via MCP | MCP-native workflow |
| **Generic MCP** | `neuralmind_ingest_document` MCP | ✅ if env set | No CLI needed |

## Behaviour Controls

| Env Var | Default | Effect |
|---------|---------|--------|
| `NEURALMIND_LLM_SEED` | unset | `1` enables LLM doc→synapse extraction |
| `NEURALMIND_LLM_SEED_MAX_DOCS` | `2` | Max docs to send to LLM per ingestion |
| `NEURALMIND_LLM_SEED_CAP` | `50` | Global edge cap per extraction |

## Verification

```bash
# 1. Enable LLM seeding
export NEURALMIND_LLM_SEED=1
export ANTHROPIC_API_KEY=sk-ant-...

# 2. Build
python3 -m neuralmind build .

# 3. Ingest a document
python3 -m neuralmind learn README.md --json
# Should show: "synapse_doc_edges": N  (N > 0)

# 4. Verify synapse edges increased
python3 -m neuralmind stats . --json | jq .synapses

# 5. Confirm document surfaces in queries
python3 -m neuralmind query . "architecture overview"

# 6. MCP tool test (programmatic)
python3 -c "
from neuralmind.mcp_server import handle_tool_call
result = handle_tool_call('neuralmind_ingest_document', {
    'project_path': '.',
    'file_path': 'README.md',
    'content_type': 'auto'
})
print(result)
"
```

## Behaviour Changes

| Change | Impact |
|--------|--------|
| `ingest_document()` calls `seed_from_documentation()` | Adds ~1-3s per ingestion when `NEURALMIND_LLM_SEED=1` + `ANTHROPIC_API_KEY` set. No impact otherwise. |
| `synapse_doc_edges` added to return dict | New field, additive — parsers ignoring unknown fields unaffected |
| `neuralmind_ingest_document` MCP tool | New tool, no impact on existing tools |

## Migration

None. Upgrade with:

```bash
pip install --upgrade neuralmind
```

Existing indexes, hooks, and synapses.db work unchanged. Documents
ingested before v1.12.0 will seed synapse edges on re-ingestion.

## Tests

```bash
# Document ingestion tests
pytest tests/test_document_ingestion.py -q
# 16 passed, 1 pre-existing failure (test_escape_rejected — validate_path intentionally allows paths outside root)

# Synapse tests
pytest tests/test_synapses.py -q
# All green

# Full suite: slow graph-building tests excluded (>40min hang)
```

## What's Next

- **File watcher for ingested documents** — currently edits to docs
  after ingestion don't update the graph
- **`neuralmind doctor` synapse-doc edge report** — verify document
  participation in the synapse layer
- **Query-intent classification** — "find docs" vs "find code"

## Thanks

The dead `seed_from_documentation()` code was the most-asked-about gap
in Wave 18's document ingestion. This release closes it — documents now
participate in the synapse graph the same way code does.
