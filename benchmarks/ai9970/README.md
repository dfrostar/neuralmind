# `benchmarks/ai9970/` — the longitudinal performance record

The rows behind https://neuralmind.uk/performance/: our own repos, re-measured
on one machine (`ai9970`, a single RTX 5000 Ada 16GB dev box), committed as each
run produced them. Registered in [`site/claims.json`](../../site/claims.json)
(`longitudinal_record`) like every other source of a number on the site.

| File | What it is |
|---|---|
| `record.jsonl` | One row per project per run. Append-only. |
| `profile.json` | What doesn't change run to run: the machine, the method, each project's shape. Every project in the record needs an entry. |
| `narratives/YYYY-MM.md` | The month's write-up, in three published blocks (see `narratives/TEMPLATE.md`). |

## Row contract

One JSON object per line. Every field below must be present; write `null` for
anything the run did not record. **Never fill a null in**: no interpolation, no
carrying a value forward, no estimate. The page shows a blank as a blank.

| Field | Type | From |
|---|---|---|
| `ts` | ISO 8601 date or date-time | when the run happened |
| `project` | repo name | `eval_history.jsonl` `project` |
| `version` | string | NeuralMind version (`version`) |
| `git_sha` | string | the project's commit (`git_sha`) |
| `hit_at_1`, `hit_at_5` | 0–1 | `hit_at_1`, `hit_at_5` |
| `mrr` | 0–1 | `mrr` |
| `avg_ctx_tok` | number | `avg_context_tokens` |
| `ratio_vs_indexed` | number | `ratio_vs_indexed` |
| `baseline_src` | string | `baseline_source`: `measured` or `naive-50k` |
| `nodes` | integer | `node_count` |
| `synapse_edges` | integer | synapse store `edges` |
| `index_age_h` | number | hours since the last build |
| `builds_7d` | integer | builds in the last seven days |
| `mean_build_s` | number | mean build time, seconds |
| `saved_tokens_cum` | integer | cumulative tokens saved (carried, not rendered) |
| `median_query_s` | number | median query time, seconds |
| `gold_n` | integer, optional | `n_questions`: the gold-set size |
| `baseline_tok` | integer, optional | `baseline_tokens`: the measured baseline the ratio divides |

The "From" column names the fields of `neuralmind eval .`'s
`.neuralmind/eval_history.jsonl` where one exists. `gold_n` and `baseline_tok`
were added to the original row shape because the page cannot show a miss count
or a ratio's baseline without them; a row may leave them out, which reads as
`null`.

The site build (`site/src/lib/record.ts`) rejects a row that has an unknown or
missing field, a rate outside 0–1, `hit_at_1` above `hit_at_5` or above `mrr`,
a hit rate that is not a whole number of hits out of `gold_n`, or a
`ratio_vs_indexed` that disagrees with `baseline_tok / avg_ctx_tok`.

## What the page does with a row

- A row whose `baseline_src` is not exactly `measured` is **withheld whole**,
  and the number withheld (with the reason) is printed under the project's
  table.
- A ratio renders only beside its `baseline_tok`.
- A hit rate renders only with `gold_n`, as "8 of 12 · 4 missed"; under 50
  questions it carries a "small sample" badge.
- A metric lower than in the last run that showed it highlights the row; the
  row stays.
- A version different from the last recorded one is marked in the table and
  as a dashed rule on the sparklines.

## Adding a month

1. Append the month's rows to `record.jsonl` (and a `profile.json` entry for a
   new project).
2. Copy `narratives/TEMPLATE.md` to `narratives/YYYY-MM.md` and fill it in.
   Every block is published, and all three go through the site's claims guards
   (`tests/test_performance_record.py`).
3. Put the month's integrity notes (how the rows were produced: reruns,
   withheld rows, open questions) in the private repo, at
   `dfrostar/neuralmind-marketing` `internal/performance-record/ai9970/YYYY-MM.md`.
   Never here: this repo is public on GitHub, and a narrative with a `## D`
   block, an integrity heading, or a file named for integrity notes under
   `benchmarks/ai9970/` fails the build and the tests.
4. Open a PR. The site build and its tests run on any change here, and merging
   to `main` redeploys the site.

The record is read from this one path, so a `workflow_dispatch` job that
uploads the rows later only has to write `record.jsonl` (and run the same
build, which validates it) — nothing in `site/` changes.

## Reproduce

On your own repo: `neuralmind eval .` (questions with gold files, in
`.neuralmind.eval.yaml`) and `neuralmind benchmark .`. These rows are
reproducible in method, not in number: the repos are ours and the machine is
one dev box.
