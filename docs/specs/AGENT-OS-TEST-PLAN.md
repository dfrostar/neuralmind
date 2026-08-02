# Agent OS — Multi-Tenancy & Self-Improving Operations, Test Plan

**Date:** 2026-08-02
**Module:** `neuralmind/agent_os/`
**Commit:** `c8e3388`
**Claim tier:** B
**Parent specs:** `docs/specs/AGENT-OS-BRD.md` · `docs/specs/AGENT-OS-TRD.md`
**Test file:** `tests/test_agent_os.py` (44 tests)

---

## 1. Test Strategy

| Layer | Count | Scope |
|-------|-------|-------|
| Unit — Tenant | 6 | `Tenant`, `TenantIdValidation` |
| Unit — TenantRegistry | 9 | CRUD, persistence, project conflicts, RBAC |
| Unit — Governance | 5 | Role permissions, check, `AgentOSGovernance` |
| Unit — Signals | 7 | `SignalDetector`, Page-Hinkley, cooldown, reset |
| Unit — Experiment | 6 | Promote/rollback/reject, history, edge cases |
| Integration | 1 | Signal → Experiment pipeline |
| **Total** | **44** | |

---

## 2. Test-to-Code Map

| Test class | File | What it covers |
|------------|------|----------------|
| `TestTenant` | `test_agent_os.py:29-78` | `Tenant.__post_init__`, `is_admin`, `is_operator`, `has_access`, roundtrip |
| `TestTenantIdValidation` | `test_agent_os.py:81-117` | `validate_tenant_id` — valid/invalid IDs |
| `TestTenantRegistry` | `test_agent_os.py:120-199` | `TenantRegistry` — create, get, conflict, persistence |
| `TestRolePermissions` | `test_agent_os.py:202-227` | `role_has_permission` matrix |
| `TestCheckPermission` | `test_agent_os.py:230-242` | `check_permission` with real tenant |
| `TestAgentOSGovernance` | `test_agent_os.py:245-275` | `AgentOSGovernance.enforce`, `list_accessible_tenants` |
| `TestSignalDetector` | `test_agent_os.py:278-325` | `SignalDetector` — stable data, shift, severity, cooldown, reset |
| `TestExperimentRunner` | `test_agent_os.py:400-452` | `ExperimentRunner` — promote, rollback, reject, history |
| `TestSignalExperimentIntegration` | `test_agent_os.py:481-490` | Anomaly → experiment promotion pipeline |

---

## 3. Code-to-Test Traceability

| Source file | Function | Test(s) |
|-------------|----------|---------|
| `tenant.py` | `Tenant.__post_init__` | `TestTenant.test_create_basic`, `test_from_dict_roundtrip` |
| `tenant.py` | `Tenant.is_admin` | `TestTenant.test_is_admin` |
| `tenant.py` | `Tenant.is_operator` | `TestTenant.test_is_operator` |
| `tenant.py` | `Tenant.has_access` | `TestTenant.test_has_access` |
| `tenant.py` | `Tenant.from_dict` | `TestTenant.test_from_dict_with_rbac_dicts` |
| `tenant.py` | `validate_tenant_id` | `TestTenantIdValidation.test_valid_ids`, `test_invalid_ids` |
| `tenant.py` | `TenantRegistry.create_tenant` | `TestTenantRegistry.test_create_and_get`, `test_duplicate_tenant_id_raises` |
| `tenant.py` | `TenantRegistry.add_project` | `TestTenantRegistry.test_project_conflict`, `test_add_role` |
| `tenant.py` | `TenantRegistry.add_role` | `TestTenantRegistry.test_add_role`, `test_add_role_non_admin_raises` |
| `tenant.py` | `TenantRegistry.delete_tenant` | `TestTenantRegistry.test_delete_tenant` |
| `tenant.py` | `TenantRegistry._save` | `TestTenantRegistry.test_persistence` |
| `governance.py` | `_resolve_role_value` | `TestRolePermissions.test_unknown_role_defaults_to_viewer` |
| `governance.py` | `role_has_permission` | `TestRolePermissions.test_admin_has_all_permissions` |
| `governance.py` | `check_permission` | `TestCheckPermission.test_check_permission` |
| `governance.py` | `AgentOSGovernance.enforce` | `TestAgentOSGovernance.test_enforce_grants`, `test_enforce_denies` |
| `governance.py` | `AgentOSGovernance.list_accessible_tenants` | `TestAgentOSGovernance.test_list_accessible_tenants` |
| `signals.py` | `_PageHinkleyState.update` | `TestSignalDetector.test_no_signal_on_stable_data`, `test_signal_on_persistent_shift` |
| `signals.py` | `_PageHinkleyState._severity_level` | `TestSignalDetector.test_severity_levels` |
| `signals.py` | `_PageHinkleyState.cooldown` | `TestSignalDetector.test_cooldown_prevents_spam` |
| `signals.py` | `SignalDetector.update_batch` | `TestSignalDetector.test_update_batch` |
| `signals.py` | `SignalDetector.reset` | `TestSignalDetector.test_reset` |
| `experiment.py` | `ExperimentRunner._compute_delta` | `TestExperimentRunner.test_promote_on_improvement`, `test_rollback_on_regression` |
| `experiment.py` | `ExperimentRunner.run` verdict logic | `TestExperimentRunner.test_reject_when_inconclusive`, `test_zero_baseline_handled` |
| `experiment.py` | `ExperimentRunner.get_history` | `TestExperimentRunner.test_history`, `test_clear_history` |
| `experiment.py` + `signals.py` | Integration | `TestSignalExperimentIntegration.test_anomaly_triggers_experiment` |

---

## 4. Test Execution

```bash
# Full suite
python -m pytest tests/test_agent_os.py -v

# Per-module
python -m pytest tests/test_agent_os.py::TestTenant -v
python -m pytest tests/test_agent_os.py::TestTenantRegistry -v
python -m pytest tests/test_agent_os.py::TestAgentOSGovernance -v
python -m pytest tests/test_agent_os.py::TestSignalDetector -v
python -m pytest tests/test_agent_os.py::TestExperimentRunner -v

# Coverage
python -m pytest tests/test_agent_os.py --cov=neuralmind.agent_os --cov-report=term-missing
```

---

## 5. Pass Criteria

| Gate | Requirement | Current |
|------|-------------|---------|
| Unit tests | 44 pass | ✅ 44/44 |
| Lint | ruff clean | ✅ |
| Import check | No circular deps | ✅ |
| Public API | All exports in `__all__` | ✅ |
| Fail-open | All error paths covered | ✅ |

---

*Generated by Hermes. AGENT-OS-TEST-PLAN — v1.0. Claim tier: B.*
