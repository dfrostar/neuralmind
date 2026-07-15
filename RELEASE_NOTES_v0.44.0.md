# NeuralMind v0.44.0 — Token receipts and batch cost estimates

Two lightweight features that turn NeuralMind's existing token-savings data into
dollar figures — pure arithmetic over logs you already have, no new I/O, no API
calls.

## What's in this release

| Feature | Command | What it does |
|---------|---------|-------------|
| **Token receipt** | `neuralmind query --cost` | After every query, print (or JSON-emit) dollars used/saved at the chosen model's input price |
| **Batch cost estimate** | `neuralmind batch-estimate` | Aggregate per-query token costs from the local event log; optionally project to a monthly budget |

---

## 1. `neuralmind query --cost` — per-query cost receipt

Add `--cost` to any `neuralmind query` invocation to get a dollar-denominated
receipt alongside the token count.

```bash
$ neuralmind query . "what does auth() do?" --cost

Query: what does auth() do?
Tokens: 1187 (38.2x reduction)
============================================================
[... context ...]
============================================================
Cost:  $0.0036 used  |  $0.1308 saved  (sonnet 3.00 $/MTok)
```

**Pricing options**

| Flag | Example | Effect |
|------|---------|--------|
| `--model` | `--model haiku` | Pick a named model slug (see table below) |
| `--rate` | `--rate 5.00` | Explicit $/MTok, overrides `--model` |

**Built-in model price table** (input price, $/MTok):

| Slug | Model | $/MTok |
|------|-------|--------|
| `sonnet` *(default)* | Claude 3.5 Sonnet | 3.00 |
| `opus` | Claude Opus 3 | 15.00 |
| `haiku` | Claude Haiku 3 | 0.25 |
| `gpt-4o` | GPT-4o | 5.00 |
| `gpt-4o-mini` | GPT-4o mini | 0.15 |

The math: `cost_used = tokens_used / 1e6 × rate` and
`cost_saved = tokens_used × (ratio − 1) / 1e6 × rate`.
The reduction ratio comes from the query result itself — no magic constants.

**JSON output** — when combined with `--json`, three extra keys appear:

```json
{
  "tokens": 1187,
  "reduction_ratio": 38.2,
  "cost_used_usd": 0.003561,
  "cost_saved_usd": 0.130797,
  "rate_per_mtok": 3.0
}
```

`--cost` is compatible with the daemon path, `--trace`, and all other `query`
flags. Default output is unchanged when `--cost` is absent.

---

## 2. `neuralmind batch-estimate` — aggregate and project costs

`neuralmind batch-estimate` reads the same JSONL event log that `neuralmind
savings` uses and converts token counts to dollar figures. Pass `--qpd` to add a
monthly projection.

```bash
$ neuralmind batch-estimate . --qpd 100

NeuralMind batch cost estimate — my-project
Model: sonnet 3.00 $/MTok

  Queries logged     :     47
  Avg tokens/query   :  1,240
  Avg cost/query     :  $0.0037

  Cumulative (47 queries)
    Tokens used      :     58,280     Cost: $0.1748
    Tokens saved     :  2,332,000     Cost: $6.9960

  Monthly projection (100 queries/day × 30 days)
    With NeuralMind  :  $11.1000/mo
    Without          :  $221.1000/mo
    Savings          :  $210.0000/mo

  Per-query breakdown (most recent 5):
    2026-07-14  [ 1187 tok / 38.2x]  "what does auth() do?"  →  $0.0036 / saved $0.1308
```

All the same `--model` / `--rate` flags apply. `--json` emits a structured
object with a `projection` key (present only when `--qpd` is given):

```json
{
  "scope": "my-project",
  "model": "sonnet",
  "rate_per_mtok": 3.0,
  "total_queries": 47,
  "total_tokens_used": 58280,
  "total_tokens_saved": 2332000,
  "total_cost_used_usd": 0.1748,
  "total_cost_saved_usd": 6.996,
  "avg_tokens_per_query": 1240.0,
  "avg_cost_per_query_usd": 0.003720,
  "projection": {
    "queries_per_day": 100,
    "projected_monthly_cost_with_nm_usd": 11.16,
    "projected_monthly_cost_without_nm_usd": 222.96,
    "projected_monthly_savings_usd": 211.80
  }
}
```

---

## What the agent actually sees post-install

| Agent | What changes | How to use it |
|-------|-------------|---------------|
| **Claude Code** | No change to context injection | Run `neuralmind query . "…" --cost` manually or in scripts |
| **Cursor / Cline / generic MCP** | No change to MCP tools | CLI-only feature; future MCP exposure is tracked |

Both features read data already on disk — they write nothing and make no network
requests. Memory logging must be enabled for `batch-estimate` to have data
(answer yes when first prompted, or set `NEURALMIND_MEMORY=1`).

---

## Upgrade

```bash
pip install --upgrade neuralmind
```
