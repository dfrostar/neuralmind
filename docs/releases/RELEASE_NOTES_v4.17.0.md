# NeuralMind v4.17.0 — an answer from a stale index says so, and package code in `__init__.py` stays in the graph

**Type:** Minor release | **Theme:** context the agent can trust. When the index is behind the code, every place the agent reads it from carries one line saying so; and an edit to a package's `__init__.py` reaches the graph instead of disappearing from it

A hands-on audit of 12 repositories on v4.12.0 ([#640](https://github.com/dfrostar/neuralmind/issues/640))
found two ways the index could fall behind the code without anyone being told:

- **4 of the 12 repositories had dead semantic search.** Their index predated
  the `.neuralmind/` layout, and `query`, `search` and the MCP tools answered
  as if nothing were wrong. Only `neuralmind doctor` said the legacy
  `graphify-out/` index wasn't read any more. An index older than the checkout,
  after a pull the git hook hadn't caught up with, was just as silent. For a
  memory product this is the most damaging failure: the agent trusts the
  context it's given ([#631](https://github.com/dfrostar/neuralmind/issues/631)).
- **Package code defined in `__init__.py` went missing.** On this repository,
  `doctor` kept reporting four `__init__.py` files "on disk not in graph" after
  `build --force --regenerate-graph`, about 35 KB of code that query and search
  couldn't see ([#632](https://github.com/dfrostar/neuralmind/issues/632)).

---

## What changed

### A stale index says so, wherever the agent reads it

`neuralmind query`, the MCP `neuralmind_query`, `neuralmind_search` and
`neuralmind_wakeup` tools, and the related-files block each prompt gets
(Claude Code's `UserPromptSubmit` hook, and the Hermes plugin's
`pre_llm_call` hook) carry one line when the index can't vouch for its answer.
`neuralmind search` prints the same line on stderr, so `--json` output stays
parseable.

The line names the first of these that applies:

| Condition | The line |
|---|---|
| The index is only in the legacy `graphify-out/` layout | `Index is in the legacy graphify-out/ layout, which NeuralMind no longer reads, so semantic search finds nothing: run neuralmind build <project>.` |
| The git hook's background rebuild failed after the last successful build | `Index may be stale: the last background rebuild failed (log: .neuralmind/hook-build.log); run neuralmind build <project>.` |
| Commits since the build started changed files in the project | `Index is stale: 2 files changed in commits since the last build (src/auth.py, src/session.py); run neuralmind build <project>.` |
| The same, while the hook's background rebuild is running | `Index is catching up: 2 files changed in commits since the last build (src/auth.py, src/session.py); a background rebuild is running.` |

A current index gets no line, so nothing changes in the common case.

**How "commits since the build" is decided.** The build now records when it
started and the commit `HEAD` pointed at. A query compares the modification
time of git's `logs/HEAD` with that start time. The reflog is the right clock
because a pull checks out commits dated before the build, so commit dates
would miss it. Only when `HEAD` moved does the query run one
`git diff --name-only <build commit> HEAD -- .`. Then a commit elsewhere in a
larger repository, or a branch switch that changes nothing in the project,
adds no line. If the build's commit is gone (after a rebase), the line says
`HEAD moved to commits the index was not built from`.

**Cost.** In the common case the check is a few `stat` calls and a read of
`.neuralmind/build_status.json`; the `git diff` runs only after `HEAD` moved.
It never raises: a failed check adds no line rather than breaking the answer.

**Where else it shows:**
- MCP: `neuralmind_query` and `neuralmind_wakeup` payloads gain a `freshness`
  field holding the line (empty when current). `neuralmind_search` keeps its
  list shape; when stale, the first result carries `freshness`.
- `neuralmind doctor` has a new **Query freshness** line: WARN with the same
  text, OK when queries carry none. `doctor --json` includes it with the other
  checks.

**The git hook records a failed rebuild.** The `post-commit`, `post-merge`,
`post-checkout` and `post-rewrite` hooks from `neuralmind init-hook` used to
discard the background build's exit status. Now a failed build leaves
`.neuralmind/.hook-build.failed` and a successful one removes it. A failure
older than the last successful build (a manual `neuralmind build` since)
doesn't count. Re-run `neuralmind init-hook .` to get the new hooks.

### Also: package code in `__init__.py` stays in the graph

The graph builder parses `__init__.py` like any other module; the incremental
path lost it, two ways:

- **Incremental builds never saw `__init__.py`.** The change scan skipped every
  path part starting with `__`, the file name included, to leave out
  `__pycache__`. So an edit to an `__init__.py` (or `__main__.py`, or a file
  under a `__tests__/` directory, which the graph does index) never counted as
  a change, and its new code never reached the graph. The scan now uses the
  graph walker's rule: dot-directories and the standard ignores
  (`__pycache__` among them).
- **A file missing from the graph stayed missing.** A file the extraction
  cache called unchanged was reused from the previous graph, so if its nodes
  had gone missing, nothing restored them. `--force` re-embeds and
  `--regenerate-graph` re-runs the tree-sitter backend, but neither clears that
  cache. Now a build re-extracts any file the graph has no node for, as a new
  file, along with the files that refer to it, so an `app.py` that calls into
  `pkg/__init__.py` gets its call edge back.

An index already in that state heals on its next build; `doctor`'s
"files on disk not in graph" line goes away.

## What the agent actually sees

When the index is current: nothing new.

When it isn't, one line, in the place the agent already reads:

- **Claude Code and Hermes**: at the end of the related-files block on each
  prompt:

```
## NeuralMind associative recall

Code matching this prompt:
- src/auth.py: login() (L12)

Index is stale: 1 file changed in commits since the last build (src/auth.py); run neuralmind build /home/me/project.
```

- **Any MCP client**: above the `context` of `neuralmind_query` and
  `neuralmind_wakeup`, and in their `freshness` field; on the first result of
  `neuralmind_search`.

The agent can act on it: rebuild, read the named files directly, or treat the
recalled context as possibly out of date.

After the `__init__.py` fix, code in a package's `__init__.py` appears in query
and search results and in the prompt's related files like any other module's.

## Per-agent expectations

| Agent | What changes |
|---|---|
| Claude Code (hooks + MCP) | The prompt's related-files block ends with the line when stale; MCP `query`/`wakeup` put it above the context and in `freshness`, `search` on the first result |
| Cursor / Cline / Continue (MCP) | MCP `query`/`wakeup`/`search` as above; no prompt hook |
| Hermes-Agent plugin | Same prompt block as Claude Code (it runs the same hook action) |
| Generic MCP client | Same as Cursor |

Every agent sees `__init__.py` code it couldn't see before, once its project is
rebuilt.

## Upgrading

- **Re-run `neuralmind init-hook .`** so the git hooks record a failed
  rebuild. Hooks installed before v4.17.0 keep working; they just never report
  a failure, so the failed-rebuild line can't appear.
- **Rebuild once** (`neuralmind build .`). The build records the commit and
  start time the "commits since the build" line compares against; an index
  built before v4.17.0 has neither, so that line stays off until the next build.
  The same build restores any `__init__.py` code missing from the graph.
- **Scripts that parse MCP payloads** get a new `freshness` key on
  `neuralmind_query` and `neuralmind_wakeup`, and on the first
  `neuralmind_search` result when stale; existing keys are unchanged.
- **Scripts that parse `doctor --json`** get one more check, "Query freshness".
  It is a WARN at most, so `doctor`'s exit code doesn't change.
- **`neuralmind search`** may print one line on stderr; stdout, including
  `--json`, is unchanged.

## Not in this release

- A time-based limit for query-time freshness (warn when the index is older
  than N, whatever git says). `stale_after` already applies to `doctor` and
  `health`.
- Uncommitted edits. The query-time line covers commits; `doctor`, `health` and
  the MCP wakeup still compare the graph with the working tree, edits included.

## Reproduce

```bash
pytest tests/test_query_freshness.py -v                      # every notice, the hook marker, query + MCP + prompt block
pytest tests/test_g4_incremental.py -k package_init -v      # the scan sees __init__.py edits
pytest tests/test_incremental_wiring.py -k PackageInit -v   # edits reach the graph; a missing file is restored
pytest tests/test_doctor.py -k returns_all_checks -v

# In a built project with the git hooks installed:
echo "# touch" >> some_module.py && git commit -qam "change"
neuralmind query . "how does X work"   # first line: Index is catching up … / Index is stale …
neuralmind doctor .                    # Query freshness line
```

## Related

- [CLI reference: query](../wiki/CLI-Reference.md#query), [search](../wiki/CLI-Reference.md#search), [doctor](../wiki/CLI-Reference.md#doctor-v0120), [init-hook](../wiki/CLI-Reference.md#init-hook)
- [Recover from a stale graph](../use-cases/recover-from-a-stale-graph.md): the walkthrough, now with the query-time line
- [v4.13.0 release notes](RELEASE_NOTES_v4.13.0.md): the git hooks that rebuild after pulls, merges, branch switches and rebases
- Issues: [#631](https://github.com/dfrostar/neuralmind/issues/631), [#632](https://github.com/dfrostar/neuralmind/issues/632), field report [#640](https://github.com/dfrostar/neuralmind/issues/640)
