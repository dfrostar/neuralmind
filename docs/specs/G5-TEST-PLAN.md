# G5 — Structural Gap Detection, Test Plan

**Date:** 2026-07-27
**Module:** `neuralmind/structural_gaps.py` + `neuralmind/cli.py` + `neuralmind/mcp_server.py`
**Commit:** pending
**Claim tier:** B+
**Parent specs:** `docs/specs/G5-BRD.md` · `docs/specs/G5-TRD.md`

---

## 1. Test Strategy

Three layers:
1. **Unit tests** — algorithm correctness on synthetic graphs (deterministic, fast)
2. **Integration tests** — CLI + MCP end-to-end on fixture projects
3. **Regression tests** — existing test suite green (no regressions to G1–G4, L0–L3, synapses)

---

## 2. Coverage Targets

| Layer | Target | Minimum |
|-------|--------|---------|
| `structural_gaps.py` | 95% | 90% |
| `cli.py` (new code) | 100% | 90% |
| `mcp_server.py` (new code) | 100% | 90% |
| Overall project | No regression | Existing ≥ current |

---

## 3. Test Cases

### 3.1 Unit Tests — `tests/test_structural_gaps.py`

#### 3.1.1 Betweenness Centrality

| ID | Test | Fixture | Expected |
|----|------|---------|----------|
| U1 | `test_betweenness_star_graph` | Star graph (1 center + 5 leaves) | Center CB = 1.0, leaves CB = 0.0 |
| U2 | `test_betweenness_line_graph` | Line A-B-C-D | CB(B) = CB(C) > CB(A) = CB(D) |
| U3 | `test_betweenness_disconnected` | Two separate triangles | Each component computed independently |
| U4 | `test_betweenness_single_node` | 1 node, no edges | CB = 0.0 |
| U5 | `test_betweenness_empty` | Empty graph | Returns `{}` |
| U6 | `test_betweenness_normalized_range` | Random graph (20 nodes) | All values in [0.0, 1.0] |
| U7 | `test_betweenness_weighted_edges` | Weighted triangle | Higher weight = more shortest paths |
| U8 | `test_betweenness_deterministic` | Same graph run 10× | Identical output |

#### 3.1.2 Bridge Candidates

| ID | Test | Fixture | Expected |
|----|------|---------|----------|
| B1 | `test_bridge_candidates_two_community` | Two communities joined by one node | Bridge node returned |
| B2 | `test_bridge_candidates_no_bridge` | Two disconnected communities | Empty list |
| B3 | `test_bridge_candidates_hub_filtered` | High-degree hub connecting communities | Hub filtered out (degree penalty) |
| B4 | `test_bridge_candidates_threshold` | Vary τ from 0.0 to 1.0 | Fewer results at higher τ |
| B5 | `test_bridge_candidates_min_communities` | Node in 1 vs 2 vs 3 communities | Only ≥2 returned |

#### 3.1.3 Gap Detection

| ID | Test | Fixture | Expected |
|----|------|---------|----------|
| G1 | `test_detect_gaps_prioritizes_low_degree_bridges` | Mixed degree fixture | Low-degree bridge has highest score |
| G2 | `test_detect_gaps_sorted_descending` | Any graph | Results sorted by gap_score DESC |
| G3 | `test_detect_gaps_top_k` | Fixture with 10+ gaps | Returns exactly top_k |
| G4 | `test_detect_gaps_empty_graph` | Empty graph | Empty list |
| G5 | `test_detect_gaps_single_community` | All nodes in community 0 | Empty list |
| G6 | `test_detect_gaps_json_serializable` | Any graph | Result is JSON-serializable |

#### 3.1.4 Gap Dataclass

| ID | Test | Fixture | Expected |
|----|------|---------|----------|
| D1 | `test_gap_dataclass_fields` | Construct Gap manually | All 7 fields populated |
| D2 | `test_gap_is_significant` | gap_score ≥ τ vs < τ | Correct boolean |
| D3 | `test_gap_frozen` | Attempt mutation | Raises `FrozenInstanceError` |
| D4 | `test_gap_ordering` | Two Gaps with different scores | `gap1 > gap2` if score higher |

#### 3.1.5 Formatting

| ID | Test | Fixture | Expected |
|----|------|---------|----------|
| F1 | `test_format_output_contains_communities` | 2-gap fixture | Output mentions community labels |
| F2 | `test_format_output_contains_scores` | 1-gap fixture | Output shows betweenness + gap_score |
| F3 | `test_format_output_empty` | Empty list | Graceful "no gaps found" message |
| F4 | `test_format_output_json_flag` | `--json` flag | Valid JSON parseable output |

#### 3.1.6 Edge Weights

| ID | Test | Fixture | Expected |
|----|------|---------|----------|
| W1 | `test_edge_weights_calls_vs_imports` | Calls edge vs imports edge | Calls contributes more to CB |
| W2 | `test_edge_weights_inherits` | Inheritance edge | Weight between calls and imports |
| W3 | `test_edge_weights_contains` | File contains function | Lowest weight |

#### 3.1.7 Robustness

| ID | Test | Fixture | Expected |
|----|------|---------|----------|
| R1 | `test_fail_open_on_missing_graph` | No graph.json | Empty list, no crash |
| R2 | `test_fail_open_single_community` | 1 community only | Empty list |
| R3 | `test_fail_open_corrupt_json` | Malformed JSON | Warning + empty list |
| R4 | `test_no_networkx_import` | Import structural_gaps | No NetworkX dependency |
| R5 | `test_pure_python_only` | Import + introspect | Only stdlib + neuralmind |

---

### 3.2 Integration Tests

| ID | Test | Command | Expected |
|----|------|---------|----------|
| I1 | `test_cli_structural_gaps_no_crash` | `neuralmind gaps --structural` on fixture | Exit 0 |
| I2 | `test_cli_structural_gaps_json` | `neuralmind gaps --structural --json` | Valid JSON on stdout |
| I3 | `test_cli_structural_gaps_threshold` | `--threshold 0.5` | Fewer results than `--threshold 0.0` |
| I4 | `test_cli_structural_gaps_top_k` | `--top-k 3` | ≤ 3 results |
| I5 | `test_mcp_tool_returns_json` | Call `neuralmind_structural_gaps` | Valid dict with `gaps` key |
| I6 | `test_mcp_tool_project_path` | MCP tool with valid path | Same result as CLI |
| I7 | `test_end_to_end_real_project` | Run on `neuralmind/` itself | Produces gaps without crash |

---

### 3.3 Regression Tests

| Test | Purpose |
|------|---------|
| Full existing suite | All pre-G5 tests pass unchanged |
| `test_g4_incremental.py` | G4 incremental build unaffected |
| `test_context_selector.py` | L0-L3 progressive disclosure unaffected |
| `test_synapses.py` | Hebbian learning unaffected |
| `test_benchmark.py` | Performance benchmarks unchanged |
| `test_doc_evolver.py` | DocEvolver blind-spot audit unaffected |

---

## 4. Test Fixtures

```
tests/fixtures/structural_gaps/
├── star_graph/
│   └── graphify-out/graph.json          # 6 nodes: 1 center + 5 leaves
├── two_community/
│   └── graphify-out/graph.json          # 2 communities, 1 bridge node
├── line_graph/
│   └── graphify-out/graph.json          # A-B-C-D linear chain
├── multi_bridge/
│   └── graphify-out/graph.json          # 3 communities, 5 bridges
├── hub_and_spoke/
│   └── graphify-out/graph.json          # Hub should be filtered
├── disconnected/
│   └── graphify-out/graph.json          # 2 components, no bridges
├── single_node/
│   └── graphify-out/graph.json          # Edge case: 1 node
├── empty/
│   └── graphify-out/graph.json          # Edge case: no nodes
├── large_synthetic/
│   └── graphify-out/graph.json          # 1000 nodes, performance test
└── corrupt/
    └── graphify-out/graph.json          # Invalid JSON for fail-open
```

### Fixture Generation Script

```python
# scripts/gen_structural_gaps_fixtures.py
# Generates deterministic graph.json files for each fixture
# Run once, commit output. Deterministic — no randomness.
```

---

## 5. Acceptance Criteria

| Criterion | Test | Threshold |
|-----------|------|-----------|
| Betweenness correctness | U1–U8 | 8/8 pass |
| Bridge detection | B1–B5 | 5/5 pass |
| Gap scoring | G1–G6 | 6/6 pass |
| Dataclass integrity | D1–D4 | 4/4 pass |
| Output formatting | F1–F4 | 4/4 pass |
| Edge weights | W1–W3 | 3/3 pass |
| Robustness | R1–R5 | 5/5 pass |
| CLI integration | I1–I4 | 4/4 pass |
| MCP integration | I5–I7 | 3/3 pass |
| No regressions | Full existing suite | 100% pass |
| Performance (1K nodes) | U1 on 1K fixture | < 500ms |
| Performance (10K nodes) | Large synthetic | < 5s |
| No NetworkX | R4 | Clean import |

**Total: 45 test cases. Minimum pass: 43/45 (2 flaky allowed).**

---

## 6. Execution Plan

```bash
# Run G5 tests only
python -m pytest tests/test_structural_gaps.py -v

# Run full regression suite
python -m pytest tests/ -v --tb=short

# Run performance tests
python -m pytest tests/test_structural_gaps.py -k "performance" -v

# Coverage report
python -m pytest tests/test_structural_gaps.py --cov=neuralmind.structural_gaps --cov-report=term-missing
```

---

*Generated by Hermes. G5-TEST-PLAN — v1.0. Claim tier: B+.*
