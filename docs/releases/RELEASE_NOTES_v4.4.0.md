# NeuralMind v4.4.0 — the index is never silently out of step with the code

**Type:** Minor release | **Theme:** index freshness

On a real 383-file repository, v4.3.5 answered from a five-month-old code
graph and reported every check as `[ok]`. The committed
`graphify-out/graph.json` had been built on Windows (`tests\...` paths), lacked
every module added since, and NeuralMind never regenerates a graphify graph.
Escaping it took a hand-written `graphgen.build_graph()` call and deleting the
vector folder by hand. After switching graphs, the store still held ~2,900
vectors from the old graph that search could return.

v4.4.0 closes that trap. One rule runs through every change: **when the index
can't be brought in step automatically, it says so — in `doctor`, `health`,
`build` and the agent's first MCP call.**

## What changed

| | Before (v4.3.5) | Now (v4.4.0) |
|---|---|---|
| Graph vs disk | `doctor` checked only nodes carrying `embedded_at`, which graphify nodes never have → `[ok]` | New freshness check compares graph and files **both ways**, whatever tool made the graph |
| Escaping a stale graphify graph | No CLI way; deleting `.neuralmind/graph.json` silently fell back to the stale legacy graph | `build --regenerate-graph`, a `graph_source` setting, and no silent fallback |
| Orphaned vectors | `build` (even `--force`) never deleted vectors whose node left the graph | Every build purges them, with a safety valve; `doctor` FAILs on extra vectors |
| Read paths | Every CLI query and each MCP server's first call ran a full `build()` — re-walking the repo and printing to **stdout**, the MCP JSON-RPC channel | Queries load the index as it stands: no rebuild, no output |

### 1. Graph freshness check (`neuralmind/freshness.py`)

`graph_freshness(project)` reports:

- **files on disk not in the graph** — new code the index can't see;
- **files in the graph no longer on disk** — deleted or renamed code still served;
- **node paths using `\` on a POSIX host** — the graph was built on another OS;
- **files changed since the graph was built** — from `git diff` against the
  commit that last touched a *committed* graph (never checkout mtimes: a fresh
  clone stamps every file with the clone time), or from mtimes confirmed by
  content hash for the untracked built-in graph;
- **commits since the graph changed** — reported as *unknown* on a shallow
  clone instead of a misleading "0 behind".

FAIL when missing + gone exceed 10% of indexable files or any path uses
foreign separators; WARN for anything smaller; OK otherwise. It is stat calls
and a few git plumbing commands — no parsing — about 80 ms on a 600-file repo.

```
[FAIL] Code graph: graphify-out/graph.json (graphify, 2026-04-22, 214 commits behind HEAD)
       51 files on disk not in graph (lib/render/overlay.tsx, scripts/collect_stats.py, ...)
       3,176 node paths (319 files) use '\' separators (built on Windows)
       -> neuralmind build . --regenerate-graph
```

Where it shows up:

- **`neuralmind doctor`** — the *Code graph* check is now this report.
- **`neuralmind health`** — exit `1` now means the freshness check WARNs or
  FAILs; it used to mean "index ≥ 24 h old", which flagged a current index
  every morning and passed a stale one built an hour ago. `0` OK, `2` no
  index, unchanged.
- **`neuralmind build`** — runs the check before embedding and prints the
  report when it isn't OK. `--strict` exits `3` before embedding on FAIL.
- **MCP `neuralmind_wakeup`** — prefixes one line when the graph isn't OK, so
  the agent learns it in its first call:
  `Index is stale: 51 files missing from graph; graph built on another OS. Run neuralmind build /repo --regenerate-graph.`

### 2. Escaping a stale graphify graph

- **`neuralmind build . --regenerate-graph`** always rebuilds
  `.neuralmind/graph.json` with the built-in tree-sitter backend and says what
  it ignored: `Graph source: built-in (tree-sitter), 8,351 nodes. Ignoring graphify-out/graph.json (graphify, 2026-04-22).`
  Later plain builds update it incrementally. `graphify-out/` is never written.
- **`graph_source` in `.neuralmind.yaml`:**

  | Value | Behaviour |
  |---|---|
  | `auto` (default) | Built-in graph when present, else the graphify graph. A graphify graph that **FAILs** freshness is replaced by a built-in graph at build time (when there is code on disk to parse), with the reason printed |
  | `builtin` | Always the tree-sitter graph; `graphify-out/` is never read |
  | `graphify` | Only `graphify-out/graph.json`; the build fails if it is missing. For teams that run graphify in CI |

- **No silent fallback.** If the last build used the built-in graph and it has
  since gone, the build stops and names both ways out (`--regenerate-graph` or
  `graph_source: graphify`) instead of quietly serving the legacy graph.
- **The source is always named.** Every build prints a `Graph:` line —
  `Graph: .neuralmind/graph.json (built-in, incremental, 8,351 nodes)` or
  `Graph: graphify-out/graph.json (graphify, read-only, 3,197 nodes)` — and
  records it in `.neuralmind/build_status.json` (shown by `build-status`).

### 3. Orphaned vectors are purged

- At the end of every build, vectors whose node left the graph are deleted —
  from the vector index **and** the BM25 keyword index, on both the turbovec
  and ChromaDB backends, per scope for scoped stores.
- Content ingested with `ingest` / `ingest-content` lives in the same store
  without being in the graph and is **never** a purge candidate.
- The build summary shows it: `Delta: +12 new, ~4 updated, =8,320 skipped, -2,879 removed`.
- **Safety valve:** when orphans exceed half the store (a wrong path, an empty
  parse, a deliberate source switch), they are kept with a warning;
  `build --prune` removes them.
- **`doctor`'s Semantic index check** compares the store with the graph:
  equal → OK; extra vectors → FAIL `2,879 vectors not in graph (stale results possible)`;
  graph nodes without a vector → WARN.

### 4. Read paths are quiet and never rebuild

- `query`, `search`, `wakeup`, `skeleton`, the MCP tools and the daemon load
  an existing index as it stands — no graph regeneration, no embedding pass.
  A stale index is reported by the freshness check, never silently rebuilt.
  A project with **no** index is still built on first use, as before.
- Build notices go to stderr unless the `build` command asks for them, so
  nothing reaches the MCP server's stdout outside JSON-RPC frames.
- The `Embedding x/N` progress bar shows only on an interactive terminal;
  piped or captured, a build prints just its summary.
- Loading a large index prints one line, `Loading index (8,936 nodes)...`,
  only if it takes over 2 s.

## What the agent actually sees post-install

| Agent | Before | After |
|---|---|---|
| **Claude Code** (MCP + hooks) | Answers from whatever graph exists, stale or not; the first query in a session triggers a rebuild | First `neuralmind_wakeup` starts with `Index is stale: …` when the graph lags the code; queries answer from the loaded index without rebuilding |
| **Cursor / Cline / Continue** (MCP) | Same, and the rebuild's `[neuralmind] generated code graph…` line could land on the JSON-RPC stdout | Same stale line in the wakeup; stdout carries only protocol frames |
| **Generic MCP client** | `neuralmind_health` reported "stale" by age only | `neuralmind_health` returns the freshness report (`freshness.status`, the missing/gone/changed lists) |
| **CI** | `neuralmind health` failed every 24 h regardless | `neuralmind health .` fails only when the graph is out of step; `neuralmind build . --strict` exits 3 on a FAIL graph |

## Upgrade notes

- **No action needed** for a project on the built-in graph or a current
  graphify graph — behaviour is unchanged apart from the new `Graph:` line and
  the purge of any orphans.
- **A stale graphify graph** is now replaced by a built-in graph on the next
  `build` (auto mode). To keep using graphify regardless, set
  `graph_source: graphify` in `.neuralmind.yaml`.
- **`health` exit 1 changed meaning:** it now means "graph out of step with the
  code", not "older than 24 h". Scripts that rebuilt on exit 1 keep working and
  rebuild less often.
- **First build after upgrading** may remove vectors left by an old graph; the
  `-N removed` delta shows how many.

## Related

- Use case: [Recover from a stale code graph](../use-cases/recover-from-a-stale-graph.md)
- CLI reference: [`build`](../wiki/CLI-Reference.md#build), [`doctor`](../wiki/CLI-Reference.md#doctor-v0120), [`health`](../wiki/CLI-Reference.md#health-v314)
