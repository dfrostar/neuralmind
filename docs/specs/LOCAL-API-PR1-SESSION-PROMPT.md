# Session prompt: implement Local API PR 1 (`/v1` daemon API)

Paste everything below the line into a new Claude Code session opened in a local
clone of `dfrostar/neuralmind`. The prompt is self-contained.

The spec documents it refers to were added to `main` by
https://github.com/dfrostar/neuralmind/pull/552. A follow-up PR from the branch
`claude/clever-sagan-m9475i` revised them with a mem0 gap analysis.

If `docs/specs/LOCAL-API-SPEC.md` on your `main` has no §4.1 ("What else to
borrow from mem0"), that revision hasn't merged yet. Read the revised docs from
the branch instead:
`git fetch origin claude/clever-sagan-m9475i && git show origin/claude/clever-sagan-m9475i:docs/specs/LOCAL-API-SPEC.md`
(and the same for `LOCAL-API-PR1-SCOPE.md`).

---

You are implementing **PR 1 of the NeuralMind Local API**: a versioned `/v1`
HTTP API on the existing local daemon, plus a stdlib Python client. Work in this
repository (`dfrostar/neuralmind`) and follow its `CLAUDE.md`.

## 1. Background (already decided; don't re-open)

### The product

NeuralMind is a local-first code-intelligence layer for AI coding agents. It has
four parts:

- a semantic index with progressive context disclosure (L0–L3);
- a Hebbian "synapse" store that learns which files go together;
- a decision memory (`DecisionStore`, `.neuralmind/memory.db`);
- MCP tools and Claude Code hooks.

It is MIT core, plus source-available modules under `neuralmind/tier2/`.

### The decision

The question was "should NeuralMind have an API like mem0, that is free?". The
answer: **copy mem0's developer experience (one documented endpoint,
`client.add()` / `client.search()`, a server you run yourself), but don't host
anything.** The reasons:

- **Privacy promise.** The README promises that NeuralMind "transmits no
  repository content off your machine" (`README.md:67`).
- **Roadmap.** Hosted SaaS is an explicit non-goal (`ROADMAP.md:212`).
- **Cost.** The free tier costs nothing to serve today; a hosted free tier would
  cost money per repository and mean holding customers' source code.
- **Latency.** Hooks run on every tool call, so a network hop doesn't belong
  there.
- **Pricing.** NeuralMind sells seats ($29/user/mo Team, in
  `commercial-terms.json`), not operations.

The API is therefore **self-hosted only**: loopback by default, with a team
"server mode" in a later PR.

### What exists today

| Piece | Where | State |
|---|---|---|
| The daemon | `neuralmind/daemon.py` | Stdlib `ThreadingHTTPServer`, default `127.0.0.1:8787`. Bearer token in `~/.neuralmind/daemon.json` (mode 0600). |
| `ProjectRegistry` | `daemon.py:145-215` | Warm `NeuralMind` instance per project, with a per-project `RLock` |
| `JobManager` | `daemon.py:254-298` | Background builds |
| `dispatch()` | `daemon.py:338-403` | Transport-agnostic. Unversioned routes `/health /status /jobs /jobs/{id} /stats /savings /query /search /build /validate /shutdown`. The project is a **raw path in the request body**. |
| `_Handler` | `daemon.py:496-546` | GET/POST only, no body cap, accepts `?token=`, and `--host` accepts any address |
| Daemon client and CLI | `neuralmind/daemon_client.py` | The CLI prefers the daemon for `query`/`stats` only (`cli.py:734-747`) |
| Decision store | `neuralmind/memory/store.py` `DecisionStore` | Writes: `record()` (:338; **swallows INSERT errors**), `update()` (:454), `update_status()` (:435), `invalidate()` (:487; **silent no-op for an unknown id**), `restore()` (:509; raises `KeyError`), `delete()` (:540). Reads: `get()` (:552), `query(text, limit, status)` (:668; only `status=None` means all statuses), `list_all(status)` (:847), `find_by_files(files, include_invalidated)` (:576; exact string match on project-relative paths). |
| Store concurrency | — | A new SQLite connection per call, WAL, `timeout=30`, autocommit. Thread- and process-safe without Python locks, so **memory routes need no project RLock**. Index routes do need it (they touch `mind.embedder` and turbovec's persistent connection). |
| MCP memory wrappers | `neuralmind/memory/mcp_tools.py` | `_compact_row` at :176. `tool_record_decision` defaults `commit_sha=""`, whereas the CLI defaults to HEAD; **v1 follows the CLI.** |
| MCP search | `mcp_server.tool_search` (:153-169) | Normalises hits to `{id, label, file_type, source_file, score}`, which is the v1 shape |
| MCP mind cache | `mcp_server.get_mind` | Has its own `_mind_cache`. **Don't call `tool_*` functions from the daemon**; call core and store methods on `ctx.registry.get(...)`. |
| Pydantic | `pyproject.toml:97` | `pydantic>=2.4` is a base dependency, used for v1 request and response models (server side only) |
| Free-standing JSON | `pyproject.toml` hatch `include` | JSON files need explicit wheel includes, so **generate OpenAPI from code at runtime** and commit only a docs snapshot |
| Perf plan | `docs/specs/PERFORMANCE-FUTURE-PROOFING-PLAN.md` Phase 2 (WP 2.2, 2.4) | Also changes the daemon: auto-spawn, idle TTL, a port move off 8787, a hook route, and `load()`/`maintain()`. **Those are not yours.** Leave the port at 8787 and add no auto-spawn. If any of it has already landed on `main`, adapt to it; put any hook route under `/_internal/` and keep it out of OpenAPI. |

## 2. Your task

Implement **exactly** what `docs/specs/LOCAL-API-PR1-SCOPE.md` describes. The
design reference is `docs/specs/LOCAL-API-SPEC.md`; read §5 (conventions, routes,
shapes), §5.4 (locking) and §6.1 (loopback security) closely. In summary:

1. **New package `neuralmind/api_v1/`** containing:
   - `routing.py`: a declarative `Route` table, path templates, and a 405 with `Allow`;
   - `errors.py`: the `{"error": {code, message, status, request_id, details}}` envelope;
   - `models.py`: pydantic v2 models, `extra="ignore"`;
   - `projects.py`: `ProjectDirectory`. Ids are `p_` plus 12 hex characters of `sha256(realpath)`. It has a reserved-path denylist **re-implemented in core** (never import `neuralmind.tier2`) and persists to `<daemon home>/projects.json` with mode 0600, written atomically;
   - `shapes.py`: shared normalisers, moved out of `mcp_server.tool_search` and `memory/mcp_tools._compact_row` without changing their behaviour;
   - `handlers/{meta,projects,index,memories,jobs}.py`;
   - `openapi.py`: OpenAPI 3.1 built from the route table plus `model_json_schema()`. `python -m neuralmind.api_v1.openapi --write docs/api/openapi-v1.json` writes the committed snapshot.
2. **Routes:**
   - Meta: `GET /v1`, `GET /v1/health` (no auth; returns no paths or pid), `GET /v1/status`, `GET /v1/openapi.json` (no auth), `POST /v1/admin/shutdown`.
   - Projects: `GET|POST /v1/projects`, `GET /v1/projects/{id}`.
   - Index, under `/v1/projects/{id}/`: `build` (202 + `Location: /v1/jobs/{jid}`, or `wait=true` for 200), `query` (passes `query_type` and `context_budget` through; maps `TokenBudget` to `tokens.{total,l0,l1,l2,l3}`), `search`, `wakeup`, `stats`, `savings`, `validate`.
   - Memories, under `/v1/projects/{id}/memories`: create (201 + `Location`), list (`status=ALL` maps to `None`, `file=` repeatable, cursor paging), `POST …/search` (limit at most 25, `view=full|compact`), get, `PATCH`, `POST …/{mid}/invalidate`, `POST …/{mid}/restore`, `DELETE` (204).
   - **Three mem0-derived additions** (spec §4.1 G3–G5; details in spec §5.3):
     - `possible_duplicates` on the create response: advisory, up to 3 ACTIVE matches by title that share a file.
     - `score` on each search result.
     - The `tag`, `type`, `author`, `created_after`, `created_before` and `min_confidence` filters on list and search, combined with AND.
   - Jobs: `GET /v1/jobs`, `GET /v1/jobs/{jid}`, with ISO-8601 UTC times.
3. **Memory rules:**
   - `commit_sha` defaults to `git rev-parse HEAD` in a git repository, otherwise `""`.
   - `files_affected` is normalised to project-relative POSIX paths. A path outside the project returns 422.
   - `decision_type` and `status` are validated strictly (422).
   - A duplicate client `id` returns 409.
   - **Read back after create**; if the record is missing, return 500.
   - **Check existence before invalidate and restore** (404).
   - **Duplicate hints.** After the write, call `query(title, limit=5, status="ACTIVE", with_scores=True)`, drop the new record, keep only matches that share a file (when the new record has files), and return at most 3. Never block or merge.
   - **Search filters.** Ask the store for `min(limit × 4, 100)` results, filter, then trim to `limit`. `min_confidence` maps to the store's existing `min_score` parameter, which filters on confidence.
4. **`daemon.py`:**
   - Add `do_PATCH` and `do_DELETE`.
   - Cap the body at `NEURALMIND_API_MAX_BODY_BYTES` (default 1 MiB; 413), for all routes.
   - Check the Host header (`127.0.0.1`, `localhost` or `[::1]`, else 403 `host_not_allowed`), for all routes.
   - `/v1/*` goes to `dispatch_v1` with **header-only** bearer auth. Every other path goes to the untouched legacy `dispatch()`.
   - Send the response headers `NeuralMind-API-Version: 1` and `X-Request-Id` (echo or generate).
   - `create_server()` and `main()` **refuse non-loopback hosts** (exit code 2 with a clear message).
   - `DaemonContext` gains `projects` and `mode="loopback"`.
   - Leave `ProjectRegistry._key` as `abspath`; read its comment.
5. **`cli.py`:** `daemon start` validates `--host` up front. **No new subcommands.**
6. **`neuralmind/client.py`:** a stdlib `urllib` client. It provides:
   - `NeuralMindClient(base_url=None, token=None)`, falling back to `NEURALMIND_API_URL` / `NEURALMIND_API_TOKEN` and then the discovery file;
   - `.project(path_or_id)`, returning a `ProjectClient` with `.build/.query/.search/.wakeup/.stats/.savings` and `.memories.add/list/search/get/update/invalidate/restore/delete`;
   - `.jobs.get/wait`;
   - frozen dataclasses with `.raw`;
   - `NeuralMindAPIError` and its subclasses.

   **Importing it must not pull in `neuralmind.core`, onnxruntime, chromadb, turbovec or pydantic.**
7. **Tests:** these new files, following the `FakeMind` pattern in `tests/test_daemon.py`, with a real `DecisionStore` in `tmp_path` for memories:
   - `test_api_v1_routing.py`
   - `test_api_v1_projects.py`
   - `test_api_v1_index.py`
   - `test_api_v1_memories.py`: includes duplicate hints, each filter, and score ordering
   - `test_memory_store_scores.py`: `with_scores=True` keeps the default order, and the default return type is unchanged
   - `test_api_v1_openapi.py`: snapshot equality and route ↔ path parity
   - `test_client.py`: includes a subprocess check that the import is lightweight
   - `test_daemon_bind_guard.py`
   - `test_api_v1_license_boundary.py`: an AST check for no `tier2` imports

   **Do not modify existing tests.**
8. **Docs, in the same PR.** This follows `CLAUDE.md`'s "Shipping a feature" checklist; the list is in scope doc §4:
   - Release notes: `docs/releases/RELEASE_NOTES_v<next minor>.md`, with the version taken from `.release-please-manifest.json` or an open release PR. Include a per-agent table: MCP agents see no change; scripts, CI and non-MCP agents gain `/v1`. Call out the loopback-only bind.
   - README: banner, history trail, an "NeuralMind API (self-hosted)" section, and the release-notes row.
   - `docs/index.html` (banner and meta) and `docs/about.html` (a "What's New" section).
   - `docs/wiki/CLI-Reference.md`: the daemon section, plus env vars `NEURALMIND_API_URL`, `NEURALMIND_API_TOKEN` and `NEURALMIND_API_MAX_BODY_BYTES`.
   - A new `docs/wiki/HTTP-API.md` with the mem0 → NeuralMind cheat sheet, linked from `Home.md` and `API-Reference.md`.
   - A new `docs/use-cases/local-http-api.md`.
   - `docs/comparisons/vs-mem0-zep.md`: the Distribution row and the "no server" bullet.
   - `pyproject.toml` keywords: `local-rest-api`, `openapi`, `agent-memory-api`.
   - `docs/sitemap.xml` and `docs/llms.txt`.

## 3. Rules

**Never:**
- edit `CHANGELOG.md`, or bump versions in `pyproject.toml` / `.release-please-manifest.json` (release-please owns them);
- import `neuralmind.tier2` from core code (license boundary);
- add runtime dependencies;
- touch hooks, `core.py` or the stores, beyond the two normaliser moves and **one** backward-compatible store change: `DecisionStore.query(…, with_scores=False)`, which returns `(record, -bm25)` pairs when `True`;
- start PR M (spec §4.2): no schema changes, history table, embeddings, `review_by`, or `agent`/`session_id` fields. That is a separate PR.

**Don't fix the unrelated bugs still open in spec §12** (compose restart loop, the dead `memory/cli.py`, the `always-on.md` port). Mention them in the PR body as follow-ups. Items 1, 2, 3 and 7 are already fixed. Build on them: the store normalises status filters, so the handler maps its `ValueError` to 422.

**Claims discipline** (CI-enforced by `tests/test_docs_claims.py` and `tests/test_site_claims.py`):
- No latency or throughput numbers; describe the mechanism instead ("keeps the index warm between calls").
<!-- claims-guard:allow (the next line quotes the forbidden phrases in order to disown them) -->
- No absolute privacy phrases ("never leaves", "no data leaves", "fully air-gapped"). The safe phrasing is "sends no telemetry and transmits no repository content off your machine."
- Document only shipped behaviour. Server mode, Docker and `/activity` are later PRs.

**Docs CLI guard.** `tests/test_docs_cli_paths.py` checks that every `neuralmind <cmd> <sub>` written in the docs exists in the parser. Don't document commands that don't exist.

**Scope.** If the change grows well past ~1,800 lines (excluding docs and the snapshot), stop and cut `PATCH`/`restore`/`DELETE` into a follow-up PR 1b rather than widening.

## 4. Suggested order

1. **Recon.** Read `CLAUDE.md`, both spec docs, `daemon.py`, `daemon_client.py`, `tests/test_daemon.py`, `memory/store.py` and `memory/mcp_tools.py`. Run `git log --oneline origin/main -- neuralmind/daemon.py` to see whether the perf Phase 2 work has landed. Then run the baseline: `pip install -e ".[dev]"` and `pytest tests/test_daemon.py tests/test_memory.py tests/test_mcp_server.py -q`.
2. Write `api_v1/errors.py`, `routing.py` and `models.py`, then the routing tests.
3. Integrate with the daemon (handler, body cap, Host check, bind guard), then the bind-guard tests.
4. Write `projects.py` and its handlers, then the tests.
5. Write the index handlers, then the tests.
6. Write the memory handlers, then the tests.
7. Write the jobs and meta handlers and `openapi.py`, generate the snapshot, then the tests.
8. Do the `shapes.py` refactor and re-run the MCP tests.
9. Write `client.py`, then its tests, including the import-weight test.
10. Write the docs.
11. **Validate:**
    - `pytest tests/ -q`
    - `ruff check .`
    - `black --check .`
    - `python scripts/check_commercial_terms.py`
    - **Manual end-to-end against this repository, with both the Python client and `curl`:** start the daemon; register `.`; build with `wait`; query and search; add a memory, search for it, invalidate it, and list with `status=ALL`; shut down. Keep a trimmed transcript.
12. **Open a draft PR from a new branch**, e.g. `feat/local-api-v1` off an up-to-date `main`.
    - Title: `feat(daemon): versioned /v1 local API with project registry, decision-memory endpoints and Python client`. `main` is squash-merged, so the title becomes the release-please commit.
    - Fill in `.github/PULL_REQUEST_TEMPLATE.md`, paste the end-to-end transcript, and list the follow-ups from spec §12.

## 5. When you finish, report

- what shipped, route by route;
- any deviation from the scope document, and why;
- test and lint results;
- the PR link;
- anything in the spec that turned out to be wrong when it met the code. If the spec revision has merged (see the note above), fix the spec in your PR; otherwise list the corrections in your report.
