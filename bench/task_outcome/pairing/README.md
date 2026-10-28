# Pairing runs: 5 hermes-agent bug fixes, with and without NeuralMind

**Exploratory, and not a product claim.** Two small runs of the same 5 tasks
from [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent),
made on 2026-10-23 and 2026-10-24 by a Hermes agent working through its own
pre-registration ([`PRE-REGISTRATION.md`](PRE-REGISTRATION.md), written before
each run's first agent call). Like the
[hermes-agent screen](https://github.com/dfrostar/neuralmind/pull/720), their
only job was to decide whether a larger study is worth running. Both say it
isn't, on this design.

These runs used their own harness, not `evals/task_outcome/`, and a different
draw from the screen's: the 5 tasks here don't overlap with the screen's 5.

## The tasks

[`tasks.json`](tasks.json) (sha256 `e058586485b6805c1adbb515e7b125eb06a6bfaae2ae7d1f0e725f1126712aaf`,
unchanged across both runs): 5 hermes-agent fix commits, each graded by the
fix's own tests (FAIL_TO_PASS and PASS_TO_PASS) overlaid on the agent's
workspace. Candidates rejected on the way are in
[`exclusions.json`](exclusions.json), with reasons.

## Run 1: MCP only, 10 runs (2026-10-23)

5 tasks × 2 arms × 1 seed. The `treatment` arm had NeuralMind's MCP server
connected and **no prompt hook**; Claude Code 2.1.308, NeuralMind built from
`main` and reporting 4.20.0, model not recorded.

| | baseline | treatment |
|---|---|---|
| Tasks solved | 4 of 5 | 4 of 5 |
| Total cost (Claude Code's estimate) | $2.19 | $2.24 |
| NeuralMind tool calls | — | 0 |
| Timed out | 0 | 0 |

- The pre-registered gate (cheaper median cost per task, no fewer solved)
  failed: the treatment's median cost per task was 7.9% higher ($0.3995
  against $0.3704).
- The MCP server connected in every treatment run; the agent called none of
  its tools. The earlier write-up reports a transcript tally of 95 Bash and
  2 Edit calls; the transcripts aren't committed, and each run records its
  transcript's SHA-256 in [`run1/runs.jsonl`](run1/runs.jsonl).
- Its `explore_before_first_edit` column reads 0 in every run because it
  didn't count Bash; [`run1/explore_corrected.json`](run1/explore_corrected.json)
  recounts it from the transcripts.

## Run 2: hook and MCP, 30 runs (2026-10-24)

5 tasks × 2 arms × 3 seeds, in a seeded shuffled order. The `neuralmind` arm
had the prompt hook (`neuralmind install-hooks`, project scope) as well as
the MCP server. Model `claude-sonnet-5-5`, Claude Code 2.1.308, NeuralMind
4.21.0 from PyPI, budget cap $3, timeout 1800 s. The decision rule was the
screen's: recommend a larger study only if the median cost change per task
is −10% or better and the NeuralMind arm solves no fewer tasks.

Result ([`run2/report.txt`](run2/report.txt), from
`python -m evals.task_outcome.analyze` on [`run2/runs.jsonl`](run2/runs.jsonl)):

- Median cost change per task with NeuralMind: **−2.8%** (95% CI −11.1% to
  +3.3%). 3 tasks cheaper, 2 dearer; Wilcoxon p = 0.22.
- Tasks solved: 4 in each arm (12 of 15 runs in each); McNemar p = 1.0.
- **Decision rule: stop.** The cost condition failed.
- NeuralMind tool calls: 0 in 15 runs. A smoke run before the matrix
  showed the agent *could* call them (one call); in the matrix it didn't.
- No run timed out or ended on a harness failure.

The run's analysis step was never carried out at the time; this report was
produced from its committed rows on 2026-10-28, with the repository's
analyzer at `79d46eb9`.

## How these fit with the screen

| | Tasks | Prompt hook | Runs | Median cost change | Solved (baseline, NeuralMind) |
|---|---|---|---|---|---|
| Run 1 | these 5 | no | 10 | +7.9% (difference of the arms' medians; one seed, no interval) | 4, 4 |
| Run 2 | these 5 | yes | 30 | −2.8% (CI −11.1% to +3.3%) | 4, 4 |
| [Screen](https://github.com/dfrostar/neuralmind/pull/720) | 5 others | yes | 30 | +1.5% (CI −28.1% to +5.2%) | 4, 5 |

Three small runs on hermes-agent, with no cost difference shown in any of
them. The agent called no NeuralMind tool in the 20 runs here where the
server was connected, nor in the screen's 15. Each run is 5 tasks: together
they can show a large effect or its absence, not rule out a small one.

## Files

| Path | What it is |
|---|---|
| `PRE-REGISTRATION.md` | Both runs' frozen protocols and deviation logs (D1–D24), as written at the time |
| `tasks.json`, `exclusions.json` | The 5 tasks and the rejected candidates |
| `run1/runs.jsonl` | Run 1's 10 rows; its sha256 matches the one recorded before run 2 started |
| `run1/explore_corrected.json` | Run 1's exploration count, recounted including Bash |
| `run2/runs.jsonl` | Run 2's 30 rows |
| `run2/report.txt` | The analyzer's report on run 2 |
| `run2/summary.json`, `run2/run-log.md` | Run 2's own summary and launch log |

Kept out of git, on the machine that ran them: the transcripts (each row
records its SHA-256), the indexes, and the one-off harness scripts, which
don't pass this repository's lint and are recorded here as they ran:

| Script | sha256 |
|---|---|
| `run_bench.py` (run 1) | `bada7907e3f37bf0e5091e0e49737e4d8f515d05ae415de9413d61fa2f794dcf` |
| `run_bench2.py` (run 2) | `5da06f51d8342b38895f256780e81c8de89694924841e9777f5dad83a16da0c1` |
| `select_tasks.py` (the draw) | `e6877c774aa5b053250baa96efee99e00b1d86778a3fa30f517dc91d82a521f3` |
