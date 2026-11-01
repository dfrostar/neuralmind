# Task-outcome benchmark — pre-registration

**Status:** pre-registered; pilot run 2026-10-20 (claim not supported, see the change log); confirmatory run not started · **Harness:** `evals/task_outcome/`

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
- Transcripts stay out of git: agents read the repo's test files, and those
  hold fake credentials that push protection blocks. Each run records its
  transcript's SHA-256, so an archive published separately can be checked
  against `runs.jsonl`.
- Every `neuralmind`-arm run records whether NeuralMind's hooks ran inside
  the session (`hook_prompts_recorded`, `hook_edits_recorded`). That's the
  manipulation check: a run where they didn't is a harness failure, not
  evidence.
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
- 2026-10-20 — before any pilot run was kept:
  - The first pilot attempt ran with a logged-out Claude Code. It printed
    "Not logged in" as a `result` event with subtype "success", so the
    harness recorded two runs as unsolved at $0. That breaks the missing-data
    rule above.
  - Those two records were deleted. The harness now treats a `result` event
    that ends on an API error (`terminal_reason` "api_error") as a harness
    failure, the same as no `result` event: nothing is recorded and the run
    is retried.
  - No design, endpoint or decision rule changed.
- 2026-10-20 — pilot run, all 120 runs recorded in `bench/task_outcome/pilot/`:
  - Pinned versions as above. The test venv ran Python 3.12.14 with the
    project's dependencies and the package uninstalled.
  - One run ended on a transient API error. The harness recorded nothing for
    it and stopped, and the run was resumed from that run, as the
    missing-data rule says.
  - Every `neuralmind`-arm run recorded hook activity (prompts and edits,
    60 of 60), so none was dropped by the manipulation check.
  - Result, labelled "pilot": claim not supported. Median per-task cost
    change +0.0% (95% CI −5.2% to +8.6%), Wilcoxon p = 0.66, 18 of 20 tasks
    solved in each arm. The interval excludes the 15% reduction the
    confirmatory run was to be powered for.
- 2026-10-29 — a second agent, before any of its runs: Hermes-Agent on a local
  model. A separate, exploratory study on the same 20 tasks; its runs are never
  pooled with the Claude Code pilot's.
  - `run.py --agent hermes` runs `hermes chat -Q --format stream-json` in each
    workspace. Pinned: Hermes Agent v0.22.5, model `gpt-oss:20b-64k` (Ollama
    digest `ffdda7cf7e79`) on a 16 GB RTX 5000 Ada, NeuralMind 4.23.1. A run
    whose Hermes session records any other model is a harness failure: Hermes
    falls back to another provider when its own model fails.
  - Isolation, for both arms: the session gets only Hermes's `file` and
    `terminal` toolsets and no MCP server (`-t file,terminal,no_mcp`), and no
    memory provider, context files or preloaded skills (`--ignore-rules`), so
    one run can't recall another through mem0 or session search.
  - What NeuralMind contributes changes. With no MCP server in either arm, the
    `neuralmind` arm gets NeuralMind only through the Hermes plugin (a block
    on every prompt, the session recap, edit learning), which serves a
    session's directory once it has an index. The `baseline` arm's workspace
    has no index, so the plugin does nothing there. `neuralmind
    install-hooks` isn't run: those are Claude Code's hooks. The manipulation
    check is unchanged.
  - The primary endpoint can't be dollars: a local model costs nothing per
    call. These runs record Hermes's reported tokens (`total_tokens`, input
    plus output) and wall-clock time. Hermes has no budget cap, so runs are
    bounded by `--max-turns` and the harness timeout instead.
  - A smoke test of 4 runs comes first, as for the pilot: the first two tasks
    in `tasks.json`, one seed per arm, in `bench/task_outcome/hermes-smoke/`.
    It checks the harness and measures how long a run takes. The full run's
    endpoint (tokens or time), its timeout, and how a timed-out run is scored
    are fixed in this log after the smoke and before the full run.
- 2026-10-29 — Hermes smoke test, 4 runs in `bench/task_outcome/hermes-smoke/`,
  `--max-turns 60`, timeout 1800 s. Not analysed, not pooled:
  - The harness worked end to end: every session ran on `gpt-oss:20b-64k`,
    every `neuralmind`-arm run recorded the plugin's prompt hook, and the
    judge ran the hidden tests.
  - The turn cap decided most runs. All 4 used 59–60 model calls, 1.6–2.1M
    tokens and 3–20 minutes; three ended "out of steps" or with an answer
    and no edit. One run solved its task: `1015eb8b95`, baseline arm.
  - On `1015eb8b95` the block named no file the fix changed (as the offline
    replay records) and quoted another file's code; the `neuralmind`-arm
    agent never edited. On `fa72224183` the block named both fixed files
    first; neither arm solved it, as neither Claude Code arm did in the
    pilot. One run per cell: no inference is drawn from either.
- 2026-10-29 — the Hermes run's design, fixed after the smoke test and before
  any of its runs:
  - **Bounds.** `--max-turns 120` (the smoke's 60 decided most runs) and a
    3600 s timeout per run. A run that hits the timeout counts as unsolved,
    with the tokens its Hermes session had used.
  - **Nothing runs on while the tests judge.** The agent's commands run in
    the Hermes gateway, which keeps a turn going when its client exits and
    starts a new one when a background command the agent left finishes (the
    smoke saw three, all before its run ended). After every run the harness
    stops any process working in the workspace and waits until Hermes has no
    turn queued or running for the session; a session still busy an hour
    later stops the benchmark as a harness failure.
  - **Primary endpoint: solve rate.** A small model's tokens mostly record how
    long it searched. A task is solved by an arm when most of its seeds solve
    it; exact one-sided McNemar test on the tasks only one arm solves. "With
    NeuralMind, gpt-oss solves more of these tasks" is supported only if
    p < 0.05. Secondary, reported but not tested: tokens (per-task relative
    change with its bootstrap interval), wall-clock time, turns, tool calls
    before the first edit, whether a gold file was edited, and solved runs per
    arm.
  - **Two stages.** Stage 1 is seed 0 for both arms, 40 runs. Then one number
    decides, pooled over both arms so it can't favour either: if fewer than 5
    of the 40 runs solve their task, the run stops there and is published as
    "these tasks are too hard for this model to tell the arms apart". Otherwise
    stage 2 runs seeds 1 and 2 (80 runs) with the same pinned versions, and the
    analysis code for this variant is committed before stage 2's results are
    read. The preflight against ai-9970's frozen environment passes before
    each stage. The result is labelled "pilot" and published whatever it shows.
- 2026-10-29 — the Hermes variant's analysis code (`analyze_hermes` and
  `stage_one` in `evals/task_outcome/analyze.py`), committed while stage 1
  was running, after 17 of its 40 runs and before any stage 2 run. It
  implements the endpoints above as written, and `analyze` picks them for any
  run set whose `agent` is `hermes`, refusing a mix of agents:
  - **Tokens are `input_tokens + output_tokens`.** Not the record's
    `total_tokens`: Hermes reports 0 there for a session that ends in an
    error, though it records that session's input and output. Stage 1's run
    13 (`404ccad4a9`, `neuralmind` arm) ended that way and logged
    `tokens=0` with 3.71M tokens used.
  - The one-sided McNemar p-value is the binomial tail of NeuralMind-only
    tasks among the discordant ones. A timed-out run never counts as solved.
- 2026-10-29 — the Hermes variant's tokens and minutes are the whole
  session's, fixed while stage 1 was running (after 24 of its 40 runs) and
  before any stage 2 run. Checking the records against Hermes's `state.db`
  found they mix two scales:
  - A run's tokens come from the Hermes client's `result` event, which counts
    every prompt token, cache reads included, for the client's own turn. When
    a background command the agent started finishes, Hermes wakes the session
    for more turns, and the tests judge the workspace after those. Stage 1's
    run 22 made 95 more model calls that way; its record holds about half of
    its session's 7.2M tokens.
  - A run cut off by the timeout has no `result` event. The runner took the
    session's `input_tokens`, which leave cache reads out: run 18's record
    says 171k tokens where its session used 2.5M. It has no duration either.
  - `evals/task_outcome/hermes_sessions.py` reads each run's session row,
    read-only, into `sessions.json` beside `runs.jsonl`: prompt tokens
    (uncached input plus cache reads and writes), output tokens, API calls,
    and minutes from the session's start to its last activity. `analyze`
    takes tokens and minutes from it, and the report counts any run without
    one. On stage 1's first 24 runs it equals the record on 21. The other
    three are runs 15 (one call after its client returned), 18 and 22.
  - The harness is unchanged, so stage 2 runs exactly as stage 1 did. Turns
    were already the session's (`api_call_count`). Tool counts, and calls
    before the first edit, still come from the client's turn.
  - `--max-turns 120` caps one Hermes turn, not a run: a wake-up starts
    another, so run 22 made 215 model calls.
- 2026-10-29 — the memory track, pre-registered before any of its runs (the
  Hermes run's stage 1 was at 27 of its 40). Exploratory, labelled "pilot",
  published whatever it shows, and never pooled with another run:
  - **Question.** Does what NeuralMind learns from use in one repository
    (its synapse store and session recaps), carried from one task to the
    next, let the same agent solve more of the later tasks than it does from
    a fresh index?
  - **Fresh arm: the Hermes run's `neuralmind` arm,** 3 seeds per task, with
    no new runs. Every task's base commit holds a team-memory bundle
    (`.neuralmind-team-memory.json`) and all 20 are empty, so those runs start
    with nothing learned. The memory track runs on the same frozen ai-9970,
    with the same pins (NeuralMind 4.23.1, Hermes v0.22.5, `gpt-oss:20b-64k`),
    isolation, `--max-turns 120` and 3600 s timeout, and a timed-out run is
    unsolved. ai-9970 isn't upgraded until the track ends. The runner gains
    an option to carry state; a run without it is unchanged.
  - **Carried arm: 3 chains, 60 new runs.** Each chain runs the 20 tasks
    once, starting from an empty store, in order of the fix commit's author
    date. On these 20 that order also puts every fix commit after its
    ancestors (checked), so no task learns from a later commit. Commit dates
    would tie four of them. The order: `0db7d2c97d 8592aa7ab7 366858e431
    b06a3ee6af e6fa9e4b80 1015eb8b95 4325e063e1 4e01f40e6a e303c7a287
    21bd34dfc4 108b1ee013 2a6448552b 404ccad4a9 24ee2924b9 53b9813363
    b4c9886021 8c0411129c 454904f4bb 7a1c90dcab fa72224183`.
    - Before each task after the first, the runner copies the previous
      task's `.neuralmind/synapses.db` (with its `-wal` and `-shm` files) and
      `.neuralmind/recaps/` into the new workspace, then builds its index.
      Everything else is rebuilt.
    - The chains run interleaved by position (chain A's first task, B's, C's,
      then A's second), so a position's three runs are close in time.
    - A chain's first task starts with nothing learned, as in the fresh arm.
  - **Primary endpoint: solve rate,** as in the Hermes run. A task counts as
    solved by an arm when most of its 3 runs solve it (seeds for the fresh
    arm, chains for the carried arm); exact one-sided McNemar test on the
    tasks only one arm solves. "Carrying NeuralMind's learned state lets the
    model solve more of these tasks" is supported only if p < 0.05. The
    smallest result that clears it is 5 tasks only the carried arm solves and
    none only the fresh arm solves, so a null result is likely even if the
    effect is real but modest.
  - **The mechanism, reported but not tested.** Hermes keeps the block
    NeuralMind adds to the prompt in the session's first user message
    (`api_content` in `state.db`), so both arms' blocks are read back
    afterwards, read-only. Per task, carried against fresh: does the block
    name a gold file, and is the first file it names one? This shows whether
    carried state reaches the agent at all, apart from what the model does
    with it.
  - **A prediction, falsifiable.** Help shows on the 12 tasks with a gold file
    that a task earlier in the order also changed ("repeats"), and there's no
    harm on the other 8. Held if the carried arm solves at least as many of
    the 12 as the fresh arm, and no more than one fewer of the 8; reported as
    held or not held, not tested. The repeats: `8592aa7ab7 4325e063e1
    4e01f40e6a e303c7a287 21bd34dfc4 108b1ee013 2a6448552b 24ee2924b9
    b4c9886021 8c0411129c 454904f4bb fa72224183`. The store learns from what
    the agent read and edited, not from the gold files, so an earlier task
    the agent didn't solve can teach the chain a wrong file.
  - **Also reported:** whole-session tokens and minutes (`hermes_sessions`),
    turns, tool calls before the first edit, runs that edited a gold file,
    solved runs per arm, and the carried arm's solve share minus the fresh
    arm's at each position in the order.
  - **Carry-over check, per carried run:** how many learned edges the run
    starts with, and how many of them have both ends in its new graph. Node
    ids are file paths plus symbol names, so an edge should survive a rebuild
    while both names do.
  - **Order of work.**
    1. The Hermes run finishes. The memory track runs only if all 120 of
       its runs complete, as its `neuralmind` arm is the fresh arm.
    2. A smoke test, not analysed or pooled: one 2-task chain, `4e01f40e6a`
       then `e303c7a287`, which both fix `secret_scan.py`. It checks that the
       second run starts with learned edges and that its block differs from
       the first run's.
    3. The 60 runs. Their analysis code is committed before their results
       are read.
  - **Threats, stated up front.**
    - Historical control: the fresh runs are days older than the carried
      ones. The frozen machine is what makes them comparable, and the
      preflight stops the track on any change.
    - Compressed time: a chain's runs are about 25 minutes apart, where real
      use spans days, and the store's decay runs on the wall clock. Reported;
      the clock isn't faked.
    - Path dependence: one early run can teach a chain the wrong files. The
      3 chains show the spread.
    - One repository, 20 tasks, 3 chains: exploratory.
- 2026-10-29 — the Hermes run's stage 1 is complete (40 runs, seed 0, from
  03:08 to 17:28 UTC), and stage 2 has started. Only the pooled count below
  was read to decide; the arms aren't compared until stage 2 ends:
  - **21 of the 40 runs solved their task, pooled over both arms.** That is
    at least 5, so stage 2 runs. A chained script counted it with the
    analysis's own rule and started stage 2 at 17:28 UTC, after the preflight
    matched ai-9970's frozen environment.
  - **One run counts as unsolved though the judge passed it.** Run 18
    (`7a1c90dcab`) hit the 3600 s timeout, and its workspace then passed the
    hidden tests, so its record says `solved: true`. As fixed above, a
    timed-out run is unsolved; `analyze` scores it that way, which is why the
    records hold 22 solves.
  - **The turn cap ended 19 runs,** at 101–121 model calls in the session.
    Hermes reports these as an error, and 7 of them still solved their task
    from the edits they made before it. Two sessions (runs 15 and 22) went
    past 120 calls because of wake-up turns, as described above.
  - **Every run is accounted for.** All 40 sessions ran on `gpt-oss:20b-64k`
    with Hermes v0.22.5 and NeuralMind 4.23.1 (tool and plugin), and all 40
    are in `state.db`, so `sessions.json` covers every run. Its tokens match
    the record on 37; the other three are runs 15, 18 and 22, as expected.
    No run left a background process for the harness to stop; the longest
    wait for Hermes to go idle was 1,113 s.
  - The agent's `pytest` runs can change directory into pytest's temporary
    directories under `~/.hermes/cache/scratch/`, where the harness's cleanup,
    which looks for processes working in the workspace, doesn't see them.
    Checks every 10–20 minutes found none still running into a later run.
    The harness is left as it is until stage 2 ends, so every run is measured
    the same way.
- 2026-10-30 — the Hermes run is complete, all 120 runs recorded in
  `bench/task_outcome/hermes-pilot/` (stage 2's 80 ran from 2026-10-29 17:28
  to 2026-10-30 18:48 UTC). `report.txt` there is `analyze`'s output:
  - **Result, labelled "pilot": claim not supported.** With NeuralMind,
    gpt-oss solved 10 of the 20 tasks (most of a task's 3 seeds), and 8
    without. The two tasks only one arm solved both went to NeuralMind:
    `e303c7a287`, solved by 3 of 3 seeds with it and 0 without, and
    `53b9813363`, 3 and 1. One-sided McNemar p = 0.25. That is the lowest p
    two discordant tasks can give; p < 0.05 needs at least 5, all one way.
  - **Solved runs: 29 of 60 with NeuralMind, 26 of 60 without.** Four tasks
    were solved by one `baseline` seed and no `neuralmind` seed
    (`4325e063e1`, `4e01f40e6a`, `24ee2924b9`, `366858e431`), so by neither
    arm under the majority rule.
  - **Secondary endpoints, reported, not tested, show no difference.**
    Median whole-session tokens per task 3.02M without NeuralMind and 3.06M
    with; the per-task change is −2.3% (95% CI −20.0% to +19.4%). Median
    minutes per task 18.4 and 17.9, turns 91.3 and 88.3, tool calls before
    the first edit 31.2 and 30.2; runs that edited a gold file 50 and 49.
    All three runs that hit the timeout were in the `baseline` arm, stage 1's
    run 18 among them.
  - **No run was a harness failure.** All 120 sessions in `state.db` ran on
    `gpt-oss:20b-64k` at the local Ollama endpoint, with Hermes's fallback
    never active, on Hermes v0.22.5 and NeuralMind 4.23.1. Every
    `neuralmind`-arm run recorded the plugin's prompt hook (60 of 60) and no
    `baseline` run did, so the manipulation check drops nothing.
  - **How the runs ended,** both stages, arms pooled: 57 with an answer (37
    solved), 54 at the turn cap (15 solved by the edits they made first), 5
    with the model's output truncated on every retry (2 solved), 1 on an
    invalid tool call (solved), and 3 at the timeout. Hermes reports all but
    the answers and the timeouts as errors; they are the model's outcomes,
    not the harness's. Stage 1's entry counted run 13 among 19 runs the turn
    cap ended; it ended on a truncated output at 101 calls, so the cap ended
    18 there.
  - **Whole-session accounting.** `sessions.json` covers all 120 runs, and
    its tokens match the record on 112. The other eight are the three
    timeouts and five runs Hermes woke up after their client returned
    (stage 1's runs 15 and 22 among them). Five sessions went past 120 calls
    through wake-ups, the most 237. The harness stopped 22 background
    processes over the 120 runs.
  - **ai-9970 changed once during stage 2.** Its Hermes had 12 cron jobs
    active, some calling the same model, one of them every 30 minutes. They
    ran through stage 1 and stage 2's first 22 runs, were paused at the
    user's request at 02:56 UTC on 2026-10-30, during run 23, and were
    resumed after the last run. The preflight doesn't check them. Both arms
    ran on both sides of the pause (63 runs before it, 33 `baseline` and 30
    `neuralmind`; 57 after, 27 and 30), and the client's median time per run
    fell from 17.6 to 14.2 minutes after it. Minutes are the endpoint that
    can move; reported, not corrected.
  - All 120 runs completed, so the memory track can start, with its smoke
    test first, as its order of work says.
- 2026-10-30 — two harness fixes, from review of the Hermes run's results and
  before any memory-track run. Runs now record `harness_version` 2:
  - **Cleanup before judging.** The harness scanned for leftover processes
    once, before it waited for Hermes to go idle, and only by working
    directory. A turn running during that wait could start a command the scan
    never saw, and a test run that had changed into pytest's temporary
    directories escaped it too. Now it repeats scan and wait until a scan finds
    nothing and the session is already idle, at most five rounds, else the run
    is a harness failure. It also stops a process whose `PWD`, exported by the
    shell that started it and inherited by its children, is in the workspace.
  - **What that changed in the Hermes run,** checked against `state.db`, where
    Hermes notes each background command's end in the session: in 36 of the
    120 runs a command the agent started was still running when judging began,
    in 33 of them `pytest` over the whole suite. 30 outlived the judging and 6
    ended during it. The agent made no tool call while any run was judged. The
    36 are 19 `neuralmind` and 17 `baseline` runs, 18 solved and 18 not, and
    none of the 18 failed only on pass-to-pass tests, the likeliest trace of a
    second test run in the same workspace: each failed tests the fix had to
    make pass. The workspaces were deleted after judging, so they can't be
    judged again; the verdicts stand as recorded, with this caveat.
  - **The manipulation check stops the run.** A `neuralmind`-arm run whose
    workspace records no NeuralMind prompt is now a harness failure, as this
    spec says, where before it was recorded with zero counts. And the runner
    refuses a Hermes plugin pinned to a project, which would serve that project
    to every run instead of the run's workspace. Neither affected the Hermes
    run: the plugin wasn't pinned (`project` is null) and all 60 `neuralmind`
    runs recorded prompts.
  - **What it means for the memory track.** Its fresh arm is the Hermes run's
    `neuralmind` arm, run on harness 1; its carried runs will run on harness 2.
    Harness 2 stops commands harness 1 left running, and a stopped command
    wakes the session, so a carried run can get a turn before judging that a
    fresh run got only after. That is added to the track's threats, and
    whether to rerun its fresh arm on harness 2 is decided before any of its
    runs.
- 2026-10-30 — harness 3, a merge and nothing else. The other-repository
  harness (`--repo`/`--profile`, `--index-cache`, `--guard`, written for the
  hermes-agent screen) had also numbered itself 2, so the runner that has both
  records 3. For this study's runs it does what harness 2 above does: the
  `neuralmind` profile, no index cache and no guard change nothing. The memory
  track's carried runs will record 3, and "harness 2" in its threats means
  them. The runner refuses `--agent hermes` with a profile that gives each
  process its own `HERMES_HOME`, since that home would reach `hermes chat`.
- 2026-10-30 — the memory track's fresh arm, changed at the user's decision
  before any of the track's runs: it runs again, beside the carried arm,
  instead of reusing the Hermes run's `neuralmind` arm.
  - **Fresh arm: 60 new runs,** 3 per task, on harness 2, with the carried
    arm's pins, isolation, bounds and scoring. A fresh run builds its index in
    an empty workspace, as the Hermes run's `neuralmind` arm did, so the arms
    differ only in what is carried. The Hermes run's `neuralmind` arm isn't
    part of the comparison.
  - **Side by side.** At each position in the order, the three chains' runs
    of that task and its three fresh runs go in a seeded shuffle, so a
    position's six runs are close in time and each chain still runs in order.
    120 runs, about 32 hours at stage 2's pace after its cron pause.
  - **Threats.** Both arms now run on the same machine, harness and days, so
    the historical control is gone, and with it the harness difference from
    the entry above. The others stand.
  - **Unchanged:** the question, the chains and what they carry, the primary
    endpoint and its test (a task counts for an arm when most of its 3 runs
    solve it; exact one-sided McNemar, supported only if p < 0.05, so at
    least 5 tasks to none), the mechanism report, the prediction, the
    secondary endpoints, the carry-over check, and the smoke test first.
  - **The harness** (`run.py --track memory`). Records hold `condition`
    (`carried` or `fresh`), `position`, and the replicate in `seed` (a
    carried run's chain).
    - Every Hermes run now records the block NeuralMind added to its first
      prompt, read back from `state.db`: the files it names, in order, those
      under its synapse section, whether it names a gold file and whether the
      first is one, and the block's SHA-256. The text stays out of git with
      the transcript.
    - A carried run records the carry-over check: learned edges when its
      store is copied in, after its build, and with both ends in its new
      graph. The `structural` and `shared` namespaces are left out of that
      count, as NeuralMind seeds them rather than learning them. Its hook
      counts leave out the carried recaps' entries, so the manipulation check
      sees only its own session.
    - A chain's state is saved after its run is judged, once NeuralMind's
      session maintenance has released its lock, and the chain moves on only
      once the run is recorded, so a resumed chain starts from its last
      recorded run.
  - Hermes's cron jobs on ai-9970 stay paused for the whole track, as they
    were for stage 2 from its run 23.
  - The analysis code is committed before the runs' results are read. Until
    then `analyze` refuses memory-track runs.
- 2026-10-30 — the memory track's analysis code (`analyze_memory` in
  `evals/task_outcome/analyze.py`), committed while its smoke test ran and
  before any of its 120 runs. `analyze` picks it for runs whose `track` is
  `memory` and refuses a mix of tracks. Its operational choices:
  - **Primary:** the Hermes variant's code, with `fresh` in the baseline's
    place and `carried` in NeuralMind's, so a task counts for a condition when
    at least 2 of its 3 runs solve it, a timed-out run never solves, and the
    one-sided McNemar test counts carried-only tasks.
  - **Mechanism:** per condition, the tasks where at least 2 of 3 runs' blocks
    name a gold file, and where at least 2 of 3 put one first; and the runs
    with no block read back.
  - **Prediction:** held when the carried arm solves at least as many of the
    12 repeat tasks as the fresh arm, and at least as many of the other 8
    minus one.
  - **Carry-over check,** over carried runs after position 1: the median
    learned edges copied in and left after the build, the share of those left
    with both ends in the new graph (summed over runs), and how many runs
    started with nothing learned.
  - **By position:** carried solve share minus fresh solve share, 3 runs each.
- 2026-10-30 — the memory track's smoke test passed, 2 runs in
  `bench/task_outcome/memory-smoke/`, not analysed or pooled: one chain,
  `4e01f40e6a` then `e303c7a287`, on harness 2 and the frozen ai-9970.
  - **Every pre-registered check passed.** The chain's first run started with
    nothing learned. The second started with the 2,016 edges the first had
    learned, all 2,016 still in the store after its build with both ends in
    its graph, and with the first run's recap. Its block differs from the
    first run's, and both runs recorded NeuralMind's prompt hook. A chained
    script checked these and started the 120 runs at 22:58 UTC.
  - **What the carried state changed in the block.** The second run's block is
    the fresh block for the same task, as the Hermes run's three `neuralmind`
    runs of `e303c7a287` got it, plus the session recap of the chain's
    previous run. The recall section, its files and its synapse section are
    identical. After one task, then, the learned edges didn't change what
    recall shows, and the carried state reached the agent only through the
    recap, which named the one file the previous run edited last
    (`neuralmind/turbovec_backend.py`, not a gold file of either task).
    Whether that holds as a chain learns more is what the mechanism report
    measures.
  - Neither run solved its task (84 and 117 model calls).
  - **One harness failure, retried.** The second run's first attempt was
    stopped at 22:30 UTC: gpt-oss emitted a truncated tool call (to
    `process_manage`, which isn't one of its tools), Ollama answered HTTP 500
    three times, and Hermes switched to its fallback model, OpenRouter's
    `qwen/qwen3.8-flash`, for the rest of the session. The harness found the
    other model in the session and recorded nothing, as the spec's rule says.
    That run's workspace was deleted and the chain's saved state wasn't
    advanced, so the retry started from the first run's state. The smoke and
    the track's scripts now retry a harness failure from the next unrecorded
    run after the preflight matches again (the track at most 5 times). None of
    the Hermes run's 120 sessions fell back.
  - For the whole track, ai-9970's Hermes cron jobs, its `neuralmind-maintain`
    user timer (whose Sunday step runs `uv tool upgrade neuralmind`) and
    Ubuntu's `apt-daily-upgrade` timer are stopped, the last by the user.
- 2026-10-30 — which harness the memory track's runs record, correcting the
  harness-3 entry above. That entry and the memory track's harness were
  written apart. The track's 120 runs record `harness_version` 2: they run on
  commit `e9d7ffec`, the Hermes harness 2 plus `--track memory`, as checked
  out on ai-9970 before harness 3 was merged. "Harness 2" in the track's
  entries means that runner. The runner with both, merged here, records 4.
  For this study's runs, 2 and 4 do the same: the `neuralmind` profile, no
  index cache and no guard change nothing, and the memory track refuses
  `--index-cache`, as a carried run never restores an index.
- 2026-10-30 — chain continuity, from review, while the track's first run was
  under way and before any of its results were read:
  - **The runner's gap.** A carried run's state is saved to the chain's
    `next` and promoted only after the run is recorded. A stop between the two
    would have left the recorded run's state unpromoted, and a resume would
    have deleted it and run the chain's next task from the state before it,
    silently. The runner merged here marks each saved state with its run and,
    before every carried run, promotes a recorded run's pending state, discards
    an unrecorded one, and stops (exit 2) if the chain's state isn't from its
    last recorded run.
  - **The track's runs don't have it:** they run on `e9d7ffec`, unchanged, so
    every run is measured the same way. The gap needs the runner to stop in
    the moment between writing a record and renaming a directory.
  - **So the analysis checks every carried run afterwards.** Each run leaves
    one session recap, so a continuous chain's run at position p starts with
    p − 1 of them. `analyze_memory` reports the carried runs where that
    doesn't hold, as runs off their chain.
- 2026-11-01 — the memory track's hook check, changed before its last 7 runs
  and before any comparison between its conditions was read. The chain had
  stopped twice on five harness failures, and none of the ten was one.
  - **What the check got wrong.** A carried run's hook counts were the
    workspace's total less the counts of the recaps it carried in. NeuralMind
    keeps its newest 10 recaps, plus any active in the last 24 hours, and
    deletes the rest as a session starts. Position 16 started 25 to 26 hours
    after position 1, so from there each carried run deleted one or two of
    its chain's oldest recaps: 11 recorded carried runs, at positions 16 to
    19, hold −1 or −2 prompts. Where the deleted recaps held one prompt and
    the session recorded one, the difference came to 0, the check's failure.
    A retry restores the same carried state, so the same run failed the same
    way: `b4c9886021` chain 0 twice, `7a1c90dcab` chains 2 (twice) and 0, then
    `7a1c90dcab` chain 1 five times in a row.
  - **NeuralMind reached all ten.** Each aborted session's first message in
    `state.db` carries its recap and recall block, and a recap is deleted
    only when the plugin starts a session.
  - **The change** (`c750fe40`, on ai-9970's checkout of `e9d7ffec`). Each
    session writes its own recap file, so the check now leaves out the
    carried files by name instead of subtracting their counts. Only the abort
    decision and the recorded `hook_*` counts change: what NeuralMind adds to
    the prompt and how a run is judged don't. The 4 carried runs after it
    (positions 19 and 20) record their own session's count, 1 prompt each.
- 2026-11-01 — the memory track is complete, all 120 runs recorded in
  `bench/task_outcome/memory-track/` (from 2026-10-30 22:58 to 2026-11-01
  13:39 UTC). `report.txt` there is `analyze`'s output:
  - **Result, labelled "pilot": claim not supported.** With the carried
    state, gpt-oss solved 9 of the 20 tasks (most of a task's 3 runs), and 7
    fresh. Of the 4 tasks only one condition solved, 3 went to carried
    (`b06a3ee6af` 2 of 3 runs against 1, `21bd34dfc4` and `108b1ee013` 3
    against 1) and 1 to fresh (`366858e431`, 3 against 1). One-sided McNemar
    p = 0.31.
  - **Solved runs: 25 of 60 carried, 21 of 60 fresh.**
  - **The fresh arm's own variation is as large.** Not part of the
    pre-registered comparison, which leaves the Hermes run out: the fresh
    arm repeats that run's `neuralmind` arm on the same tasks, machine and
    pins, two days later, and solved 7 tasks to its 10. The 9 carried solved
    are all among those 10, and so are the 3 only carried solved here.
  - **Mechanism, reported: no difference.** Tasks where most of the runs'
    blocks name a gold file: 16 carried, 16 fresh; where most put one first:
    11 and 11. One run in each condition had no block read back.
  - **Prediction: held.** Carried solved 5 of the 12 repeat tasks to fresh's
    3, and 4 of the other 8 to fresh's 4.
  - **Carry-over check.** The 57 carried runs after position 1 carried in a
    median 36,222 learned edges, all still in the store after the build,
    96% of them with both ends in the new graph. None started with nothing
    learned.
  - **12 runs "off their chain", none of them broken.** All 12 are the three
    chains' runs at positions 17 to 20. The check assumed a run at position p
    starts with p − 1 recaps, which NeuralMind's retention (above) ends: from
    position 17 a chain carries 11 to 14 of them, not 16 to 19. That is the
    product as shipped; the learned edges carry whole. Two other checks
    show the chains unbroken. In 56 of the 57 carried runs after position 1,
    the block's recap quotes the previous position's task (the 57th is the
    run with no block). And each chain's final state holds the recaps of
    exactly its own runs at positions 10 to 20.
  - **Secondary endpoints, reported, not tested.** Median whole-session
    tokens per task 2.83M fresh and 3.43M carried; the per-task change is
    +18.2% (95% CI −2.4% to +28.5%). Median minutes per task 14.7 and 15.8,
    turns 86.8 and 100.2, tool calls before the first edit 30.2 and 30.8;
    runs that edited a gold file 44 and 52; one timeout in each.
  - **Harness failures: 11, none recorded.** The hook check's 10 false
    alarms above, and one run (`fa72224183`) that Hermes moved to its
    fallback model, `qwen/qwen3.8-flash`, which the harness caught. All 120
    recorded sessions ran on `gpt-oss:20b-64k` with Hermes v0.22.5,
    NeuralMind 4.23.1 (tool and plugin) and harness 2, and all are in
    `state.db`, so `sessions.json` covers every run. Every fresh run
    recorded the plugin's prompt hook.
- 2026-11-01 — lexical anchoring for the prompt hook's block, pre-registered
  before any scorer code was written. Offline replays only, no agent runs;
  the hypothesis, mechanism, tuning allowance and gate are fixed here first.
  - **Question.** The block names a file the fix touched on 4 of the 12
    held-out hermes-agent tasks (first on 3) under every ranking tried
    (`bench/task_outcome/hermes-agent-test-ranking/`), because the file isn't
    among the embedding hits at all. A git-grep replay of the exact
    identifiers in each prompt (backticked spans, snake_case and CamelCase
    names, `--flags`, quoted error messages), scoring files by the sum over
    matched identifiers of 1 / ln(1 + files matching the identifier), named
    6 of the 12 (first on 3), with firsts disjoint from the hook's: together
    7 named and 6 first, a bound no fusion can beat. On the pilot's 20 tasks
    it named 17 (first 11), the hook's own figures. Does adding that lexical
    evidence to the block's ranking reach the held-out gate below while
    holding the pilot's floors?
  - **Mechanism, behind a default-off flag** (`NEURALMIND_RECALL_LEXICAL=1`;
    with it unset the block is byte-identical to today's):
    - *Extract* exact identifiers from the prompt: each backticked span and
      each single- or double-quoted span of 8 characters or more, whole, and
      the identifier-like words of 4 characters or more inside them;
      `--flags`; snake_case, CamelCase and UPPER_CASE names of 4 characters
      or more anywhere in the prompt. A generic stop list of English and
      programming words (not repository names) is dropped, as are URLs. At
      most 24 identifiers per prompt, in order of appearance.
    - *Match* them exactly, case-sensitively, over the project's working tree
      with one `git grep -F` call, restricted to files the index holds code
      nodes for. Test files are left out of the lexical evidence unless the
      prompt names a test, the rule the ranking already applies to test
      files. An identifier matching more than 60 files is dropped as
      uninformative. A project that isn't a git work tree gets no lexical
      evidence (the flag fails open).
    - *Score* each matched file by the sum over its matched identifiers of
      1 / ln(1 + files matching the identifier): an identifier found in one
      file is worth 1.44, in two 0.91, in five 0.56.
    - *Fuse*: a matched file enters the ranking with `LEXICAL_WEIGHT` times
      its lexical score added to the summed embedding scores of its matching
      symbols, through its own file node when the graph has one, so a file no
      embedding hit is in can still be named. Everything after that is
      unchanged: tests after the code, the reserved test slot, the
      tested-code credit, the excerpt's 2:1 margin, the linked section, the
      docs line, and the hook's similarity gate.
    - *Why not the index's BM25*: the build's unified BM25 index holds each
      code node's symbol name and path and each docstring, not the source
      text. On the held-out tasks the identifiers that found the gold file
      are mostly string literals and constants (`'storage_unavailable': 503`,
      `"readiness check still in progress; retrying next tick"`,
      `ENV_EXAMPLE_FILENAME = ".env.EXAMPLE"`), which no symbol index holds;
      and loading that index is a 196 MB JSON parse per hook call on
      hermes-agent. `git grep -F` over 9,603 Python files took 0.2–0.5 s per
      prompt there; the hook's time with the flag on is reported.
  - **Tuning allowance.** `LEXICAL_WEIGHT` is chosen from {0.25, 0.5, 1.0}
    on the pilot's 20 tasks and the hermes-agent screen's 5 tasks (both were
    the earlier ranking changes' tuning sets), by named then first on both
    sets, ties to 0.5. The value is fixed, and recorded in the results
    README, before the held-out replay, which runs once. Nothing else is
    tuned.
  - **Gate**, on the real `neuralmind _hook prompt-submit`, scored by
    `evals/task_outcome/replay.py`'s `score()`, on the same cached indexes
    (built once with v4.22.1) as the test-ranking study, so the flag is the
    only difference between the rows:
    - held out, 12 hermes-agent tasks: a file the fix touched is listed on
      at least 6 of 12, and listed first on at least 5 of 12;
    - pilot, 20 tasks: listed on at least 17, first on at least 11 (today's
      figures, not the CI floors of 15 and 9);
    - the share of test files among the files the 12 held-out blocks list
      does not rise above today's 14 of 84.
    All three must hold. If they do, the next step is confirmation on 12 new
    held-out tasks from the seeded walk (seed 20261025, positions 25 onward)
    before any agent run; the default stays off until then. If they don't,
    the replay is published as it is, with a plain reading of what moved.
  - **Also reported, not gated:** per task, the files listed, which changed
    against the flag-off row, the identifiers extracted and matched; the
    excerpt shown and on a changed file; median block size; the hook's time
    per call on one held-out index, flag off and on; the same figures on the
    screen's 5 tasks.
  - **Threats, stated up front.**
    - The prompts were written by an agent from each fix's tests and diff.
      They may quote identifiers more faithfully than a user's bug report
      would, which favours lexical matching; the hook's `#731` and credit
      changes were measured on the same prompts, so the comparison is fair,
      but the size of the gain may not transfer.
    - The lexical-only held-out figures above were known before this entry
      was written (they motivate it). The gate is on the fused block, which
      hasn't been run, and on the pilot's floors.
    - 12 tasks from one repository: enough to see the count move, not to
      estimate the size of the effect. Hence the confirmation step.
    - More identifiers in a prompt mean more lexical evidence; a long
      pasted traceback could crowd the embedding ranking. The 24-identifier
      cap and the 60-file cut bound it; the per-task listings show whether
      it happened.
- 2026-11-01 — lexical anchoring replayed, as pre-registered above; results
  in `bench/task_outcome/lexical-anchoring/`. Offline, no agent runs.
  - **`LEXICAL_WEIGHT` = 0.5,** chosen in-process on cached hits before the
    held-out replay: on the pilot's 20, 0.25 gave 17 listed / 13 first, 0.5
    and 1.0 gave 18 / 13; on the screen's 5 all three gave 3 / 3, and 1.0
    listed two more test files. 0.5 and 1.0 tied on listed and first over
    both sets, so 0.5 kept it. The held-out replay then ran once.
  - **The gate holds.** Through the real hook on the test-ranking study's
    indexes, flag off against flag on: held out 4 listed / 3 first against
    **7 / 5** (gate 6 / 5); pilot 17 / 11 against **18 / 13** (gate 17 / 11);
    test files among the held-out blocks' files 14 of 84 both ways (gate: not
    above). The flag-off rows reproduce the study's `#731 + credit` rows task
    for task.
  - **What moved.** Held out, 6 of 12 blocks changed: two tasks gained first
    on a quoted message found in one file (`24b4f90e97`, `cd69be6909`), one
    gold file went from absent to second (`4a78de2805`), the three firsts
    the hook had held, and `696f6e9ff9` changed to other wrong files. Pilot,
    18 of 20 blocks changed: one task gained listed and first, two gained
    first, one lost first to the `cli.py` its quoted flags live in. Code
    quoted / from a changed file: held out 3 / 1 both ways, pilot 8 / 7 to
    10 / 9. Median hook time on hermes-agent 9.32 to 9.82 s (cold graph
    loads: these indexes predate the graph cache), on this repository 0.50
    to 0.68 s.
  - **Read against the bound.** The git-grep replay that motivated the entry
    took backticked spans only; the pre-registered extractor also takes
    quoted messages, which is what found `24b4f90e97`. So the fused block
    reaches that replay's union-with-the-hook on listed (7) and falls one
    short of it on first (5 against 6).
  - **The first count is exactly at its threshold,** from two tasks
    changing. As registered, the next step is confirmation on 12 new
    held-out tasks from the seeded walk (seed 20261025, positions 25
    onward), before any agent run; the default stays off until then.
  - **Run twice, same blocks.** Review of the PR changed the code after the
    first run (URLs blanked before every extraction pass, untracked files
    searched, a file-level entry where the graph has no file node) and the
    diagnostic record (made with the hook's own matcher). All six rows were
    re-run; every one of the 72 blocks was identical to the first run's, so
    the counts stand as the single pre-registered replay. The committed rows
    and the hook times are the second run's.
