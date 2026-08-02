# Agent OS — QA Report

**Date:** 2026-08-02
**Commit:** `c8e3388` (code) + `0871eb3` (QA patches)
**Models:** GLM-5.2 (catch-missed-issues), DeepSeek v4 Per (per-module)
**Final:** 45/45 tests pass, ruff clean

---

## Findings Summary

| # | Severity | Module | Finding | Status |
|---|----------|--------|---------|--------|
| 1 | 🔴 CRITICAL | governance.py | `create_tenant` always 403 — bootstrap impossible | ✅ Patched |
| 2 | 🔴 CRITICAL | api.py | RBAC bypass on signals/experiments routes | ✅ Patched |
| 3 | 🔴 CRITICAL | experiment.py | Zero-baseline delta ignores `higher_is_better` | ✅ Patched |
| 4 | ⚠️ WARNING | signals.py | Dead `alpha` param (doc'd as EWMA, never used) | ✅ Patched |
| 5 | 🔴 CRITICAL | tenant.py | Path traversal in `delete_tenant` via `../` tenant_id | ✅ Patched |
| 6 | ⚠️ WARNING | tenant.py | Cache/disk inconsistency on `_save` failure | ✅ Patched |
| 7 | ⚠️ WARNING | tenant.py | Email normalization not enforced at `from_dict` | ✅ Patched |

---

## Finding Details

### 1. `create_tenant` always returns 403

**Module:** `governance.py:272`
**Found by:** GLM

```python
@require_permission(Permission.MANAGE_PROJECTS)
def create_tenant(self, tenant_id, email, name, tier="free", projects=None):
    return self._tenant_registry.create_tenant(...)

The decorator looks up tenant_id in the registry BEFORE the tenant exists →
always raises InsufficientPermissionError("Tenant not found: …") → API maps to 403.

Fix: Removed @require_permission. Bootstrap has no prior tenant context.
Validation of tenant_id and project ownership is performed by the registry.

### 2. RBAC bypass on signals/experiments API routes

**Module:** `api.py:204-278`
**Found by:** GLM

get_signals, update_signal, run_experiment, list_experiments performed ZERO
permission/tenant checks. A viewer (whom governance.enforce correctly denies)
could call the API route and PROMOTE an experiment. Signals routes accepted
no email/tenant at all.

Fix: Added _require_permission(governance, tenant_id, email, permission)
helper wired into all four routes. viewer → 403, operator → 200.

### 3. Zero-baseline delta ignores `higher_is_better`

**Module:** `experiment.py:109-113`
**Found by:** GLM

if abs(baseline) < 1e-9:
    return 0.0 if abs(candidate) < 1e-9 else 1.0  # always "improvement"!

Verified: baseline=0, candidate=10, lower-is-better (latency) → delta=+1.0 →
PROMOTED (a 10× regression shipped as "100% improvement").

Fix: Applied inversion in zero-baseline branch:
    return 1.0 if higher_is_better else -1.0

### 4. Dead `alpha` parameter in Page-Hinkley

**Module:** `signals.py:86`
**Found by:** GLM

SignalDetector(alpha=0.05) / _PageHinkleyState.alpha threaded through 4
places but NEVER read. Comment said "Exponentially-weighted deviation"
but mean is plain arithmetic running mean.

Fix: Removed dead `alpha` param and false EWMA comment. PH detection
still works (50×100.0→200.0 fires at lambda_threshold=1.0).

### 5. Path traversal in `delete_tenant`

**Module:** `tenant.py:374`
**Found by:** DeepSeek

delete_tenant accepted arbitrary tenant_id strings:
    tenant_id = "../victim"
    path = tenants_dir / f"{tenant_id}.json"  →  tenants_dir/../victim.json
    path.unlink()  → arbitrary file deleted.

Verified: a real victim.json above tenants_dir was deleted.

Fix: validate_tenant_id(tenant_id) in delete_tenant. Defense in depth:
_load_all already rejects non-slug ids via _TENANT_ID_RE, so a crafted
file in tenants_dir can't inject a non-slug id.

### 6. Cache/disk inconsistency on save failure

**Module:** `tenant.py:318-322, 341-345, 359-363, 276-280`
**Found by:** DeepSeek

If _save raises OSError, the in-memory _cache/_project_index still holds
the mutation — caller thinks the change succeeded, but disk is unchanged.
Next _load_all returns stale state, but the running process has diverged.

Fix: try/except around _save in all 4 mutation methods, calling
_load_all() to roll back the in-memory state before re-raising.

### 7. Email normalization not enforced at from_dict

**Module:** `tenant.py:76-77`
**Found by:** DeepSeek

RoleAssignment.from_dict stored email as-is from JSON. Comparisons
lowercased, but storage didn't — mixed-case emails persisted, creating
an inconsistency where two JSON loads of the same tenant could yield
different rbac lists.

Fix: data["email"].strip().lower() in from_dict.

---

## Verification

```bash
$ python -m pytest tests/test_agent_os.py -q
.............................................  [100%]
45 passed in 5.2s

$ python -m ruff check neuralmind/agent_os/ tests/test_agent_os.py
All checks passed!

$ python -m pytest tests/test_daemon.py -q
.....................  [100%]
21 passed
```

---

## Files Modified

| File | Changes |
|------|---------|
| `governance.py` | Removed `@require_permission` from `create_tenant` |
| `api.py` | Added `_require_permission` helper, wired to 4 routes |
| `experiment.py` | Fixed zero-baseline delta inversion |
| `signals.py` | Removed dead `alpha` param |
| `tenant.py` | Path traversal guard, save-failure rollback, email normalization |
| `tests/test_agent_os.py` | Added test for higher_is_better zero-baseline |

---

*Generated by Hermes. AGENT-OS-QA-REPORT — v1.0.*
