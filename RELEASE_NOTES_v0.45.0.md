# NeuralMind v0.45.0 — The token receipt gets a price tag

`neuralmind savings` has always answered *"how many tokens did NeuralMind save
me?"* against your own logged usage. v0.45.0 adds the question your CFO (or
your invoice) actually asks: **how many dollars?**

```bash
neuralmind savings --cost
```

## What you see

```text
NeuralMind token savings — global

  Queries logged    : 2695
  Wakeups logged    : 622
  Avg reduction     : 380.6x

  Tokens actually used :    694,677
  Est. cost without NM : 165,850,000  (at 50,000 tokens/query)
  Tokens saved         : 165,155,323

  Dollar savings — claude-opus-4-8 @ $5.0/MTok input
    Cost without NM : $    829.25
    Cost with NM    : $      3.47
    Saved           : $    825.78
    Projected       : $24.90/day · $746.86/month  (at 100 queries/day)
```

The totals above are real, from this repo's own event log at the time of
release. The **`Projected`** line is illustrative: this repo's log mixes
queries and wakeups, and the projection basis was corrected during review
(scaled by the per-*query* average, not diluted by wakeup events — see
"Provenance" below) after this example was captured, so the exact `$/day`
figure a fresh run prints will differ slightly from the one shown.

## New flags on `neuralmind savings`

| Flag | Default | What it does |
|---|---|---|
| `--cost` | off | Append the dollar-savings block (text) or a `dollar_savings` object (`--json`) |
| `--model` | `claude-opus-4-8` | Pricing model. Choices come from the built-in table below |
| `--queries-per-day` | `100` | Assumed daily query volume for the daily/monthly projection |

With `--json`, the report gains a `dollar_savings` block:

```json
"dollar_savings": {
  "model": "claude-opus-4-8",
  "price_per_mtok": 5.0,
  "baseline_cost_total": 829.25,
  "actual_cost_total": 3.47,
  "saved_total": 825.78,
  "daily_saved": 24.9,
  "monthly_saved": 746.86,
  "queries_per_day": 100,
  "days": 30
}
```

## How the math works (and why it's honest)

- **Input-token pricing only.** NeuralMind is a retrieval layer: it decides
  which context tokens get shipped to the LLM. Its savings are input-token
  savings, so output pricing never enters the math.
- **Totals come straight from the token totals.** `saved_total` is
  `(baseline_tokens − used_tokens) / 1M × price` — no re-scaling, no
  compounding. The baseline is the same 50,000-tokens-per-query internal
  reference the token report has always used, so the dollar figure inherits
  exactly the assumptions the token figure already disclosed.
- **Projections are labeled assumptions.** `daily_saved` scales the observed
  *average savings per query* — query events only, not wakeups — by
  `--queries-per-day`; `monthly_saved` is 30 of those days. Change the
  assumption, the projection changes — that's the point.

## Provenance & the corrected math

Re-derived from an uncommitted prototype recovered from an Agent Zero
container backup. The prototype had two bugs, both caught before merge and
pinned by regression tests:

1. Totals were re-multiplied by the event count (`tokens / 1M × price ×
   events` on already-summed totals), inflating every figure ~N-fold.
2. The daily projection treated *total* tokens as *per-query* tokens.

Review caught a third, more subtle one before merge: the projection's
per-event average included **wakeup** events (which log ~0 tokens saved)
alongside queries, so a log with both understated `$/day` relative to what
`--queries-per-day` — a *query* volume assumption — actually claims to
represent. Fixed by scaling from the per-query average specifically; also
pinned by a regression test.

## Pricing table

USD per million **input** tokens, as of 2026-07 (`MODEL_PRICING_PER_MTOK` in
`neuralmind/memory.py` — refresh when providers reprice):

| Model | $/MTok input |
|---|---|
| `claude-fable-5` | 10.00 |
| `claude-opus-4-8` | 5.00 |
| `claude-sonnet-5` | 3.00 |
| `claude-sonnet-4-6` | 3.00 |
| `claude-haiku-4-5` | 1.00 |
| `gpt-5.1` | 1.25 |
| `gpt-5-mini` | 0.25 |
| `gemini-2.5-pro` | 1.25 |
| `gemini-2.5-flash` | 0.30 |

An unrecognized `--model` value is rejected by the CLI; programmatic callers
of `estimate_dollar_savings()` fall back to the default model's price.

## Honest scope

- The figures are **estimates anchored to the 50k/query baseline**, not a
  reconciliation of your provider invoice. Prompt caching, output tokens, and
  per-request overhead are out of scope.
- Prices are a **snapshot** (2026-07). The table is a plain dict — PRs
  refreshing it are one-liners.
- No new environment variables, hooks, or MCP surface — this is a pure CLI
  addition; agents see nothing new unless they run `savings --cost`.

## For agents and scripts

`estimate_dollar_savings()` lives in `neuralmind.memory` and is importable
directly — the same function backs the CLI, so a dashboard or CI job can
compute dollar figures from any token totals without shelling out.
