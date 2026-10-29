# NeuralMind v4.23.2 — the first prompt after an upgrade keeps its recall on a large repository

**Type:** Patch release | **Theme:** an upgrade no longer throws away the graph cache, so the Hermes plugin's first turn after it gets its block

v4.23.0 made the per-prompt hook fast on a large index by keeping the loaded
graph in `.neuralmind/graph_cache.marshal`. That file's header named the
NeuralMind release that wrote it, so every upgrade made every large index read
its graph from `index_ir.json` again, once. In a live Hermes smoke test of
v4.23.1 on an M3, on hermes-agent (269,151 nodes, a 424 MB `index_ir.json`),
the first turn after the cache went stale ran past the plugin's 8 s timeout
(`NEURALMIND_HERMES_TIMEOUT`) and went ahead without its recall block. Timed
with `tests/benchmark/hook_latency.py`, such a call took 6.4–8.2 s there. The
next turn was fast again, because the stopped call had started a background
process that rewrote the cache.

No release since the cache began has changed how the graph is read. The
header named the release only because the conversion from `index_ir.json` to
the graph *could* change between releases.

---

## What changed

- **The header names the conversion, not the release.** It holds a format
  number (`graph_cache.FORMAT`, now 1) in place of the NeuralMind version. A
  release that changes how the same files load as a graph bumps it, and only
  then does the cache get read from its sources again. The rest of the header
  is unchanged: both source files' size, modification time and inode, and the
  Python version, since `marshal`'s format belongs to the interpreter.
- **A cache written by 4.23.0 or 4.23.1 is still read.** They put their own
  version in the header. Their conversion code is byte for byte the code of
  format 1, so their headers count as format 1. The upgrade to this release is
  therefore already fast. That stops once the format changes.
- **A forgotten bump fails CI.** `tests/test_graph_cache.py` fingerprints the
  source of the code the format covers: which file wins
  (`graph_cache.prefer_ir`), `graph_cache._read_sources`, and in
  `neuralmind/ir.py` `IndexIR.from_dict` and the record parsers it calls,
  `migrate_payload`, `to_graph_json` and the supported IR versions. When any of
  that code changes, the test fails and says to bump `FORMAT` if the same
  files can now load differently. The fingerprint is the same on Python 3.11
  to 3.14, and for v4.23.0, v4.23.1 and this release.

The cache still changes how fast the graph loads, never what loads: a header
that doesn't match, a damaged file or anything that isn't a graph is read
from the sources, as before.

## What the agent sees post-install

| Agent | Before v4.23.2 | From v4.23.2 |
|---|---|---|
| **Hermes-Agent plugin**, large repository | After every NeuralMind upgrade, the first turn's recall read the whole graph again. On hermes-agent that call took 8.3–10.5 s here, so the turn could go without its block | The upgrade keeps the cache: that first call took 1.4–1.9 s, the same block |
| **Claude Code** (`UserPromptSubmit` hook), large repository | The first prompt after an upgrade waited for the graph to be read again (Claude Code doesn't stop the hook at 8 s, so only slower) | As fast as any other prompt |
| **Every command that loads an index** (`query`, MCP tools) | Read the graph again once after each upgrade | Use the cache across upgrades |
| **Cursor, Cline, generic MCP** | Same as the commands above | Same as the commands above |
| A repository whose graph file is under 16 MB | Never cached; unaffected | Unchanged |

## Measured

`tests/benchmark/hook_latency.py` on held-out task 0cb3760383's hermes-agent
index and prompt, on an M3. macOS's `mediaanalysisd` used about 1.3 cores
throughout, so load averages were 6–9, and every time here is slower than on
an idle machine. Each NeuralMind ran from a copy on `PYTHONPATH`. To simulate
an upgrade, the same code ran with `__version__` set to 4.99.0 on the cache
the previous step left. The steps ran in turn, on one index. Raw results:
[`bench/hook_latency/upgrade-hermes-agent-0cb3760383-m3.json`](../../bench/hook_latency/upgrade-hermes-agent-0cb3760383-m3.json).

| Cache written by | Code after the upgrade | First call | Calls 2–5 | Within 8 s |
|---|---|---|---|---|
| v4.23.1 | v4.23.1 | 8.75 s | 1.47–1.67 s | 4 of 5 |
| v4.23.1 | v4.23.1 (run again later) | 10.50 s | 1.52–1.80 s | 4 of 5 |
| this release | this release | 1.85 s | 1.50–1.99 s | 5 of 5 |
| v4.23.1 | this release | 1.44 s | 1.55–1.91 s | 5 of 5 |

The other states, from the full runs of each version:

| | uncached | cache missing | cached |
|---|---|---|---|
| v4.23.1 | 6.95 s (6.50–8.11) | 7.84 s (7.54–8.24) | 1.44 s (1.43–1.45) |
| this release | 7.26 s (6.57–8.68) | 8.79 s (7.83–9.83) | 1.59 s (1.46–1.68) |

This release doesn't change a miss, only how often one happens. The two rows
ran minutes apart on a loaded machine; the upgrade rows above alternated
between versions. Every one of the 51 timed calls returned the same block,
SHA-256
`cf55ceb9a220a8072b351f0f0eab4eb12d2e4c5030f9a03e52d60e0eaa30270c`. That's the
hash the v4.23.1 smoke test recorded.

## What it doesn't change

- **A cache missing, or a graph changed outside `build`,** is read from the
  sources, as before. The background writer still rewrites the cache, so a
  turn the plugin stops leaves it for the next one.
- **A new Python minor version** still reads the graph again once, because
  `marshal`'s format can differ between interpreters. So does a release that
  bumps `FORMAT`, and its notes will say so.
- **Going back to v4.23.1 or older** reads the graph again once. Those
  releases don't recognise the new header (8.34 s for that call above).

## Tests

`tests/test_graph_cache.py` checks that:

- an upgrade keeps the cache, and starts no background writer;
- a cache of another format is read from its sources and rewritten;
- a cache with the header 4.23.0 or 4.23.1 wrote is read, while the format is
  1, and not once it changes;
- a cache another release keyed on its version is not read;
- the code the format covers matches its recorded fingerprint.

The test that a cache from another NeuralMind version is never read is gone:
that is the behaviour this release changes.

## Upgrading

```bash
pip install -U neuralmind
```

Nothing else to do. Caches written by v4.23.0 or v4.23.1 are kept, so even
this upgrade's first prompt is fast. If you ran `neuralmind build` or a query
after upgrading only to warm the cache, you can skip that from now on.

## Use cases

- **Existing: [NeuralMind in Hermes](../use-cases/hermes-agent.md).** Upgrading
  NeuralMind no longer costs a large repository's next Hermes turn its recall.
- **Potential: upgrades with no warm-up step.** v4.23.0's notes suggested
  running `neuralmind build` or a query after upgrading, to write the cache
  before the first Hermes turn. An unattended upgrade (`pipx upgrade-all` on
  a schedule, say) had no such step, so the first turn after it on each large
  repository could lose its block. It no longer needs one.
