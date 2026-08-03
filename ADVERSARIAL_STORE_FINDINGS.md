# NeuralMind v2.0.2 — Adversarial Review of neuralmind/agent_os/store.py

Repo: /home/dtfrost5/neuralmind @ main (`5572679`, v1.16.0 HEAD)
Scope: unified SQLite store (replaces 5 JSONL stores). Read store.py (760 lines),
signals.py (D17), governance.py (D20), auto_trigger.py, cli.py, proposal_store.py.

## NEW CRITICAL FINDINGS

### [CRITICAL] N1 — Deadlock in `increment_signal_count` (non-reentrant lock re-acquisition)
- store.py:501-517: `increment_signal_count` wraps body in `with self._tx()` which
  acquires the non-reentrant `threading.Lock` (store.py:200).
- store.py:517: `return self.get_proposal(tenant_id, proposal_id)` is called INSIDE that
  `with self._tx()` block. `get_proposal` (store.py:450-455) does `with self._lock:` again.
- `threading.Lock` is NOT reentrant → the second acquire blocks forever.
- **Reproducer**: `python3 repro_deadlock.py` — hangs (killed by `timeout`, exit 124) after
  printing "calling increment_signal_count...". Confirmed hard deadlock.
- **Trigger path**: `auto_trigger.py:93` calls `increment_signal_count` every time a
  second signal fires on an already-open proposal → the LIVE DAEMON hangs on the 2nd signal.
- **Why CI missed it**: `tests/test_signal_pipeline.py:267` and `test_ship_callable.py` set
  `signal_count` via `update_proposal`, never via `increment_signal_count`. No test covers it.
- Severity: CRITICAL — daemon availability / silent hang.

### [CRITICAL] N2 — No schema migration; startup crash on _SCHEMA_VERSION bump (vector 1)
- store.py:39 `_SCHEMA_VERSION=2`. store.py:226-238 `_init_db` does `executescript(_SCHEMA)`
  then only INSERTs version when `schema_version` is EMPTY (store.py:233-238).
- There is NO migration path. If the DB has version 1 and code bumps to 2, nothing compares
  versions, nothing runs ALTER TABLE.
- Because `CREATE TABLE IF NOT EXISTS` no-ops on an existing table, a new column added to a
  table in vN+1 is SILENTLY MISSING — and the schema references it in an index →
  **`executescript(_SCHEMA)` raises `OperationalError: no such column: metric_name`**
  and the daemon refuses to start. Reproducer confirmed (`repro_migration2.py`):
  - v1 table `signals` without `metric_name` → `AgentOSStore()` crashes.
  - healthy v1 DB (version=1) → after init `schema_version` is STILL 1, never bumped to 2.
- The `schema_version` table is pure dead weight; nothing reads it to gate migrations.
- Severity: CRITICAL — any schema evolution bricks existing deployments; data can't be read.

### [MEDIUM] N3 — Split/business-level transactions, no atomicity (vector 3)
- The store's `_tx()` gives atomicity ONLY per single method call. The end-to-end auto-promote
  flow in `auto_trigger.py:_auto_run_experiment` (155→158→162) is split across many independent
  transactions: `update_proposal(running)` → `_engine.run()` (insert_experiment/promotion/
  incumbent, each its own txn) → `update_proposal(final)`.
- Crash between them leaves a proposal stuck `running` with no experiment/verdict row. This is
  the same "split transaction divergence on crash" the store claims to have fixed (D19 was
  scoped only to a single audit INSERT). No multi-statement business transaction exists.
- Severity: MEDIUM — inconsistent state on crash (not data loss, but corrupt workflow state).

### [MEDIUM] N4 — `update_proposal` silently drops unknown keys (FK-relaxation side effect)
- `auto_trigger.py:162-167` passes `{"last_experiment_id":..., "last_verdict":...}` to
  `store.update_proposal`. The columns don't exist in `proposals` (schema store.py:89-104) and
  `update_proposal` (store.py:463-499) merges them into `current` but never writes them to SQL
  (fixed column list only). The experiment→proposal linkage is silently LOST — no error, no log.
- Severity: MEDIUM — silent data-model mismatch; the "last experiment" link is dropped.

## NEW FINDINGS (lower severity)

### [LOW] N5 — Connection lifecycle no `__del__` / no atexit (vector 6)
- No `__del__`, no `atexit` handler anywhere in agent_os. Only explicit `close()` (store.py:723)
  and `reset_store()` (755) close the connection. Components that hold a store and never close
  leak the connection (and a WAL writer) for process lifetime. Minor for a daemon, but the
  module singleton (`_store`) pins `~/.neuralmind/agent-os.db` open from first `get_store()`.
  Verified `has __del__: False`.

### [LOW] N6 — module-level read lock contention (vector 7)
- store.py:200 one `threading.Lock` serializes ALL reads AND writes. Reads (get_signals,
  list_proposals, get_audit_log) take `self._lock` even though they don't need one vs. the
  same-thread serialization; the daemon is single-process so cross-thread writes are the only
  real writers, but the lock still blocks every other store call behind a slow bulk insert.
  WAL + single connection means SQLite itself serializes anyway; the Python lock adds head-of-line
  blocking on top. Contention path exists but is bounded. Severity: LOW-PERF.

### [LOW] N7 — Path traversal via env var (vector 10)
- store.py:189-198 / 738-746 build db_path from `NEURALMIND_AGENTOS_DIR` /
  `NEURALMIND_DAEMON_HOME`. A malicious/root-compromising env can point `agent-os.db` at
  `/root/.ssh/...` etc. Confirmed opening an arbitrary path is allowed (`mkdir` even creates
  parents, store.py:229). `agent-os.db` is just a sqlite file the process writes — it won't
  overwrite `/etc/shadow` (that's not a valid sqlite target), but it WILL clobber any writable
  path. This is standard config-injection surface, not a new privilege boundary. Severity: LOW
  (daemon-owned env, same trust domain).

### [LOW] N8 — Error handling (vector 8)
- store.py has NO `except Exception: pass`. audit() is fail-closed (raise, 690-693). Callers
  in signals.py wrap correlator/auto_trigger in `log.warning` (signals.py:296-301, 307-309) —
  those swallow but log. The store's `_tx` re-raises after rollback. Summary: no silent
  swallowing in store.py. The main hidden-error risk is N4 (silent column drop), not exceptions.

## ORIGINAL FINDING VERIFICATION

### D17 (state persistence on restart) — PARTIALLY FIXED
- store.py persists Page-Hinkley state (signal_states table, persist_signal_state store.py:285);
  `SignalDetector._load_state` (signals.py:238-244) restores via `get_all_signal_states`.
  Verified: persisted count=5, running_sum=3.0 restored on fresh detector (repro_origfindings.py).
- **BUT** the CLI path `cli.py:30` builds `SignalDetector(correlator=correlator)` with NO store
  → `_load_state`/`_persist_state` no-op (signals.py:240,257). State is only persisted/restored
  in the daemon auto-trigger path (auto_trigger.py:33). CLI `push`/`experiments` never touch the
  store on that object. So D17 is fixed in the daemon, still broken through the CLI.

### D19 (audit integrity) — FIXED
- audit() uses `_tx()` (single-statement atomic INSERT, store.py:676-689). Crash mid-write →
  rollback. Fail-closed raise on error. Verified source.

### D20 (cascade cleanup) — FIXED
- delete_tenant (store.py:705-719) deletes across all 9 tables, isolated by tenant_id. Verified:
  9/9 rows removed for t1, t2 untouched (repro_origfindings.py).

### O6/O7 (unbounded growth) — NOT FIXED
- No VACUUM, no wal_checkpoint, no retention/compaction in store.py or agent_os. `signals`,
  `insights`, `audit_log` grow forever; the DB file and WAL grow unbounded. The only pruning in
  the codebase is in other subsystems (metrics_pipeline retention, synapses). SQLite auto-
  checkpoints WAL at 1000 pages by default, so the WAL is bounded, but the main DB file is not.
  Severity: MEDIUM (long-running daemon → unbounded disk).

### Q25 (list_proposals O(n)) — FIXED
- Verified via EXPLAIN QUERY PLAN: indexed. tenant+status+metric uses `idx_proposals_metric`;
  tenant-only uses `idx_proposals_tenant`. Only weakness: `ORDER BY created_at DESC` triggers a
  TEMP B-TREE (no covering index on created_at), but it's not an O(n) table scan. Q25 resolved.

## SUMMARY SEVERITY TABLE
| ID | Vector | Severity | Status |
|----|--------|----------|--------|
| N1 | increment_signal_count deadlock | CRITICAL | NEW, reproducable hang |
| N2 | No migration / startup crash on schema bump | CRITICAL | NEW |
| N3 | Split business transactions | MEDIUM | NEW |
| N4 | update_proposal drops unknown keys | MEDIUM | NEW |
| N5 | Connection leak (no __del__/atexit) | LOW | NEW |
| N6 | Global lock contention | LOW | NEW |
| N7 | Env-var path injection | LOW | NEW |
| N8 | Error handling | n/a | clean |
| D17 | State restore on restart | PARTIAL | daemon yes / CLI no |
| D19 | Audit atomicity | FIXED | verified |
| D20 | Cascade delete | FIXED | verified (9 tables) |
| O6/O7 | Unbounded growth | NOT FIXED | no retention/compaction |
| Q25 | list_proposals indexing | FIXED | verified via EXPLAIN |

KEY: Fix N1 first (deadlock), then N2 (migration + version gating). N3/N4 are design gaps in
the auto-promote workflow. Recommend adding tests for increment_signal_count and the auto
promote path.
