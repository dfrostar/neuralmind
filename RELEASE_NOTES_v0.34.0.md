# NeuralMind v0.34.0 — answerability, not just findability

**Release Date:** June 2026

## TL;DR

The public benchmark now answers its own hardest critique. Gold-file recall
measures whether the **right file** lands in the window — *locating*, not
*answering*. The new opt-in **answerability arm** adds the answering signal:

```bash
ANTHROPIC_API_KEY=… python -m evals.public.run --judge   # off by default
```

For each query it takes **the real context each backend would put in the
window** — whole files for `full-file`/`ripgrep`, retrieved chunks for
`embedding-rag`, the compact L0–L3 assembly for `neuralmind` — asks a pinned
model (`claude-opus-4-8`) to answer **using only that context**, and a separate
judge call grades the answer against the **same def-site gold anchor** on a 0–2
scale (plus a `grounded` flag). The model + prompts + **every raw transcript**
are committed under `bench/public/judge/`.

## Why this matters

*"Recall of the def-site file ≠ the agent could actually answer."* It's the
sharpest question a serious reviewer raises — and we already conceded it in our
own docs. Now it's answered, with published transcripts, **before** anyone has to
ask. Recall-at-N×-tokens stays the headline; this is a clearly-labeled secondary.

## Fair by construction (so it can't be dismissed)

- **Each backend judged on its *real* window** — not a uniform whole-file proxy.
  A low-recall window scores low instead of being papered over from the model's
  prior knowledge (the answerer must say "insufficient context").
- **Same answerer + judge prompts, same pinned model, every backend** — full-file,
  ripgrep, embedding-rag, and neuralmind are graded identically.
- **Published provenance.** Answerer prompt, judge rubric, pinned model id, and
  raw per-query transcripts (question, context tokens, answer, verdict,
  rationale) committed under `bench/public/judge/`. Re-score it, or swap the
  model, yourself.
- **Honest caveats, stated plainly.** It's LLM-judged (not deterministic like
  recall); a single judge model is one viewpoint (disclosed; transcripts let
  anyone re-score); it never displaces the recall headline.

## Off the deterministic path (by design)

The arm needs `ANTHROPIC_API_KEY`, **never runs in CI**, and the recall table is
**byte-identical** with or without `--judge`. Absent a key it skips cleanly and
the recall benchmark still runs — same fail-closed discipline as the competitor
row.

## What ships

- **`evals/public/judge.py`** — answerer + judge calls (pinned `claude-opus-4-8`,
  adaptive thinking, structured-output verdict), `JudgeArm` aggregation, fail-
  closed without a key.
- **`evals/public/run.py`** — `--judge` flag + `--judge-out`; backends now expose
  their real window text (`BackendResult.context_text`, never serialized into the
  deterministic results); a separately-labeled answerability section in the
  report.
- **`docs/benchmarks/public.md`** — the planned arm is now the shipped arm, with
  framing + caveats.
- Tests: `tests/test_answerability_judge.py` (hermetic — fake client, no network).
- PRD: `docs/prd/answerability-judge.md`.

## Upgrade

```bash
pip install --upgrade neuralmind
```

No runtime changes to the agent path — this release is **evidence**. To produce
the answerability arm, run `python -m evals.public.run --judge` from a clone with
`ANTHROPIC_API_KEY` set; the recall benchmark runs key-free as always.
