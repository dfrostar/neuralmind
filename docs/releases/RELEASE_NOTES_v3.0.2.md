# Release Notes — v3.0.2 (August 2026)

**Tag:** v3.0.2 | **Published:** 2026-08-03

---

## TL;DR

v3.0.2 completes the v3.0.x stabilization: the Agent OS package is extracted to
a private repo (`dfrostar/agencyOS`), remaining `agent_os` references are
purged from LICENSE/README/site terms, the dashboard is rebranded to
"NeuralMind", and the `neuralmind learn` command now correctly detects the
project root.

---

## What's Fixed

### Agent OS Extracted to Private Repo

`neuralmind/agent_os/` has been moved to `dfrostar/agencyOS` (private). This
repo no longer contains the Agent OS source. Users with existing installs
can continue using it; new development happens in the private repo. This
clarifies the boundary between MIT core and commercial modules.

### Removed Remaining Agent OS References

- LICENSE: removed Agent OS dual-license language
- README: removed Agent OS feature flags and roadmap entries
- Site terms: removed Agent OS-specific terms
- Adversarial docs: removed Agent OS references that were superseded by extraction

### Dashboard Rebrand

The public dashboard is now branded "NeuralMind" throughout — no more
"Agent OS" or "Agency OS" references in the UI, ROADMAP, or tests. The
product is NeuralMind; Agent OS was the codename for the commercial
multi-tenant engine that is now extracted.

### `neuralmind learn` Project Root Detection

The `learn` command now uses `args.project_path` for root detection, falling
back to CWD and file walk-up. Previously it could pick the wrong directory
when invoked from a subdirectory, causing documents to be ingested into the
wrong project index.

### MCP Dependency Cap

Capped `mcp<2` — SDK 2.0 removes the server's decorator API that NeuralMind
relies on. Without this cap, installs would pull a breaking MCP SDK version.

---

## Verification

```bash
# 1. Verify agent_os is gone from this repo
ls neuralmind/agent_os 2>&1 # Should not exist

# 2. Verify LICENSE is clean
grep -i "agent.os" LICENSE # Should return nothing

# 3. Verify learn command root detection
cd /tmp && mkdir test-project && cd test-project
neuralmind init .
neuralmind learn ../some-doc.md --json # Should detect test-project as root

# 4. Verify MCP version constraint
grep "mcp" pyproject.toml # Should show <2 cap
```

## Behaviour Changes

| Change | Impact |
|--------|--------|
| Agent OS extracted to private repo | MIT core is cleaner; commercial modules are in a separate private repo |
| Dashboard rebrand | UI, ROADMAP, tests now say "NeuralMind" |
| `learn` command root detection | Documents ingest into the correct project index |
| MCP `<2` cap | Prevents breaking SDK upgrade |

## Migration

```bash
pip install --upgrade neuralmind
```

No breaking changes for core users. If you depended on `neuralmind/agent_os/`,
it's now in `dfrostar/agencyOS` (private — access on request).

## Tests

```bash
# Core tests (agent_os removed)
pytest tests/ -q --ignore=tests/test_agent_os.py

# Verify no agent_os references remain
grep -r "agent_os" neuralmind/ --include="*.py" | grep -v __pycache__
```

## What's Next

- **v3.1.0** — Synapse layer activation (reinforce on every query, explicit feedback CLI)
- **v3.2.0** — Scheduled decay, status dashboard, diagnostic "Is it learning?" page
