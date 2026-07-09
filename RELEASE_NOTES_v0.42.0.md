# NeuralMind v0.42.0 — The map stops going stale, and starts warm

**TL;DR:** Two things. **(1)** `neuralmind build` was never regenerating the
graph — it re-embedded a frozen map, so every file you added after the first
build was invisible to retrieval, and the git post-commit hook ran exactly that
command, making "auto-rebuild on commit" a structural no-op for the entire life
of the feature. Both are fixed; `neuralmind watch` now re-indexes by default and
the incremental path is exposed as a new `neuralmind update` command. **(2)** New
`neuralmind mine-history` seeds the associative layer from git commit history, so
the synapse memory is useful on the first query instead of after a week of usage.

**If you installed the git hook on an earlier version, run
`neuralmind build . --force` once to repair your index.**

---

## The bug

`NeuralMind.build()` calls `_maybe_generate_builtin_graph()` before loading the
graph. That function returned early whenever `graphify-out/graph.json` already
existed and `force` was False:

```python
if graph_path.exists():
    if not force:
        return          # ← the bug
```

The intent was *never clobber a graphify-produced graph*. But the check keyed on
`force`, not on **who wrote the graph** — so it also skipped refreshing graphs
NeuralMind generated itself. The result:

```console
$ neuralmind build .                    # a.py indexed
$ echo 'def two(): ...' > b.py
$ neuralmind build .                    # "Build successful! Nodes: 2"
$ neuralmind search . "two"             # two() is not there
```

`build` reported success. The embedder faithfully re-embedded every node in the
graph. The graph just didn't have `b.py` in it. Only `--force` regenerated.

Two documented claims were false as a consequence — `README.md` said `build .` was
"incremental — only re-embeds changed nodes," which described the embedder while
the graph sat frozen underneath.

### Why it mattered more than it looks

`neuralmind init-hook` installs a git post-commit hook. Through v0.41.0 that hook
ran a bare `neuralmind build .` — the exact call that skipped regeneration. So the
headline "the index rebuilds automatically after every commit" behavior never
refreshed structure at all. It re-embedded a map frozen at whatever the repo
looked like the first time you ran `build`.

Separately, `neuralmind watch` only reinforced synapse weights unless you passed
`--reindex`. The stock watcher therefore spent its time making retrieval *more
confident* about a graph that no longer matched the code — arguably worse than not
running at all, because the learned signal was strengthening associations against
stale structure.

Taken together: the three surfaces a user would reach for to keep the index fresh
(`build`, the git hook, `watch`) each looked like they were doing it, and none of
them were, unless you knew to pass a flag.

---

## What changed

### 1. Ownership decides, not `--force`

`_maybe_generate_builtin_graph()` now reads the existing graph's `generated_by`
and refuses only when graphify owns it:

```python
if graph_path.exists():
    existing = json.loads(graph_path.read_text(...))
    if "neuralmind.graphgen" not in str(existing.get("generated_by", "")):
        return          # graphify owns this graph — never overwrite it
    # our own graph: refresh it, force or not
```

Every `build` now refreshes a graph we wrote. A graphify graph is still never
touched, on any code path. `--force` retains its real meaning: whether the
*embedder* re-embeds nodes whose content hash hasn't changed.

The `force` parameter is gone from that function's signature rather than left in
place doing nothing.

### 2. `neuralmind update` — the incremental fast path, as a command

```bash
neuralmind update [paths...] [--project PATH] [--stdin] [--json]
```

Re-parses only the named files into the existing graph, prunes embeddings for
symbols that disappeared, and re-embeds only what actually changed. Unchanged
files keep their nodes, edges, and community ids byte-for-byte, so the embedder's
content hash skips them.

```console
$ neuralmind update src/api.py
Re-indexed 1 file(s): 1 node(s) re-embedded, 41 unchanged, 0 pruned
```

A path that no longer exists on disk is treated as a deletion and pruned from both
the graph and the vector store.

It exits **non-zero** when the incremental path doesn't apply — no graph yet, a
graphify-owned graph, or tree-sitter unavailable — so a caller can fall back:

```bash
git diff-tree --no-commit-id --name-only -r HEAD \
  | neuralmind update --stdin || neuralmind build .
```

`--stdin` reads newline-delimited paths. That's not cosmetic: it's what makes
filenames with spaces survive the git hook without shell quoting games.

### 3. The git hook re-indexes what the commit touched

`neuralmind init-hook` now installs:

```sh
if command -v neuralmind >/dev/null 2>&1; then
    nm_changed=$(git diff-tree --no-commit-id --name-only -r HEAD 2>/dev/null)
    if [ -n "$nm_changed" ] && echo "$nm_changed" | neuralmind update --stdin >/dev/null 2>&1; then
        echo "[neuralmind] Index updated"
    elif neuralmind build . >/dev/null 2>&1; then
        echo "[neuralmind] Index rebuilt"
    else
        echo "[neuralmind] Index update failed (non-critical)"
    fi
fi
```

Root commits and merges make `git diff-tree` print nothing, so they fall through
to a full build. So does a graphify-owned graph, and a project with no index yet.
The hook remains idempotent and still appends to an existing `post-commit` rather
than clobbering it.

### 4. `neuralmind watch` re-indexes by default

Incremental re-index is **on**. `--no-reindex` opts out; `--reindex` is still
accepted as a no-op so existing scripts, systemd units, and docs don't break.

When re-index can't apply, the watcher now prints a **one-time warning to stderr**
rather than silently swallowing the same failure on every batch:

```
  ! incremental re-index unavailable: incremental update only applies to the built-in backend
    Synapses still reinforce, but the graph will not track your edits. Pass --no-reindex to silence this.
```

---

## Warm start: `neuralmind mine-history`

The staleness fixes above are about keeping the *graph* current. This is about
the *synapse layer* — NeuralMind's actual differentiator, and the piece with the
worst first-run story.

On a fresh install the associative memory is empty. It learns which files go
together from live editing, which means it says nothing useful until you've spent
roughly a week feeding it. That's a brutal activation curve for the capability
the product leads with.

But the signal already exists. Files that changed together in a commit are the
same co-activation a live edit produces — just already recorded, thousands of
observations deep. `neuralmind mine-history` reads it and seeds the store:

```console
$ neuralmind mine-history .
Mined 1847 co-change edge(s) (206 durable) from 1983 of 2000 commit(s) into the 'history' namespace.
  + 412 directional transition(s) from 388 same-author commit sequence(s) (feeds `neuralmind next`).
  Skipped 17 commit(s) touching more than 50 files (noise).
  1847 edge(s) + 412 transition(s) written.
  These now bias recall from the first query. Re-run any time; clear with `neuralmind memory reset --namespace history`.
```

After that, a query surfaces historically co-changed siblings immediately —
before any live usage has accrued.

**How it decides what's signal:**

- **File granularity.** Each changed path maps to its single file-level graph
  node, not every symbol in the file. A k-file commit becomes k(k-1)/2 pairs, not
  a clique over every symbol of every file. (This is also why it doesn't route
  through `activate_files`, which would explode a 5-file commit into thousands of
  symbol-pairs.)
- **Focused commits weigh more.** Per-commit pair weight scales as `1/(k-1)`, so
  a two-file commit is strong evidence two files relate and a sprawling refactor
  barely registers. Commits above `--max-files` (default 50) are skipped outright.
- **Durable pairs are protected.** A pair that co-changed in ≥ 5 commits is
  written already LTP-protected, so a real structural fact about the repo doesn't
  decay away before you've generated usage to replace it.
- **Direction comes from commit sequences.** Two consecutive commits by the same
  author within six hours are one work session — after committing the API change,
  they went on to commit the migration — and each such sequence records
  directional transitions (older commit's files → newer commit's files, weight
  `1/(|A|·|B|)`). That's the same signal `neuralmind next` learns from live
  editing, so next-file prediction works from the first session too. Rebased
  history (negative timestamp gaps) breaks the inferred session rather than
  fabricating a sequence.

**How loud it is:** edges land in a dedicated `history` namespace that reads at
`W_HISTORY` (0.35) — below both your personal usage (0.8) and imported team
memory (0.5). It is a *prior*: it gives recall a running start and is designed to
be overtaken by what you actually do. It decays slowly (a co-change fact is
long-lived), is idempotent to re-run (`import_edges` merges by MAX), and is
cleared independently with `neuralmind memory reset --namespace history`.

Options: `--max-commits` (default 2000), `--max-files` (default 50), `--dry-run`
to preview the edges without writing, `--json` for scripts.

---

## What the agent actually sees post-install

Nothing new on the wire — no new MCP tools, no new hooks, no schema change. What
changes is that the graph the agent queries now corresponds to the code on disk.

| Agent | Before v0.42.0 | After |
|---|---|---|
| **Claude Code** | `neuralmind_query` / `neuralmind_search` answered from a graph frozen at first build. A function added last week returned no hits, and the agent confidently reported it didn't exist. | Same tools, live graph. With `watch` running (or the git hook installed), new symbols are queryable within one debounce window / one commit. |
| **Cursor / Cline / Continue** | Same staleness through the MCP server. | Same fix — it's below the MCP layer. |
| **Generic MCP** | Same. | Same. |

The `SYNAPSE_MEMORY.md` export is unaffected: synapse learning always operated on
file paths and never depended on graph freshness. But the associations it learned
were, until now, pointing into a graph that might not contain the nodes.

---

## Upgrading

```bash
pip install -U neuralmind
neuralmind build . --force      # one-time repair: regenerate the frozen graph
neuralmind init-hook .          # if you use the git hook, reinstall it
```

The `--force` is the important part. A plain `build` will now refresh the graph
correctly going forward, but a single `--force` also re-embeds nodes whose content
hash matched against the stale graph, which is the safe way to reconcile an index
that has been drifting.

Nothing to change if you drive NeuralMind purely through `graphify` — that path
was never affected, and is still never touched.

---

## Compatibility

- **No breaking changes.** `--reindex` still parses. The `build` CLI surface is
  unchanged. `_maybe_generate_builtin_graph()` is private; its signature lost the
  unused `force` parameter.
- **`build` is slower than it was**, because it now does the work it claimed to be
  doing: a full re-parse of the repo. Embedding is still content-hashed, so the
  expensive half is unchanged. Use `neuralmind update <paths>` for the cheap path.
- Incremental re-index (`update`, `watch`) applies to the **built-in tree-sitter
  backend only**. A graphify-owned graph is left to graphify.
- `mine-history` adds a `history` namespace to the default merged read. An empty
  namespace contributes nothing, so this is inert until you mine — existing
  behavior is unchanged on any project that never runs the command.
- **Transition keys are now repo-relative POSIX paths.** The watcher used to
  record file transitions under absolute native paths, which `neuralmind next
  src/api.py` could never match — live-learned "what comes next" was
  effectively unqueryable by the path form users type. Writes now normalize
  (`activate_files`), queries normalize plus **dual-read** the old absolute
  form (`neuralmind next`, the `neuralmind_next_likely` MCP tool), so
  pre-v0.42.0 stores keep working without migration; legacy successors are
  normalized on the way out.

## Tests

The build/update work adds ten tests across `tests/test_core.py` and
`tests/test_cli.py` pinning three invariants: a graph we own is refreshed on a
plain `build`; a graphify-owned graph is never overwritten; and the post-commit
hook attempts `update` before `build`. Eight fail against v0.41.0.

`mine-history` adds `tests/test_history.py` — 21 stdlib-only tests: the git-log
parser against hand-written fixtures, the weighting/gating/dedup logic against
synthetic commit filesets, and the namespace wiring on a real `SynapseStore`
(mined edges surface in a merged read yet stay isolated and independently
clearable). Two exercise the real `git` subprocess when a binary is present and
skip otherwise.
