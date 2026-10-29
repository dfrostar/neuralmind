# NeuralMind v4.23.3 — a rebuild gives the graph a full build gives, re-extracts far less, and its type pass parses only the files that changed

**Type:** Patch release | **Theme:** the same output, sooner on every rebuild: an incremental build now writes what a full build writes, byte for byte, and neither its graph extraction nor its type pass redoes work an edit can't affect

v4.23.2 made the build's type pass, which annotates call edges with return
types, read each file once: 17 s of a hermes-agent build instead of 122 s.
It still parsed every file on every build, incremental ones included, so a
build after a one-line commit paid the same 17 s as a build from scratch.
Every `neuralmind build` runs that pass, including the git hooks' rebuilds
after a commit, pull, merge or branch switch.

This release keeps each file's results between builds. The type edges, the
rows the synapse store keeps and the block the agent gets come out
identical, checked byte for byte.

A profile of NeuralMind 4.23.1 also found that rebuilding NeuralMind's own
repository after a one-file edit extracted the graph for longer than a full
build did. Two problems lay behind that, and fixing the first exposed more:

- **Ignored files counted as new on every build.** The incremental scan
  walked the tree without `.gitignore`, `.neuralmindignore` or the
  `.neuralmind.yaml` globs, while the extraction cache only ever held the
  files a build indexes. On NeuralMind's repository, 372 files its
  `.neuralmindignore` excludes (`tests/`, `docs/`, `*.config.js`) came back
  as "added" every time, and the search for files naming them re-extracted
  almost everything.
- **A rebuild could link a call to a different function than a full build.**
  A call resolves by name to the first function of that name in build order.
  An incremental build registered the unchanged files' names before the
  re-extracted files', so with two functions called `load`, a call could
  point at the wrong one. The first problem hid this on NeuralMind's own
  repository, by making every rebuild an almost full one; on a repository
  with nothing ignored, any rebuild could show it.
- **Gaining, losing or renaming a name didn't move its callers.** A function
  added under an existing name should take over calls in files nobody
  edited, and a package rename moves every import of it. Only files that
  imported the changed one were re-extracted, which missed both and, on a
  large repository, re-extracted most of it anyway.
- **The file watcher's updates** (`neuralmind watch --reindex`) differed
  from a full build on every one of 16 random edits.

All are fixed. An incremental build now writes the same `graph.json` as a
full build, byte for byte, and re-extracts only what a change can affect.

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

### An incremental build gives the graph a full build gives

#### The scan uses the build's own file list

It compares the extraction cache with the files the build indexes, after
`.gitignore`, `.neuralmindignore` and the config's globs, so an ignored file
is never "added", and a file that becomes ignored leaves the graph like a
deleted one.

#### Each unchanged file keeps its place

Its names go into the lookup tables, and its nodes and edges into the graph,
where a full build would have extracted that file. So a call resolves to the
same function as in a full build, and nodes and edges come out in the same
order. Python, TypeScript, Go, Rust and C/C++ files replay this from the
previous graph. Java, C#, PHP and Ruby take module names from a file's
`package` or `namespace` line, which the graph doesn't record, so an
unchanged file in those languages is parsed again for it.

#### What a change can affect is re-extracted, and only that

- the changed files;
- every file that names a function, class or module a change added, removed
  or reordered, so a function added under an existing name takes over the
  calls it should, and a package rename moves its imports. A header in a C++
  project is read as C++ for this, as the build reads it;
- every user of a stand-in node for an external base class (`class X extends
  EventEmitter`) that a changed or deleted file owned: the first file in
  build order that uses one owns it, and the next one takes it over.

Files that only import a changed one keep their edges: the nodes those point
at come back under the same ids. Before, a change re-extracted every file
that imported it, those files' importers, and so on.

#### The file watcher uses the same rules

`update_files`, which `neuralmind watch --reindex` calls, gives the same nodes
and edges as a full build. Its output was never in a build's order, and still
isn't.

#### Carrying community numbers over is no longer quadratic

It rebuilt the set of current files once for every node of the previous
graph: 38 s of a one-file rebuild of hermes-agent's graph.

## What the agent sees post-install

| Agent | Before | After |
|---|---|---|
| Claude Code (`UserPromptSubmit`) | The block from the last build | The same block; a rebuild after a commit or pull (the git hooks) finishes its type pass in about 1 s instead of 17 s on hermes-agent |
| Hermes-Agent (plugin) | As above | As above |
| Cursor, Cline, generic MCP | The index the last build wrote | The same index, written sooner |
| Every agent, after an incremental rebuild | A call in an unedited file could point at a different same-named function than after a full build, and so could the context built from it | The graph a full build gives, so the same context however the index was built |
| Anyone who builds | The type pass took 17 s of every hermes-agent build, first or not | 16 s on a first build, ~1 s on a rebuild, with the same type edges |
| Anyone who rebuilds after an edit (`neuralmind build`, the git hooks, `watch --reindex`) | A one-file graph rebuild took 1.6–1.9 s on NeuralMind and 80.5–82.6 s on hermes-agent, longer than a full build | 0.27–0.81 s and 9.8–10.7 s |

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

### Graph extraction

`graphgen.write_graph` alone, one-file edits, on an M3. v4.23.2's graph
extraction is v4.23.1's:

| | v4.23.2 | v4.23.3 | full build |
|---|---|---|---|
| NeuralMind | 1.6–1.9 s | 0.27–0.81 s, median 0.49 s | 0.75–0.83 s |
| hermes-agent (10,270 code files) | 80.5–82.6 s, and a graph that differs from a full build's | 9.8–10.7 s | 34.5–36.0 s |

A comment edit to `neuralmind/embedder.py`, which defines a property and its
setter, re-extracts 1 file.

Every incremental graph was compared, byte for byte, with a full
re-extraction of the same tree that keeps the previous `graph.json`, so
community numbers carry over the same way:

- 30 of 30 random edits on NeuralMind's repository, and 4 of 4 on
  hermes-agent (functions added under existing names, removed, renamed and
  moved; files added and deleted);
- every language fixture through five edits each (a comment, a function
  gaining a name other files call, that name renamed, a file added, a file
  deleted; the comment, the addition and the deletion where no file calls
  another);
- targeted cases: stand-in nodes changing owner both ways, a Java package
  rename, a Java file importing an unchanged one, a header in a C++ project
  gaining a method.

All matched. A full build gives the same `graph.json` as v4.23.2 on
NeuralMind, requests, hermes-agent and every fixture.

## What it doesn't change

- **The output.** Every check above compares type edges, stored rows, risks
  or the block, and they match. A full build's `graph.json` is
  byte-identical to v4.23.2's.
- **A first build.** It still parses every file once: 15.9 s on
  hermes-agent for the type pass.
- **Community numbers.** An incremental build keeps each existing file's
  community number, as before, so the embedder can skip unchanged nodes.
- **One known difference remains.** When one file defines the same class
  name twice, a re-extracted subclass of it gets one `inherits` edge to it
  where a full build gives two (a duplicate). Calls aren't affected. No file
  in NeuralMind or hermes-agent subclasses such a class.
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
- `tests/test_incremental_matches_full.py`: incremental builds and the
  watcher's `update_files` against a full re-extraction: calls with two
  same-named functions, a name gained, removed or renamed, stand-in nodes
  changing owner, a Java package rename and a Java file importing an
  unchanged one, a header in a C++ project gaining a method, and a comment
  edit to a file with a property and its setter re-extracting only that
  file.
- `tests/test_incremental_every_fixture.py`: every language fixture through
  the five edits above, byte for byte for the build and the same nodes and
  edges for `update_files`. It fails on v4.23.2.
- `tests/test_incremental_wiring.py`: an ignored file never counts as a
  change, and one that stops being ignored is added; an extraction cache from
  an earlier version is dropped, so a call edge an older incremental build
  got wrong is rebuilt.
- `tests/test_incremental_detection.py`: a file that only names a new module
  no longer brings its importers along.

## Upgrading

```bash
pip install -U neuralmind
```

Nothing else to do. The first build after upgrading runs the type pass at
first-build speed and writes `.neuralmind/type_cache.json`; later builds
reuse it.

It also extracts the whole graph once: the extraction cache from earlier
versions is dropped, because an incremental build in those versions could
have left a call pointing at the wrong function, and incremental builds now
carry unchanged files' edges over. Embeddings are cached by content, so
only nodes whose text or edges changed are embedded again.

## Use cases

- **Existing: [a growing monorepo](../use-cases/growing-monorepo.md).** The
  post-commit hook rebuilds after every commit. On a large repository it
  no longer costs the same as a build from scratch: graph extraction
  re-extracts only what the commit can affect, and the type pass parses only
  the files it changed. The graph is the one a full build gives.
- **Potential: CI that caches `.neuralmind/` between runs.** The cache is
  keyed by each file's text, not its path or timestamps, so a cache restored
  onto a fresh checkout still matches every unchanged file: the stat check
  misses, the hash matches, and the file isn't parsed. A CI job like the
  walkthrough's, restoring `.neuralmind/` before `neuralmind build`, then
  skips this pass's parsing for unchanged files. That holds while the
  runner's Python and tree-sitter versions stay the same; a cache written by
  others is ignored.
