# Release Notes — v1.14.0 (2026-08-02)

## Agent OS Multi-Tenancy

**Ship status:** Released to PyPI, GHCR, and neuralmind.uk.

This release adds the **Agent OS** — a multi-business orchestration layer
that runs NeuralMind as a product with business-scoped isolation, RBAC,
anomaly detection, and self-improvement loops.

### What ships

| Module | What it does |
|--------|-------------|
| `agent_os/tenant.py` | Business-scoped tenant registry with per-tenant RBAC (admin/operator/viewer). Thread-safe, JSON-backed, atomic writes. Project-to-tenant assignment with hard invariant (one tenant per project). |
| `agent_os/governance.py` | Permission enforcement via decorator. `require_permission(Permission.MANAGE_RBAC)` — fail-closed. Audit logging per-tenant. |
| `agent_os/signals.py` | Page-Hinkley anomaly detection. No fixed thresholds — detects small persistent shifts. Severity levels, cooldown, per-metric state. |
| `agent_os/experiment.py` | A/B experiment runner with promote/rollback governance. `higher_is_better` support for metrics like throughput vs latency. |
| `agent_os/api.py` | Daemon HTTP routes: tenant CRUD, project assignment, RBAC, signal push, experiment run. |

### Governance model

```
admin     → full control (manage RBAC, delete tenant)
operator  → manage projects, view signals, run experiments
viewer    → read-only access
```

Unknown roles default to viewer (fail-closed).

### Signal detection

Page-Hinkley test tracks cumulative deviation from running mean.
When deviation exceeds `lambda × running_std`, a signal fires.
Cooldown prevents repeated alerts.

### Experiment governance

```
delta >= promote_threshold   → PROMOTED
delta <= rollback_threshold  → ROLLED_BACK
otherwise                    → REJECTED
```

Positive delta = improvement (normalized for both lower-is-better and
higher-is-better metrics).

### What the agent sees

```python
from neuralmind.agent_os import TenantRegistry, SignalDetector, ExperimentRunner

# Create tenant
registry = TenantRegistry()
tenant = registry.create_tenant(
    tenant_id="acme",
    name="Acme Corp",
    admin_email="ops@acme.com",
)

# Detect anomalies
detector = SignalDetector()
signal = detector.update("latency_ms", 1200.0)
if signal:
    # Run experiment comparing fix vs current
    runner = ExperimentRunner()
    result = runner.run(
        proposal_id="reduce_latency_v2",
        metric_name="latency_ms",
        baseline_value=signal.value,
        candidate_value=signal.baseline,
    )
```

### 44 tests

All new code paths covered by tests in `tests/test_agent_os.py`:

- Tenant CRUD, persistence, project conflict detection
- Role permission matrix (admin/operator/viewer, unknown role fallback)
- Governance enforcement (grant/deny with audit trail)
- Signal detection (stable data, persistent shift, cooldown, batch)
- Experiments (promote, rollback, reject, zero baseline)
- Integration: anomaly → experiment promotion

### Lint

- ruff: all checks passed
- mypy: type-safe

### Files added

```
neuralmind/agent_os/__init__.py   (61 lines)
neuralmind/agent_os/tenant.py     (367 lines)
neuralmind/agent_os/governance.py (280 lines)
neuralmind/agent_os/signals.py    (276 lines)
neuralmind/agent_os/experiment.py (191 lines)
neuralmind/agent_os/api.py        (414 lines)
tests/test_agent_os.py            (490 lines)
```

### Roadmap

- PostgreSQL + pgvector persistence (from SQLite)
- Multi-instance deployment (2× P40 GPUs + RTX 3060)
- Team memory namespaces at scale
- Statistical significance testing (bootstrap CI, p-values)

---

*NeuralMind v1.14.0 — Adaptive semantic code intelligence for AI coding agents.*
*Persistent memory. 12–50× cheaper code questions. 100% local.*
