# Agent OS — Multi-Tenancy & Self-Improving Operations, Technical Requirements Document (TRD)

**Date:** 2026-08-02
**Module:** `neuralmind/agent_os/`
**Commit:** `c8e3388`
**Claim tier:** B
**Parent spec:** `docs/specs/AGENT-OS-BRD.md`

---

## 1. Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         AGENT OS ARCHITECTURE                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────────┐     ┌──────────────────────┐     ┌─────────────┐  │
│  │ TenantRegistry  │────▶│  AgentOSGovernance   │────▶│  Daemon API │  │
│  │                 │     │                      │     │             │  │
│  │ JSON-per-tenant │     │ @require_permission  │     │ HTTP routes │  │
│  │ atomic writes   │     │ role→permission map  │     │ token-guard │  │
│  │ project index   │     │ audit JSONL          │     │ JSON resp   │  │
│  └─────────────────┘     └──────────────────────┘     └─────────────┘  │
│           │                        │                                    │
│           ▼                        ▼                                    │
│  ┌─────────────────┐     ┌──────────────────────┐                      │
│  │ SignalDetector  │     │ ExperimentRunner     │                      │
│  │                 │     │                      │                      │
│  │ Page-Hinkley    │     │ promote/rollback     │                      │
│  │ severity levels │     │ threshold governance │                      │
│  │ cooldown        │     │ history              │                      │
│  └─────────────────┘     └──────────────────────┘                      │
│           │                        │                                    │
│           └──────────┬─────────────┘                                    │
│                      ▼                                                  │
│            ┌────────────────────┐                                       │
│            │ Integration:       │                                       │
│            │ signal → experiment│                                       │
│            └────────────────────┘                                       │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### Data Flow

```
1. Tenant CRUD
   Client → POST /tenants → create_tenant() → validate_id → check conflicts
          → save JSON → update cache + index → return Tenant

2. Project Assignment
   Client → POST /tenants/{id}/projects → add_project() → admin check
          → resolve path → conflict check → append + save → return

3. Signal Detection
   Metric push → update() → Page-Hinkley state update → cumulative dev check
             → if exceeds λ×std → emit Signal → reset trackers

4. Experiment
   Client → POST /experiments → compute delta → verdict: PROMOTED/ROLLED_BACK/REJECTED
          → append history → return ExperimentResult
```

---

## 2. Data Model

### Tenant (`tenant.py`)

```python
@dataclass
class Tenant:
    tenant_id: str           # URL-safe slug: ^[a-z][a-z0-9-]{0,63}$
    name: str
    tier: str                # "free" | "team" | "enterprise"
    projects: list[str]      # absolute paths
    rbac: list[RoleAssignment]
    governance: dict         # per-tenant overrides
    created_at: str          # ISO UTC
    updated_at: str          # ISO UTC

@dataclass
class RoleAssignment:
    email: str               # normalized lowercase
    role: str                # "admin" | "operator" | "viewer"
```

### Persistence

```
~/.config/neuralmind/tenants/
├── level2logic.json
├── cybersentinel.json
└── neuralmind.json

~/.config/neuralmind/
└── agent-os-audit.jsonl
```

---

## 3. RBAC Model

### Roles & Permissions (`governance.py`)

| Permission | Admin | Operator | Viewer |
|-----------|-------|----------|--------|
| MANAGE_PROJECTS | ✅ | ✅ | ❌ |
| VIEW_PROJECTS | ✅ | ✅ | ✅ |
| MANAGE_RBAC | ✅ | ❌ | ❌ |
| VIEW_RBAC | ✅ | ✅ | ✅ |
| VIEW_SIGNALS | ✅ | ✅ | ✅ |
| MANAGE_SIGNALS | ✅ | ✅ | ❌ |
| RUN_EXPERIMENTS | ✅ | ✅ | ❌ |
| VIEW_EXPERIMENTS | ✅ | ✅ | ✅ |
| DELETE_TENANT | ✅ | ❌ | ❌ |
| MANAGE_GOVERNANCE | ✅ | ❌ | ❌ |

### Enforcement Pattern

```python
@require_permission(Permission.MANAGE_RBAC)
def assign_role(self, tenant_id, admin_email, target_email, role):
    # Decorator checks permission before method body executes
    ...
```

Fail-closed: unknown role → viewer → no permissions.

---

## 4. Algorithms

### 4.1 Page-Hinkley Test (`signals.py`)

For a metric stream `x₁, x₂, ..., xₙ`:

```
mean_n = (Σ x_i) / n
var_n  = (Σ x_i²) / n - mean_n²
std_n  = sqrt(max(var_n, 0))

deviation_i = x_i - mean_n
max_cum_dev = max(max_cum_dev + deviation_i, 0)
min_cum_dev = min(min_cum_dev + deviation_i, 0)

cumulative_deviation = max_cum_dev - min_cum_dev
severity = cumulative_deviation / std_n   (if std > 1e-9)

FIRE if: severity ≥ λ (default 4.0) AND cooldown expired
```

### 4.2 A/B Delta (`experiment.py`)

```
raw_delta = (candidate - baseline) / |baseline|
delta     = raw_delta if higher_is_better else -raw_delta   # invert so positive = improvement

verdict:
  delta ≥ promote_threshold   → PROMOTED
  delta ≤ rollback_threshold  → ROLLED_BACK
  otherwise                   → REJECTED
```

---

## 5. API Surface

### 5.1 `tenant.py`

```python
class TenantRegistry:
    def create_tenant(tenant_id, name, tier, admin_email, projects) -> Tenant
    def get_tenant(tenant_id) -> Tenant | None
    def get_tenant_by_project(project_path) -> Tenant | None
    def list_tenants() -> list[Tenant]
    def add_project(tenant_id, project_path, admin_email) -> Tenant
    def remove_project(tenant_id, project_path, admin_email) -> Tenant
    def add_role(tenant_id, email, role, admin_email) -> Tenant
    def remove_role(tenant_id, email, admin_email) -> Tenant
    def delete_tenant(tenant_id, admin_email) -> None
```

### 5.2 `governance.py`

```python
class AgentOSGovernance:
    def enforce(tenant_id, email, permission) -> GovernanceResult
    @require_permission(MANAGE_PROJECTS)
    def create_tenant(tenant_id, email, name, tier, projects) -> Tenant
    @require_permission(MANAGE_RBAC)
    def assign_role(tenant_id, admin_email, target_email, role) -> Tenant
    @require_permission(MANAGE_PROJECTS)
    def add_project(tenant_id, email, project_path) -> Tenant
    @require_permission(DELETE_TENANT)
    def delete_tenant(tenant_id, admin_email) -> None
    def list_accessible_tenants(email) -> list[Tenant]
    def can_access_project(email, project_path) -> bool
```

### 5.3 `signals.py`

```python
class SignalDetector:
    def update(metric_name, value) -> Signal | None
    def update_batch(metrics: dict) -> list[Signal]
    def get_stats(metric_name) -> dict | None
    def list_metrics() -> list[str]
    def reset(metric_name | None) -> None
```

### 5.4 `experiment.py`

```python
class ExperimentRunner:
    def run(proposal_id, metric_name, baseline_value, candidate_value,
            threshold_pct=None, higher_is_better=False, details=None) -> ExperimentResult
    def get_history() -> list[ExperimentResult]
    def clear_history() -> None
```

---

## 6. Daemon Integration (`daemon.py`)

Routes registered via `create_agent_os_routes()`:

| Method | Path | Handler | Auth |
|--------|------|---------|------|
| POST | `/api/agent-os/tenants` | create_tenant | token |
| GET | `/api/agent-os/tenants` | list_tenants | token |
| GET | `/api/agent-os/tenants/{id}` | get_tenant | token |
| POST | `/api/agent-os/tenants/{id}/projects` | add_project | token |
| DELETE | `/api/agent-os/tenants/{id}` | delete_tenant | token |
| POST | `/api/agent-os/tenants/{id}/rbac` | assign_role | token |
| GET | `/api/agent-os/signals` | get_signals | token |
| POST | `/api/agent-os/signals` | update_signal | token |
| POST | `/api/agent-os/experiments` | run_experiment | token |
| GET | `/api/agent-os/experiments` | list_experiments | token |

---

## 7. Error Handling

| Condition | Behavior |
|-----------|----------|
| Invalid tenant_id | `InvalidTenantIdError` (subclass of `TenantError`) |
| Duplicate tenant_id | `TenantConflictError` |
| Project already assigned | `TenantConflictError` |
| Tenant not found | `TenantNotFoundError` |
| Permission denied | `PermissionError` → HTTP 403 |
| Missing required field | HTTP 400 |
| Internal error | HTTP 500, log exception |
| Audit log write fail | Swallowed (fail-open) |

---

## 8. Performance Budget

| Metric | Target | Max |
|--------|--------|-----|
| Tenant CRUD | < 50ms | < 100ms |
| Project assignment | < 100ms | < 200ms |
| Signal update | < 1ms | < 5ms |
| Experiment run | < 1ms | < 5ms |
| HTTP round-trip | < 500ms | < 1s |
| Memory per tenant | < 1MB | < 5MB |

---

## 9. File Manifest

```
neuralmind/agent_os/
├── __init__.py          # Public API exports
├── tenant.py            # Tenant, TenantRegistry, RoleAssignment
├── governance.py        # AgentOSGovernance, RBAC, audit
├── signals.py           # SignalDetector, Page-Hinkley
├── experiment.py        # ExperimentRunner, delta governance
└── api.py               # Daemon route handlers

tests/
└── test_agent_os.py     # 44 tests

docs/specs/
├── AGENT-OS-BRD.md      # Business requirements
├── AGENT-OS-TRD.md      # THIS FILE
├── AGENT-OS-TEST-PLAN.md
└── AGENT-OS-QA-PLAN.md
```

---

## 10. Future Work

| Item | Priority | Blocker |
|------|----------|---------|
| PostgreSQL persistence | High | Schema migration |
| Statistical significance testing | High | Sample populations |
| Auto-promote/rollback wiring | Medium | Signal quality baseline |
| Web UI for Agent OS | Low | Frontend framework |
| Multi-instance federation | Low | Consensus protocol |

---

*Generated by Hermes. AGENT-OS-TRD — v1.0. Claim tier: B.*
