# Task outcomes, track 1: a small model on a big repository

**Status:** pre-registered 2026-11-01; stages 0 and 0b complete; stage 1's
prerequisites under way (2026-11-05), no agent run yet.
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

Stage 0b result (2026-11-03,
[`bench/task_outcome/lexical-anchoring/`](../../bench/task_outcome/lexical-anchoring/README.md#confirmation-12-new-tasks-stage-0b)):
flag on, a changed file listed first on **5 of 12** (flag off 2; named 7 of 12
both ways). **Passed, exactly at the gate.**

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
- 2026-11-03 — stage 0b's procedure, fixed before the walk is continued.
  - **Gate, unchanged:** flag on, the first-listed file is one the fix changed
    on at least 5 of 12 tasks ("first", chosen before the replay as registered;
    "named" is not used). The flag-off row is reported beside it.
  - **Population:** the seeded walk (seed 20261025, hermes-agent pinned at
    `710fa8a`) from position 25 on, in walk order, with `draw.py` as committed
    in `evals/task_outcome/studies/hermes-agent-screen/`; a commit qualifies as
    it has so far (a fail-to-pass test). Positions 0–24 are the screen and the
    first held-out set.
  - **Prompts and exclusions:** a separate agent that sees only each fix's tests
    and diff writes the prompt, as for the first held-out set. It may mark a task
    unwritable only where its tests check names the fix introduces. It sees no
    ranking, replay output, threshold or stage. Each exclusion is recorded with
    its reason, and the walk goes on until 12 tasks have prompts.
  - **Order of work:** the task list (ids, commits, gold files, prompts,
    exclusions) is committed before any replay runs.
  - **Replay:** NeuralMind v4.24.0, the first release carrying the flag, through
    `bench/task_outcome/lexical-anchoring/replay_lexical.py`: one index per task
    built once with that version, then `neuralmind _hook prompt-submit` with the
    flag off and with it on on a fresh clone of each index, scored by
    `evals/task_outcome/replay.py`'s `score()`.
  - **If it fails:** the flag stays default-off and stage 1 does not start. The
    result is stated with the flag-off row and every task's outcome, misses
    included.
- 2026-11-03 — correction to the entry above, made before any task of the set was
  read or any prompt written. The exclusion reasons are the screen's (a), (b) and
  (c) (`docs/specs/TASK-OUTCOME-HERMES-AGENT-SCREEN.md`), not (c) alone: the entry
  above named only the one the first held-out set happened to use. The writing
  agent records each exclusion under its letter in `confirm/exclusions.json`, and
  the walk still goes on until 12 tasks have prompts.
- 2026-11-03 — stage 0b run, as registered above. Walk positions 25 to 39; 12
  tasks with prompts, 2 commits excluded under (c) (`cf94a29319`, `e68c489c96`);
  NeuralMind 4.24.0, one index per task, the real hook, flag off and on.
  - **Result:** flag on, a changed file listed first on 5 of 12; flag off 2 of 12.
    Named: 7 of 12 both ways. The flag gained *first* on 3 tasks and lost none.
  - **The gate is met at its threshold, with no margin.** It counts tasks, so one
    task moving either way flips it. Stage 0's *first* count was also exactly at
    its threshold. The *first* gains replicate across the two held-out sets
    (3 to 5, then 2 to 5, no losses); the *named* gain (4 to 7) did not (7 to
    7): this set's flag-off block already named 7 of 12.
  - **What follows:** stage 1 may start once its prerequisites are met. The
    flag's default is unchanged (off); turning it on is a separate decision.
  - **The three confirmation tasks for stage 1**, in walk order, named here before
    its first run: `f94d72f7e8`, `ebf002cd3e`, `5381678d03`. The floor check may
    replace tasks only as its "if it fails" column says.
- 2026-11-05 — stage 1's prerequisites, before its first run. Every change to
  the frozen ai-9970 baseline is recorded in `~/nm-pilot/environment.json` as it
  is made, and `preflight.py` stops the chain if anything else moves.
  - **The harness could not run the design.** Since 2026-10-30 (harness 3) the
    runner refused `--agent hermes` with the `hermes-agent` profile, whose
    workspaces get their own `HERMES_HOME`, because that home would reach
    `hermes chat`. This track's design, written two days later, is that pair,
    and nothing in it said so. Harness 6 runs it (main spec, 2026-11-05):
    `hermes chat` keeps the host's home, the index build and the judge's test
    runs get the workspace's, `--guard ~/.hermes/hermes-agent/.hermes/bin` is
    the net. The agent's own commands run in the gateway under the host's home
    either way.
  - **The prompt's test line.** In the Hermes pilot, `python -m pytest` in the
    gateway was Hermes's own venv, without the project's dependencies; `No
    module named` answered 88 of the agent's pytest commands, both arms alike
    (main spec, 2026-11-05). For Hermes the prompt now spells out the test
    venv's interpreter, and each run records the line (`pytest_command`). The
    task prompts are the committed ones, unchanged.
  - **Tasks:** `evals/task_outcome/studies/t1-bigrepo-smallmodel/tasks.json`,
    the 20 named above in the registered order, committed before any run, each
    entry copied unchanged from its source. Before the first run they are
    re-harvested on ai-9970 with the stage 1 test venv (select_tasks' rule: the
    same FAIL_TO_PASS and PASS_TO_PASS as committed); the result is logged
    below.
  - **Environment, recorded as it is set:** Hermes 0.22.6, not the 0.22.5
    baseline — the user ran `hermes update` on ai-9970 on 2026-11-03 15:22 UTC;
    stage 1 and 2 run on the one version, and a further update stops the chain.
    Compression provider `custom` at `http://127.0.0.1:11434/v1` — Hermes
    rewrote the baseline's `ollama` into that equivalent form on 11-03 (same
    model, same local endpoint). NeuralMind **4.24.0** as the tool and the
    Hermes plugin: the pin move from 4.23.1 named in the design; 4.23.1 remains
    the baseline for every earlier track. Test venv: Python 3.14.7 with
    hermes-agent's locked dependencies at `710fa8a` (`uv export --frozen`,
    installed without re-resolution) plus `pyyaml`, `pytest 9.1.1`,
    `pytest-asyncio 1.4.0`, as the screen's. hermes-agent clone at `710fa8a`.
  - **Runs:** out dir `~/nm-bench/tracks/t1-bigrepo-smallmodel/runs`,
    `--order-seed 20261014` (the runner's default, as the pilot), `--max-turns
    120 --timeout 3600`. The floor check is `--arms baseline --seeds 1`; its 20
    runs are stage 2's baseline seed-0 runs, as in the Hermes pilot, so stage 2
    adds 100. Hermes's cron jobs are paused and the apt and
    `neuralmind-maintain` timers stopped for the runs, as for the memory track;
    the 20 indexes are built once into `~/nm-bench/index-cache/` with 4.24.0
    before the floor check, so no measured run builds one.
  - **Re-harvest on ai-9970 (2026-11-06), before the first run:** 18 of 20
    identical. `24b4f90e97`: the same FAIL_TO_PASS, and the committed 8
    PASS_TO_PASS all pass, among 23 that pass there (15 process-custody tests
    the Mac skipped); judged by the committed lists, unchanged. `696f6e9ff9`:
    `tests.tui_gateway.test_tui_gateway_server::test_notification_poller_live_loop_requeues_foreign_completion_for_owner`,
    PASS_TO_PASS as committed, failed at the base commit inside the full suite
    in both harvests there and passed at the fix in one of the two, while
    passing 5 of 5 alone at either commit: flaky in the suite under load, and
    no evidence about the fix. It is removed from that task's PASS_TO_PASS
    (723 to 722 judged tests); the task's FAIL_TO_PASS and everything else
    stand. No other task changed.
  - **Done on ai-9970 at 04:38 UTC 2026-11-06,** recorded in
    `environment.json`: NeuralMind 4.24.0 as the tool and the plugin;
    `NEURALMIND_RECALL_LEXICAL=1` in the gateway's environment for the whole
    track (a baseline workspace has no index, so nothing to anchor there); 13
    cron jobs paused (`~/nm-bench/cron-paused-for-t1.txt`), the apt and
    `neuralmind-maintain` timers stopped; gateway restarted; preflight exit 0
    against the updated record. The index builds and then the floor check run
    from a chain (`~/nm-bench/t1_floor_chain.sh`) that stops on drift or a
    fifth harness failure and does not start stage 2: the floor result is read
    first.
