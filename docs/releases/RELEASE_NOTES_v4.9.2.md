# NeuralMind v4.9.2 — two loose ends from v4.9.1

**Type:** Patch release | **Theme:** Prose chapters in `validate`, and the sleep pass's long-term rule

While fixing the [v4.9.1](RELEASE_NOTES_v4.9.1.md) bugs, two related problems
turned up. This release fixes both. Neither loses data.

---

## What changed

- **`validate` stops flagging prose chapters as stale.** In a project whose
  queries go through the prose path (a `chapters/` directory, built with a
  graph rather than as a book), each query records the chapters it retrieved
  in the synapse store by file name, such as `ch01.md`. That's never a graph
  node id, so `neuralmind validate` reported every chapter synapse as stale.
  A chapter name now counts as known when the index still holds
  `chapters/<name>`. A chapter you deleted is still reported, and so is any
  other name that doesn't resolve.
- **The daemon sleep pass no longer treats ephemeral edges as long-term.**
  `DaemonSleep.promote_ltp_edges` nudges long-term edges back up after decay.
  It picked them by activation count and weight alone, so it also boosted
  edges in the `ephemeral` namespace, which decay never protects. It now uses
  the same long-term rule as decay, `status` and `SYNAPSE_MEMORY.md`: at least
  five activations, a weight of at least 0.20, and not ephemeral. Nothing in
  the CLI, hooks, daemon or MCP tools runs the sleep pass yet; this fixes the
  `neuralmind.sleep` API for code that calls it.

## What the agent actually sees post-install

| Agent | Before | After |
|-------|--------|-------|
| **Claude Code** (MCP + hooks) | Nothing changed | Same |
| **Cursor / Cline / Claude Desktop** (MCP) | Nothing changed | Same |
| **Generic MCP client** | Nothing changed | Same |
| **Agents or CI that run `neuralmind validate`** on a prose project with a graph | A `stale_synapse` warning counted every chapter synapse | Only synapses to removed chapters, or other unknown nodes, are counted |

## Environment variables

None added or changed.

## Upgrade notes

None. No stored data changes shape, and no command takes new arguments.

## Related

- [CLI reference: validate](../wiki/CLI-Reference.md#validate-v0230)
- [v4.9.1 release notes](RELEASE_NOTES_v4.9.1.md) ·
  [v4.9.0 release notes](RELEASE_NOTES_v4.9.0.md)
