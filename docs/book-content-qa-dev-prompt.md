# NeuralMind Engineering Refactor Prompt

**Status:** Approved for Development  
**Source Intelligence:** `/home/dtfrost/neuralmind/docs/market-research/intel.py`  
**Strategic Alignment:** Strategic Report (§6–7), 5-Year Financial Model (Year 1–2)  
**Target Audience:** Senior engineer or spec-driven AI coding agent  
**Scope:** Architecture decomposition, technical debt elimination, enterprise hardening, code quality gates.

> **Non-negotiable constraint:** Every change must preserve backward compatibility for OSS users during the transition. No big-bang rewrites. Each PR must be independently deployable.

---

## 1. Situational Summary

NeuralMind is a local-first, graph-based code intelligence platform. The core module (`neuralmind/core.py`) has grown to **1,811 lines** and the IR module (`neuralmind/ir.py`) to **963 lines**. Both exceed the maintainability threshold and create an unacceptable change surface for a codebase targeting enterprise SOC2 deployment within 18 months.

Current module inventory:
- `core.py` — 1,811 lines (god-object: graph construction, query execution, synapse learning, orchestration, audit, IR materialization)
- `ir.py` — 963 lines (versioning, adapter, validation, synapse bundles — mixed concerns)
- `server.py` — 648 lines (HTTP handlers, auth, SSE, file watching, editor launching)
- `graphgen.py` — 3,149 lines (tree-sitter graph backend — see note)
- `mcp_server.py` — 725 lines (MCP tool implementations, 725 lines but ~350 are tool stubs)

Test infrastructure: 75 test files covering 41 source modules. Current estimated coverage: <40% for core modules.

---

## 2. Architecture Decomposition

### 2.1 core.py → 4 focused modules

**File:** `neuralmind/core.py` (1,811 lines)

Decompose along the logical boundaries that already exist in the code:

| Module | Responsibility | Approximate content |
|--------|---------------|-------------------|
| `neuralmind/orchestration.py` | `NeuralMind` class — public API surface | `__init__`, `build`, `query`, `wakeup`, `search`, `skeleton`, `benchmark`, `retrieval_probe`, `export_context`, `get_stats`, `graph_data`, `switch_backend`, `close` |
| `neuralmind/synapse_manager.py` | Hebbian learning integration | `activate`, `activate_files`, `deactivate_files`, `record_edit_activity`, `_reinforce_from_query`, `synaptic_neighbors`, `_recall_for_selection`, `_recall_for_selection_detailed`, `_external_symbol_index`, `_REUSE_IDENT_RE`, `_NON_SYMBOL_FILE_TYPES` |
| `neuralmind/ir_materializer.py` | Canonical IR (PRD 1) lifecycle | `_materialize_ir`, `load_ir`, `validate`, `ir_path`, `ir_meta_path`, `validate_project` (module-level function) |
| `nebralmind/legacy.py` | Deprecated backward-compat shims | `GraphNotBuiltError`, `create_mind`, `_RECENT_QUERIES_APPEND_LOCK`, `_lock_byte0`, `_unlock_byte0` |

**Explicit interface contract:**

```python
# neuralmind/orchestration.py
class NeuralMind:
    def __init__(
        self,
        project_path: str,
        db_path: str | None = None,
        backend_type: str | None = None,
        hybrid_context: bool | None = None,
        enable_synapses: bool = True,
        memory_namespace: str | None = None,
    ): ...
    
    # The following MUST remain importable from neuralmind.core for backward compat:
    # from neuralmind.core import NeuralMind, create_mind, GraphNotBuiltError, validate_project
```

**Migration path:**
1. Create the 4 new modules; move functions/classes; re-export from `core.py` with `_deprecated` alias markers
2. Add `neuralmind/core.py` deprecation docstring pointing to new locations
3. All existing `from neuralmind.core import X` continues to work
4. Remove `core.py` entirely in Year 3 (v1.0 boundary)

**Dependencies to preserve:**
- `orchestration.py` imports from `synapse_manager`, `ir_materializer`, `legacy`, `context_selector`, `backend_manager`, `audit`, `memory`, `synapses`, `ir`, `namespaces`
- `synapse_manager.py` depends on: `synapses`, `embedder` (via self), `audit`
- `ir_materializer.py` depends on: `ir`, `synapses`, `audit`

### 2.2 ir.py → 3 focused modules

**File:** `neuralmind/ir.py` (963 lines)

| Module | Responsibility | Approximate content |
|--------|---------------|-------------------|
| `neuralmind/ir_model.py` | Canonical dataclasses + serialization | `IRNode`, `IREdge`, `IRCluster`, `IRSynapse`, `IndexIR`, `IR_VERSION`, `SUPPORTED_IR_VERSIONS`, `NODE_KINDS`, `EDGE_RELATIONS`, `COVERAGE_COARSE`, `COVERAGE_PRECISE`, `_SUFFIX_LANG`, `IRError` |
| `neuralmind/ir_adapter.py` | graphify ⇄ IR adapter + migration | `from_graph_json`, `to_graph_json`, `_derive_clusters`, `_coarse_file_type`, `migrate_payload`, `project_artifact`, `_line_from_location`, `_language_for`, `_looks_like_filename`, `_kind_for_node`, `_STD_NODE_KEYS`, `_STD_EDGE_KEYS` |
| `neuralmind/ir_synapses.py` | Synapse bundles + validation | `synapses_from_edges`, `load_synapses_for_project`, `export_synapse_bundle`, `validate_synapse_bundle`, `import_synapse_bundle`, `validate_ir`, `validation_summary`, `has_errors`, `ValidationIssue`, `SYNAPSE_BUNDLE_FORMAT`, `SYNAPSE_BUNDLE_VERSION`, `SYNAPSE_BUNDLE_KIND_TRANSITION` |

**Explicit interface contract:**

```python
# neuralmind/ir.py (re-exports for backward compat)
from neuralmind.ir_model import IRNode, IREdge, IRCluster, IRSynapse, IndexIR, IRError
from neuralmind.ir_model import IR_VERSION, SUPPORTED_IR_VERSIONS, NODE_KINDS, EDGE_RELATIONS
from neuralmind.ir_model import COVERAGE_COARSE, COVERAGE_PRECISE
from neuralmind.ir_adapter import from_graph_json, to_graph_json, migrate_payload, project_artifact
from neuralmind.ir_synapses import (
    synapses_from_edges, load_synapses_for_project,
    export_synapse_bundle, validate_synapse_bundle, import_synapse_bundle,
    validate_ir, validation_summary, has_errors, ValidationIssue,
    SYNAPSE_BUNDLE_FORMAT, SYNAPSE_BUNDLE_VERSION, SYNAPSE_BUNDLE_KIND_TRANSITION,
)
```

**Key constraint:** `ir_model.py` MUST remain stdlib-only — the docstring explicitly states "Stdlib-only on purpose." No tree-sitter, chromadb, or numpy dependencies.

### 2.3 graphgen.py — Note only

`graphgen.py` is 3,149 lines due to per-language extractors. This is **not** in scope for this refactor. Track as `TECH-DEBT-004` for a future language-plugin architecture (one module per grammar). Do NOT attempt to split during this phase.

---

## 3. Refactoring Priorities (P0–P2)

### P0 — Critical (Week 1, pre-OSS-launch gate)

#### 3.1 Eliminate regex-based source mutation

**Context from intel.py:** "Dangerous, unrecoverable source mutation" — risk of data-loss during experimentation.

**Current state audit:** No regex-experiment.py file exists in the working tree, but the pattern is documented as a known anti-pattern. The `_REUSE_IDENT_RE` in `core.py:363` is a regex pattern (`r"[A-Za-z_][A-Za-z0-9_]*"`) used for identifier extraction — this is acceptable and should remain. Verify any ad-hoc regex mutation patterns in the codebase are identified and eliminated before launch.

**Task:**
1. Search the entire codebase for `re.sub(`, `re.compile(...).sub`, or any regex applied to file-write operations
2. Replace any patterns found with `ast`-based transformation using Python's `ast` module (Python) or `tree-sitter` parse-edit for other languages
3. If no active regex-mutation code exists, create a test that asserts this invariant:
   ```python
   def test_no_regex_source_mutation():
       """Assert no regex pattern performs in-place file mutation."""
       # grep for re.sub calls touching files; fail if found
   ```

#### 3.2 Remove deprecated `enable_reranking` attribute

**Current state:** `enable_reranking` is a no-op parameter in `NeuralMind.__init__` (core.py:180–207). Still referenced in:
- `tests/test_core.py:50-61` — `test_init_accepts_deprecated_enable_reranking`
- `tests/test_ir.py` — not present
- `graphify-out/graph.json` — stale graph data (regenerate after rebuild)
- `docs/about.html`, `docs/wiki/Learning-Guide.md`, `README.md`, `RELEASE_NOTES`

**This is NOT a removal task.** The parameter exists for backward compatibility and is explicitly documented as a no-op. The correct action is:

**Task:**
1. Ensure `enable_reranking` remains in the signature and is stored as `self.enable_reranking` but has zero behavioral effect
2. Add a runtime `warnings.warn(..., DeprecationWarning, stacklevel=2)` when the caller explicitly passes `enable_reranking=` (detect via sentinel)
3. Update the test to assert the deprecation warning fires, not just that the kwarg is accepted
4. **Do not remove the parameter** — breaking the public API in Year 0 contradicts the OSS launch strategy

```python
# Recommended implementation in __init__:
import warnings
_ENABLE_RERANKING_SENTINEL = object()

def __init__(self, ..., enable_reranking=_ENABLE_RERANKING_SENTINEL, ...):
    if enable_reranking is not _ENABLE_RERANKING_SENTINEL:
        warnings.warn(
            "enable_reranking is deprecated and ignored. "
            "The learned_patterns reranker was removed in v0.25.0. "
            "The synapse layer supersedes it.",
            DeprecationWarning,
            stacklevel=2,
        )
    self.enable_reranking = bool(enable_reranking) if enable_reranking is not _ENABLE_RERANKING_SENTINEL else True
```

### P1 — High (Weeks 2–4)

#### 3.3 server.py decomposition

**Current state:** 648 lines mixing HTTP routing, auth, SSE streaming, editor launching, file watching.

**Target modules:**

| Module | Responsibility |
|--------|---------------|
| `neuralmind/server.py` | `serve()` entrypoint, `_Handler` class, HTTP routing |
| `neuralmind/server_sse.py` | SSE streaming (`_stream_events`, `_sse_send`, heartbeat logic) |
| `nebralmind/server_open.py` | Editor launching (`_editor_command`, `_compute_allowed_open_paths`, `_resolve_open_target`) |
| `neuralmind/server_bridge.py` | Event log bridge + activity watcher (`_start_event_log_bridge`, `_start_activity_watcher`) |

Preserve:
- Auth cookie flow (`_AUTH_COOKIE`, `_check_auth`, `_deny`)
- `/healthz` unauthenticated endpoint
- `allowed_open_paths` allowlist pattern (security-critical, do not weaken)
- Path traversal defense in `_resolve_open_target`

#### 3.4 MCP server stability hardening

**File:** `neuralmind/mcp_server.py` (725 lines)

**Current issues:**
- Module-level `_mind_cache: dict[str, NeuralMind] = {}` — unbounded growth, no TTL, no cleanup
- No graceful degradation when build fails mid-request
- Tool stubs (`tool_synapse_decay`, `tool_export_synapse_memory`) lack input validation

**Tasks:**
1. Add `_mind_cache` eviction: LRU with max 10 entries; evict on `MemoryError`
2. Wrap each tool handler in try/except with structured MCP error response (not 500)
3. Add request-level timeout for `tool_build` (default 120s, configurable)
4. Validate `signal` parameter in `tool_feedback` (only `"positive"` | `"negative"` allowed)
5. Add `/healthz` mirroring from `server.py` for MCP process monitoring

---

## 4. Enterprise-Ready Technical Improvements

**Financial context (from intel.py):** Year 2 targets 50 enterprise seats. SSO/RBAC and audit trail expansion are gate requirements for the first paid pilots.

### 4.1 SSO / RBAC Integration

**Current state:** `mcp_security.py` has a static `RBACPolicy` with hardcoded `DEFAULT_ROLE_POLICY`. No SSO integration exists. `server.py` uses a single shared token cookie — suitable for local-only dev, not multi-user enterprise.

**Target architecture:**

```python
# neuralmind/auth/sso.py (new module)
class SSOPolicy:
    """Pluggable SSO provider interface."""
    def authenticate(self, token: str) -> Identity: ...
    def resolve_role(self, identity: Identity) -> str: ...

class OIDCProvider(SSOPolicy):
    """OpenID Connect / OAuth2 PKCE flow."""

class SAMLProvider(SSOPolicy):
    """SAML 2.0 for enterprise IdP (Okta, Azure AD, etc.)."""
```

**Tasks:**
1. Create `neuralmind/auth/sso.py` with pluggable `SSOPolicy` ABC
2. Implement `OIDCProvider` (authorization code flow with PKCE) as default
3. Implement `SAMLProvider` stub (raise `NotImplementedError` with setup docs) — full SAML is Year 3
4. Replace `server.py:_check_auth` with `SSOPolicy` integration (single-user token still allowed via `--local-auth` flag)
5. Replace `mcp_security.py:DEFAULT_ROLE_POLICY` with config file loader (`neuralmind-rbac.yaml`)
6. Add `role` field to audit events (`AuditEvent.actor` already exists — extend with `role`)

**Backward compat:** `--local-auth` flag preserves current single-token localhost behavior for OSS users.

### 4.2 Audit Trail Expansion

**Current state:** `audit.py` already has `AuditTrail.append_event`, `read_events`, `nist_rmf_summary`. Categories: `audit`, `backend`, `security`. NIST RMF control rollups (AU, AC, SI) present.

**New event categories required for SOC2:**
- `auth` — SSO login/logout/failed-auth
- `rbac` — permission denied, role switch
- `data_export` — context export, synapse bundle export
- `admin` — backend switch, force-rebuild, config change

**Tasks:**
1. Add `actor_role: str = ""` and `ip_address: str = ""` fields to `AuditEvent`
2. Add `trail.search(category=..., action=..., since=..., until=...)` method for log querying
3. Add `trail.rotate(max_bytes=100MB, keep=90)` for log rotation (SOC2 requires 90-day retention)
4. Emit `auth` events on every MCP tool call (already have security category — extend)
5. Emit `data_export` event in `NeuralMind.export_context()` and `ir_synapses.export_synapse_bundle()`
6. Add GDPR-compliant `trail.redact_actor(actor_id)` method (replaces actor with one-way hash for right-to-be-forgotten)

### 4.3 On-Prem Deployment Hardening

**Current state:** `backend_manager.py` supports turbovec (default) and chroma backends. No deployment packaging exists beyond PyPI.

**Tasks:**
1. **Docker image:** Create `Dockerfile` with multi-stage build (builder + runtime), distroless base, non-root user
2. **Helm chart:** Create `deploy/neuralmind/` with:
   - Deployment (single-replica, for multi-replica add Redis-backed synapse store later)
   - PersistentVolumeClaim for `graphify-out/` and `.neuralmind/`
   - Secret for SSO/OIDC credentials
   - NetworkPolicy isolating pod egress (zero code egress = core value prop; enforce in K8s)
3. **Air-gap installer:** Shell script that bundles wheel + all tree-sitter grammars + offline embedding model
4. **Config encryption:** `neuralmind-backend.yaml` secrets (API keys, DB creds) encrypted at rest via `sops` or KMS
5. **Health endpoints:** Add `/readyz` (build complete) and `/livez` (process alive) for K8s probes

**Critical:** Air-gap installer MUST work without internet access. Tree-sitter grammar `.so` files must be pre-bundled.

### 4.4 Tree-Sitter Language Coverage

**Current state (from graphgen.py:74–92):** Python, TypeScript, Go, Rust, Java, C, C++, C#, Ruby, PHP, JSX, TSX, Markdown.

**Enterprise gaps (from competitor analysis):**
- Swift (iOS/macOS teams — Tabnine enterprise segment uses this)
- Kotlin (Android/JVM teams)
- Scala (data engineering)
- Protobuf/API schema (cross-language dependency detection)

**Priority order:**
1. **Kotlin** — first, largest enterprise gap, same JVM family as Java (likely easier grammar integration)
2. **Swift** — second, mobile teams are a distinct paid segment
3. **Scala** — third, data engineering overlaps with enterprise platform teams
4. **Protobuf** — fourth, schema-level edges (`defines_rpc`, `message_field`) require new `EDGE_RELATIONS` entries

**Tasks:**
1. Add grammar registration pattern identical to existing `_SUFFIX_LANG`/`_EXTRACTORS` dispatch
2. For each language, implement `_extract_symbols(tree, source) -> (nodes, edges)` with canonical node/edge model
3. Add parity test fixture under `tests/fixtures/sample_project_{language}/`
4. Update `ir_model.py:NODE_KINDS` if new entity kinds emerge (e.g., `rpc_method`, `message_field`)
5. Validate round-trip faithfulness eval passes for each language

### 4.5 MCP Server Stability (Extended)

**Current state:** `mcp_security.py` has `RateLimiter` (sliding window) and `RBACPolicy`. These are process-local — no cross-process consistency.

**Enterprise requirements:**
- **Session affinity:** MCP clients (Cursor, VS Code) maintain long-lived connections; `_mind_cache` must survive across requests but not indefinitely
- **Multi-project:** Single MCP server should serve multiple project paths (current `_mind_cache` is keyed by absolute path — this works, but needs eviction)
- **Graceful degradation:** When tree-sitter grammar is missing for a language, log warning and skip file rather than failing build

**Tasks:**
1. Replace `_mind_cache` simple dict with `cachetools.TTLCache(maxsize=10, ttl=3600)`
2. Add `--max-projects N` CLI flag (default 5) to bound memory
3. Add per-project build timeout (default 120s) with `concurrent.futures.TimeoutError` handling
4. Add circuit breaker: if 3 consecutive builds fail for a project, disable auto-build and return cached error response
5. Add `MCP_SCHEMAS` package with JSON Schema for each tool's input/output — enables runtime validation in Year 2

---

## 5. Code Quality Hardening

### 5.1 Type Coverage Targets

**Current state:** No type stubs (`.pyi`) exist. Partial inline typing (e.g., `from __future__ import annotations` in ir.py, server.py).

**Targets by module tier:**

| Tier | Modules | Target | Tool |
|------|---------|--------|------|
| Tier 1 (public API) | `orchestration.py`, `ir_model.py`, `ir_adapter.py` | 100% strict | `mypy --strict` |
| Tier 2 (internal core) | `synapse_manager.py`, `server.py`, `mcp_server.py`, `mcp_security.py` | 100% strict | `mypy --strict` |
| Tier 3 (supporting) | `audit.py`, `backend_manager.py`, `context_selector.py`, etc. | 90% | `mypy` |
| Tier 4 (legacy/growing) | `graphgen.py`, `watcher.py`, `hooks.py` | 70% | `mypy` (no strict) |

**Tasks:**
1. Add `pyproject.toml` `[tool.mypy]` section with `python_version = "3.12"`, `warn_return_any = true`
2. Add `# type: ignore` audit: CI fails on new `# type: ignore` comments without `[code: ...]` justification
3. Create `neuralmind/py.typed` PEP 561 marker file
4. Add `mypy` to CI pipeline with 0 new errors gate
5. Generate `.pyi` stubs for `orchestration.py` and `ir_model.py` (using `stubgen` as baseline, hand-curate)

### 5.2 Test Coverage Targets

**Current state:** 75 test files for 41 source modules. Core modules <40% coverage.

**Phase 1 targets (Weeks 2–4):**

| Module | Current (est.) | Target | Requirement |
|--------|---------------|--------|-------------|
| `core.py` | 35% | 70% | Characterization tests BEFORE decomposition |
| `ir.py` | 55% | 85% | Round-trip faithfulness already tested — extend |
| `server.py` | 25% | 60% | Auth, SSE, path traversal |
| `mcp_security.py` | 60% | 90% | Already decent — fill gaps |
| `mcp_server.py` | 20% | 60% | Tool handler contracts |
| `audit.py` | 40% | 80% | NIST RMF, rotation, search |
| `ir_materializer.py` (new) | — | 85% | IR validation paths |

**Tasks:**
1. Before ANY decomposition: write characterization tests capturing current behavior of `NeuralMind.build()`, `.query()`, `.wakeup()`, `.search()`
2. Add `coverage.py` with `[run]` source + `[report]` fail_under per module tier
3. Add `pytest-cov` to CI; PR fails if coverage decreases
4. Add property-based tests for `from_graph_json`/`to_graph_json` round-trip (use `hypothesis`)
5. Add integration test fixture: a 5-file Python project covering functions, classes, calls, imports, rationale

**Characterization test template:**

```python
def test_build_emits_audit_event(temp_project):
    """Characterization: build() always emits a backend/build audit event."""
    mind = NeuralMind(str(temp_project))
    mind.build()
    events = mind.audit.read_events()
    assert any(e["action"] == "build" for e in events)

def test_query_returns_context_result(temp_project):
    """Characterization: query() always returns a ContextResult with budget."""
    mind = NeuralMind(str(temp_project))
    result = mind.query("How does auth work?")
    assert hasattr(result, "context")
    assert hasattr(result, "budget")
    assert result.budget.total > 0
```

### 5.3 Debuggability

**Current state:** No structured logging. `print()` calls in `core.py:846`, `core.py:857`. Basic `trace=` flag on `query()`.

**Tasks:**
1. Replace all `print()` calls with `logging.getLogger(__name__).info/warning`
2. Add `logging.DEBUG` structured trace: every query emits a JSONL line with `{timestamp, question, layers_used, tokens, search_hits}` — this powers the "explainability" enterprise feature
3. Add OpenTelemetry trace spans for: `build`, `query`, `search`, `synapse_reinforce` — optional via `NEURALMIND_OTEL=1`
4. Add `neuralmind doctor` subcommand that validates: tree-sitter grammars importable, backend writable, disk space, config schema
5. Add crash dump: on unhandled exception, write `neuralmind-crash-{timestamp}.json` with stack trace + system info (no code PII)

---

## 6. Execution Principles

1. **Characterization tests first.** Never refactor a function without a test asserting current behavior.
2. **Backward compat layer.** Every public API change gets a shim in `core.py` / `ir.py` re-exports.
3. **No big-bang PRs.** Max 400 lines changed per PR; each independently mergeable and deployable.
4. **Security-critical paths frozen.** `server.py:_resolve_open_target`, `mcp_security.py:secure_call` — don't refactor, only test and harden.
5. **OSS user is sacred.** Every change must be no-op default for `pip install neuralmind && neuralmind build`.
6. **Enterprise pluggable.** SSO/RBAC/type-checking/OTEL all opt-in via environment variables or config — zero impact on existing users.

---

## 7. PR Sequence (Suggested)

| PR | Scope | Est. Lines | Depends On |
|----|-------|-----------|------------|
| 1 | Characterization tests for `core.py` | +200 | — |
| 2 | Characterization tests for `ir.py` | +150 | — |
| 3 | Add `warnings.warn` for `enable_reranking` | +15 | — |
| 4 | Regex-mutation test + elimination | +30 | — |
| 5 | Split `ir.py` → `ir_model`, `ir_adapter`, `ir_synapses` | ±200 | PR 2 |
| 6 | Split `core.py` → `orchestration`, `synapse_manager`, `ir_materializer`, `legacy` | ±400 | PR 1 |
| 7 | `server.py` decomposition | ±200 | — |
| 8 | MCP server hardening (TTLCache, timeouts) | ±100 | — |
| 9 | SSO/RBAC integration layer | ±300 | — |
| 10 | Audit trail expansion (auth/rbac/admin events, rotation) | ±150 | — |
| 11 | Type coverage (mypy strict for Tier 1) | ±50 | PR 5, PR 6 |
| 12 | Docker + Helm chart | ±200 | — |
| 13 | Tree-sitter Kotlin + Swift | ±400 each | — |

---

## 8. Success Criteria

- [ ] `core.py` no longer exists (all consumers import from `orchestration`, `synapse_manager`, etc.)
- [ ] `ir.py` is a re-export shim only; logic lives in `ir_model`, `ir_adapter`, `ir_synapses`
- [ ] `mypy --strict` passes for Tier 1 modules with 0 errors
- [ ] Test coverage: Tier 1 ≥ 85%, Tier 2 ≥ 70%, overall ≥ 60%
- [ ] `enable_reranking` emits `DeprecationWarning` when explicitly passed
- [ ] No `re.sub` patterns perform file-write operations
- [ ] MCP server survives 1000 consecutive tool calls without OOM (TTLCache eviction works)
- [ ] SSO flow documented with OIDC example (Google/Okta)
- [ ] Docker image builds air-gapped; image size <500MB
- [ ] `neuralmind doctor` passes on fresh Ubuntu 22.04 + Python 3.12 install

---

## 9. Out of Scope (Tracked Separately)

- `TECH-DEBT-004` — `graphgen.py` module-per-grammar decomposition (~3149 lines)
- `TECH-DEBT-005` — synapse store backend migration from SQLite to Redis (multi-user Year 3)
- `TECH-DEBT-006` — LSP/SCIP precise-backend integration (currently stubbed in `ir_model.py`)
- `FEATURE-001` — Web UI React migration (currently vanilla JS in `web/`)
- `FEATURE-002` — Team memory merge conflict resolution (Year 3 multi-user)

---

## 10. Reference: Financial Model Alignment

From `intel.py:FINANCIAL`, the 5-year trajectory:

| Year | Phase | Engineering Focus |
|------|-------|------------------|
| Y1 (now) | OSS launch | **This refactor** — stabilize, decompose, type coverage |
| Y2 | First enterprise pilots (50 seats) | **SSO/RBAC + audit trail** — PRs 9–10 |
| Y3 | Enterprise tier launch (250 users) | **SOC2 + Redis synapse + LSP** — TECH-DEBT-005/006 |
| Y4 | Multi-region + partnerships (750 users) | **Helm chart hardening + team memory** — PR 12 |
| Y5 | Category leadership ($2.4M ARR) | Scale + strategic options |

**Critical path:** PRs 1–8 must land before Year 2 pilot onboarding begins. SSO/RBAC (PR 9) is the revenue gate for first paid invoices.
