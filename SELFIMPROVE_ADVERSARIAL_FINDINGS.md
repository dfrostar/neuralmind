# NeuralMind v2.0.2 — Adversarial Re-Review: Self-Improving Loop & Crash Safety

**Repo:** `/home/dtfrost5/neuralmind` @ `main`, HEAD `5572679` ("feat(agent-os): v1.16.0 phases 5-7")
**Version reality:** `pyproject.toml:7` and `neuralmind/__init__.py:111` still report **2.0.1**; `git tag` has **v2.0.1, no v2.0.2**. The SQLite migration this pass targets is present as an un-released dev state toward v2.0.2.
**Method:** full file trace + 9 executable reproducers (run under `.venv`; all but the deadlock reproduced live in this session).

---

## A. SELF-IMPROVING LOOP END-TO-END TRACE — **BROKEN at 6 independent points**

Wanted: `signal_detector.push()` → `auto_trigger._on_signal_insight()` → `experiment_runner.run()` → `promotion_engine.run()` → `ship_callable()`. Every link after `push()` is severed in the wired daemon path.

### [CRITICAL] S1 — Loop never STARTS over the HTTP surface: `update_signal` drops `project_path`
- `api.py:267` calls `signal_detector.push(metric_name, sample)` with **no `project_path`**.
- `signals.py:291` gates correlator on `project_path is not None` → insight is always `None` → `_on_signal_insight` (the auto-trigger callback) is never invoked (`signals.py:304`).
- **Proved (probe A1):** pushed 30 anomaly values through the real route handler → 0 insights, 0 proposals, 0 experiments created. The self-improving "brain" is not reachable through the daemon's own `POST /api/agent-os/signals`.
- Daemon HTTP is the ONLY surface that instantiates the loop (`daemon.py:552`); CLI `signals push` builds a storeless detector (`cli.py` → `SignalDetector(correlator=…)`, no store/auto-trigger registered). So **no reachable surface starts the loop.**

### [CRITICAL] S2 — `AutoTriggerLoop` wired WITHOUT store and incumbent → promotion is a NO-OP
- `daemon.py:552`: `AutoTriggerLoop(signal_detector)` — omits `store=store` and any `incumbent`.
- `auto_trigger.py:48-50`: with `incumbent=None`, `_engine=None`; `_detector._auto_trigger` still registered, but the loop has no store and no incumbent.
- `_on_signal_insight` falls back to `get_store()` (`auto_trigger.py:58-60`), but `_auto_run_experiment` uses `self._store` directly with **no fallback** (`auto_trigger.py:109`) → `store=None` in daemon → engine built with `store=None` → **experiment and promotion rows never persisted** (`auto_trigger.py:123/144`).

### [CRITICAL] S3 — `ship_callable` is the NO-OP default; incumbent never updates (M10 verification)
- In `_auto_run_experiment`, the engine is first created with `incumbent=` but **`proposal=None`** (`auto_trigger.py:123-127`).
- `promotion.py:222-227`: because `proposal is None`, `_ship_callable = _noop_ship` and `_auto_promote = False`.
- Later the `else` branch only patches `_proposal`/`_signal_count` (`auto_trigger.py:149-151`); it **never rewires `_ship_callable` or flips `_auto_promote`**.
- **Proved (probe4):** after forcing the experiment through, `engine._auto_promote=False`, `_ship_callable=<function _noop_ship>`, incumbent value stayed `100.0`, DB incumbent row `None`, experiment/promotion rows empty. The noop logs "Human review required" and returns — **PROMOTED/ROLLED_BACK never touch `TunerIncumbent`.**

### [CRITICAL] S4 — `increment_signal_count` hard DEADLOCK blocks the 2nd signal (N1 confirmed)
- `store.py:501-517`: body wrapped in `with self._tx()` (non-reentrant `threading.Lock`, `store.py:200`), then `store.py:517` calls `self.get_proposal()` → `with self._lock:` again → **self-deadlock**. `threading.Lock` is not reentrant.
- Trigger: `auto_trigger.py:93` on the **2nd signal** for an open proposal.
- **Proved (`repro_deadlock.py`):** timed out via SIGALRM — "increment_signal_count deadlocked (non-reentrant Lock)". 
- Decisive: since the loop (direct path) creates a proposal at signal #1 (`signal_count=1`), signal #2 deadlocks the daemon. **The MIN_SIGNALS=5 gate cannot be reached on any open proposal — the live loop hard-hangs before promotion, making auto-promote unreachable by design.**

### [HIGH] S5 — Page-Hinkley with constant baseline (std=0) can FAIL to ever fire (severity/0 guard)
- `signals.py:124-127`: `severity_ratio = cumulative_deviation / std`; `signals.py:148` requires `std > 1e-9`. A perfectly stable stream (`m2≈0`) → `std≈0` → signal never fires regardless of shift magnitude, until enough shifted samples accumulate variance. Not deterministic on real noisy streams, but the "one-way" ratio is fragile. (Probe B2/B3 show state loads fine; the trigger path is what's brittle.)

### [MEDIUM] S6 — Default `higher_is_better=False` makes the loop a net REGRESSION engine
- `promotion.py:257 expt run` defaults `higher_is_better=False`; `_auto_run_experiment` never passes `higher_is_better=True` (`auto_trigger.py:158`).
- `experiment.py:129-135` negates the delta when `higher_is_better=False`: a candidate value *higher* than baseline → negative delta → `ROLLED_BACK`.
- **Proved (probe4):** candidate=200 vs baseline=100 → verdict `rolled_back`, `delta=-1.0`. So even a correctly-wired promotion would roll back every genuine improvement.

### [HIGH] S7 — TOCTOU: duplicate proposals per metric under concurrency
- `_on_signal_insight`: `list_proposals` (auto_trigger.py:63) then `create_proposal` (72) — no store lock across check-and-create; the detector RLock is process-local and does not serialize store writes.
- **Proved (probe7):** two concurrent fires → **two proposals** (`prop_3…`, `prop_c…`), both `signal_count=1`. Splits the signal budget across duplicates → MIN_SIGNALS unreachable per proposal; state bloat.

### AutoTriggerLoop lifecycle (daemon):  **NOT a daemon thread; process-bound.**
- `daemon.py:552` builds the loop **lazily** when the first agent-os route is matched (`_match_agent_os_route` init, `daemon.py:509-511, 529-556`). It is not spun up at startup, not a daemon thread, and has no on-disk rehydration — it simply re-runs every process on `_init_agent_os_routes` (module-level cached on the function, `daemon.py:509`). Rediscovered state comes from the shared SQLite store (state restore works — see B), but the loop's in-memory `_incumbent`/`_engine`/`_history` are **fresh every restart**, so a "resume" only re-runs via DB reads; no loop-safe continuation.

---

## B. CRASH SAFETY — **SQLite WAL gives atomic single-op writes, but durability gaps remain**

### [OK] B-fixed — Kill -9 after committed writes: rows survive
- **Proved (probe6):** child process killed with `SIGKILL` after `insert_signal`/`persist_signal_state`/`insert_experiment`/`persist_incumbent` → all four rows intact after reopening. WAL files (`agent-os.db-wal`, `-shm`) remain on disk and replay correctly. No manual checkpoint/VACUUM is issued (SQLite autocheckpoint at 1000 pages bounds the WAL). Acceptable.

### [HIGH] B1 — Corrupt DB bricks startup; no recovery path
- `store.py:226-238 _init_db` → `executescript(_SCHEMA)` raises `DatabaseError: file is not a database` on a corrupt/garbage file (probe6). No fallback, no backup-and-recreate, no error boundary. **Daemon won't start; `SignalDetector._load_state` never runs.** Signals/experiments/incumbent unwritable. (Additional: N2 — no schema-migration gate means any future `_SCHEMA_VERSION` bump + new column bricks existing DBs on startup.)

### [MEDIUM] B2 — Signal state recovery works (fixed), but only in the daemon-store path
- **OK (probe6/B3):** `_load_state` (`signals.py:238-244`) restores `_PageHinkleyState` from `signal_states`; Page-Hinkley counters, `last_signal_at`, `cooldown_seconds` all reloaded. **Fixed vs v2.0.1** (D17 daemon path).
- **Gap:** CLI constructs a storeless detector (`cli.py`) → `_load_state` no-op → CLI builds Page-Hinkley from scratch each invocation (D17 "daemon yes / CLI no").

### [MEDIUM] B3 — Audit is a SEPARATE transaction, and the loop never audits anything
- `store.audit()` is its own `_tx()` (`store.py:666-693`) — **not atomic with** the action it records. Crash between action-commit and audit-commit loses the audit row but keeps the action.
- More importantly: **the agent_os loop performs ZERO audit writes.** `store.audit()` is called only from `governance.py:_audit` for RBAC permission checks and tenant lifecycle (governance.py:217,224,268,286,297). Signal detection, proposal creation, experiment runs, promotions, rollbacks, and incumbent updates are **never audit-logged** → no governance trail for the self-improving loop. (Separate `signals_log.py` writes to its own logs — not the audit_log table.)

### [OK] B4 — TunerIncumbent recovery: last shipped value restored
- **Proved (probe6/B3):** `TunerIncumbent.__init__` (`promotion.py:110-116`) loads persisted `value`/`tag`/`history` from `tuner_incumbents`; a value of `120.0`/tag `candidate` was restored after kill-9. Fallback is the `initial_value` constructor arg if no row. **Fixed** for the store-backed path. (But recovery only matters if promotion ever ships — it never does, per S3.)

---

## C. ORIGINAL FINDING VERIFICATION (v2.0.1 → now)

| ID | Original | Status | Evidence |
|----|----------|--------|----------|
| **O9** (HIGH) self-improving loop dead | `AutoTriggerLoop` is now instantiated in daemon (`daemon.py:552`) with a real `_auto_trigger` callback (`auto_trigger.py:52`). **But:** (a) no `project_path` on the API push (S1) means the callback never fires from any reachable surface; (b) `store`/`incumbent` not passed → `_auto_promote=False` + no-op ship + no persistence (S2/S3); (c) 2nd signal deadlocks (S4). | **NOT FIXED — worse described** | probes A1, 2, 4; `repro_deadlock.py` |
| **M10** (HIGH) promotion/rollback not wired | `ship_callable` is wired *only* when `incumbent AND proposal` are passed together (`promotion.py:222`). `_auto_run_experiment` passes incumbent alone first (`auto_trigger.py:123`) → no-op default; the later patch doesn't rewire it (S3). `_tuner_incumbent_ship_callable` (`promotion.py:150-167`) correctly maps PROMOTED→candidate / ROLLED_BACK→baseline, but is **never installed in the loop path**. | **NOT FIXED** | probe4 |
| **C21** (MEDIUM) thread safety | RLock `signals.py:232` covers detector state + the whole correlated callback. But the Store's lock is the non-reentrant `threading.Lock` (`store.py:200`) and `increment_signal_count` re-acquires it → **deadlock** (S4). Daemon creates TWO AgentOSStore instances to the SAME file — `store` (local, `daemon.py:541`) vs `get_store()` singleton (callback) — separate connections + separate locks, so they don't serialize each other (probe8). TOCTOU duplicate proposals on concurrent signals (S7). | **NOT FIXED** | probes 7, 8; `repro_deadlock.py` |
| **C22** (MEDIUM) experiment history per-tenant | Per-tenant filtering exists in the SQL (`store.py:559-568`: `WHERE tenant_id = ? AND metric_name = ?`). **But `ExperimentRunner._history_from_store` hardcodes `metric_name="all"`** (`experiment.py:108`) → returns rows only if a metric is literally named `all` → **effectively always empty** → p-value and CI historical base are empty → `p_value` is always `None` (proved probe5). API `list_experiments` calls in-memory `get_history()` (`api.py:337`) → **empty after restart even though rows persist** (a fresh `ExperimentRunner` never loads `_history` from the store at construction). | **PER-TENANT SQL YES / history pipeline NO** | probe5 |

---

## NEW FINDINGS SUMMARY
| ID | Finding | Severity | Location |
|----|---------|----------|----------|
| S1 | `project_path` never passed → auto-trigger unreachable via daemon HTTP | CRITICAL | api.py:267, signals.py:291/304 |
| S2 | AutoTriggerLoop no store/incumbent → noop engine, no persistence | CRITICAL | daemon.py:552, auto_trigger.py:48-50, 109, 123/144 |
| S3 | ship_callable = `_noop_ship`; incumbent never updates | CRITICAL | auto_trigger.py:123-151, promotion.py:222-227 |
| S4 | `increment_signal_count` self-deadlock (N1) → 2nd signal / daemon hang, MIN_SIGNALS unreachable | CRITICAL | store.py:200/501-517, auto_trigger.py:93 |
| S5 | Page-Hinkley std=0 guard can prevent firing | HIGH | signals.py:124-148 |
| S6 | default `higher_is_better=False` negates delta → improves always rolled back | MEDIUM | experiment.py:129-135, auto_trigger.py:158 |
| S7 | TOCTOU duplicate proposals under concurrency | HIGH | auto_trigger.py:63-83 |
| B1 | corrupt DB bricks daemon startup; no migration gate (N2) | HIGH | store.py:226-238, 39 |
| B2 | CLI storeless detector → no state persist/restore on CLI | MEDIUM | cli.py, signals.py:240/257 |
| B3 | audit separate txn + self-improving loop never audited | MEDIUM | store.py:666-693, governance.py:185-200 |
| N1 | (confirmed from prior pass) increment_signal_count deadlock | CRITICAL | store.py:501-517 |
| N3/N4 | split business transactions; `update_proposal` silently drops `last_experiment_id`/`last_verdict` columns (auto_trigger.py:162-167) | MEDIUM | auto_trigger.py:155-167, store.py:463-499 |

**Outcome:** The self-improving loop is *wired in shape but dead in function*. A signal pushed to the one surface the daemon exposes never produces an insight (S1); if the direct path somehow fires, the loop has no store/incumbent (S2), ships nothing (S3), and deadlocks on the second signal (S4) before the MIN_SIGNALS=5 gate is ever reached. Promotion/rollback cannot ship a single value. **Not shippable as a self-improving loop; the "autonomous signal→diagnose→experiment→promote" claim (site/docs) is unsupported by the executable path.**

## Artifacts
Executable reproducers copied to `/tmp/nm_adversarial_repros/` (`probe*.py`, `adversarial_loop_repro.py`, `repro_deadlock.py`). Repo left clean — probe scripts removed; no tracked files modified.
