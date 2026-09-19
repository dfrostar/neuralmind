# Release Notes — NeuralMind v4.1.0

**Release Date:** 2026-09-18  
**License:** MIT  
**Compare:** [v4.0.0 → v4.1.0](https://github.com/dfrostar/neuralmind/compare/v4.0.0...v4.1.0)

---

## What's New

### Memory Layer v1.0 — Decision Memory with Commit-Level Invalidation

A persistent, queryable record of architectural decisions that survives across agent sessions. Every decision is tied to the git commit where it was made; when that commit is amended or the affected files change, the decision is automatically flagged as stale.

| Capability | Purpose | Status |
|-----------|---------|--------|
| **Decision Store** | SQLite-backed decision records with FTS search | ✅ Shipped |
| **Commit Invalidation** | Auto-stale on file-touch, commit mismatch, cascade | ✅ Shipped |
| **CLI** | `neuralmind memory {record,query,amend,audit,export,...}` | ✅ Shipped |
| **MCP Tools** | 4 new tools for any agent (query, audit, record, invalidate) | ✅ Shipped |
| **Eval Harness** | Reproducible quality tracking for decision retrieval | ✅ Shipped |

### CLI — `neuralmind memory`

```bash
# Record a decision
neuralmind memory record . --title "Use SQLite for decision store" \
  --rationale "Single-file, no server, ACID-compliant" \
  --commit abc1234 --files "neuralmind/memory/store.py" \
  --type architecture --confidence 0.95

# Query decisions
neuralmind memory query . "database choice" --limit 10

# Audit (list all, stale-only, or orphaned)
neuralmind memory audit . --stale-only

# Amend an existing decision
neuralmind memory amend <decision-id> --rationale "Updated reasoning"

# Export all decisions
neuralmind memory export . --format md --output decisions.md

# Invalidate (mark stale)
neuralmind memory invalidate <decision-id> --reason "Superseded by new approach"

# Restore a stale decision
neuralmind memory restore <decision-id>

# Run eval harness
neuralmind memory eval .
```

### MCP Tools (4 new)

| Tool | Description | Scope |
|------|-------------|-------|
| `neuralmind_query_decisions` | Natural-language search over decision store | Read |
| `neuralmind_audit_decisions` | List all decisions, filter by status | Read |
| `neuralmind_record_decision` | Store a new decision with evidence | Write |
| `neuralmind_invalidate_decision` | Mark a decision as stale | Write |

**RBAC:** Builder role gets all 4 tools; Reader role gets query + audit only (write operations denied).

### Security Hardening

- Bumped `next` 15.5.23 → 15.5.24 (2 critical RCE alerts — unreachable in static export, bumped anyway)
- Bumped `sharp` → 0.35.4 (libheif vulnerabilities)
- Bumped `browserslist` → 4.28.7 (crash via untrusted stats)
- Bumped `baseline-browser-mapping` → 2.11.0 (DoS on invalid input)
- Dismissed 3 chromadb alerts as `not_used` (embedded client only, no server — see SECURITY.md)
- **0 open Dependabot alerts**

---

## Bug Fixes

- **memory:** `DecisionStore.update()` referenced nonexistent `decision.files` attribute — `AttributeError` was swallowed by `except: pass`, making every `update()` a silent no-op. Fixed to use `files_affected`. Caught by regression test.

---

## Benchmarks (Reproducible)

| Metric | Value | Command |
|--------|-------|---------|
| Gold-file recall | **93.75%** mean / 79–100% per repo | `python -m evals.public.run` |
| Token reduction vs pasting | **45–257×** | Same |
| Decision store query latency | **<5ms** for 10k decisions | `neuralmind memory query . "test"` |

---

## Upgrade Notes

**No breaking changes.** Existing NeuralMind users:

```bash
pip install --upgrade neuralmind
neuralmind wakeup .   # picks up new modules automatically
```

The memory layer is **opt-in** — it creates a `.neuralmind/memory.db` in your project root on first use. No existing behavior changes.

---

## Assets

- `neuralmind-4.1.0-py3-none-any.whl`
- `neuralmind-4.1.0.tar.gz`
- SBOM: `neuralmind-v4.1.0.sbom.json`

---

**Full Changelog**: [CHANGELOG.md](https://github.com/dfrostar/neuralmind/blob/main/CHANGELOG.md)
