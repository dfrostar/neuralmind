# Exploration share of the token bill, 2026-10-02 to 2026-11-01

**Field report: one developer's two machines, not a product claim.** What share
of the prompt tokens an agent's sessions were billed for was *exploration*,
reading and searching code, as defined and pre-registered in
[`docs/specs/EXPLORATION-SHARE-SPEC.md`](../../../docs/specs/EXPLORATION-SHARE-SPEC.md)
before any figure was computed. Per-session rows stay on the machines (they
hold paths and project names); only these aggregates are committed. Sessions
started 2026-10-02T00:00Z up to the run on 2026-11-01 at about 22:00Z; a
session still writing when its file is read is deferred to a later run (and
replaced by it once it has written more), as the spec's change log says.

## Result (pass 5)

Two shares are reported for exploration, because they answer different
questions. **Of the recorded context** is the spec's headline: exploration tool
results present in each API call, over everything the transcript records as
present, both with the same tokenizer and presence model. **Of the billed
prompt** divides the same numerator by what the provider billed; the part of
the prompt the transcript doesn't hold (tool schemas, system-reminders,
thinking blocks) contains no tool results, so this is the recorded share times
the calibration ratio, not a bound.

| Agent, source | Sessions | API calls | Prompt tokens billed | Context est. ÷ billed | **Exploration, of recorded context** | **of billed prompt** | median per session | NeuralMind block | Edits | Other shell |
|---|---|---|---|---|---|---|---|---|---|---|
| Claude Code, interactive (Mac) | 88 | 12,540 | 3,736,688,230 | 64.0% | **30.7%** | **19.7%** | 21.1% | 0.0% | 4.5% | 14.8% |
| Hermes, interactive (ai-9970) | 67 | 5,435 | 860,795,351 | 100.0% | **10.4%** | **10.4%** | 5.4% | 1.2% | 8.7% | 13.3% |
| Hermes, automated (cron etc.) | 1,770 | 6,648 | 83,507,196 | 100.1% | 7.2% | 7.2% | 0.0% | 1.7% | 0.3% | 8.0% |
| Hermes, subagent | 11 | 40 | 707,956 | 100.0% | 18.9% | 18.9% | 0.0% | 0.0% | 0.0% | 0.1% |
| Hermes, benchmark (task-outcome harness) | 261 | 33,148 | 788,919,603 | 100.0% | 50.6% | 50.6% | 50.1% | 0.2% | 3.1% | 3.1% |

Tokenizer `o200k_base` throughout. Hermes bills per session, so its estimate
is calibrated to billing by construction and the two shares coincide; Claude
Code bills per call, and the transcript accounts for 64.0% of it (quartiles
0.63 / 0.69 / 0.76 across sessions over 1M tokens).

**Pre-registered reading, interactive sessions.** The spec's thresholds apply
to the headline, the share of recorded context:

- **Claude Code (the Mac, where the coding happens): 30.7%, "30% or more", by
  seven tenths of a point.** Per-session quartiles 10.0% / 21.1% / 29.6%. Of
  the billed prompt the same exploration is 19.7%, inside the 10–30% band. Both
  are true; the figure that speaks to a bill is the second. Said carefully: on
  this machine, about a fifth of what the sessions were billed for was code
  being read or searched and re-sent, and about a third of the context the
  agent could see. A reading this close to a line is not a finding about the
  line: the passes below put it at 27.4%, 30.6%, 30.1% and 30.7%.
- **Hermes (ai-9970, mostly operations and chat): 10.4%, "10% to 30%", at the
  band's lower edge** (5.4% per session). The claim stands with the share
  beside it; on these sessions the saving is small. Same caution: the passes
  put it at 9.7%, 10.4%, 10.5% and 10.4%.

The nightly job on ai-9970 and the next Mac run accumulate more sessions; they
decide which side of each line these settle on.

What else the data says:

- **Exploration is what gets written, not what gets kept.** 75% of the
  content Claude Code's transcripts hold is exploration output (first-time
  share), but Claude Code trims and compacts it: 108 of 12,540 calls had to be
  trimmed to fit what was billed, 11 compactions were recorded, and the share
  of recorded context is 31%.
- **NeuralMind's own block cost 1.2% of the Hermes interactive prompt** (the
  block appeared in 42 of the 67 sessions) and a rounding of zero on the Mac,
  where it appeared in 2 of 88 sessions (most Mac sessions were in projects
  without NeuralMind hooks). In the benchmark sessions it appeared in 191 of
  261 (the baseline arm has none) and cost 0.2%.
- **The benchmark sessions are not usage.** The task-outcome harness's 261
  Hermes sessions spent 51% of their context on exploration, because a 20B
  model on a 120-turn budget reads and greps far more than a developer does.
  They are reported, never pooled into the headline.

## Earlier passes, superseded (kept for the record)

The spec's change log has the detail; the files are `*.summary.pass<n>.json`.

| Pass | Claude Code interactive (recorded context; billed prompt) | Hermes interactive | Why superseded |
|---|---|---|---|
| 1 | 72.3% (median 38.4%) | 11.3% (chars/4 tokenizer) | kept every tool result until a compaction line, counted no prompt the transcript doesn't hold: calibrated 0.23× to 7.4× per session |
| 2 | 22.5% (median 14.6%) | 7.6% (median 3.8%) | calibrated to billing, but split pipeline stages on `\|`, `;`, `&&` inside quotes (quoted regexes counted as shell), never dropped an earlier compaction summary, could record a still-running session once |
| 3 | 27.4%; 17.4% (median 19.7%) | 9.7% (median 4.9%) | tool-call arguments counted as assistant text; active Hermes rows immune to the billing cap; `git branch feature` counted as exploration; one still-running session (1,457 calls, 480M tokens, share 13%) included |
| 4 | 30.6%; 19.6% (median 21.0%) | 10.4% (median 5.4%) | `git -C <path> diff` read as shell; `env pytest` read as exploration; a comment swallowing its newline; a session recorded while running stayed half-counted |
| 5 | **30.7%; 19.7% (median 21.1%)** | **10.4% (median 5.4%)** | this report |

What moved each time, on the Mac. Pass 3 → 4: deferring the still-running
session took the pooled figures from 27.4% / 17.4% to 29.1% / 18.6%, and
counting tool-call arguments with their category moved them to 30.6% / 19.6%.
Pass 4 → 5: running the pass-4 and the pass-5 classifier on the same 87
sessions, all the fixes since pass 4 (`git` global options, `env` as a
wrapper, comments, quoted operator characters, and re-collecting a session
that has written since) move the pooled figures from 30.66% / 19.62% to
30.69% / 19.64%, which is nothing. The difference between the pass 4 and
pass 5 rows is which sessions the run could read: sessions still writing when
the file is read are deferred (this one, for example), and others kept
growing between runs. That session-set drift, about half a point on the
headline, is the real size of the uncertainty around the 30% line. Passes 3
to 5 came from code review of the pull request after the previous pass had
been read; the thresholds never changed.

## Files

- `claude-code.summary.json`, `hermes.summary.json` — pass 5 aggregates
  (`python -m evals.exploration_share report` output).
- `*.summary.pass1.json` … `*.summary.pass4.json` — earlier passes.

## Reproduce

On a machine with the sessions (per-session rows are written locally and never
committed):

```bash
python -m evals.exploration_share claude-code --root ~/.claude/projects \
  --since 2026-10-02T00:00:00Z --until 2026-11-02T00:00:00Z --out rows.jsonl
python -m evals.exploration_share hermes --db ~/.hermes/state.db \
  --since 2026-10-02T00:00:00Z --until 2026-11-02T00:00:00Z --out rows.jsonl
python -m evals.exploration_share report --rows rows.jsonl --out-json summary.json --out-md summary.md
```

`tests/test_exploration_share.py` fixes the presence model on synthetic
sessions. On ai-9970 the Hermes cron job `neuralmind-exploration-share`
(no-agent script, 02:30 UTC daily) appends new sessions to
`~/nm-bench/tracks/t2-exploration-share/sessions.jsonl` (replacing the row of
a session that has written since) and regenerates the summary; the Mac is
re-run by hand.
