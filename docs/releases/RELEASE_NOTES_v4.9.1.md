# NeuralMind v4.9.1 — the last four fixes from the v4.8.2 bug hunt

**Type:** Patch release | **Theme:** Loose ends from the end-to-end bug hunt

[v4.8.2](RELEASE_NOTES_v4.8.2.md) fixed the low-severity bugs found by testing
v4.7.0 end to end, and listed four small problems it left for later. This
release fixes those four. None of them lose data. They are a command that
acted on the wrong thing, a warning that didn't mean what it said, a count
that read too high, and an argument order the CLI refused.

---

## What changed

### Memory and learning

- **`feedback` won't adjust a query from before memory went off.** With query
  memory off, `neuralmind feedback good|bad` boosted or penalized the newest
  query still in `.neuralmind/recent_queries.jsonl`. Queries asked since
  memory went off aren't recorded, so that was an older query than the one
  you meant. It now exits 1 and changes nothing. It names the last recorded
  query and when it was asked, and says how to turn memory back on.
- **"LTP-protected" counts the edges decay protects.** `neuralmind status`,
  `neuralmind synapse stats` and the dashboard counted every edge with at
  least five activations. That included edges penalized below the 0.20 floor
  and edges in the `ephemeral` namespace, and decay protects neither. The
  count now uses decay's rule, the one `SYNAPSE_MEMORY.md` has used since
  v4.8.2, and the two can no longer disagree. Expect a lower number.
- **`validate` stops flagging the prose path's query nodes.** For prose
  projects, reinforcement records a query's terms as nodes that aren't in the
  graph, and `neuralmind validate` reported each of those synapses as stale.
  They're now written as `query:<term>`, which no graph id can be, and aren't
  counted as stale. A deleted real node such as `query_handler.py` still is.

### CLI

- **The project path can come after options.** `neuralmind decisions restore
  <id> --commit SHA <path>` failed with `unrecognized arguments: <path>` on
  Python 3.10 and 3.11, on 3.12 before 3.12.7, and on 3.13.0. So did
  `decisions amend`, `invalidate` and `query`, and `memory review-approve` /
  `review-reject`. They now accept the path before or after the options on
  every supported Python, as newer versions already did. A list option such
  as `--files` or `--evidence` still takes every value up to the next option,
  so put the path before one.

  **Known issue, fixed in [v4.9.2](RELEASE_NOTES_v4.9.2.md):** on Python 3.10
  and 3.11, on 3.12 before 3.12.8, and on 3.13.0, these six subcommands can
  ignore `--`. `decisions query -- -q .` fails with `unrecognized arguments:
  -q`, and `decisions query -- --json .` turns on `--json` and searches for
  ".".

## What the agent actually sees post-install

| Agent | Before | After |
|-------|--------|-------|
| **Claude Code** (MCP + hooks) | An agent that ran `neuralmind feedback` with memory off adjusted an older query's edges. `neuralmind status` overstated the protected edge count | `feedback` exits 1, names the recorded query, and changes nothing. The count is the edges decay keeps |
| **Cursor / Cline / Claude Desktop** (MCP) | No MCP tool changed | Same |
| **Generic MCP client** | No MCP tool changed | Same |
| **Agents that run the CLI** (Hermes skill, scripts) | `decisions restore <id> --commit X <path>` failed on Python 3.10, 3.11, 3.12.0–3.12.6 and 3.13.0 | Options and the path can come in either order, but `--` may not end the options on those Pythons (and 3.12.7); [v4.9.2](RELEASE_NOTES_v4.9.2.md) fixes that |

## Environment variables

None added or changed.

## Upgrade notes

- **"LTP-protected" counts go down.** The edges they stop counting were
  never protected from decay. Nothing about learning or decay changed.
- **`feedback` needs query memory on.** With memory off it now always exits 1,
  even when older queries are still recorded.
- **Prose projects:** synapses stored under the old `query_<term>` spelling
  are no longer reinforced, so `validate` still counts them as stale until
  they decay.

## Related

- [CLI reference: feedback](../wiki/CLI-Reference.md#feedback-goodbad-v314) ·
  [synapse stats](../wiki/CLI-Reference.md#synapse-stats-v314) ·
  [validate](../wiki/CLI-Reference.md#validate-v0230) ·
  [decisions](../wiki/CLI-Reference.md#decisions-v410)
- [v4.9.0 release notes](RELEASE_NOTES_v4.9.0.md) ·
  [v4.8.2 release notes](RELEASE_NOTES_v4.8.2.md)
