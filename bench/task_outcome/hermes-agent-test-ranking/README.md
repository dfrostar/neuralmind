# Prompt hook test ranking: hermes-agent, held out

**Offline replays only, no agent runs, and not a product claim.** What the
`UserPromptSubmit` hook's block lists, scored against each task's real fix,
for three versions of how it ranks test files
([v4.23.0 release notes](../../../docs/releases/RELEASE_NOTES_v4.23.0.md)).
Whether an agent does anything differently with the new block is not
measured.

## Why

On the [hermes-agent](https://github.com/NousResearch/hermes-agent) task-outcome
screen's 5 tasks, 18 of the 32 files the block listed were tests. The block was
meant to put tests after the code they test unless the prompt is about tests,
but any test word counted, and every benchmark prompt has one: the harness
tells the agent how to run the tests and not to change them. Two changes
followed, both made on those 5 tasks, which therefore can't show they work:

- **#731 (on `main`):** test files come after the code unless the prompt
  *names* a test (a test function or class, or a test file's path); a prompt
  that only mentions tests keeps one slot for its best test file; the excerpt
  is from a source file whenever one is listed.
- **This change, on top:** a matched test file credits the code file it tests,
  found by name (`tests/agent/test_x.py` → `agent/x.py`), with its best score
  (`TESTED_CODE_CREDIT = 1.0`).

This folder is the check on new tasks.

## Method

- **Held out:** 12 hermes-agent bug-fix tasks.
  - 3 are screen candidates the screen didn't select: `e9eba2188a`,
    `24b4f90e97`, `3c53adbc1e`.
  - 9 come from continuing the screen's seeded walk (seed 20261025,
    hermes-agent pinned at `710fa8a`) from position 12 to 24. Of those 13
    positions, 12 qualified and 1 didn't.
  - 3 qualifying tasks were excluded because their tests check names the fix
    introduces, which no fix written from the symptom could produce
    ([exclusions.json](heldout/exclusions.json)).
  - A separate agent wrote the prompts from each fix's tests and diff
    ([tasks.json](heldout/tasks.json)), without seeing any ranking.
  - Every test run during the walk kept the Hermes launcher guard on
    `~/.hermes/hermes-agent/.hermes/bin`. The launchers were unchanged
    afterwards, and `hermes --version` still worked. Nothing here runs
    hermes-agent code.
- **Versions:**
  - `v4.22.1`: `main` at `472f1fa1`.
  - `main-731`: `main` at `1fc17ea9`, with #731.
  - `this-pr`: #731 plus the credit.

  All three report `neuralmind 4.22.1`, the version on `main` at the time.
- **Same indexes for all:** each task's index was built once with v4.22.1, and
  every hook call ran on a fresh APFS clone of it, so the versions differ only
  in ranking.
- **Scored by `evals/task_outcome/replay.py`'s `score()`:**
  - *named*: a file the fix changed is listed.
  - *first*: it's listed first.
  - *excerpt on gold*: the quoted code is from such a file.

## Result

Held out, 12 tasks, through the real `neuralmind _hook prompt-submit`
([v4.22.1](heldout/v4.22.1/replay-results.json),
[main-731](heldout/main-731/replay-results.json),
[this-pr](heldout/this-pr/replay-results.json)):

| | v4.22.1 | #731 | #731 + credit |
|---|---|---|---|
| A file the fix changed is listed | 4 | 4 | 4 |
| …and listed first | 1 | 3 | 3 |
| Code quoted / from a changed file | 2 / 0 | 4 / 1 | 3 / 1 |
| Test files among the files listed | 33 of 82 | 16 of 83 | 14 of 84 |
| Median block size (characters) | 923 | 826 | 804 |

Turning the credit off and on in-process on cached search hits
([variants-heldout.json](variants-heldout.json)) gives the same counts as the
two hook replays.

The 5 screen tasks, both changes' tuning set
([dev/](dev/); the v4.22.1 row is the screen's own replay in #720):

| | v4.22.1 | #731 | #731 + credit |
|---|---|---|---|
| Listed | 2 | 2 | 3 |
| First | 1 | 2 | 3 |
| Code quoted / from a changed file | 3 / 1 | 1 / 1 | 1 / 1 |
| Tests listed | 18 of 32 | 6 of 35 | 6 of 35 |

The pilot's 20 tasks on NeuralMind's own repository, with the floors CI's
**Prompt-recall replay** job enforces ([pilot/](pilot/)). All three ran on the
same 20 indexes, built once with v4.22.1. A second v4.22.1 run on them matched
the first exactly, so the hook's own writes don't move the scores.

| Pilot, 20 tasks | v4.22.1 | #731 | #731 + credit | Floor |
|---|---|---|---|---|
| Listed | 17 | 17 | 17 | 15 |
| First | 10 | 10 | 11 | 9 |
| Code from a changed file / quoted | 7 / 9 | 7 / 9 | 7 / 8 | 70% |

What it shows, and what it doesn't:

- **#731 holds on new tasks.** Test files go behind the code, falling from 40%
  of the listed files to 19%, and the file to fix comes first on 3 tasks
  instead of 1.
- **The block names the file to fix no more often.** It's listed on 4 of 12
  under every version. Where it was missing, the prompts matched other code,
  not tests sitting in its place.
- **The credit adds little held out.**
  - It changed 3 of the 12 blocks and named no new changed file.
  - On one task the file it listed left no file 2:1 ahead, so an excerpt from
    the wrong file is no longer shown.
  - Its gain on the screen (one task) didn't carry over.
- **The samples are small.** 12 tasks from one repository is enough to see the
  order change, not to estimate its size.

## Before #731

This branch first had its own version of the narrower test rule, with a
different excerpt rule and no reserved test slot. It was replayed the same way
before #731 merged ([pre-731/](pre-731/)). The `variants-*.json` there compare
v4.22.1's rule, the narrower rule alone, and the narrower rule with the credit:

| Held out, 12 tasks | v4.22.1 | narrower rule | + credit |
|---|---|---|---|
| Listed / first | 4 / 1 | 4 / 3 | 4 / 3 |
| Code quoted / from a changed file | 2 / 0 | 2 / 1 | 2 / 1 |
| Tests listed | 33 of 82 | 8 of 83 | 6 of 84 |

That code was replaced by #731's when the branches merged. The script that
produced these numbers is in the branch's history (commit `2e470bc3`).

## Reproduce

The script needs the task-outcome harness from #719/#720 (see its docstring)
and a hermes-agent clone at `~/nm-bench/hermes-agent`. A *shim* is a directory
with a `neuralmind` executable that runs the version under test, for example
`PYTHONPATH=<checkout> python -P -m neuralmind "$@"`. The `-P` matters: inside
a NeuralMind checkout, as on the pilot's tasks, `-m` would otherwise import
the checkout's own copy of `neuralmind`.

```bash
python replay_heldout.py build heldout <shim-v4.22.1> <task-id>...
python replay_heldout.py prepare heldout
python replay_heldout.py hook heldout <shim> <label>    # once per version
python replay_heldout.py capture heldout
python replay_heldout.py variants heldout
```

Building the 12 indexes took 20–30 minutes each on one M-series Mac. Each
hermes-agent index is about 300,000 graph nodes.
