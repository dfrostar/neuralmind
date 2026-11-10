# Track 1, stage 1: the floor check

**Pre-registered** in
[`TASK-OUTCOME-BIGREPO-SMALLMODEL.md`](../../../../docs/specs/TASK-OUTCOME-BIGREPO-SMALLMODEL.md):
gpt-oss:20b-64k through Hermes, **without** NeuralMind, seed 0, the 20
hermes-agent tasks of
[`studies/t1-bigrepo-smallmodel/`](../../../../evals/task_outcome/studies/t1-bigrepo-smallmodel/).
Gate to go on: at least 3 of 20 solved. Not a product claim: one arm, one seed,
run to decide whether stage 2's 120 runs are worth running.

**Result: 3 of 20 solved. The gate is met at its threshold, with no margin.**

## Setup

- ai-9970, 2026-11-06 08:03 to 11:46 UTC, from the chain in the spec's
  2026-11-05 entry. Harness 6, Hermes 0.22.6, NeuralMind 4.24.0 installed but
  unused (no index in a baseline workspace), `--max-turns 120`, timeout
  3600 s, `--order-seed 20261014`. Preflight matched the recorded environment
  before the first run.
- Test venv Python 3.14.7 with hermes-agent's lock at `710fa8a`; the prompt
  named that interpreter (`pytest_command` in every record).
- No run timed out, none ended on a harness failure, none used a paid
  provider (Hermes priced every session at $0; the harness aborts otherwise).
  Whole-session tokens and minutes are in `sessions.json`
  (`hermes_sessions`), the per-run records in `runs.jsonl`.

## The 20 runs

| Task | Solved | F2P passed | P2P failed | API calls | Edited | Touched a gold file | Explore calls before the first edit | Minutes | Prompt tokens |
|---|---|---|---|---|---|---|---|---|---|
| `0968fa2631` | no | 0/2 | 0 | 28 | no | no | 27 | 1.0 | 0.57M |
| `e9eba2188a` | no | 1/2 | 0 | 59 | yes | yes | 24 | 9.4 | 2.10M |
| `24b4f90e97` | no | 0/1 | 0 | 108 | yes | yes | 82 | 10.1 | 3.14M |
| `5381678d03` | no | 0/1 | 0 | 118 (cap) | no | no | 115 | 21.4 | 4.11M |
| `1c39127d37` | no | 0/1 | 0 | 105 | no | no | 102 | 13.4 | 3.59M |
| `e3fbd32d26` | no | 0/1 | 0 | 119 (cap) | no | no | 115 | 6.9 | 4.00M |
| `cd69be6909` | no | 1/1 | 1 | 119 (cap) | yes | yes | 12 | 11.2 | 4.26M |
| `a3537b6f04` | **yes** | 1/1 | 0 | 19 | yes | yes | 14 | 1.1 | 0.44M |
| `696f6e9ff9` | no | 0/2 | 1 | 120 (cap) | no | no | 120 | 9.4 | 4.16M |
| `3c53adbc1e` | no | 0/3 | 0 | 17 | yes | yes | 14 | 1.0 | 0.31M |
| `28e6496a5e` | no | 0/3 | 0 | 120 (cap) | no | no | 120 | 9.1 | 3.98M |
| `4a78de2805` | **yes** | 3/3 | 0 | 120 (cap) | yes | yes | 7 | 15.4 | 4.06M |
| `167a2d00ed` | no | 0/1 | 0 | 106 | yes | no | 47 | 14.3 | 3.62M |
| `ebf002cd3e` | no | 0/1 | 0 | 118 (cap) | yes | no | 46 | 15.3 | 4.09M |
| `859b999db5` | no | 0/1 | 0 | 119 (cap) | yes | no | 33 | 12.5 | 4.51M |
| `d4fa373017` | **yes** | 1/1 | 0 | 19 | yes | yes | 15 | 4.0 | 0.48M |
| `652e4b9194` | no | 0/1 | 0 | 120 (cap) | no | no | 118 | 9.2 | 4.25M |
| `0cb3760383` | no | 0/1 | 0 | 109 | no | no | 104 | 11.5 | 3.71M |
| `44cf71f231` | no | 0/2 | 0 | 119 (cap) | no | no | 113 | 14.8 | 4.42M |
| `f94d72f7e8` | no | 0/3 | 0 | 117 (cap) | no | no | 107 | 14.5 | 3.88M |

The API calls column is `num_turns`, which the runner fills from the
session's count of model requests; tool calls are in `tool_counts` and run a
little lower. "cap" marks the 11 sessions that exited nonzero with 117 to 120
API calls against the 120-turn limit. That is the evidence for calling them
turn-limit endings: the runner writes `subtype: error` for any nonzero exit,
the records carry no termination reason from Hermes, and no session that
exited cleanly made more than 109 calls.

## What the runs show

- **Solved 3 of 20:** `a3537b6f04` (19 API calls, 1.1 min), `d4fa373017` (19
  API calls, 4.0 min) and `4a78de2805` (3 of 3 tests, solved on the last turn
  before the cap, 15.4 min). The Hermes pilot's baseline on NeuralMind's own
  repository (about 50k lines) solved 10 of 20 at seed 0 with a median of
  97 tool calls (99 API calls); here, on about a million lines, the median is
  110 tool calls (117.5 API calls).
- **Exploration ate the budget.** 11 runs ended at the turn cap, 10 never
  edited a file, and in nine of those the agent made 101 to 120
  `search_files` and `read_file` calls (the tenth, `0968fa2631`, stopped
  after 27). Seven runs touched a file the fix changed; four of
  those still failed (`e9eba2188a` passed 1 of 2 tests, `cd69be6909` fixed
  its test but broke another, `24b4f90e97` and `3c53adbc1e` edited the
  right file and did not pass). Median session: 117 API calls, 3.9M prompt
  tokens (the context is re-sent on every call), 10.7 minutes; 3.4 GPU-hours
  in all.
- **The agent mostly ignored the interpreter it was given.** Of 48 pytest
  commands it typed across the 11 runs that ran tests, 10 used the venv path
  the prompt named and 38 a bare `python`/`pytest`, which in the gateway is
  Hermes's own venv: `No module named` came back 15 times, 17 commands went
  to the background, and 2 returned a pass/fail count directly. Harness 6's
  line is true, and a 20B model does not reliably follow it. This holds for
  both arms alike in stage 2; the mechanism endpoints there do not depend on
  the agent's own test runs.

## What it does and doesn't decide

- The registered rule is met, so stage 2 may run as designed; "exactly at
  the threshold" is a fact about the sample, not a reason to move it.
- These 20 runs were to be stage 2's baseline seed-0 runs. Hermes was
  updated to 0.23.0 on 2026-11-06 19:40 UTC, after the last of them: whether
  stage 2 reuses them across that version change or runs all 120 on one
  version is decided in the spec's change log before stage 2's first run.
- No arm comparison exists yet: nothing here says anything about NeuralMind.
