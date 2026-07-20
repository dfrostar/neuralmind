# Wave 4 — Technical Requirements Document (TRD)

**Date:** 2026-07-21
**Repos:** `dfrostar/neuralmind` (public), `dfrostar/neuralmind-autopilot` (PRIVATE)
**BRD:** `docs/WAVE4-BRD.md`
**Previous TRDs:** Wave 1 (D/B1/G1), Wave 2 (A1-A2/B2-B3/C1/G2), Wave 3 (C2-C3/A3-A4/B4/F1-F2)
**NeuralMind release:** v1.1.0 → v1.2.0
**Autopilot release:** v0.8.0 → v0.9.0

---

## 1. Scope

Wave 4 closes the self-improvement loop (C4), completes the quality harness (D3/D4), wires team-memory merge semantics (E1-E4), adds observability (F3/F4), and raises graph precision (G3/G4). 11 workstreams total.

Cross-references:
- FUTURE-PROOFING-PLAN.md §9 (sequence) and §10 (decisions)
- WAVE3-TRD (C2-C3, A3-A4, F1-F2)
- WAVE2-TRD (C1, A1-A2, B2-B3, G2)
- WAVE1-TRD (D, B1, G1)

---

## 2. Architecture

### 2.1 Self-Improvement Loop (C4)

```
┌─────────────────────────────────────────────────────┐
│ Autopilot (operator, private)                        │
│                                                       │
│  tuner.py                                             │
│    run_generation()                                   │
│      → evaluate_candidate() → fitness (C1)           │
│      → if best > incumbent + margin:                  │
│          experiment_runner.run_experiment()            │
│            → harness.evaluate() → verdict             │
│            → promotion_engine.ship_or_rollback()      │
│                ├─ ship: apply_config(best)             │
│                └─ rollback: restore_config(incumbent) │
│                                                       │
│  promotion_engine.py                                  │
│    ship_callable = apply_config  ← wired in Wave 4    │
│    rollback_callable = restore_config  ← wired now    │
│                                                       │
│  experiment_runner.py                                 │
│    run_experiment(candidate, baseline)                │
│      → harness.evaluate(candidate) → fitness_delta    │
│      → if fitness_delta >= MARINEL: verdict = SHIP   │
│      → if fitness_delta < 0: verdict = ROLLBACK      │
│      → else: verdict = HOLD                           │
└─────────────────────────────────────────────────────┘
```

### 2.2 Team Memory Merge (E1-E4)

```
┌─────────────────────────────────────────────────────┐
│ NeuralMind (product, public)                          │
│                                                       │
│  team_memory.py                                       │
│    publish(bundle, contributor)                       │
│      → contribution_scoring.score(contributor)        │
│      → merge_semantics.merge(bundle, quality_score)   │
│      │  ├─ same edge, higher quality: winner wins     │
│      │  └─ same edge, lower quality: loser decays     │
│      → if team_baseline: flag_for_review()            │
│      → if stale(team_edge): flag_for_prune()          │
│                                                       │
│  contribution_scoring.py (NEW)                        │
│    score(contributor) → float                         │
│      → lookup E1.5 eval delta for contributor         │
│      → normalize to [0.1, 1.0] range                 │
│                                                       │
│  merge_semantics.py (EXTEND)                          │
│    merge(bundle_a, bundle_b, quality_a, quality_b)    │
│      → entity_resolution.resolve()  (A2)              │
│      → for conflicting edges: weight by quality       │
│      → loser: apply accelerated decay                 │
│                                                       │
│  team_staleness.py (EXTEND)                           │
│    detect_stale(edges, threshold_days=60)             │
│      → flag edges with no reinforcement > threshold   │
│      → sleep consolidation prunes flagged edges (A4)  │
└─────────────────────────────────────────────────────┘
```

### 2.3 Metrics Pipeline (F3/F4)

```
┌─────────────────────────────────────────────────────┐
│ NeuralMind daemon                                     │
│                                                       │
│  daemon.py                                            │
│    on_query_complete(query, result, metrics)          │
│      → metrics_pipeline.log({                         │
│          ts: now(),                                   │
│          query_fp: hash(query),                       │
│          latency_ms: elapsed,                         │
│          reuse_rate: result.reused / result.total,    │
│          success: result.success,                     │
│          token_cost: result.tokens,                   │
│          synapse_activations: result.activations,     │
│        })                                             │
│      → async write to .neuralmind/metrics/*.jsonl     │
│                                                       │
│  backpressure.py (NEW)                                │
│    acquire(timeout=0.1) → bool                        │
│      → if queue_depth >= MAX: circuit.open()          │
│      → if circuit.open: fail fast                     │
│      → if recovery_timeout elapsed: circuit.half_open │
│                                                       │
│  metrics_pipeline.py (EXTEND)                         │
│    log(entry) → None                                  │
│      → async write, bounded retention (30 days)       │
│      → feeds fitness function (C1)                    │
│      → feeds team-memory quality scoring (E1)         │
└─────────────────────────────────────────────────────┘
```

### 2.4 Graph Precision (G3/G4)

```
┌─────────────────────────────────────────────────────┐
│ NeuralMind graphgen                                   │
│                                                       │
│  graphgen.py                                          │
│    build_graph()                                      │
│      → if incremental:                                │
│          incremental_extract.scan_files() → changed    │
│          incremental_extract.get_changed_with_dependents() │
│          re-extract symbols from changed + dependents  │  ← G4 NEW
│          skip unchanged files                          │
│      → _assign_communities()                          │
│          → if G3 enabled: louvain/Leiden algorithm     │  ← G3 NEW
│          → else: balanced-per-file (legacy)            │
│                                                       │
│  louvain.py (NEW)                                     │
│    cluster(graph) → communities                        │
│      → Louvain modularity optimization                │
│      → deterministic seed for reproducibility          │
│      → fallback: balanced-per-file if graph too small │
└─────────────────────────────────────────────────────┘
```

---

## 3. Component Requirements

### 3.1 C4 — CI-Gated Tuner Promotion

```python
# autopilot/experiment_runner.py — extend run_experiment()
def run_experiment(self, candidate: dict, baseline: dict) -> Verdict:
    candidate_fitness = self._evaluate(candidate)
    baseline_fitness = self._evaluate(baseline)
    delta = candidate_fitness - baseline_fitness

    if delta >= PROMOTION_MARGIN:  # default 0.05
        return Verdict.SHIP
    elif delta < 0:
        return Verdict.ROLLBACK
    else:
        return Verdict.HOLD

# autopilot/promotion_engine.py — wire real callables
def ship_or_rollback(verdict, candidate, incumbent):
    if verdict == Verdict.SHIP:
        apply_config(candidate)  # was no-op lambda
        log.info(f"Promoted candidate: fitness delta={delta:.4f}")
    elif verdict == Verdict.ROLLBACK:
        restore_config(incumbent)
        log.info(f"Rolled back to incumbent")
    else:
        log.info(f"Hold: candidate within hysteresis margin")
```

### 3.2 D3 — Populate Judge Transcripts

```bash
# Run on >= 3 projects, commit transcripts
neuralmind benchmark --public --judge --project /path/to/project1
neuralmind benchmark --public --judge --project /path/to/project2
neuralmind benchmark --public --judge --project /path/to/project3
# Commit: bench/public/judge/<project>_<date>.json
```

### 3.3 D4 — Per-Language Fixtures

```python
# tests/fixtures/ts_fixture.json, go_fixture.json, rs_fixture.json, java_fixture.json
{
  "language": "typescript",
  "queries": [
    {"query": "How does auth middleware work?", "gold_facts": ["src/auth/middleware.ts:45", "src/auth/verify.ts:12"]},
    ...
  ]
}
```

### 3.4 E1 — Contribution-Quality Scoring

```python
# neuralmind/contribution_scoring.py (NEW)
class ContributionScorer:
    def __init__(self, eval_db_path: Path):
        self.eval_db = eval_db_path

    def score(self, contributor: str) -> float:
        """Return quality score in [0.1, 1.0] based on E1.5 eval delta."""
        delta = self._lookup_eval_delta(contributor)
        return clamp(0.5 + delta, 0.1, 1.0)
```

### 3.5 E2 — Merge Semantics

```python
# neuralmind/merge_semantics.py — extend merge()
def merge_bundles(bundle_a, bundle_b, quality_a, quality_b):
    resolved = entity_resolution.resolve(bundle_a, bundle_b)  # A2
    for edge in resolved.conflicts:
        if quality_a >= quality_b:
            edge.weight = bundle_a.edges[edge.id].weight
            decay(bundle_b.edges[edge.id], factor=0.5)  # loser decays
        else:
            edge.weight = bundle_b.edges[edge.id].weight
            decay(bundle_a.edges[edge.id], factor=0.5)
    return resolved
```

### 3.6 E3 — Peer Review Gate

```python
# neuralmind/team_memory.py — extend publish()
def publish(self, bundle, contributor):
    if bundle.target == "team_baseline":
        self._flag_for_review(bundle, contributor)
        # PR created by operator; bundle not committed until PR merged
    else:
        self._commit_directly(bundle, contributor)
```

### 3.7 E4 — Staleness Detection

```python
# neuralmind/team_staleness.py — extend detect_stale()
def detect_stale(self, edges, threshold_days=60):
    stale = []
    for edge in edges:
        if edge.namespace != "team_baseline":
            continue
        last_reinforcement = self._last_reinforced(edge)
        if last_reinforcement and days_since(last_reinforcement) > threshold_days:
            stale.append(edge)
    return stale
```

### 3.8 F3 — Tool-Use Metrics Pipeline

```python
# neuralmind/metrics_pipeline.py — extend log()
def log(self, entry: dict) -> None:
    """Async write to .neuralmind/metrics/*.jsonl with bounded retention."""
    self._buffer.append(entry)
    if len(self._buffer) >= FLUSH_SIZE:
        self._flush()
```

### 3.9 F4 — Backpressure + Circuit Breakers

```python
# neuralmind/backpressure.py (NEW)
class CircuitBreaker:
    def __init__(self, max_concurrent=5, recovery_timeout=30):
        self.max_concurrent = max_concurrent
        self.recovery_timeout = recovery_timeout
        self.state = "closed"  # closed | open | half-open
        self._active = 0
        self._last_failure = None

    def acquire(self, timeout=0.1) -> bool:
        if self.state == "open":
            if time.time() - self._last_failure > self.recovery_timeout:
                self.state = "half-open"
            else:
                return False
        if self._active < self.max_concurrent:
            self._active += 1
            return True
        return False

    def release(self):
        self._active -= 1

    def record_failure(self):
        self._last_failure = time.time()
        self.state = "open"
```

### 3.10 G3 — Modularity Clustering

```python
# neuralmind/louvain.py (NEW)
def cluster(graph: Graph) -> dict[str, int]:
    """Louvain modularity optimization. Returns {node_id: community_id}."""
    # Use python-louvain or Leidenalg package
    # Fallback: balanced-per-file if graph < 10 nodes
    partition = community.best_partition(graph.to_networkx())
    return partition
```

### 3.11 G4 — Incremental Re-extraction

```python
# neuralmind/graphgen.py — extend build_graph()
def build_graph(self, incremental=True):
    if incremental:
        changed = self.incremental_extract.scan_files()
        with_dependents = self.incremental_extract.get_changed_with_dependents(changed)
        self._re_extract(with_dependents)  # NEW: re-extract symbols
        self._re_embed(with_dependents)
    else:
        self._full_build()
```

---

## 4. Database

No new tables. Uses existing:
- `tuner_history` (C4 promotion/rollback events)
- `reasoning_traces` (A1 — feeds fitness function)
- `synapses.db` (team memory edges)
- `.neuralmind/metrics/*.jsonl` (F3 metrics)

---

## 5. Security

1. **Tuner promotion is fail-closed.** Harness unavailable → no promotion.
2. **Merge semantics are one-directional.** Loser decays; no bidirectional loops.
3. **Metrics are local-only.** JSONL files in `.neuralmind/`, never uploaded.
4. **Peer review gate is operator-controlled.** No automated commit to team baseline.
5. **Circuit breaker prevents resource exhaustion.** Bounded queue depth.

---

## 6. Test Plan

See `docs/WAVE4-TEST-PLAN.md`.

| Test | File | Covers |
|------|------|--------|
| test_tuner_promotes_on_positive_delta | test_experiment_runner.py | C4 |
| test_tuner_rolls_back_on_negative_delta | test_experiment_runner.py | C4 |
| test_tuner_holds_within_hysteresis | test_experiment_runner.py | C4 |
| test_judge_transcripts_exist | test_benchmark.py | D3 |
| test_per_language_fixtures | test_eval.py | D4 |
| test_contribution_scoring | test_contribution_scoring.py | E1 |
| test_merge_semantics_conflict_resolution | test_merge_semantics.py | E2 |
| test_peer_review_gate | test_team_memory.py | E3 |
| test_staleness_detection | test_team_staleness.py | E4 |
| test_metrics_pipeline_logging | test_metrics_pipeline.py | F3 |
| test_circuit_breaker_opens_on_overload | test_backpressure.py | F4 |
| test_louvain_clustering | test_graphgen.py | G3 |
| test_incremental_re_extraction | test_incremental_extract.py | G4 |

---

## 7. Acceptance

- [ ] C4: Tuner auto-promotes or auto-rolls-back based on harness verdict
- [ ] D3: Judge transcripts committed for >= 3 projects
- [ ] D4: Per-language fixtures pass eval
- [ ] E1: Contribution-quality scoring weights edges
- [ ] E2: Merge semantics resolve conflicts by quality
- [ ] E3: Peer review gate flags team-baseline contributions
- [ ] E4: Staleness detection flags unreinforced edges
- [ ] F3: Metrics pipeline logs JSONL
- [ ] F4: Backpressure + circuit breakers prevent overload
- [ ] G3: Louvain/Leiden communities replace balanced-per-file
- [ ] G4: Incremental re-extraction skips unchanged files
- [ ] All existing tests pass
- [ ] ruff clean
- [ ] Docs: BRD, TRD, Test Plan, Decisions committed
- [ ] ROADMAP.md updated

---

*TRD v1.0. Wave 4 — Close the Loop.*
