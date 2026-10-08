# N-17 Retrieval Resilience — Fail-Loud Index Health, Self-Healing Recovery, and Watch Instance Safety

**Status:** DRAFT for review, revision 3 (see the revision history at the end)
**Date:** 2026-10-08
**Baseline:** v4.11.0 (`main` @ `ed66521`). Every `file:line` below was checked against that commit.
**Scope:** the retrieval read path (`search`, `query`, MCP tools), the turbovec index lifecycle, `doctor`, `build`, and `watch` process management.
**Companions:** [`N-18-PERSISTED-VECTORS-SPEC.md`](N-18-PERSISTED-VECTORS-SPEC.md), embedder-free recovery from 1M documents up (split out of this spec as R7).
**Related:** [`PERFORMANCE-FUTURE-PROOFING-SPEC.md`](PERFORMANCE-FUTURE-PROOFING-SPEC.md) §5 (daemon/latency) and [`RETRIEVAL-BENCHMARK-SPEC.md`](RETRIEVAL-BENCHMARK-SPEC.md) (retrieval *quality*).

> **Scope note.** This spec covers retrieval **availability and truthfulness**. It does not cover retrieval *quality* (ranking, nDCG, relevance grading) — that is N-15's domain.

### Conventions

- **Normative language.** In §3, the key words MUST, MUST NOT, SHOULD and MAY are used as described in [RFC 2119](https://www.rfc-editor.org/rfc/rfc2119) and [RFC 8174](https://www.rfc-editor.org/rfc/rfc8174), and carry that meaning only in uppercase. Lowercase prose elsewhere is explanatory.
- **Stable IDs.** Findings (F*n*), gaps (G*n*), requirements (R*n*.*m*) and acceptance criteria (AC*n*) are never renumbered. A requirement that moves or is withdrawn keeps its ID as a pointer (R7, AC20). Implementation PRs and tests cite these IDs, and §5.1 traces each requirement to its evidence, criteria and delivery PR.
- **Evidence grades.** Every quantitative statement is one of:

  | Grade | Meaning | Example |
  |---|---|---|
  | **measured** | Produced by a run whose script is in Appendix A or the repo | turbovec load at 1M = 526 ms |
  | **derived** | Arithmetic on measured figures, with no run of its own | ≈10 h to re-embed 1M rows at 27 docs/s |
  | **projected** | Extrapolated beyond what was run; replaced once the tier runs it | 10M SQLite scans (§2.2, footnote 2) |
  | **hypothesis** | A mechanism consistent with the evidence, not yet confirmed by a test | §2.0 G1–G3, confirmed or refuted by AC0 |
  | **reported** | Observed in the field incident, not reproduced in CI | F1–F4 |

  This is the same evidence discipline as `site/claims.json`. No figure in this spec is quoted without one of these grades, and a figure here does not become site copy without a `claims.json` entry.

---

## 1. Summary

NeuralMind can be simultaneously **"healthy" by every surface it exposes** and **returning zero results for every query**. The failure is silent in three independent places:

| Layer | What it reports | Reality |
|---|---|---|
| `search` / `query` | `[]` with exit code 0 | index unavailable |
| `build` | `Build successful!` | index still unusable |
| `doctor` | `[FAIL] Index quarantined` | may be a false positive on a *working* index |

An agent (or a human) that trusts any of these gets a confident wrong answer: "the codebase does not contain that symbol." That is worse than an error, because it is indistinguishable from a true negative.

This spec specifies the fixes as **six product-level requirements**. R1–R5 hold regardless of how the index became unusable: version mismatch, corruption, partial write, empty store, or missing directory. R6 makes recovery safe from 100k up to 10M documents (§2.2–§2.3). Making recovery *fast* above 1M needs persisted vectors, which is a separate spec, N-18 (see R7).

---

## 2. Background — the turbovec index lifecycle

The vector index is a turbovec `.tvim` file (`IdMapIndex`) alongside a SQLite row store:

```
<project>/.neuralmind/neuralmind_turbovec/
  index.code.tvim        <- the vector index (binary, version-stamped)
  store.code.sqlite      <- nodes table: uid, node_id, document, ...  (source of truth)
  bm25_index.code.json   <- lexical index
  index.code.tvim.stale  <- quarantine backup, written when load fails
```

`turbovec.IdMapIndex.load()` raises `ValueError`/`OSError` when the on-disk stamp is incompatible with the installed `turbovec`, or the file is corrupt. The baseline already recovers **automatically** on two paths:

1. **First touch.** `_load_index()` (`neuralmind/turbovec_backend.py:443-463`) catches the load error, renames the file to `<name>.stale`, and calls `_rebuild_index_from_store()`.
2. **Build.** `embed_nodes(force=False)` (`turbovec_backend.py:810-830`) checks whether `_load_index()` returned `None` while the store still has rows. If so, it calls `_rebuild_index_from_store()` again, and if that returns 0 it escalates to `force=True`. A plain `build` therefore already re-embeds a quarantined index, and the baseline tests require recovery without `--force`.

`_rebuild_index_from_store()` (`turbovec_backend.py:465-523`) is **a full re-embed, not a vector copy**. SQLite keeps each node's `document` text, not its vector, so the function passes the whole corpus to `_embed_matrix`. Its value is *coverage*: it also restores rows ingested through `embed_content`, which `embed_nodes` cannot rebuild from the graph. It saves no embedding time. When it returns 0, the cause is almost always the embedder itself (no ONNX runtime, no model). The `force=True` fallback calls that same embedder, so it usually fails the same way.

### 2.0 Why the existing recovery did not fire *(hypothesis)*

The reproduced build printed `+3 new, =4,471 skipped`. Hash-skipping only happens with `force=False` and a non-`None` index. So in that run `_load_index()` returned a **loadable** index, and neither recovery path ran. The code has three gaps that, together, produce exactly that state:

- **G1 — recovery runs only on the touch that finds the file.** `_load_index()` attempts the rebuild only when the `.tvim` file exists and fails to load. If that attempt fails, the file has already been renamed to `.stale`. Every later touch sees no file, returns `None`, and does not retry. `search` turns that `None` into `[]` (`turbovec_backend.py:994-996`).
- **G2 — `embed_content` writes a subset index.** `embed_content` reaches `_ensure_index()` (`turbovec_backend.py:525-535`, called at `:736`) without the `rows > 0` guard that `embed_nodes` has. If the file is absent, it creates a fresh, empty index, adds only its pending vectors, and persists that. The result is a loadable index holding a few vectors, next to a store with thousands of rows. From then on, `_load_index()` succeeds, no recovery runs, and every `build` hash-skips the missing rows. The `watch --reindex` processes in F4 are another writer that can race into this window.
- **G3 — `search` swallows the mismatch.** `search` computes `k` from the *store's* row count and searches with an allowlist of store uids. When the index lacks those uids, `idx.search` raises, the retry raises, and the error becomes `[]` (`turbovec_backend.py:1011-1021`; the comment there names "allowlist has dangling uids not in index").

This mechanism is **consistent with the evidence but not yet confirmed** against the incident project. PR 1 (§7) must first reproduce it as a failing test: quarantine → failed rebuild → `embed_content` → `build` → `search` returns `[]`. Fixes land only after that test fails for the right reason. If it reproduces some other way, the requirements below still hold, because they are stated against the observable state, not the path that produced it.

### 2.1 Evidence base *(reported)*

All findings below were reproduced on the baseline commit against a real 5,780-node project index.

| # | Finding | Evidence |
|---|---|---|
| F1 | Retrieval returns empty silently | `neuralmind search <proj> "score_predictions"` → `[]`, exit 0, no stderr. After repair, same command returns 5 ranked hits (0.70…0.64). |
| F2 | `build` reports success while index is quarantined | `neuralmind build <proj> --scope code` → `Build successful! … Delta: +3 new, =4,471 skipped`. Index still quarantined; `search` still `[]`. |
| F3 | `doctor` quarantine check is a file-existence test | `neuralmind/doctor.py:470` — `if stale_path.exists(): return <FAIL>`. No load attempt, no liveness check. Persists as FAIL after the index is repaired and working. |
| F4 | `watch` has no single-instance guard | Two `watch --reindex` processes ran against the same project concurrently for ~24h (one in `D` state, 1.7 GB RSS). A `flock` helper already exists at `neuralmind/metrics_pipeline.py:44-66` (`_lock_file`/`_unlock_file`); `watch` does not use it. |
| F5 | The repair flag's help text describes a different operation | `--rebuild-index` (`cli.py:6346`) is documented as "Rebuild the vector index from stored vectors (recovers from version mismatch without full re-embed)". It actually just sets `force = True` (`cli.py:675`), which is a full graph re-embed. No path anywhere rebuilds from stored vectors, because none are stored (§2). *Corrected in review: an earlier draft said this flag was the only recovery path. It is not; see §2.* |
| F6 | Read path has no index-health preflight | `neuralmind/cli.py:2059-2069` (`cmd_search`) calls `mind.search()` and prints whatever comes back, including `[]`. |
| F7 | A loadable index can silently hold a subset of the store | §2.0 G2/G3. Nothing compares the index's vector count with the store's row count, so a 3-of-4,474 index counts as "loaded". |

**F2, F3 and F7 are the load-bearing defects.** F2 produces a false success on the write path. F3 produces a false failure on the diagnostic path. F7 is the state where both of them happen. Together they make the true state of the index unknowable from the CLI.

### 2.2 Cost at scale *(measured; derived and projected rows marked)*

The incident index held 5,780 nodes. Every requirement below must also hold for far larger corpora, up to **10,000,000 documents**: monorepos, plus `embed_content` docs and compliance libraries. They are tested at four tiers (T0 10k, T1 100k, T2 1M, T3 10M; see §6.1). Measured on a 4-vCPU / 15 GB Linux container, Python 3.13, turbovec 1.1.2, the default `bit_width=4`, 384-dim random unit vectors. The scripts are in Appendix A.

| Operation | 10k | 100k | 1M | 10M |
|---|---:|---:|---:|---:|
| `.tvim` file size | 2.5 MB | 20.9 MB | 204 MB | 2,040 MB |
| `IdMapIndex.load()` | 2 ms | 20 ms | 526 ms | 4.4 s |
| `len(index)` | O(1) | O(1) | 6 µs | 9 µs |
| `contains()` over every uid (id-set diff) | 2 ms | 21 ms | 0.7 s | 7.3 s |
| Build from ready vectors (`add_with_ids` in 100k chunks + `prepare`)¹ | 0.13 s | 0.23 s | 15.8 s | 148 s |
| `search` k=5, no allowlist | 0.3 ms | 3.0 ms | 3–4 ms | 21 ms |
| `search` k=5, 50% allowlist | 0.3 ms | 2.6 ms | 43 ms | 621 ms |
| Peak RSS of the benchmark process | — | — | 841 MB | 2,847 MB |

¹ At 1M and 10M the time includes generating the synthetic vectors chunk by chunk. 10k/100k figures were built in one call.

| SQLite store (~1 KB documents) | 100k | 1M | 10M (projected²) |
|---|---:|---:|---:|
| `COUNT(*)` | 1.8 ms | 9 ms | ≈ 0.1 s |
| `COUNT(*) WHERE document IS NOT NULL AND document != ''` | 33 ms | 440 ms | ≈ 4.4 s |
| `SELECT uid …` (uid set for the diff) | 92 ms | 877 ms | ≈ 9 s |
| `SELECT uid, document` fetchall, as `_rebuild_index_from_store` does today | 0.77 s, ~92 MB held | ~0.9 GB held | ~9 GB held |
| Store size on disk | ~0.1 GB | 1.04 GB | ≈ 10 GB |

² The 10M store was not built (≈10 GB of scratch disk); these are full-scan queries scaled linearly from 1M. Treat them as projections until T3 (§6.1) measures them.

| Embedder (ONNX MiniLM, ~600-char node documents) | Throughput |
|---|---:|
| In-process | 32 docs/s |
| `_embed_matrix` production path (one subprocess per 256 docs) | **27 docs/s** (9.5 s/batch) |

Also confirmed: `idx.search(…, allowlist=…)` raises `KeyError: 'allowlist contains id(s) not present in index'` when an allowlisted uid is absent. That is §2.0 G3, reproduced directly.

Re-embedding cost per tier at the measured 27 docs/s (arithmetic, not a run):

| Tier | Documents | Recovery by re-embed (today's only path) | Recovery from stored vectors (index build, measured above) |
|---|---:|---:|---:|
| T0 | 10k | ≈ 6 min | 0.13 s |
| T1 | 100k | ≈ 1 h | 0.23 s |
| T2 | 1M | ≈ 10 h | 15.8 s |
| T3 | 10M | ≈ 4.3 days | 148 s |

What follows from it:

- **Diagnosis is cheap through T1 and has to be designed for T2/T3.** A full health check (load, `len`, filtered store count, uid-set diff) costs about 0.2 s at 100k. At 1M it is ≈2 s. At 10M it is ≈16 s plus a 4.4 s index load (part measured, part projected; see footnote 2). That is fine for `doctor --deep` and `build`, but wrong per query. So the per-query preflight must not scan the store (R3.3).
- **Recovery is expensive, and the cost is all in the embedder.** Faster hardware divides the hours but does not change the ratio. Past T1, no amount of checkpointing makes re-embedding an acceptable recovery path: it takes 10 h at 1M and days at 10M. That is why N-18 exists.
- Today's recovery is shaped for small indexes, and at 100k it breaks in five ways:
  1. **It runs on the read path.** `_load_index()` performs the rebuild inline, so the first `search` or MCP call after a quarantine blocks for the whole re-embed. Any client timeout fires long before it finishes.
  2. **It is all-or-nothing.** `_rebuild_index_from_store` embeds the whole corpus and persists once, at the end. An interrupt at minute 59 loses everything and leaves the file renamed: G1 again.
  3. **Memory is unbounded.** It holds every document (~92 MB) plus the full float32 matrix (100k × 384 × 4 B ≈ 154 MB, before normalisation copies) at once.
  4. **It is silent.** An hour with no progress output looks exactly like the hung `D`-state watcher in F4.
  5. **Nothing stops parallel runs.** `build`, `watch --reindex`, the daemon and a `search` first touch can each start the same hour-long rebuild of the same index at the same time.

R6 addresses these.

### 2.3 Where it breaks, by row count *(derived)*

The row count at which each cost crosses a budget an agent or operator would notice. Budgets are stated, not measured. Crossing points are interpolated from §2.2 on this 4-vCPU container, so faster hardware moves them right, but by a constant factor, not an order of magnitude.

| Breaks at ≈ | What | Why (from §2.2) | Fixed by |
|---:|---|---|---|
| **~1,600 rows** | A `search` / MCP call that hits a quarantined index runs past a 60 s tool-call budget | The first-touch rebuild runs inline at 27 docs/s. **The incident project (5,780 nodes) is already past it: an inline rebuild there takes ≈3.6 min.** | R6.1 |
| ~16,000 | Recovery passes 10 min with no progress output | 27 docs/s, silent | R6.6 |
| ~100,000 | Recovery ≈ 1 h; an interrupted run loses all of it | All-or-nothing persist | R6.2, R6.3 |
| ~230,000 | A store-scanning preflight would pass 100 ms per query | Filtered `COUNT` ≈ 0.44 µs/row (440 ms at 1M) | R3.3 counter |
| ~250,000–400,000 | `_rebuild_index_from_store` passes 1 GB RSS | It holds all document text (~0.9 KB/row) plus the float32 matrix (1.5 KB/row) and its normalised copy at once *(arithmetic)* | R6.4 |
| **~1,000,000** | Re-embed recovery ≈ 10 h, so re-embedding stops being a viable recovery | 27 docs/s | N-18 (R7 known gap) |
| ~2,000,000 | CLI cold start passes 1 s per `search`; a filtered search (50% allowlist) passes 100 ms | Load ≈ 0.45 µs/vector (526 ms at 1M, 4.4 s at 10M); allowlist search 43 ms → 621 ms from 1M to 10M | Daemon (out of scope, §4); allowlist cost noted for N-15 |
| ~10,000,000 | Re-embed ≈ 4.3 days; index 2 GB on disk and ~2.8 GB peak RSS to build; store ≈ 10 GB; `doctor --deep` ≈ 15 s | §2.2 | N-18, T3 runner sizing (§6.1) |

Untouched at any measured tier: index `len()` (≤ 9 µs), unfiltered k=5 search (≤ 22 ms at 10M), and the uid-set diff, which stays fast enough for `build` and `doctor --deep` (7.3 s at 10M).

---

## 3. Requirements

### R1 — Retrieval fails loud, never empty

**R1.1** `search` and `query` MUST NOT present an empty result set as a successful search when the vector index is unavailable: missing, unloadable, or inconsistent with the store (R3.1). This applies on **every** surface: the CLI, the daemon, and the MCP tools.

**R1.2** When results are empty, the tool MUST distinguish two cases, and say which:

| Case | Meaning | Required behaviour |
|---|---|---|
| No matches | index healthy, query genuinely has no hits | report "no matches" + the fact that the index was consulted |
| Index unavailable | any non-healthy R3.1 state | report an **error** naming the state and the repair command; `search` exits non-zero (`query` degrades instead, R1.6) |

**R1.3** The distinction MUST be machine-readable, not only human-readable. Each surface carries it in the channel that surface already has:

| Surface | `ok` / `no_matches` | `index_unavailable` |
|---|---|---|
| CLI `search --json` (default) | bare array, exactly as today; exit 0 | bare `[]` on stdout; one-line error on stderr; **exit 69** |
| CLI `search --json-v2` (opt-in) | envelope, exit 0 | envelope, exit 69 |
| CLI `query` (text and `--json`) | unchanged; exit 0 | context still returned (see R1.6); `"index_status"` key added to the JSON object; warning on stderr; exit 0 |
| MCP `neuralmind_search` | list, exactly as today | the server's existing error shape: `{"error": "...", "code": "index_unavailable", "reason": "...", "repair": "..."}`, the same convention as `project_not_found` / `security_denied` (`mcp_server.py:1346`, `:1478-1496`) |
| MCP `neuralmind_query` | object, unchanged | object with `"index_status"` added (R1.6) |
| Daemon query / search | unchanged | MUST forward `index_status`; the thin daemon response MUST NOT drop it (`cli.py:1158-1190`) |

The `--json-v2` envelope is:

```json
{ "status": "ok",                "results": [ ... ] }
{ "status": "no_matches",        "results": [], "index_available": true }
{ "status": "index_unavailable", "results": [], "index_available": false,
  "reason": "unloadable | missing | inconsistent | empty",
  "repair": "neuralmind build <path>" }
```

`repair` names a **plain `build`**, since R2 makes that self-healing. `--rebuild-index` is not suggested here. If a plain build has already failed to repair the index, the build's own output names the cause (R2.3).

**R1.4** Backwards compatibility. The default `--json` payload of `search` stays a top-level array in **every** case, including `index_unavailable`. The status therefore travels in the exit code and on stderr, not in stdout. The status envelope exists only behind `--json-v2`. R1.3's status vocabulary is defined once and used by `--json-v2`, MCP and the daemon; the default `--json` output never contains it.

**R1.5** Exit codes for `search`: `0` = ok or a genuine no-match; `69` = index unavailable. 69 is `EX_UNAVAILABLE` from `sysexits.h` ("a service is unavailable"). It is chosen because every lower code already means something in this CLI: argparse and usage errors use `2`, generic failures `1`, `daemon status` uses `3` for "not running" (`cli.py:4738`), and the licence-expiry check uses `6` and `7` (`cli.py:5685-5687`). A script can therefore detect this failure without parsing prose, and one code means the same thing across subcommands.

**R1.6** `query` is degraded, not empty. With no usable index, its L0/L1 layers (graph summary, communities) are still correct, but L2/L3 search hits are missing. It MUST therefore keep returning context, plus:
- an `"index_status": {"status": "index_unavailable", "reason": ..., "repair": ...}` key in the JSON / MCP object. This is additive: object consumers tolerate a new key, and the key is absent when the index is healthy, so healthy output stays byte-identical;
- one line **inside the returned context text** saying semantic search was unavailable and hits were omitted. The agent reads the context, not the metadata, and the incident's wrong answer came from an agent reading a context with no hits in it.

### R2 — `build` does not report success on an unusable index

**R2.1** `build` MUST verify the index is loadable **after** writing it, before printing any success line. A build that leaves a quarantined index MUST NOT print `Build successful!`.

**R2.2** `build` MUST self-heal **every** unusable state in R3.1, not only the one the baseline already handles. The baseline escalation (`_load_index() is None` with store rows, §2) stays as it is. It MUST also trigger on `inconsistent`: a loadable index whose vector count differs from the store's row count (§2.0 G2). On that path the build repairs the difference (R6.2): it re-embeds only the rows missing from the index. Hash-skipping is allowed only after the index has been verified consistent.

**R2.3** If the store-backed re-embed returns 0, `build` MUST NOT silently retry another full re-embed through the same embedder (§2: it fails the same way). It MUST surface the embedder's actual error and exit non-zero:

```
Build incomplete!
  Nodes: 4474
  Vector index: UNUSABLE (inconsistent: 3 of 4474 vectors)
  Recovery: re-embedding 4474 stored documents failed — <embedder error>
  Fix the embedder (e.g. `pip install onnxruntime`), then: neuralmind build <path>
```

The `Delta` line MUST NOT imply success when the index was not repaired. `=N skipped` next to an unusable index is a **failure to repair**, not an optimisation.

**R2.4** A write path MUST NOT persist an index that is smaller than the store. `embed_content`, and any other caller of `_ensure_index()`, MUST take the same `rows > 0` recovery branch as `embed_nodes` before creating a fresh index (closes §2.0 G2). Recovery that `_load_index()` attempts and fails MUST be retried on the next **write-path** touch (`build`, `watch`, `migrate-index`) rather than lost once the file is renamed (closes G1). It is never retried on the read path (R6.1).

**R2.5** `--rebuild-index` remains available for explicit operator use but is not required for recovery. Its help text MUST describe what it does: force a full re-embed. It MUST NOT promise a rebuild "from stored vectors … without full re-embed" (F5).

Recovery that skips the embedder entirely, by persisting vectors, is N-18. It matters from T2 (1M documents) up, where re-embedding takes hours to days (§2.3, R7).

### R3 — Index health is a state machine, and `doctor` reports it truthfully

**R3.1** Replace the `.stale`-existence test with an actual load attempt **and** a count check. Let *V* be the loaded index's vector count and *N* the store's row count with a non-empty `document`. The states, evaluated in this order, are:

| State | Detection | `doctor` verdict | `search` status (R1) |
|---|---|---|---|
| `missing` | no index file, *N* = 0 | FAIL — "never built; run build" | `index_unavailable` / `missing` |
| `empty` | index loads, *V* = 0, *N* = 0 | WARN — "nothing indexed in this scope" | `index_unavailable` / `empty` |
| `unloadable` | no index file **or** load fails, *N* > 0 | FAIL — "index unreadable, *N* documents in store; run build". R5.3 splits off version mismatch | `index_unavailable` / `unloadable` |
| `inconsistent` | index loads, *V* ≠ *N* | FAIL — "index holds *V* of *N* vectors; run build" | `index_unavailable` / `inconsistent` |
| `healthy` | index loads, *V* = *N*, no `.stale` | ok | `ok` / `no_matches` |
| `recovered` | index loads, *V* = *N*, `.stale` present | **ok** (advisory note) | `ok` / `no_matches` |

The four FAIL/WARN states cover all five causes in §1: version mismatch and corruption → `unloadable`; partial write → `inconsistent`; empty store → `empty`; missing directory → `missing` or `unloadable`.

**R3.1a — diagnosis is read-only.** The state is computed by one function, `index_health(project, scope) -> IndexHealth`. It calls `turbovec.IdMapIndex.load()` on the path directly and **never** calls `_load_index()`, because `_load_index()` renames and rebuilds as side effects. `doctor` never repairs anything. Repair belongs to `build` (R2) and `migrate-index` (R5).

**R3.2** `recovered` MUST report **ok**, not FAIL. The presence of a `.stale` file is *evidence of a past incident*, not a current fault. Report it as an advisory line so the history is visible without failing the check:

```
[ ok ] Turbovec compatibility: index loads (1 stale backup present, from a repaired mismatch)
```

**R3.3** `doctor` MUST attempt the load, so its verdict cannot drift from what `search` will experience. The cost per tier is in §2.2 (≈20 ms at 100k, ≈0.5 s at 1M).
- **Per-query preflight (`search`, MCP, daemon): O(1) in corpus size.** It compares `len(index)` with a `vectorizable_rows` counter kept in the store's `meta` table. Every insert or delete updates the counter in the same transaction as the row. It MUST NOT run `COUNT(*) … WHERE document != ''`, which costs 440 ms at 1M and ≈4.4 s at 10M. Long-lived processes evaluate it once per index load and again only when the `.tvim` mtime changes.
- **`doctor` default:** load + `len` + counter. **`doctor --deep` and `build`:** the full uid-set diff (≈1.6 s at 1M; ≈16 s at 10M: 7.3 s measured `contains()` plus ≈9 s projected uid scan). `build` runs the diff only when `len(index) ≠ vectorizable_rows` or the counter is absent (a legacy store, in which case it backfills the counter once). A healthy build never pays for it. `search` derives its R1 status from the same `index_health()` result. Under R6.1 the read path performs no recovery (apart from the small-store exception), so it reports the state exactly as `doctor` would find it.

**R3.4** `doctor`'s overall `Setup incomplete` summary MUST be driven by the state machine, not by the count of advisory lines.

### R4 — One watcher per project, enforced

**R4.1** `watch` MUST take an exclusive, per-project lock on startup and exit cleanly (code 0, one clear line) if another instance holds it:

```
neuralmind watch: another watcher already holds /home/.../.neuralmind/watch.lock (pid 1234) — exiting
```

**R4.2** The lock SHOULD reuse the existing flock helper (`neuralmind/metrics_pipeline.py:44-66`, `_lock_file`/`_unlock_file`) rather than add a second locking idiom. POSIX `flock(LOCK_EX|LOCK_NB)`; on Windows fall back to the byte-0 lock already implemented there.

**R4.3** The lock MUST be per-project (keyed on the resolved project path), not global — multiple projects legitimately run one watcher each.

**R4.4** Stale locks MUST NOT deadlock: a lock whose holder PID is gone MUST be reclaimable without manual cleanup. `flock` gives this for free (the lock dies with the process); the byte-0 fallback needs an explicit liveness check.

**R4.5** The systemd unit MUST NOT `Restart=always` a second instance into a hot loop. Combined with R4.1 the unit SHOULD observe a clean exit and stay stopped.

### R5 — Format-version preflight with an idempotent migration

**R5.1** `build`, `doctor` and `migrate-index` MUST detect an incompatible index **before** the slow path, and name the cause:

```
Vector index format mismatch.
  On-disk: written by turbovec <X>     (or: "unknown — written before N-17")
  Installed: turbovec <Y>
Recovery: re-embed <N> stored documents (≈<estimate from measured docs/s>).
          After N-18: rebuild from persisted vectors instead.
```

turbovec does not expose the version that wrote an index: `IdMapIndex.load()` only raises. The existing `turbovec_index_version()` (`turbovec_backend.py:366-393`) returns the *installed* version, despite its name. So the writer version MUST be recorded by NeuralMind itself. Every `_persist_index()` writes `turbovec_version` into the store's existing `meta` table, alongside the `dim` / `bit_width` keys already kept there. An index with no such key (any index written before this change) reports `On-disk: unknown — written before N-17`, and the mismatch is inferred from the load error alone. `turbovec_index_version()` SHOULD be renamed or re-documented so it stops implying it reads the on-disk stamp.

**R5.2** NeuralMind MUST expose an idempotent, safe-to-rerun migration entry point so upgrade tooling can call it non-interactively:

```bash
neuralmind migrate-index <project>    # exit 0 if already healthy (no-op)
```

**R5.3** `neuralmind doctor` MUST surface a version mismatch as its own finding, distinct from generic quarantine, so operators can tell "my toolchain moved" from "the file is corrupt".

### R6 — Recovery scales from T1 (100k documents) up

**R6.1 No recovery on the read path.** `search`, `query`, the MCP tools and the daemon's query handler MUST NOT run a re-embed inline. When they find an unusable index, they report `index_unavailable` (R1) at once, naming the state. Recovery belongs to `build`, `watch` and `migrate-index`. This replaces today's first-touch rebuild in `_load_index()` for reads. The one exception: a store small enough that recovery fits well inside a client timeout (threshold set from §2.2 throughput, e.g. ≤ 1 embedder batch). Even then, it runs only under the R6.5 lock.

**R6.2 Repair the difference, not the corpus.** For `inconsistent`, recovery MUST compute the missing uids (store uids where `index.contains(uid)` is false; ≈0.1 s at 100k) and re-embed only those, and MUST drop index ids absent from the store. Full re-embed is reserved for `unloadable`, where no index survives. A 99,000-of-100,000 partial write then costs 1,000 documents (≈40 s), not 100,000 (≈1 h).

**R6.3 Checkpointed and resumable.** Recovery MUST stream the store in chunks: fetch → embed → `add_with_ids` → persist index → commit. Each chunk MUST be durable before the next starts. An interrupted recovery leaves a loadable `inconsistent` index, and the next run resumes it through R6.2 with no special resume code. A chunk-sized write never leaves the file absent or renamed.

**R6.4 Bounded memory.** Recovery memory MUST be O(chunk), independent of corpus size. That means no `fetchall()` of every document and no corpus-wide vector matrix.

**R6.5 One recovery per index.** Recovery MUST take an exclusive per-index lock with the same flock helper as R4, keyed on the index path. A second process that finds the lock held MUST NOT start a parallel re-embed. A write-path caller waits or exits with "recovery already in progress (pid N)". A read-path caller reports `index_unavailable` / `recovering`.

**R6.6 Visible progress.** Recovery MUST report `done/total` documents and elapsed time through the existing `ProgressReporter` on a TTY, and as a plain line at least every 30 s otherwise. While a recovery holds the lock, `doctor` and the R1 `reason` field report `recovering (done/total)`, so an agent can tell "being fixed" from "broken".

**R6.7 Throughput is not made worse.** The current one-subprocess-per-256-docs path (§2.2: 27 docs/s, 9.5 s/batch) exists to work around an onnxruntime deadlock and is out of scope here. But recovery MUST NOT lower it: chunking (R6.3) MUST reuse `_embed_matrix`'s batching, not add per-chunk model reloads. Its batches also run one at a time. Running them across cores would divide the T1 hour, but it cannot bring T2/T3 into range (§2.2), so it is left to the embedder's own spec.

### R7 — Moved to N-18

Rebuilding the index from persisted vectors instead of re-embedding is now [`N-18-PERSISTED-VECTORS-SPEC.md`](N-18-PERSISTED-VECTORS-SPEC.md). It is a storage and schema commitment with its own open recall question, and R1–R6 do not depend on it. The ID R7 stays reserved so references do not shift.

**Known gap until N-18 lands.** From T2 (1M documents) up, recovering an `unloadable` index means re-embedding the whole store: ≈10 h at 1M and ≈4.3 days at 10M at the measured 27 docs/s (§2.2). R6 makes that recovery safe (off the read path, checkpointed, resumable, locked, visible) but not fast. `doctor` and the R5.1 message MUST state the expected re-embed cost at T2/T3, so that an operator learns the price before starting recovery, not halfway through it.

---

## 4. Non-requirements / out of scope

- **Retrieval ranking quality.** nDCG/MRR/relevance grading is N-15.
- **Changing the turbovec format or versioning scheme.** Upstream concern; we adapt.
- **Persisted vectors / embedder-free recovery.** [`N-18`](N-18-PERSISTED-VECTORS-SPEC.md); see R7 for the known gap.
- **CLI cold-start at T2/T3.** Each CLI `search` loads the whole index (0.5 s at 1M; 4.4 s at 10M, §2.2). The daemon is the answer to that, and it belongs to `PERFORMANCE-FUTURE-PROOFING-SPEC.md` §5. This spec requires only that the health check adds O(1) on top of the load (R3.3).
- **Parallelising the embedder.** See R6.7.
- **Cross-repo / federated indexes.** Explicitly not a NeuralMind capability.
- **Daemon/MCP latency.** `PERFORMANCE-FUTURE-PROOFING-SPEC.md` §5.
- **The `--project-path` vs positional-argument inconsistency** across subcommands. Real, but a separate CLI-consistency ticket.

---

## 5. Acceptance criteria

Each is testable without a human in the loop.

| ID | Criterion |
|---|---|
| AC0 | A test reproduces §2.0: quarantine → failed store rebuild → `embed_content` → `build` (hash-skips) → `search` returns `[]`. It fails on the baseline and passes after PR 3. |
| AC1 | With an unusable index, `search` exits 69 and names `neuralmind build <path>` (not `--rebuild-index`) on stderr. With a healthy index and an unmatched query, `search` exits 0 and reports no-matches. |
| AC2 | `search --json-v2` emits the R1.3 envelope with the correct `status` for all three cases. The default `search --json` payload is a bare array in all three cases (R1.4), with the unavailable case signalled only by exit 69 and stderr. |
| AC2a | MCP `neuralmind_search` on an unusable index returns `{"code": "index_unavailable", ...}`, not `[]`. MCP `neuralmind_query` and daemon-served `query` both carry `index_status`, and the context text contains the R1.6 notice. With a healthy index, all three responses are unchanged. |
| AC3 | `build` on an unusable index either repairs it or exits non-zero with the embedder's error (R2.3). It never prints `Build successful!` while `index_health()` is anything but `healthy` / `recovered`. |
| AC4 | A plain `build` (no `--rebuild-index`) repairs both an `unloadable` and an `inconsistent` index. |
| AC5 | `doctor` returns **ok** for the `recovered` state, with the stale backup noted as advisory. |
| AC6 | `doctor` returns FAIL for `missing`, `unloadable` and `inconsistent`, with a different message for each, and WARN for `empty`. |
| AC7 | For every R3.1 state, a table-driven test asserts that `doctor`'s verdict and `search`'s status are both derived from one `index_health()` result and agree (FAIL ⇔ `index_unavailable`). Running `doctor` leaves the index directory byte-identical (R3.1a). |
| AC8 | A second `watch` on the same project exits 0 within 2s with one clear message; the first is unaffected. |
| AC9 | Two `watch` processes on **different** projects both run (lock is per-project). |
| AC10 | Killing a watcher with `SIGKILL` leaves a reclaimable lock; a new watcher starts without manual cleanup. |
| AC11 | `migrate-index` on a healthy project exits 0 and changes nothing (idempotent). |
| AC12 | The full sequence — quarantine a healthy index, run `build`, run `search` — recovers without any `--rebuild-index` flag and without a manual `.stale` cleanup. |
| AC13 | An index written after this change records `turbovec_version` in `meta`. A legacy index without it reports the on-disk version as unknown, and the code never crashes or guesses a value (R5.1). |
| AC14 | On a 100k-row synthetic store with a fake embedder (CI-speed): an `unloadable` index makes `search` / MCP return `index_unavailable` immediately, with zero embedder calls (R6.1). |
| AC15 | Same fixture, index holding 99,000 of 100,000 uids: `build` passes exactly 1,000 documents to the embedder (R6.2). |
| AC16 | Same fixture: kill recovery partway (fake embedder raises after *k* chunks). The index on disk is loadable and `inconsistent`, and a re-run embeds only the remaining documents (R6.3). |
| AC17 | Same fixture: peak RSS during recovery does not grow with corpus size, measured at 10k vs 100k within a fixed margin (R6.4). |
| AC18 | Two concurrent `build`s on one unusable index: exactly one runs the re-embed, and the other reports `recovering` (R6.5). |
| AC19 | At every tier T0–T3 (§6.1), the per-query preflight adds ≤ 50 ms on top of the index load, and it issues no full-table SQL scan (R3.3). The test asserts both: wall time, and the SQL issued, via a statement trace. |
| AC20 | *Moved to N-18 (AC-N18-2). The ID stays reserved.* |
| AC21 | At T2 and T3, peak RSS during recovery stays within the tier's index size plus a fixed chunk allowance (default 512 MB), and does not scale with the store's document text (R6.4). |
| AC22 | At T2 and T3, `doctor --deep` and the `build` consistency check finish within 2× the recorded tier baseline. Default `doctor` stays O(1) in corpus size (R3.3). |

### 5.1 Traceability

| Requirement | Motivated by | Verified by | Delivered in |
|---|---|---|---|
| R1 fail loud | F1, F6, G1, G3 | AC1, AC2, AC2a | PR 2 |
| R2 truthful, self-healing `build` | F2, F5, F7, G2 | AC0, AC3, AC4, AC12 | PR 3 |
| R3 index-health state machine | F3, F7 | AC5, AC6, AC7, AC19, AC22 | PR 1 (preflight counter in PR 2) |
| R4 one watcher per project | F4 | AC8, AC9, AC10 | PR 4 |
| R5 version stamp + `migrate-index` | F5 | AC11, AC13 | PR 5 |
| R6 recovery at scale | §2.2, §2.3 | AC14–AC18, AC21 | PR 2 (R6.1, AC14), PR 3 (R6.2–R6.7), PR 6 (tiers) |
| R7 *(moved)* | §2.3 | AC20 *(moved)* | N-18 |

Every AC appears in exactly one row. AC0 is written in PR 1 as an expected failure and turns green in PR 3.

---

## 6. Test plan

**Unit**
- State-machine transitions for R3.1: table-driven over `{index file present/absent} × {load ok/fails} × {V = N / V ≠ N} × {N = 0 / N > 0} × {.stale present/absent}` → expected state.
- `search` status derivation for R1.2/R1.3, including the empty-store and subset-index cases, for the CLI, MCP, and daemon surfaces.
- Lock acquisition/release/reclaim for R4, including the `SIGKILL` path (AC10).

**Integration (fixture project)**
- Reproduce §2.0 end to end → AC0.
- Quarantine a valid index by stamping a wrong version → assert AC1, AC3, AC5, AC12.
- Delete the index file with the store empty → assert AC6 (`missing`); with the store populated → `unloadable`.
- Corrupt the index body (truncate) → assert `unloadable` and a message distinct from version mismatch (R5.3).
- Replace the index with one holding a subset of the store's uids → assert `inconsistent`, AC4.
- Make the embedder unavailable during recovery → assert AC3's non-zero exit names the embedder error, and that no second full re-embed is attempted.
- Two watchers, same project → AC8; two projects → AC9.

**Regression guards**
- `--json` default payload shape unchanged (R1.4) — this is the one that can silently break the hooks and MCP layer. Assert the bare-array shape explicitly.
- `savings` / `benchmark` still parse query results after the status field is added.
- An existing healthy project's `query` output is byte-identical before/after the change.

### 6.1 Scale tiers

Every scale requirement (R3.3, R6) is tested at four tiers, and N-18 reuses the same tiers. A tier fixture is a synthetic store plus index, generated in chunks by a deterministic fake embedder (hash → unit vector). The fake embedder lets the tiers test **NeuralMind's** logic and the **real** turbovec and SQLite at size, without spending hours on ONNX. Real-embedder throughput is measured separately on a fixed 2,048-document sample, and per-tier re-embed times are derived from it, never asserted.

| Tier | Documents | Footprint (store + index) | Runs | ACs |
|---|---:|---|---|---|
| T0 | 10k | ≈ 0.01 + 0.003 GB | every PR (pytest) | all functional ACs |
| T1 | 100k | ≈ 0.1 + 0.02 GB | every PR (pytest, fixture builds in < 1 s) | AC14–AC19 |
| T2 | 1M | ≈ 1.0 + 0.2 GB (+ 0.77 GB vectors after N-18) | nightly scheduled workflow + `workflow_dispatch`; fits a standard hosted Linux runner | AC14–AC19, AC21–AC22; recovery time measured, not gated (R7 known gap) |
| T3 | 10M | ≈ 10 + 2.0 GB (+ 7.7 GB vectors after N-18) | weekly + before every release, `workflow_dispatch`; needs a runner with ≥ 32 GB disk and ≥ 16 GB RAM (a larger hosted or self-hosted runner) | AC14–AC19, AC21–AC22; recovery time measured, not gated (R7 known gap) |

- Each T2/T3 run writes its measurements (every row of the §2.2 tables, plus the AC timings and peak RSS) to `bench/scale/results.json`, with runner specs and package versions. The relative gates in AC21–AC22 compare against the committed file. Same contract as `bench/public/results.json`: re-baselining means committing the new file in the same change that explains why.
- T3 replaces this spec's projected 10M SQLite figures (§2.2 footnote 2) with measured ones on its first run.
- A T2/T3 failure files an issue and blocks the release workflow. It does not block PRs, because those tiers do not run on PRs.

**Manual verification on a real corpus**
- Run the AC12 sequence with the real embedder against a ≥100,000-document corpus (T1, real). Record wall time, peak RSS, and docs/s, then compare them with §2.2's 27 docs/s. Real-embedder runs at T2/T3 are not required: they would take ≈10 h and ≈4 days, which is the point of N-18.

---

## 7. Delivery

Suggested split, each independently mergeable and testable:

| PR | Contents | Requirements |
|---|---|---|
| 1 | §2.0 reproduction test (xfail) + index-health state machine + truthful `doctor` | R3, AC0 (xfail), AC5–AC7 |
| 2 | Fail-loud retrieval: CLI exit code + `--json-v2`, MCP error, query `index_status`, daemon forwarding; no recovery on the read path | R1, R6.1, AC1–AC2a, AC14 |
| 3 | Self-healing `build`, guarded `_ensure_index`, truthful success line, `--rebuild-index` help fix; chunked, resumable, diff-only, locked recovery with progress | R2, R6.2–R6.7, AC0 (passes), AC3–AC4, AC12, AC15–AC18 |
| 4 | Watch single-instance lock | R4, AC8–AC10 |
| 5 | Version stamp in `meta` + preflight + `migrate-index` | R5, AC11, AC13 |
| 6 | T2/T3 tier workflows + `bench/scale/results.json` (recovery time measure-only) | R3.3, R6, AC19, AC21–AC22 |

PR 1 goes first. It is the smallest and pure diagnosis, PRs 2–3 read its state machine, and its reproduction test confirms (or refutes) §2.0 before any fix is written. PR 4 is fully independent and can land any time. PR 6 depends on PR 3's chunked writer, but its tier workflows can land early, measure-only with gates off, to record baselines. Persisted vectors ship under N-18, which builds on PR 3 and PR 6.

**Migration note.** PR 2 changes contracts on three surfaces. The CLI default `--json` and both healthy-index MCP payloads are unchanged (R1.4). The changes are a new exit code (69), a new MCP error `code`, and an additive `index_status` key. Audit the hooks and the MCP clients for code that treats `[]` as "no results", or that treats any non-zero `search` exit as fatal.

---

## 8. Why this matters beyond one project

Every defect here is a **silent-wrong-answer** class bug, which is the worst failure mode for a tool whose entire value proposition is "an agent can trust what I return."

The generalisable lessons:

1. **A tool that can return empty must distinguish "nothing" from "I couldn't look."** These are different answers and callers act on them differently.
2. **A write path must verify its own output.** `Build successful!` printed after a skipped, unrepaired index is a lie that costs hours of downstream debugging.
3. **A diagnostic must test the live thing, not a proxy for it.** `stale_path.exists()` is a proxy for "was quarantined once," not "is broken now."
4. **Long-running processes need mutual exclusion by default.** The locking primitive already existed in the codebase; it simply wasn't applied.

---

## 9. Open questions

| # | Question | Owner | Resolves by |
|---|---|---|---|
| Q1 | Does §2.0's mechanism (G1–G3) reproduce the incident, or did something else defeat recovery? | PR 1 | AC0 passing or failing for the right reason |
| Q2 | ~~Is exit code 3 free?~~ **Resolved in rev 3:** no, `daemon status` uses 3. R1.5 now uses 69 (`EX_UNAVAILABLE`), unused across `neuralmind/`. | — | resolved |
| Q3 | What R6.1 small-store threshold keeps first-touch recovery inside the MCP client timeouts actually in use (Claude Code, Cursor, Cline)? | PR 2 | measured client timeouts, recorded in the PR |
| Q4 | Do the projected 10M SQLite figures (§2.2 footnote 2) hold? | PR 6 | the first T3 run |

## 10. Revision history

| Rev | Date | Change |
|---|---|---|
| 1 | 2026-10-08 | First draft: five requirements, twelve ACs. |
| 2 | 2026-10-08 | Review fixes (Codex, Copilot on #621). Corrected F5: the baseline already recovers automatically. Added §2.0 gap analysis (G1–G3), the per-surface status contract, the V-vs-N state machine and the on-disk version stamp. Added measured scale tiers to 10M (§2.2–§2.3), R6, R7 and AC14–AC22. |
| 3 | 2026-10-08 | Split R7 and AC20 out to N-18, leaving a known-gap statement. Adopted RFC 2119 key words, stable IDs, evidence grades, the traceability matrix (§5.1) and open questions (§9). Moved the index-unavailable exit code from 3, already used by `daemon status`, to 69 (`EX_UNAVAILABLE`). |

---

## Appendix A — reproducing §2.2

Index timings (`pip install turbovec numpy`; `python bench.py <outdir> 10000 100000 1000000 10000000`). The 10M run needs ≈3 GB RAM and ≈2 GB disk:

```python
import os, sys, time, resource, numpy as np, turbovec
d, out = 384, sys.argv[1]
for n in map(int, sys.argv[2:]):
    idx, rng, C = turbovec.IdMapIndex(dim=d, bit_width=4), np.random.default_rng(0), 100_000
    t = time.perf_counter()
    for s in range(0, n, C):                      # chunked: bounded memory at any n
        c = min(C, n - s)
        x = rng.standard_normal((c, d)).astype(np.float32)
        x /= np.linalg.norm(x, axis=1, keepdims=True)
        idx.add_with_ids(x, np.arange(s + 1, s + c + 1, dtype=np.uint64))
    idx.prepare(); build = time.perf_counter() - t
    p = os.path.join(out, f"i{n}.tvim"); idx.write(p); del idx
    t = time.perf_counter(); j = turbovec.IdMapIndex.load(p); load = time.perf_counter() - t
    ids = np.arange(1, n + 1, dtype=np.uint64)
    t = time.perf_counter(); sum(j.contains(int(i)) for i in ids); diff = time.perf_counter() - t
    t = time.perf_counter(); j.search(x[:1], 5, allowlist=ids[: n // 2]); sa = time.perf_counter() - t
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    print(f"{n:,} build={build:.2f}s load={load*1e3:.0f}ms len={len(j)} diff={diff:.2f}s "
          f"allow50={sa*1e3:.0f}ms size={os.path.getsize(p)/1e6:.0f}MB peakRSS={rss:.0f}MB")
    try:
        j.search(x[:1], 5, allowlist=np.array([n + 5], dtype=np.uint64))
    except KeyError as e:
        print("  dangling allowlist ->", e)   # §2.0 G3
    del j; os.remove(p)
```

Store timings: a `nodes(uid INTEGER PRIMARY KEY, node_id TEXT UNIQUE, document TEXT, content_hash TEXT)` table with N rows of ~1 KB documents. Time the three queries in the §2.2 store table, warm (second run).

Embedder throughput: call `TurboVecEmbedder._embed_matrix` on 2,048 node-sized (~600-char) documents with the default ONNX MiniLM embedder, and divide by wall time.
