# NeuralMind Codebase Review & Fix Status

**Date:** 2026-07-11 | **Branch:** `pr-fix-board` | **Maintained by:** Hermes Agent (LongCat-2.0)

---

## Audit Summary

A 5-layer codebase audit (`audit-findings-2026-07-15.md`) identified:
- 0 CRITICAL, 0 HIGH, **7 MEDIUM**, 7 LOW findings.

The fix board (`fix-board.md`) tracks all 12 findings with concrete code and verification commands.

---

## Fixes Completed (Batch 1)

| Finding | File | Lines | Change |
|---------|------|-------|--------|
| **FIX-001** MCP Auth Bypass | `mcp_server.py:675-686` | 12 | Reject tools calls with falsy `project_path` — return `{"error": "project_path is required", "code": "invalid_request"}` |
| **FIX-002** Token Persistence | `server.py:594-607` | 12 | Token persisted to `~/.neuralmind/server-token.json` with `0o600` perms. On restart, read back existing token. |
| **FIX-005** Auth-Bypass Tests | `test_mcp_security.py` | 42 | `test_handle_tool_call_rejects_missing_project_path` + `test_handle_tool_call_rejects_empty_project_path` |
| **FIX-008** Cache Cleanup | `mcp_server.py:47-60` | 11 | `clear_all_caches()` + `get_cache_stats()` for observability and test isolation |
| **FIX-009** Frozen Env Var | `config.py:17` | 1 | Removed `os.environ.get("OPENROUTER_API_KEY")` from `DEFAULT_CONFIG` (frozen at import time) |

### Verification Status
```
tests/test_mcp_security.py::test_handle_tool_call_rejects_missing_project_path PASSED
tests/test_mcp_security.py::test_handle_tool_call_rejects_empty_project_path PASSED
tests/test_mcp_security.py ..................  5/5 PASSED
tests/test_config.py .........................  12/12 PASSED
```

**Branch:** pushed to `origin/pr-fix-board`

---

## Fixes In Progress (Subagents Running)

| Finding | File | Change | Subagent |
|---------|------|--------|----------|
| FIX-003 | `synapses.py:450-520` | Batch `reinforce()` INSERTs into chunks of 500 (avoid O(n²) writes) | ✅ Running |
| FIX-004 | `test_synapses.py` | `test_concurrent_reinforce` — 2 threads, overlapping node IDs, final weight verification | ✅ Running |
| FIX-006 | `test_server.py` | `test_auth_enabled_flows` — request without token (401), with valid token (200), with invalid (401) | ✅ Running |
| FIX-007 | `test_embedder.py` | `test_onnx_embedding_e2e` — real ONNX path (shape `(n, dim)`) | ✅ Running |
| FIX-010 | `synapses.py:600-720` | Chunk `decay()` into batches of 1000 namespaces per transaction | ✅ Running |
| FIX-011 | `test_core.py:250-275` | Remove trivial `mock.patch` on `log_query_event`; verify real call via spy | ✅ Running |

**Batch 1:** 3 subagents (FIX-003, FIX-006, FIX-004)  
**Batch 2:** 3 subagents (FIX-007, FIX-011, FIX-010)

---

## After Subagents Complete

1. **Merge subagent branches** into `pr-fix-board`
2. **Run full test suite** to verify no regressions
3. **Type-check** if `mypy`/`pyright` configured

```bash
python3 -m pytest tests/ -v 2>&1 | tail -20
```

4. **Commit + push** to `origin/pr-fix-board`

---

## Remaining Finding

| Finding | File | Action Needed |
|---------|------|---------------|
| FIX-012 | `synapses.py:155-165` | False positive — `PRIMARY KEY (from_node, to_node, namespace)` is correct. No code change. Document in audit. |

---

## Post-Merge Checklist

- [ ] All 12 fixes applied
- [ ] Full test suite green (`pytest tests/ -v`)
- [ ] No new warnings from existing tests
- [ ] `fix-board.md` marked all items Done
- [ ] `audit-findings-2026-07-15.md` updated with resolution status
