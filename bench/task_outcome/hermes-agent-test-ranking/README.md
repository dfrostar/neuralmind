# Prompt hook test ranking: hermes-agent, held out

**Offline replays only, no agent runs, and not a product claim.** What the
`UserPromptSubmit` hook's block lists, scored against the real fix, before and
after the change that makes it list source files ahead of tests
([release notes](../../../docs/releases/RELEASE_NOTES_v4.23.0.md)). Whether an
agent does anything differently with the new block is not measured.

## Why

On the [hermes-agent](https://github.com/NousResearch/hermes-agent) task-outcome
screen's 5 tasks, 18 of the 32 files the block listed were tests. The block was
meant to put tests after the code they test unless the prompt is about tests,
but its test for "about tests" was any mention of a test. Every benchmark
prompt mentions one: the task-outcome harness ends each prompt with a line
about the project's tests, and bug reports often do too. So the ordering never
applied.

## What changed

- **A:** a prompt is about tests only when it names one: a `test_*` function, a
  `Test*` class, or a test file's path.
- **C:** a matched test file credits the code file it tests, found by name
  (`tests/agent/test_x.py` → `agent/x.py`), with its best score
  (`TESTED_CODE_CREDIT = 1.0`).

## Method

- **Tuned on (dev):** the screen's 5 tasks. Variants were compared in-process
  on cached search hits. The `main` row reproduces the screen's own replay
  exactly.
- **Choice fixed before held-out results:** A + C, with A alone as the
  ablation. Two other variants were tried on dev and dropped: searching 48 or
  64 hits deep to fill code slots, and keeping tests out of the "connected"
  list.
- **Held out:** 12 hermes-agent bug-fix tasks.
  - 3 are screen candidates the screen didn't select: `e9eba2188a`,
    `24b4f90e97`, `3c53adbc1e`.
  - 9 come from continuing the screen's seeded walk (seed 20261025, hermes-agent
    pinned at `710fa8a`) from position 12 to 24. Of those 13 positions, 12
    qualified and 1 didn't.
  - 3 qualifying tasks were excluded because their tests check names the fix
    introduces, which no fix written from the symptom could produce
    ([exclusions.json](heldout/exclusions.json)).
  - A separate agent wrote the prompts from each fix's tests and diff, without
    seeing either ranking.
  - Every test run during the walk kept the Hermes launcher guard on
    `~/.hermes/hermes-agent/.hermes/bin`. The launchers were unchanged
    afterwards, and `hermes --version` still worked.
- **Before** is `main` at `472f1fa1` (v4.22.1). **After** is this branch. Both
  report `neuralmind 4.22.1`, the version on `main` at the time.
- **Same indexes for both:** each task's index was built once with v4.22.1, and
  every hook call ran on a fresh clone of it. Before and after differ only in
  ranking.
- **Scored by `evals/task_outcome/replay.py`'s `score()`:**
  - *named*: a file the fix changed is listed.
  - *first*: it's listed first.
  - *excerpt on gold*: the quoted code is from such a file.

## Result

Held out, 12 tasks, through the real `neuralmind _hook prompt-submit`
([before](heldout/before/replay-results.json),
[after](heldout/after/replay-results.json)):

| | v4.22.1 | After |
|---|---|---|
| A file the fix changed is listed | 4 | 4 |
| …and listed first | 1 | 3 |
| Code quoted / from a changed file | 2 / 0 | 2 / 1 |
| Test files among the files listed | 33 of 82 | 6 of 84 |
| Median block size (characters) | 923 | 728 |

The ablation, from in-process recall on cached hits
([variants-heldout.json](variants-heldout.json)). Its `main` and `A+C1.0`
rows match the hook replays above exactly:

| Held out, 12 tasks | v4.22.1 | A | A + C |
|---|---|---|---|
| Listed | 4 | 4 | 4 |
| First | 1 | 3 | 3 |
| Code from a changed file / quoted | 0 / 2 | 1 / 2 | 1 / 2 |
| Tests listed | 33 / 82 | 8 / 83 | 6 / 84 |

Dev, 5 tasks, the ones it was tuned on ([variants-dev.json](variants-dev.json)):

| Dev, 5 tasks | v4.22.1 | A | A + C |
|---|---|---|---|
| Listed | 2 | 2 | 3 |
| First | 1 | 2 | 3 |
| Code from a changed file / quoted | 1 / 3 | 1 / 1 | 1 / 1 |
| Tests listed | 18 / 32 | 2 / 35 | 2 / 35 |

What it shows, and what it doesn't:

- **Tests go to the back on held-out tasks too.** The share of listed files
  that are tests fell from 40% to 7%. On 2 tasks the file to fix moved to the
  top, and on a third the block now quotes it.
- **The block names the file to fix no more often.** It's listed on 4 of 12
  either way. Where it was missing before, it's still missing: the prompts
  match other code, not tests sitting in its place.
- **The credit (C) adds nothing measurable held out.** It changed 2 of 84
  listed files and no score. Its dev gain (one task) didn't carry over. It
  ships as pre-registered, as the smaller part of the change.
- **The samples are small.** 12 held-out tasks from one repository is enough to
  see the ordering change, not to estimate its size.

On NeuralMind's own repository, the pilot's 20-task replay floors
(`replay.py --check`) still pass. Both versions ran on the same 20 indexes,
built once with v4.22.1, and a second v4.22.1 run on them matched the first
exactly ([before](pilot/before/replay-results.json),
[after](pilot/after/replay-results.json)):

| Pilot, 20 tasks | v4.22.1 | After | Floor |
|---|---|---|---|
| Listed | 17 | 17 | 15 |
| First | 10 | 11 | 9 |
| Code from a changed file / quoted | 7 / 9 | 7 / 8 | 70% |

The old rule matched all 20 pilot prompts, because the harness's prompt asks
the agent not to change tests. The new one matches none of them.

## Reproduce

The script needs the task-outcome harness from #719/#720 (see its docstring)
and an hermes-agent clone at `~/nm-bench/hermes-agent`.

```bash
python replay_heldout.py build heldout <shim-v4.22.1> <task-id>...
python replay_heldout.py prepare heldout
python replay_heldout.py hook heldout <shim-v4.22.1> before
python replay_heldout.py hook heldout <shim-branch> after
python replay_heldout.py capture heldout
python replay_heldout.py variants heldout
```

Building the 12 indexes took 20–30 minutes each on one M-series Mac,
hermes-agent being about 300,000 graph nodes.
