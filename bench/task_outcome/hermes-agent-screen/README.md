# Screen: 5 hermes-agent bug fixes

**Exploratory, and not a product claim.** Pre-registered in
[`TASK-OUTCOME-HERMES-AGENT-SCREEN.md`](../../../docs/specs/TASK-OUTCOME-HERMES-AGENT-SCREEN.md).
Its only job was to decide whether a full study on
[NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent)
(about a million lines of Python) is worth running.

**Setup**

- 5 tasks × 2 arms × 3 seeds = 30 runs, on 2026-10-25. Model
  `claude-sonnet-5-5`, Claude Code 2.1.309, NeuralMind 4.21.0 from PyPI,
  budget cap $3, timeout 1800 s. Task files:
  [`studies/hermes-agent-screen/`](../../../evals/task_outcome/studies/hermes-agent-screen/).
- Each task's index was built once (18–22 minutes) and a fresh copy restored
  into each of its neuralmind-arm runs (`--index-cache`).
- Every run had its own `HERMES_HOME`, and the launcher guard found the host's
  Hermes launchers unchanged after all 30.
- No run hit the timeout or ended on a harness failure.

**Result** ([report.txt](report.txt))

- Median cost change per task with NeuralMind: **+1.5%** (95% CI −28.1% to
  +5.2%). 2 tasks cheaper, 3 dearer; Wilcoxon p = 0.41.
- Tasks solved (majority of seeds): baseline 4, NeuralMind 5; runs solved
  11 of 15 against 14 of 15. McNemar p = 1.0.
- **Decision rule: stop.** It needed a median of −10% or better *and* no
  fewer tasks solved. The second holds; the first doesn't.
- As in the pilot, the agent called a NeuralMind tool in **0 of 15** runs and
  never called ToolSearch. The prompt hook was the only channel that reached it.

**What the hook showed** ([replay-results.json](replay-results.json))

Claude Code's stream doesn't record a `UserPromptSubmit` hook's output, so
[`hook_replay.py`](../../../evals/task_outcome/studies/hermes-agent-screen/hook_replay.py)
replays it offline on the same restored indexes and prompts, with no agent:

| Task | Hook named the fixed file | Listed first | Code excerpt | Cost change |
|---|---|---|---|---|
| `167a2d00ed` | yes | yes | on the fix's lines | −28.1% |
| `28e6496a5e` | yes | no | none | −5.4% |
| `652e4b9194` | no | no | none | +1.5% |
| `859b999db5` | no | no | a test file | +3.6% |
| `0968fa2631` | no | no | a test file | +5.2% |

- The hook named a fixed file on **2 of 5** tasks. On the pilot's 20 tasks in
  NeuralMind's own repository it named one on 17.
- **18 of the 32 files it listed are under `tests/`**, and 2 of its 3 code
  excerpts quoted a test file. On a repository with a large test tree, the
  tests crowd the source out of the block.
- The one task where it put the fixed file first and quoted the fix's lines is
  the one that got cheaper by most: explore calls before the first edit fell
  from 6.0 to 2.0, and 2 of 3 runs solved it against 1 of 3. One task is an
  anecdote, not evidence, and these 5 tasks can't be used to tune and then
  test the same change.

Transcripts are kept out of git, as in the pilot; each run records its
transcript's SHA-256.
