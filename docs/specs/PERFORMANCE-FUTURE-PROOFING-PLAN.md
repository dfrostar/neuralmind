# Performance & Future-Proofing — Delivery Plan

**Status:** DRAFT for review
**Date:** 2026-09-15
**Spec:** [`PERFORMANCE-FUTURE-PROOFING-SPEC.md`](PERFORMANCE-FUTURE-PROOFING-SPEC.md) — finding IDs (H1, S3, D1 …) refer to its Section 3.
**Baseline:** v3.11.3

This plan turns the spec into six phases of shippable work. Each phase is a
release (or a `fix:` patch release for Phase 0), ships with the docs/SEO
checklist from `CLAUDE.md`, and is gated by the measurement harness that
Phase 1 delivers. Nothing in Phases 2–5 starts until Phase 1's gates are green
on `main`, because without them no phase can prove it helped or prove it
didn't regress.

Effort is given in engineer-days (ED) for one engineer familiar with the
codebase, and is an estimate, not a commitment.

---

## Phase map

| Phase | Release | Theme | Findings closed | ED | Exit gate |
|-------|---------|-------|-----------------|----|-----------|
| 0 | v3.11.4 (`fix:`) | Stop the bleeding | D1, D4, D3 | 1.5 | `neuralmind-mcp` starts on mcp 1.30 and 2.2 in CI; `--version` matches pyproject |
| 1 | v3.12.0 | Measure before optimising | M1–M5, D8 (markers) | 5 | `perf.py` runs in `ci-benchmark.yml` with a committed baseline; hook/cold-start/scaling gates active (initially at today's values) |
| 2 | v3.13.0 | Edge processes go read-only; daemon becomes real | H1–H9, R9, R10 | 9 | `prompt-submit` p95 ≤ 250 ms on fixture without daemon, ≤ 100 ms with; `query` no longer builds |
| 3 | v3.14.0 | Synapse store: bounded, concurrent-safe, rebuild-safe | S1–S9 | 8 | contention test passes; DB growth gate; zero orphans after rebuild |
| 4 | v3.15.0 | Build path: atomic, deduplicated, chunked, parallel | B1–B10 | 8 | no-op build ≤ 10 % of cold; artifacts byte-identical across no-op builds; 10k-file synthetic builds under the RSS gate |
| 5 | v3.16.0 | Retrieval constant factors + backend contract + dependency posture | R1–R8, D2, D5–D7, D9, D10 | 10 | scaling exponent ≤ 1.15; `VectorBackend` parity suite; 3.13 required in CI; domain tables out of the library |

Total ≈ 41 ED across six releases. Phases 3 and 4 are independent of each
other and can run in parallel if two engineers are available; Phase 5 is a
bag of independent work packages that can be split across releases.

---

## Phase 0 — Stop the bleeding (v3.11.4, `fix:`)

Ship within days. No behaviour change beyond "it works again".

| WP | Work | Files | Test | ED |
|----|------|-------|------|----|
| 0.1 | **MCP 2.x shim.** In `run_mcp_server()`: if `Server.__init__` accepts `on_list_tools`, construct with `on_list_tools=` / `on_call_tool=` handlers returning `ListToolsResult` / `CallToolResult`; else use the existing decorators. Re-instate input validation the 2.x SDK dropped by validating `arguments` against `TOOLS[name]["inputSchema"]` with the existing `test_future_proof` schema helpers. Cap becomes `mcp>=1.28.1,<4`; `requirements-pinned.txt` comment corrected. | `neuralmind/mcp_server.py:1284-1296`, `pyproject.toml:80`, `requirements-pinned.txt` | New `tests/test_mcp_transport.py` that spawns `neuralmind-mcp` over stdio and completes `initialize` + `tools/list` + one `tools/call`; parametrised over the installed SDK. New CI step in `fresh-install` that runs it. Add a second `fresh-install` leg with `pip install "mcp<2"` so both lines stay green. | 1.0 |
| 0.2 | **Version single-source.** `__version__ = importlib.metadata.version("neuralmind")` with the literal as fallback for source checkouts; test asserting equality with `pyproject.toml`. Restore release-please as the only bumper (KANBAN's manual "sync version" step is retired). | `neuralmind/__init__.py:112`, `tests/test_version.py` (new) | unit | 0.25 |
| 0.3 | **tree-sitter floor.** `tree-sitter>=0.22`, grammar packages `>=0.23`; `functools.lru_cache` on `_load_language`; the `except Exception: return None` in `_load_language` logs the exception at debug level so a real `TypeError` is no longer reported as "grammar not installed". | `pyproject.toml:130-141`, `neuralmind/graphgen.py:119-165, 205` | existing graphgen tests | 0.25 |

Release notes must say plainly: "v3.10.0–v3.11.3 installed after 2026-08-31
may have a non-starting MCP server; upgrade fixes it." Cursor/Cline/generic
MCP rows in the per-agent table.

---

## Phase 1 — Measure before optimising (v3.12.0)

Delivers Section 6 of the spec. Also the release that carries the retrieval
fixes already specced in `SPEC_PERFORMANCE_IMPROVEMENTS_v3.12.0.md` (Fixes 2–4;
**Fix 1 — pre-loading ONNX in `__init__` — is withdrawn**, see Phase 2).

| WP | Work | Test / gate | ED |
|----|------|-------------|----|
| 1.1 | `tests/benchmark/perf.py` emitting the Section 6 JSON; corpora `synthetic-{100,1k,10k}` from `generate_synthetic_repo` (moved to `tests/benchmark/corpora.py`) + `sample_project`. Spawn-isolated per measurement; `getrusage` for RSS; N=50 warm queries; hooks timed end-to-end via `subprocess` with stdin JSON exactly as Claude Code sends it. | self-test on `synthetic-100` in the main test job (`perf` marker) | 2.0 |
| 1.2 | Timings in `RetrievalTrace` (`timings_ms`) and `perf_counter` spans in `hooks.py` / `mcp_server.py` entrypoints → `.neuralmind/metrics/*.jsonl`; `neuralmind stats --perf`. | unit | 0.75 |
| 1.3 | `ci-benchmark.yml` job `perf` on a fixed runner label; committed `tests/benchmark/perf_baseline.json`; `tests/test_perf_regression.py` with the Section 6 gating table, initial thresholds set to **today's measured values** so the job is green on day one and every later phase tightens them. Delete the read-cached-results branch in `test_benchmark_regression.py:40`; import `REDUCTION_FLOOR` from one module. Make the tiktoken step fail loudly. | CI | 1.0 |
| 1.4 | Apply `slow` / `integration` / `perf` markers; `--durations=25` in the test job; `test_synapse_latency.py` behind `perf`; fix or delete `bench/benchmark.py` and the hard-coded path in `peptide_benchmark.py` (parametrise the corpus path via env). | CI | 0.75 |
| 1.5 | Publish: `docs/benchmarks/perf.md` generated from the baseline JSON (the same generator that writes the chart), and `site/claims.json` entries for any figure the site will quote, all marked `ci-gated` only if the gate is real. | `tests/test_site_claims.py` | 0.5 |

**Gate values recorded from this checkout (2026-09-15, Linux x86_64 container,
`NEURALMIND_ORT_THREADS=1`, `tests/fixtures/sample_project`, 135 nodes)** —
these become the Phase 1 baseline and the "before" column for every later phase:

| Measurement | Value |
|-------------|-------|
| `import neuralmind.cli` (warm) | ~90 ms |
| `neuralmind _hook …` spawn floor (`NEURALMIND_SYNAPSE_INJECT=0`) | ~105 ms |
| `prompt-submit` hook, index present | ~600–640 ms, **0 bytes of context returned** (empty synapse store) |
| `compress-read` / `edit-activity` / `session-start` hooks | ~105–120 ms each |
| `neuralmind query`, warm index, no daemon | ~630–660 ms |
| No-op `neuralmind build` | ~400 ms |
| Cold `neuralmind build` (incl. first-run model fetch and ONNX session) | ~16.5 s |
| `graph.json` links after builds 1→6 with no file changes | 189 → 193 → 217 → 221 → 225 (`contains` +4 per build) |

The last row is finding B2 reproduced; it is a correctness bug, not a
performance one, and gets its own `fix:` in Phase 4 (or earlier if convenient).

---

## Phase 2 — Edge processes go read-only; the daemon becomes real (v3.13.0)

The architectural change. Everything here is behind the existing kill
switches so a user can revert to v3.12 behaviour with one env var.

| WP | Work | Files | Test / gate | ED |
|----|------|-------|-------------|----|
| 2.1 | **Index stamp** (`.neuralmind/index.stamp`, spec §5.2). Written atomically at the end of `maintain()`; read by `load()`. Includes model id + sha, backend name/version/format, graph/IR/BM25/synapse schema versions, package version. | `core.py`, `turbovec_backend.py`, `embedder.py`, `ir.py`, new `neuralmind/stamp.py` | unit: mismatch on each field → `StaleIndex`; `neuralmind doctor` prints the stamp | 1.5 |
| 2.2 | **Split `build()` → `load()` + `maintain()`** (spec §5.3). `_ensure_built` → `_ensure_loaded`; `create_mind(auto_build=True)` = maintain only if stamp missing/stale. `query()` signature unchanged. | `core.py:488-610, 1256-1264`, `cli.py:1048` | existing suite; new test that `query()` on a fresh index performs zero writes under `graphify-out/` and `.neuralmind/` (assert mtimes) | 2.0 |
| 2.3 | **Hook fast path** (spec §5.4). `main()` short-circuits `_hook` before building the parser; `prompt-submit` and `edit-activity` never call `maintain()` or ONNX; lexical seeds from a persisted `node_names.json` (written by `maintain()`); wall-clock budget `NEURALMIND_HOOK_BUDGET_MS=150`; `"timeout": 5` and `if` predicates in `_hook_block()`; single SQLite connection per hook run. Model download moves to `maintain()` only. | `cli.py:5236+, 6522`, `hooks.py:42-100, 437-452, 511, 532` | `perf.py` gate: `hook.prompt_submit_p95_ms ≤ 250`; unit: hook with no index exits 0 silently within budget | 2.0 |
| 2.4 | **Daemon auto-spawn + idle TTL + hook route.** First edge process with no live discovery file spawns `neuralmind-daemon` detached (once per TTL, guarded by a lock file); `NEURALMIND_DAEMON_IDLE_TTL` default 30 min; `NEURALMIND_DAEMON=0` disables. Hooks `POST /hook/<action>` with a 100 ms budget and fall back locally. Daemon port → 8788 (`server.py` keeps 8787) or, better, OS-assigned port recorded in the discovery file. MCP server shares `ProjectRegistry` (per-project `RLock`, bounded cache). | `daemon.py`, `daemon_client.py`, `hooks.py`, `mcp_server.py:48-70` | integration: two concurrent MCP calls on a cold cache build once; daemon exits after TTL; `perf.py` `hook.prompt_submit_p95_ms ≤ 100` with daemon | 2.5 |
| 2.5 | **Session-start diet.** Decay, team-memory import, and markdown export move off the hook into a daemon job (or a `maintain()` step when no daemon); hook only clears the ephemeral namespace and *requests* the rest via a meta flag. | `hooks.py:319-360` | perf gate for `session-start` ≤ 150 ms | 0.5 |
| 2.6 | Withdraw v3.12.0 spec Fix 1. Document in release notes that the correct cold-start fix is 2.2–2.4, and that ONNX is never constructed in a hook. | docs | — | 0.25 |
| 2.7 | Docs/SEO: `docs/wiki/CLI-Reference.md` env-var table (`NEURALMIND_DAEMON`, `NEURALMIND_DAEMON_IDLE_TTL`, `NEURALMIND_HOOK_BUDGET_MS`), a use-case walkthrough "What happens on every prompt", per-agent expectations table, `pyproject.toml` keywords (`warm-daemon`, `hook-latency`). | per `CLAUDE.md` checklist | `tests/test_docs_claims.py` | 0.5 |

Risk: users with hand-started daemons on 8787 and the graph UI. Mitigation:
discovery file carries the port; `neuralmind doctor` reports both.

---

## Phase 3 — Synapse store: bounded, concurrent-safe, rebuild-safe (v3.14.0)

Schema migration v1 → v2. Independent of Phase 4.

| WP | Work | Files | Test / gate | ED |
|----|------|-------|-------------|----|
| 3.1 | `BEGIN IMMEDIATE` everywhere via one `_write_tx()` context manager with bounded exponential-backoff retry on "database is locked"; per-instance thread-local connection; PRAGMAs once; `executescript(SCHEMA)` only when `meta.schema_version` is absent or lower. Fix `synapse_client.deactivate` (S9). | `synapses.py:377-406, 605-2263`, `synapse_client.py:54` | new `tests/test_synapse_contention.py`: 3 processes (watcher-like, hook-like, MCP-like) hammering one DB for 10 s → zero lost writes, zero swallowed `OperationalError` | 1.5 |
| 3.2 | Co-activation cap `MAX_COACTIVATION_NODES=64` (top-scored by file relevance; remainder = activation bumps only); set-wise learned-half-life update in one `UPDATE … FROM`; batched replay-queue insert; `deactivate_files` in one transaction; `normalize_hubs` in one statement. | `synapses.py:583-644, 1001-1045, 2156-2188`, `synapse_feedback.py:97-115, 214+`, `learned_decay.py`, `synapse_dynamics.py:691-709, 828-833` | perf gate `synapse.reinforce_200files_ms ≤ 50`; unit: batch of 500 ids yields ≤ 64·63/2 pairs | 1.5 |
| 3.3 | Decay gated by `last_decay` (≥ 6 h) and run only from batch/daemon; `wal_checkpoint(TRUNCATE)` + `incremental_vacuum` in the same pass; `auto_vacuum=INCREMENTAL` set by the v2 migration. | `synapses.py:821-959`, `hooks.py:328`, `cli.py:3802` | perf gate `synapse.db_growth_after_100_sessions_mb ≤ 2×` | 1.0 |
| 3.4 | **Rebuild-time remap + GC.** Stable markdown heading IDs (`{file_id}__h_{slug}[_{n}]`); after `maintain()`, remap edges by `(file, heading-slug)` secondary key, mark absent nodes with `last_seen`, delete after 30 days; LTP floor no longer protects orphans; `structural_edges`/`type_edges` rows with `last_seen` older than the current build are removed. | `graphgen.py:899`, `synapses.py:66-69, 1091-1101, 2293-2300`, new `neuralmind/synapse_gc.py` | unit: rename a heading → edge survives; delete a file → its edges gone after grace; perf gate "zero orphans after rebuild" | 2.0 |
| 3.5 | Index `idx_syn_ns_last (namespace, last_activated)`; `edges()`/`transitions()` push merge/ORDER BY/LIMIT into SQL; `ir.export_synapse_bundle` limit becomes a real cap. | `synapses.py:1968, 2131`, `ir.py:703-717` | perf: `edges(limit=100)` on a 1M-row store ≤ 20 ms | 0.75 |
| 3.6 | One ordered migration list (`MIGRATIONS = [(1, …), (2, …)]`) keyed off `meta.schema_version`; `SynapseDynamics` rows fold into it; forward guard (newer schema → read-only + one warning). Pending-review queue → table; `stc_tag` rows capped/pruned. | `synapses.py:401-502`, `synapse_dynamics.py:145-189, 443-463`, `team_memory.py:85-97` | migration tests v0→v2, v1→v2, v2 opened by v1 code | 1.25 |

Release notes: "Your `.neuralmind/synapses.db` is migrated in place on first
use; a backup copy `synapses.db.v1.bak` is kept for one release."

---

## Phase 4 — Build path: atomic, deduplicated, chunked, parallel (v3.15.0)

Independent of Phase 3. WP 4.2 can ship earlier as a `fix:`.

| WP | Work | Files | Test / gate | ED |
|----|------|-------|-------------|----|
| 4.1 | Atomic writes (`tmp` + `os.replace`) for `graph.json`, `index_ir.json`, `ir_meta.json`, BM25 payload, stamp; `indent=None` for machine-read artifacts (`neuralmind export --pretty` for humans). Markdown `content_text` no longer duplicated into `graph.json`. | `graphgen.py:4211`, `core.py:120, 795, 1161, 1224`, `ir.py:469`, `bm25.py:252-270` | unit: kill -9 mid-write leaves the previous artifact intact | 1.0 |
| 4.2 | **Edge dedup** on `(relation, source, target, source_location)` in `add_edge`; doc/schema files participate in `changed_set` so carry-over and re-emit cannot both happen. | `graphgen.py:423-445, 1321-1331`, `incremental_extract.py:162` | regression test: `len(links)` identical across 3 no-op builds on `sample_project` (today 189→193→217) | 0.75 |
| 4.3 | Single ignore-pruned `os.scandir` walk → `{suffix: [paths]}`; `.neuralmindignore` parsed once; live-path `set` instead of per-node `exists()`; file-size cap 2 MB with logged skip. | `graphgen.py:1193-1359`, `incremental_extract.py:119` | perf gate `build.incremental_noop_s / build.cold_s ≤ 0.10` | 1.0 |
| 4.4 | Content-hash cache extended to markdown/YAML/SQL/proto; Louvain skipped when nothing changed; `extraction_cache.json` carries `schema_version` → full rebuild on mismatch. | `graphgen.py:920, 1076-1140, 1152-1167`, `incremental_extract.py` | unit | 1.0 |
| 4.5 | Chunked embedding (2,048 per chunk, persist per chunk); dynamic padding; `_BATCH=64`; prefetch `(node_id, uid, content_hash)` in one SELECT; BM25 build skipped when nothing changed; opt-in int8 model `NEURALMIND_EMBED_QUANT=int8` with its own stamp `model_id`. | `turbovec_backend.py:806-849, 1137-1200`, `onnx_embedder.py:44, 133` | perf gate: `synthetic-10k` cold build under the RSS gate; `embed.vectors_per_s` ≥ 1.5× baseline | 1.5 |
| 4.6 | `ProcessPoolExecutor` for pass-1 extraction (`NEURALMIND_BUILD_WORKERS`, default `min(4, cpu)`), pass 2 unchanged; graceful fallback to in-process when the pool cannot start (sandboxes, Windows spawn quirks). | `graphgen.py:1292-1311` | test that parallel output == serial output byte-for-byte | 1.5 |
| 4.7 | `graphify-out/` → `.neuralmind/` consolidation behind a single `paths.py` resolver with legacy fallback (already on `ROADMAP.md`). | ~12 modules | existing suite + migration test | 1.25 |

---

## Phase 5 — Retrieval constant factors, backend contract, dependency posture (v3.16.0 and onward)

A set of independent work packages; ship in any order across releases.

| WP | Work | Files | Test / gate | ED |
|----|------|-------|-------------|----|
| 5.1 | BM25 posting lists; payload header with `tokenizer`/`mode`; lazy load; code projects index code nodes or skip BM25 entirely (decide by measurement in `evals/quality`). | `bm25.py`, `turbovec_backend.py:1164` | perf: `query.warm_p95_ms` scaling exponent ≤ 1.15 over the three synthetic corpora | 1.5 |
| 5.2 | turbovec `search` batched hit fetch; community summaries precomputed per load; prose cross-chapter expansion over an adjacency map; single query embedding shared by `impact()`/`synaptic_neighbors()`. | `turbovec_backend.py:912-968, 1047`, `context_selector.py:724-734, 1875-1891`, `core.py:1542, 1608` | same gate | 1.0 |
| 5.3 | **`VectorBackend` protocol** (spec §5.9) + `evals/parity` as the conformance suite; selector talks only to the protocol; the duplicated `_node_to_text`/`_node_metadata` collapse into one module. Chroma `get_stats` sampling bug fixed (R6). | new `neuralmind/backends/protocol.py`, `context_selector.py:580-1598`, `embedder.py:610` | parity suite green for turbovec and chroma | 2.5 |
| 5.4 | Tuned weights → `.neuralmind.yaml` `retrieval:` section with today's values as defaults and their provenance in comments; docstring/behaviour drift (R8) resolved; `terminology.py` and `_PROSE_CHAPTER_INTENT_WEIGHTS` become a per-project plug-in (`.neuralmind/domain/*.yaml`) loaded only when present. | `context_selector.py`, `terminology.py`, `retrieval_enhancement.py` | `evals/quality` and the peptide benchmark unchanged with the plug-in present; faster without | 1.5 |
| 5.5 | Dependency posture: `turbovec>=0.7,<2` + nightly `canary-deps.yml` (latest turbovec, mcp, onnxruntime, tree-sitter → `evals/parity` + `tests/test_mcp_transport.py`); ChromaDB re-labelled "supported fallback"; `watchdog` declared as an extra and the polling watcher demoted. | `pyproject.toml`, `.github/workflows/canary-deps.yml` (new) | nightly | 0.75 |
| 5.6 | Python matrix: 3.13 required; 3.14 and 3.14t informational; drop 3.10 the release after 2026-10-04; `docs/COMPATIBILITY.md` regenerated from the matrix; `datetime.utcnow()` and `tarfile.extractall(filter=)` fixed; locks around `_mind_cache` and the turbovec SQLite handle for free-threaded correctness; `mypy` required for `synapses.py`, `core.py`, `hooks.py`. | `ci.yml`, `export.py:273`, `onnx_embedder.py:122`, `mcp_server.py:48`, `turbovec_backend.py:153` | CI | 1.0 |
| 5.7 | **Embedding experiments** (informational rows only): Model2Vec `potion-base-32M` as an in-process hook-side embedder; EmbeddingGemma-300M ONNX as opt-in code model; offline-optimised ORT graph for the default MiniLM. Each recorded with `model_id` in the stamp; none becomes default without an `evals/quality` win. | `bge_embedder.py` seam | perf rows + `evals/quality` | 1.5 |
| 5.8 | `server.py`: `daemon_threads=True`, `/api/graph` paginated/capped (nodes and edges), SSE thread per tab replaced by a single fan-out thread. | `server.py:26, 340, 479-491, 745` | integration | 0.75 |
| 5.9 | Monolith splits, mechanically: `neuralmind/commands/<verb>.py` with an entry-point group and `cmd_*` returning `int`; `neuralmind/graphgen/lang/<name>.py` registering into `_EXTRACTORS`. No behaviour change; enables third-party language and command plug-ins. | `cli.py`, `graphgen.py` | existing suite | 2.5 |

---

## Sequencing and dependencies

```
Phase 0 ──► Phase 1 ──► Phase 2 ──┬──► Phase 3 ──┐
                                  └──► Phase 4 ──┴──► Phase 5 (any order)
```

- Phase 2 depends on Phase 1 only for its gates; the stamp (2.1) is a
  prerequisite for 3.4 (remap needs to know a rebuild happened), 4.4 (schema
  versioning) and 5.7 (model identity).
- Phase 4's WP 4.2 (edge dedup) is a correctness fix and may ship as a
  `fix:` at any time, including in Phase 0 if the reviewer prefers.
- Nothing in Phase 5 blocks a release; treat it as the standing backlog.

---

## Risks and mitigations

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Daemon auto-spawn surprises users or is blocked by sandboxes | Medium | Off switch, idle TTL, `doctor` visibility, local fallback path always present; release notes lead with it |
| Synapse v2 migration corrupts a large store | Low | Backup copy, migration inside `BEGIN IMMEDIATE`, tested on a 1M-edge synthetic store in `perf.py` |
| Perf gates flake on shared runners | High (today's harness already shows AVX-512 bimodality and Windows fsync variance) | Gate ratios and exponents, not absolute ms; fixed runner label; wide 1.5× band; absolute numbers as artifacts only |
| turbovec cap `<2` blocks a needed fix upstream | Low | Cap is on the major only; canary tells us early; quarantine path already handles format breaks |
| Dropping Python 3.10 loses users | Low | Announce a release ahead; upstream EOL and onnxruntime's wheel sunset make it unavoidable |
| Read-only hooks return less context while the index is stale | Medium | Stamp-driven background rebuild in the daemon; hook output includes a one-line "index N minutes stale" hint when > 1 h |
| Scope creep from Phase 5 into earlier releases | Medium | Phases 0–4 have explicit exit gates; anything else is Phase 5 |

---

## What "done" looks like

A Claude Code user on v3.16.0 with a 10k-file repo sees: install → first
`build` runs once (parallel, chunked, atomic); every prompt thereafter costs
≤ 100 ms of hook time and returns learned associations that survived their
last `git pull` and rename; a `git checkout` of 200 files costs the synapse
store tens of milliseconds, not a locked database; `neuralmind stats --perf`
shows them the numbers; and the site quotes the same numbers, marked
CI-gated, because they are.
