# PR 1: the `/v1` daemon API

**Spec:** [`LOCAL-API-SPEC.md`](LOCAL-API-SPEC.md). Section numbers (§) below refer to it.
**Baseline:** v4.3.5 (`main` @ `39617aa`)
**Suggested PR title:** `feat(daemon): versioned /v1 local API with project registry, decision-memory endpoints and Python client`
**Release effect:** `feat:` makes release-please open a minor release. Don't bump versions by hand.
**Estimate:** about 2.5–3.5 engineer-days. The expected size is about 1,200–1,600 changed lines, not counting docs and the OpenAPI snapshot.
**Cut line:** if the PR grows well past that, move `PATCH`, `restore` and `DELETE` for memories into a follow-up "PR 1b". Keep create, list, search, get and invalidate in PR 1, because they are the mem0-parity core.

---

## 1. Goal

When PR 1 lands, a developer can run:

```bash
neuralmind daemon start
python - <<'EOF'
from neuralmind.client import NeuralMindClient
repo = NeuralMindClient().project(".")
repo.build(wait=True)
print(repo.query("how does synapse decay work?").context[:400])
repo.memories.add(title="Use SQLite WAL for synapses",
                  rationale="Concurrent writers: hooks, watcher, MCP.",
                  files=["neuralmind/synapses.py"])
print([m.title for m in repo.memories.search("sqlite")])
EOF
```

They can also drive the same calls with `curl` against a documented, versioned contract whose OpenAPI document is generated from code. Every existing CLI, MCP and legacy-daemon behaviour stays the same, with one deliberate exception: a daemon can no longer bind a non-loopback address. That is a security fix (§1.1 A3).

---

## 2. In scope

### 2.1 New package: `neuralmind/api_v1/`

| Module | Contents |
|---|---|
| `__init__.py` | `API_VERSION = "1"` and the public exports |
| `routing.py` | A `Route` dataclass with `method`, `template` (`/v1/projects/{project_id}/memories/{memory_id}`), `handler`, `request_model`, `response_model`, `permission` (the name a later PR's RBAC will use), `summary`, `auth=True`, `status=200`. Also `ROUTES: list[Route]`, a matcher that compiles templates to regexes, and `dispatch_v1(ctx, method, raw_path, headers, body_bytes) -> (status, headers, payload)`. A path that matches but has the wrong method returns 405 with an `Allow` header. |
| `errors.py` | An `ApiError(status, code, message, details=None)` exception, the code constants from §5.1, and `envelope(err, request_id)`. Pydantic `ValidationError` maps to 422 `validation_error`. Unexpected exceptions map to 500 `internal_error`; in loopback mode `details.exception` is `Type: message`. |
| `models.py` | Pydantic v2 request and response models for every PR 1 route, all with `model_config = ConfigDict(extra="ignore")`. Limits: `question` and `query` 1–8,000 characters; `n` 1–100; memory search `limit` 1–25; list `limit` 1–200. `decision_type` and `status` are `Literal` types matching `memory/store.py`. |
| `projects.py` | `ProjectDirectory`: derives ids (`"p_" + sha256(realpath)[:12]`); validates paths (must be a directory; resolved with `realpath`; reserved-path denylist from §6.1, **re-implemented here, not imported from `neuralmind/tier2/`**); persists to `<daemon home>/projects.json` (file 0600, directory 0700, written via temp file + `os.replace`, honours `NEURALMIND_DAEMON_HOME`); loads lazily on start, skipping paths that no longer exist. |
| `shapes.py` | Shared normalisers. `search_hit(raw) -> {id, label, file_type, source_file, score}`, moved out of `mcp_server.tool_search` (`mcp_server.py:153-169`). `compact_memory_row(rec)`, moved out of `memory/mcp_tools.py:176` (keep a re-export there so existing imports still work). `memory_record(rec) -> dict` serialises `DecisionRecord` with ISO-8601 UTC times. `job(j) -> dict` converts epoch floats to ISO strings. |
| `handlers/meta.py` | `GET /v1`, `GET /v1/health`, `GET /v1/status`, `GET /v1/openapi.json`, `POST /v1/admin/shutdown` |
| `handlers/projects.py` | `GET /v1/projects`, `POST /v1/projects`, `GET /v1/projects/{id}` |
| `handlers/index.py` | `build`, `query`, `search`, `wakeup`, `stats`, `savings`, `validate`. These call `ctx.registry` under `lock_for(...)` exactly as today's `_query`/`_search`/`_stats`/`_build` do (`daemon.py:427-488`). `query` passes `query_type` and `context_budget` through to `NeuralMind.query`. |
| `handlers/memories.py` | Create, list, search, get, patch, invalidate, restore, delete, all on `DecisionStore(project_root)`, with **no project RLock** (§5.4). Follow the create, invalidate and restore rules in §5.3 exactly: commit defaults to HEAD; files normalised to project-relative paths; strict 422s; read-back after write; existence checked before invalidate. |
| `handlers/jobs.py` | `GET /v1/jobs`, `GET /v1/jobs/{jid}` |
| `openapi.py` | `build_openapi() -> dict` assembles an OpenAPI 3.1 document from `ROUTES` and each model's `model_json_schema()` (components, bearer security scheme, the error envelope as a shared response). `python -m neuralmind.api_v1.openapi --write docs/api/openapi-v1.json` regenerates the committed snapshot. **No new CLI subcommand**, which keeps `tests/test_docs_cli_paths.py` simple. |

**Routes in PR 1** (§5.2): `GET /v1`, `GET /v1/health`, `GET /v1/status`, `GET /v1/openapi.json`, `POST /v1/admin/shutdown`, the three project routes, the seven index routes, the eight memory routes, and the two job routes.

### 2.2 Changes to `neuralmind/daemon.py`

**`_Handler`:**
- Add `do_PATCH` and `do_DELETE`.
- **Read the body once, with a cap.** Cap at `NEURALMIND_API_MAX_BODY_BYTES` (default 1 MiB) and return 413 above it. The cap applies to legacy routes too.
- **Check the Host header** before anything else, on all routes: allowed values are `127.0.0.1`, `localhost` and `[::1]`, any port. Anything else gets 403 `host_not_allowed`.
- **Route by prefix:**
  - A path starting with `/v1` goes to `api_v1.routing.dispatch_v1` and uses header-only auth. A `?token=` is ignored, so the request gets 401.
  - Everything else goes to the existing `dispatch()`, unchanged: same shapes, same `?token=` support, no deprecation headers yet.
- **Send the v1 response headers** (`NeuralMind-API-Version`, `X-Request-Id`, `Location` where applicable). Send no body on 204.

**`DaemonContext`:** gains `projects: ProjectDirectory` and `mode: str = "loopback"`.

**`create_server()` and `main()`:** refuse a non-loopback `host` with `ValueError`, and `main()` turns that into exit code 2 with the message: `"neuralmind daemon binds loopback only; remote access arrives with server mode (see docs/specs/LOCAL-API-SPEC.md §6.2)"`. Allowed hosts are `127.0.0.0/8`, `::1` and `localhost`.

**Leave alone:**
- The registry's `_key` stays `os.path.abspath`. Its comment explains a deliberate static-analysis constraint (`daemon.py:166-172`).
- v1 passes the already-validated realpath. Known edge case: the same project reached through a symlink by legacy routes and via v1 can warm two instances. Note it in the PR; don't fix it here.

### 2.3 Changes to `neuralmind/cli.py`

`cmd_daemon` validates `--host` before spawning, so the user sees the loopback-only error directly rather than "failed to start (see ~/.neuralmind/daemon.log)". No new subcommands. The CLI keeps using the legacy routes through `daemon_client` in PR 1; it moves to `/v1` in PR 2.

### 2.4 New Python client: `neuralmind/client.py`

As described in §7.1:
- `NeuralMindClient(base_url=None, token=None, *, timeout=30.0)`. With no arguments it uses `NEURALMIND_API_URL` / `NEURALMIND_API_TOKEN`, then the discovery file.
- `.project(path_or_id)` returns a `ProjectClient`. It accepts a path (it `POST`s `/v1/projects` and caches the id) or an id.
- `ProjectClient` methods: `.build(force=False, wait=False)`, `.query(question, *, query_type="auto", context_budget=None, trace=False)`, `.search(query, n=10)`, `.wakeup()`, `.stats()`, `.savings(...)`.
- `ProjectClient.memories` methods: `.add(title, rationale, *, files=None, commit_sha=None, decision_type="ARCHITECTURE", confidence=1.0, evidence=None, rejected=None, tags=None, id=None)`, `.list(status="ACTIVE", files=None, limit=50)` (follows cursors), `.search(query, limit=10, status="ACTIVE")`, `.get(id)`, `.update(id, **fields)`, `.invalidate(id, reason)`, `.restore(id, commit_sha=None)`, `.delete(id)`.
- `NeuralMindClient` also has `.jobs.get(id)` and `.jobs.wait(id, timeout=600)`.
- Return types are frozen dataclasses with `.raw`.
- Errors are `NeuralMindAPIError` and its subclasses.
- **Stdlib only.** Importing `neuralmind.client` must not import `neuralmind.core`, onnxruntime, chromadb, turbovec or pydantic. A test enforces this, because the client should stay cheap for scripts.
- Existing `neuralmind/daemon_client.py` is untouched.

### 2.5 Small refactors

- `mcp_server.tool_search` uses `api_v1.shapes.search_hit`. Behaviour must not change; existing MCP tests cover it.
- `memory/mcp_tools._compact_row` delegates to `api_v1.shapes.compact_memory_row`.

### 2.6 OpenAPI snapshot

- `docs/api/openapi-v1.json` is committed and regenerated with the `python -m` command above.
- It is served at `/v1/openapi.json`, built in memory from code; nothing reads the snapshot file at runtime, so no packaging change is needed.

---

## 3. Tests

All new tests follow `tests/test_daemon.py`: a `FakeMind` injected through `ProjectRegistry(mind_factory=…)`, a real `ThreadingHTTPServer` on port 0 in a thread, and `NEURALMIND_DAEMON_HOME` pointed at `tmp_path`. Memory tests use a real `DecisionStore` in `tmp_path`, which needs only SQLite and pydantic.

| File | Asserts |
|---|---|
| `tests/test_api_v1_routing.py` | Template matching, 404 for unknown routes, 405 with `Allow`, 415 without JSON content type, 413 over the cap, 422 envelope shape, header-only auth (`?token=` gives 401 on `/v1` but still works on legacy routes), Host check gives 403, `X-Request-Id` echoed and generated, 500 envelope (with `details.exception` in loopback mode) |
| `tests/test_api_v1_projects.py` | Deterministic ids; idempotent register (201, then 200); the denylist (`/`, `/etc`, `$HOME`, `~/.ssh`) and non-directories rejected with 422; persistence across a server restart; `GET` on an unknown id gives `project_not_found` |
| `tests/test_api_v1_index.py` | Build returns 202 then the job completes, and `wait=true` returns 200; query maps the `TokenBudget` fields to `tokens.l0..l3`; `query_type` and `context_budget` reach `FakeMind.query`; search returns the MCP hit shape; wakeup, stats, savings and validate are reachable; per-project lock reuse (two concurrent queries on a cold project build once) |
| `tests/test_api_v1_memories.py` | Create: 201 with `Location`; HEAD default for `commit_sha` in a temp git repo and `""` outside one; path normalisation; a path outside the project gives 422; a bad `decision_type` gives 422; a duplicate `id` gives 409; a simulated store failure on read-back gives 500. List with status filters and `file=` filters, plus cursor paging. Search (`ALL` really returns every status; compact view). Get, patch, invalidate (unknown id gives 404), restore (unknown id gives 404), delete (204, then 404). |
| `tests/test_api_v1_openapi.py` | The generated document equals the committed snapshot; every `Route` appears, and every OpenAPI path maps back to a `Route`; every route has a response model; the structure is OpenAPI 3.1 (`openapi`, `info`, `paths`, `components.securitySchemes`). No new validator dependency. |
| `tests/test_client.py` | End-to-end through `NeuralMindClient` against a running test daemon; error subclasses map from status and code; `NEURALMIND_API_URL` / `NEURALMIND_API_TOKEN` override discovery; **lightweight import**: in a subprocess, `import neuralmind.client`, then assert `neuralmind.core`, `onnxruntime`, `chromadb`, `turbovec` and `pydantic` are absent from `sys.modules` |
| `tests/test_daemon_bind_guard.py` | `create_server(host="0.0.0.0")` raises; `main(["--host", "0.0.0.0"])` exits 2; `127.0.0.1`, `::1` and `localhost` are accepted |
| `tests/test_api_v1_license_boundary.py` | No module under `neuralmind/api_v1/`, and not `neuralmind/client.py`, imports `neuralmind.tier2` (checked by AST scan) |

Existing suites must pass **unchanged**, especially `tests/test_daemon.py` (the legacy contract), `tests/test_mcp_server.py`, `tests/test_memory*.py`, `tests/test_docs_claims.py`, `tests/test_docs_cli_paths.py` and `tests/test_site_claims.py`.

---

## 4. Documentation (same PR, per `CLAUDE.md` "Shipping a feature")

Find the release version from `.release-please-manifest.json` (next minor), or from the open release-please PR if one exists. Hard-code it only in the release-notes filename and the banners that already carry versions.

**Release notes:** `docs/releases/RELEASE_NOTES_v<X.Y.Z>.md`.
- Angle: "what the agent and developer actually see after installing."
- Include a per-agent expectations table:

| Agent | What changes |
|---|---|
| Claude Code, Cursor, Cline, generic MCP | Nothing changes by default; MCP stdio is untouched |
| Scripts, CI and non-MCP agents | Can now call `/v1` or use the Python client |

- Call out the loopback-only bind change.

**`README.md`:**
- Bump the top banner and demote the previous release into the history trail.
- Add a short "NeuralMind API (self-hosted)" section with the Python snippet and one `curl` example.
- Add the release-notes row.

**`docs/index.html`:** banner and earlier-releases trail; `<meta name="description">` and `keywords` gain "local REST API" and "OpenAPI".

**`docs/about.html`:** a new "What's New in v<X.Y.Z>" section above the previous one.

**`docs/wiki/CLI-Reference.md`:**
- The `daemon` section (`:2287-2338`) gains the loopback-only rule and a link to the new HTTP API page.
- The environment-variables table (around `:2926`) gains `NEURALMIND_API_URL`, `NEURALMIND_API_TOKEN` and `NEURALMIND_API_MAX_BODY_BYTES`.

**New `docs/wiki/HTTP-API.md`:**
- Conventions, auth, the error envelope and code table, every PR 1 route with a `curl` example, the Python client, and the mem0 → NeuralMind cheat sheet (§4).
- Link it from `docs/wiki/Home.md` (the table near `:317`) and from `docs/wiki/API-Reference.md`.

**New `docs/use-cases/local-http-api.md`:** "Give any script, CI job or non-MCP agent NeuralMind context and decision memory over HTTP." Cover:
- the existing use case it improves: scripting against `neuralmind query` output;
- the new one it unlocks: recording decisions from CI, and non-MCP agents.

Mention only what PR 1 ships. Server mode, Docker and `/activity` are not shipped yet, so leave them out.

**`docs/comparisons/vs-mem0-zep.md`:** update the "Storage … no server, no hosted platform option" bullet and the Distribution row to say there is now an optional local HTTP API (loopback) and still no hosted platform.

**`pyproject.toml` keywords:** add `local-rest-api`, `openapi`, `agent-memory-api`.

**`docs/sitemap.xml`:** add the release notes, the use case and `wiki/HTTP-API.html`.

**`docs/llms.txt`:** one line pointing at the HTTP API page.

**Claims discipline:**
- No latency or throughput numbers. Nothing measures them yet, and `site/claims.json` lists query latency as `unsourced_do_not_use`. Speak about mechanism, for example "the daemon keeps the index warm between calls."
- No absolute privacy phrasing. Use "sends no telemetry and transmits no repository content off your machine."
- Run the guards listed in §6.

**Don't** edit `CHANGELOG.md` or bump versions by hand.

---

## 5. Explicitly out of scope (later PRs, see §10)

- Server mode: `--allow-remote`, project allowlist, tokens file, roles, TLS, rate limiting, audit (PR 2)
- Routes for associations, `activity`, `feedback`, `documents` and `timeline` (PR 2)
- Moving the CLI to `/v1`, and legacy `Deprecation` headers (PR 2)
- `/v1/events`, dashboard consolidation, Docker and compose fixes (PR 3)
- MCP Streamable HTTP (PR 4)
- TypeScript client (PR 5)
- Auto-spawn, idle TTL, moving the daemon port off 8787, and `/_internal/hook/*` (performance plan, WP 2.4)
- The side findings in §12. File them as separate fixes.

---

## 6. Acceptance criteria

1. `pytest tests/ -q` passes, with existing tests unmodified.
2. `ruff check .` and `black --check .` are clean.
3. `python scripts/check_commercial_terms.py` passes, as do `tests/test_docs_claims.py`, `tests/test_docs_cli_paths.py` and `tests/test_site_claims.py`.
4. `docs/api/openapi-v1.json` matches what `build_openapi()` generates.
5. A manual end-to-end run against this repository works, and its trimmed transcript is pasted into the PR body:
   - start the daemon;
   - register `.`;
   - build with `wait=true`;
   - query and search;
   - add a memory, search for it, invalidate it, and list with `status=ALL`;
   - shut down.

   Do it with the Python client and with `curl`.
6. `neuralmind daemon start --host 0.0.0.0` fails fast with the loopback-only message.
7. `import neuralmind.client` stays lightweight (test above).
8. Nothing in `neuralmind/api_v1/` or `neuralmind/client.py` imports `neuralmind/tier2/`.
9. The docs checklist in §4 is complete, and the PR template's "Documentation & discoverability" boxes are ticked honestly.

---

## 7. Risks

| Risk | Mitigation |
|---|---|
| The first `query` on a cold project builds synchronously and can exceed a client timeout | The client gives `query` a 120 s timeout and documents calling `build(wait=True)` first. 409 `index_not_built` is reserved for perf WP 2.2. |
| The perf plan's Phase 2 rewrites parts of `daemon.py` at the same time | PR 1 confines its daemon changes to `_Handler` routing, the body cap, the Host check and the bind guard. The route table keeps the rebase mechanical. Check `git log origin/main -- neuralmind/daemon.py` before starting. |
| The bind guard breaks someone running the daemon on `0.0.0.0` | No shipped template runs the daemon: compose runs nothing (§1.1 A7), and the systemd/launchd templates run `serve`. The release notes call it out, and server mode in PR 2 is the supported path. |
| `DecisionStore` writes fail silently | Read-back after create returns 500 instead of a phantom 201. |
| pydantic in the request path slows imports | `api_v1` is imported only inside the daemon process, never by the client or the hooks. |
