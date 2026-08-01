# Release Notes — NeuralMind v1.12.0

> **Status:** Released 2026-08-02
> **DeepSeek QA:** Clean

---

## What's New in v1.12.0

### Synapse Doc Seeding (`core.py` → `synapses.py`)

Documents now *teach* the synapse graph, not just get searched. Ingested docs
seed Hebbian edges that connect documented architectural relationships to code
nodes — so the graph learns "the docs say authentication delegates to hashing"
as a retrievable association, not just text you can search.

`ingest_document()` now calls `seed_from_documentation()` post-embed. The method:

1. Reads `README.md` and `docs/architecture.md` from the project root
2. Sends them to an LLM to extract architectural relationships (A calls/delegates-to/uses B)
3. Creates synapse edges at weight 0.25–0.40 in the `shared` namespace (60-day half-life)
4. Returns the count of edges created (0 if LLM unavailable)

Gated on `NEURALMIND_LLM_SEED=1` + `ANTHROPIC_API_KEY`. Fail-open: without
these, documents still embed and search as before.

### `neuralmind_ingest_document` MCP Tool

MCP users can now ingest documents directly — previously CLI-only.

```
neuralmind_ingest_document(project_path, file_path, content_type="auto")
```

Params: `project_path`, `file_path`, `content_type` (auto/pdf/markdown/text)

### Synapse-Linked Ingestion Audit

Audit log records `synapse_doc_edges` for each ingestion. Check with
`neuralmind stats . --json` — the `synapses` count increases after doc ingestion
when LLM seeding is enabled.

### Multi-Project Scoping (Operator Rule)

New operator rule: NeuralMind isolates automatically (per-project `.neuralmind/`).
memU, Hermes memory, and session_search do NOT isolate. Scope every retrieve query
with `[project]` prefix. Tag every Hermes memory entry with `[project]`. Autopilot
is NEVER indexed (contains secrets).

Full doc: [Multi-Project Scoping](wiki/Multi-Project-Scoping)

---

## Bug Fixes & Hardening

- Fixed MCP tool count test (now 20 tools)
- Removed stale SESSION-HANDOFF.md from main repo (moved to autopilot docs)

## Behaviour Controls

| Env Var | Default | Effect |
|---------|---------|--------|
| `NEURALMIND_LLM_SEED` | unset | `1` enables LLM doc→synapse extraction |

## Verification

```bash
export NEURALMIND_LLM_SEED=1
export ANTHROPIC_API_KEY=sk-ant-...
python3 -m neuralmind build .
python3 -m neuralmind learn README.md --json
# Should show: "synapse_doc_edges": N  (N > 0)
python3 -m neuralmind stats . --json | jq .synapses
```

## Migration

None. Upgrade with `pip install --upgrade neuralmind`.
Existing indexes, hooks, and synapses.db work unchanged.
