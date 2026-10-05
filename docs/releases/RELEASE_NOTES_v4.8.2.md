# NeuralMind v4.8.2 — the low-severity bug-hunt fixes

**Type:** Patch release | **Theme:** The rest of the end-to-end bug hunt

v4.8.1 fixed the high- and medium-severity bugs found by testing v4.7.0 end to
end. This release fixes the low-severity ones, plus a few closely related
problems found while fixing them. None of them lose data. They are wrong
answers, misleading messages, and a test suite that dirtied the checkout.

The ones you're most likely to notice:

- **A mistyped project path is an error.** It used to create a new, empty
  project at that path and answer from it.
- **The daemon and `neuralmind serve` answer malformed requests with a 4xx.**
  They used to drop the connection, return a 500, or raise inside the handler.
- **Ingesting a Markdown file that `build` already indexed stores it once.**
  The same text used to come back twice in query context.
- **`feedback` and `doctor` say what actually turns query memory on.**

---

## What changed

### Project paths and decisions

- **A project path that doesn't exist is an error.** `query`, `search`,
  `wakeup`, `stats`, the `decisions` subcommands that open a store (`record`,
  `query`, `amend`, `audit`, `export`, `restore`, `invalidate`) and every MCP
  tool used to create `<path>/.neuralmind/` for a mistyped path and run
  against an empty index or decision store. The CLI now exits 2 with `project path does not
  exist: <path>`. MCP tools return `code: "project_not_found"`, with a hint to
  pass an absolute path when the path was relative, and the daemon answers 404.
  Nothing is created. `build` in an existing directory works as before.
- **`decisions restore` and `decisions invalidate` report failures.** An
  unknown id made `restore` print a traceback and `invalidate` print success.
  A database error was logged and then reported as success. Both now print
  `Decision not found: <id>` or `Could not … decision <id>: …` and exit 1. The
  MCP invalidate tool returns `not_found` or `storage_error`.
- **`decisions record --confidence` must be between 0 and 1.** `7` was
  accepted and stored as 1.0, and so was `nan`. The CLI and the MCP record
  tool now reject the value.
- **`search --n` must be at least 1.** `--n 0` and `--n -3` returned one
  result. The MCP tools now enforce the numeric bounds their schemas declare.
- **`stats .` names the project.** It printed `Project: ` with nothing after
  it, in the CLI and in the MCP `neuralmind_stats` tool.

### Memory and learning

- **`feedback` and `doctor` say how to turn query memory on.** With memory
  off, `feedback good|bad` said "run a query first", and the next query wasn't
  recorded either. `doctor` advised `NEURALMIND_MEMORY=1`, which changes
  nothing: the variable is on by default, and logging also needs a yes in
  `~/.neuralmind/memory_consent.json`. Both now name what's off and what
  turns it on.
- **`validate` stops warning about stale synapses on a fresh index.** Every
  edge it flagged pointed at a `community_<id>` node or a compliance-control
  key, which NeuralMind writes on purpose. Synapses to deleted nodes, or to
  communities a rebuild dropped, are still reported.
- **The synapse memory export reports what each association earned.**
  `.neuralmind/SYNAPSE_MEMORY.md` added a pair's weight and activation count
  across namespaces, so a weight could read 2.00, and it tagged edges
  "(long-term)" by count alone. A pair now shows its strongest namespace, and
  "long-term" means protected from decay: at least five activations, weight at
  or above 0.20, and not ephemeral. Expect fewer long-term tags.
- **The `SynapseDynamics` API does what its docstrings say.** Resource
  limiting can trigger (ten potentiations per node until replenished),
  retrieval-induced forgetting weakens competitor edges that exist, and
  lateral inhibition keeps the strongest results instead of sometimes
  returning none. Nothing in the CLI, hooks or MCP tools calls this API.

### Servers, demo and ingest

- **The daemon and `neuralmind serve` answer malformed requests with a 4xx.**
  A non-numeric `Content-Length` dropped the connection with no response. A
  non-object JSON body or a non-integer `n` was a 500. A non-ASCII token
  raised inside the handler. They now get a 400 with a JSON error naming the
  problem: 413 for a body over 1 MiB, 401 for the token. The daemon reads
  flags such as `force` strictly; `"false"` used to count as true. Both
  servers close a request that stalls for 30 seconds, and the graph view's
  session-cookie check is constant-time.
- **`neuralmind demo` stops reporting stale files.** It copied the bundled
  project with the bundle's timestamps, so when the bundled graph was older
  than its sources, every run printed "N files changed since the graph was
  built".
- **Ingesting a Markdown file that's already in the project stores it once.**
  The built-in graph already holds a Markdown file's text, heading by
  heading. `neuralmind ingest docs/guide.md` and the
  `neuralmind_ingest_document` MCP tool stored a second copy under the
  absolute path, so the text came back twice in query context. Both now skip
  such a file and list it under `already_indexed`. Any other file inside the
  project is stored under its project-relative path.

### For contributors

- **`pytest` leaves the checkout clean.** The graph tests built the committed
  fixture projects in place, and each build rewrote their extraction caches.
  They now build throwaway copies, and the cache files are no longer tracked.

## What the agent actually sees post-install

| Agent | Before | After |
|-------|--------|-------|
| **Claude Code** (MCP + hooks) | A tool call with a mistyped `project_path` ran against a new, empty project created there. `neuralmind_ingest_document` on a Markdown file in the project put its text in context twice | The call returns `code: "project_not_found"` and creates nothing. The ingest is skipped and the file listed under `already_indexed` |
| **Cursor / Cline / Claude Desktop** (MCP) | Same as Claude Code | Same as Claude Code |
| **Generic MCP client** | Out-of-range `n` or `confidence` was accepted | Rejected with `invalid_request`, per the bounds the tool schema declares |
| **Daemon clients** | A malformed request could drop the connection or return a 500. `"false"` flags counted as true | 4xx with a JSON error naming the problem; flags read strictly; a missing project is a 404 |

## Environment variables

None added or changed.

## Upgrade notes

- **A project path that doesn't exist now fails.** A script that relied on a
  command creating `<path>/.neuralmind/` should create the directory, or run
  `neuralmind build`, first.
- **Daemon clients:** flags must be booleans (or `"true"`, `"false"`, `1`,
  `0`), request bodies are capped at 1 MiB, and a missing project is a 404.
- **`SYNAPSE_MEMORY.md` shows fewer long-term tags.** It now counts only
  associations that are actually protected from decay.

## Related

- [CLI reference: search](../wiki/CLI-Reference.md#search) ·
  [decisions](../wiki/CLI-Reference.md#decisions-v410) ·
  [exit codes](../wiki/CLI-Reference.md#exit-codes)
- [v4.8.1 release notes](RELEASE_NOTES_v4.8.1.md) ·
  [v4.8.0 release notes](RELEASE_NOTES_v4.8.0.md)
