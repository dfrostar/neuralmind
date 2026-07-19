# Wave 3 — Technical Requirements Document (TRD)

**Date:** 2026-07-17
**Author:** Hermes (architecture)
**Approved by:** <pending> dfrostar review
**Source:** `docs/WAVE3-BRD.md`, `docs/FUTURE-PROOFING-PLAN.md`, `docs/WAVE2-BRD.md`

---

## 1. Architecture Rules (from v2.0 plan, mandatory)

1. **Local-first.** No cloud. No phone-home.
2. **Fail-open.** Every new subsystem degrades gracefully.
3. **Stdlib-only where it counts.**
4. **IR is the contract (after B1).**
5. **Existing public commands are byte-compatible.**
6. **The honesty asset.** `HONEST-ASSESSMENT.md` gets *more* honest.

---

## 2. Shared Contracts (Wave 3a spike)

### 2.1 File Layout

```
neuralmind/
  contracts.py         # TuneableParam dataclass, TUNABLE_PARAMS registry
  tuning.py            # C2: Parameter registry population, bounds validation
  tuner.py             # C3: PopulationTuner evolutionary search
  learned_decay.py    # A3: Per-edge decay rate computation
  sleep.py             # A4: DaemonSleep consolidation pass
  summarize.py         # B4: RAPTOR-style hierarchical summarization
  mcp_http.py          # F1: Streamable HTTP transport
  daemon_memory.py     # F2: Shared daemon memory model

tests/
  test_tuning.py       # ≥15 tests
  test_tuner.py        # ≥20 tests
  test_learned_decay.py # ≥15 tests
  test_sleep.py        # ≥15 tests
  test_summarize.py    # ≥12 tests
  test_mcp_http.py     # ≥12 tests
  test_daemon_memory.py # ≥12 tests
```

### 2.2 Core Contracts (interfaces all workstreams depend on)

```python
# neuralmind/contracts.py — frozen after Wave 3a spike
from dataclasses import dataclass, field
from typing import Any

@dataclass(frozen=True)
class TuneableParam:
    """A single parameter the tuner can optimize."""
    name: str
    min_value: float
    max_value: float
    default: float
    description: str

    def clamp(self, value: float) -> float:
        return max(self.min_value, min(self.max_value, value))

# Registry of all tuneable parameters (populated by C2)
TUNABLE_PARAMS: dict[str, TuneableParam] = {}

def register_param(param: TuneableParam) -> None:
    """Register a tuneable parameter. Idempotent."""
    TUNABLE_PARAMS[param.name] = param

def get_param(name: str) -> TuneableParam | None:
    """Look up a parameter by name."""
    return TUNABLE_PARAMS.get(name)

def clamp_value(name: str, value: float) -> float:
    """Clamp a parameter value to its bounds."""
    param = TUNABLE_PARAMS.get(name)
    if param is None:
        return value
    return param.clamp(value)
```

```python
# Synapse meta table keys (A3, C3)
META_DECAY_RATE_MIN = "self_improve:decay_rate_min"
META_DECAY_RATE_MAX = "self_improve:decay_rate_max"
META_TUNER_INCUMBENT = "self_improve:tuner_incumbent_config"
META_TUNER_FITNESS = "self_improve:tuner_incumbent_fitness"
META_TUNER_PROMOTED_AT = "self_improve:tuner_promoted_at"
```

```python
# Fitness interface (C3 depends on C1)
from neuralmind.fitness import FitnessInputs, FitnessScore, compute_fitness
# FitnessScore.total is the信号 C3 optimizes
```

```python
# Reasoning traces query API (C3, A4 depend on A1)
from neuralmind.traces import TraceStore
# TraceStore.successful_fingerprints(min_success=0.7) → list[str]
# TraceStore.query(since=..., outcome="success", limit=N) → list[ReasoningTrace]
```

---

## 3. C2 — Expanded Parameter Space

### 3.1 Interface

```python
# neuralmind/tuning.py
from neuralmind.contracts import TuneableParam, register_param, get_param, clamp_value

# Parameter definitions (populated at module load)
DEFAULT_PARAMS = [
    TuneableParam("SYNAPSE_BOOST_WEIGHT", 0.0, 2.0, 0.3, "Synapse-driven recall boost weight"),
    TuneableParam("STRUCTURAL_BOOST_WEIGHT", 0.0, 2.0, 0.35, "Structural edge recall boost weight"),
    TuneableParam("SPREAD_DEPTH", 1, 5, 2, "Synapse spread depth"),
    TuneableParam("L0_MAX_TOKENS", 50, 300, 150, "L0 identity layer token budget"),
    TuneableParam("L1_MAX_TOKENS", 200, 1000, 600, "L1 summary layer token budget"),
    TuneableParam("L2_MAX_TOKENS", 400, 1500, 800, "L2 on-demand layer token budget"),
    TuneableParam("L3_MAX_TOKENS", 500, 2000, 1000, "L3 search layer token budget"),
    TuneableParam("STRUCTURAL_HUB_DEGREE", 10, 100, 50, "Structural hub degree for normalization"),
    TuneableParam("DECAY_RATE_MIN", 1.0, 30.0, 3.0, "Minimum per-edge half-life (days)"),
    TuneableParam("DECAY_RATE_MAX", 30.0, 365.0, 120.0, "Maximum per-edge half-life (days)"),
]

def init_registry() -> None:
    """Register all default parameters. Idempotent."""
    for param in DEFAULT_PARAMS:
        register_param(param)

def get_bounds(name: str) -> tuple[float, float]:
    """Get (min, max) for a parameter. Returns (0.0, 1.0) if unknown."""
    param = get_param(name)
    if param is None:
        return (0.0, 1.0)
    return (param.min_value, param.max_value)
```

### 3.2 Integration with existing code

- `context_selector.py`: Replace hardcoded `SYNAPSE_BOOST_WEIGHT = 0.3` with `get_param("SYNAPSE_BOOST_WEIGHT").default`
- `synapses.py`: Replace hardcoded `HALF_LIFE_DAYS = 30.0` with `get_param("DECAY_RATE_MIN").default` as floor
- No change to output shape (byte-compatible)

### 3.3 Persistence

- Parameters stored in synapse meta table as JSON: `self_improve:params = {"SYNAPSE_BOOST_WEIGHT": 0.45, ...}`
- If meta key missing, fall back to registry defaults
- Fail-open: unknown keys logged, not applied

---

## 4. C3 — Population-Based Evolutionary Search

### 4.1 Interface

```python
# neuralmind/tuner.py
from dataclasses import dataclass
from typing import Any
from neuralmind.fitness import FitnessInputs, FitnessScore
from neuralmind.tuning import get_param, clamp_value

@dataclass
class CandidateConfig:
    """One candidate parameter set."""
    params: dict[str, float]
    fitness: float = 0.0

class PopulationTuner:
    def __init__(
        self,
        population_size: int = 15,
        generations: int = 8,
        hysteresis: float = 0.05,
        uniform_explore_p: float = 0.15,
    ):
        self.population_size = population_size
        self.generations = generations
        self.hysteresis = hysteresis
        self.uniform_explore_p = uniform_explore_p

    def sample_candidate(self, incumbent: dict[str, float]) -> dict[str, float]:
        """Gaussian perturbation around incumbent (or uniform explore)."""
        ...

    def evaluate_candidate(
        self,
        params: dict[str, float],
        project_path: str,
        store: Any,  # SynapseStore
    ) -> float:
        """Evaluate a candidate against C1 fitness on real query traces."""
        ...

    def promote_if_better(
        self,
        candidate: dict[str, float],
        fitness: float,
    ) -> bool:
        """Promote candidate if fitness > incumbent * (1 + hysteresis)."""
        ...

    def run_generation(
        self,
        project_path: str,
    ) -> tuple[dict[str, float], float]:
        """Run one full generation. Returns (best_config, best_fitness)."""
        ...
```

### 4.2 Evaluation flow

1. Read `reasoning_traces` from last N days
2. Compute `re_query_rate` + `transition_margin` (session health)
3. Compute `faithfulness_delta` (retrieval quality) by re-running retrieval with candidate params
4. Compute `efficiency` = token reduction ratio
5. Feed three axes into `compute_fitness()` from C1
6. Return `FitnessScore.total`

### 4.3 Fail-open rules

- If fitness eval raises, incumbent stands
- If no query traces exist, skip generation
- If promotion would set any param out of bounds, clamp and retry
- Log every generation result for audit

---

## 5. A3 — Learned Per-Edge Decay

### 5.1 Schema migration

```sql
-- Add per-edge half-life override (nullable; fall back to namespace default)
ALTER TABLE synapses ADD COLUMN half_life_days REAL;
ALTER TABLE synapses ADD COLUMN learned_at REAL;
```

Migration in `synapses.py`:
- Check if column exists; if not, ALTER
- Backfill: set `half_life_days = NULL` for existing rows (uses namespace default)
- Version-stamp the migration

### 5.2 Per-edge rate computation

```python
# neuralmind/learned_decay.py
def compute_edge_half_life(
    activation_count: int,
    last_activated: float,
    first_activated: float,
    namespace_default: float,
) -> float:
    """Adapt half-life from reinforcement frequency + recency.

    Edges with frequent reinforcement get longer half-lives.
    Edges that are rarely reinforced decay faster.
    Bounded to [HALF_LIFE_MIN, HALF_LIFE_MAX].
    """
    ...
```

### 5.3 Integration with synapses.py

- `decay_weight()`: use `half_life_days if not None else namespace_default`
- `reinforce()`: update `learned_at` and recompute `half_life_days`
- C1 fitness eval: report learned decay effectiveness
- C3 tuner: can propose `DECAY_RATE_MIN`/`DECAY_RATE_MAX` bounds

---

## 6. A4 — Sleep Consolidation

### 6.1 Interface

```python
# neuralmind/sleep.py
class DaemonSleep:
    def __init__(
        self,
        interval_days: float = 7.0,
        stale_days: float = 60.0,
        prune_threshold: float = 0.01,
    ):
        self.interval_days = interval_days
        self.stale_days = stale_days
        self.prune_threshold = prune_threshold

    def should_run(self, store: Any) -> bool:
        """Check if enough time has passed since last sleep."""
        ...

    def run(self, project_path: str) -> dict[str, Any]:
        """Execute the sleep pass. Returns stats."""
        ...

    def prune_redundant_edges(self, conn: Any) -> int:
        """Prune edges below threshold with no reinforcement in N days."""
        ...

    def promote_ltp_edges(self, conn: Any) -> int:
        """Promote LTP edges that survived decay."""
        ...

    def emit_team_bundle(self, store: Any) -> dict[str, Any]:
        """Emit consolidated team-baseline bundle."""
        ...

    def detect_stale_edges(self, conn: Any) -> list[str]:
        """Flag edges with no reinforcement in N days."""
        ...
```

### 6.2 Fail-open rules

- Any exception during a sub-step is logged; other sub-skeps continue
- Never deletes edges above `PRUNE_THRESHOLD` regardless of staleness
- Team bundle emission is best-effort (doesn't block query/build/search)

---

## 7. B4 — Hierarchical Summarization

### 7.1 Interface

```python
# neuralmind/summarize.py
from typing import Callable

class RaptorSummarizer:
    def __init__(
        self,
        depth: int = 3,
        max_tokens_per_layer: int = 500,
        embed_fn: Callable[[str], list[float]] | None = None,
    ):
        self.depth = depth
        self.max_tokens_per_layer = max_tokens_per_layer
        self.embed_fn = embed_fn

    def summarize(self, text: str, layer: int = 0) -> str:
        """Recursive RAPTOR-style summarization."""
        ...

    def get_l2_summary(self, community_id: int, store: Any) -> str:
        """Generate a learned summary for an L2 community."""
        ...
```

### 7.2 Gating

- `NEURALMIND_SUMMARIZE=1` to enable
- Falls back to hand-tuned constants if disabled
- Layer budgets remain byte-compatible

---

## 8. F1 — Streamable HTTP MCP Transport

### 8.1 Interface

```python
# neuralmind/mcp_http.py
from starlette.applications import Starlette
from starlette.routing import Route
from mcp.server.streamable_http import StreamableHTTPServer

class StreamableHTTPMCP:
    def __init__(self, mind: Any):  # NeuralMind instance
        self.mind = mind
        self.sessions: dict[str, Any] = {}

    def create_session(self, client_id: str) -> str:
        """Create a new session. Returns session_id."""
        ...

    def handle_request(self, request: Any) -> Any:
        """Handle an MCP request over Streamable HTTP."""
        ...

    def get_starlette_app(self) -> Starlette:
        """Return the Starlette application for mounting."""
        ...
```

### 8.2 Fallback

- Stdio transport retained; env `NEURALMIND_MCP_TRANSPORT=streamable_http` to enable
- Default: stdio (byte-compatible)

---

## 9. F2 — Shared Daemon Memory

### 9.1 Interface

```python
# neuralmind/daemon_memory.py
class SharedDaemonMemory:
    def __init__(self, project_path: str):
        self.project_path = project_path
        self._instance: Any | None = None  # NeuralMind instance
        self._clients: dict[str, Any] = {}  # client_id → access scope

    def get_instance(self, client_id: str) -> Any:
        """Get or create the warm NeuralMind instance for a client."""
        ...

    def register_client(self, client_id: str, project_path: str) -> None:
        """Register a new MCP client."""
        ...

    def is_authorized(self, client_id: str, target_project: str) -> bool:
        """Check if a client can access another project's synapses."""
        ...

    def release_client(self, client_id: str) -> None:
        """Release a client's resources."""
        ...
```

### 9.2 Access scoping

- A client can only read synapses in the `shared` namespace OR its own project's namespace
- Cross-project reads are denied unless the target project has been explicitly shared
- Authorization enforced at query layer, not at the synapse store level

---

## 10. Testing Strategy

| Test file | Count | Key cases |
|---|---|---|
| `test_tuning.py` | ≥15 | Registry, bounds, clamp, persistence |
| `test_tuner.py` | ≥20 | Sampling, mutation, fitness eval, promotion, hysteresis |
| `test_learned_decay.py` | ≥15 | Rate computation, bounds, schema migration, fallback |
| `test_sleep.py` | ≥15 | Pruning, LTP promotion, staleness, scheduling, fail-open |
| `test_summarize.py` | ≥12 | Recursive summarization, depth selector, fallback |
| `test_mcp_http.py` | ≥12 | Session mgmt, multi-client, stdio fallback, OAuth |
| `test_daemon_memory.py` | ≥12 | Shared instance, access scoping, cold-start fallback |

All existing tests must still pass (regression gate).

---

## 11. Integration Points

| Existing Module | New Module | What Changes |
|---|---|---|
| `context_selector.py` | `tuning.py` | Reads from registry instead of hardcoded constants |
| `synapses.py` | `learned_decay.py` | Uses per-edge `half_life_days` when available |
| `synapses.py` | `sleep.py` | Sleep pass opens connection, runs, closes |
| `core.py` | `tuner.py` | SessionStart hook triggers tuner generation |
| `core.py` | `sleep.py` | Daemon scheduler triggers sleep pass |
| `core.py` | `daemon_memory.py` | Warm registry shared across MCP clients |
| `server.py` (MCP) | `mcp_http.py` | Streamable HTTP transport alongside stdio |

No new middleware, no new API routes, no new RSC, no new i18n (per project constraints).

---

*Prepared by Hermes. Pending maintainer approval.*
