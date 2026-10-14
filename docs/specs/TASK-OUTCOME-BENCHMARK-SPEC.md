# Task-outcome benchmark — pre-registration

**Status:** pre-registered — design, 20 pilot tasks, prompts and pinned versions committed; not yet run · **Harness:** `evals/task_outcome/`

Every number NeuralMind publishes today measures retrieval: whether the right
file reaches the agent's context, and at what token cost. None measures what a
company pays for: whether an agent finishes real work for less, without
finishing less of it. The headline ratio (51–242× fewer tokens than pasting
every source file) uses a baseline no agent follows. Agents search and read a
few files. So the saving that matters is the exploration an agent skips, and it
can be zero, or negative when NeuralMind's context is added to a question the
agent would have answered in one search.

This document fixes, before any agent runs, what is measured, how, and what
result supports which sentence. It is committed before the first run, and any
change after that is recorded in the change log at the end with its reason.

## Question

Given the same real bug-fix tasks, does the same coding agent cost less per
task with NeuralMind than without it, without solving fewer of them?

## Design

**Tasks.** Bug fixes from this repository's history, each turned into a task
by `evals/task_outcome/harvest.py`:

- The agent starts from the fix's parent commit, exported as a one-commit
  repository, so the later history and the fix can't be read.
- The oracle is the fix's own tests, applied only after the agent stops:
  - FAIL_TO_PASS: tests that fail before the fix and pass after it;
  - PASS_TO_PASS: tests that pass both before and after.
- A task is solved when all of them pass.

**Selection rule.** A commit becomes a candidate task when all of these hold:
- its subject starts with `fix`;
- it was committed on or after 2026-07-01;
- it changes 1–3 Python files under `neuralmind/` and at least one `tests/test_*.py`;
- the harvester finds at least one FAIL_TO_PASS test.

`evals/task_outcome/select_tasks.py` then draws the pilot's tasks:
1. It shuffles the candidates, sorted by commit, with `random.Random(20261014)`.
2. It walks them in that order, skipping any excluded candidate. Each
   exclusion and its reason is recorded in `exclusions.json` before the walk.
   The reasons that count:
   - the failing tests check documentation, wording or test infrastructure
     rather than the program's behaviour;
   - the symptom can't be stated without naming the file or function to change.
   - the FAIL_TO_PASS tests depend on something a symptom can't reach: a
     name, parameter, constant or file format the fix itself introduces, or
     an internal input no user-facing path produces. A correct fix written
     from the symptom would still fail them, in both arms. SWE-bench Verified
     drops tasks for the same reason.
3. It harvests every other candidate a second time, and rejects it as flaky if
   the oracle comes out different.
4. It keeps the first 20 that remain.

**Prompts.** One per task, written from the commit's description before any
agent runs:
- it states the symptom a user would report, and never names the file,
  function or test to change;
- `select_tasks.py` refuses any prompt that names a gold file;
- the same prompt and suffix (`run.PROMPT`) go to both arms.

**Arms.** Identical except for NeuralMind:

| | `baseline` | `neuralmind` |
|---|---|---|
| Agent | Claude Code headless (`claude -p`) | same |
| Settings loaded | project only (`--setting-sources project`) | same |
| MCP servers | none (`--strict-mcp-config`) | `neuralmind-mcp` only |
| Hooks | none, `NEURALMIND_BYPASS=1` | from `neuralmind install-hooks` |
| Index | none | `neuralmind build` before the clock starts |
| Tools | the allowlist in `run.BASE_TOOLS` | same, plus `mcp__neuralmind` |
| Budget cap | `--max-budget-usd 2` | same |

The agent is not told to use NeuralMind; it gets what a user gets after
install. Runs are interleaved in a seeded random order so neither arm runs
first in bulk. Each (task, arm) pair runs 3 times.

**Pinned versions.** The model, Claude Code version and NeuralMind version are
fixed for a run and recorded in it. Pilot: NeuralMind 4.15.1. The model and
Claude Code version are named in the change log when the pilot starts.

## Endpoints

The unit of analysis is the task: each arm's runs on a task are averaged.

1. **Primary, cost.** Per task, `d = mean cost with NeuralMind − mean cost
   without`. One-sided Wilcoxon signed-rank test, exact, that `d` is centred
   below zero. Cost is Claude Code's reported `total_cost_usd`.
2. **Co-primary, solve rate.** A task is solved by an arm when most of its
   seeds solve it. Exact McNemar test on the tasks only one arm solves.
3. **Effect size.** Median per-task relative cost change, with a 95%
   bootstrap interval over tasks (10,000 resamples, seed 20261014).
4. **Secondary**, reported, not tested for the claim:
   - cost per solved task in each arm;
   - tool calls before the first edit (the exploration NeuralMind is meant to
     shorten);
   - turns and wall-clock time;
   - whether the agent's edit touched a gold file.

**Missing data.**
- **A run that hits the harness timeout** has no reported cost. It counts as
  unsolved, at its arm's budget cap: the worst case for that arm, so a failure
  can never make an arm look cheaper.
- **A run where Claude Code exits without a result** (authentication, model or
  CLI failure) is a harness failure, not an outcome. It is not recorded and is
  retried.
- **Any other gap means no verdict.** The analyzer refuses unless every (task,
  arm) holds the same complete set of seeds.
- **Versions are recorded on every run.** That's the Claude Code and NeuralMind
  version, and a resumed run refuses to mix them.

## Decision rule

The sentence **"NeuralMind lowers a coding agent's cost per task without
lowering its solve rate"** is supported only when all three hold:

1. the Wilcoxon p < 0.05;
2. the upper bound of the 95% interval on the median relative change is below zero;
3. NeuralMind's arm solves at least as many tasks as the baseline, minus one
   (the non-inferiority margin).

Otherwise the result is reported as what it is: no difference shown, or a
loss. `evals/task_outcome/analyze.py` applies this rule mechanically.

**The pilot is exploratory.** Twenty tasks can show a large effect but not
rule out a small one. The pilot's result is published labelled "pilot", with
its interval, and is not quoted as a product claim. Its spread sets the size
of the confirmatory run. That run needs enough tasks for 80% power, at
α = 0.05 one-sided, to detect a 15% median cost reduction:
`n ≈ ((1.645 + 0.842) · σ / 0.15)² / 0.955`, where σ is the pilot's standard
deviation of per-task relative change. The confirmatory run uses new tasks,
drawn by the same rule, that the pilot didn't use.

## Publication

- `bench/task_outcome/<run>/runs.jsonl` (one line per run) and the analyzer's
  report are committed, whatever the result.
- A result quoted on the site gets a `site/claims.json` entry naming this
  spec and the command that reproduces it.
- A null or negative result is published with the same prominence as a
  positive one.

## Threats to validity, stated up front

- **One repository, NeuralMind's own.** Its `CLAUDE.md` describes NeuralMind,
  and both arms read it. Results may not transfer to other codebases; a second
  repository is the next step.
- **Cold start only.** Each run builds a fresh index, so the synapse layer has
  learned nothing. This measures retrieval and hooks, not learning over time.
  The memory track (sequential tasks in one repository, state carried over)
  is a separate run.
- **The prompts are written by the project's author.** This is mitigated by
  four things:
  - prompts are written and committed before any run;
  - a check rejects any prompt that names a gold file;
  - both arms get the same prompt;
  - prompts describe symptoms, not locations.
- **Cost is Claude Code's estimate at API prices.** On a subscription login no
  money changes hands per run, so it measures relative usage, not a bill.
- **Contamination.** Tasks are taken from commits after 2026-07-01. If the
  pinned model's training data could include them, the run is flagged in the
  change log.
- **Small n.** See the decision rule: the pilot sizes the confirmatory run; it
  doesn't stand in for it.

## Change log

- 2026-10-14 — design, endpoints and decision rule pre-registered. Model for the pilot: Sonnet 5.5. Tasks, prompts and the Claude Code version follow in a separate commit, before any run.
- 2026-10-14 — before any run, after review on #665:
  - the missing-data rule above;
  - the harvester enforces the eligibility gates itself;
  - both arms run with a `PATH` cleaned of any host NeuralMind install;
  - turns and wall-clock time are added to the report.
- 2026-10-14 — before any run, while drawing tasks:
  - Added exclusion reason (c). Writing the prompts showed that 12 of the
    first 38 candidates have tests that import a name the fix created, so no
    symptom-only fix could pass them. That was first filed under (b) and is
    now recorded under its own reason.
  - Prompts and exclusions were written by a separate agent session from
    each fix's message, diff and tests. They are committed here before any
    run.
- 2026-10-14 — task draw complete, before any run:
  - `select_tasks.py` walked the seeded order and recorded 14 exclusions
    (2 under (a), 12 under (c)).
  - It accepted 20 tasks, and every one gave the same oracle on a second
    harvest, so none was rejected as flaky.
  - Pinned for the pilot: model `claude-sonnet-5-5`, Claude Code 2.1.287 and
    NeuralMind 4.15.1.
  - A smoke test of 4 runs comes first: the first two tasks in `tasks.json`,
    one seed per arm. It checks the harness end to end. Its runs go to
    `bench/task_outcome/smoke/` and are never pooled with the pilot.
