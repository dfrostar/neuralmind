# Wave 6 — Technical Requirements Document (TRD)

**Date:** 2026-07-19
**Source:** `f31037a feat(v0.50.0): metrics CLI, /api/metrics endpoint, team memory integration test`
**BRD:** `docs/WAVE6-BRD.md`

---

## 1. Scope

Metrics observability for the self-improving loop: CLI summary, HTTP endpoint, team memory E2E integration test.

---

## 2. Architecture

### 2.1 Metrics Pipeline

```
neuralmind/metrics_pipeline.py
    MetricsCollector.summarize(days=7) → dict
        ↓
neuralmind/cli.py:2660  metrics_p subparser
   --days N (default 7)
   --json   (machine-readable to stdout)
        ↓
neuralmind/server.py  GET /api/metrics
   Returns MetricsCollector.summarize() as JSON
```

### 2.2 Fields

| Field | Source | Type |
|-------|--------|------|
| latency_p95 | query log | float (ms) |
| tokens_per_query | query log | float |
| retrieval_reuse_rate | query log | float (0-1) |
| success_rate | query log | float (0-1) |
| synapses_activated | synapses.db | int |

---

## 3. Component Requirements

### 3.1 CLI (`neuralmind/cli.py:2660`)

```python
metrics_p = subparsers.add_parser("metrics", help="Show project health metrics")
metrics_p.add_argument("project_path", nargs="?", default=".")
metrics_p.add_argument("--days", type=int, default=7, help="Window in days")
metrics_p.add_argument("--json", "-j", action="store_true", help="Machine-readable output")
```

Handler:
1. Load `NeuralMind(project_path)`
2. Call `MetricsCollector(nm).summarize(days=days)`
3. If `--json`: `print(json.dumps(summary))`
4. Else: ASCII table via `tabulate` or manual formatting

### 3.2 HTTP Endpoint (`neuralmind/server.py`)

```python
@app.get("/api/metrics")
async def api_metrics(project_path: str = ".", days: int = 7):
    nm = NeuralMind(project_path, backend_type="turbovec", enable_synapses=False)
    summary = MetricsCollector(nm).summarize(days=days)
    return summary
```

### 3.3 Integration Test (`tests/test_team_memory_integration.py`)

```python
class TestTeamMemoryIntegration:
    def test_full_contributor_lifecycle(self, tmp_path):
        # 1. Contributor A publishes
        store_a = SynapseStore(tmp_path / "a.db")
        store_a.publish_team_bundle(bundle_a)
        
        # 2. Contributor B imports
        store_b = SynapseStore(tmp_path / "b.db")
        result = store_b.import_team_bundle(bundle_a)
        
        # 3. Peer review gate
        assert result["status"] == "promoted"  # or "review"
        
        # 4. Quality-weighted merge
        merged = store_b.get_merged_edges()
        assert len(merged) > 0
        
        # 5. Staleness accelerates decay
        staleness = TeamStaleness(store_b)
        staleness.run_staleness_pass()
        # Verify decay rate increased for stale edges
```

---

## 4. Test Plan

| Test | File | What it verifies |
|------|------|-----------------|
| `test_metrics_cli_prints_table` | test_cli.py | ASCII output, <500ms |
| `test_metrics_json_output` | test_cli.py | Valid JSON, correct fields |
| `test_api_metrics_endpoint` | test_server.py | HTTP 200, JSON matches CLI |
| `test_team_memory_full_lifecycle` | test_team_memory_integration.py | E1→E2→E3→E4 chain |
| `test_peer_review_auto_promote` | test_team_memory_integration.py | High-quality auto-promotes |
| `test_peer_review_flags_low_quality` | test_team_memory_integration.py | Low-quality flags for review |
| `test_merge_quality_weighted` | test_team_memory_integration.py | Quality wins over recency |
| `test_staleness_accelerates_decay` | test_team_memory_integration.py | Fast-decay after threshold |
| `test_empty_bundle_noop` | test_team_memory_integration.py | No crash on empty |
| `test_malformed_bundle_rejected` | test_team_memory_integration.py | Graceful rejection |

---

## 5. Acceptance

- [ ] `neuralmind metrics --summary` prints table in <500ms
- [ ] `neuralmind metrics --json` returns valid JSON
- [ ] `GET /api/metrics` returns 200 + JSON
- [ ] 10 integration tests pass
- [ ] All existing tests still pass (1374+)

---

*TRD v1.0. Wave 6 shipped 2026-07-19 as v0.50.0.*
