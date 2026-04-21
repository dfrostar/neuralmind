# Use Case: LLM Cost Optimization

## What you're solving for

Your team or product spends measurable money on LLM API calls for code questions. You need to reduce spend **without** moving to a cheaper model or cutting features, and report the savings to a stakeholder.

## Step 1 — Baseline the current spend

Before installing NeuralMind, capture what you're spending. Pick a representative workday:

```bash
# Count tokens per query today by logging your agent's input/output
# (most agents have a debug mode or you can estimate with tiktoken)
```

Compute: `avg_tokens_per_query × queries_per_day × 30 × $_per_MTok`. That's your monthly floor.

## Step 2 — Install NeuralMind

```bash
pip install neuralmind graphifyy
graphify update .
neuralmind build .
neuralmind install-hooks .     # Claude Code users only
```

## Step 3 — Measure the new baseline

```bash
neuralmind benchmark . --json
```

Returns:

```json
{
  "wakeup_tokens": 341,
  "avg_query_tokens": 739,
  "avg_reduction_ratio": 65.6,
  "results": [...]
}
```

Compare `avg_query_tokens` to your pre-install baseline. This is the **retrieval-side** savings.

## Step 4 — Measure consumption-side savings (Claude Code)

PostToolUse hooks compress Read/Bash/Grep output. Rough numbers:

| Tool | Typical reduction |
|---|---|
| Read | ~88% (file → skeleton) |
| Bash | ~91% (errors + tail) |
| Grep | Capped at 25 matches |

Combined retrieval + consumption is typically **5–10× total reduction** vs baseline.

## Step 5 — Report to stakeholders

A one-page summary template:

> **NeuralMind rollout — token cost impact**
>
> - Baseline: `{avg_tokens} × {queries/day} × 30 × ${price}/MTok = ${monthly}`
> - After NeuralMind: `{new_tokens} × {queries/day} × 30 × ${price}/MTok = ${new_monthly}`
> - Reduction: **{ratio}×** on retrieval, **{total_ratio}×** combined with PostToolUse hooks
> - Setup cost: one-time `graphify update && neuralmind build` (~minutes)
> - Ongoing cost: incremental rebuild on git commit (seconds)
> - Risk: fully local, no new SaaS dependency, MIT-licensed

## Ongoing hygiene

- **Index freshness:** `neuralmind init-hook .` auto-rebuilds on every commit.
- **Adapt to workflow:** enable memory (TTY prompt) + periodically `neuralmind learn .` to rerank by actual query patterns.
- **Model changes:** run `neuralmind benchmark` again when you switch models — absolute dollar savings scale with input price.

## What this doesn't fix

- **Output tokens** — NeuralMind reduces input context, not model output length. Pair with prompt instructions to keep responses concise.
- **Non-code LLM usage** — docs QA, ticket triage, etc. NeuralMind is code-specific.
- **One-off experiments** — savings compound with repeated queries; single questions show less benefit.

---

[← Back to use-case index](./README.md) · [Main README](../../README.md)
