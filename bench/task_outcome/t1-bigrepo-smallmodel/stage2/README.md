# Track 1, stage 2: the full run

**Pre-registered** in
[`TASK-OUTCOME-BIGREPO-SMALLMODEL.md`](../../../../docs/specs/TASK-OUTCOME-BIGREPO-SMALLMODEL.md):
gpt-oss:20b-64k through Hermes on the 20 hermes-agent tasks of
[`studies/t1-bigrepo-smallmodel/`](../../../../evals/task_outcome/studies/t1-bigrepo-smallmodel/),
baseline against NeuralMind 4.24.0 with lexical anchoring on, 3 seeds each,
120 runs. Primary endpoint: tasks solved by a majority of 3 seeds, one-sided
exact McNemar, claim supported at p < 0.05.

**Result: claim not supported.** Each arm solved 3 of 20 tasks. One task was
solved only by the baseline and one only with NeuralMind; p = 0.75. Counted by
run, the baseline solved 12 of 60 and NeuralMind 10 of 60. This is the sixth
task-outcome study in a row with no significant difference, and the spec's
registered consequence for this stage is "stop building for agents; publish".

`analyze.txt` is the analyzer's output as written on the machine; `runs.jsonl`
holds the 120 run records, `sessions.json` the whole-session tokens and
minutes, `gpu-watch.log` the GPU's occupants on every change.

## Setup

- ai-9970, 2026-11-09 05:33 UTC to 2026-11-10 06:54 UTC. Harness 6 at
  `e286fbcf`, Hermes 0.23.0 for all 120 runs (the spec's 2026-11-08 entry; the
  floor check's 20 runs on 0.22.6 are not reused), `--max-turns 120`, timeout
  3600 s. Every NeuralMind run restored a cached index.
- No recorded run timed out or used a paid provider.

## Per task: runs solved of 3

| Task | Baseline | NeuralMind | Block listed a gold file first (of 3) |
|---|---|---|---|
| `f94d72f7e8` | **3** | **2** | 3 |
| `a3537b6f04` | **3** | **3** | 2 |
| `4a78de2805` | **2** | 1 | 0 |
| `d4fa373017` | 1 | **2** | 3 |
| `167a2d00ed` | 0 | 1 | 3 |
| `652e4b9194` | 1 | 1 | 0 |
| `0968fa2631` | 1 | 0 | 0 |
| `cd69be6909` | 1 | 0 | 0 |
| `0cb3760383` | 0 | 0 | 3 |
| `28e6496a5e` | 0 | 0 | 3 |
| `44cf71f231` | 0 | 0 | 3 |
| the other 9 | 0 | 0 | 0 |

Bold marks a task solved by majority. The other 9 are `ebf002cd3e`,
`1c39127d37`, `e9eba2188a`, `24b4f90e97`, `696f6e9ff9`, `859b999db5`,
`5381678d03`, `3c53adbc1e`, `e3fbd32d26`.

## Mechanism and secondary, reported, not tested

| | Baseline | NeuralMind |
|---|---|---|
| Runs that edited a gold file | 28 of 60 | 30 of 60 |
| Runs that edited anything | 37 of 60 | 38 of 60 |
| Runs at the 120-turn cap (119 or more turns) | 26 of 60 | 26 of 60 |
| Median tool calls before the first edit, per task | 61.0 | 54.3 |
| Median tokens per task | 3,134,905 | 3,302,606 |
| Median minutes per task | 10.1 | 10.7 |

- Median per-task token change with NeuralMind: -7.7%, 95% CI -12.2% to
  +11.6%. The interval spans zero.
- The prompt block named a gold file on 7 of 20 tasks, and whenever it named
  one it listed it first (20 of 60 runs). On those 7 tasks the arms solved 2
  and 3 by majority; where the block named no gold file, 1 and 0.
- The agent made no NeuralMind tool call in any of the 60 NeuralMind runs.
  Everything NeuralMind did, it did through the prompt hook.
- Not computed here: the index of the first tool call on a gold file and of
  the first read of one. Both need the transcripts, which stay on the machine.

## Deviations, all recorded

- **The start slipped 13.5 hours and no run was affected.** The index rebuild
  ended at 19:38 UTC on 11-08. Preflight then refused to start: a new local
  model server (Fara1.5-9B, a systemd unit set up that evening) held 10 GB of
  the 16 GB GPU, and the Hermes config file was newer than the gateway. With
  the owner's go-ahead the unit was stopped for the window and the gateway
  restarted at 05:32 UTC on 11-09; preflight then matched the record.
- **Two attempts were aborted and re-run, both in the NeuralMind arm**
  (`ebf002cd3e` seed 1 at 06:17 UTC, `0cb3760383` seed 1 at 20:42 UTC on
  11-09). The local endpoint returned an internal server error, Hermes fell
  back to a cloud model (qwen3.8-flash through OpenRouter), and the runner
  refused to record a session on the wrong model. Both were re-run on
  gpt-oss and recorded, both unsolved. Of the 81 Hermes sessions in the
  window only those two used the fallback; none of the 120 recorded runs did.
  A re-run replaces an attempt whose outcome is unknown: neither task was
  solved in any arm or seed, so no re-run outcome could move the primary
  endpoint.
- **One run shared the GPU.** Between 02:11 and 03:00 UTC on 11-10 another
  local model (`qwen3.8-27b-rvn`, called from the machine itself) was loaded
  through Ollama about twenty times, evicting gpt-oss each time
  (`gpu-watch.log`). gpt-oss was fully on the GPU whenever it was loaded. The
  one run in that window, `859b999db5` NeuralMind seed 2, took 54 minutes
  against a median of 10, hit the turn cap and was unsolved. That task was
  solved 0 of 6 times, so the run cannot move the primary endpoint either.
  Preflight gates a run's start, not its middle; the watch log is what caught
  this.
- The prompt's interpreter line (stage 1's finding) applies to both arms
  alike.

## What it does and doesn't say

- On the setting chosen as the most favourable (a 20B local model, a
  million-line repository, a ranking change that put the right file first
  more often), NeuralMind did not change how many tasks the agent solved.
- The block's effect on where the agent looks is small here: two more runs
  edited a gold file, and the first edit came about seven tool calls sooner
  per task at the median. Neither is tested and neither became a solve.
- 20 tasks with a 15% solve rate detect only a large effect. The result rules
  out a large gain; it does not show NeuralMind does harm.
- The retrieval and token measurements elsewhere in this repository are
  unaffected: they measure whether the right file is found and what a
  question costs, not whether an agent finishes a task.
