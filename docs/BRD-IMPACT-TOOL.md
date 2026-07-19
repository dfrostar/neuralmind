# Business Requirements Document: Impact — a friendlier blast-radius tool
**Product**: dfrostar/neuralmind v0.47.0 (target)  
**Date**: 2026-07-16  
**Owner**: Engineering / DevEx Team

## 0. Relationship to the Competitive Response plan
`docs/plans/2026-07-17-brd-competitive-response.md` / `-trd-competitive-response.md`
(committed to `main` after this branch was cut) scope `impact` far more ambitiously
as Objective A's P0 item #1: a dedicated `impact_engine.py` module, confidence
tiers (high/medium/low) cross-referenced against synapse history, historical
outcome notes ("last N edits: M broke tests"), a <500ms/1M-LOC performance SLA,
and per-symbol-per-commit caching — plus two sibling P0 items this release does
**not** build, `detect_changes` and `rename`.

**This release is a deliberately smaller, immediately-shippable slice of that
same Objective A item** — naming and output-richness only, no confidence
scoring, no historical learning integration, no caching, no SLA. It gets a
working `impact` tool in front of users now rather than blocking on the fuller
design. Confidence scoring, `impact_engine.py`, `detect_changes`, and `rename`
remain open follow-on work against the Competitive Response plan; this BRD's
§5 Outstanding Gaps already named the confidence-scoring gap independently,
before the existing plan was discovered.

## 1. Executive Summary
A Reddit comparison against GitNexus (an MCP-native code-intelligence competitor,
~42k GitHub stars) flagged "no `impact`/blast-radius tool" as a P0 gap. That's
mostly not true: `neuralmind structural --blast-radius` and
`neuralmind_structural_neighbors(blast_radius=true)` have shipped since v0.42.0's
structural code-graph edge layer (`docs/prd/structural-edges-brd.md`), and they
already answer "what depends on this symbol?" from the static code graph. The real
gap is narrower — **naming and output richness**, not capability. An agent (or a
human comparing tools) reaching for "impact analysis" wouldn't find it under
`structural --blast-radius`, and the existing output was a flat sorted id list with
no indication of *how* each dependent depends on the symbol or how many hops away
it is. This release adds `impact` as a friendlier-named, richer-output entry point
over the same structural index — it's a naming/discoverability/output-richness
release, not new capability, and that's a more credible story than claiming a
from-scratch build.

## 2. Competitive Context
GitNexus's `impact` MCP tool is its headline differentiator: pre-computed,
confidence-scored blast-radius answers in a single tool call, so an agent doesn't
chain multiple graph queries to understand what a change touches. NeuralMind's
equivalent capability already existed under a different name with weaker output:

| | GitNexus `impact` | NeuralMind `structural --blast-radius` (pre-v0.47.0) | NeuralMind `impact` (this release) |
| --- | --- | --- | --- |
| Tool name an agent would guess | `impact` | `structural` + a boolean flag | `impact` |
| Output | Confidence-scored rows | Flat sorted id list | Rows with `hop` + `relation` + `depends_on` |
| Underlying traversal | Pre-computed at index time | BFS over typed edges, computed on request | Same BFS (shared implementation, no duplication) |

## 3. What Changes
| Surface | Before | After |
| --- | --- | --- |
| `neuralmind structural --blast-radius <symbol>` | Flat id list | Unchanged — still available, still flat |
| `neuralmind impact <symbol>` (new) | Did not exist | Friendlier-named CLI command, same underlying traversal |
| `neuralmind_impact` (new MCP tool) | Did not exist | Same as CLI, agent-callable |
| `StructuralIndex.blast_radius()` | Flat BFS returning ids | Thin wrapper over `blast_radius_detail()` — same output, same behavior |
| `StructuralIndex.blast_radius_detail()` (new) | Did not exist | Returns `{id, relation, hop, depends_on}` rows |

## 4. Acceptance Criteria
- [ ] `neuralmind impact <project> <symbol> --depth 2` prints dependents with hop
      and relation, exits 1 with a clear message when nothing resolves
- [ ] `neuralmind impact <project> <symbol> --json` returns `{symbol, depth,
      relations, resolution, resolved_node, dependents, count}`
- [ ] `neuralmind_impact(project_path, symbol, depth)` MCP tool returns the same
      shape; admin-role RBAC by default (matches `structural_neighbors`)
- [ ] `structural --blast-radius` output is byte-identical to before this release
      (verified: it's now a one-line wrapper over the same traversal)
- [ ] `pytest tests/test_core.py tests/test_structural.py tests/test_mcp_server.py tests/test_cli.py -k "Impact or blast_radius"` passes

## 5. Outstanding Gaps / Non-Goals
1. **Relation fidelity at view boundaries.** Two raw relations
   (`imports_from`/`imports`) share one view pair (`importers`); a dependent row
   reports the more specific one (`imports_from`) regardless of which the
   original edge actually was. Per-edge relation tracking would resolve this but
   isn't justified by the current ask — see TRD §2.
2. **No confidence scoring.** GitNexus's `impact` tool reports confidence per
   dependent; NeuralMind's traversal doesn't score confidence, it reports
   hop-distance and relation type as the signal instead.
3. **No pre-computation.** GitNexus pre-computes blast radius at index time;
   NeuralMind computes it on request from the in-memory structural index — fast
   enough in practice (pure-Python BFS over a hub-capped adjacency), but not
   cached across calls the way GitNexus's approach is.
