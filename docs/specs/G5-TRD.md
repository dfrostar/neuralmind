# G5 — Structural Gap Detection, Technical Requirements Document (TRD)

**Date:** 2026-07-27
**Module:** `neuralmind/structural_gaps.py` (+ `neuralmind/cli.py`, `neuralmind/mcp_server.py`)
**Commit:** pending
**Claim tier:** B+
**Parent spec:** `docs/specs/G5-BRD.md`

---

## 1. Scope

Add InfraNodus-style betweenness-centrality gap detection to NeuralMind's structural graph. Surface cross-community bridge candidates and structural blind spots via CLI + MCP tool.

**In scope:**
- Brandes betweenness-centrality algorithm (pure Python, stdlib-only)
- Bridge candidate identification (nodes bridging ≥2 communities)
- Gap scoring: `betweenness × inverse_degree`
- CLI: `neuralmind gaps --structural`
- MCP tool: `neuralmind_structural_gaps`

**Out of scope:** Visualization, AI suggestions, temporal tracking, synapse integration, incremental betweenness update.

---

## 2. Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        G5 ARCHITECTURE                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────┐     ┌──────────────────────┐     ┌─────────────┐  │
│  │ graph.json   │────▶│ structural_gaps.py   │────▶│ CLI / MCP   │  │
│  │ (existing)   │     │                      │     │             │  │
│  │              │     │ compute_betweenness()│     │ $ nm gaps   │  │
│  │ nodes[]      │     │ find_bridge_cands()  │     │   --struct  │  │
│  │ links[]      │     │ detect_gaps()        │     │             │  │
│  │ communities  │     │ format_struct_gaps() │     │ MCP tool    │  │
│  └──────────────┘     └──────────────────────┘     └─────────────┘  │
│                              │                                       │
│                              ▼                                       │
│                     ┌────────────────┐                               │
│                     │ Gap dataclass  │                               │
│                     │ - node_id      │                               │
│                     │ - node_name    │                               │
│                     │ - communities  │                               │
│                     │ - betweenness  │                               │
│                     │ - degree       │                               │
│                     │ - gap_score    │                               │
│                     │ - suggested    │                               │
│                     └────────────────┘                               │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Data Flow

```
1. Load graph.json from graphify-out/
2. Extract nodes, edges, community assignments
3. Build adjacency list (weighted by edge type: calls > imports > inherits)
4. Compute betweenness centrality (Brandes algorithm)
5. Identify bridge candidates (nodes with betweenness ≥ τ, appearing in ≥2 communities)
6. Score gaps: gap_score = betweenness × (1 / (degree + 1))
7. Sort by gap_score DESC
8. Return top_k gaps
```

---

## 3. Data Model

### Gap Dataclass

```python
@dataclass(frozen=True)
class Gap:
    """A structural gap — a node that bridges communities but is under-connected."""
    node_id: str
    node_name: str
    communities: tuple[str, ...]  # sorted community labels this node bridges
    betweenness: float             # [0, 1] normalized
    degree: int                    # number of direct neighbors
    gap_score: float               # betweenness * (1 / (degree + 1))
    suggested_connections: tuple[str, ...]  # node_ids this could connect to

    @property
    def is_significant(self) -> bool:
        return self.gap_score >= GAP_THRESHOLD_DEFAULT
```

### Edge Weights

| Edge Type | Weight | Rationale |
|-----------|--------|-----------|
| `calls` | 1.0 | Strongest structural relationship |
| `imports_from` | 0.8 | Dependency, weaker than calls |
| `inherits` | 0.9 | Strong OOP relationship |
| `contains` | 0.3 | Structural containment, not semantic |
| `rationale_for` | 0.2 | Docstring link, weakest |

---

## 4. Algorithms

### 4.1 Betweenness Centrality (Brandes)

For a graph G = (V, E) with n nodes:

```
CB(v) = Σ_{s≠v≠t} (σ_st(v) / σ_st)
```

Where σ_st = number of shortest paths from s to t, σ_st(v) = number of those passing through v.

**Complexity:** O(VE) for unweighted, O(VE + V² log V) with weighted (Dijkstra).
**For NeuralMind graphs:** V ≤ 10K, E ≤ 50K typical. O(VE) = ~5×10⁸ operations worst case. Acceptable.

**Optimization:** Sample if V > MAX_BETWEENNESS_NODES (default 5K). Use k-approximate betweenness with k = min(V, 1000) for large graphs.

### 4.2 Normalization

```
normalized = raw / ((n-1)(n-2))     for undirected graphs
```

So CB ∈ [0, 1].

### 4.3 Bridge Candidate Detection

A node `v` is a bridge candidate if:
1. `betweenness(v) ≥ τ` (default τ = 0.1)
2. `v` appears in ≥ 2 distinct community neighborhoods
3. `degree(v) ≤ median_degree × 2` (filters out hubs)

### 4.4 Gap Score

```
gap_score(v) = CB(v) × (1 / (deg(v) + 1))
```

Higher = more critical missing connector.

---

## 5. API Surface

### 5.1 `structural_gaps.py`

```python
def compute_betweenness(
    graph: dict,
    *,
    normalized: bool = True,
    weight: str = "weight",
) -> dict[str, float]:
    """Return {node_id: betweenness_centrality}."""

def find_bridge_candidates(
    graph: dict,
    communities: dict[str, int],
    *,
    threshold: float = 0.1,
    min_communities: int = 2,
) -> list[str]:
    """Return node_ids that bridge communities."""

def detect_gaps(
    graph: dict,
    communities: dict[str, int],
    *,
    top_k: int = 10,
    threshold: float = 0.1,
) -> list[Gap]:
    """Return ranked list of structural gaps."""

def format_structural_gaps(gaps: list[Gap]) -> str:
    """Human-readable report."""
```

### 5.2 CLI

```bash
neuralmind gaps --structural [project_path] [--threshold 0.1] [--top-k 10] [--json]
```

Options:
- `--structural`: use structural gap detection (vs existing `--mock-only` test coverage gaps)
- `--threshold`: betweenness threshold (default 0.1)
- `--top-k`: max results (default 10)
- `--json`: machine-readable output

### 5.3 MCP Tool

```python
@mcp_tool("neuralmind_structural_gaps")
def structural_gaps(
    project_path: str,
    threshold: float = 0.1,
    top_k: int = 10,
) -> dict:
    """Return structural gap analysis."""

# Returns:
# {
#   "gaps": [
#     {
#       "node_id": "auth/user.py::User",
#       "node_name": "User",
#       "communities": [0, 2],
#       "betweenness": 0.42,
#       "degree": 3,
#       "gap_score": 0.105,
#       "suggested_connections": ["billing/invoice.py::Invoice", "auth/session.py::Session"]
#     }
#   ],
#   "total_nodes": 150,
#   "total_edges": 420,
#   "num_communities": 5
# }
```

---

## 6. Integration Points

### 6.1 Graph Source

Reads `graphify-out/graph.json` — same as `embedder.py`, `context_selector.py`. No new artifacts.

### 6.2 Community Source

Communities come from `graph.json` `community` field (Louvain, populated by G3). If no communities exist, G5 v1 will run Louvain inline using `neuralmind/modularity.py::louvain_clustering`.

### 6.3 CLI Registration

Add subcommand in `neuralmind/cli.py`:
```python
gaps_p = subparsers.add_parser("gaps", ...)
gaps_p.add_argument("--structural", action="store_true", ...)
```

### 6.4 MCP Registration

Add tool in `neuralmind/mcp_server.py` following existing pattern (`neuralmind_stats`, `neuralmind_query`, etc.).

---

## 7. Error Handling

| Condition | Behavior |
|-----------|----------|
| Missing graph.json | Print "No graph found. Run `neuralmind build` first." |
| Empty graph (no nodes) | Return empty list |
| Single community | Return empty list (gaps need ≥2 communities) |
| Corrupt JSON | Print warning, return empty |
| Graph too large (>10K nodes) | Log warning, sample for betweenness |
| Missing community field | Run Louvain inline, log info |

---

## 8. Performance Budget

| Metric | Target | Max |
|--------|--------|-----|
| Build graph.json | existing | existing |
| Compute betweenness (1K nodes) | < 500ms | < 1s |
| Compute betweenness (10K nodes) | < 5s | < 15s |
| CLI total (incl I/O) | < 10s | < 30s |
| MCP tool response | < 10s | < 30s |
| Memory | < 500MB | < 1GB |

---

## 9. Test Plan

### 9.1 Unit Tests (`tests/test_structural_gaps.py`)

| Test | Input | Expected |
|------|-------|----------|
| `test_betweenness_star_graph` | Star graph (center connects to all) | Center CB = 1.0 |
| `test_betweenness_line_graph` | Line graph A-B-C-D | B, C have higher CB than A, D |
| `test_betweenness_disconnected` | Two disconnected components | Each component independent |
| `test_bridge_candidates_two_community` | Two communities joined by single node | Bridge node identified |
| `test_detect_gaps_prioritizes_low_degree_bridges` | Fixture with varied degrees | Low-degree bridge scores highest |
| `test_gap_dataclass_fields` | Construct Gap | All fields populated |
| `test_format_output_contains_communities` | Format gaps list | Output mentions community pairs |
| `test_fail_open_on_missing_graph` | No graph file | Empty list, no crash |
| `test_fail_open_single_community` | Graph with 1 community | Empty list |
| `test_no_networkx_import` | Import structural_gaps | No NetworkX in imports |
| `test_edge_weights_calls_stronger` | Calls vs imports edge | Calls contributes more to CB |
| `test_normalized_betweenness_range` | Any graph | All values in [0, 1] |

### 9.2 Integration Tests

| Test | Input | Expected |
|------|-------|----------|
| `test_cli_structural_gaps_no_crash` | Run CLI on fixture | Exit 0 |
| `test_cli_json_output` | `--json` flag | Valid JSON |
| `test_mcp_tool_returns_json` | Call MCP tool | Valid dict with gaps key |
| `test_end_to_end_on_neuralmind_self` | Run on neuralmind itself | Produces gaps without crash |

### 9.3 Test Fixtures

```
tests/fixtures/structural_gaps/
├── star_graph/          # star topology, known betweenness
├── two_community/       # two communities, one bridge
├── line_graph/          # linear chain
├── multi_bridge/        # multiple bridge candidates
└── real_world_small/    # 50-node realistic fixture
```

---

## 10. Future Work

| Item | Priority | Blocker |
|------|----------|---------|
| Temporal gap tracking | Medium | Needs gap history store |
| AI-powered gap resolution | Medium | LLM integration, prompt design |
| Gap visualization in graph view | Low | Frontend (Sigma.js/D3) |
| Synapse integration (bridge seeds) | Low | Synapse store API change |
| Incremental betweenness update | Low | Approximate algorithms |
| Leiden algorithm for better communities | Low | `python-igraph` C dep |

---

## 11. File Manifest

```
neuralmind/
├── structural_gaps.py          # NEW: core algorithm
├── cli.py                      # MODIFIED: add --structural subcommand
├── mcp_server.py               # MODIFIED: add structural_gaps tool
tests/
├── test_structural_gaps.py     # NEW: unit tests
├── fixtures/
│   └── structural_gaps/        # NEW: test fixtures
docs/
├── specs/
│   ├── G5-BRD.md               # DONE
│   ├── G5-TRD.md               # THIS FILE
│   └── G5-TEST-PLAN.md         # TODO (or fold into TRD)
```

---

*Generated by Hermes. G5-TRD — v1.0. Claim tier: B+.*
