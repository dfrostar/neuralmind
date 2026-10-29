# Use Case: Growing Monorepo

## What you're solving for

Your codebase is growing fast. Every week there are new services, new modules, refactors. Agent context goes stale quickly. You need retrieval that **stays accurate without manual effort** as the repo evolves.

## The freshness problem

The NeuralMind index is built from `graphify-out/graph.json`. If the graph isn't up to date, retrieval will reference entities that have moved, renamed, or been deleted. You'll notice:

- Agent cites functions that no longer exist.
- New code doesn't appear in search results.
- Cluster summaries describe an older architecture.

**v4.4.0+: you no longer have to notice.** `neuralmind doctor .` and
`neuralmind health .` compare the graph with the files on disk in both
directions — new files the graph lacks, deleted files it still serves, files
changed since it was built — and your agent's first `neuralmind_wakeup` call
starts with `Index is stale: …` when they disagree. Each build also purges
vectors for nodes that left the graph. See
[Recover from a stale code graph](./recover-from-a-stale-graph.md).

## Three ways to keep it fresh

### 1. Git post-commit hook (recommended)

```bash
neuralmind init-hook .
```

After every `git commit`, the hook runs `neuralmind build .` in the background. Incremental — only re-embeds changed nodes — so it's seconds, not minutes.

Since v4.6.0 it first runs `neuralmind decisions scan`: any recorded decision whose files the commit changed after it was recorded goes STALE, so a fast-moving codebase doesn't keep serving rationale the code has outgrown ([walkthrough](./decision-memory-across-commits.md)). Re-run `neuralmind init-hook .` on an existing checkout to pick that up.

Coexists with existing hooks (husky, pre-commit, lint-staged) — appends safely rather than overwriting.

### 2. CI pipeline

```yaml
# .github/workflows/neuralmind.yml
on:
  push:
    branches: [main]
jobs:
  reindex:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install neuralmind
      - run: neuralmind build . --strict   # exits 3 if the code graph fails the freshness check
      - run: neuralmind wakeup . > AI_CONTEXT.md
      - uses: actions/upload-artifact@v4
        with: { name: ai-context, path: AI_CONTEXT.md }
```

Everyone on the team can download the latest `AI_CONTEXT.md` artifact — useful for PR reviews, onboarding, and pasting into non-MCP chats.

### 3. Scheduled cron

```cron
0 6 * * * cd /path/to/repo && neuralmind build .
```

Good for slower-moving repos or shared machines.

## Large-repo tuning

**Incremental-only builds:**

```bash
neuralmind build .              # default: incremental
```

Only re-embeds nodes whose source changed. Run time scales with the churn, not the repo size.

Since v4.23.3 graph extraction re-extracts only the files a change can affect, and writes the same `graph.json` a full build would, byte for byte. Files your `.gitignore` and `.neuralmindignore` exclude never count as changes. On hermes-agent a one-file rebuild of the graph took 9.8–10.7 s against 34.5–36.0 s for a full extraction. The first build after upgrading to v4.23.3 extracts the whole graph once.

Since v4.23.3 the build's type pass keeps each file's return types in `.neuralmind/type_cache.json`, keyed by a hash of the file's text, and parses only files whose text changed: on hermes-agent (347,376 type edges) it took 1.0–1.2 s on a rebuild against 15.9 s from scratch ([release notes](../releases/RELEASE_NOTES_v4.23.3.md)). Deleting that file costs one build at first-build speed and changes nothing in the result.

**Force full rebuild (rare — after graphify upgrades, schema changes):**

```bash
neuralmind build . --force
```

**Check what the index sees:**

```bash
neuralmind stats . --json
```

Watch `total_nodes` and `communities` — sudden drops mean something went wrong with the graph build (`neuralmind build`).

**Validate index integrity (v0.23.0+):**

```bash
neuralmind validate . --json
```

A backend-free schema check over the canonical index IR — it reports dangling edges, orphaned nodes, and unknown kinds, turning "why is retrieval weird?" into a one-line check (ideal for CI). Add `--write` to migrate a pre-IR project's state in place, no rebuild required.

## Query patterns for large repos

- **Start every session with `wakeup`** — with hundreds of clusters, orientation matters more, not less.
- **Use `search` before `query`** when you know the entity name: `neuralmind search . "PaymentController"` is faster and cheaper than an LLM round-trip.
- **Use `skeleton` aggressively** — for multi-thousand-line files, skeleton is the only sane entry point.

## Enable learning

Query patterns in a large repo often cluster around hot paths (auth, billing, search). Enable memory (TTY prompt) and install the hooks so the synapse layer learns from how the repo is actually used:

```bash
neuralmind install-hooks .
neuralmind watch &          # optional: also learn from file co-edits
```

The synapse layer reinforces the edges between code nodes that fire together (queries, tool calls, file edits) and lets unused edges decay. Recall then spreads activation across that learned graph, surfacing related code that pure vector search would miss. Over a few weeks, retrieval starts to anticipate what you mean — automatically, with no `neuralmind learn` step (that command was deprecated in v0.25.0). Inspect what's been learned with `neuralmind memory inspect .`.

## Always-on activity tracking (v0.6.0+)

For monorepos that get touched by multiple agents and multiple
developers across the day, run a long-lived `neuralmind watch`
daemon next to your normal workflow:

```bash
# Terminal 1: live graph in browser
neuralmind serve .

# Terminal 2: always-on synapse learning from file edits
neuralmind watch . --quiet &
```

The v0.6.0 cross-process JSONL bridge means `serve` and `watch`
share a live feed even though they're separate processes. Every
file save anywhere in the monorepo coalesces into a co-activation
event; the corresponding nodes pulse on the canvas; the synapse
store reinforces.

After a week of normal team use, the pulse pattern on the canvas
visibly concentrates around the parts of the monorepo currently
under active development. Stale subtrees fade. "Synapse density
over the last week" becomes a real, observable property of the
graph — useful for onboarding ("here's what we've actually been
working on"), for refactor planning ("here's the hot path
nobody's touched in a month"), and for retrieval-quality
debugging ("this cluster is over-represented, let me dial it back").

`NEURALMIND_EVENT_LOG=0` disables the bridge if you don't need it.

---

[← Back to use-case index](./README.md) · [Main README](../../README.md) ·
[Multi-agent: shared brain across tools](./multi-agent.md)
