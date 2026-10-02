# NeuralMind Local API (`/v1`) — Technical Spec

**Status:** DRAFT for review
**Date:** 2026-10-02
**Baseline:** v4.3.5 (`main` @ `39617aa`). Every `file:line` below was checked against that commit.
**Companions:**
- [`LOCAL-API-PR1-SCOPE.md`](LOCAL-API-PR1-SCOPE.md): the first PR, scoped to files, routes, tests and docs.
- [`LOCAL-API-PR1-SESSION-PROMPT.md`](LOCAL-API-PR1-SESSION-PROMPT.md): a ready-to-paste prompt for the session that implements PR 1.

**Related:** [`PERFORMANCE-FUTURE-PROOFING-SPEC.md`](PERFORMANCE-FUTURE-PROOFING-SPEC.md) §5 and [`PERFORMANCE-FUTURE-PROOFING-PLAN.md`](PERFORMANCE-FUTURE-PROOFING-PLAN.md) Phase 2. They cover the same daemon from the latency side. §9 lists where the two programmes touch.

> **Scope note.** `CLAUDE.md` routes BRD/TRD strategy documents to the private
> `neuralmind-marketing` repo. This is an engineering spec that cites
> `file:line` in this repo, like the performance spec next to it, so it lives
> in `docs/specs/`. Move it if you prefer.

---

## 0. Summary

**The question:** should NeuralMind offer an API "like mem0, that is free"?

**The answer this spec implements:** copy mem0's developer experience, but not its hosting model. Concretely:
- One documented, versioned HTTP contract (`/v1`).
- It is served by the process users already run: the daemon.
- A stdlib Python client with mem0-shaped verbs.
- A Docker image a team runs on its own infrastructure.

Cheval-Volant LLC hosts nothing. The README's statement that NeuralMind "transmits no repository content off your machine" (`README.md:67`) stays true by construction:
- The default bind is loopback.
- Binding to other interfaces is a separate, opt-in *server mode*.
- In server mode, projects are allowlisted and every caller authenticates with a per-user token.

**Why not a hosted API.** This was assessed in the conversation that produced this spec; the reasons are recorded here so they aren't re-litigated:
1. **Positioning.** "Local-first, no telemetry" is the headline (`README.md:10,16,67`), and "Hosted SaaS" is an explicit non-goal (`ROADMAP.md:212`).
2. **Unit cost.** The free tier costs Cheval-Volant nothing per user today (`commercial-terms.json` → `pricing.free`). A hosted free tier would mean per-repository index compute and storage, plus custody of customers' source code.
3. **The hot path is local.** Hooks run on every tool call and the watcher reads the working tree. A remote API adds a network hop to that path and still needs a local install.
4. **Pricing model.** NeuralMind prices seats ($29/user/mo Team); a mem0-style API prices operations. A hosted API is also, in practice, the "real-time cross-machine sync" that `commercial-terms.json` → `do_not_market` says not to market.

**What mem0 ships**, for parity reference:

| mem0 surface | What it is |
|---|---|
| Hosted Platform (`api.mem0.ai`, `/v1/` prefix) | Free Hobby tier (10K memory adds and 1K retrievals per month). Paid tiers are gated by operation quotas, not seats. |
| OSS REST server | `POST /memories`, `POST /search`, CRUD by id, interactive OpenAPI at `/docs`, auth on by default (per-user `X-API-Key`). |
| OSS Docker stack | API server + Postgres/pgvector + Neo4j |
| SDK verbs | `add`, `search`, `get_all`, `get`, `update`, `delete`, `history` |

**What NeuralMind takes from mem0:** the verbs, one documented contract, a generated OpenAPI document, auth on by default, and a one-command Docker server.

**What it leaves out:**
- An LLM in the write path.
- External databases; the stores stay in SQLite under `.neuralmind/`.
- A hosted tier.

---

## 1. What exists today

| Surface | Where | Bind / port | Auth | Contract | State |
|---|---|---|---|---|---|
| Daemon | `neuralmind/daemon.py` (dispatch `:338-403`, HTTP `:496-546`) | `127.0.0.1:8787` by default, but `--host` accepts anything (`daemon.py:652`, `cli.py:6798`) | Bearer token, or `?token=` (`:508-516`), from `~/.neuralmind/daemon.json` (mode 0600, `:67-85`) | Unversioned `/health /status /jobs /jobs/{id} /stats /savings /query /search /build /validate /shutdown`; the project is a raw filesystem path in the body or query string | Documented as "experimental" (`docs/wiki/CLI-Reference.md:2287`). The CLI uses it for `query` and `stats` only (`cli.py:734-747, 1048-1087, 1865-1881`). |
| Graph UI server | `neuralmind/server.py` | `8787` by default (`server.py:720`), which collides with the daemon | `?token=` exchanged for a cookie; `/healthz` is open (`:225-305, 321`) | `/api/graph`, `/api/search`, `/api/events` (SSE), `/api/dashboard/*` | Dashboard-shaped, not a public contract |
| MCP over HTTP | `neuralmind/mcp_http.py` | `uvicorn` on `127.0.0.1:8765`, hard-coded (`mcp_server.py:1409`) | None | `/mcp` returns a fixed JSON reply (`mcp_http.py:93-130`) | Skeleton: no JSON-RPC, no OAuth |
| Self-hosted config | `neuralmind/tier2/self_hosted.py:21-26`, `neuralmind/tier2/config.py:64-80` | `bind_address`, `port=8765` | — | — | Config with **no consumer**: nothing reads `port` or `bind_address` |
| MCP stdio | `neuralmind/mcp_server.py` | stdio | RBAC role is taken from the tool arguments the client sends (`:1321-1322`) | 28 tools | Production |
| Python API | `neuralmind.core.NeuralMind` | in-process | — | `docs/wiki/API-Reference.md` | Production |
| Decision memory | `neuralmind/memory/store.py` `DecisionStore` → `.neuralmind/memory.db` | — | — | `neuralmind decisions …` (`cli.py:2766-2935`) and 7 MCP tools (`memory/mcp_tools.py:329-548`) | Production |

### 1.1 Problems this spec fixes

**A1. There is no versioned public contract, and every surface returns a different search shape:**
- Daemon `/search` returns raw backend hits: `{id, document, metadata, distance, score}`.
- MCP `neuralmind_search` returns `{id, label, file_type, source_file, score}` (`mcp_server.py:153-169`).
- The UI's `/api/search` returns `{id, label, source_file, community, score}` (`server.py:75-94`).

**A2. Projects are addressed by any filesystem path the request supplies** (`daemon.py:363-394`):
- No allowlist of project roots exists anywhere. `core.validate_project` and `paths.py` only keep *artifact* subpaths inside the root they are given.
- As a result, `POST /validate {"write": true}` writes `.neuralmind/` files into any directory the daemon user can write (`core.py:76-126`).

**A3. The network posture is unguarded:**
- `--host` accepts any address, so the result is plaintext HTTP and indexing of whatever path the request names, protected only by the token.
- There is no Host-header check.
- There is no request-body cap (`daemon.py:532-535`).
- The token is accepted in the URL query string (`daemon.py:515`), which leaks into logs and shell history.

**A4. Errors have no code.** Every error is `{"error": "<text>"}`, and a 500 returns the exception's class and message (`daemon.py:402-403`).

**A5. Nothing can be written over HTTP.** Decisions, feedback, file activity and document ingest are reachable only through MCP or the CLI.

**A6. Ports collide:**
- The daemon and `serve` both default to 8787 (perf spec finding H5).
- 8765 is claimed by four things: the systemd/launchd `serve` templates (`scripts/systemd/neuralmind-serve.service`, `scripts/launchd/com.neuralmind.serve.plist`), `scripts/install-team.sh:47`, the MCP-over-HTTP stub, and `SelfHostedConfig`.

**A7. Docker does not run a server:**
- `docker-compose.yml` has no `command:`, and the image `CMD` is `neuralmind --help` (`Dockerfile:66-67`), so the container exits and `restart: unless-stopped` restarts it in a loop.
- The license is mounted at `/app/license.json`, but `NEURALMIND_LICENSE_PATH` is never set, so the default path doesn't find it.
- The Dockerfile has no `HEALTHCHECK` and no `VOLUME`.

**A8. MCP RBAC is self-asserted:**
- The caller supplies `actor` and `role` (`mcp_server.py:1321-1322`).
- The config-driven `mcp_security.get_security_manager` is never called; `mcp_server.py:76-81` builds a manager with default settings instead.
- Over stdio this is harmless, because the caller is the local user. Over any network transport it would make the RBAC meaningless.

**A9. The HTTP contract has no documentation.** `CLI-Reference.md:2287-2338` documents the `daemon` command, not what it serves.

---

## 2. Goals and non-goals

**Goals**

| Id | Goal |
|---|---|
| G1 | One versioned contract, `/v1`, with an OpenAPI 3.1 document **generated from the route table** so the two cannot drift. |
| G2 | mem0-grade developer experience: `pip install neuralmind`, then `NeuralMindClient().project(".").memories.add(...)`, with no extra service to set up locally. |
| G3 | The same contract for every client: CLI, Python client, MCP over HTTP, dashboard, scripts, other agents, CI. |
| G4 | Teams can self-host: one Docker command runs the API (and, later, the UI and MCP) on the team's own infrastructure. |
| G5 | Privacy posture unchanged: loopback by default; remote access opt-in, allowlisted, and authenticated per user. |
| G6 | Stdlib transport and stdlib client, so PR 1 to PR 3 add no new runtime dependencies. |

**Non-goals**

| Id | Non-goal |
|---|---|
| N1 | A hosted service. `ROADMAP.md:212` stands. |
| N2 | LLM extraction on write. Memories are explicit records, as today; `neuralmind decisions record` already works this way. |
| N3 | Cross-machine sync or replication (`do_not_market`). A team server is *one shared server*, not sync. |
| N4 | SSO/SAML (`do_not_market`, roadmap only). |
| N5 | Replacing MCP stdio. It stays the default integration for agent hosts. |
| N6 | Guidance for exposing the server on the public internet. The docs say "put it behind your reverse proxy or VPN" and stop there. |

---

## 3. Design principles

**P1. One dispatch core, many transports.** This is already the stated intent of the daemon (`daemon.py:338-344`, PRD 5 FR3). `/v1` adds a declarative route table on top, and the legacy unversioned routes call the same handler functions, so behaviour cannot drift between them.

**P2. Loopback is the default; remote access is a mode.** Server mode is switched on explicitly (`--allow-remote`), and switching it on changes three things together:
- Projects come from an allowlist; they cannot be registered over HTTP.
- Tokens are per user and carry a role.
- TLS is required, unless the operator passes an explicit `--insecure-http` acknowledgement for a TLS-terminating proxy.

**P3. Identity comes from credentials, never from the request body.** This is the opposite of A8.

**P4. Handlers call cores and stores, not the `tool_*` wrappers.**
- `mcp_server.get_mind` keeps its own `_mind_cache`, so calling `tool_*` from the daemon would load each project twice.
- Normalisers that both MCP and REST need (search-hit shape, compact memory row) move into one shared module that both import.

**P5. License boundary: everything in this spec is MIT core.**
- `neuralmind/tier2/` may configure or extend the API (seat checks, the hash-chained audit, `SelfHostedConfig`) by importing core.
- Core never imports `neuralmind/tier2/`.
- So the reserved-path guard in `tier2/self_hosted.py:33-113` is re-implemented in core, not imported.

**P6. Changes within `v1` are additive.**
- New routes and response fields are allowed.
- Removing or renaming anything requires `/v2`.
- Clients must ignore response fields they don't recognise; servers ignore request fields they don't recognise.

**P7. Side effects are documented per route.** Some reads also learn. For example, `query` reinforces synapses through `reinforce_from_query` (`synapse_feedback.py:229`, called from `mind.query()`). The reference states this for every route where it happens.

---

## 4. Resource model and the mem0 mapping

| Resource | What it is | Backed by |
|---|---|---|
| **Project** | A registered repository root, identified by an opaque `id` | `ProjectRegistry` (`daemon.py:145-215`) plus a persisted registration file |
| **Index** | Build, progressive-disclosure query, entity search, wakeup, stats | `NeuralMind.build/query/search/wakeup/get_stats` (`core.py:494, 1320, 1498, 1296, 1538`) |
| **Memory** | A decision record: title, rationale, the files it governs, a commit, and a status (ACTIVE, STALE or INVALIDATED) | `DecisionStore` (`memory/store.py:269-952`) |
| **Association** | Learned synapses plus the structural call/import graph | `SynapseStore` (`synapses.py`), `NeuralMind.synaptic_neighbors/structural_neighbors/impact` (`core.py:1621, 1713, 1754`) |
| **Activity** | "These files were used together", reported by any agent | `NeuralMind.activate_files` (`core.py:353`) |
| **Document** | A PDF, Markdown or text file ingested into the index | `NeuralMind.ingest_document` (`core.py:825`) |
| **Job** | Long-running work such as a build | `JobManager` (`daemon.py:254-298`) |
| **Event** | A live stream of synapse, file and decision events | `event_bus.py` |

**Project ids.**
- In loopback mode the id is `p_` followed by the first 12 hex characters of `sha256(realpath(root))`. It is deterministic and stable across daemon restarts.
- In server mode an operator may assign readable aliases (`--project api=/srv/repos/api` gives id `api`).
- Ids match `^[a-z0-9][a-z0-9_-]{0,63}$`.
- Clients treat ids as opaque.

**mem0 → NeuralMind**

| mem0 | NeuralMind `/v1` | Python client | Notes |
|---|---|---|---|
| `add(messages, user_id=…)` | `POST /v1/projects/{id}/memories` | `p.memories.add(title, rationale, files=[…])` | An explicit record; no LLM extraction. The `files` field ties it to code, so it goes STALE when those files change (the existing invalidation rules). |
| `search(query, user_id=…)` | `POST /v1/projects/{id}/memories/search` | `p.memories.search(q)` | FTS5/bm25 over title, rationale and evidence (`store.py:668`) |
| `get_all(user_id=…)` | `GET /v1/projects/{id}/memories` | `p.memories.list(status=…)` | |
| `get(memory_id)` | `GET /v1/projects/{id}/memories/{mid}` | `p.memories.get(mid)` | |
| `update(memory_id, …)` | `PATCH /v1/projects/{id}/memories/{mid}` | `p.memories.update(mid, …)` | Amend semantics, like `neuralmind decisions amend` |
| `delete(memory_id)` | `DELETE …/memories/{mid}`, or the soft form `POST …/memories/{mid}/invalidate` | `p.memories.delete(mid)` / `.invalidate(mid, reason)` | Prefer invalidate, which keeps the record and its audit trail |
| `history(memory_id)` | `GET …/memories/{mid}/timeline` (PR 2) | `p.memories.timeline(mid)` | Chronological neighbours (`tool_memory_timeline`), not per-field history |
| *(no equivalent)* | `POST /v1/projects/{id}/query` | `p.query(question)` | Token-budgeted code context, NeuralMind's main feature |
| *(no equivalent)* | `POST /v1/projects/{id}/search` | `p.search(q)` | Code entity search |
| *(no equivalent)* | `POST /v1/projects/{id}/activity` (PR 2) | `p.activity(files=[…])` | Lets any agent, not only Claude Code hooks, report which files it used together, so NeuralMind learns associations from it |
| `user_id` / `agent_id` / `run_id` scoping | Project, plus synapse namespace (`personal`/`shared`/`ephemeral`, branch-aware) | — | A different axis: memory is per repository, not per person |

---

## 5. API v1 reference

### 5.1 Conventions

**Base URL.**
- Local: `http://127.0.0.1:<port>/v1`. The port and token come from the discovery file (`daemon.py:56-104`).
- Server mode: whatever the operator configures.

**Auth.**
- `Authorization: Bearer <token>`. Under `/v1`, the token is **not** accepted in the query string.
- Unauthenticated routes: `GET /v1/health` and `GET /v1/openapi.json`.

**Body.**
- JSON in UTF-8 only.
- A request body requires `Content-Type: application/json`; otherwise the response is 415.
- The maximum body is 1 MiB by default (`NEURALMIND_API_MAX_BODY_BYTES`); larger bodies get 413.
- The size cap also applies to legacy routes.

**Response headers.**
- `Content-Type: application/json; charset=utf-8`
- `NeuralMind-API-Version: 1`
- `X-Request-Id`: an inbound value matching `[A-Za-z0-9-]{1,64}` is echoed back; otherwise one is generated.

**Host check (defence against DNS rebinding).**
- Loopback mode accepts `Host` values of `127.0.0.1`, `localhost` or `[::1]`, on any port.
- Server mode accepts the configured `public_hosts`.
- Anything else gets 403 `host_not_allowed`.

**Validation.**
- Request and response models are pydantic v2, which is already a base dependency (`pyproject.toml:97`).
- Models use `extra="ignore"`.
- A failed validation returns 422 `validation_error`, with `details.errors` listing `{loc, msg, type}` for each error.

**Pagination.**
- Parameters: `limit` (default 50, maximum 200) and an opaque `cursor`.
- Response shape: `{"items": […], "next_cursor": "…" | null}`.

**Long-running work.**
- Returns `202 Accepted` with a `Location: /v1/jobs/{job_id}` header and `{"job": {…}}` in the body.
- Passing `"wait": true` runs the work inline instead.

**Formats.** Timestamps are ISO-8601 UTC strings; the legacy routes' epoch floats are converted. Ids are opaque strings.

**Success codes.**

| Code | Used for |
|---|---|
| 200 | Ordinary success |
| 201 | Create, with a `Location` header |
| 202 | Job accepted |
| 204 | Delete |

**Error envelope.**

```json
{
  "error": {
    "code": "memory_not_found",
    "message": "no memory with id 9b2c…",
    "status": 404,
    "request_id": "a1b2c3",
    "details": {}
  }
}
```

**Error codes.**

| Status | `code` | When |
|---|---|---|
| 400 | `invalid_request` | Malformed JSON, or a malformed query parameter |
| 401 | `unauthorized` | Missing or invalid token |
| 403 | `forbidden` | The caller's role doesn't allow the route (server mode) |
| 403 | `registration_disabled` | `POST /v1/projects` in server mode |
| 403 | `host_not_allowed` | The `Host` header is not allowed |
| 404 | `not_found` | Unknown route |
| 404 | `project_not_found` / `memory_not_found` / `job_not_found` | Unknown id |
| 405 | `method_not_allowed` | The path exists but the method doesn't; an `Allow` header is sent |
| 409 | `conflict` | A memory with a client-supplied `id` already exists |
| 409 | `index_not_built` | **Reserved.** Used once perf WP 2.2 makes `query` stop building (§9). |
| 413 | `payload_too_large` | Body over the cap |
| 415 | `unsupported_media_type` | A body without `application/json` |
| 422 | `validation_error` | Schema validation failed |
| 429 | `rate_limited` | Server mode; a `Retry-After` header is sent |
| 500 | `internal_error` | In loopback mode `details.exception` carries `Type: message` for debugging. Server mode omits it; the detail goes to the log under the request id. |
| 503 | `unavailable` | The backend failed to load, for example the embedding model is missing on an offline machine |

### 5.2 Routes

The **PR** column is the delivery PR (§10). `{id}` is a project id, `{mid}` a memory id and `{jid}` a job id.

| Method & path | Purpose | Side effects | PR |
|---|---|---|---|
| `GET /v1` | API root: `{api_version, neuralmind_version, mode, openapi_url}` | — | 1 |
| `GET /v1/health` | Unauthenticated liveness check: `{ok, api_version}`. Deliberately returns no paths, pid or projects. | — | 1 |
| `GET /v1/status` | `{pid, uptime_seconds, mode, version, projects:[{id,name,built,warm}], jobs_active}` | — | 1 |
| `GET /v1/openapi.json` | Generated OpenAPI 3.1 document | — | 1 |
| `POST /v1/admin/shutdown` | Graceful stop | Stops the daemon | 1 |
| `GET /v1/projects` | List registered projects | — | 1 |
| `POST /v1/projects` | Register `{path}`. Returns 201 if new, 200 if already registered; idempotent. | Persists the registration | 1 (403 in server mode) |
| `GET /v1/projects/{id}` | `{id, name, path, built, warm}` | — | 1 |
| `POST /v1/projects/{id}/build` | `{force=false, wait=false}` | Writes the index | 1 |
| `POST /v1/projects/{id}/query` | `{question, query_type="auto", context_budget=null, trace=false, trace_verbose=false}` | **Reinforces synapses.** The first call in a daemon's lifetime builds the index (see §9). | 1 |
| `POST /v1/projects/{id}/search` | `{query, n=10}` returns hits in the MCP shape | First call may build | 1 |
| `GET /v1/projects/{id}/wakeup` | Project wake-up context (`NeuralMind.wakeup()`) | First call may build | 1 |
| `GET /v1/projects/{id}/stats` | `NeuralMind.get_stats()` | — | 1 |
| `GET /v1/projects/{id}/savings` | `?cost=&model=&queries_per_day=` → `compute_savings` | — | 1 |
| `POST /v1/projects/{id}/validate` | `{write=false}` | `write=true` writes IR files. Allowed only in loopback mode or for the admin role. | 1 |
| `POST /v1/projects/{id}/memories` | Record a decision | Writes `memory.db` | 1 |
| `GET /v1/projects/{id}/memories` | `?status=ACTIVE\|STALE\|INVALIDATED\|ALL&file=…&limit=&cursor=` | — | 1 |
| `POST /v1/projects/{id}/memories/search` | `{query, limit=10, status="ACTIVE", view="full"\|"compact"}` | — | 1 |
| `GET /v1/projects/{id}/memories/{mid}` | One record | — | 1 |
| `PATCH /v1/projects/{id}/memories/{mid}` | Amend the record | Writes | 1 |
| `POST /v1/projects/{id}/memories/{mid}/invalidate` | `{reason}` | Writes | 1 |
| `POST /v1/projects/{id}/memories/{mid}/restore` | `{commit_sha?}` (defaults to HEAD) | Writes | 1 |
| `DELETE /v1/projects/{id}/memories/{mid}` | Hard delete | Writes. Admin only in server mode. | 1 |
| `GET /v1/projects/{id}/memories/{mid}/timeline` | `?before=3&after=3` | — | 2 |
| `GET /v1/projects/{id}/neighbors/synaptic` | `?q=&depth=2&top_k=10` | First call may build | 2 |
| `GET /v1/projects/{id}/neighbors/structural` | `?q=&relations=&blast_radius=false&depth=2` | — | 2 |
| `GET /v1/projects/{id}/impact` | `?symbol=&depth=1` | — | 2 |
| `GET /v1/projects/{id}/next` | `?from=&top_k=5` (directional transitions) | — | 2 |
| `POST /v1/projects/{id}/feedback` | `{node_id, signal: positive\|negative, context_node_ids[]}` | Writes synapses | 2 |
| `POST /v1/projects/{id}/activity` | `{files: […], strength=1.0}`, using `activate_files` | Writes synapses and transitions; may build | 2 |
| `GET /v1/projects/{id}/synapses/stats` | `SynapseStore.stats()` | — | 2 |
| `POST /v1/projects/{id}/documents` | `{path, content_type="auto"}`. The path is resolved **against the project root** and must stay inside it. | Writes the index | 2 |
| `GET /v1/jobs`, `GET /v1/jobs/{jid}` | Job list and detail | — | 1 |
| `GET /v1/events?project={id}` | SSE stream of project-tagged events | — | 3 |
| `/mcp` | MCP Streamable HTTP over the same dispatch core | Same as the tools it calls | 4 |
| `/_internal/hook/{action}` | Hook fast path (perf WP 2.4). **Not in OpenAPI and not covered by v1 stability.** Loopback only. | — | perf Phase 2 |

### 5.3 Shapes for the PR 1 routes

All values below are illustrative.

**Project**

```json
{ "id": "p_3f9a1c2b7d4e", "name": "neuralmind", "path": "/home/me/src/neuralmind", "built": true, "warm": true }
```

**Query**

Request: `POST /v1/projects/p_3f9a1c2b7d4e/query`

```json
{ "question": "how does synapse decay work?", "query_type": "auto", "context_budget": null, "trace": false }
```

Response `200`:

```json
{
  "project_id": "p_3f9a1c2b7d4e",
  "question": "how does synapse decay work?",
  "context": "…",
  "tokens": { "total": 0, "l0": 0, "l1": 0, "l2": 0, "l3": 0 },
  "layers_used": ["L0", "L1", "L3"],
  "reduction_ratio": 0.0,
  "search_hits": 0,
  "trace": null
}
```

- `tokens` maps the `TokenBudget` fields (`context_selector.py:33-47`): `l0_identity → l0`, `l1_summary → l1`, `l2_ondemand → l2`, `l3_search → l3`.
- Unlike the legacy route, `query_type` and `context_budget` are passed through. Their absence is why the CLI currently falls back to direct mode (`cli.py:1048-1087`).

**Search**

Request: `{"query": "...", "n": 10}`

Response `200`:

```json
{ "project_id": "…", "query": "…",
  "results": [ { "id": "…", "label": "…", "file_type": "code", "source_file": "neuralmind/synapses.py", "score": 0.0 } ] }
```

This is exactly the MCP `neuralmind_search` shape. The normaliser moves out of `mcp_server.tool_search` (`:153-169`) into a shared module that both import.

**Memory**

A record mirrors `DecisionRecord` (`memory/store.py:79-107`):

```json
{
  "id": "9b2c…", "title": "Use SQLite WAL for the synapse store",
  "rationale": "Hooks, the watcher and MCP write concurrently…",
  "commit_sha": "39617aa…", "files_affected": ["neuralmind/synapses.py"],
  "decision_type": "ARCHITECTURE", "confidence": 1.0, "status": "ACTIVE",
  "author": null, "evidence": [], "rejected_alternatives": [],
  "dependency_constraints": [], "tags": ["storage"],
  "created_at": "2026-10-02T12:00:00Z", "updated_at": "2026-10-02T12:00:00Z"
}
```

**Create rules.** `title` and `rationale` are required; everything else is optional.
- **`commit_sha` defaults to `HEAD`** when the project is a git repository, otherwise `""`. This matches the CLI. The MCP wrapper defaults to `""` (`mcp_tools.py:89`), which weakens the staleness rules.
- **`files_affected`** is normalised to project-relative POSIX paths. Absolute paths inside the project are made relative. Paths outside the project return 422, because `find_by_files` does exact matches on the stored strings (`store.py:576`).
- **`decision_type` and `status` are validated strictly**, returning 422. The store silently replaces invalid values with defaults (`store.py:338`).
- **A client-supplied `id` that already exists** returns 409 `conflict`.
- **The handler reads the record back with `get(id)` after writing.** `DecisionStore.record()` swallows INSERT errors and returns the record anyway, so if the read-back finds nothing the handler returns 500 `internal_error` ("write did not persist").
- **Response:** `201` with `Location: /v1/projects/{id}/memories/{mid}`.

**List.**
- `status=ALL` maps to `status=None`.
- `file=` may repeat; it uses `find_by_files(files, include_invalidated=(status in {INVALIDATED, ALL}))`.
- `list_all()` returns everything, so the handler pages it with `limit` and `cursor`.

**Search.**
- `limit` is capped at 25. `status=ALL` maps to `None`; the MCP tool has a bug here, see §12.
- `view=compact` returns the MCP compact row (`mcp_tools.py:176`).
- The store returns no relevance score, so results are in rank order and v1 exposes no `score` field.

**Patch.** Accepts any of `rationale`, `confidence`, `tags`, `files_affected`, `evidence_append[]` and `rejected_append[]`. The handler loads the record, applies the changes, then calls `store.update()`. Concurrent edits are last-write-wins in PR 1; `If-Match` on `updated_at` is optional in PR 2.

**Invalidate.**
- Returns 404 for an unknown id. The store's `invalidate()` is a silent no-op in that case (`store.py:487`), so the handler checks existence first.
- On success it returns the updated record with status INVALIDATED; the store appends the reason to `evidence`.

**Restore.** `commit_sha` defaults to HEAD. Returns 404 for an unknown id (the store raises `KeyError`, `store.py:509`).

**Delete.** Returns 204, or 404 for an unknown id.

**Job**

```json
{ "id": "a1b2c3d4e5f6", "kind": "build", "project_id": "p_…", "status": "queued|running|done|error",
  "result": null, "error": null, "created_at": "…", "finished_at": null }
```

### 5.4 Locking per route

Taken from a read of the stores; see also perf spec P0-4.

**Index routes take `registry.lock_for(project)`.** These are build, query, search, wakeup and stats, and in PR 2 also synaptic/structural neighbours, impact, activity and documents.
- They touch `mind.embedder`, including turbovec's persistent `check_same_thread=False` connection (`turbovec_backend.py:155`).
- They may call `_ensure_built()`.
- This is today's behaviour (`daemon.py:427-482`).

**Memory routes take no project lock.**
- They use a `DecisionStore(root)` built per request, or one cached per project; its constructor runs idempotent DDL.
- `DecisionStore` opens a new connection for every call with WAL mode, `timeout=30` and autocommit (`store.py:281-293`), which already makes it safe across threads and processes.

**Synapse-only routes (PR 2 `feedback`, `next`, `synapses/stats`) take no project lock.**
- They go through `mind.synapses`, which is guarded by `_synapses_lock` (`core.py:200`), and then through SQLite.
- Write endpoints return the number of pairs touched. That makes perf P0-4's silently swallowed `SQLITE_BUSY` visible to callers; perf Phase 3 fixes the cause.

---

## 6. Security model

### 6.1 Loopback mode (default; PR 1)

**Bind.**
- The bind address must be loopback: `127.0.0.0/8`, `::1` or `localhost`.
- PR 1 refuses any other address at startup with a message pointing to server mode. This also closes A3 for the legacy routes.
- PR 2 adds `--allow-remote`.

**Token.**
- The existing per-user token from the discovery file (file mode 0600, directory 0700).
- `/v1` accepts it in the header only.

**Host allowlist.** As in §5.1.

**CORS.**
- The server sends no CORS headers.
- `/v1` requires `Content-Type: application/json` and a bearer header, so a cross-origin browser request is always preflighted, and the preflight fails.
- Together with the Host check, this covers browser-based CSRF and DNS rebinding.

**Project registration.** Allowed for any directory the daemon user can read, except a reserved-path denylist re-implemented in core (P5), modelled on `tier2/self_hosted.py:33-113`:
- `/`, `/proc`, `/sys`, `/dev`, `/etc`, `/boot`, `/run`
- `$HOME` itself
- `~/.ssh`, `~/.gnupg`, `~/.aws`, `~/.kube`, `~/.docker`, `~/.config`

The path must be a directory and is resolved with `realpath` first.

**Threat model.**
- **Trusted:** processes running as the same OS user. They can read the token file anyway.
- **Not trusted:** other local users, browsers, and network peers.

### 6.2 Server mode (PR 2)

**Start-up.**

```
neuralmind daemon start --allow-remote --host 0.0.0.0 --port 8765 \
    --config /etc/neuralmind/server.toml [--tls-cert … --tls-key … | --insecure-http]
```

**Projects.**
- Defined in config, for example `[[projects]] id = "api"  path = "/srv/repos/api"`.
- `POST /v1/projects` returns 403 `registration_disabled`.

**Tokens.**
- Stored in a tokens file as sha256 hashes, each mapped to `{actor, role, projects: [...] | "*"}`.
- `neuralmind daemon token create --actor alice --role builder` prints the token once.
- The role comes from the token, never from the request (P3).

**Roles.**
- `reader`, `builder` and `admin`, with permission names shared with `mcp_security.DEFAULT_ROLE_POLICY` (`mcp_security.py:14-59`).
- Each route maps to a permission; for example `memories.create` maps to `neuralmind_record_decision`.
- That way one policy governs both MCP and REST.

**TLS.**
- Either `--tls-cert`/`--tls-key`, using stdlib `ssl.SSLContext.wrap_socket`, or `--insecure-http`, which acknowledges a TLS-terminating proxy.
- Start-up refuses a non-loopback bind with neither.

**Rate limiting.**
- `mcp_security.RateLimiter` per actor, returning 429 with `Retry-After`.
- The limiter needs a lock first: today it is not thread-safe (`mcp_security.py:77-92`), and `ThreadingHTTPServer` is multi-threaded.

**Audit.** Every mutating call appends `AuditTrail.append_event(category="api", action=<permission>, actor=<actor>)` (core `audit.py:114`).

**Restricted operations.** These are admin-only in server mode:
- `validate` with `write=true`
- memory `DELETE`
- `admin/shutdown`

**Config bridge.**
- tier2's `self_hosted.bind_address` and `port` (`tier2/config.py:64-80`) feed server mode through an adapter that lives in tier2.
- These would be the first consumers those fields have ever had.

### 6.3 What does not change

NeuralMind itself still transmits no repository content. A team that runs server mode is moving its own data to its own server, and the docs must say exactly that, using the safe phrasing that `tests/test_docs_claims.py` recommends.

---

## 7. Clients

### 7.1 Python client: `neuralmind/client.py` (PR 1)

The client is stdlib-only (`urllib`), finds the daemon the same way `daemon_client.connect()` does, and adds no import-time cost.

```python
from neuralmind.client import NeuralMindClient

nm = NeuralMindClient()  # local daemon, found via the discovery file
# nm = NeuralMindClient("https://nm.internal:8765", token=os.environ["NEURALMIND_API_TOKEN"])

repo = nm.project(".")   # POST /v1/projects (idempotent); returns a handle
repo.build(wait=True)

ctx = repo.query("how does synapse decay work?")
print(ctx.context, ctx.tokens.total)

repo.memories.add(
    title="Use SQLite WAL for the synapse store",
    rationale="Hooks, the watcher and MCP write concurrently; WAL lets readers proceed.",
    files=["neuralmind/synapses.py"],
)
for m in repo.memories.search("sqlite concurrency"):
    print(m.id, m.title, m.status)
```

**Return types.** Small frozen dataclasses (`QueryResult`, `SearchHit`, `Memory`, `Job`, `Project`). Each also exposes `.raw`, the full response dict, so a field added later is reachable before the client is updated.

**Errors.** `NeuralMindAPIError(status, code, message, details, request_id)`, with subclasses `NotFound`, `Unauthorized`, `Forbidden`, `ValidationFailed`, `Conflict`, `RateLimited`.

**Connection settings.**
- `NEURALMIND_API_URL` and `NEURALMIND_API_TOKEN` override discovery.
- `autostart=False` is the default. Perf WP 2.4 owns the auto-spawn policy; the client exposes the switch but does not decide it.

**Timeouts.** 30 s by default. `query` uses 120 s, and `build(wait=True)` 600 s, matching `daemon_client.py`.

### 7.2 Other clients

**CLI (PR 2).**
- `daemon_client` moves to `/v1`.
- `neuralmind search` is routed through the daemon too; today it is always direct (`cli.py:1852-1862`).
- Legacy routes then return `Deprecation: true` and `Link: </v1/…>; rel="successor-version"`.
- Legacy routes are removed no sooner than two minor releases after that.

**Dashboard (PR 3).** It reads `/v1` and `/v1/events`. `server.py`'s `/api/*` routes become thin adapters, then are deleted.

**MCP over HTTP (PR 4).**
- `/mcp` uses the `mcp` SDK's Streamable HTTP session manager, and its tool handlers call the daemon's `dispatch()` with the shared `ProjectRegistry`. This is also what perf WP 2.4 needs.
- Auth is a token from the same tokens file; OAuth 2.1 comes later.
- The SDK needs ASGI (starlette, uvicorn), which arrives transitively through `mcp` (`pyproject.toml:88`). See open decision 4.

**TypeScript client (PR 5, optional).** Generated from the committed OpenAPI snapshot.

---

## 8. Packaging and Docker (PR 3)

**Dockerfile changes.**
- `EXPOSE 8765`.
- `VOLUME ["/data", "/repos"]`.
- A `HEALTHCHECK` that calls `python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/v1/health')"`, because the slim image has no curl.

**`docker-compose.yml` changes.**
- Add a real `command:` running `neuralmind daemon start --foreground --allow-remote --host 0.0.0.0 --port 8765 --config /config/server.toml --insecure-http`.
- Publish the port on loopback by default (`127.0.0.1:8765:8765`); operators put a proxy in front.
- Set `NEURALMIND_LICENSE_PATH=/app/license.json`.
- Mount repositories at `/repos`.

**Repository mounts must be writable for now.** `.neuralmind/` lives inside each project (`state_dir.py`). PR 3 investigates letting state live under `NEURALMIND_DATA_DIR` so repositories can be mounted read-only.

**README.** A "Run the NeuralMind API with Docker" block: `docker compose up`, then `curl localhost:8765/v1/health`.

**The end-state port map:**

| Process | Port |
|---|---|
| Local daemon | OS-assigned, recorded in the discovery file (perf WP 2.4) |
| `neuralmind serve` (UI) | 8787, until PR 3 folds the UI into the daemon |
| Team server | 8765, serving `/v1`, the UI and `/mcp` together |

---

## 9. Coordination with the performance programme

| Perf item | Effect on this spec | Rule |
|---|---|---|
| WP 2.2: split `build()` into `load()` and `maintain()` | Today the first query of a daemon's lifetime builds (`ensure_built`, `daemon.py:193-202`). After 2.2, `query` on a project with no index returns 409 `index_not_built`, and `details.job_id` names an automatically submitted build. The Python client waits on that job when `auto_build=True`. | The code is reserved now, so the change is additive |
| WP 2.4: auto-spawn, idle TTL, port move | PR 1 keeps 8787 and does not auto-spawn; the client's `autostart` defaults to off | WP 2.4 owns the port and spawn policy |
| WP 2.4: hook route | The perf plan's `/hook/<action>` lives at `/_internal/hook/<action>`, outside OpenAPI | Whichever lands second adopts the prefix |
| WP 2.4: MCP shares `ProjectRegistry` | PR 4 needs this too | Build it once |
| P0-4: deferred `BEGIN` → `SQLITE_BUSY` | PR 2 write endpoints return counts | Phase 3 fixes the cause |
| WP 5.8: SSE fan-out thread | PR 3's `/v1/events` uses a single fan-out thread from the start | — |

**Ordering.**
- PR 1 doesn't depend on perf Phase 1 or 2. It touches daemon routing and new modules, not hooks, `core.py` or the stores.
- If perf Phase 2 merges first, PR 1 rebases onto its daemon changes. The route table makes that merge mechanical.

---

## 10. Delivery plan

| PR | Type | Contents | Exit gate |
|---|---|---|---|
| **1** | `feat:` (minor) | `/v1` core: route table and conventions, projects, index routes, memories, jobs, OpenAPI with a committed snapshot, Python client, loopback guard, docs. **Scope: [`LOCAL-API-PR1-SCOPE.md`](LOCAL-API-PR1-SCOPE.md).** | All PR 1 acceptance criteria |
| 2 | `feat:` | Server mode (allowlist, tokens, roles, TLS, rate limit, audit); association, activity, document and timeline routes; CLI moves to `/v1`; legacy deprecation headers | A non-loopback bind is refused without the flags; role-by-route matrix test; remote e2e test on a TLS socket |
| 3 | `feat:` | `/v1/events` (project-tagged), dashboard on `/v1`, Docker and compose fixed (A7), use case "Run a team NeuralMind API server" | CI runs `docker compose up` and gets 200 from `/v1/health` |
| 4 | `feat:` | MCP Streamable HTTP on the dispatch core, token auth, shared registry | `initialize` / `tools/list` / `tools/call` round trip over HTTP in CI on both `mcp` SDK lines |
| 5 | `feat:` | TypeScript client, examples (CI script, non-MCP agent), `docs/comparisons/vs-mem0-zep.md` gains an "API parity" section | — |

Every PR ships with the `CLAUDE.md` docs and SEO checklist in the same PR.

---

## 11. Open decisions

1. **Seats in server mode.** Commercial terms say features aren't gated and seats beyond one are a Team license. Recommendation: core doesn't enforce seats; tier2 registers a hook that *warns* when the number of distinct token actors exceeds licensed seats.
2. **Project id format.** A hash (recommended: stable, no state, nothing to leak) or a slug. Server mode gets aliases either way.
3. **SSE auth (PR 3).** `EventSource` can't set headers. Recommendation: the dashboard uses `fetch` streaming with the bearer header, and `/v1` stays header-only.
4. **ASGI dependency.** If PR 4 relies on starlette and uvicorn, declare them explicitly rather than inheriting them through `mcp`. Recommendation: `/v1` stays on the stdlib server in every mode, and ASGI is used only for `/mcp`, in the same process and sharing the registry.
5. **Path redaction.** Should `path` be hidden from the `reader` role in server mode? Recommendation: yes.
6. **Public name.** Recommendation: "NeuralMind API (self-hosted)" in public docs, so nothing implies a hosted service; "local API" in engineering docs.
7. **Hard delete.** Keep it (mem0 parity, and a way to erase a mistaken record), but admin-only in server mode. Invalidate stays the recommended path.

---

## 12. Side findings (separate fixes, not in PR 1)

Found while surveying for this spec; each was verified against `39617aa`.

1. **`neuralmind_memory_search` with `status: "all"` matches nothing.** The schema advertises "all" (`memory/mcp_tools.py:480`), but `tool_memory_search` passes the string straight to `DecisionStore.query`, which treats only `None` as "all statuses" (`:193-226`).
2. **`InvalidationEngine` raises `AttributeError` in its error path.** The event-bus failure branch logs `event.id` (`memory/invalidate.py:387`), but `InvalidationEvent` has `decision_id`, not `id` (`:195-212`).
3. **"Not built" is reported as a security denial.** `GraphNotBuiltError` subclasses `RuntimeError` (`core.py:129`), and MCP maps every `RuntimeError` to `code: "security_denied"` (`mcp_server.py:1335-1336`).
4. **The compose service restart-loops, and the license path is wrong** (A7).
5. **`neuralmind/memory/cli.py` is dead code.** It defines a second decision store at `.neuralmind/memory/decisions.sqlite` with a different schema and lowercase statuses, and its `build_memory_subparsers` is never called. The live path is `neuralmind decisions` → `DecisionStore`.
6. **`docs/use-cases/always-on.md` disagrees with the shipped service templates.** It says `serve` runs on 8787; the systemd and launchd templates use 8765.

---

## 13. Sources

- mem0 OSS REST API: https://docs.mem0.ai/open-source/features/rest-api
- mem0 platform pricing (third-party summaries, September–October 2026): https://toolradar.com/tools/mem0-ai/pricing, https://costbench.com/software/ai-memory-context/mem0/free-plan/, https://usagepricing.com/blueprint/mem0
- NeuralMind's existing mem0 comparison: [`docs/comparisons/vs-mem0-zep.md`](../comparisons/vs-mem0-zep.md)
