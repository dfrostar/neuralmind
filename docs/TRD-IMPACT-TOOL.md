# Technical Requirements Document: Impact — a friendlier blast-radius tool
**Product**: dfrostar/neuralmind v0.47.0 (target)  
**Date**: 2026-07-16  
**Owner**: Engineering / DevEx Team

## 1. Technical Summary
`impact` is built as a thin, richer-output layer over the existing
`StructuralIndex` reverse-dependency traversal — **not** a second, independently
evolving BFS implementation. One BFS, two entry points:

- `StructuralIndex.blast_radius_detail(node_id, depth) -> list[dict]` (new) — the
  real logic: same breadth-first traversal `blast_radius()` already used
  (`BLAST_VIEWS`, hub-cap, cycle-safe visited set), but accumulates
  `{"id", "relation", "hop", "depends_on"}` per dependent instead of a bare id.
- `StructuralIndex.blast_radius()` (existing, refactored) — now
  `sorted(row["id"] for row in self.blast_radius_detail(...))`, a one-line
  wrapper. Output is unchanged; behavior is unchanged; there is exactly one
  traversal implementation.
- `NeuralMind.impact(symbol, depth=1) -> dict` (new) — resolves `symbol` (exact
  node id or NL description), calls `blast_radius_detail()`, shapes the response.
- `cmd_impact` (cli.py) / `tool_impact` (mcp_server.py) — thin CLI/MCP wrappers,
  following the exact conventions of `cmd_structural`/`tool_structural_neighbors`.

## 2. Design Decisions
**Extend `structural.py`, don't duplicate it.** An earlier uncommitted diff
(`18bdcbf`, `wip-neuralmind-impact`) implemented `impact()` as an independent BFS
over `IMPACT_RELATIONS = ("calls", "inherits", "imports_from", "shares_data_with")`
directly against `self.embedder.edges`. That diff predates `structural.py`
(PR #320, merged 2026-07-12), which already ships a hub-normalized, cycle-safe
reverse-dependency traversal (`blast_radius()`) with a *different* relation set
(`BLAST_VIEWS` → `calls`/`imports_from`/`inherits`/`implements`, no
`shares_data_with`). Shipping the diff as-written would create two independently
evolving "what depends on X" implementations with different relation sets,
different hub-normalization (the diff's from-scratch BFS has none), that would
silently drift apart over time. This release rewires the diff's CLI/MCP surface
onto `blast_radius_detail()` instead — one traversal, one relation set, one place
to fix bugs.

**Report the raw relation, not the view name — with one known imprecision.**
`BLAST_VIEWS` (`callers`, `importers`, `subclasses`, `implementers`) are
*view* names; a dependent row should say `calls`/`inherits`/`imports_from`/
`implements`, the relation an agent actually reasons about. A static
`BLAST_VIEW_RELATION: dict[str, str]` reverse-maps view → relation. This is exact
for three of four views. The fourth, `importers`, is fed by two raw relations
(`imports_from` and `imports`, per `RELATION_VIEWS`) — the map reports
`imports_from` for both, since per-edge relation tracking (storing the original
relation per `(view, node, neighbor)` triple, not just per view) would roughly
double the index's memory footprint for a distinction the current ask doesn't
need. Documented as a known imprecision (BRD §5.1), not silently swallowed.

**`resolution` field is scoped to `impact()`, not threaded through
`_resolve_node_id()` generally.** `blast_radius()`/`structural_neighbors()`
(existing, shipped, untested-at-the-NeuralMind-level methods) resolve symbols via
`_resolve_node_id()`, which always does a semantic search — there's no
"is this already an exact node id?" fast path. `impact()` adds that fast path
(`embedder.get_nodes_by_ids([symbol])` before falling back to
`_resolve_node_id()`) locally, rather than modifying the shared
`_resolve_node_id()` helper both existing methods use. Extending the shared
helper was considered (it would improve `blast_radius`/`structural_neighbors`
too) but rejected for this release: those two methods have no integration-level
test coverage in this codebase today, so changing their resolution behavior
carries real regression risk with no test signal to catch it. Scoping the new
exact-match path to `impact()` — the only method this PR actually needs to test
and ship — keeps the change's blast radius (no pun intended) matched to its
test coverage.

**Test-fixture fix, not a production bug fix.** Investigated whether
`structural.py`'s edge-relation read (`edge.get("relation", edge.get("label",
edge.get("kind", "")))`) needed a `"type"` fallback, since `tests/conftest.py`'s
shared `sample_graph` fixture only set `"type"` on edges. Grepped the production
extractor (`neuralmind/graphgen.py`) and confirmed it emits `"relation"`
exclusively — no code path anywhere reads edge `"type"`. This is a test-fixture
staleness issue, not a live bug: `structural.py` was correct, `sample_graph` was
out of date. Fixed by adding `"relation"` alongside the existing `"type"` key in
the fixture's five edges, rather than adding unneeded fallback branches to
production code for a scenario that doesn't occur.

## 3. Files Touched
- `neuralmind/structural.py` — `blast_radius_detail()`, `BLAST_VIEW_RELATION`, `blast_radius()` refactored to a wrapper
- `neuralmind/core.py` — `NeuralMind.impact()`, `BLAST_VIEW_RELATION` import
- `neuralmind/cli.py` — `cmd_impact`, `impact` subparser (reuses existing `_structural_label` helper for display)
- `neuralmind/mcp_server.py` — `tool_impact`, `neuralmind_impact` `TOOLS` entry + dispatch (admin-role RBAC by default, unchanged policy — not added to the `builder`/`reader` sets, matching `structural_neighbors`)
- `tests/conftest.py` — `sample_graph` fixture: added `"relation"` key alongside `"type"` on its five edges
- `tests/test_structural.py` — `blast_radius_detail` hop/relation/nearest-hop-wins tests, `blast_radius`-is-a-wrapper test
- `tests/test_core.py` — `TestNeuralMindImpact` (exact/semantic resolution, transitive hops, relation exclusion, no-match)
- `tests/test_mcp_server.py` — `TestToolImpact` (delegation, dispatch routing, RBAC denial); `TestToolDefinitions` count/name-set updates

## 4. Test Plan
- Unit: `blast_radius_detail()` hop/relation/`depends_on` attribution, nearest-hop-wins when a node is reachable via multiple paths, `blast_radius()`'s output is byte-identical whether read directly or derived from `blast_radius_detail()`.
- Unit: `NeuralMind.impact()` — exact-id resolution skips semantic search entirely (asserted via a `search` mock that raises if called), semantic fallback resolves via `_resolve_node_id`, transitive dependents carry correct `hop`/`depends_on`, non-blast-radius relations (`uses`) are excluded, no-match returns `resolution: "none"`.
- Integration: `tool_impact` delegates to `NeuralMind.impact()`; `handle_tool_call` routes `neuralmind_impact` correctly and denies the default `builder` role (RBAC parity with `structural_neighbors`).
- Manual smoke test: `neuralmind impact <demo project> authenticate --depth 2` (both `--json` and human-readable) against the real demo fixture — confirmed working end-to-end during implementation.
- Full suite: `pytest tests/ -x -q` before opening the PR.

## 5. Relation to PRD: Structural Code Graph
This release is an extension of `docs/prd/structural-edges-brd.md` /
`structural-edges-trd.md` (v0.42.0), not a new PRD. That PRD shipped the
structural edge layer and `blast_radius()`/`structural_neighbors()`; this release
adds a friendlier name and richer per-dependent output on top of the same index,
closing the discoverability gap a competitive analysis surfaced without
duplicating the underlying capability.
