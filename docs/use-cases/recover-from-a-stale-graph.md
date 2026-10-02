# Recover from a stale code graph

**Best for:** anyone whose repo has a committed `graphify-out/graph.json`, a
graph built on another machine or OS, or a team that switched between graphify
and the built-in backend — and anyone wiring NeuralMind into CI.

**Primary goal:** know within a second whether the index describes the code
you have, and get back in step with one command when it doesn't (v4.4.0+).

A code graph that lags the code is the worst kind of stale index: every query
still "works", it just answers from code that no longer exists and can't see
code that does. Before v4.4.0 that was silent. A graphify graph committed months
ago, built on Windows, missing every module added since, still passed `doctor`.

---

## 1. Check: does the graph match the files on disk?

```bash
neuralmind doctor .
```

The *Code graph* check now compares the graph with the working tree in both
directions, whatever tool built it:

```
  [FAIL] Code graph: graphify-out/graph.json (graphify, 2026-04-22, 214 commits behind HEAD), 3,197 nodes
         51 files on disk not in graph (lib/render/overlay.tsx, scripts/collect_stats.py, ...)
         3,176 node paths (319 files) use '\' separators (built on Windows)
         -> neuralmind build . --regenerate-graph
```

What each line means:

| Finding | Meaning | Severity |
|---|---|---|
| files on disk not in graph | new code the index can't answer about | WARN, FAIL above 10% |
| files in graph no longer on disk | deleted or renamed code still being served | WARN, FAIL above 10% |
| node paths use `\` separators | the graph was built on Windows; none of its paths line up with a POSIX checkout | FAIL |
| files changed since the graph was built | edited after the graph; from `git diff` for a committed graph | WARN |
| commits behind HEAD | how old a committed graph is; "age unknown: shallow clone" on a depth-1 checkout | informational |

The same report appears in `neuralmind health` (exit `1` when it isn't OK),
at the start of `neuralmind build`, and as one line at the top of your agent's
first `neuralmind_wakeup` call — so the agent knows not to trust the index
before it answers from it.

## 2. Fix: regenerate with the built-in backend

```bash
neuralmind build . --regenerate-graph
```

```
Graph source: built-in (tree-sitter), 8,351 nodes. Ignoring graphify-out/graph.json (graphify, 2026-04-22).
Graph: .neuralmind/graph.json (built-in, regenerated, 8,351 nodes)
Build successful!
   ...
   Delta: +8,351 new, ~0 updated, =0 skipped, -3,197 removed
```

- `graphify-out/` is never written; the new graph lives in `.neuralmind/`.
- Vectors from the old graph are purged (`-3,197 removed`), so search can't
  return them. If they're more than half the store, the build keeps them and
  tells you to rerun with `--prune` — a safety valve against a wrong path.
- Later plain `neuralmind build .` runs update the built-in graph incrementally.

You often don't need the flag: with the default `graph_source: auto`, a
graphify graph that **fails** the freshness check is replaced by a built-in
graph on the next `build`, and the build prints why.

## 3. Choose the graph source on purpose

`.neuralmind.yaml`:

```yaml
graph_source: auto      # default: built-in graph if present, else graphify;
                        # a failing graphify graph is replaced at build time
# graph_source: builtin # always tree-sitter; graphify-out/ is never read
# graph_source: graphify # only graphify-out/graph.json — teams that run graphify in CI
```

NeuralMind never switches source silently. If the last build used the built-in
graph and `.neuralmind/graph.json` disappears, the next build stops and names
both ways out (`--regenerate-graph`, or `graph_source: graphify`) instead of
quietly serving an old graphify graph. Every build prints which graph it used
on a `Graph:` line, and `neuralmind build-status` shows it afterwards.

## 4. Gate it in CI

```bash
neuralmind health .            # 0 = in step, 1 = out of step (or nothing to check), 2 = no index
neuralmind build . --strict    # exits 3 before embedding when the graph FAILs
```

`health` used to fail whenever the index was older than 24 hours. It now fails
only when the graph and the code disagree, so a nightly job stops rebuilding a
current index and starts catching a stale one.

---

## The potential use case: a pre-merge freshness gate

Because the check is stat calls and a few `git` commands — no parsing — it is
cheap enough to run on every pull request. A team that commits its graph (or
ships one in a container image) can fail the PR when the graph no longer covers
the code under review, instead of finding out when an agent confidently
describes a module that was deleted last sprint.

Related: [Release notes v4.4.0](../releases/RELEASE_NOTES_v4.4.0.md) ·
[Growing monorepo](./growing-monorepo.md) ·
[Index any repo with just `pip`](./zero-install-indexing.md)
