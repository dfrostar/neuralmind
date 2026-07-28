# G5 — Structural Gap Detection, Session Kickoff Prompt

> **START HERE.** Copy this entire document into a new Hermes session to execute G5 (structural gap detection). All context is inline — no need to re-read old sessions.

---

## CONTEXT (where we are)

**NeuralMind** (`/home/dtfrost/neuralmind`): **v1.8.0** live on PyPI. G5 is the next feature — InfraNodus-style betweenness-centrality gap detection ported to codebases.

**What G5 does:** Reads `graph.json` (nodes + edges + Louvain communities), computes betweenness centrality via Brandes algorithm, identifies cross-community bridge nodes, scores gaps as `betweenness × (1/(degree+1))`, surfaces via CLI (`neuralmind gaps --structural`) + MCP tool (`neuralmind_structural_gaps`).

**Why:** NeuralMind has the graph + communities but never analyzes what's *between* them. InfraNodus does this for text — G5 ports it to code. Result: detect missing connectors between auth↔billing, api↔worker, etc.

**Docs committed:**
- `docs/specs/G5-BRD.md` — Business requirements
- `docs/specs/G5-TRD.md` — Technical spec (algorithms, data model, API, integration)
- `docs/specs/G5-TEST-PLAN.md` — 45 test cases
- `docs/specs/G5-ADR.md` — Architecture decisions

---

## CLARIFYING DECISIONS (already made)

1. **Pure Python Brandes algorithm** — no NetworkX, stdlib-only. Matches house style (`synapses.py`, `modularity.py`).
2. **Read-only additive** — reads `graph.json`, no changes to `build()`, `query()`, or synapses. Zero regression risk.
3. **Edge-weighted betweenness** — calls (1.0) > inherits (0.9) > imports (0.8) > contains (0.3) > rationale (0.2).
4. **Gap score = betweenness × (1/(degree+1))** — filters hubs (utilities with high betweenness but already connected).
5. **Brandes exact** for <5K nodes, k-approximate sampling fallback for larger.
6. **No integration with synapses/L2/L3** — G5 is detection-only. Integration is G6 territory.

---

## WORKSTREAMS (execute in order A→E)

### A. Core Algorithm — `neuralmind/structural_gaps.py`

**Gap:** No betweenness computation exists.

**Work:**
1. Implement `compute_betweenness(graph, normalized=True) -> dict[str, float]`
   - Brandes algorithm (pure Python, stdlib only)
   - Weighted edges (type-based: calls=1.0, inherits=0.9, imports=0.8, contains=0.3, rationale=0.2)
   - Normalization: divide by `(n-1)(n-2)` for undirected
   - Sampling fallback for V > MAX_BETWEENNESS_NODES (default 5K)
2. Implement `find_bridge_candidates(graph, communities, threshold=0.1) -> list[str]`
   - Nodes with betweenness ≥ τ, appearing in ≥2 communities
   - Degree filter: exclude nodes with degree > median × 2
3. Implement `detect_gaps(graph, communities, top_k=10) -> list[Gap]`
   - Gap score: `betweenness × (1/(degree+1))`
   - Sort by gap_score DESC
   - Return top_k
4. Implement `Gap` dataclass (frozen):
   - `node_id`, `node_name`, `communities`, `betweenness`, `degree`, `gap_score`, `suggested_connections`
   - `is_significant` property (gap_score ≥ τ)
5. Implement `format_structural_gaps(gaps) -> str`
   - Human-readable report with community pairs, betweenness, gap_score

**Files:**
- `neuralmind/structural_gaps.py` (NEW)

**Acceptance:**
- `compute_betweenness()` returns correct values on star graph (center=1.0, leaves=0.0)
- `detect_gaps()` ranks low-degree bridge higher than high-degree hub
- Pure Python — `test_no_networkx_import` passes
- No new imports beyond stdlib

---

### B. CLI Command — `neuralmind gaps --structural`

**Gap:** No CLI command surfaces structural gaps.

**Work:**
1. Add `neuralmind gaps --structural` subcommand in `neuralmind/cli.py`
   - `--threshold` (float, default 0.1) — betweenness threshold
   - `--top-k` (int, default 10) — max results
   - `--json` flag for machine-readable output
   - Project path positional arg (default `.`)
2. Wire to `structural_gaps.detect_gaps()` + `format_structural_gaps()`
3. Fail-open: if no graph.json → print "Run `neuralmind build` first", exit 0
4. If <3 communities → print "Need ≥3 communities for gap detection", exit 0

**Files:**
- `neuralmind/cli.py` (MODIFIED — add `gaps --structural` subparser)

**Acceptance:**
- `neuralmind gaps --structural` prints ranked gap list
- `neuralmind gaps --structural --json` returns valid JSON
- `neuralmind gaps --structural --threshold 0.5` returns fewer results than `--threshold 0.0`

---

### C. MCP Tool — `neuralmind_structural_gaps`

**Gap:** No MCP tool for structural gaps.

**Work:**
1. Add `neuralmind_structural_gaps` tool in `neuralmind/mcp_server.py`
   - Follow pattern of `neuralmind_stats`, `neuralmind_query`
   - Params: `project_path` (str), `threshold` (float, 0.1), `top_k` (int, 10)
   - Returns: `{gaps: [...], total_nodes, total_edges, num_communities}`
2. Gap dict shape:
   ```json
   {
     "node_id": "auth/user.py::User",
     "node_name": "User",
     "communities": [0, 2],
     "betweenness": 0.42,
     "degree": 3,
     "gap_score": 0.105,
     "suggested_connections": ["billing/invoice.py::Invoice"]
   }
   ```

**Files:**
- `neuralmind/mcp_server.py` (MODIFIED — add tool)

**Acceptance:**
- MCP tool returns valid JSON with `gaps` key
- Same result as CLI for same project path

---

### D. Test Fixtures

**Gap:** No test fixtures for structural gap testing.

**Work:**
1. Create `tests/fixtures/structural_gaps/` with synthetic graph.json files:
   - `star_graph/` — center + 5 leaves (betweenness = 1.0 for center)
   - `two_community/` — two communities joined by one bridge node
   - `line_graph/` — A-B-C-D chain
   - `multi_bridge/` — 3 communities, 5 bridges
   - `hub_and_spoke/` — hub (should be filtered) + spoke communities
   - `disconnected/` — two components, no bridges
   - `single_node/` — edge case: 1 node
   - `empty/` — edge case: no nodes
   - `large_synthetic/` — 1000 nodes, performance test
   - `corrupt/` — malformed JSON for fail-open testing
2. Generate deterministically via `scripts/gen_structural_gaps_fixtures.py`

**Files:**
- `tests/fixtures/structural_gaps/*/graphify-out/graph.json` (NEW)
- `scripts/gen_structural_gaps_fixtures.py` (NEW)

**Acceptance:**
- All fixtures load as valid graph.json
- Deterministic — regenerating produces identical output
- Star graph fixture: center node has 6 neighbors, 0 edges between leaves

---

### E. Tests — `tests/test_structural_gaps.py`

**Gap:** No test coverage for G5.

**Work:**
Implement all 45 tests from `docs/specs/G5-TEST-PLAN.md`:

| Layer | Count | Key tests |
|-------|-------|-----------|
| Unit — betweenness | 8 | star, line, disconnected, single, empty, normalized, weighted, deterministic |
| Unit — bridge candidates | 5 | two_community, no_bridge, hub_filtered, threshold, min_communities |
| Unit — gap detection | 6 | prioritize_low_degree, sorted, top_k, empty, single_community, json |
| Unit — Gap dataclass | 4 | fields, is_significant, frozen, ordering |
| Unit — formatting | 4 | communities, scores, empty, json |
| Unit — edge weights | 3 | calls_vs_imports, inherits, contains |
| Unit — robustness | 5 | missing_graph, single_community, corrupt, no_networkx, pure_python |
| Integration — CLI | 4 | no_crash, json, threshold, top_k |
| Integration — MCP | 3 | returns_json, project_path, e2e |
| Regression | All | Full existing suite green |

**Files:**
- `tests/test_structural_gaps.py` (NEW)

**Acceptance:**
- 43+/45 tests pass (2 flaky allowed)
- All existing tests still pass (zero regression)
- Performance: 1K nodes < 500ms, 10K nodes < 5s

---

### F. DeepSeek QA Gate (parallel dispatch after A–E complete)

**Policy:** Per-module review. Provider pinned to deepseek-v4-pro, inline code, explicit risk checklist.

**Batches (parallel via delegate_task):**
- Batch 1 (HIGH risk — 1 module each): `structural_gaps.py` (algorithm correctness), `cli.py` (new code)
- Batch 2: test file, fixtures
- Batch 3 (LOW risk): ADR doc, TRD doc

**Patch workflow:** Apply 🔴 CRITICAL + ⚠️ WARNING immediately after verification, pytest after patching.

---

## ACCEPTANCE (ship checklist)

- [ ] `compute_betweenness()` correct on all synthetic fixtures
- [ ] `detect_gaps()` ranks bridges over hubs (gap_score formula works)
- [ ] `neuralmind gaps --structural` prints ranked list
- [ ] `neuralmind gaps --structural --json` returns valid JSON
- [ ] `neuralmind_structural_gaps` MCP tool works
- [ ] 43+/45 new tests pass
- [ ] Zero regressions in existing test suite
- [ ] Pure Python — no NetworkX
- [ ] Brandes exact for <5K nodes, sampling fallback for larger
- [ ] Fail-open on missing graph / single community / corrupt JSON
- [ ] Edge-weighted: calls > inherits > imports > contains > rationale
- [ ] `ROADMAP.md` updated with G5
- [ ] `RELEASE_NOTES_G5.md` drafted
- [ ] DeepSeek QA gate passed

---

## FILES MANIFEST

```
neuralmind/
├── structural_gaps.py          # NEW: Brandes + bridge detection + gap scoring
├── cli.py                      # MODIFIED: add `gaps --structural` subcommand
├── mcp_server.py               # MODIFIED: add neuralmind_structural_gaps tool
tests/
├── test_structural_gaps.py     # NEW: 45 tests
├── fixtures/
│   └── structural_gaps/        # NEW: 10 synthetic fixtures
├── scripts/
│   └── gen_structural_gaps_fixtures.py  # NEW: fixture generator
docs/
├── specs/
│   ├── G5-BRD.md               # DONE
│   ├── G5-TRD.md               # DONE
│   ├── G5-TEST-PLAN.md         # DONE
│   ├── G5-ADR.md               # DONE
│   └── G5-QA-PLAN.md           # TODO (Wave 5+)
├── WAVE8-SESSION-KICKOFF.md    # This file
└── RELEASE_NOTES_G5.md         # TODO (post-ship)
```

---

*Generated by Hermes. G5-SESSION-KICKOFF — v1.0. Claim tier: B+.*
