# Exploration share of the token bill, 2026-10-02 to 2026-11-01

**Field report: one developer's two machines, not a product claim.** What share
of the prompt tokens an agent's sessions were billed for was *exploration*,
reading and searching code, as defined and pre-registered in
[`docs/specs/EXPLORATION-SHARE-SPEC.md`](../../../docs/specs/EXPLORATION-SHARE-SPEC.md)
before any figure was computed. Per-session rows stay on the machines (they
hold paths and project names); only these aggregates are committed. Sessions
started 2026-10-02T00:00Z up to the run on 2026-11-01 at about 19:55Z.

## Result (pass 3)

| Agent, source | Sessions | API calls | Prompt tokens billed | Context est. ÷ billed | **Exploration share** (billed) | median per session | NeuralMind block | Edits | Other shell |
|---|---|---|---|---|---|---|---|---|---|
| Claude Code, interactive (Mac) | 87 | 14,105 | 4,218,516,248 | 63.5% | **27.4%** | 19.7% | 0.0% | 0.3% | 8.9% |
| Hermes, interactive (ai-9970) | 67 | 5,435 | 860,795,351 | 100.3% | **9.7%** | 4.9% | 1.3% | 2.5% | 8.8% |
| Hermes, automated (cron etc.) | 1,767 | 6,637 | 83,380,570 | 100.1% | 6.8% | 0.0% | 1.7% | 0.1% | 5.2% |
| Hermes, subagent | 11 | 40 | 707,956 | 100.0% | 19.8% | 0.0% | 0.0% | 0.0% | 0.0% |
| Hermes, benchmark (task-outcome harness) | 261 | 33,148 | 788,919,603 | 100.5% | 51.7% | 51.8% | 0.2% | 1.4% | 2.5% |

Tokenizer `o200k_base` throughout. "Exploration share (billed)" is the
exploration tool results present in each API call's context, summed over
calls, divided by the estimated context the same way; "median per session" is
the median of that ratio across sessions.

**Pre-registered reading, interactive sessions:**

- **Claude Code (the Mac, where the coding happens): 10% to 30%.** The
  per-question token claim stands, with the share quoted beside it. Per-session
  quartiles 9.9% / 19.7% / 27.4%. One caveat the spec requires: the transcript
  accounts for 63.5% of what was billed (quartiles 0.62 / 0.68 / 0.76 across
  sessions over 1M tokens); the rest is prompt the transcript doesn't hold
  (tool schemas added during the session, system-reminders, thinking blocks,
  which Claude Code doesn't store). If none of it is exploration, exploration
  was 17% of the billed prompt; so **between 17% and 27%** of what these
  sessions were billed for was code being read or searched and re-sent.
- **Hermes (ai-9970, mostly operations and chat): under 10%, just.** 9.7%
  pooled, 4.9% per session: on these sessions the saving is arithmetic, real
  per question and not felt on a bill. It sits at the edge of the band, so the
  nightly job's next weeks decide which side it settles on.

What else the data says:

- **Exploration is what gets written, not what gets kept.** 72% of the
  content Claude Code's transcripts hold is exploration output (first-time
  share), but Claude Code trims and compacts it: 106 of 14,105 calls had to be
  trimmed to fit what was billed, 21 compactions were recorded, and the billed
  share is 27%.
- **NeuralMind's own block cost 1.3% of the Hermes interactive prompt** (the
  block appeared in 42 of the 67 sessions) and a rounding of zero on the Mac,
  where it appeared in 4 of 87 sessions (most Mac sessions were in projects
  without NeuralMind hooks). In the benchmark sessions it appeared in 191 of
  261 (the baseline arm has none) and cost 0.2%.
- **The benchmark sessions are not usage.** The task-outcome harness's 261
  Hermes sessions spent 52% of their context on exploration, because a 20B
  model on a 120-turn budget reads and greps far more than a developer does.
  They are reported, never pooled into the headline.

## Earlier passes, superseded (kept for the record)

The spec's change log has the detail; the files are `*.summary.pass1.json`
and `*.summary.pass2.json`.

| Pass | Claude Code interactive | Hermes interactive | Why superseded |
|---|---|---|---|
| 1 | 72.3% (median 38.4%) | 11.3% (chars/4 tokenizer) | kept every tool result until a compaction line, counted no prompt the transcript doesn't hold: calibrated 0.23× to 7.4× per session |
| 2 | 22.5% (median 14.6%) | 7.6% (median 3.8%) | calibrated to billing, but split pipeline stages on `\|`, `;`, `&&` inside quotes (quoted regexes counted as shell), never dropped an earlier compaction summary, and could record a still-running session once |
| 3 | **27.4% (median 19.7%)** | **9.7% (median 4.9%)** | this report |

Pass 3's fixes came from code review of the pull request after pass 2 had
been read; the thresholds never changed.

## Files

- `claude-code.summary.json`, `hermes.summary.json` — pass 3 aggregates
  (`python -m evals.exploration_share report` output).
- `*.summary.pass1.json`, `*.summary.pass2.json` — earlier passes.

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
`~/nm-bench/tracks/t2-exploration-share/sessions.jsonl` and regenerates the
summary; the Mac is re-run by hand.
