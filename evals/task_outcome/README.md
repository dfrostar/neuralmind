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

**Hermes-Agent on a local model** (`run --agent hermes`, the spec's Hermes
variant) has no cost per call, so solve rate is its primary endpoint. Before
analysing, collect each run's whole-session tokens and minutes from Hermes's
`state.db` on the machine that ran it. A run's record covers only the Hermes
client's own turn, and has no tokens on the same scale for a run that timed
out:

```bash
python -m evals.task_outcome.hermes_sessions <out_dir>   # writes <out_dir>/sessions.json
```

**Two environments**, so the agent's tool and the code under test can't mix:

- **Tool venv:** the NeuralMind release being measured (`pip install
  neuralmind==X`). Its `bin/` is on `PATH` only in the `neuralmind` arm.
- **Test venv:** the project's dependencies with the package itself
  uninstalled (`pip install ".[dev]" && pip uninstall -y neuralmind`).
  `python -m pytest` from a workspace root then imports that workspace's code.

**What a run costs.** Each run is one headless Claude Code session, capped by
`--budget` (default $2). The pilot is 20 tasks × 2 arms × 3 seeds = 120 runs.

**What it doesn't measure.**
- **Learning over time:** every run starts from a fresh index, so the synapse
  layer has learned nothing.
- **Other codebases:** the tasks come from this repository only.

The spec lists every threat to validity.

`tests/test_task_outcome_stats.py` pins the statistics to hand-computed values.
