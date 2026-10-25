# Task-outcome screen on hermes-agent — pre-registration

**Status:** pre-registered, tasks drawn; not yet run · **Harness:** `evals/task_outcome/` (profile `hermes-agent`) · **Study files:** `evals/task_outcome/studies/hermes-agent-screen/`

## Why a screen, and why here

The [task-outcome pilot](TASK-OUTCOME-BENCHMARK-SPEC.md) found no cost
difference on 20 bug fixes from NeuralMind's own repository, and an
exploratory rerun with v4.21.0 found the same. On those tasks the agent
found the file to fix in about four searches with or without help, which left
little to save.

The case for NeuralMind is a large codebase the agent doesn't know.
NousResearch/hermes-agent (MIT) is one: about a million lines of non-test
Python. A full study there costs about 180 agent runs. This screen runs 5
tasks first, and its only job is to decide whether that full study is worth
running. **It is not a product claim either way.** Five tasks can show a large
effect or no effect; they can't establish one.

## Question

On 5 real hermes-agent bug fixes, does the same coding agent cost less per
task with NeuralMind than without it, without solving fewer?

## Tasks

**Repository:** NousResearch/hermes-agent, `origin/main`, pinned at the commit
in the change log.

**Metadata gates** (the pilot's, with this repository's layout, from
`profiles.py`, profile `hermes-agent`):
- the subject starts with `fix`;
- committed on or after 2026-09-15 (committer date, UTC), after the pinned
  model's training data could include it;
- it changes 1–3 `.py` files outside `tests/`, `tests-js/`, `website/`,
  `scripts/` and `evals/`, and at least one `tests/**/test_*.py`;
- not a merge.

**Draw.** The commits that pass the gates are sorted by hash and shuffled with
`random.Random(20261025)`. They're walked in that order, and each is
harvested (`harvest.harvest_one`): its tests run on the parent with the fix's
tests laid over, and on the fix. It qualifies with at least one FAIL_TO_PASS
test. The walk stops at 12 qualified candidates and records every commit's
outcome, test counts included, in `walk.jsonl`. The pilot harvested every
candidate and then shuffled; here there are thousands, so the order comes
first. Both give every candidate the same chance.

**Exclusions** (the pilot's reasons, written to `exclusions.json` before any
run, by a separate agent session from each fix's message, diff and tests):
- (a) the FAIL_TO_PASS tests check documentation, wording or test
  infrastructure rather than behaviour;
- (b) the symptom can't be stated without naming the file or function to
  change;
- (c) the FAIL_TO_PASS tests depend on a name, parameter, constant or file
  format the fix itself introduces, or on an internal input no user-facing
  path produces.

`select_tasks.py --seed 20261025` sorts the 12 by hash, shuffles them with
the same seed, walks that order, skips exclusions, re-harvests each and
rejects it as flaky if the oracle changes, and keeps the first 5.

**Prompts.** One per task, the symptom a user would report, written by the
same separate session before any run. `select_tasks.py` refuses a prompt that
names a gold file. Both arms get the same prompt and suffix, naming the
repository as `hermes-agent`.

## Arms

As in the pilot (`run.py`):

| | `baseline` | `neuralmind` |
|---|---|---|
| Agent | Claude Code headless (`claude -p`) | same |
| Settings | project only, `--strict-mcp-config` | same, plus `neuralmind-mcp` |
| Hooks | none, `NEURALMIND_BYPASS=1` | from `neuralmind install-hooks` |
| Index | none | `neuralmind build`, once per task (`--index-cache`), restored unused into every run |
| Budget cap | `--max-budget-usd 3` | same |
| Timeout | 1800 s | same |

The cap is $3, not the pilot's $2: on a repository this size a fix can take
more turns, and a cap that binds in one arm more often than the other would
decide the result by itself.

**Hermes isolation.** Every test run and agent run gets a `HERMES_HOME` inside
its workspace, and `--guard ~/.hermes/hermes-agent/.hermes/bin` checksums
the host's real Hermes launchers around every run: a change stops the screen
with nothing recorded.

**Runs.** 5 tasks × 2 arms × 3 seeds = 30, in the seeded interleaved order
(`--order-seed 20261025`).

**Pinned:** model `claude-sonnet-5-5`, Claude Code 2.1.309, NeuralMind 4.21.0
(PyPI), test environment Python 3.14.7 with hermes-agent's pinned
dependencies at the pinned commit plus `pyyaml` (older commits in the window
import it; current `pyproject.toml` no longer lists it).

## Endpoints

The pilot's (`analyze.py`): per-task relative cost change (median, 95%
bootstrap interval), the one-sided Wilcoxon test, solved tasks with exact
McNemar; and, reported, NeuralMind tool calls, explore calls before the first
edit, turns, and cost per solved task.

## Decision rule

The screen recommends the full study only if **both** hold:
1. the median per-task cost change with NeuralMind is −10% or better;
2. NeuralMind's arm solves no fewer tasks than the baseline.

Otherwise it recommends stopping. With 5 tasks the Wilcoxon test can reach
p = 0.031 only if all five tasks get cheaper, so p isn't part of the rule;
it's reported.

## Publication

`bench/task_outcome/hermes-agent-screen/`: `runs.jsonl` and the analyzer's
report, committed whatever the result, labelled exploratory. Transcripts stay
out of git.

## Threats to validity

- **Five tasks.** Large effects only; the full study exists for the rest.
- **One agent and model,** cold index, cost as Claude Code's estimate at API
  prices; on a subscription login no money changes hands.
- **Popular repository.** The cutoff keeps fixes after the model's training
  data, but older code in the same files may be familiar to it.
- **Dependency drift.** One environment serves every task's commit; a task
  whose tests can't run in it fails to qualify and is recorded in
  `walk.jsonl`, which biases the draw toward commits whose code matches it.

## Change log

- 2026-10-25 — design, gates, seed, endpoints and decision rule written before
  any agent run.
- 2026-10-25 — draw complete, before any agent run:
  - hermes-agent pinned at `710fa8a073f9a8136e10749b083a16779341faef`;
    6,568 commits pass the metadata gates.
  - The first walk ran its tests under Python 3.12, where hermes-agent's core
    dependencies (all marked `python_version >= '3.14'`) don't install, so
    every test errored. It was stopped and its records discarded; the walk
    was rerun from the start under Python 3.14.7, with `pyyaml` added after a
    check showed a window commit importing it. The walk now records each
    commit's test counts.
  - The rerun walked 12 commits; all 12 qualified (`walk.jsonl`).
  - A separate agent session, reading each fix's message, diff and tests with
    git only, wrote 8 prompts and excluded 4, all under (c): tests that pin
    wording, a constant, a parameter or a setting the fix introduces
    (`exclusions.json`).
  - `select_tasks.py` accepted 5, none flaky: `28e6496a5e`, `167a2d00ed`,
    `0968fa2631`, `652e4b9194`, `859b999db5` (`tasks.json`).
  - One prompt (`0968fa2631`) quotes the provider's error message, which
    contains the string the fix matches on. A real report would quote it, so
    it stays; that task is easier to locate than the others.
