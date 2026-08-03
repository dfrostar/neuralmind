# NeuralMind v2.0.2 — Adversarial Re-Review — Consolidated Findings

**Date:** 2026-08-02
**Repo:** `/home/dtfrost5/neuralmind` (HEAD `5572679`, main)
**Review method:** 3 independent subagents (store/ auth/ loop) + main-thread cross-verification

---

## Summary

| Category | Count |
|----------|-------|
| **Total findings** | **28** |
| From original 27 — FIXED | 10 |
| From original 27 — PARTIALLY FIXED | 4 |
| From original 27 — NOT FIXED | 13 |
| **New findings** | **11** |

**QA GATE: FAIL**

v2.0.2 is **not** ready for production. The SQLite migration is architecturally sound, but 4 CRITICAL new findings and 13 unresolved original findings (including all 5 original CRITICAL auth/RBAC issues) remain exploitable. The self-improving loop is **wired in shape but dead in function** — it never fires through any reachable surface.

---

## Original 27 — Verification Matrix

| ID | Original | Severity | Status | Evidence |
|----|----------|----------|--------|----------|
| **F1/S31** | Auth boundary — email from request body | CRITICAL | **NOT FIXED** | api.py:92-96 — body-email fallback still active; session-token code path (auth.py) is dead code; no caller passes headers to handlers |
| **F2/S32** | RBAC + tenant isolation | CRITICAL | **NOT FIXED** | signals.py:287, experiment.py:183 — all writes use hardcoded `tenant_id="default"`; no per-tenant data separation |
| **D17** | State persistence on restart | CRITICAL | **PARTIAL** | store.py:285 persists Page-Hinkley; daemon path restores via `_load_state` (signals.py:238); **CLI path** builds storeless detector (cli.py) → no state persist |
| **C5** | Audit fail-closed | CRITICAL | **FIXED** | store.py:690-693 — audit() raises on error; `_tx()` re-raises after rollback |
| **C1-C4** | Auth bypass (bootstrap + body trust) | CRITICAL | **NOT FIXED** | api.py:99-118 bootstrap trusted; api.py:92-96 body-identity trusted; session-token path dead code |
| **F3/P14** | PostgreSQL overclaim | HIGH | **NOT FIXED** | postgres.py still exists (neuralmind/agent_os/postgres.py:141); docs/UPGRADING.md:154 still advertises pgvector |
| **O5** | Token model multi-tenant | HIGH | **NOT FIXED** | auth.py token model built but never wired; api.py:86-91 dead code path |
| **O9** | Self-improving loop not instantiated | HIGH | **NOT FIXED** | AutoTriggerLoop created at daemon.py:552 but no store/incumbent passed; project_path never passed (api.py:267); deadlocks on 2nd signal |
| **M10** | Promotion/rollback not wired | HIGH | **NOT FIXED** | ship_callable defaults to `_noop_ship` (promotion.py:222-227); `_auto_run_experiment` passes incumbent but not proposal (auto_trigger.py:123); rewiring never happens |
| **E28** | Embedding guard | HIGH | **PARTIAL** | No explicit model-identity check; hardcoded `all-MiniLM-L6-v2` (onnx_embedder.py:39) reduces risk; no guard if env `NEURALMIND_ONNX_MODEL_DIR` points to different model |
| **C21** | Thread safety | MEDIUM | **NOT FIXED** | increment_signal_count deadlocks (store.py:501-517 — non-reentrant Lock re-acquisition); two store instances to same file in daemon (store + get_store singleton) |
| **C22** | Experiment history per-tenant | MEDIUM | **PARTIAL** | SQL filters by tenant_id (store.py:559) but `ExperimentRunner._history_from_store` hardcodes `metric_name="all"` (experiment.py:108) → always empty |
| **D19** | Audit integrity | MEDIUM | **FIXED** | Single-statement atomic INSERT via `_tx()` (store.py:676-689); crash → rollback |
| **D20** | Cascade cleanup | MEDIUM | **FIXED** | delete_tenant removes across all 9 tables (store.py:705-719); verified |
| **O6/O7** | Unbounded growth | MEDIUM | **NOT FIXED** | No VACUUM, no wal_checkpoint, no retention; signals/insights/audit_log grow forever |
| **Q25** | list_proposals O(n) | LOW | **FIXED** | Indexed via `idx_proposals_metric`/`idx_proposals_tenant` (verified EXPLAIN) |
| **M13** | Stray agent_os/ at repo root | LOW | **FIXED** | No `agent_os/` directory at repo root |

---

## New Findings

### CRITICAL (4)

**[N-01] Hard deadlock in increment_signal_count**
- Location: store.py:501-517
- `with self._tx()` acquires non-reentrant Lock → calls `self.get_proposal()` → re-acquires same Lock → **self-deadlock**
- Trigger: auto_trigger.py:93 fires on 2nd signal for an open proposal → daemon hangs permanently
- Reproducer: `repro_deadlock.py` — confirmed hang (timeout exit 124)
- **Why CI missed it:** No test exercises `increment_signal_count`; tests use `update_proposal` instead

**[N-02] Schema migration crash on _SCHEMA_VERSION bump**
- Location: store.py:226-238
- `_init_db` runs `executescript(_SCHEMA)` but schema_version only set on empty DB
- If code bumps version, old DB stays at old version → new column missing → `OperationalError: no such column` on startup → daemon refuses to start
- Reproducer: `repro_migration2.py` — confirmed crash
- **No migration path exists**; CREATE TABLE IF NOT EXISTS silently no-ops on existing tables

**[N-03] Self-improving loop never starts via HTTP (project_path dropped)**
- Location: api.py:267, signals.py:291/304
- `update_signal` calls `signal_detector.push(metric_name, sample)` with NO `project_path`
- signals.py:291 gates correlator on `project_path is not None` → insight always None → auto-trigger never fires
- Daemon HTTP is the ONLY surface with AutoTriggerLoop; CLI path builds storeless detector
- **Proved:** 30 anomaly values pushed → 0 insights, 0 proposals, 0 experiments

**[N-04] Auth bypass — body-email grants admin without session**
- Location: api.py:92-96, governance.py:250
- `add_project` with body `{"email": "<any admin email>"}` returns 200 — full admin from self-declared identity
- No session token, no Authorization header — complete trust of body-identity
- Bootstrap `create_tenant` has no auth — attacker creates any tenant as admin

### HIGH (4)

**[N-05] AutoTriggerLoop wired without store/incumbent → promotion NO-OP**
- Location: daemon.py:552, auto_trigger.py:48-50
- `AutoTriggerLoop(signal_detector)` omits `store=store` and `incumbent`
- `_auto_run_experiment` uses `self._store` with no fallback → engine built with store=None → no rows persisted

**[N-06] ship_callable defaults to _noop_ship; incumbent never updates**
- Location: promotion.py:222-227, auto_trigger.py:123-151
- Engine created with `proposal=None` → `_ship_callable = _noop_ship` and `_auto_promote = False`
- Later patch (auto_trigger.py:149-151) updates proposal/signal_count but never rewires ship_callable
- Result: PROMOTED verdict logs "Human review required" and returns — no value change

**[N-07] Corrupt DB bricks daemon; no recovery path**
- Location: store.py:226-238
- `_init_db` → `executescript(_SCHEMA)` raises `DatabaseError: file is not a database` on corrupt file
- No backup-and-recreate, no error boundary, no fallback

**[N-08] TOCTOU: duplicate proposals under concurrency**
- Location: auto_trigger.py:63-83
- `list_proposals` then `create_proposal` — no lock across check-and-create
- Two concurrent signals → two proposals for same metric → splits signal budget → MIN_SIGNALS=5 unreachable

### MEDIUM (4)

**[N-09] Default `higher_is_better=False` negates delta → improvements always rolled back**
- Location: experiment.py:129-135, auto_trigger.py:158
- Candidate=200 vs baseline=100 → verdict `rolled_back`, delta=-1.0
- Even correctly-wired promotion would roll back every genuine improvement

**[N-10] Audit is separate transaction; loop never audited**
- Location: store.py:666-693, governance.py
- Audit committed independently from action → crash between loses audit row
- **Self-improving loop (signal/proposal/experiment/promotion/rollback) performs ZERO audit writes** — no governance trail

**[N-11] update_proposal silently drops unknown columns (last_experiment_id, last_verdict)**
- Location: auto_trigger.py:162-167, store.py:463-499
- auto_trigger passes keys that don't exist in proposals table → merged into `current` but never written to SQL
- Experiment→proposal linkage is silently LOST — no error, no log

### LOW (3)

**[N-12] Connection leak — no __del__ / atexit handler**
- Location: store.py:723, :755
- Only `close()` and `reset_store()` close the connection
- Components holding store leak connection + WAL writer for process lifetime

**[N-13] Global lock serializes all reads + writes**
- Location: store.py:200
- Single `threading.Lock` for all operations → head-of-line blocking on slow writes
- WAL + single connection already serializes in SQLite; Python lock adds redundant contention

**[N-14] Env-var path injection for db_path**
- Location: store.py:189-198
- `NEURALMIND_AGENTOS_DIR` / `NEURALMIND_DAEMON_HOME` can point at arbitrary writable paths
- Standard config-injection surface (daemon-owned env, same trust domain)

---

## End-to-End Failure: Self-Improving Loop

Wanted: signal → insight → proposal → experiment → promotion → ship

```
push(metric, value)          ← api.py:267: NO project_path
  ↓
Page-Hinkley detect          ← signals.py:280: works ✓
  ↓
correlate(insight)           ← signals.py:291: project_path=None → SKIP ✗ DEAD HERE
  ↓
_on_signal_insight()         ← auto_trigger.py:58: never invoked
  ↓
increment_signal_count()     ← store.py:517: DEADLOCK (2nd signal) ✗
  ↓
_auto_run_experiment()       ← auto_trigger.py:109: store=None (not passed) ✗
  ↓
engine.run()                 ← promotion.py:222: proposal=None → noop ✗
  ↓
ship_callable()              ← defaults to _noop_ship → log + return ✗
```

**The loop cannot ship a single value through any reachable surface.**

---

## Repository State After Review

```
M neuralmind/agent_os/store.py         ← deadlock fix (from Task A)
 M tests/test_agent_os_v2.py           ← deadlock regression test (pre-existing)
?? ADVERSARIAL_STORE_FINDINGS.md       ← Task A deliverable
?? SELFIMPROVE_ADVERSARIAL_FINDINGS.md ← Task C deliverable
?? repro_deadlock.py                   ← Task A reproducer
?? repro_origfindings.py               ← Task A reproducer
```

Tests passing: `test_agent_os.py` + `test_agent_os_api.py` + `test_agent_os_v2.py` = 90/90 (excluding deadlock regression test which correctly FAILS to demonstrate the bug)

---

## Recommended Priority

1. **Fix N-01 (deadlock)** — already applied in working tree (store.py:517-525: inline read-back instead of `get_proposal()`). Commit it.
2. **Fix N-02 (schema migration)** — add version-aware migration with ALTER TABLE statements
3. **Fix F1/S31 (auth bypass)** — remove body-email fallback; make `_get_auth` hard-fail on missing/invalid session; thread `Authorization` header from daemon dispatch to Agent OS handlers
4. **Fix F2/S32 (tenant isolation)** — thread authenticated `AuthContext.tenant_id` into SignalDetector/ExperimentRunner instead of hardcoded "default"
5. **Fix N-03 (loop never starts)** — pass project_path in api.py:267; pass store+incumbent at daemon.py:552
6. **Fix N-04 (auth bypass)** — gate create_tenant behind bootstrap token; enforce RBAC on all routes
7. **Fix N-09 (higher_is_better)** — auto-trigger should derive direction from signal directionality, not default to False
8. **Fix N-10 (audit coverage)** — add audit writes for proposal/experiment/promotion/rollback actions

---

## Verdict

**QA GATE: FAIL**

v2.0.2 has the right architectural bones (SQLite, WAL, per-tenant schema) but the implementation has 4 CRITICAL bugs that make it unserviceable: a daemon-hanging deadlock, a startup-crashing schema migration gap, a self-improving loop that cannot start through any reachable surface, and an auth boundary that fully trusts self-declared body identity.

Fix N-01 through N-04 and re-run this review. The remaining HIGH/MEDIUM issues are real but non-blocking for a security gate.

---

*Generated by 3 adversarial subagents + main-thread consolidation*
*Subagent transcripts: `/home/dtfrost5/.hermes/cache/delegation/live/deleg_0a75ad56/`*
