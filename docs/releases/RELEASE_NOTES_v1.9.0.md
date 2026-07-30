# Release Notes — NeuralMind v1.9.0

> **Status:** Released 2026-07-29
> **DeepSeek QA:** Clean

---

## What's New in v1.9.0

### G5 — Structural Gap Detection

NeuralMind now identifies **structural gaps** in your codebase — missing bridges
between code communities that should be connected but aren't. Built on **Brandes'
algorithm** for betweenness centrality over the structural graph.

**Capabilities:**
- Betweenness centrality via Brandes algorithm (O(VE) exact, O(VE/log V) approximate for large graphs)
- Cross-community bridge detection: finds communities that should share edges but don't
- Gap scoring: `betweenness × 1/(degree+1)` — high-betweenness, low-degree nodes are the gaps
- CLI: `neuralmind gaps --structural` (top-N gaps, community filter, JSON output)
- MCP tool: `neuralmind_structural_gaps` (returns ranked gap list with scores + communities)
- Louvain modularity with resolution parameter for community tuning

**Performance:** For graphs with >100K nodes, approximate betweenness is used
automatically (sampling-based, configurable threshold).

**Tests:** 43 tests covering exact + approximate betweenness, Louvain resolution,
gap scoring, CLI output, MCP tool contract, edge cases.

### Bug Fixes & Hardening

- **G5 DeepSeek QA patches** — gap ordering deterministic, Louvain fallback for disconnected graphs, dead code removal, docstring accuracy
- **DocEvolver failure-path tests** — 4 new tests covering rollback, evolution failure, patch failure, file-not-found
- **Test matrix** — Node 18 → 22 (fixes ESM module error in jsdom/vitest)
- **GitHub Pages decommissioned** — marketing site served via Cloudflare Pages (eliminates failing CI job)
- **Extraction cache** — `extraction_cache.json` added to gitignore

---

## Upgrade Guide

```bash
pip install --upgrade neuralmind
```

No breaking changes. Existing code-graph indexes are unchanged. The new G5 gap
detection runs on the same structural graph.

---

*Shipped with DeepSeek v4 Pro code review. 43 G5 tests green. CI passing.*
