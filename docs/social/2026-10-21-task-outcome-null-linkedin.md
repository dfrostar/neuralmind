**Draft — post only after [#692](https://github.com/dfrostar/neuralmind/pull/692) merges**, so the link resolves to committed data.

# LinkedIn post — 2026-10-21

Company-page post leading with the task-outcome pilot's null result. Every
figure is in `site/claims.json` (the pilot entry, recomputed from
`bench/task_outcome/pilot/` by `tests/test_site_claims.py`) or the public
benchmark entries. Drafted here so `tests/test_docs_claims.py` vets it before
it is posted.

## Post text

We ran a test we could have kept private.

NeuralMind gives coding agents a local index of your codebase, so they get the right code in fewer tokens. On our public benchmark that holds up: the right file on 40 of 40 pre-registered queries, against 32 of 40 for keyword ripgrep, at 31–67× fewer tokens. On a larger 150-question eval it's 93.3% top-five, and the 10 misses are published.

But fewer tokens in the context window isn't the same as a cheaper agent. So we pre-registered a task-outcome pilot: 20 real bug-fix tasks, Claude Code with and without NeuralMind, three seeds each, 120 runs.

The result: no difference.
• Tasks solved: 18 of 20 in both arms
• Cost per solved task: $0.227 without, $0.216 with
• Median per-task cost change: +0.0% (95% CI −5.2% to +8.6%)

The useful part is why. In 60 runs the agent never once called NeuralMind's tools. It explored the code on its own, just as it did without NeuralMind (a median of 4 explore calls before the first edit in both arms). Better retrieval doesn't help an agent that never asks for it.

It's a pilot: 20 tasks, one agent, one model. We'll publish the next run the same way, whatever it shows. If we only published the benchmarks we win, you'd have no reason to trust them.

Spec, harness and raw data: https://github.com/dfrostar/neuralmind/pull/692

## Fact check (against the committed run)

| Claim | Source |
|---|---|
| 40 of 40 vs ripgrep's 32 of 40, 31–67× | `bench/public/results.json`, `site/claims.json` |
| 93.3% top-five, 10 misses | `bench/retrieval/on-v4.12/results.json` |
| 20 tasks, 3 seeds, 120 runs; 18 of 20 solved in both arms | `bench/task_outcome/pilot/report.txt`, `runs.jsonl` |
| $0.227 vs $0.216 per solved task; +0.0% (95% CI −5.2% to +8.6%) | `bench/task_outcome/pilot/report.txt` |
| No NeuralMind MCP tool called in the 60 runs with it | `runs.jsonl` `tool_counts` (no `mcp__` entry) |
| Median 4 explore calls before the first edit, both arms | `runs.jsonl` `explore_calls_before_first_edit` |
