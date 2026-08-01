# Release Notes — NeuralMind v1.13.1

> **Status:** Released 2026-08-02
> **DeepSeek QA:** Clean

---

## What's New in v1.13.1

This is a hardening release that fixes gaps in v1.12.0's document synapse seeding.

### Bug Fixes & Hardening

- **Doc synapse seeding now warns when gated.** `seed_from_documentation()` prints a hint when `NEURALMIND_LLM_SEED=1` or `ANTHROPIC_API_KEY` is missing — no more silent failures. Users know why their docs aren't enriching the graph.
- **`ingest_cmmc` now seeds synapses.** Reinforces co-activation between ingested CMMC practices. Previously only `ingest_document` seeded synapses — inconsistent.
- **`synapse_doc_edges` surfaced in CLI.** `neuralmind learn` now prints the count of synapse edges created from documentation. Previously only MCP callers could see it.
- **`test_escape_rejected` fixed.** Test now matches the intentionally relaxed path validation (files outside root allowed, symlinks rejected).

### New Infrastructure

- **Release notes template.** `docs/releases/RELEASE_TEMPLATE.md` enforces consistent format across all future releases.
- **Release Notes link in site footer.** neuralmind.uk footer now links to the `docs/releases/` directory.
- **Multi-project scoping wiki.** Documents isolation rules for NeuralMind (per-project), memU (needs `[project]` prefix), Hermes memory (needs tags), and session_search (needs project name).

### Integration Tests Added

- `test_seed_from_documentation_writes_edges` — verifies LLM-extracted relations create synapse edges
- `test_seed_from_documentation_gated_off_returns_zero` — verifies env var gate
- `test_seed_from_documentation_no_anthropic_key_returns_zero` — verifies API key gate
- `test_seed_from_documentation_empty_docs_returns_zero` — verifies empty doc handling

## Behaviour Controls

| Env Var | Default | Effect |
|---------|---------|--------|
| `NEURALMIND_LLM_SEED` | unset | `1` enables LLM doc→synapse extraction |

## Verification

```bash
# Enable doc seeding
export NEURALMIND_LLM_SEED=1
export ANTHROPIC_API_KEY=sk-ant-...

# Build
python3 -m neuralmind build .

# Ingest a document — should print synapse edge count
python3 -m neuralmind learn README.md

# Verify synapse edges increased
python3 -m neuralmind stats . --json | jq .synapses

# Run targeted tests
python3 -m pytest tests/test_synapse_integration.py tests/test_mcp_server.py tests/test_document_ingestion.py -q
# Expected: 55 passed
```

## Migration

None. Upgrade with `pip install --upgrade neuralmind`.

Existing indexes, hooks, and synapses.db work unchanged.
