# Performance & Future-Proofing — Research Findings and Technical Spec

**Status:** DRAFT for review
**Date:** 2026-09-15
**Baseline:** v3.11.3 (`main` @ `883371f`)
**Companion:** [`PERFORMANCE-FUTURE-PROOFING-PLAN.md`](PERFORMANCE-FUTURE-PROOFING-PLAN.md) (phased delivery plan)
**Supersedes / extends:** `SPEC_PERFORMANCE_IMPROVEMENTS_v3.12.0.md` (repo root) and
`SESSION_PROMPT_PERFORMANCE_FIXES.md`, which cover retrieval quality on one prose
corpus. This document covers the whole runtime: hooks, CLI, MCP, daemon, build,
synapse store, dependencies, and measurement.

> Scope note. `CLAUDE.md` routes BRD/TRD strategy documents to the private
> `neuralmind-marketing` repo. This is an engineering spec that references
> `file:line` in this repo and feeds `docs/specs/` like the two benchmark specs
> already here, so it lives here. Move it if you prefer.

---

## 0. Executive summary

NeuralMind is mature: the retrieval pipeline, incremental graph extraction,
turbovec quarantine/recovery, hook fail-open discipline, and the claims
provenance guard are all genuinely well engineered. The audit found that the
remaining performance problems are **architectural, not algorithmic** — the
same expensive work is repeated in the wrong process at the wrong time — plus
a handful of **shipped-broken or drifting** items that a future-proofing pass
must clear first.

The six findings that matter most, in priority order:

| # | Finding | Evidence | Impact |
|---|---------|----------|--------|
| P0-1 | **`neuralmind-mcp` crashes at startup on a fresh install.** Dependabot commit `1eadb8d` (2026-08-31) lifted the cap to `mcp<3` and pinned `mcp==2.1.1`; MCP Python SDK 2.0.0 (2026-07-28) removed `Server.list_tools()` / `Server.call_tool()` decorators that `mcp_server.py:1286-1291` use. Reproduced: `mcp==2.2.0` → `hasattr(Server('x'),'list_tools') == False`. The CI fresh-install job only *imports* `mcp_server` (`ci.yml:178-181`), so it passes. | `pyproject.toml:80`, `requirements-pinned.txt` (comment still says "Held at 1.x"), `mcp_server.py:1284-1296` | Every v3.10.0+ user who installed after 2026-08-31 with a fresh resolver gets a dead MCP server. Cursor / Cline / generic-MCP users have no other integration path. |
| P0-2 | **Every hook and CLI query runs a full `build()` in a fresh process.** `UserPromptSubmit` → `_spread_for_prompt` → `NeuralMind(cwd).synaptic_neighbors()` → `_ensure_built()` → `build()` (graphgen walk + re-hash, `graph.json` re-write with `indent=2`, IR materialize + write, per-node SQLite SELECT, unconditional BM25 rebuild, structural index over all edges) and *then* constructs an ONNX session to embed the prompt. Same for `neuralmind query`. **Measured on this checkout:** ~600 ms per prompt at 135 nodes and ~1.5 s per prompt at 10,220 nodes, returning 0 bytes of context in both cases (Section 1.1). | `hooks.py:437-452`, `core.py:1256-1264`, `core.py:488-610`, `core.py:1099-1164`, `turbovec_backend.py:806-849`, `cli.py:1048` | Per-prompt cost grows with repo size because the hook re-walks the repo. This is the root cause of the "P95 14.9 s" and "3.5 s first query" numbers in the two existing perf docs, and it sits synchronously in front of every prompt. The v3.12.0 spec's Fix 1 (pre-load ONNX in `__init__`) would move that cost *onto* every hook, not off it. |
| P0-3 | **Learned memory does not survive rebuilds, and the store cannot shrink.** Markdown heading node IDs embed a line index (`graphgen.py:899`); nothing garbage-collects synapse edges whose nodes vanished; edges reaching 5 activations get `LTP_FLOOR=0.20 > PRUNE_THRESHOLD=0.01` and become immortal (`synapses.py:66-69`, `:2293-2300`); `structural_edges`/`type_edges` never decay; no `VACUUM`/checkpoint anywhere; `last_decay` is written but never read, so full-table decay runs on every SessionStart and every 600 s in `watch`. | `synapses.py:821-959`, `hooks.py:328`, `cli.py:3802` | Months-old installs on large repos accumulate a DB of orphaned, unprunable edges that every decay tick rewrites in full. |
| P0-4 | **Multi-writer SQLite without `BEGIN IMMEDIATE` or busy retry.** Watcher, hooks, MCP server, CLI and daemon all write `synapses.db`; 13 of 14 write transactions use deferred `BEGIN` (`synapses.py:605…2263`), which in WAL mode returns `SQLITE_BUSY` on read→write upgrade *without* invoking the 30 s busy handler. Every caller swallows the exception. `reinforce()` is O(n²) in batch size with no cap (`synapses.py:583-588`); a checkout touching 200 files can enqueue millions of pairs in one transaction. | `synapses.py:377-384, 583-588`, `synapse_feedback.py:97-115`, `watcher.py:33` | Silent learning loss under contention; occasional multi-second lock stalls on a hook. Not covered by any test (`test_synapse_latency.py` scales store size, not batch size). |
| P1-5 | **No end-to-end latency, cold-start, build-time, memory or scaling measurement exists — and nothing gates them.** `tests/benchmark/latency.py` measures only synapse store ops on a synthetic 4k-node store; `run.py` measures token ratio and hit rate; the good harness (`bench/benchmark_turbovec.py`: RSS, index bytes, p50/p95) is referenced by no workflow. `hooks.py` and `core.py` contain zero timers. `REDUCTION_FLOOR` is defined twice. The regression test reads a gitignored `results.json` and skips when no graph is present. | `tests/benchmark/*`, `tests/test_benchmark_regression.py:26-42`, `.github/workflows/ci-benchmark.yml` | A performance program cannot claim wins or prevent regressions until this exists. It is the first deliverable in the plan. |
| P1-6 | **Dependency and platform drift.** `turbovec` is PyPI *Development Status 3 – Alpha* (first release 2026-04-13, 1.0.0 2026-08-18) and is the *default* vector backend, uncapped. `tree-sitter>=0.21` floor is wrong (code uses the 0.22+ single-arg `Language()`; installed 0.26.0). `__version__` in `neuralmind/__init__.py:112` is `3.10.0` while `pyproject.toml` is `3.11.3` (manual version bumps bypassed release-please's `version-file`). `docs/COMPATIBILITY.md` claims Python 3.13 "actively tested"; CI stops at 3.12 and Python 3.10 reaches end-of-life in October 2026; onnxruntime announced it stops shipping 3.10 wheels after 1.23. No embedding-model identity is stored with the index, so a model swap silently mixes vector spaces. | `pyproject.toml:110-127`, `graphgen.py:119-165`, `turbovec_backend.py:464-483`, `ci.yml:45` | Each is small; together they are how a mature project quietly becomes unmaintainable. |

**The architectural answer** (Section 5) is to make per-prompt processes
*read-only and cheap*, move all index maintenance into one warm, idle-expiring
daemon that hooks and MCP share, and stamp every persisted artifact with the
version of the code and model that produced it. Everything else in this
document is a constant-factor improvement layered on that.

---

## 1. Method

1. Static audit of the hot paths by five parallel read-throughs (retrieval,
   synapse store, process startup/hooks/MCP/daemon, build/indexing,
   measurement/CI), each producing `file:line` evidence. Headline claims were
   independently re-verified in source before inclusion here.
2. Reproduction where a claim was cheap to prove: the MCP 2.x crash was
   reproduced in a scratch venv; import cost was measured with
   `python -X importtime`.
3. External research on the dependency surface (MCP SDK, turbovec, ONNX
   Runtime, py-tree-sitter, CPython free-threading, embedded vector stores,
   small embedding models, Claude Code hook contract). Sources in Section 9.
4. Cross-check against the repo's own performance notes
   (`SPEC_PERFORMANCE_IMPROVEMENTS_v3.12.0.md`, `SESSION_PROMPT_PERFORMANCE_FIXES.md`,
   `tests/benchmark/peptide_report.md`, `docs/HONEST-ASSESSMENT.md`).

Nothing in this document is an invented figure. Where a number is a
projection it is labelled as one.

### 1.1 Measurements taken on this checkout

Linux x86_64 container, Python 3.11.15, clean venv resolving to
`mcp 2.2.0`, `onnxruntime 1.30.0`, `turbovec 1.0.0`, `tree-sitter 0.26.0`,
`numpy 2.4.6`. Wall-clock via `date +%s%N` around the subprocess, 3–5 runs,
values rounded. Fixture = scratch copy of `tests/fixtures/sample_project`;
synthetic = `bench/benchmark_turbovec.generate_synthetic_repo(n_files=600)`.
Fixture runs used `NEURALMIND_ORT_THREADS=1`; the synthetic cold build used
the default thread count.

| Measurement | Fixture (135 nodes) | Synthetic (600 files, 10,220 nodes) |
|-------------|--------------------:|------------------------------------:|
| `import neuralmind.cli` (warm) | ~90 ms | — |
| `neuralmind _hook …` spawn floor (`NEURALMIND_SYNAPSE_INJECT=0`) | ~105 ms | — |
| `prompt-submit` hook, index present | ~600–640 ms | ~1,500–1,650 ms |
| context bytes returned by `prompt-submit` | 0 | 0 |
| `compress-read` / `edit-activity` / `session-start` hooks | ~105–120 ms | ~100 ms (`edit-activity`) |
| `neuralmind query`, warm index, no daemon | ~630–660 ms | ~1,500–1,600 ms |
| No-op `neuralmind build` (nothing changed) | ~400 ms | ~1,300–1,400 ms |
| Cold `neuralmind build` | ~16.5 s (incl. first-run model fetch) | ~192 s |
| `graph.json` size | 113 KB | 6.9 MB |
| `graph.json` links, builds 1→6, no file changes | 189 → 193 → 217 → 221 → 225 | 9,610 (stable; no markdown in corpus) |
| `neuralmind-mcp` startup | `AttributeError: 'Server' object has no attribute 'list_tools'` | same |

Two things to read off this table. First, the hook's cost is the no-op
build plus an ONNX session, and both scale with the repo, so a real 50k-node
repo will sit well above Claude Code's comfort zone on every prompt. Second,
the edge growth is specific to markdown `contains` edges (B2), which is why
the markdown-free synthetic corpus is stable.

---

## 2. What is already good (do not re-propose)

This list exists so reviewers and future implementers don't spend budget
re-solving solved problems.

- **Lazy heavy imports.** numpy, onnxruntime, chromadb, mcp, pydantic,
  cryptography and tree-sitter are all deferred; `import neuralmind.cli` pulls
  only `yaml` + `sqlite3` from third parties (measured ≈90 ms warm in a clean venv with the full vector stack
  installed; bare interpreter ≈11 ms). CI asserts the default install is
  ChromaDB-free (`ci.yml:167-186`).
- **Incremental graph extraction is real.** Content-hash + mtime cache,
  persisted importer index, transitive-importer invalidation, fail-open on a
  corrupt cache, and a test proving incremental output equals a full rebuild
  (`graphgen.py:1170-1391`, `incremental_extract.py`, `tests/test_graphgen.py:1172`).
- **Community-ID carry-over** keeps unchanged nodes byte-identical so the
  embedder's content-hash skip actually fires (`graphgen.py:1093-1137`).
- **turbovec quarantine + rebuild from persisted documents**
  (`turbovec_backend.py:393-471`) — a backend major bump is recoverable, not fatal.
- **IR versioning with an explicit unsupported-version error** (`ir.py:39-46, 481-502`).
- **Synapse store basics:** WAL, `synchronous=NORMAL`, 30 s busy timeout,
  indexed spreading activation that never loads the full edge table,
  `executemany` on the batched writes, a rollback-safe tested v0→v1 migration,
  and a `node_a < node_b` CHECK constraint.
- **Hooks fail open** with per-feature kill switches (`NEURALMIND_BYPASS`,
  `NEURALMIND_SYNAPSE_INJECT`, `NEURALMIND_REUSE_FEEDBACK`) and stdout kept
  clean for the JSON channel.
- **MCP server** loads each project once per process and runs tool work in
  `asyncio.to_thread` so the event loop never blocks (`mcp_server.py:48, 1292`).
- **Daemon** has a transport-free `dispatch()` seam, per-project `RLock`,
  0600 token file, Windows-correct PID liveness, job eviction and graceful
  SIGTERM (`daemon.py`). It is inert only because nothing starts it.
- **Secret-scan prefilter** with measured justification and size caps
  (`secret_scan.py:479-543`) — the best-engineered hot path in the codebase.
- **Claims provenance guard** (`site/claims.json`, `tests/test_site_claims.py`,
  `tests/test_docs_claims.py`) — this is why no latency number has been
  published without a harness. Keep it; the plan adds the harness.
- **Bounded-cost discipline** in several places: betweenness sampling above
  2,000 nodes, doc↔code coupling capped at 50 edges, replay queue capped at
  1,000, team bundle capped at 5,000 entries, `_displace` budget-neutral
  swaps with a documented rationale.

---

## 3. Detailed findings

Each finding has an ID used by the plan. Severity: **P0** ship-blocking or
user-visible today; **P1** materially affects large repos or long-lived
installs; **P2** hygiene / future risk.

### 3.1 Process model and hooks

| ID | Sev | Finding | Evidence |
|----|-----|---------|----------|
| H1 | P0 | `prompt-submit` hook constructs `NeuralMind` and calls `synaptic_neighbors`, which calls `_ensure_built()` → full `build()`, then creates an ONNX `InferenceSession` to embed the prompt. Runs synchronously before every user prompt. | `hooks.py:437-452`, `core.py:1540-1548`, `core.py:1256-1264` |
| H2 | P2 | `edit-activity` hook constructs `NeuralMind` per Edit/Write but does **not** build (`record_edit_activity` never calls `_ensure_built`); measured at the ~100 ms spawn floor. Listed so nobody "fixes" it. | `hooks.py:511-528`, `core.py:360` |
| H3 | P1 | `build()` on the query path re-runs `graphgen.build_graph()` (walk + hash every file), **rewrites `graph.json` with `indent=2` unconditionally**, materialises and writes `index_ir.json`, issues one SQLite SELECT per node in `embed_nodes`, and rebuilds BM25 from a full table scan even when zero nodes changed. | `core.py:1099-1164`, `core.py:762-798`, `turbovec_backend.py:806-849, 1137-1200` |
| H4 | P1 | `main()` builds the entire 59-subcommand argparse tree before dispatching the hidden `_hook` subcommand. `cli.py:13` and `mcp_server.py:42` prepend to `sys.path` at import time. | `cli.py:5236-6751, 6522` |
| H5 | P1 | Hooks never use the daemon; only `cmd_query`/`cmd_stats` try it, and the daemon must be started by hand. No idle auto-shutdown. Daemon port 8787 collides with `server.serve` default 8787. | `cli.py:693, 1011, 1825`, `daemon.py:48`, `server.py:717` |
| H6 | P1 | `compress-read`/`edit-activity` open three separate SQLite connections per tool call; every `SynapseStore` method opens its own connection and re-issues PRAGMAs; `executescript(SCHEMA)` runs on every store construction (~15 construction sites per session). | `hooks.py:532`, `synapses.py:377-406` |
| H7 | P1 | No `timeout` key on any registered hook. Claude Code's default is 600 s for command hooks and 30 s for `UserPromptSubmit`; a wedged hook stalls the session for that long. First-ever run may download a ~90 MB model *inside the hook* with 3 retries. | `hooks.py:42-100`, `onnx_embedder.py:92-123` |
| H8 | P1 | `session-start` runs full-table `decay()`, team-memory import (score every incoming and existing bundle edge, per-row import, staleness pass) and markdown export (5 aggregate scans + degree group-by) inline. | `hooks.py:319-360`, `team_memory.py:203-353`, `synapse_memory.py:90-216` |
| H9 | P2 | Query path performs synchronous JSONL append + compaction, SQLite reinforcement and audit write inline after retrieval. | `core.py:1339-1353` |

### 3.2 Retrieval hot path

| ID | Sev | Finding | Evidence |
|----|-----|---------|----------|
| R1 | P1 | BM25 `search` scans every document for every query term — no posting lists. O(terms × N). | `bm25.py:162-177, 214` |
| R2 | P1 | turbovec `search` does `SELECT COUNT(*)` plus one `SELECT` per hit (N+1); `_allowlist_uids` materialises the whole filtered uid set. | `turbovec_backend.py:912-968` |
| R3 | P1 | `get_community_summary` is a linear scan over all nodes per community; L1 calls it for 10 communities, L2 for up to `l2_recall_k` more — up to ~13 O(N) scans on first query. | `turbovec_backend.py:1047`, `context_selector.py:724-734` |
| R4 | P1 | `_expand_cross_chapter` iterates the entire edge list for each of the top-3 prose hits. | `context_selector.py:1875-1891` |
| R5 | P1 | BM25 payload stores both `docs` and per-doc `tf` maps as JSON; load holds 2-3× corpus size in RAM; the tokenizer/mode is not persisted, so a prose-tokenised index queried via `search()` uses the code tokenizer. turbovec BM25 indexes only document/chunk nodes, so code projects rebuild an index that RRF then finds empty. | `bm25.py:252-289`, `turbovec_backend.py:1164` |
| R6 | P1 | Chroma `get_stats` samples only the first 1,000 nodes for the community distribution → wrong L0/L1/L2 budgets above 1k nodes. | `embedder.py:610` |
| R7 | P2 | `synapse_seeded_expansion` issues two `LIKE '%ident%'` full-table scans per identifier with an O(n²) dedup; `_search_source_files` (flag-gated) substring-matches every identifier against every node and reads files from disk per candidate. | `retrieval_enhancement.py:569-590, 812-939` |
| R8 | P2 | `_adaptive_weights` computes `doc_count` and ignores it; returned weights (0.5/0.5) contradict its docstring (0.4/0.6) and `_weighted_hybrid_score` defaults (0.7/0.3). `_apply_prose_intent_boost` documents 2.0×/1.5× but applies 1.3×/1.1×. | `context_selector.py:421-422, 1600-1612, 1750-1784` |
| R9 | P2 | `impact()`, `synaptic_neighbors()` and `_resolve_node_id()` each embed the query again. | `core.py:1542, 1608` |
| R10 | P2 | mtime-based "prefer IR over graph.json" flip-flops because `build()` rewrites both. | `turbovec_backend.py:500-509`, `embedder.py:119-128` |

### 3.3 Build and indexing

| ID | Sev | Finding | Evidence |
|----|-----|---------|----------|
| B1 | P1 | turbovec embeds the entire pending set in one `_embed_matrix` call — all changed texts + a full `(n,384)` float32 matrix resident. Fatal on a cold build of a very large repo. | `turbovec_backend.py:849` |
| B2 | P1 | `_GraphBuilder.add_edge` never dedups, and doc/schema files are never in `changed_set`, so markdown `contains`/`describes` edges are both carried over *and* re-emitted each incremental build. Likely monotonic growth of `graph["links"]`. **Needs a reproduction test before fixing.** | `graphgen.py:423-445, 1321-1331`, `incremental_extract.py:162` |
| B3 | P1 | Markdown / YAML / SQL / proto extraction is not incremental; every YAML in the repo (CI, compose, k8s) is `yaml.safe_load`ed every build with no size cap. | `graphgen.py:920, 1321-1331` |
| B4 | P1 | Six full filesystem walks per build (`detect_project_kind`, unfiltered `rglob("*")` that walks `node_modules`/`.venv` then filters, `_iter_source_files` twice, markdown walk, schema walk); `.neuralmindignore` re-parsed per walk; one `exists()` stat per graph node. | `graphgen.py:1193-1359`, `incremental_extract.py:119` |
| B5 | P1 | `graph.json`, `index_ir.json`, `ir_meta.json` written non-atomically (`write_text`, no tmp + `os.replace`) and pretty-printed (`indent=2` ≈ 2× size). A mid-write interrupt corrupts the index → silent full rebuild. Markdown `content_text` is stored verbatim in `graph.json`, so prose repos duplicate the whole book. | `graphgen.py:4211`, `core.py:120, 795, 1161, 1224`, `ir.py:469` |
| B6 | P1 | ONNX pads every batch to the full 256 tokens; `_BATCH=32`; fp32 only. No file-size cap in graphgen (`document_ingestion.py` has 10 MB). | `onnx_embedder.py:44, 133`, `graphgen.py:1298` |
| B7 | P1 | Zero parallelism in build (no `ProcessPoolExecutor` anywhere in graphgen or embed path). | `graphgen.py`, `turbovec_backend.py` |
| B8 | P2 | Louvain runs on every build even when every file's community is carried over; one `frozenset` allocated per edge visit. | `graphgen.py:1076-1140`, `modularity.py:141-148` |
| B9 | P2 | `SCHEMA_VERSION` bump in graphgen does not invalidate the extraction cache or existing graph (only `generated_by` is checked); turbovec SQLite schema is versioned only by `ALTER TABLE … except: pass`; `.tvim` has no readable version. | `graphgen.py:1152-1167`, `turbovec_backend.py:208-227, 316-343` |
| B10 | P2 | `graphify-out/` legacy path hard-coded in ~6 places; `ROADMAP.md` already lists consolidation to `.neuralmind/`. | `graphgen.py:1158, 4208`, `embedder.py:77`, `turbovec_backend.py:127`, `core.py:1115` |

### 3.4 Synapse store

| ID | Sev | Finding | Evidence |
|----|-----|---------|----------|
| S1 | P0 | `reinforce()` builds all pairs from the full id list with no cap; `activate_files` expands every touched file to *all* its nodes; watcher debounce is 0.75 s. Inside the transaction, `update_learned_half_life` issues a SELECT + UPDATE per pair. | `synapses.py:583-644`, `synapse_feedback.py:97-115`, `watcher.py:33`, `learned_decay.py:128-162` |
| S2 | P0 | 13 of 14 write transactions use deferred `BEGIN`; no `OperationalError` retry anywhere; every caller swallows the exception; export path uses a 2 s timeout and renders "none yet" on a locked store. | `synapses.py:605-2263`, `synapse_memory.py:90,130`, `hooks.py:326-330`, `synapse_client.py:44-47` |
| S3 | P0 | Orphaned edges: nothing joins `synapses` against the live node set after a rebuild; markdown heading IDs embed the line index; `LTP_FLOOR > PRUNE_THRESHOLD` makes ≥5-activation edges immortal; `structural_edges`/`type_edges` never decay; `synapses_dynamics_meta` gains one `stc_tag` row per pair forever; no VACUUM/checkpoint. | `graphgen.py:899`, `synapses.py:66-69, 1091-1101, 2293-2300`, `synapse_dynamics.py:443-463` |
| S4 | P1 | `decay()` rewrites essentially every row (4 UPDATE passes per namespace chunk + prunes) on every SessionStart and every 600 s in `watch`; `last_decay` is written but never read. | `synapses.py:821-959`, `hooks.py:328`, `cli.py:3802, 3902` |
| S5 | P1 | Missing index on `synapses(namespace, last_activated)` — full scans in `prune_stale`, `stats_detailed`, `sleep.prune_redundant_edges`, `team_staleness.detect_stale_in_store`. | `synapses.py:2293, 2307`, `sleep.py:158`, `team_staleness.py:111` |
| S6 | P1 | `edges()`/`transitions()` select a whole namespace into Python, merge, sort, then slice; `ir.export_synapse_bundle` passes `limit=100_000`. | `synapses.py:1968, 2131`, `ir.py:703-717` |
| S7 | P1 | `SynapseDynamics.reinforce` enqueues one replay row per pair, each in its own connection with `COUNT(*)` + conditional DELETE. `deactivate_files` runs one transaction per node. `normalize_hubs` runs one UPDATE per hub on every PreCompact. | `synapse_dynamics.py:691-709, 828-833`, `synapse_feedback.py:214+`, `synapses.py:2156-2188`, `hooks.py:410` |
| S8 | P2 | Two independent migration systems (`meta.schema_version` + ad-hoc `_has_column` ALTERs, and `SynapseDynamics`' own version table); no forward-compat guard when a newer schema is opened by older code. Pending-review queue is one JSON blob rewritten per append. | `synapses.py:401-433`, `synapse_dynamics.py:145, 186-189`, `team_memory.py:85-97` |
| S9 | P2 | `synapse_client.deactivate` calls `store.decay(node_ids)` but `decay()` takes a timestamp — silently no-ops under a bare except. | `synapse_client.py:54`, `synapses.py:821` |

### 3.5 Dependencies, platform, versioning

| ID | Sev | Finding | Evidence |
|----|-----|---------|----------|
| D1 | P0 | `mcp>=1.28.1,<3` admits 2.x; server uses removed decorator API; fresh install crashes. Pinned file says `mcp==2.1.1` under a comment that says "held at 1.x". CI never runs the server. | `pyproject.toml:80`, `requirements-pinned.txt`, `mcp_server.py:1284-1296`, `ci.yml:178-181` |
| D2 | P1 | `turbovec` (default backend) is PyPI Alpha, five months old, uncapped. Recovery path exists, but a behavioural (not format) regression upstream lands directly in every user's default install with no cap and no canary. | `pyproject.toml:110-127` |
| D3 | P1 | `tree-sitter>=0.21.0` floor is below what the code needs (0.22+ `Language(capsule)`); on 0.21 the `TypeError` is swallowed and surfaces as "grammar not installed". `_load_language` is uncached. | `graphgen.py:119-165, 205`, `type_verifier.py:177-191` |
| D4 | P1 | `__version__` drift: `neuralmind/__init__.py:112` = `3.10.0`; `pyproject.toml` = `3.11.3`. The v3.11.x bumps were manual (`a5ed0df "chore: sync version"`), bypassing release-please's `version-file`. `neuralmind --version` and the daemon health payload report the stale value. | `release-please-config.json:9`, `cli.py:5215`, `daemon.py:565` |
| D5 | P1 | Python matrix 3.10–3.12; no 3.13, 3.14 or free-threaded build; `docs/COMPATIBILITY.md` says 3.13 is tested. Python 3.10 EOL is 2026-10; onnxruntime drops 3.10 wheels after 1.23. Free-threading hazards: unlocked module caches (`mcp_server.py:48`), `check_same_thread=False` SQLite without a guarding lock (`turbovec_backend.py:153`), class-attribute state on `server._Handler`. | `ci.yml:45`, `docs/COMPATIBILITY.md` |
| D6 | P1 | No embedding-model identity in the index. turbovec meta stores only `dim` and `bit_width`; `content_hash` covers node text only. Swapping MiniLM for another model (or a MiniLM revision) leaves old vectors in place and mixes vector spaces silently. 384-d and 256-token limits are hard-coded in several places. | `turbovec_backend.py:383-387, 464-483, 806`, `onnx_embedder.py:44` |
| D7 | P2 | Corpus-specific tables and magic numbers baked into the library: `_PROSE_CHAPTER_INTENT_WEIGHTS` is one book's chapter filenames; `terminology.DRUG_TO_CLASS` (50 drug names) runs on every prose query; `RRF_K=10` commented "for 61-node index"; ~20 tuned weights with no provenance or config surface. | `context_selector.py:374, 500-517, 1464-1490, 1684-1696`, `terminology.py:15-64`, `retrieval_enhancement.py:500-505, 867-875` |
| D8 | P2 | `mypy` job is `continue-on-error`; `slow`/`integration` markers declared but never used; `test_synapse_latency.py` timing test runs unmarked on every matrix cell including Windows (measured 167 ms fsync there vs ~3 ms local). `datetime.utcnow()` and `tarfile.extractall` without `filter=` (3.14 default flips). | `ci.yml:120`, `pyproject.toml:289-292`, `export.py:273`, `onnx_embedder.py:122` |
| D9 | P2 | `cli.py` 6,766 lines / 59 `cmd_*` / 104 `sys.exit()`; `graphgen.py` 4,212 lines with ten language extractors inline; no entry-point seam. Dispatch and the language seam are clean, so both splits are mechanical. | `cli.py`, `graphgen.py:79-99` |
| D10 | P2 | `server.py`: `ThreadingHTTPServer` without `daemon_threads`, one non-daemon thread per SSE client, `/api/graph` returns the entire node/edge set uncapped, polling watcher does `rglob("*")` + `stat()` every 2 s because `watchdog` is not a declared dependency. | `server.py:26, 340, 479-491, 651, 745`, `watcher.py:142-171` |

### 3.6 Measurement and CI

| ID | Sev | Finding | Evidence |
|----|-----|---------|----------|
| M1 | P1 | No end-to-end query latency, cold-start, hook latency, MCP tool latency, build time, index size, RSS, synapse DB growth, or scaling-vs-N benchmark exists in CI. | `tests/benchmark/latency.py:17-21` (explicit disclaimer) |
| M2 | P1 | `bench/benchmark_turbovec.py` already measures index bytes, peak RSS, tracemalloc, search p50/p95 with spawn isolation — but no workflow runs it. | `bench/benchmark_turbovec.py` |
| M3 | P1 | `REDUCTION_FLOOR = 4.0` defined twice with a "keep in sync" comment; regression test returns a cached gitignored `results.json` if present and skips when `graph.json` is absent (the default local state). tiktoken download is `continue-on-error`, so a failure silently changes the gate's units. | `tests/benchmark/run.py:58`, `tests/test_benchmark_regression.py:26-42`, `ci-benchmark.yml:52` |
| M4 | P2 | Orphaned harnesses: `bench/benchmark.py` hard-codes `/a0/usr/workdir/neuralmind`, imports undeclared `psutil`, counts tokens via `len(output.split())` on a `QueryResult`; `peptide_benchmark.py:20` hard-codes a home-directory corpus path. | `bench/benchmark.py:9`, `tests/benchmark/peptide_benchmark.py:20` |
| M6 | P1 | **The quality gates do not protect `main`.** The three v3.12.0 `feat:` commits (`cf85a68`…`51cb0d5`, 2026-09-15) were pushed directly to `main`; the Self-benchmark workflow then failed there (run 1707: faithfulness delta −0.054 vs floor +0.000, identical across three repeats; parity gate fails the same row). Every PR opened since inherits a red Self-benchmark it cannot fix. The next direct push (`d6428dc`…`03ff311`, v3.13.0, 2026-09-16 01:41 UTC) then turned the main `CI` workflow red as well: the Black formatting check fails and the test suite fails on all five OS/Python cells (run 1818), while Self-benchmark stays red (run 1713). Separately, Dependabot PR #517 is open to bump `mcp` 2.1.1→2.2.0, which would keep D1 broken. Direction: branch protection requiring `Self-benchmark` and `fresh-install` on `main`, no direct pushes, and a Dependabot rule that runs the MCP transport test (Phase 0.1) before a major bump can merge. | `.github/workflows/ci-benchmark.yml`, run 34998224547 |
| M5 | P2 | `RetrievalTrace` records relevance attribution but no timings; `metrics_pipeline.py` logs per-query latency to `.neuralmind/metrics/*.jsonl` but nothing reads it. | `context_selector.py:2086-2106`, `neuralmind/metrics_pipeline.py` |

---

## 4. External research — what the ecosystem looks like in September 2026

Findings that change what "future-proof" means for this codebase.

**MCP Python SDK.** 2.0.0 shipped 2026-07-28 as "a major rework"; latest is
2.2.0 (1.30.0 on the 1.x line, 2026-09-07). The low-level `Server` now takes
`on_list_tools=` / `on_call_tool=` constructor kwargs with
`(ctx, params) -> Result` handlers returning `ListToolsResult` /
`CallToolResult`; automatic JSON-schema input validation was removed. The
migration is ~15 lines here because `TOOLS` is plain dicts and
`handle_tool_call` is a sync dict dispatch (`mcp_server.py:1150-1272`). The
1.x line is still receiving releases, so a dual-path shim is cheap and lets the
cap become `<4`.

**turbovec.** PyPI classifier *Development Status 3 – Alpha*; 1.0.0 on
2026-08-18; wheels for manylinux_2_28 x86_64/aarch64, macOS arm64, win_amd64
only. This is the default backend for every user. The recovery path for
format breaks exists; what does not exist is protection against a *behavioural*
regression (ranking, quantisation error) shipping straight into the default
install. The plan adds a nightly canary and an upper cap on the *major*
(`<2`) with an explicit re-evaluation trigger, and keeps ChromaDB as the
supported fallback rather than the "legacy" one.

**ONNX Runtime.** Session creation cost is dominated by online graph
optimisation; the documented mitigation is offline optimisation (serialise the
optimised graph once, load with optimisations disabled) or the ORT model
format with saved runtime optimisations. 1.24.x ships Python 3.13/3.14
wheels; the project announced it stops publishing 3.10 wheels after 1.23.

**Embedding models.** `all-MiniLM-L6-v2` remains the right *default* at
this size (≈46 MB, 384-d, ~15 ms/1k tokens on CPU). Two directions worth an
experiment, not a default change: (a) **Model2Vec static embeddings**
(`potion-base-32M`: ~70× faster than MiniLM on CPU at ~92 % of its retrieval
quality, no ONNX session at all, so hooks could embed a prompt in-process in
single-digit ms); (b) **EmbeddingGemma-300M** as an opt-in higher-quality
model for code (best MTEB-Code score in its size class, but ~620 MB — an
opt-in like the existing `bge-large` path). Either requires D6 (model identity
in the index) first.

**py-tree-sitter.** 0.25/0.26 removed `Language.version` (→ `abi_version`),
`Language.query()` (→ `Query(language, source)`), and `keep_text`. Grammar
packages ≥0.23 return capsules that older cores cannot accept. The code
already targets the capsule form; the floor must say so. `_make_parser`
already handles the Parser churn.

**CPython.** 3.10 EOL October 2026. Free-threaded builds are officially
supported in 3.14 (5–10 % single-thread overhead; C extensions without the
free-threading flag silently re-enable the GIL). The relevant risk for this
codebase is not speed but correctness of unlocked shared state under a
free-threaded interpreter; the plan adds a `3.14t` CI leg as *informational*
first.

**Embedded vector search.** `sqlite-vec` (exact brute-force, fine to low
millions), usearch (HNSW), and binary/int8 quantisation are all viable
in-process options; none is obviously better than turbovec for this workload
today. The right investment is the **backend contract** (a versioned
`VectorBackend` protocol with parity tests) so any of them can be swapped in
without touching the selector, rather than another migration.

**Claude Code hooks.** Command-hook default timeout 600 s; `UserPromptSubmit`
30 s; `SessionEnd` 1.5 s shared budget; `async: true` and `asyncRewake: true`
exist for command hooks; the docs recommend the `if` field to avoid spawn
overhead and treat a timed-out hook as non-blocking. New event types since the
hooks were written (`PostToolBatch`, `PostCompact`, `FileChanged`,
`SubagentStart/Stop`) are directly relevant: `FileChanged` can replace the
polling watcher for Claude Code users and `PostToolBatch` can replace per-tool
`compress-read` spawns.

---

## 5. Target architecture

### 5.1 Principle: three process classes, one owner of mutation

| Class | Examples | Contract |
|-------|----------|----------|
| **Edge process** (short-lived, many per minute) | every `neuralmind _hook …`, `neuralmind query` without daemon | **Read-only. Never builds. Never embeds with ONNX.** Hard wall-clock budget (default 150 ms, `NEURALMIND_HOOK_BUDGET_MS`). If no fresh index exists, emit nothing and exit 0. If a daemon is reachable, forward and return; otherwise do the cheap local thing (SQLite spread from lexical seeds, tool-transition record). |
| **Warm service** (one per user, idle-expiring) | `neuralmind-daemon`, `neuralmind-mcp` | Owns the loaded graph, ONNX session, BM25 index and synapse store connection per project. Serialises mutations per project. Auto-spawned by the first edge process that needs it; exits after `NEURALMIND_DAEMON_IDLE_TTL` (default 30 min). |
| **Batch job** | `neuralmind build`, `watch`, CI autoindex, decay/sleep passes | Only class allowed to run graphgen, embed, rebuild BM25, decay, vacuum, or import team memory. Atomic artifact writes. |

Today all three classes run the batch job's code path. That is finding H1–H3
in one sentence.

### 5.2 Index freshness without a rebuild

Introduce `.neuralmind/index.stamp` (JSON, written atomically at the end of
every successful batch job):

```json
{
  "stamp_version": 1,
  "graph_sha256": "…",          "graph_schema_version": 3,
  "ir_version": 2,
  "embedding": {"model_id": "all-MiniLM-L6-v2", "model_sha256": "…", "dim": 384, "max_tokens": 256},
  "vector_backend": {"name": "turbovec", "version": "1.0.0", "index_format": 5},
  "bm25": {"version": 2, "tokenizer": "prose"},
  "synapse_schema_version": 1,
  "neuralmind_version": "3.12.0",
  "built_at": 1757980000.0
}
```

Edge processes and the warm service **load if the stamp matches what the
running code expects; otherwise they degrade** (edge: no output; service:
schedule a batch rebuild and serve the old index until it lands). The stamp
replaces the mtime heuristic (R10), gives D6 its model identity, and gives B9
its schema gating in one artifact. A model or backend change *invalidates by
construction* instead of silently mixing spaces.

### 5.3 Split `build()` into `load()` and `maintain()`

- `NeuralMind.load()` — read stamp, mmap/load vectors, load BM25, open synapse
  store. No writes. Used by edge and service.
- `NeuralMind.maintain(force=False)` — the current `build()` body, plus atomic
  writes, plus stamp. Used only by batch jobs and by the service's background
  rebuild.
- `_ensure_built()` becomes `_ensure_loaded()`, and raises
  `GraphNotBuiltError` (already exists) instead of building.
- `create_mind(auto_build=True)` keeps its signature (the query interface must
  not change — `SESSION_PROMPT_PERFORMANCE_FIXES.md` rule 5) but `auto_build`
  means "maintain if the stamp is missing or stale", not "always".

### 5.4 Hook fast path

```
neuralmind _hook prompt-submit
  ├─ parse argv[1:3] only (no argparse tree)          ~1 ms
  ├─ read stdin JSON                                  ~0 ms
  ├─ daemon discovery file present & alive?
  │     yes → POST /hook/prompt-submit, 100 ms budget → print → exit 0
  │     no  → spawn daemon detached (once per TTL), fall through
  ├─ stamp present & matches?  no → exit 0 (silent)
  ├─ lexical seeds: top-k node ids by identifier match from a
  │     small persisted `node_names.json` (no ONNX)              ~5 ms
  ├─ SynapseStore.spread(seeds, depth=2, top_k=8)                ~5–20 ms
  └─ print context, exit 0
```

Registered hook entries gain `"timeout": 5` (seconds), and `compress-read` /
`edit-activity` gain an `if` predicate so Claude Code skips the spawn for
tools that cannot produce a hit. Where the client supports `PostToolBatch`,
register one batch hook instead of three per-tool hooks. Where it supports
`FileChanged`, prefer it over the polling watcher.

### 5.5 Synapse store hardening

- All write transactions `BEGIN IMMEDIATE`; one `_write_tx()` wrapper with
  bounded exponential-backoff retry on `OperationalError: database is locked`.
- Co-activation batch cap: `MAX_COACTIVATION_NODES = 64` (env-tunable). Above
  the cap, keep the top-scored 64 by file relevance and record the rest as
  activation counts only. Reject batches early with a debug log.
- `decay()` gated by `last_decay` (skip if < 6 h) and executed only by batch
  jobs / the service; hooks *request* a decay via a meta flag.
- Rebuild-time **remap + GC**: after `maintain()`, join `synapses` against the
  live node set; migrate edges whose IDs changed only by the line-index suffix
  (markdown headings) using a `(file, heading-slug)` secondary key; delete
  edges whose nodes are gone (with a 30-day grace via `last_seen`).
- Immortality fix: LTP floor applies only while both endpoints are live; a
  `PRUNE_ORPHANS` pass ignores the floor.
- Stable IDs for markdown headings: `{file_id}__h_{slug(heading)}[_{n}]` with
  `n` disambiguating duplicates, no line number.
- Add index `idx_syn_ns_last (namespace, last_activated)`. Push
  merge/ORDER BY/LIMIT for `edges()`/`transitions()` into SQL.
- One connection per store instance (thread-local), PRAGMAs once, schema
  `executescript` guarded by the `meta.schema_version` check.
- Periodic `PRAGMA wal_checkpoint(TRUNCATE)` + `PRAGMA incremental_vacuum`
  in the batch decay pass; `auto_vacuum=INCREMENTAL` set on creation (v2
  migration for existing DBs).
- Single ordered migration list keyed off `meta.schema_version`, forward
  guard (`recorded > SCHEMA_VERSION` → open read-only, warn once).
- Replay queue: batched insert + periodic trim. Pending-review queue: a table.

### 5.6 Build path

- One filesystem walk producing `{suffix: [paths]}` with ignore-pruned
  `os.scandir`; `.neuralmindignore` parsed once.
- Extend the content-hash cache to `_DOC_SUFFIXES` + `_SCHEMA_SUFFIXES`.
- `add_edge` dedup on `(relation, source, target, source_location)`; a test
  asserting `len(links)` is stable across three no-op incremental builds
  (this doubles as the B2 reproduction).
- Atomic writes (`tmp` + `os.replace`) for every artifact; drop `indent` for
  machine-read files; `content_text` for markdown moved out of `graph.json`
  into the store's `document` column (it is already persisted there).
- Chunked embedding (2,048 texts per chunk, persist per chunk); dynamic
  padding to per-batch max length; `_BATCH` 64; optional int8 model behind
  `NEURALMIND_EMBED_QUANT=int8`.
- `ProcessPoolExecutor` for pass-1 symbol extraction across files of one
  language (`NEURALMIND_BUILD_WORKERS`, default `min(4, cpu_count)`); pass 2
  stays single-process.
- File-size cap 2 MB with a logged skip; Louvain skipped when `changed_set`
  is empty and no new files.
- `extraction_cache.json` carries `schema_version`; mismatch → full rebuild.

### 5.7 Retrieval

- BM25 posting lists (`term → [(doc_idx, tf)]`), persisted with `tokenizer`
  and `mode` in the payload header; loaded lazily; BM25 build skipped when
  `added + updated == 0`. Code projects either index code nodes too or skip
  the build entirely.
- turbovec `search`: batch the hit fetch (`WHERE uid IN (…)`), drop the
  `COUNT(*)`.
- Community summaries: precomputed once per load into a dict.
- Prose cross-chapter expansion over an adjacency map, not the edge list.
- Config surface for tuned weights: `neuralmind-retrieval.yaml` (or the
  existing `.neuralmind.yaml`) with the current values as defaults and the
  corpus they were tuned on recorded in a comment; domain tables
  (`terminology.py`, chapter intent weights) become optional plug-ins loaded
  from the project, not the library.
- Fix the docstring/behaviour drift in R8 (either direction, but recorded).

### 5.8 Dependencies and versioning

- `mcp>=1.28.1,<4` with a transport shim: try 2.x constructor kwargs, fall
  back to 1.x decorators. Add a CI step that actually starts `neuralmind-mcp`
  and completes an `initialize` + `tools/list` round-trip over stdio.
- `turbovec>=0.7,<2` with a documented re-evaluation trigger; nightly canary
  workflow that installs latest turbovec and runs `evals/parity`.
- `tree-sitter>=0.22`; grammar packages `>=0.23`; `_load_language` cached.
- `__version__` from `importlib.metadata.version("neuralmind")` with a
  fallback literal; a test that asserts it equals `pyproject.toml`.
- CI matrix: add 3.13 (required) and 3.14 + 3.14t (informational, allowed to
  fail for one release). Drop 3.10 in the release after Python 3.10 EOL.
  Update `docs/COMPATIBILITY.md` to match reality.
- `mypy` becomes required for `neuralmind/synapses.py`, `core.py`, `hooks.py`
  first (incremental strictness), then the rest.
- Apply `slow` / `integration` / `perf` markers; move `test_synapse_latency.py`
  behind `perf`.

### 5.9 `VectorBackend` contract

A versioned `typing.Protocol` in `neuralmind/backends/protocol.py`:

```python
class VectorBackend(Protocol):
    backend_id: str            # "turbovec" | "chroma" | …
    format_version: int
    def load(self, stamp: IndexStamp) -> None: ...
    def upsert(self, rows: Iterable[NodeRow]) -> UpsertStats: ...
    def search(self, vector: np.ndarray, k: int, where: Filter | None = None) -> list[Hit]: ...
    def get_nodes(self, ids: Sequence[str]) -> list[NodeRow]: ...
    def community_summaries(self) -> Mapping[int, CommunitySummary]: ...
    def bm25(self) -> BM25Index | None: ...
```

`context_selector.py` talks only to the protocol (today it probes six
backend-specific attribute names — `context_selector.py:580, 608, 963, 1596-1598`).
`evals/parity` becomes the conformance suite any new backend must pass.

---

## 6. Measurement spec (the first deliverable)

**Harness:** `tests/benchmark/perf.py` (stdlib + the package; reuses
`bench/benchmark_turbovec.py`'s spawn isolation, `getrusage`, `_dir_size_bytes`).
Emits one JSON document per run:

```json
{
  "schema": 1, "commit": "…", "python": "3.12.4", "platform": "linux-x86_64", "runner": "ubuntu-24.04",
  "corpus": {"name": "synthetic-1k", "files": 1000, "nodes": 10412},
  "build": {"cold_s": 0.0, "incremental_noop_s": 0.0, "incremental_1file_s": 0.0, "peak_rss_mb": 0.0},
  "artifacts": {"graph_json_mb": 0.0, "vector_store_mb": 0.0, "bm25_mb": 0.0, "synapse_db_mb": 0.0},
  "cold_start": {"import_cli_ms": 0.0, "load_index_ms": 0.0, "first_query_ms": 0.0},
  "query": {"warm_p50_ms": 0.0, "warm_p95_ms": 0.0, "n": 50},
  "hook": {"prompt_submit_p95_ms": 0.0, "compress_read_p95_ms": 0.0, "edit_activity_p95_ms": 0.0},
  "mcp": {"tools_list_ms": 0.0, "query_tool_p95_ms": 0.0},
  "embed": {"vectors_per_s": 0.0},
  "synapse": {"reinforce_200files_ms": 0.0, "decay_ms": 0.0, "db_growth_after_100_sessions_mb": 0.0}
}
```

**Corpora:** `synthetic-100`, `synthetic-1k`, `synthetic-10k` (generated by
`generate_synthetic_repo`, deterministic seed) for the scaling sweep; the
existing `tests/fixtures/sample_project` for the CI gate; the four pinned OSS
repos from `evals/public` for the reproducible-on-demand table.

**Gating rules** (added to `ci-benchmark.yml`):

| Metric | Gate | Rationale |
|--------|------|-----------|
| `hook.prompt_submit_p95_ms` | ≤ 250 ms (fixture), hard fail | This is the user-visible promise. |
| `cold_start.first_query_ms` on a fresh index | ≤ 1,500 ms without daemon; ≤ 300 ms with daemon | Replaces the ungated 14.9 s. |
| Scaling exponent of `query.warm_p95_ms` vs nodes, fitted over the three synthetic corpora | ≤ 1.15 | Host-independent; catches a new O(N) scan. |
| `build.incremental_noop_s` / `build.cold_s` | ≤ 0.10 | Catches B3/B4/H3-style "incremental" regressions. |
| `artifacts.graph_json_mb` across 3 no-op builds | identical | Catches B2. |
| `synapse.db_growth_after_100_sessions_mb` | ≤ 2× the 10-session size | Catches S3/S4. |
| Everything else | ≤ 1.5× committed baseline JSON on the same runner label; absolute values published as artifacts | Wide band; flake-tolerant. |

**Baselines:** `tests/benchmark/perf_baseline.json` committed and updated by
an explicit `chore(perf): refresh baseline` commit only. The regression test
never reads a gitignored results file (M3).

**Instrumentation:** `RetrievalTrace` gains `timings_ms: dict[str, float]`
(`embed`, `vector_search`, `bm25`, `synapse_spread`, `assemble`); `hooks.py`
and `mcp_server.py` entrypoints wrap in a `perf_counter` span that is appended
to the existing `.neuralmind/metrics/*.jsonl` (already has 30-day retention).
`neuralmind stats --perf` reads it.

**Publishing:** every gated number that the site wants to quote goes into
`site/claims.json` with `evidence: "ci-gated"` per the existing rule.

---

## 7. Acceptance criteria for the programme

| Area | Today (measured or documented) | Target | How verified |
|------|------|--------|--------------|
| MCP server on fresh install | crashes with `AttributeError` on mcp ≥ 2.0 | starts and answers `tools/list` on mcp 1.30 **and** 2.2 | new CI step |
| `prompt-submit` hook, index present | full `build()` + ONNX session: ~0.6 s at 135 nodes, ~1.5 s at 10k nodes (measured); P95 3.5–14.9 s on the prose corpus per existing docs | p95 ≤ 250 ms without daemon; ≤ 100 ms with | `perf.py` gate |
| `neuralmind query`, warm index, no daemon | full `build()` per invocation: ~0.65 s at 135 nodes, ~1.5 s at 10k nodes (measured) | load-only; p95 ≤ 1.5 s incl. ONNX on fixture | `perf.py` gate |
| Incremental no-op build | re-walks, re-writes `graph.json`, rebuilds BM25: ~0.4 s at 135 nodes, ~1.35 s at 10k nodes (measured) | ≤ 10 % of cold build; artifacts byte-identical | `perf.py` gate |
| Synapse DB after 100 sessions on `synthetic-1k` | unmeasured; unbounded by construction | ≤ 2× the 10-session size; zero orphans after rebuild | `perf.py` + new unit tests |
| `reinforce()` with 200 touched files | O(n²) pairs, unbounded | capped at 64 nodes/batch; ≤ 50 ms | unit + perf |
| Concurrent writers (watcher + hook + MCP) | silent loss on `SQLITE_BUSY` | zero lost writes in a 3-process contention test | new integration test |
| Index stamp | none | present; model/backend/schema mismatch → deterministic rebuild, never mixed vectors | unit tests |
| Python support | 3.10–3.12 tested | 3.11–3.13 required, 3.14/3.14t informational | CI matrix |
| Version string | drifted | equals `pyproject.toml` | unit test |
| Dependency caps | `mcp<3` broken, `turbovec` uncapped, `tree-sitter` floor wrong | `mcp<4` with shim, `turbovec<2` + canary, `tree-sitter>=0.22` | CI |

---

## 8. Open decisions for the reviewer

1. **Daemon auto-spawn by default?** It gives the best hook latency but adds
   a background process users didn't ask for. Recommendation: on by default
   with an idle TTL of 30 min and `NEURALMIND_DAEMON=0` to disable; document
   it in the release notes and `neuralmind doctor`.
2. **Drop Python 3.10 in v3.13 or v4.0?** Recommendation: announce in v3.13
   release notes, drop in the first release after 2026-10-04 (upstream EOL).
3. **Cap turbovec at `<2`?** Recommendation: yes, with the canary; the
   quarantine path covers format breaks but not ranking regressions.
4. **Model2Vec experiment for hook-side embedding** — worth a two-day spike
   behind a flag once the stamp (D6) lands? Recommendation: yes, as an
   informational benchmark row, not a default change.
5. **Should the domain tables (`terminology.py`, chapter intent weights) move
   out of the library into a per-project plug-in now, or when the second
   prose customer appears?** Recommendation: now, because they run on every
   prose query for every user and are the clearest example of D7.
6. **Where do these two documents live?** `docs/specs/` here (current) or
   `neuralmind-marketing/internal/plans/` per `CLAUDE.md`.

---

## 9. Sources

Internal:
- `SPEC_PERFORMANCE_IMPROVEMENTS_v3.12.0.md`, `SESSION_PROMPT_PERFORMANCE_FIXES.md`
- `tests/benchmark/peptide_report.md`, `tests/benchmark/retrieval_report.md`, `tests/benchmark/ADVERSARIAL_QA_ANALYSIS.md`
- `docs/HONEST-ASSESSMENT.md` ("What we haven't measured well yet"), `benchmarks/README.md`
- `site/claims.json` (`unsourced_do_not_use`), `docs/COMPATIBILITY.md`, `ROADMAP.md`, `KANBAN.md`

External (accessed 2026-09-15):
- MCP Python SDK migration guide — https://py.sdk.modelcontextprotocol.io/migration/ ; PyPI `mcp` release history (2.0.0 2026-07-28, 2.2.0 latest, 1.30.0 2026-09-07) — https://pypi.org/project/mcp/
- Representative downstream breakages from the same cap mistake: chunkhound#405, mcp-pandoc#40, mcp-logseq#92, nutrient-pdf-mcp-server#9
- turbovec on PyPI (Alpha classifier, 1.0.0 2026-08-18, wheel tags) — https://pypi.org/project/turbovec/ ; https://github.com/RyanCodrai/turbovec
- ONNX Runtime graph optimisations / offline mode — https://onnxruntime.ai/docs/performance/model-optimizations/graph-optimizations.html ; ORT-format runtime optimisation — https://onnxruntime.ai/docs/performance/model-optimizations/ort-format-model-runtime-optimization.html ; releases (3.13/3.14 wheels; 3.10 wheel sunset) — https://github.com/microsoft/onnxruntime/releases
- py-tree-sitter 0.25/0.26 API changes — https://tree-sitter.github.io/py-tree-sitter/ ; tree-sitter-python#280 (capsule/core version mismatch)
- Python free-threading HOWTO — https://docs.python.org/3/howto/free-threading-python.html
- Model2Vec — https://github.com/MinishLab/model2vec ; EmbeddingGemma-300M ONNX — https://huggingface.co/onnx-community/embeddinggemma-300m-ONNX
- sqlite-vec — https://alexgarcia.xyz/blog/2024/sqlite-vec-stable-release/index.html
- Claude Code hooks reference (timeouts, `async`, `if`, event list) — https://code.claude.com/docs/en/hooks
- Chroma 1.x migration notes — https://docs.trychroma.com/docs/overview/migration
