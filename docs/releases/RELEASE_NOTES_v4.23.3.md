# NeuralMind v4.23.3 — a rebuild's type pass parses only the files that changed

**Type:** Patch release | **Theme:** the same output, sooner on every rebuild

v4.23.2 made the build's type pass, which annotates call edges with return
types, read each file once: 17 s of a hermes-agent build instead of 122 s.
It still parsed every file on every build, incremental ones included, so a
build after a one-line commit paid the same 17 s as a build from scratch.
Every `neuralmind build` runs that pass, including the git hooks' rebuilds
after a commit, pull, merge or branch switch.

This release keeps each file's results between builds. The type edges, the
rows the synapse store keeps and the block the agent gets come out
identical, checked byte for byte.

---

## What changed

### The type pass keeps each file's results between builds

The pass reduces each file to a map from every function name in it to its
return type. That map is now kept in `.neuralmind/type_cache.json`, keyed by
a hash of the file's text, so the next build reuses it while the text is the
same:

- **A file is read again** only when its size, modification time, inode
  change time or inode differ from the last build's, and **parsed again**
  only when its hash differs too.
- **A file changed in the last 10 seconds is always hashed.** A second edit
  inside the filesystem's timestamp resolution can leave its size and
  modification time as they were.
- **On Windows every file is hashed**, because `st_ctime` is the creation
  time there, not the inode change time.
- **The function index** that resolves a call with no source file is built
  from the same per-file results, with its own rules for which directories
  it skips. It no longer walks into the directories it skips.
- **A file the build no longer reaches drops out of the cache**, and a cache
  written by another Python or tree-sitter version is ignored.

Like the rest of `.neuralmind/`, the file isn't committed: the directory
ignores itself. Deleting it costs one build at first-build speed and changes
nothing in the result.

A first build walks less, too. The Python pass visits only the statements a
function can be defined in, which meets functions in the same breadth-first
order as `ast.walk` over every node, and the tree-sitter trees are walked
with a cursor. Parsing still dominates a first build, so that saves about a
second on hermes-agent.

## What the agent sees post-install

| Agent | Before | After |
|---|---|---|
| Claude Code (`UserPromptSubmit`) | The block from the last build | The same block; a rebuild after a commit or pull (the git hooks) finishes its type pass in about 1 s instead of 17 s on hermes-agent |
| Hermes-Agent (plugin) | As above | As above |
| Cursor, Cline, generic MCP | The index the last build wrote | The same index, written sooner |
| Anyone who builds | The type pass took 17 s of every hermes-agent build, first or not | 16 s on a first build, ~1 s on a rebuild, with the same type edges |

---

## Measured

### The type pass

`TypeVerifier.augment_graph` on each project's `graph.json`, timed by
itself, on an M3 MacBook (8 cores, 16 GB). One run each on hermes-agent and
requests, two on NeuralMind, while other sessions' jobs shared the machine.
A first build starts with no `.neuralmind/type_cache.json`; a rebuild runs
on the same files with the cache the first build wrote.

| Repository | Type edges | v4.23.2 | v4.23.3, first build | v4.23.3, rebuild | Edges, rows and risks |
|---|---|---|---|---|---|
| requests | 1,041 | 0.04 s | 0.05 s | 0.01 s | identical |
| NeuralMind | 9,364 | 0.55–0.59 s | 0.43–0.45 s | 0.02 s | identical |
| hermes-agent | 347,376 | 17.2 s | 15.9 s | 1.0–1.2 s | identical |

On hermes-agent:

- a rebuild after editing one file took 1.1 s;
- hashing every file instead of trusting the stat, as on Windows, took
  1.0 s;
- the cache file is 9.9 MB;
- v4.23.1 took 122.2 s on the same graph.

"Identical" means the multiset of `graph["type_edges"]`, the rows
`persist_type_edges` writes, and `detect_type_risks`'s output, compared
with v4.23.1's code and v4.23.2's. On hermes-agent that's 347,376 edges,
258,415 rows and 159,919 risks, on a first build, a rebuild, a rebuild
hashing every file and a rebuild after the one-file edit.

**The prompt block.** The sample fixture (`tests/fixtures/sample_project`)
was built with v4.23.1's type pass, whose output v4.23.2's matches, and with
this one, then rebuilt on the warm cache. Both gave the same `graph.json`,
the same 49 stored type-edge rows and the same prompt block SHA-256
(`tests/benchmark/hook_latency.py`, 3 calls each).

## What it doesn't change

- **The output.** Every check above compares type edges, stored rows, risks
  or the block, and they match.
- **A first build.** It still parses every file once: 15.9 s on
  hermes-agent.
- **Old quirks, kept so the output stays the same:**
  - Rust files never enter the function index; it asks for a grammar named
    `"rs"`.
  - A project inside a dot-directory gets an empty function index, because
    the skip rule checks the whole path.
  - TypeScript arrow-function parameter names count as function names.

## Tests

- `tests/test_type_verifier.py`, against a copy of v4.23.1's per-lookup
  search kept in the test: every language fixture under `tests/fixtures/`,
  with the graph the build extracts and with its committed graph, gives the
  same type edges and stored rows on a first build and on a rebuild. So does
  a project of edge cases: a name defined at several depths, a file that
  doesn't parse, a file that's gone, calls resolved through the function
  index (and the directories it skips), TypeScript, Go and Rust.
- `tests/test_type_verifier.py`, the cache:
  - a rebuild parses no file, and reads none when their stat matches;
  - an edit that keeps the file's size and restores its modification time
    is still seen;
  - a deleted file leaves the cache;
  - a corrupt cache, or one from another version, is ignored and rewritten;
  - a project without `.neuralmind/` gets no cache file.
- The one-walk-per-file test now counts node visits rather than `ast.walk`
  calls, so it holds for any walk. It still fails on v4.23.1.

## Upgrading

```bash
pip install -U neuralmind
```

Nothing else to do. The first build after upgrading runs the type pass at
first-build speed and writes `.neuralmind/type_cache.json`; later builds
reuse it.

## Use cases

- **Existing: [a growing monorepo](../use-cases/growing-monorepo.md).** The
  post-commit hook rebuilds after every commit. On a large repository its
  type pass no longer costs the same as a build from scratch.
- **Potential: CI that caches `.neuralmind/` between runs.** The cache is
  keyed by each file's text, not its path or timestamps, so a cache restored
  onto a fresh checkout still matches every unchanged file: the stat check
  misses, the hash matches, and the file isn't parsed. A CI job like the
  walkthrough's, restoring `.neuralmind/` before `neuralmind build`, then
  skips this pass's parsing for unchanged files. That holds while the
  runner's Python and tree-sitter versions stay the same; a cache written by
  others is ignored.
