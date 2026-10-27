# LinkedIn post — 2026-10-21

**Draft, ready to post.** [#692](https://github.com/dfrostar/neuralmind/pull/692) has merged, so the data link resolves to the committed run. Updated 2026-10-27 with the v4.21.0 exploratory rerun ([#696](https://github.com/dfrostar/neuralmind/pull/696)).

Company-page post leading with the task-outcome pilot's null result. Every
figure is in `site/claims.json` (the pilot entry, recomputed from
`bench/task_outcome/pilot/` by `tests/test_site_claims.py`), the public
benchmark entries, or the rerun's committed report
(`bench/task_outcome/exploratory-agent-uptake/report.txt`). Drafted here so
`tests/test_docs_claims.py` vets it before it is posted.

LinkedIn renders plain text: paste the post as it stands, with no Markdown.
The first two lines show above "see more". LinkedIn tends to show posts with
links to fewer people; if reach matters, move the last two lines into the
first comment and end the post with "Methodology and raw data in the
comments."

## Post text

We tested whether our own product makes AI coding agents cheaper. It didn't. Here is what we found.

NeuralMind gives coding agents a local index of a codebase, so they can find the right code using far fewer tokens. On retrieval, the evidence is strong. On our public benchmark it found the correct file on 40 of 40 pre-registered queries, against 32 of 40 for keyword ripgrep, while using 31–67× fewer tokens. On a larger 150-question evaluation it ranks the correct file in the top five 93.3% of the time, and we publish all 10 misses.

But retrieval quality is not the same as task outcomes. So we pre-registered a pilot: 20 real bug-fix tasks, Claude Code with and without NeuralMind, three runs of each, 120 runs in total.

The results:
• Tasks solved: 18 of 20, with and without NeuralMind
• Cost per solved task: $0.216 with, $0.227 without
• Median per-task cost change: +0.0% (95% CI −5.2% to +8.6%)

No measurable difference.

The more important finding was the reason. In all 60 runs with NeuralMind installed, the agent never called a single NeuralMind tool. It searched and read files much as it did without it.

We then shipped a change aimed at exactly that in v4.21.0: explicit tool instructions and a shorter tool list. We reran the tasks. The agent still made no NeuralMind tool calls in 60 runs, and the cost change was −2.1% (95% CI −6.9% to +6.5%), again within noise. That rerun was exploratory, not pre-registered.

Our takeaway: better retrieval only helps if the agent actually uses it. That is the problem we are working on now, and we will publish the next result the same way, whatever it shows.

These are small studies (20 tasks, one agent, one model), and we label them that way. But if we only published the benchmarks we win, you would have no reason to trust any of them.

Full methodology, raw data and every miss: https://neuralmind.uk/benchmark
The v4.21.0 rerun's data: https://github.com/dfrostar/neuralmind/tree/main/bench/task_outcome/exploratory-agent-uptake

#AIEngineering #DeveloperTools #Benchmarking

## Fact check (against the committed runs)

| Claim | Source |
|---|---|
| 40 of 40 vs ripgrep's 32 of 40, 31–67× | `bench/public/results.json`, `site/claims.json` |
| 93.3% top-five, 10 misses | `bench/retrieval/on-v4.12/results.json` |
| 20 tasks, 3 seeds, 120 runs; 18 of 20 solved in both arms | `bench/task_outcome/pilot/report.txt`, `runs.jsonl` |
| $0.216 with vs $0.227 without per solved task; +0.0% (95% CI −5.2% to +8.6%) | `bench/task_outcome/pilot/report.txt` |
| No NeuralMind MCP tool called in the 60 pilot runs with it | `bench/task_outcome/pilot/runs.jsonl` `tool_counts` (no `mcp__` entry) |
| "Searched and read files much as it did without it" (median 4 explore calls before the first edit, both arms) | `runs.jsonl` `explore_calls_before_first_edit` |
| v4.21.0 change: MCP instructions and a six-tool list (the pilot's server listed 28) | `bench/task_outcome/exploratory-agent-uptake/report.txt`, `site/claims.json` pilot note |
| Rerun: 0 of 60 runs called a NeuralMind tool | `bench/task_outcome/exploratory-agent-uptake/report.txt` |
| Rerun: −2.1% (95% CI −6.9% to +6.5%); exploratory, not pre-registered | `bench/task_outcome/exploratory-agent-uptake/report.txt` |
| 20 tasks, one agent, one model | `site/claims.json` pilot note (claude-sonnet-5-5, Claude Code, one repository) |

The two commitments in the post ("the problem we are working on now", "we
will publish the next result the same way, whatever it shows") are the
poster's to make; check them before posting.
