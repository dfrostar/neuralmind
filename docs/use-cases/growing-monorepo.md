# Use Case: Growing Monorepo

## What you're solving for

Your codebase is growing fast. Every week there are new services, new modules, refactors. Agent context goes stale quickly. You need retrieval that **stays accurate without manual effort** as the repo evolves.

## The freshness problem

The NeuralMind index is built from `graphify-out/graph.json`. If the graph isn't up to date, retrieval will reference entities that have moved, renamed, or been deleted. You'll notice:

- Agent cites functions that no longer exist.
- New code doesn't appear in search results.
- Cluster summaries describe an older architecture.

## Three ways to keep it fresh

### 1. Git post-commit hook (recommended)

```bash
neuralmind init-hook .
```

After every `git commit`, the hook runs `neuralmind build .` in the background. Incremental — only re-embeds changed nodes — so it's seconds, not minutes.

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
      - run: pip install neuralmind graphifyy
      - run: graphify update . && neuralmind build .
      - run: neuralmind wakeup . > AI_CONTEXT.md
      - uses: actions/upload-artifact@v4
        with: { name: ai-context, path: AI_CONTEXT.md }
```

Everyone on the team can download the latest `AI_CONTEXT.md` artifact — useful for PR reviews, onboarding, and pasting into non-MCP chats.

### 3. Scheduled cron

```cron
0 6 * * * cd /path/to/repo && graphify update . && neuralmind build .
```

Good for slower-moving repos or shared machines.

## Large-repo tuning

**Incremental-only builds:**

```bash
neuralmind build .              # default: incremental
```

Only re-embeds nodes whose source changed. Run time scales with the churn, not the repo size.

**Force full rebuild (rare — after graphify upgrades, schema changes):**

```bash
neuralmind build . --force
```

**Check what the index sees:**

```bash
neuralmind stats . --json
```

Watch `total_nodes` and `communities` — sudden drops mean something went wrong with `graphify update`.

## Query patterns for large repos

- **Start every session with `wakeup`** — with hundreds of clusters, orientation matters more, not less.
- **Use `search` before `query`** when you know the entity name: `neuralmind search . "PaymentController"` is faster and cheaper than an LLM round-trip.
- **Use `skeleton` aggressively** — for multi-thousand-line files, skeleton is the only sane entry point.

## Enable learning

Query patterns in a large repo often cluster around hot paths (auth, billing, search). Enable memory (TTY prompt) and run weekly:

```bash
neuralmind learn .
```

Future queries get a `+0.3` rerank boost on modules that historically cooccur with your team's queries. Over a few weeks, retrieval starts to anticipate what you mean.

---

[← Back to use-case index](./README.md) · [Main README](../../README.md)
