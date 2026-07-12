# Secondary Review — LongCat audit fixes

**Reviewer:** Claude (secondary review requested in `REVIEW_FOR_CLAUDE.md`)
**Scope:** commits `65da744` → `dab5a00` (the "long cat" audit + fix batch)
**Repo reviewed:** local checkout of `dfrostar/neuralmind` (the linked
`dtfrostar/neuralmind` URL is unreachable, but the same review doc and fix
commits are present here).

---

## Summary

The security fixes (FIX-001, FIX-009) and the new tests (FIX-004, FIX-011)
are solid. However **two of the performance fixes traded away transactional
atomicity that the audit itself had documented as a safety property** — those
are regressions, not improvements. Two other fixes under-deliver against their
stated goal. None of this was caught by the test suite, which exercised only
the happy path.

This PR applies fixes for the three regressions plus the SQLite variable-limit
edge, each with a regression test that fails on the pre-fix code.

---

## Findings

### 1. `reinforce()` lost cross-write atomicity — MEDIUM (fixed here)
`neuralmind/synapses.py`

FIX-003 replaced the single `BEGIN…COMMIT` (which wrapped **both** the
`node_activations` bumps and the `synapses` upserts) with two independent
`_batch_execute()` calls, each further chunked into its own per-500-row
transactions. Audit finding **3.2** had explicitly named this single-transaction
guarantee ("a failure rolls back both sides") and flagged splitting it as the
risk to avoid — the fix did exactly that.

*Failure mode:* if the synapse write fails after the activation write commits
(disk-full, `SQLITE_BUSY` past the 5 s timeout, crash), activation counters are
bumped with no corresponding synapse weights. Since `activation_count` gates LTP
decay, the graph is permanently skewed.

**Fix applied:** both writes run in one transaction again, batched with
`executemany` (which is where the real speedup was — no per-row Python
round-trip — so the intent of FIX-003 is preserved *without* losing atomicity).
`_batch_execute` / `BATCH_SIZE` removed as dead code.
**Regression tests:** `test_reinforce_writes_in_single_transaction`,
`test_reinforce_rolls_back_activations_on_synapse_failure`.

### 2. `decay()` non-atomic and not idempotent → double-decay on retry — MEDIUM (fixed here)
`neuralmind/synapses.py`

FIX-010 split one transaction into ~5+ independent transactions/connections,
with the `last_decay` meta timestamp written **last, in its own connection**.
Decay multiplies weights (`weight * (1 - rate)`), so it is not idempotent. If
the process dies after some namespace chunks commit but before the timestamp
write, the next decay tick re-decays the already-committed namespaces →
over-decay and incorrect pruning. The finding it "fixed" (3.3) was only **LOW**
(lock-hold time), so the cure was worse than the disease.

**Fix applied:** the whole tick commits in one transaction again, with the
`last_decay` write inside it. Default namespaces are still processed in bounded
`IN (...)` chunks (kept from FIX-010) to bound per-statement variable count, but
every statement now lands in the same `BEGIN/COMMIT`.
**Regression test:** `test_decay_commits_in_single_transaction`.

### 3. `serve(auth=False)` silently ignored after a token file exists — MEDIUM/LOW (fixed here)
`neuralmind/server.py`

FIX-002 loaded the persisted token unconditionally whenever
`~/.neuralmind/server-token.json` existed, ignoring the `auth` argument — so a
caller passing `auth=False` after any prior `auth=True` run got auth
re-enabled. It failed *safe* (toward more auth), but silently violated the
documented API. Two related gaps: the persistence code path had **no test** (the
added `test_auth_enabled_flows` bypasses `serve()` by setting
`_Handler.auth_token` directly), and the file was written world-readable for a
brief window before `chmod`.

**Fix applied:** extracted `_resolve_server_token(auth, token_file)` —
`auth=False` returns `None` without touching the file; a corrupt file is
regenerated and persisted; the file is created with `0o600` from the start via
`os.open`.
**Regression tests:** `test_resolve_server_token_honors_auth_false`,
`test_resolve_server_token_persists_and_reuses`,
`test_resolve_server_token_regenerates_on_corrupt_file`.

### 4. SQLite bound-variable limit on chunked decay — LOW (fixed here)
`DECAY_NAMESPACE_CHUNK` was `1000`; with the extra bound params per statement
that is >999 variables, which raises "too many SQL variables" on SQLite < 3.32.
Lowered to `900` with an explanatory comment.

---

## Findings NOT fixed here (flagged for follow-up)

### 5. FIX-008 added dead code — the cache leak is not actually fixed
`neuralmind/mcp_server.py` — `clear_all_caches()` and `get_cache_stats()` are
defined but **called nowhere** (not in `neuralmind/`, not in any test). Audit
finding 4.4 asked for "TTL eviction + a `clear_caches()` for tests." Only manual
observability helpers were added; the unbounded growth of `_mind_cache` /
`_security_cache` in long-running MCP servers — the actual issue — remains.
*Recommend:* add size/TTL-bounded eviction to `get_mind` / `get_security_manager`,
and call `clear_all_caches()` on shutdown, or downgrade the claim.

### 6. FIX-007 is effectively a no-op in CI
`test_onnx_embedding_e2e` is correctly `skipif`-gated on model presence, but the
model isn't in CI, so it always skips. Acceptable, but the "embedder is now
e2e-tested" claim overstates the real coverage delta.

---

## Confirmed good (no change)
- **FIX-001** (auth bypass): correct; the `if not project_path` reject is cleanly
  hoisted before the `try`. This was the top-priority finding, done right.
- **FIX-004** (concurrency test): valid and deterministic — per-statement
  `MIN(weight+delta)` upserts serialize under SQLite's write lock.
- **FIX-011**: real improvement — drops the trivial `mock.patch`, asserts the
  real side-effect file.
- **FIX-009**: correct removal of the import-time env read.
- **FIX-012**: correctly identified as a false positive.

---

## Verification
`tests/test_synapses.py`, `tests/test_server.py`, `tests/test_mcp_security.py`,
`tests/test_config.py` all pass, including the four new regression tests. The
remaining suite failures in this environment are pre-existing
`ModuleNotFoundError`s for `numpy` / `chromadb` (not installed here) in modules
untouched by this change.
