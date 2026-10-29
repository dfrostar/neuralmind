# NeuralMind v4.23.2 — a faster prompt hook on large repositories, and a type pass that no longer slows every build

**Type:** Patch release | **Theme:** the same output, sooner: the prompt hook stops paying for work it doesn't need, and the build's type pass reads each file once

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
  every hermes-agent build.

All three now skip that work. The block the agent gets, the graph and the
stored type edges come out identical, checked byte for byte.

---

## What changed

### The prompt hook exits without tearing down its graph

`neuralmind _hook` flushes its output and ends the process with `os._exit`.
The exit code and everything the hook printed are unchanged. Nothing in a
hook relies on cleanup at exit: there are no exit handlers, files are written
in `with` blocks, and background work (the graph-cache warmer, session
maintenance) runs in detached processes of its own.

### Loading an index asks only whether it has rows

Each vector backend has a cheap `has_rows()` check (`SELECT 1 … LIMIT 1` on
turbovec, a row count on ChromaDB), and loading an index uses it instead of
the full statistics. The notice printed when a load takes over two seconds
now reads `Loading index...`, without the node count it no longer has.

### The type verifier reads each file once, in one thread

The first lookup in a file builds a map from every function name in it to
its return type, in one pass; later lookups read the map. Each name keeps
the function the old search found first, so every lookup gets the same
answer: breadth-first for Python, as `ast.walk` searched, and depth-first
for the TypeScript, Go and Rust trees, as their search did. The pass runs in
one thread, and its edges come out in call-edge order, the same order every
build. Before, they came out in whatever order the threads finished.

## What the agent sees post-install

| Agent | Before | After |
|---|---|---|
| Claude Code (`UserPromptSubmit`) | The block, after the hook freed its graph and counted the index | The same block, 0.24 s sooner per prompt on hermes-agent, ~0.03 s on typical repositories (M3) |
| Hermes-Agent (plugin) | As above, through the plugin's `pre_llm_call` | As above |
| Cursor, Cline, generic MCP | The MCP server checks the index once when it loads | The same check without the count; no per-prompt hook |
| Anyone who builds | The type pass took 121–123 s of a hermes-agent build | 17 s, with the same type edges |

---

## Measured

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
`graph.json`, timed by itself):

| Repository | Type edges | v4.23.1 | v4.23.2 | Edges and risks |
|---|---|---|---|---|
| requests | 1,041 | 0.07 s | 0.04 s | identical |
| NeuralMind | 9,281 | 1.73 s | 0.56 s | identical |
| hermes-agent | 347,376 | 120.7 s, 123.3 s | 17.0 s | identical |

The remaining 17 s on hermes-agent is reading and parsing each of its 5,240
files once. The profile timed a full hermes-agent build at 1,180 s, with
129.6 s of it in this pass; that build wasn't rerun end to end here, so this
release doesn't quote a new total for it.

**A full build, end to end.** NeuralMind's own repository built from scratch
by each version (one build each: 29 s and 27 s) gave a byte-identical
`graph.json`, the same 6,010 stored type-edge rows (timestamps aside), the same
11,579 structural edges and synapse count, and the same prompt block.

Reproduce, from a source checkout, on a **copy** of a built project (the hook
writes to it):
`python -m tests.benchmark.hook_latency <project-copy> --states cached --runs 5`;
for the previous version, put its checkout on `PYTHONPATH`.

### What it doesn't change

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

### Tests

- `tests/test_cli.py`: a hook process keeps its output (200 KB, more than a
  pipe holds) and its exit code.
- `tests/test_graph_cache.py`: loading an index asks only whether it has
  rows, and an empty store still reports no index.
- `tests/test_turbovec_backend.py`: `has_rows()` before and after embedding,
  and after deleting every node.
- `tests/test_type_verifier.py`: a name defined twice keeps the first in
  breadth-first order (Python) and depth-first order (TypeScript), as the
  previous version's search found them (both tests pass on it too); each file
  is parsed once however many lookups it gets; a file that doesn't parse
  gives no types; the pass runs in one thread and keeps edge order.

### Upgrading

Nothing to do.
