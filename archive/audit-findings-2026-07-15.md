# NeuralMind Codebase Audit Report — 2026-07-15

## 1. Layer 1 — Integration Verification

**No pxpipe/LLM proxy integration exists for verification.** NeuralMind is a purely local-first system — it makes zero HTTP calls to any remote LLM endpoint (`api.openai.com` or otherwise). All embedding, synapse, and query logic is local. Per guidance, this section flags proxy misconfigurations, so the relevant finding is:

### 1.1 LLM Integration — NOT APPLICABLE (by design)
`neuralmind/embedder.py:86-88` | `neuralmind/onnx_embedder.py:40-66`
The codebase contains no LLM/chat completions proxy. Search hits for `openai`, `pxpipe`, and `api.openai.com` returned zero matches. All embeddings run through `chromadb.PersistentClient` or the bundled `turbovec_backend.ONNXEmbedder`, which loads an onnx model from disk (configurable via `NEURALMIND_ONNX_MODEL_DIR`). **No findings for this layer.**

## 2. Layer 2 — Auth & Access Control

### 2.1 Server auth token tied to process restart, not user
**MEDIUM** `neuralmind/server.py:594`
`serve()` generates a new random token with `secrets.token_urlsafe(16)` on each startup but never persists it to a file or config. A user who starts the server programmatically (not via `neuralmind serve`) must capture the printed URL to get the token — there is no way to retrieve it afterward. If the printed line is lost, there is no way to authenticate without restarting the server.

### 2.2 Auth is opt-in rather than opt-out
**MEDIUM** `neuralmind/server.py:582-583` | `neuralmind/mcp_server.py:681-685`
The HTTP server's `auth` parameter defaults to `True`, but the MCP server handler (`handle_tool_call`) skips security enforcement when `project_path` is falsy (line 681). If a caller omits `project_path` (which the schema does not require at the handler level — only individual tool `inputSchema` objects require it), the tool runs with no RBAC check. The daemon always requires `project_path`, but a future transport could call `handle_tool_call` without it.

### 2.3 Secret stored in plain JSON with 0o600 permissions — adequate but not encrypted
**LOW** `neuralmind/daemon.py:67-85`
The discovery file (`~/.neuralmind/daemon.json`) holds the bearer token in plaintext with `0o600` file permissions. This is adequate for a single-user localhost daemon. Not a code bug, but worth noting if multi-user or CI environments share `$HOME`.

## 3. Layer 3 — Data Integrity & Concurrency

### 3.1 Synapse reinforce uses per-row INSERT/UPDATE in a transaction, but the Python side builds pairs in a list — N+1-like construction under load
**MEDIUM** `neuralmind/synapses.py:456-508`
`reinforce()` iterates over `n` nodes to produce O(n²) pairs, then executes one SQL statement per pair inside a single transaction. This is not the classic N+1 query (it's one round-trip per node-pair), but it is **O(n² in Python with no batching**. Passing 100 node IDs yields ~5000 INSERT/UPDATE statements in one transaction. SQLite's performance degrades with large write transactions, and the connection is opened/closed per `reinforce()` call. A graph update from the watcher could pass many node ids at once.

### 3.2 No transactional guard between `node_activations` increment and `synapses` upsert in `reinforce()`
**LOW** `neuralmind/synapses.py:459-489`
The whole method runs inside `BEGIN/COMMIT`, so a failure rolls back both sides. Not a bug today — the transaction wraps both writes. Flagged as LOW because the code structure makes it easy for a future refactor to split the two write paths (e.g., wrapping `node_activations` and `synapses` in separate transactions), which would create a partial-failure state where activations bump but synapses don't.

### 3.3 `decay()` runs multiple UPDATE/DELETE statements in sequence, not batched
**LOW** `neuralmind/synapses.py:611-711`
`decay()` executes 9 SQL statements for `synapses` plus 4 for `synapse_transitions` plus a meta upsert — all inside one transaction. Correctness is fine, but each statement is a full-table UPDATE (no WHERE targeting specific namespaces beyond the `IN (?, ?)` clause). On a large synapse store, a single `decay()` call's UPDATEs can hold locks for the whole table.

### 3.4 No UNIQUE constraint on `synapse_transitions` for `(from_node, to_node)` without `namespace`
**LOW** `neuralmind/synapses.py:155-165`
The schema has `PRIMARY KEY (from_node, to_node, namespace)`, which is correct. The `CHECK (from_node <> from_node)` is fine. No missing UNIQUE.

## 4. Layer 4 — Type Safety & Code Quality

### 4.1 No `@ts-nocheck` or `# type: ignore` without justification
**NOTE**: This is a Python repo. TypeScript equivalents (`@ts-nocheck`) do not apply. All `# type: ignore` comments include code justifications (`attr-defined`, `assignment`, `import-untyped`, `no-redef`, `method-assign`). No instances of blanket type suppression.

### 4.2 Duplicate backend construction paths
**MEDIUM** `neuralmind/backend_manager.py:92-128` vs `neuralmind/mcp_server.py:47-58`
`BackendManager.create_backend()` is the official factory, constructing `GraphEmbedder`, `InMemoryEmbeddingBackend`, or `TurboVecEmbedder`. The MCP server's `get_mind()` also constructs `NeuralMind(abs_path)` directly, which is fine (it delegates to `BackendManager`). However, the `serve()` function in `server.py:589` does the same — each entrypoint relies on `NeuralMind.__init__` → `BackendManager`. There is no duplicated Praxis-like singleton pattern (good), but there is no unified "boot a mind" factory; three call sites all instantiate `NeuralMind(...)` directly.

### 4.3 `configline` advisory: `DEFAULT_CONFIG.api.api_key` reads env at import time
**LOW** `neuralmind/config.py:7-20`
```python
"api_key": os.environ.get("OPENROUTER_API_KEY"),
```
This reads the environment variable when the module is imported. Combined with `CONFIG = load_config()` at module line 44, the value is frozen for the lifetime of the process. Any process that calls `load_config()` late (e.g., after `os.environ["OPENROUTER_API_KEY"] = ...`) will have a stale value.

### 4.4 Global mutable caches (`_mind_cache`, `_security_cache`, `_SECURITY_MANAGERS`)
**LOW** `neuralmind/mcp_server.py:47-48` | `neuralmind/mcp_security.py:35`
Three module-level dicts hold warm instances. These are never cleared unless the MCP server process exits. Long-running MCP servers (the common case) will leak `NeuralMind` instances for every unique `project_path` they ever see — each holds an open embedding backend (ChromaDB/ONNX session).

## 5. Layer 5 — Testing Adequacy

### 5.1 Security unit tests exist but coverage is thin
**MEDIUM** `tests/test_mcp_security.py` (50 lines), `tests/test_integration_security_backend_audit.py` (89 lines)
- `test_mcp_security.py`: 4 tests covering RBAC allow/deny, rate limit sliding window, audit trail records success+denied. Does **not** test the MCP handler itself (`handle_tool_call`), only the security manager primitives.
- `test_integration_security_backend_audit.py`: 3 tests covering end-to-end backend switching, audit trail validation, and MCP RBAC enforcement. The last test (`test_end_to_end_mcp_security_enforcement`) **is** a real handler test — but only covers one allowed + one denied case.
- Missing: no test for the auth-bypass path in `handle_tool_call` (line 681-685 where `project_path` is falsy), no test for security config loading from `neuralmind-backend.yaml`, no test for the daemon handler's auth flow (`_authed()` in `daemon.py:480-488`).

### 5.2 Synapse layer lacks integration coverage
**MEDIUM** `tests/test_synapses.py`, `tests/test_synapse_*.py`
Multiple synapse test files exist (synapses, synapse_integration, synapse_memory, synapse_namespaces). Coverage is good for pure logic (edge cases, namespace merging, LTP floor, decay math) but weak on **concurrency**: no test that calls `reinforce()` on two threads with overlapping node sets and verifies the final weight equals the expected sum.

### 5.3 HTTP server auth tests are shallow
**MEDIUM** `tests/test_server.py:165-207`
Tests cover `/healthz` bypass and static paths. They do **not** test that `_check_auth` rejects a request with an expired/mismatched cookie, or that `_send_json` sets the cookie correctly on the first authenticated request. The test at line 144 disables auth (`auth_token = None`) so no auth-enabled request path is exercised in this file.

### 5.4 Embedder (GraphEmbedder) is only tested via mocks
**LOW** `tests/test_embedder.py` checks pure logic and OCI paths. `GraphEmbedder.embed_nodes()` is only exercised behind a ChromaDB mock (`mock_chromadb` fixture). No test runs the ONNX path.

### 5.5 Benchmark/eval scripts are not tested in the test suite
**LOW** `tests/test_public_benchmark.py` exists but only tests result parsing. `evals/swe_bench/runner.py`, `evals/quality/runner.py`, `evals/faithfulness/runner.py`, `evals/onboarding/runner.py*, `evals/parity/run.py` are entirely untested by the pytest suite — they run only in CI as separate pipeline steps.

## 6. Cross-cutting concerns

### 6.1 `mock.patch` used on `neuralmind.core.log_query_event` in test_core.py — defeats the integration under test
**LOW** `tests/test_core.py:261-264`
`test_query_logs_memory_event` patches the very function that it means to verify is called. This test passes trivially — it only proves `mock.patch` works, not that `query()` actually calls `log_query_event`. Similar trivial mocks appear in test_core.py around `_ensure_built` paths.

---

# Summary by Severity

| Severity | Count | Key Findings |
|----------|-------|-------------|
| HIGH | 0 | (no HIGH findings) |
| MEDIUM | 7 | Auth not enforced when `project_path` is falsy; token not retrievable after start; O(n²) pair writes; synapse layer has no concurrency tests; MCP handler has no auth-bypass test; server auth flow not tested; embedder only mock-tested |
| LOW | 7 | Frozen env var at import; global caches never cleared; `decay` holds large-table locks; `reinforce` transaction could be split by future refactor; no daemon auth-flow test; mock-only embedder tests; trivial mocks in test_core |
| NOTE | 2 | No pxpipe/LLM proxy (by design); no `@ts-nocheck` anti-pattern (Python repo) |

# Most urgent fix

**MEDIUM: auth bypass when `project_path` is absent.**
`neuralmind/mcp_server.py:680-685` runs any tool call without RBAC when `project_path` evaluates falsy today (empty string, `None`, or missing key). Every tool's `inputSchema` declares `project_path` as required, but JSON-schema validation is not enforced in `handle_tool_call` — that's the MCP framework's job. If a misconfigured client omits `project_path`, the handler silently skips `security.secure_call()` and runs the tool with no RBAC or rate limiting.

**Concrete fix**: reject the call when `project_path` is falsy:

```python
project_path_raw = arguments.get("project_path")
project_path = str(project_path_raw) if project_path_raw else None
if not project_path:
    return json.dumps({"error": "project_path is required", "code": "invalid_request"})
security = get_security_manager(project_path)
result = security.secure_call(actor, role, name, lambda: handlers[name](arguments))
return json.dumps(result, indent=2, default=str)
```

Remove the `else` branch entirely. This eliminates the silent bypass.
