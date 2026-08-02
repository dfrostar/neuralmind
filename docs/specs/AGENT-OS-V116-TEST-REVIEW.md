# Agent OS v1.16.0 — Comprehensive Testing Review & Scope Expansion

**Date:** 2026-08-02
**Author:** Hermes Agent
**Status:** Draft for review

---

## 1. Current Coverage Audit

### Test Inventory (as of v1.15.0)

| Test File | Tests | Scope | Agent OS Specific |
|-----------|-------|-------|-------------------|
| test_agent_os.py | 47 | Tenant, governance, signals, experiments | ✅ |
| test_agent_os_v2.py | 12 | Correlator, promotion | ✅ |
| test_daemon.py | 21 | Daemon core (health, query, build, jobs) | ❌ General daemon |
| test_dashboard.py | 17 | Dashboard data layer (synapses, ingestion, savings) | ❌ General dashboard |
| **Agent OS Total** | **59** | | |
| **All listed** | **97** | | |

### Source Module Coverage Matrix

| Module | Lines | Unit Tests | Integration Tests | E2E Tests | Coverage Grade |
|--------|-------|------------|-------------------|-----------|----------------|
| tenant.py | 417 | 19 | 0 | 0 | A (unit complete) |
| governance.py | 358 | 10 | 0 | 0 | A (unit complete) |
| signals.py | 243 | 7 | 0 | 0 | B+ (severity edge cases missing) |
| experiment.py | 222 | 9 | 1 | 0 | A (unit complete) |
| correlator.py | 268 | 4 | 0 | 0 | C (no git/config integration) |
| promotion.py | 210 | 8 | 0 | 0 | B (no real ship_callable) |
| **api.py** | **382** | **0** | **0** | **0** | **F — ZERO COVERAGE** |
| **cli.py** | **116** | **0** | **0** | **0** | **F — ZERO COVERAGE** |
| **postgres.py** | **206** | **0** | **0** | **0** | **F — ZERO COVERAGE** |
| __init__.py | 68 | implicit | — | — | — |

### Integration Point Coverage

| Integration Point | Tested? | Gap Severity |
|-------------------|---------|--------------|
| Daemon dispatch → Agent OS routes | ❌ No | **CRITICAL** |
| Token guard on Agent OS endpoints | ❌ No | **CRITICAL** |
| Path parameter extraction (/tenants/{id}) | ❌ No | **CRITICAL** |
| Dashboard `agent_os_tenants` | ❌ No | HIGH |
| Dashboard `agent_os_signals` | ❌ No | HIGH |
| Dashboard `agent_os_experiments` | ❌ No | HIGH |
| Correlator wired into signal fire → insight | ❌ No | HIGH |
| ship_callable real tuner integration | ❌ No | MEDIUM |
| CLI subprocess E2E | ❌ No | MEDIUM |
| RBAC enforcement at CLI level | ❌ No | MEDIUM |
| Audit log persistence | ❌ No | LOW |

### The Core Problem

> "Testing the code is not enough. It's about end-to-end results, end-to-end process top-down side to side."

Current testing is **bottom-up unit-heavy**: we test isolated modules well. But the **user-facing surface** (HTTP API, CLI) has **ZERO coverage**. That means:

- A tenant creator could be broken at the HTTP layer and we wouldn't know.
- RBAC could fail at the API boundary and unit tests wouldn't catch it.
- CLI argument parsing could be broken and no test would fail.
- The correlator could produce insights that never reach the dashboard.

**Coverage is not just line coverage. It's process coverage.**

---

## 2. Coverage Philosophy Shift

### Old Approach (v1.15.0)
- Unit test each module in isolation
- Verify code paths (status codes, return types)
- Assume integration works if units pass

### New Approach (v1.16.0)
- **Top-down**: Start from user-visible behavior
- **Side-to-side**: Cross-module integration at every boundary
- **E2E verification**: Real HTTP, real CLI, real subprocess
- **Invariant-focused**: What must always be true, not just status codes

### What "State of the Art" Means Here

1. **Traceability matrix**: Every requirement → test(s)
2. **Boundary testing**: Every module interface has contract tests
3. **Failure injection**: What happens when git is missing? When DB is down?
4. **Permission matrix**: Every role × every endpoint tested
5. **E2E golden path**: Full signal → insight → experiment → promote/rollback flow
6. **CLI contract**: Every command verifiable via subprocess
7. **Dashboard rendering**: Agent OS tab actually shows data

---

## 3. Test Categories Needed

### A. API Route Tests (test_agent_os_api.py) — 20+ tests

Every HTTP endpoint tested for:
- **Happy path**: Valid request → correct response
- **Auth enforcement**: Missing/invalid token → 401
- **RBAC enforcement**: Wrong role → 403
- **Validation**: Missing required fields → 400
- **Parameterized routes**: `/tenants/{id}` resolves correctly
- **State mutations**: Create actually persists, delete actually removes

### B. CLI E2E Tests (test_agent_os_cli.py) — 15+ tests

Every CLI command run as subprocess:
- `tenants create` → tenant file created on disk
- `tenants list` → JSON output parseable
- `tenants delete` → tenant file removed
- `rbac add` → role assignment persisted
- `signals push` → signal detected
- `experiments run` → verdict in output
- `experiments history` → JSON array

### C. Daemon Integration Tests (test_agent_os_daemon.py) — 10+ tests

Actual HTTP round-trip through daemon:
- Start real daemon with Agent OS routes
- Hit `/api/agent-os/tenants` with token
- Verify 401 without token
- Verify parameterized route `/api/agent-os/tenants/{id}`
- Verify signal push → experiment flow over HTTP

### D. Dashboard Integration (test_agent_os_dashboard.py) — 5+ tests

- `agent_os_tenants()` returns real tenant data
- `agent_os_signals()` returns signal stats
- `agent_os_experiments()` returns history
- Dashboard HTML renders Agent OS tab

### E. Correlator Integration (test_agent_os_correlator_integration.py) — 5+ tests

- Wire correlator into signal detection
- Signal fires → insight generated
- Insight stored/persisted
- Multiple hypotheses ranked by confidence

### F. Ship Callable Production Wiring — 3+ tests

- Real tuner update function called on PROMOTED
- Rollback tag tracking works
- ship_callable exception → FAILED status (not crash)

### G. Postgres Schema — 3+ tests

- Schema generation (mock psycopg2)
- Migration status check
- Graceful failure without psycopg2

---

## 4. Updated v1.16.0 Scope

### Original Items (preserved)

| # | Item | Priority | Status |
|---|------|----------|--------|
| 1 | E2E CLI verification | HIGH | Now expanded to full CLI test suite |
| 2 | Daemon integration test | HIGH | Now expanded to full HTTP round-trip |
| 3 | Root-cause correlator integration | MEDIUM | Unchanged |
| 4 | Auto-promote/rollback production wiring | MEDIUM | Unchanged |
| 5 | scipy.stats.t.sf p-value | LOW | Unchanged |
| 6 | Tenant federation doc | LOW | Unchanged |

### New Items Added

| # | Item | Priority | Deliverable |
|---|------|----------|-------------|
| 7 | **API route test suite** | **CRITICAL** | test_agent_os_api.py — 20+ tests covering all 10 endpoints |
| 8 | **CLI E2E subprocess tests** | **HIGH** | test_agent_os_cli.py — 15+ tests |
| 9 | **Daemon Agent OS HTTP round-trip** | **HIGH** | test_agent_os_daemon.py — 10+ tests |
| 10 | **Dashboard Agent OS sections** | **MEDIUM** | test_agent_os_dashboard.py — 5+ tests |
| 11 | **Correlator-signal pipeline integration** | **MEDIUM** | test_agent_os_correlator_integration.py — 5+ tests |
| 12 | **Postgres schema + migration tests** | **MEDIUM** | test_agent_os_postgres.py — 3+ tests |
| 13 | **RBAC permission matrix E2E** | **HIGH** | All roles × all endpoints tested |
| 14 | **Audit log persistence** | **LOW** | Verify JSONL entries written |

### Test Count Projection

| Category | Existing | New | Total |
|----------|----------|-----|-------|
| Unit (existing) | 59 | 0 | 59 |
| API routes | 0 | 22 | 22 |
| CLI E2E | 0 | 15 | 15 |
| Daemon integration | 0 | 12 | 12 |
| Dashboard integration | 0 | 6 | 6 |
| Correlator integration | 0 | 5 | 5 |
| Postgres | 0 | 3 | 3 |
| **Total** | **59** | **63** | **122** |

Target: **122 tests** (exceeds 100+ requirement).

---

## 5. Success Criteria — Updated

### Original
- [ ] All CLI commands work end-to-end (manual verification)
- [ ] Daemon Agent OS routes reachable via HTTP with token guard
- [ ] Correlator generates insights on signal fire
- [ ] Auto-promote/rollback wired with real ship_callable
- [ ] p-value uses scipy when available
- [ ] 100+ tests (80 existing + 20 new)
- [ ] ruff clean, mypy clean

### New
- [ ] **All 10 API endpoints have happy-path + auth + RBAC + validation tests**
- [ ] **CLI commands verifiable via subprocess (not just --help)**
- [ ] **Daemon HTTP round-trip works for Agent OS routes (with + without token)**
- [ ] **Parameterized routes resolve correctly (/tenants/{id})**
- [ ] **RBAC permission matrix tested: admin/operator/viewer × every endpoint**
- [ ] **Correlator wired into signal detection pipeline (signal → insight → storage)**
- [ ] **ship_callable production wiring with real tuner + rollback tag tracking**
- [ ] **Dashboard Agent OS sections render real data**
- [ ] **Postgres schema + migration tested**
- [ ] **Audit log entries written for permission grants/denials**
- [ ] **scipy.stats.t.sf p-value with graceful fallback**
- [ ] **Tenant federation limitation documented**
- [ ] **122 tests (59 existing + 63 new)**
- [ ] **ruff clean, mypy clean**

---

## 6. Execution Order

### Phase 1: Critical Gaps (HIGH)
1. **API route test suite** (22 tests) — most user-facing surface, currently zero coverage
2. **Daemon Agent OS HTTP round-trip** (12 tests) — proves integration works
3. **CLI E2E subprocess** (15 tests) — proves operator UX works

### Phase 2: Integration (MEDIUM)
4. **Correlator-signal pipeline** (5 tests) — proves self-improving loop works
5. **Dashboard Agent OS sections** (6 tests) — proves visibility works
6. **Postgres schema + migration** (3 tests) — proves persistence layer

### Phase 3: Production Wiring (MEDIUM)
7. **ship_callable real tuner + rollback tags**
8. **scipy p-value + confidence interval**
9. **Audit log persistence tests**

### Phase 4: Documentation (LOW)
10. **Tenant federation limitation doc**
11. **Traceability matrix (tests ↔ requirements)**

---

## 7. Key Risks

| Risk | Mitigation |
|------|------------|
| Agent OS route handlers share mutable global state | Test isolation via tmp_path + clear state between tests |
| CLI subprocess tests slow | Use pytest-xdist, keep to <5s total |
| Token guard integration requires real daemon | Use existing test_daemon.py pattern (running_daemon fixture) |
| Dashboard tests need mock NeuralMind | Use SimpleNamespace pattern from test_dashboard.py |
| Postgres tests need psycopg2 | Mock at import boundary; test graceful degradation |

---

## 8. The Bottom Line

v1.15.0 shipped with **solid unit foundations** but **zero coverage on user-facing surfaces**. v1.16.0 must shift from "we tested the code" to "we verified the process end-to-end."

The 63 new tests aren't vanity metrics — they cover the actual paths users (and operators) exercise:
- Creating a tenant through the CLI → verified on disk
- Hitting an API endpoint without a token → 401
- A viewer trying to create a tenant → 403
- A signal firing → insight generated → experiment run → verdict surfaced in dashboard

That's the difference between "code that works in isolation" and "a product that works in production."
