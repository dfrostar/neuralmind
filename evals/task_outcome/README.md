# Task-outcome benchmark

**Does a coding agent finish real tasks for less with NeuralMind, without
finishing fewer?** Every other benchmark in this repository measures
retrieval. This one measures the agent's whole run, from the task starting to
the hidden tests judging the fix. The design, endpoints and decision rule are
pre-registered in
[`docs/specs/TASK-OUTCOME-BENCHMARK-SPEC.md`](../../docs/specs/TASK-OUTCOME-BENCHMARK-SPEC.md).

```bash
# 1. Turn bug-fix commits into tasks with a test oracle (no agent, no API cost)
python -m evals.task_outcome.harvest --python <test-venv>/bin/python \
    --work-dir <scratch> --out <scratch>/candidates.json <commit> ...

# 2. Run both arms (spends API usage; --dry-run shows the plan first)
python -m evals.task_outcome.run --tasks evals/task_outcome/tasks.json \
    --out bench/task_outcome/pilot --model <model-id> --seeds 3 \
    --tool-venv <venv with neuralmind==X> --test-python <test-venv>/bin/python \
    --work-dir <scratch> --dry-run

# 3. Apply the pre-registered statistics and decision rule
python -m evals.task_outcome.analyze bench/task_outcome/pilot
```

**Two environments**, so the agent's tool and the code under test can't mix:

- **Tool venv:** the NeuralMind release being measured (`pip install
  neuralmind==X`). Its `bin/` is on `PATH` only in the `neuralmind` arm.
- **Test venv:** the project's dependencies with the package itself
  uninstalled (`pip install ".[dev]" && pip uninstall -y neuralmind`).
  `python -m pytest` from a workspace root then imports that workspace's code.

**What a run costs.** Each run is one headless Claude Code session, capped by
`--budget` (default $2). The pilot is 20 tasks × 2 arms × 3 seeds = 120 runs.

**Stopping and resuming.** `runs.jsonl` is the record: rerunning the same
command skips every (task, arm, seed) already in it. A run that fails before
the agent gives a result (a logged-out CLI, an API error) records nothing and
exits 3; log in again and rerun. Start long runs detached so they don't depend
on a terminal or an agent session staying open:

```bash
tmux new -d -s bench 'python -m evals.task_outcome.run … >> bench.log 2>&1'
```

**Another repository.** `--repo <clone> --profile <name>` on `harvest`,
`select_tasks` and `run`. A profile ([`profiles.py`](profiles.py)) sets what
counts as source, the earliest fix date, and the repository name the prompt
gives the agent; the `neuralmind` profile is the pilot's, unchanged. For
`select_tasks`, `--study-dir` holds the study's own `exclusions.json` and
`prompts.json`, and `--seed` its pre-registered seed.

- **`--index-cache <dir>`:** builds each task's index once and restores a copy
  into every neuralmind-arm workspace, so each run still starts from a fresh,
  unused index. An entry is reused only for the same base commit and the same
  NeuralMind version; anything else is rebuilt. On a large repository it saves
  the build per run: hermes-agent (about a million lines) takes 22 minutes to
  index.
- **Hermes-Agent:** its `hermes-agent` profile gives every test run and agent
  run a `HERMES_HOME` inside its workspace. Hermes's code re-publishes its
  launchers for the active `HERMES_HOME`, so also pass
  `--guard ~/.hermes/hermes-agent/.hermes/bin` on a machine that has Hermes
  installed: a run that changes any file there stops the benchmark (exit 4,
  nothing recorded, workspace kept), checked after setup, after the session
  (before a failed session is cleaned up) and after the tests.

**What it doesn't measure.**
- **Learning over time:** every run starts from a fresh index, so the synapse
  layer has learned nothing.
- **Other codebases:** the pilot's tasks come from this repository only.

The spec lists every threat to validity.

`tests/test_task_outcome_stats.py` pins the statistics to hand-computed values.
