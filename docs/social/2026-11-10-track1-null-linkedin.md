# LinkedIn post — 2026-11-10

**Draft, not posted.** Post only after
[#785](https://github.com/dfrostar/neuralmind/pull/785) has merged, so the
data link resolves to the committed run, and after the owner has decided what
the last paragraph commits to.

Company-page post leading with track 1's null result: the sixth task-outcome
study, on the setting picked as the most favourable. Every task-outcome figure
is in `bench/task_outcome/t1-bigrepo-smallmodel/stage2/` (`analyze.txt` is the
analyzer's own output, `runs.jsonl` the 120 records); the retrieval figures are
the ones `site/claims.json` already carries. Drafted here so
`tests/test_docs_claims.py` vets it before it is posted.

LinkedIn renders plain text: paste the post as it stands, with no Markdown.
The first two lines show above "see more". If reach matters, move the last two
lines into the first comment and end the post with "Methodology and raw data
in the comments."

## Post text

We gave our product its best shot at making an AI coding agent solve more tasks. It solved the same number. Here is the full result.

NeuralMind gives coding agents a local index of a codebase, so they can find the right code using far fewer tokens. On retrieval, the evidence is strong: on our public benchmark it found the correct file on 40 of 40 pre-registered queries, against 32 of 40 for keyword ripgrep, using 31–67× fewer tokens.

Five earlier studies found no difference in what agents actually finish. So we pre-registered one more, on the setting where finding the right file should matter most: a small local model (20B, running on one laptop GPU) working in a repository of about a million lines, where the agent's own searching is slow and expensive. 20 real bug-fix tasks, with and without NeuralMind, three runs of each, 120 runs in total.

The results:
• Tasks solved: 3 of 20 with NeuralMind, 3 of 20 without
• One task was solved only with it, one only without (p = 0.75)
• Runs solved: 10 of 60 with, 12 of 60 without
• Median token change per task: −7.7% (95% CI −12.2% to +11.6%)

No measurable difference.

What we saw underneath: NeuralMind's prompt hook named a file the fix needed on 7 of the 20 tasks, and put it first every time. Slightly more runs then edited a right file (30 of 60 against 28), and the first edit came a few tool calls sooner. None of that turned into more solved tasks. A model that solves 3 of 20 is mostly not failing at finding the file.

Three things went wrong during the run and are in the published record: the start slipped 13.5 hours because another model was holding the GPU, two attempts were thrown away and re-run when the agent fell back to a cloud model, and one run shared the GPU with another job. None of them touched a task that either arm solved.

The limits: 20 tasks, one model, one repository, and a 15% solve rate, which can only detect a large effect. This rules out a large gain. It does not show harm.

We wrote down beforehand what a null result here would mean: stop building for agents, and publish. This is the publishing.

Full methodology, raw data and every deviation: https://github.com/dfrostar/neuralmind/tree/main/bench/task_outcome/t1-bigrepo-smallmodel/stage2
The pre-registration and its change log: https://github.com/dfrostar/neuralmind/blob/main/docs/specs/TASK-OUTCOME-BIGREPO-SMALLMODEL.md

#AIEngineering #DeveloperTools #Benchmarking

## Fact check (against the committed runs)

| Claim | Source |
|---|---|
| 40 of 40 vs ripgrep's 32 of 40, 31–67× | `bench/public/results.json`, `site/claims.json` |
| Five earlier studies, no significant difference | the spec's "Why this track" (pilot, v4.21.0 rerun, hermes-agent screen, Hermes pilot, memory track) |
| 20B local model on one laptop GPU; ~1M-line repository | spec: gpt-oss:20b-64k on ai-9970 (RTX 5000 Ada laptop GPU), hermes-agent at `710fa8a` |
| 20 tasks, 3 seeds, 120 runs | `stage2/runs.jsonl` (60 per arm) |
| 3 of 20 in each arm; one discordant task each way; p = 0.75 | `stage2/analyze.txt` |
| 10 of 60 and 12 of 60 runs solved | `stage2/analyze.txt` |
| −7.7% (95% CI −12.2% to +11.6%) | `stage2/analyze.txt` |
| Block named a gold file on 7 of 20 tasks, always first | `runs.jsonl` `block_names_gold`, `block_first_is_gold` (20 of 60 runs, both fields equal) |
| 30 of 60 against 28 edited a gold file | `stage2/analyze.txt` |
| "A few tool calls sooner" (median 54.3 against 61.0 before the first edit) | `stage2/analyze.txt`; reported, not tested |
| 13.5 h slip, two re-run attempts, one shared-GPU run; none on a solved task | `stage2/README.md` "Deviations", spec entry 2026-11-10 |
| "Stop building for agents; publish" was written beforehand | the spec's stage table, row 2, in the file since 2026-11-01 |

Two sentences are judgment, not measurement, and are the poster's to stand
behind: "mostly not failing at finding the file" (an inference from 26 of 60
runs in each arm ending at the turn cap, and from gold-file edits that did not
pass), and "This is the publishing", which quotes the registered consequence
without saying what the company does next. Decide that before posting; the
post can carry one more sentence on it or none.
