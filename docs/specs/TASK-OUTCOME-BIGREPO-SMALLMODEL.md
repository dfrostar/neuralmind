# Task outcomes, track 1: a small model on a big repository

**Status:** pre-registered 2026-11-01; stage 0 complete, stage 1 not started.
**Owner:** Darren Frost. **Machine:** ai-9970 (`~/nm-bench/tracks/t1-bigrepo-smallmodel/STATUS.md`
mirrors this table). **Harness:** `evals/task_outcome/run.py`, as in
[`TASK-OUTCOME-BENCHMARK-SPEC.md`](TASK-OUTCOME-BENCHMARK-SPEC.md), whose
primary endpoint (majority-of-3 solve per task, one-sided McNemar) and
deviation-logging rules apply unchanged.

## Why this track

Five task-outcome studies found no significant difference in tasks solved or
cost (pilot, v4.21.0 rerun, hermes-agent screen, Hermes pilot, memory track).
The one behavioural effect seen in transcripts is that the prompt block gets the
agent to a file the fix touches sooner (Hermes pilot: first tool call on such a
file in 16 of 60 runs against 0 of 60; first read at call 4 against 7). That
can only matter where the agent's own search is expensive and only when the
block names the right file. This track tests the one setting with both: a
local 20B model on a ~1M-line repository ([hermes-agent](https://github.com/NousResearch/hermes-agent),
pinned at `710fa8a`), after a ranking change that made the block name the
right file there more often.

## Stages and gates

| Stage | Where | What runs | Gate to go on | If it fails |
|---|---|---|---|---|
| 0. Lexical gate | Mac, offline | lexical anchoring in `prompt_recall`, replayed on cached indexes ([`bench/task_outcome/lexical-anchoring/`](../../bench/task_outcome/lexical-anchoring/README.md), PR #764) | held-out 12: ≥ 6 named, ≥ 5 first; pilot 20: ≥ 17 / ≥ 11; test share not above 14 of 84 | no agent run; the big-repo story ends |
| 0b. Confirmation | Mac, offline | 12 new held-out hermes-agent tasks from the seeded walk (seed 20261025, positions 25 on), prompts written blind to any ranking | named ≥ 6 of 12 **or** first ≥ 5 of 12 (one of the two, chosen before the replay: *first*) | the flag stays default-off; stage 1 does not start |
| 1. Floor check | ai-9970 | gpt-oss:20b-64k **without** NeuralMind, seed 0, the 20 tasks below | ≥ 3 of 20 solved | the tasks are too hard for a 20B model: replace with easier ones from the walk (single-file fixes, diff ≤ 40 lines) and rerun the floor check once |
| 2. Full run | ai-9970 | 20 tasks × {baseline, neuralmind with the flag on} × 3 seeds = 120 runs | primary endpoint p < 0.05 | stop building for agents; publish |

Stage 0 result (2026-11-01, PR #764): held-out 7 named / 5 first against 4 / 3;
pilot 18 / 13 against 17 / 11; test share 14 of 84 unchanged. **Passed.**

## Stage 1 and 2 design, fixed now

- **Tasks:** the 12 held-out tasks of
  [`hermes-agent-test-ranking/heldout/tasks.json`](../../bench/task_outcome/hermes-agent-test-ranking/heldout/tasks.json)
  (which already include the 3 screen candidates the screen didn't select),
  the screen's 5
  ([`studies/hermes-agent-screen/tasks.json`](../../evals/task_outcome/studies/hermes-agent-screen/tasks.json)),
  and the first 3 qualifying tasks of stage 0b's confirmation set (the seeded
  walk from position 25, in walk order), in that order: 20 distinct tasks.
  The 3 confirmation tasks are named here, by id, before stage 1's first run;
  the floor check may replace tasks only as its "if it fails" column says, and
  the replacement list is committed before stage 2's first run.
- **Agent:** Hermes (version recorded per run) on `gpt-oss:20b-64k` via Ollama
  on ai-9970, as in the Hermes pilot; same prompts (the task prompts say how to
  run the tests and not to change them), same 120-turn cap and timeout as the
  Hermes pilot.
- **NeuralMind:** the first release carrying lexical anchoring, with the flag
  **on** in the neuralmind arm; the version is a recorded pin change from
  4.23.1, which remains the baseline for every earlier track. Indexes are built
  once per task into `~/nm-bench/index-cache/` and restored per run
  (`--index-cache`); the index build is not part of the measured run.
- **Endpoints.** Primary: tasks solved (majority of 3), one-sided McNemar,
  claim supported at p < 0.05 (needs ≥ 5 discordant tasks one way). Mechanism,
  reported with the result: index of the first tool call on a file the fix
  touched, index of the first read of one, tool calls to the first edit, runs
  that edited a gold file, 120-turn cap hits. Secondary: tokens, minutes, turns.
  No arm comparison is read before a stage ends.
- **Deviations** are logged in the change log below with the same rules as the
  main spec: harness failures retried and counted, model fallbacks recorded,
  nothing dropped.

## Change log

- 2026-11-01 — Track pre-registered after the memory track completed and the
  lexical gate passed. Stage 0b (confirmation) added to the lexical PR's own
  plan; stages 1–2 wait for it.
