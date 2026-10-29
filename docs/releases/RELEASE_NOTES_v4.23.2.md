# NeuralMind v4.23.2 — a faster prompt hook on large repositories, a type pass that no longer slows every build, and an upgrade that keeps the graph cache

**Type:** Patch release | **Theme:** the same output, sooner: the prompt hook stops paying for work it doesn't need, the build's type pass reads each file once (and on a rebuild only the files that changed), and an upgrade no longer throws away a large repository's graph cache, so the Hermes plugin's first turn after it gets its block

A profile of NeuralMind 4.23.1 on an M3 split the prompt hook and the build
into phases. On a typical repository the hook already takes under half a
second, and most of that is starting a Python process. A full build is
79–85% ONNX embedding, which is already native code. But some of the time
went to work that changes nothing in the result:

- **The prompt hook freed its graph at exit.** On a large index the hook
  holds its graph in a reference cycle, so Python's exit spent ~0.16 s
  freeing ~1.4 GB of objects the process was about to drop anyway.
- **Loading an index counted every community.** Before reading the graph,
  the hook asked the vector store for its statistics, a count of every row
  grouped by community, only to learn that the store wasn't empty: ~65 ms on
  hermes-agent.
- **The type pass searched each file once per callee.** The build's type
  verifier, which annotates call edges with return types, read a file's whole
  syntax tree again for every distinct function it looked up there, in a pool
  of eight threads that only contended for Python's global lock: 121–123 s of
  every hermes-agent build. And every build, incremental ones included,
  parsed every file again, whether it had changed or not.

All three now skip that work. The block the agent gets, the graph and the
stored type edges come out identical, checked byte for byte.

A fourth cost came from outside the profile.
v4.23.0 made the per-prompt hook fast on a large index by keeping the loaded
graph in `.neuralmind/graph_cache.marshal`. That file's header named the
NeuralMind release that wrote it, so every upgrade made every large index read
its graph from `index_ir.json` again, once. In a live Hermes smoke test of
v4.23.1 on an M3, on hermes-agent (269,151 nodes, a 424 MB `index_ir.json`),
the first turn after the cache went stale ran past the plugin's 8 s timeout
(`NEURALMIND_HERMES_TIMEOUT`) and went ahead without its recall block. Timed
with `tests/benchmark/hook_latency.py`, such a call took 6.4–8.2 s there. The
next turn was fast again, because the stopped call had started a background
process that rewrote the cache.

No release since the cache began has changed how the graph is read. The
header named the release only because the conversion from `index_ir.json` to
the graph *could* change between releases.

---

## What changed

### The prompt hook exits without tearing down its graph

`neuralmind _hook` flushes its output and ends the process with `os._exit`.
The exit code and everything the hook printed are unchanged. Nothing in a
hook relies on cleanup at exit: NeuralMind registers no exit handler
(logging's has nothing left to flush), files are written in `with` blocks,
and background work (the graph-cache warmer, session maintenance) runs in
detached processes of its own. An independent review ran all eleven hook
actions and found nothing left for the interpreter's exit to do.

### Loading an index asks only whether it has rows

Each vector backend has a cheap `has_rows()` check (`SELECT 1 … LIMIT 1` on
turbovec, a row count on ChromaDB), and loading an index uses it instead of
the full statistics. The notice printed when a load takes over two seconds,
`Loading index (8,936 nodes)...`, still names the count: it is counted only
then, so a fast load never pays for it.

### The type verifier reads each file once, in one thread

The first lookup in a file builds a map from every function name in it to
its return type, in one pass; later lookups read the map. Each name keeps
the function the old search found first, so every lookup gets the same
answer: breadth-first for Python, as `ast.walk` searched, and depth-first
for the TypeScript, Go and Rust trees, as their search did. The pass runs in
one thread, and its edges come out in call-edge order, the same order every
build. Before, they came out in whatever order the threads finished.

One thread also ends a race. When a call's target has no source file, the
verifier looks the name up in a project-wide function index it builds on
first use, and with eight threads some lookups read that index while another
thread was still filling it: v4.23.1 dropped some type edges at random on
such a project. An independent review measured 21–23 edges across 12 runs on
one; v4.23.2 gives all 23 every time. hermes-agent, NeuralMind, requests and
the test fixtures never build that index, so their results below are the
same as before.

A first build walks less, too: the Python pass visits only the statements a
function can be defined in, which meets functions in the same breadth-first
order as `ast.walk` over every node, and the tree-sitter trees are walked
with a cursor.

### A rebuild parses only the files that changed

Each file's map is kept in `.neuralmind/type_cache.json`, keyed by a hash of
the file's text, so the next build reuses it while the text is the same. A
build reads a file again only when its size, modification time, inode change
time or inode differ from the last build's, and parses it again only when its
hash differs too. A file changed in the last 10 seconds is always hashed: a
second edit inside the filesystem's timestamp resolution can leave its size
and modification time as they were. On Windows, where `st_ctime` is the
creation time rather than the inode change time, every file is hashed.

The function index that resolves a call with no source file is kept the same
way, with its own rules for which directories it skips. A file the build no
longer reaches drops out of the cache, and a cache written by another Python
or tree-sitter version is ignored. Like the rest of `.neuralmind/`, the file
isn't committed: the directory ignores itself. Deleting it costs one build at
first-build speed and changes nothing in the result.

### An upgrade keeps the graph cache

- **The header names the conversion, not the release.** It holds a format
  number (`graph_cache.FORMAT`, now 1) in place of the NeuralMind version. A
  release that changes how the same files load as a graph bumps it, and only
  then does the cache get read from its sources again. The rest of the header
  is unchanged: both source files' size, modification time and inode, and the
  Python version, since `marshal`'s format belongs to the interpreter.
- **A cache written by 4.23.0 or 4.23.1 is still read.** They put their own
  version in the header. Their conversion code is byte for byte the code of
  format 1, so their headers count as format 1. The upgrade to this release is
  therefore already fast. That stops once the format changes.
- **A forgotten bump fails CI.** `tests/test_graph_cache.py` fingerprints the
  source of the code the format covers: which file wins
  (`graph_cache.prefer_ir`), `graph_cache._read_sources`, and in
  `neuralmind/ir.py` `IndexIR.from_dict` and the record parsers it calls,
  `migrate_payload`, `to_graph_json` and the supported IR versions. When any of
  that code changes, the test fails and says to bump `FORMAT` if the same
  files can now load differently. The fingerprint is the same on Python 3.11
  to 3.14, and for v4.23.0, v4.23.1 and this release.

The cache still changes how fast the graph loads, never what loads: a header
that doesn't match, a damaged file or anything that isn't a graph is read
from the sources, as before.

## What the agent sees post-install

| Agent | Before | After |
|---|---|---|
| Claude Code (`UserPromptSubmit`) | The block, after the hook freed its graph and counted the index | The same block, 0.24 s sooner per prompt on hermes-agent, ~0.03 s on typical repositories (M3) |
| Claude Code, large repository, first prompt after an upgrade | Waited for the graph to be read again (Claude Code doesn't stop the hook at 8 s, so only slower) | As fast as any other prompt |
| Hermes-Agent (plugin) | As above, through the plugin's `pre_llm_call` | As above |
| Hermes-Agent (plugin), large repository, first turn after an upgrade | The turn's recall read the whole graph again. On hermes-agent that call took 8.3–10.5 s here, so the turn could go without its block | The upgrade keeps the cache: that first call took 1.4–1.9 s, the same block |
| Cursor, Cline, generic MCP | The MCP server checks the index once when it loads | The same check, cheaper; no per-prompt hook |
| Every command that loads an index (`query`, MCP tools) | Read the graph again once after each upgrade | Use the cache across upgrades |
| Anyone who builds | The type pass took 121–123 s of every hermes-agent build | 16 s on a first build and ~1 s on a rebuild, with the same type edges |
| A repository whose graph file is under 16 MB | Never cached; unaffected by the upgrade change | Unchanged |

---

## Measured

### The prompt hook and the type pass

On an M3 MacBook (8 cores, 16 GB), alternating the previous version (main
at `a2f6ecd2`) and this one over three rounds, with the load average around
3. Raw results: `bench/hook_latency/speed-v4.23.2-m3.json`.

**The prompt hook** (`tests/benchmark/hook_latency.py --states cached`, 5
calls per round, so 15 per version; mean of the round means, and the range
of single calls):

| Repository (index nodes) | v4.23.1 | v4.23.2 | Block |
|---|---|---|---|
| requests (1,112) | 0.45 s (0.44–0.45) | 0.42 s (0.42–0.43) | same SHA-256 on every call |
| NeuralMind (~8,000) | 0.55 s (0.54–0.57) | 0.52 s (0.51–0.54) | same |
| hermes-agent (269,151) | 1.40 s (1.31–1.88) | 1.16 s (1.08–1.41) | same |

The saving on hermes-agent, 0.24 s, is most of what the profile attributed
to the two changes (~0.16 s teardown, ~0.07 s row count). On the small
repositories it is the teardown alone.

**The type verifier** (`TypeVerifier.augment_graph` on each project's
`graph.json`, timed by itself; one run each on hermes-agent and requests, two
on NeuralMind, while other sessions' jobs shared the machine). A first build
starts with no `.neuralmind/type_cache.json`; a rebuild runs on the same
files with the cache the first build wrote:

| Repository | Type edges | v4.23.1 | v4.23.2, first build | v4.23.2, rebuild | Edges, rows and risks |
|---|---|---|---|---|---|
| requests | 1,041 | 0.08 s | 0.05 s | 0.01 s | identical |
| NeuralMind | 9,364 | 1.9–2.2 s | 0.43–0.45 s | 0.02 s | identical |
| hermes-agent | 347,376 | 122.2 s (120.7 s, 123.3 s in earlier runs) | 15.9 s | 1.0–1.2 s | identical |

On hermes-agent a rebuild after editing one file took 1.1 s, and the cache
file is 9.9 MB. Hashing every file instead of trusting the stat, as on
Windows, took 1.0 s. A first build still reads and parses each of the 5,240
files once; reading each file once without the cache, the pass took 17.2 s
there, 0.55–0.59 s on NeuralMind and 0.04 s on requests. The profile timed
a full hermes-agent build at 1,180 s, with 129.6 s of it in this pass; that
build wasn't rerun end to end here, so this release doesn't quote a new
total for it.

**A full build, end to end.** NeuralMind's own repository built from scratch
by each version (one build each: 29 s and 27 s) gave a byte-identical
`graph.json`, the same 6,010 stored type-edge rows (timestamps aside), the same
11,579 structural edges and synapse count, and the same prompt block. The
sample fixture (`tests/fixtures/sample_project`) built with v4.23.1's type
pass and with the cached one, then rebuilt on the warm cache, gave the same
`graph.json`, the same 49 stored type-edge rows and the same prompt block
SHA-256.

Reproduce, from a source checkout, on a **copy** of a built project (the hook
writes to it):
`python -m tests.benchmark.hook_latency <project-copy> --states cached --runs 5`;
for the previous version, put its checkout on `PYTHONPATH`.

### The first prompt after an upgrade

These runs measured the cache change on its own, before the speed-ups above
were merged: "this release" in them is v4.23.1 plus the new cache header.

`tests/benchmark/hook_latency.py` on held-out task 0cb3760383's hermes-agent
index and prompt, on an M3. macOS's `mediaanalysisd` used about 1.3 cores
throughout, so load averages were 6–9, and every time here is slower than on
an idle machine. Each NeuralMind ran from a copy on `PYTHONPATH`. To simulate
an upgrade, the same code ran with `__version__` set to 4.99.0 on the cache
the previous step left. The steps ran in turn, on one index. Raw results:
[`bench/hook_latency/upgrade-hermes-agent-0cb3760383-m3.json`](../../bench/hook_latency/upgrade-hermes-agent-0cb3760383-m3.json).

| Cache written by | Code after the upgrade | First call | Calls 2–5 | Within 8 s |
|---|---|---|---|---|
| v4.23.1 | v4.23.1 | 8.75 s | 1.47–1.67 s | 4 of 5 |
| v4.23.1 | v4.23.1 (run again later) | 10.50 s | 1.52–1.80 s | 4 of 5 |
| this release | this release | 1.85 s | 1.50–1.99 s | 5 of 5 |
| v4.23.1 | this release | 1.44 s | 1.55–1.91 s | 5 of 5 |

The other states, from the full runs of each version:

| | uncached | cache missing | cached |
|---|---|---|---|
| v4.23.1 | 6.95 s (6.50–8.11) | 7.84 s (7.54–8.24) | 1.44 s (1.43–1.45) |
| this release | 7.26 s (6.57–8.68) | 8.79 s (7.83–9.83) | 1.59 s (1.46–1.68) |

This release doesn't change a miss, only how often one happens. The two rows
ran minutes apart on a loaded machine; the upgrade rows above alternated
between versions. Every one of the 51 timed calls returned the same block,
SHA-256
`cf55ceb9a220a8072b351f0f0eab4eb12d2e4c5030f9a03e52d60e0eaa30270c`. That's the
hash the v4.23.1 smoke test recorded.

## What it doesn't change

- **The output.** Every check above compares the block, the graph or the
  type edges byte for byte, and they match.
- **Embedding.** It is still 79–85% of a full build, and it already runs in
  onnxruntime's native code. Making it faster without changing the vectors
  means not embedding the same text twice, which is a separate change.
- **A known issue in incremental builds, found while measuring.** When a
  function name is defined in more than one file, an incremental build can
  resolve a call to a different one of them than a full build does: it
  registers the unchanged files' symbols before the re-extracted files'.
  A fix, together with the incremental scan's own problem (on NeuralMind's
  repository it counts 372 ignored files as new on every build), comes in a
  later release, checked against full builds.
- **A cache missing, or a graph changed outside `build`,** is read from the
  sources, as before. The background writer still rewrites the cache, so a
  turn the plugin stops leaves it for the next one.
- **A new Python minor version** still reads the graph again once, because
  `marshal`'s format can differ between interpreters. So does a release that
  bumps `FORMAT`, and its notes will say so.
- **Going back to v4.23.1 or older** reads the graph again once. Those
  releases don't recognise the new header (8.34 s for that call above).

## Tests

- `tests/test_cli.py`: a hook process keeps its output (200 KB, more than a
  pipe holds) and its exit code.
- `tests/test_graph_cache.py`: loading an index asks only whether it has
  rows, and an empty store still reports no index.
- `tests/test_turbovec_backend.py`: `has_rows()` before and after embedding,
  and after deleting every node.
- `tests/test_type_verifier.py`: a name defined twice keeps the first in
  breadth-first order (Python) and depth-first order (TypeScript), as the
  previous version's search found them (both tests pass on it too); each file
  is walked once however many lookups it gets (this one fails on the previous
  version); a file that doesn't parse gives no types; the pass runs in one
  thread and keeps edge order.
- `tests/test_type_verifier.py`, against a copy of v4.23.1's per-lookup
  search kept in the test: every language fixture under `tests/fixtures/`,
  with the graph the build extracts and with its committed graph, gives the
  same type edges and stored rows on a first build and on a rebuild. So does
  a project of edge cases: a name defined at several depths, a file that
  doesn't parse, a file that's gone, calls resolved through the function
  index (and the directories it skips), TypeScript, Go and Rust.
- `tests/test_type_verifier.py`, the cache: a rebuild parses no file, and
  reads none when their stat matches; an edit that keeps the file's size and
  restores its modification time is still seen; a deleted file leaves the
  cache; a corrupt cache, or one from another version, is ignored and
  rewritten; a project without `.neuralmind/` gets no cache file.

`tests/test_graph_cache.py` checks that:

- an upgrade keeps the cache, and starts no background writer;
- a cache of another format is read from its sources and rewritten;
- a cache with the header 4.23.0 or 4.23.1 wrote is read, while the format is
  1, and not once it changes;
- a cache another release keyed on its version is not read;
- the code the format covers matches its recorded fingerprint.

The test that a cache from another NeuralMind version is never read is gone:
that is the behaviour this release changes.

## Upgrading

```bash
pip install -U neuralmind
```

Nothing else to do. Caches written by v4.23.0 or v4.23.1 are kept, so even
this upgrade's first prompt is fast. If you ran `neuralmind build` or a query
after upgrading only to warm the cache, you can skip that from now on.

## Use cases

- **Existing: [NeuralMind in Hermes](../use-cases/hermes-agent.md).** Upgrading
  NeuralMind no longer costs a large repository's next Hermes turn its recall.
- **Potential: upgrades with no warm-up step.** v4.23.0's notes suggested
  running `neuralmind build` or a query after upgrading, to write the cache
  before the first Hermes turn. An unattended upgrade (`pipx upgrade-all` on
  a schedule, say) had no such step, so the first turn after it on each large
  repository could lose its block. It no longer needs one.
