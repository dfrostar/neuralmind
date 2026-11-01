# Exploration share of the token bill, 2026-10-02 to 2026-11-01

**Field report: one developer's two machines, not a product claim.** What share
of the prompt tokens an agent's sessions were billed for was *exploration*,
reading and searching code, as defined and pre-registered in
[`docs/specs/EXPLORATION-SHARE-SPEC.md`](../../../docs/specs/EXPLORATION-SHARE-SPEC.md)
before any figure was computed. Per-session rows stay on the machines (they
hold paths and project names); only these aggregates are committed.

## Result (pass 2, calibrated)

| Agent, source | Sessions | API calls | Prompt tokens billed | Context est. ÷ billed | **Exploration share** (billed) | median per session | NeuralMind block | Edits | Other shell |
|---|---|---|---|---|---|---|---|---|---|
| Claude Code, interactive (Mac) | 87 | 14,077 | 4,208,706,244 | 62.0% | **22.5%** | 14.6% | 0.0% | 0.3% | 14.8% |
| Hermes, interactive (ai-9970) | 66 | 5,434 | 860,781,331 | 100.3% | **7.6%** | 3.8% | 1.3% | 2.5% | 10.8% |
| Hermes, automated (cron etc.) | 1,766 | 6,636 | 83,366,696 | 100.2% | 6.3% | 0.0% | 1.7% | 0.1% | 5.7% |
| Hermes, subagent | 11 | 40 | 707,956 | 100.0% | 19.8% | 0.0% | 0.0% | 0.0% | 0.0% |
| Hermes, benchmark (task-outcome harness) | 261 | 33,148 | 788,919,603 | 100.5% | 48.3% | 48.9% | 0.2% | 1.3% | 2.3% |

Tokenizer `o200k_base` throughout. "Exploration share (billed)" is the
exploration tool results present in each API call's context, summed over
calls, divided by the estimated context the same way; "median per session" is
the median of that ratio across sessions.

**Pre-registered reading, interactive sessions:**

- **Claude Code (the Mac, where the coding happens): 10% to 30%.** The
  per-question token claim stands, with the share quoted beside it. Per-session
  quartiles 7.6% / 14.6% / 20.3%. One caveat the spec requires: the transcript
  accounts for 62% of what was billed (quartiles 0.60 / 0.67 / 0.73 across
  sessions over 1M tokens); the rest is prompt the transcript doesn't hold
  (tool schemas added during the session, system-reminders, thinking blocks,
  which Claude Code doesn't store). If none of it is exploration, exploration
  was 14% of the billed prompt; so **between 14% and 22.5%** of what these
  sessions were billed for was code being read or searched and re-sent.
- **Hermes (ai-9970, mostly operations and chat): under 10%.** On these
  sessions the saving is arithmetic: real per question, not felt on a bill.

What else the data says:

- **Exploration is what gets written, not what gets kept.** 70.5% of the
  content Claude Code's transcripts hold is exploration output (first-time
  share), but Claude Code trims and compacts it: 110 of 14,077 calls had to be
  trimmed to fit what was billed, 21 compactions were recorded, and the billed
  share is 22.5%.
- **NeuralMind's own block cost 1.3% of the Hermes interactive prompt** (the
  block appeared in 42 of the 66 sessions) and a rounding of zero on the Mac,
  where it appeared in 4 of 87 sessions (most Mac sessions were in projects
  without NeuralMind hooks). In the benchmark sessions it appeared in 191 of
  261 (the baseline arm has none) and cost 0.2%.
- **The benchmark sessions are not usage.** The task-outcome harness's 261
  Hermes sessions spent 48% of their context on exploration, because a 20B
  model on a 120-turn budget reads and greps far more than a developer does.
  They are reported, never pooled into the headline.

## Pass 1, superseded (kept for the record)

The presence model as first written kept every tool result at full size until
a compaction line and counted no prompt the transcript doesn't hold. It
calibrated between 0.23× and 7.4× of the billed prompt per session on the Mac
and read **72.3%** for Claude Code (median 38.4%) and 11.3% for Hermes
interactive (chars/4 tokenizer, tiktoken not yet installed there), 71.4% for
the benchmark sessions. Those figures are in `*.summary.pass1.json`; the
spec's change log says what changed and why. The thresholds did not change.

## Files

- `claude-code.summary.json`, `hermes.summary.json` — pass 2 aggregates
  (`python -m evals.exploration_share report` output).
- `claude-code.summary.pass1.json`, `hermes.summary.pass1.json` — pass 1.

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
