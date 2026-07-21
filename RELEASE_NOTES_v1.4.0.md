v1.4.0 — 2026-07-23
-------------------

G3 — Louvain modularity clustering over structural code-dependency edges. `build_graph` now groups files by architectural layer, not by source path.

- `neuralmind/modularity.py`: stdlib-only Louvain (Phase 1 O(n·k), Phase 2 single collapse), resolution parameter, deterministic output, fail-open
- `neuralmind/graphgen.py`: `_assign_communities(b, existing_graph)` wires Louvain into `build_graph`, carries over community IDs from previous build for incremental stability
- Tests: 11 modularity tests (+6 over prior), 35 graphgen/incremental tests pass
- Full suite: 1582+ passed, ruff clean
- DeepSeek QA: 0 CRITICAL, 3 WARNINGs patched inline

**Result:** 7-file test project went from 7 per-file communities to 4 architectural-layer communities.
