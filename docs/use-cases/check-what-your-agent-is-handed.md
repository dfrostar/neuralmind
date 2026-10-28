# Check what your agent is handed, before paying for agent runs

**Best for:** contributors changing NeuralMind's ranking or its prompt hook,
and anyone deciding whether a context tool's output is worth an agent
benchmark.

**Primary goal:** see, offline and with no API cost, what the
`UserPromptSubmit` hook gives the agent on real bug-fix tasks, scored against
the fixes themselves (v4.21.0+).

A context tool can find the right file and still not help. The only way to
know is to run the agent on real tasks with and without it, and that costs a
headless agent session per task, arm and seed. NeuralMind's
[task-outcome pilot](../specs/TASK-OUTCOME-BENCHMARK-SPEC.md) did that: 20 real
bug fixes, 120 runs, and no difference (median cost per task +0.0%, 95% CI
−5.2% to +8.6%; 18 of 20 tasks solved either way).

The cheaper question comes first: what did the agent actually receive? Replaying
the hook on the pilot's 20 prompts showed that the block named the file the fix
changed in 17 of 20 tasks, and the agent still searched before its first edit.
That replay is now a script and a CI gate.

---

## 1. Get a clone with its history

The tasks are bug fixes from NeuralMind's own history. The replay exports each
fix's parent commit from git, so it needs the full history, not a shallow
clone:

```bash
git clone https://github.com/dfrostar/neuralmind.git
cd neuralmind
pip install -e .        # or put the release you want to measure on PATH
```

The replay measures whichever `neuralmind` is on `PATH`. Install the working
tree to measure a change; install a release into a venv to measure that
release.

## 2. Replay the hook

```bash
python -m evals.task_outcome.replay --work-dir <scratch> --out <dir>
```

For each of the 20 tasks in `evals/task_outcome/tasks.json` it exports the
fix's parent commit into `<scratch>/<task-id>`, runs `neuralmind build` there,
and pipes the task's prompt into `neuralmind _hook prompt-submit`, the command
Claude Code runs on `UserPromptSubmit`. No agent runs. It clears every
`NEURALMIND_*` variable for the build and the hook, so it scores the defaults.

- `--reuse` keeps a workspace's index when it's already built, so a second run
  skips the 20 builds. Leave it off after changing anything the build does.
- `--check` exits 1 when a count falls below the floors in `replay.py`. CI's
  **Prompt-recall replay** workflow runs it with `--check` on every pull
  request that touches the recall path.

## 3. Read what the agent would have seen

The run writes two things to `<dir>`:

- `blocks/<task-id>.md`: the block the hook printed, exactly as the agent
  would get it as `additionalContext`. Read a few before you read any score.
- `replay-results.json`: a `summary` and one record per task, with the files
  the block listed, the fix's gold files and the scores.

What each score means:

| Score | True when |
|---|---|
| `named` | a file the fix changed is among the files the block lists |
| `first` | that file is the first one listed |
| `excerpt_shown` | the block quotes code (only when one file's summed match score is at least twice the next file's) |
| `excerpt_on_gold` | the quoted code is from a file the fix changed |
| `excerpt_on_fix` | the quoted lines overlap lines the fix changed |

The summary counts each over the 20 tasks, and `excerpt_on_gold_share` is
`excerpt_on_gold` divided by `excerpt_shown`.

Measured on v4.21.0:

| Of 20 tasks | v4.21.0 |
|---|---|
| The block names a file the fix changed | 17 |
| …and names it first | 10 |
| The block quotes code | 9 |
| …from a file the fix changed | 7 of 9 |
| …covering lines the fix changed | 2 of 9 |

Read the last row first. The best-matching symbol is usually in the right file
and usually not the function the fix touched: a symptom reads like what the
code is *about*, not where it breaks. And the excerpt's 2:1 gate was set on
these same 20 prompts, so 7 of 9 is a ceiling, not an estimate. The floors
guard against a regression on prompts the pilot ran; they don't predict new
tasks.

Then count the test files among the files each block lists: no score does.
On a 5-task screen in
[NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent), the
block named a changed file on 2 tasks, and 18 of the 32 files it listed were
under `tests/`: the prompt's "run the existing tests" sentence had switched off
the ordering that puts tests after the code. v4.23.0 fixed that ordering
([release notes](../releases/RELEASE_NOTES_v4.23.0.md)); on the same 5 tasks
tests fell to 6 of 35 files listed. Those are the tasks that found the
problem, so they can't also show the fix works.

### Changing the ranking? Hold tasks out

The floors are set on the prompts that tuned the ranking, so passing them
says a change broke nothing there, not that it helps elsewhere. For a ranking
change of your own, tune on one set of tasks, settle the change, then replay
tasks it never saw, before and after, on the same index for each task, so
only the ranking differs. v4.23.0's test-file ordering was checked this way
*(v4.23.0+)*: made on the 5-task screen, then replayed on 12 held-out
hermes-agent bug fixes. Test files fell from 33 of 82 listed to 14 of 84, and
the file to fix was listed first on 3 tasks instead of 1, but it was named on
4 either way: the change reordered the block more than it found new files.
The tasks, prompts, exclusions, results and script are in
[`bench/task_outcome/hermes-agent-test-ranking/`](https://github.com/dfrostar/neuralmind/blob/main/bench/task_outcome/hermes-agent-test-ranking/README.md).

## 4. Then measure the outcome

A better block is a reason to run the agent, not a result. The harness that
measures the outcome is `evals/task_outcome/run.py`, described in
[`evals/task_outcome/README.md`](https://github.com/dfrostar/neuralmind/blob/main/evals/task_outcome/README.md):

```bash
python -m evals.task_outcome.run --tasks evals/task_outcome/tasks.json \
    --out bench/task_outcome/<run> --model <model-id> --seeds 3 \
    --tool-venv <venv with neuralmind==X> --test-python <test-venv>/bin/python \
    --work-dir <scratch> --dry-run    # drop --dry-run to spend the runs

python -m evals.task_outcome.analyze bench/task_outcome/<run>
```

It runs each task as a headless Claude Code session with and without
NeuralMind, judges the fix with tests the agent never sees, and applies the
pre-registered statistics. Each run spends API usage, capped by `--budget`;
`--dry-run` shows the plan first. The replay tells you which tasks' blocks
changed, and `--task <id>` runs only those.

---

## What this doesn't tell you

The replay scores what NeuralMind hands the agent, not what the agent does
with it. A block that names the right file first didn't stop the pilot's agent
from making a median of 4 search or read calls before its first edit, and
v4.21.0 didn't change that: an
[exploratory rerun](https://github.com/dfrostar/neuralmind/blob/main/bench/task_outcome/exploratory-agent-uptake/README.md)
with it found the agent still called no NeuralMind tool in 60 runs and made a
median of 4.0 such calls (4.0 without NeuralMind), at a cost per task within
−6.9% to +6.5% of the baseline. The right file in the block is necessary, not
sufficient. The 20 tasks also come from one
repository, NeuralMind's own.

## The potential use case: look before you pay, for any context tool

The pattern isn't specific to NeuralMind. Take real fixes, phrase each as the
symptom someone saw, feed the prompt to whatever your context tool injects, and
score the output against the fix's diff. If the right file isn't there, an
agent benchmark will only measure that more expensively. If it is there and
the outcome still doesn't move, the problem is how the agent uses it, which is
what v4.21.0's MCP server instructions and code excerpt try to change.

On your own repository, the closest built-in check is
[`neuralmind eval` with symptom-phrased gold questions](./does-it-earn-its-place.md).

Related: [NeuralMind in Claude Code](./claude-code.md) ·
[Does NeuralMind earn its place?](./does-it-earn-its-place.md) ·
[Measure retrieval on your own repo](./measure-retrieval-on-your-repo.md) ·
[Task-outcome benchmark spec](../specs/TASK-OUTCOME-BENCHMARK-SPEC.md) ·
[Release notes v4.21.0](../releases/RELEASE_NOTES_v4.21.0.md)
