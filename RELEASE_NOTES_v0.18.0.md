# NeuralMind v0.18.0 — incremental per-file graph updates

**Release Date:** June 2026

## TL;DR

Until now, picking up a code change meant re-running `neuralmind build`, which
re-parses the **whole** repo (the embedder already skipped unchanged nodes, but
the parse was full). v0.18.0 adds a **per-file incremental update**: re-parse
just the file you edited, re-embed only its nodes, leave everything else
byte-for-byte untouched.

Wire it to the watcher and your index stays fresh as you type — no manual
rebuild:

```bash
neuralmind watch . --reindex
```

## What the agent actually sees, post-install

With `--reindex`, every debounced batch of edits is re-parsed into the built-in
graph and the changed nodes re-embedded — so a query right after a save already
reflects the new code. The watcher prints what it did:

```
  ↻ re-indexed 1 file(s): 2 node(s) re-embedded, 135 unchanged, 0 pruned
```

Programmatically, the new API is `NeuralMind.update_files(paths)`. The graph
contract is unchanged, so retrieval, synapses, the graph view, and MCP tools
consume the freshly-updated graph with no changes.

### Per-agent expectations

| Agent | What changes in v0.18.0 |
|-------|--------------------------|
| **Claude Code** | `neuralmind watch --reindex` keeps the index live as files change; nothing changes by default. |
| **Cursor / Cline** | Same MCP tools; the served graph is fresher when the watcher re-indexes. |
| **Generic MCP client** | `NeuralMind.update_files()` API for incremental re-index; no contract change. |
| **Contributors / CI** | Incremental-update tests assert only the edited file's nodes change. |

## How it works

`graphgen.update_files(project, graph, changed, removed)` splices a re-parse of
just the changed files back into an existing `graph.json`:

- **Unchanged files keep their nodes, edges, *and community numbers*
  byte-for-byte.** That last part is the trick — renumbering communities would
  change every node's content hash and force a full re-embed; preserving them
  means the embedder's content hashing skips every untouched node.
- The edited file's **outgoing** edges (imports / calls / inherits) are
  re-resolved against the whole project's symbols.
- Edges into a **removed or renamed** symbol are pruned, so the graph stays
  valid with no dangling edges.

`NeuralMind.update_files(paths)` then writes the graph, deletes embeddings for
removed symbols, reloads, and re-embeds — which, because of content hashing,
only touches the edited file's nodes. On the reference fixture, editing one file
re-embeds **2 nodes and skips 135**.

Only the **built-in** tree-sitter graph is updated in place; a graphify graph is
left to graphify. The optional SCIP precision pass (v0.17.0) is re-applied after
an incremental update when enabled.

## Honest scope & caveats

- **Built-in backend only**, and only for indexable suffixes (`.py`, `.ts`,
  `.tsx`, `.go`, `.md`).
- **Edited-file edges only.** A rename in file A prunes file B's now-stale edge
  into A but doesn't re-link B to the new name until B is itself re-parsed (or a
  full `neuralmind build` reconciles) — the acceptance scope is "the edited
  file's nodes/edges regenerate."
- **`--reindex` is opt-in** on `neuralmind watch`, since re-embedding needs the
  retrieval stack in the watch process. Default behavior (synapse co-activation
  only) is unchanged.

## What ships

- **`graphgen.update_files()`** — per-file re-parse with community-stable,
  byte-identical unchanged files + dangling-edge pruning.
- **`NeuralMind.update_files(paths)`** — incremental re-index (writes graph,
  prunes removed embeddings, re-embeds only changed nodes); re-applies the
  precision pass when enabled.
- **`GraphEmbedder.delete_nodes()`** — prune embeddings for removed symbols.
- **`neuralmind watch --reindex`** — wire incremental updates to the watcher.
- 5 incremental-update tests (unchanged files byte-identical, matches a full
  rebuild, removal prunes edges, no-op when nothing changed, communities
  preserved).

## What's next

- **Lean into the moat** — MCP auto-detection across Claude Code / Cursor /
  Cline out of the box, and a measured learned-synapse onboarding-lift
  (E1.5 onboarding eval) as the headline differentiator.

## Upgrade

```bash
pip install --upgrade neuralmind
```

No migration, no config changes. `neuralmind build` is unchanged; opt into live
incremental indexing with `neuralmind watch --reindex`.
