# Does NeuralMind actually work on *your* codebase?

Don't take our word for it. The self-benchmarking suite proves the 40–70× claim on a committed fixture in CI — but your codebase isn't our fixture. The only way to know what NeuralMind does for *you* is to run it on *your* code.

This walkthrough gets you from zero to a real before/after number on your repository in **under 5 minutes**, with no commitment beyond a pip install.

## What you'll have at the end

- A measured **reduction ratio** on your actual code (typical: 30–80×)
- An **estimated monthly savings** in dollars, at your query volume and your model's pricing
- A **JSON blob** you can share with your team (or contribute back to the public community benchmarks — your choice, zero telemetry)

If the numbers don't justify the install — you uninstall and move on. Nothing else happens. NeuralMind never uploads anything.

## Step 1 — Install (60 seconds)

```bash
pip install neuralmind graphifyy tiktoken
```

`graphifyy` builds the code knowledge graph NeuralMind reads from; `tiktoken` is needed for accurate OpenAI-model token counting. If you only care about a rough number, `tiktoken` is optional.

## Step 2 — Index your repo (2–3 minutes)

```bash
cd /path/to/your-project
graphify update .
neuralmind build .
```

The first build takes 1–3 minutes depending on repo size. Incremental rebuilds after code changes take seconds.

**Sanity check — make sure it worked:**

```bash
neuralmind stats .
```

You should see something like:
```
Project: your-project
Built: True
Nodes: 1,247
Communities: 23
```

If `Built: False`, the build step failed — see [Troubleshooting](../wiki/Troubleshooting.md).

## Step 3 — Run the benchmark

```bash
neuralmind benchmark .
```

Output (your numbers will vary):

```
Project: your-project
Wake-up tokens: 412
Avg query tokens: 891
Avg reduction: 46.0x
Summary: NeuralMind query returns 46x less context than loading files naively
```

**What those numbers mean for you:**

| Metric | What it says |
|---|---|
| **Wake-up tokens** | Cost of one "orient the agent" call at session start. ~400 tokens = ~$0.0012 on Claude Sonnet. |
| **Avg query tokens** | Cost of one code question (across NeuralMind's default 5-query sample). ~900 tokens = ~$0.0027 per question. |
| **Avg reduction** | How many times smaller NeuralMind's context is vs loading whole files. 46× means your bill drops by ~97.8% per query. |

## Step 4 — Translate to real money

At **100 queries/day** on **Claude 3.5 Sonnet** ($3/MTok input):

- Naive (load relevant files, ~20K tokens/query): ~$180/month
- NeuralMind (46× reduction, ~430 tokens/query): ~$4/month
- **Saved: ~$176/month per developer**

Adjust for your model and volume — the math scales linearly. GPT-4o costs ~5× more than Sonnet, so savings are larger. Claude Haiku costs less, so savings are smaller in absolute terms but the ratio stays the same.

## Step 5 — Decide

You now have measured, reproducible numbers on **your code**, not ours. Three paths:

### Path A — Install and use it

If the savings justify it, nothing more to do — you've already installed. Start asking code questions:

```bash
neuralmind query . "How does authentication work?"
neuralmind skeleton src/auth/handlers.py
```

Claude Code users: install the PostToolUse compression hooks for an extra 5–10× reduction layer on top:

```bash
neuralmind install-hooks .
```

### Path B — Share the numbers with your team

```bash
neuralmind benchmark . --contribute --submitter your-github-handle
```

That flag emits a JSON blob with your project name, numbers, and the exact command that produced them. **Nothing is uploaded.** You get a text blob to paste into Slack, a design doc, or a PR.

### Path C — Contribute to the public community benchmarks (optional)

If your project is open source (or the numbers are OK to share), drop the JSON blob into the community leaderboard:

- **Easy:** [open a benchmark submission issue](https://github.com/dfrostar/neuralmind/issues/new?template=community-benchmark.yml) — form fields map 1:1 to the `--contribute` output.
- **Direct PR:** add the entry to `docs/community-benchmarks.json` and run `python scripts/render_community_table.py --inject README.md`.

Every submission is auditable — entries include the exact `neuralmind benchmark` command that produced them.

## If the numbers *don't* look good on your repo

A few things to check before giving up:

1. **Is the graph actually built?** `neuralmind stats .` should report a non-zero node count. If it's tiny, `graphify` may have missed your language or the project structure.
2. **Tiny repos don't need this.** If your whole codebase is under 5K tokens, just paste it into the chat — there's nothing for NeuralMind to compress.
3. **Try a larger query set.** The default 5-query benchmark is representative, not exhaustive. Pass `sample_queries` if you use the Python API.
4. **Enable PostToolUse hooks** (Claude Code only) — that's the second compression phase. Retrieval-only numbers miss half the story.
5. **Open an issue** with your numbers and repo characteristics. Retrieval quality is the thing we most want to improve.

## Related

- [Use case: Cost optimization](./cost-optimization.md) — baseline → measure → report template for stakeholders
- [Use case: Claude Code user](./claude-code.md) — full two-phase workflow
- [Comparisons: vs long context windows](../comparisons/vs-long-context.md) — why 1M-token windows don't solve this

---

[← Back to use-case index](./README.md) · [Main README](../../README.md)
