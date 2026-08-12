# Release Notes — v3.1.4 (August 2026)

**Tag:** v3.1.4 | **Published:** 2026-08-11

---

## TL;DR

v3.1.4 resolves all 12 dogfood issues from v3.1.2, adds **code/document scoring** for better retrieval precision, and introduces **intent detection** for automatic query classification. After install, your agent gets: health check endpoint, synapse pruning, audit trail queries, code/doc type filtering, and cross-project search.

---

## What's Fixed

### P0 — Critical

| # | Issue | Fix |
|---|-------|-----|
| 1 | Role-gated MCP tools block ROI measurement | Analytics tools (savings, compliance, structural_gaps, synapse_stats) added to `builder` role |
| 2 | No auto-rebuild on file changes | Post-build hint suggests `init-hook` or `watch` |
| 4 | No incremental build | Graph regenerated on every build (graphgen reuses by hash) |

### P1 — High

| # | Issue | Fix |
|---|-------|-----|
| 3 | No `.neuralmindignore` support | `.gitignore`-style exclusion in file discovery |
| 8 | Markdown bloat dilutes retrieval | Same fix as #3 |

### P2 — Medium

| # | Issue | Fix |
|---|-------|-----|
| 5 | Unknown edge relations | Added `describes` to EDGE_RELATIONS |
| 6 | No audit trail query | Added `audit recent` subcommand |
| 7 | No SOC2 compliance detection | Added SOC2 regex pattern |
| 9 | No code/doc type filter | Added `--type code/docs/auto` flag with intent detection |
| 10 | No cross-project query | Added `--projects` flag |

### P3 — Low

| # | Issue | Fix |
|---|-------|-----|
| 11 | Stale synapses have no prune tool | Added `synapse prune/stats` commands |
| 12 | No health check endpoint | Added `health` CLI + MCP tool |

---

## What's New

### Code/Document Scoring

NeuralMind now auto-detects query intent (code vs docs) and applies type-aware boosting to search results:

- **Code queries** ("Show me the auth.py implementation"): boost code nodes 3×, demote docs 0.5×
- **Doc queries** ("Explain the architecture"): boost docs 2×, demote code 0.7×
- **Configurable** via `NEURALMIND_CODE_BOOST`, `NEURALMIND_DOC_BOOST`, `NEURALMIND_INTENT_THRESHOLD`

```bash
neuralmind query . "implement authentication" --type code
neuralmind query . "explain the architecture" --type docs
```

### Health Check Endpoint

Lightweight health signal for CI/CD and orchestrators:

```bash
neuralmind health .    # Exit 0=healthy, 1=stale, 2=no index
```

MCP tool `neuralmind_health` returns: index age, node count, disk usage, synapse edge count.

### Synapse Pruning

Clean up stale associations:

```bash
neuralmind synapse stats .     # Total, active, dormant, LTP-protected
neuralmind synapse prune . --days 30
```

LTP-protected edges (≥5 activations) are preserved to maintain learned associations.

### Audit Trail Queries

Search recent audit events:

```bash
neuralmind audit recent -n 10
neuralmind audit recent --since "2026-08-01"
```

### Cross-Project Search

Query across multiple indexed projects:

```bash
neuralmind query --projects /repo/a,/repo/b "authentication logic"
```

---

## What the Agent Actually Sees Post-Install

### New Commands

| Command | Description |
|---------|-------------|
| `neuralmind health` | Health check with exit codes |
| `neuralmind synapse prune` | Remove stale synapses |
| `neuralmind synapse stats` | Detailed synapse diagnostics |
| `neuralmind audit recent` | Query audit trail |
| `neuralmind query --type code/docs/auto` | Type-filtered search |
| `neuralmind query --projects a,b` | Cross-project search |

### New MCP Tools

| Tool | Description |
|------|-------------|
| `neuralmind_health` | Health check (index age, nodes, disk, edges) |
| `neuralmind_synapse_stats` | Synapse diagnostics |
| `neuralmind_synapse_decay` | Run decay manually |
| `neuralmind_feedback` | Explicit good/bad feedback |
| `neuralmind_savings` | Token savings report |
| `neuralmind_compliance_report` | Compliance framework detection |
| `neuralmind_structural_gaps` | Find structural gaps in graph |
| `neuralmind_export_synapse_memory` | Export synapses to markdown |
| `neuralmind_ingest_document` | Ingest documents via MCP |

### New Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `NEURALMIND_CODE_BOOST` | `3.0` | Boost factor for code nodes |
| `NEURALMIND_DOC_BOOST` | `2.0` | Boost factor for doc nodes |
| `NEURALMIND_INTENT_THRESHOLD` | `0.6` | Confidence threshold for intent classification |

---

## Upgrade

```bash
pip install --upgrade neuralmind
```

**No breaking changes.** All new features are additive. Existing queries return identical results (default `auto` intent detection preserves current behavior).

---

*End of release notes.*
