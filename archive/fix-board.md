# NeuralMind Fix Board

_Date: 2026-07-11 | Source: audit-findings-2026-07-15.md_

---

## MEDIUM Findings (Fix First)

### FIX-001: MCP Auth Bypass When `project_path` Absent
**Severity:** MEDIUM | **Layer:** Auth & Access Control

**Problem:** `neuralmind/mcp_server.py:680-685` silently skips RBAC/rate-limiting when `project_path` is falsy. A misconfigured client can bypass all security.

**File:** `neuralmind/mcp_server.py:680-685`

**Fix:** Reject the call when `project_path` is falsy. Change:
```python
# OLD (allows bypass):
project_path_raw = arguments.get("project_path")
project_path = str(project_path_raw) if project_path_raw else None
if project_path:
    security = get_security_manager(project_path)
    result = security.secure_call(actor, role, name, lambda: handlers[name](arguments))
    return json.dumps(result, indent=2, default=str)
else:
    return json.dumps(handlers[name](arguments), indent=2, default=str)

# NEW (rejects bypass):
project_path_raw = arguments.get("project_path")
project_path = str(project_path_raw) if project_path_raw else None
if not project_path:
    return json.dumps({"error": "project_path is required", "code": "invalid_request"})
security = get_security_manager(project_path)
result = security.secure_call(actor, role, name, lambda: handlers[name](arguments))
return json.dumps(result, indent=2, default=str)
```

**Verify:** `pytest tests/test_mcp_security.py tests/test_integration_security_backend_audit.py -v`

---

### FIX-002: Server Auth Token Not Persistent
**Severity:** MEDIUM | **Layer:** Auth & Access Control

**Problem:** `neuralmind/server.py:594` generates a new random token per startup via `secrets.token_urlsafe(16)` but never persists it. If the printed line is lost, there's no way to authenticate without restarting.

**File:** `neuralmind/server.py:594`

**Fix:** Persist the token to `~/.neuralmind/server-token.json` with `0o600` perms on first start, read it back on subsequent starts.

**Verify:** `pytest tests/test_server.py -v`

---

### FIX-003: `reinforce()` O(n²) Unbatched Writes
**Severity:** MEDIUM | **Layer:** Data Integrity & Concurrency

**Problem:** `neuralmind/synapses.py:456-508` executes one SQL statement per node-pair. 100 node IDs → ~5000 INSERT/UPDATEs in one transaction. SQLite degrades with large write transactions.

**File:** `neuralmind/synapses.py:456-508`

**Fix:** Batch the INSERT/UPDATE statements using `executemany()` or chunk the work into smaller transactions (e.g., 500 pairs per commit).

**Verify:** `pytest tests/test_synapses.py -v` + benchmark at 100+ nodes

---

### FIX-004: No Concurrency Test for Synapse Layer
**Severity:** MEDIUM | **Layer:** Testing Adequacy

**Problem:** No test calls `reinforce()` from two threads with overlapping node sets to verify final weights are correct.

**File:** `tests/test_synapses.py` (missing test)

**Fix:** Add a test that spawns 2 threads, each calling `reinforce()` on overlapping node IDs, then verifies the final weight equals the expected sum.

**Verify:** `pytest tests/test_synapses.py::test_concurrent_reinforce -v`

---

### FIX-005: No Auth-Bypass Test in `handle_tool_call`
**Severity:** MEDIUM | **Layer:** Testing Adequacy

**Problem:** `tests/test_mcp_security.py` only tests the security manager primitives, not the MCP handler's auth-bypass path (line 681-685).

**File:** `tests/test_mcp_security.py` (missing test)

**Fix:** Add a test that calls `handle_tool_call` with a missing `project_path` and verifies it returns the error response (does NOT execute the tool).

**Verify:** `pytest tests/test_mcp_security.py::test_handle_tool_call_requires_project_path -v`

---

### FIX-006: Server Auth Flow Not Tested
**Severity:** MEDIUM | **Layer:** Testing Adequacy

**Problem:** `tests/test_server.py:144` disables auth (`auth_token = None`) so no auth-enabled request path is exercised. Tests don't verify that `_check_auth` rejects expired/mismatched cookies.

**File:** `tests/test_server.py` (missing test)

**Fix:** Add tests that:
1. Start server WITH auth
2. Make a request without token → expect 401
3. Make a request with valid token → expect 200
4. Make a request with invalid token → expect 401

**Verify:** `pytest tests/test_server.py::test_auth_flow -v`

---

### FIX-007: Embedder Only Mock-Tested
**Severity:** MEDIUM | **Layer:** Testing Adequacy

**Problem:** `tests/test_embedder.py` only exercises pure logic and ChromaDB mocks. The ONNX path (`onnx_embedder.py`) is never tested.

**File:** `tests/test_embedder.py` (missing ONNX test)

**Fix:** Add a test that runs the ONNX embedder end-to-end (if the model is available in CI). Mark with `@pytest.mark.skipif` if model is not present.

**Verify:** `pytest tests/test_embedder.py::test_onnx_embedding -v`

---

## LOW Findings (Fix After MEDIUM)

### FIX-008: Global Mutable Caches Never Cleared
**Problem:** `_mind_cache`, `_security_cache`, `_SECURITY_MANAGERS` module-level dicts in `mcp_server.py:47-48` and `mcp_security.py:35` grow without bound. Long-running MCP servers leak `NeuralMind` instances for every unique `project_path`.
**Fix:** Add TTL eviction + a `clear_caches()` method for tests.
**Verify:** `pytest tests/test_mcp_security.py -v` + manual inspection after running >5 minutes

### FIX-009: Frozen Env Var at Import Time
**Problem:** `neuralmind/config.py:7-20` reads `OPENROUTER_API_KEY` at import time. Any late env change is ignored.
**Fix:** Change `api_key` to read from `os.environ` at call time (lazy), not import time.
**Verify:** `pytest tests/test_config.py -v`

### FIX-010: `decay()` Holds Large-Table Locks
**Problem:** `neuralmind/synapses.py:611-711` runs 9 UPDATEs + 4 DELETEs + meta upsert in one transaction. Each UPDATE is a full-table scan (no WHERE targeting specific namespaces beyond `IN (?, ?)`).
**Fix:** Chunk the UPDATEs by namespace in smaller transactions (e.g., 1000 rows per commit).
**Verify:** `pytest tests/test_synapses.py -v` + benchmark at 100K+ synapses

### FIX-011: Trivial Mocks in `test_core.py`
**Problem:** `tests/test_core.py:261-264` patches `log_query_event` then asserts it was called — proves `mock.patch` works, not that `query()` actually calls it.
**Fix:** Remove the patch; call the real function and inspect via spy or side-effect.
**Verify:** `pytest tests/test_core.py::test_query_logs_memory_event -v`

### FIX-012: No UNIQUE Constraint on `synapse_transitions` (False Positive)
**Problem:** Audit flagged the schema, but the `PRIMARY KEY (from_node, to_node, namespace)` is actually correct.
**Fix:** No code fix. Update audit report to confirm no missing UNIQUE.

---

## Execution Order

| Order | Fix | Time | Blocker |
|-------|-----|------|---------|
| 1 | FIX-001 | 5 min | None |
| 2 | FIX-005 | 10 min | None (independent) |
| 3 | FIX-002 | 15 min | None |
| 4 | FIX-006 | 20 min | None |
| 5 | FIX-004 | 15 min | None |
| 6 | FIX-007 | 15 min | None |
| 7 | FIX-008 | 20 min | None |
| 8 | FIX-003 | 30 min | None |
| 9 | FIX-010 | 30 min | None |
| 10 | FIX-009 | 10 min | None |
| 11 | FIX-011 | 10 min | None |
| 12 | FIX-012 | 2 min | None |

**Total: ~3.5 hours of focused work**

---

## Done Criteria

- [ ] All 12 fixes applied
- [ ] Each fix verified with `pytest` + `mypy`/`pyright`
- [ ] Each fix committed individually
- [ ] Regression: no test failures, no new warnings
