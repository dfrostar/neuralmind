# PRD: Opt-in LLM-judged answerability arm for the public benchmark

**Status:** Draft · **Owner:** dfrostar · **Created:** 2026-06-20
**Tracking branch:** `claude/answerability-judge` · **Target:** v0.34.0

## 1. Background & strategic motivation

The public benchmark (v0.31.0) scores **gold-file recall** — an objective,
deterministic, no-LLM-judge findability metric. It is deliberately honest about
its own limit, in `docs/benchmarks/public.md`:

> "Pure gold-file recall measures *locating*, not *answering*."
> "An optional, opt-in LLM-judged answerability arm (`--judge`, with the model +
> prompt + transcripts published) is planned as a clearly-labeled *secondary*
> signal — never the headline."

That gap is the **single sharpest critique a serious reviewer will raise** on
HN/Reddit: "recall of the def-site file ≠ the agent could actually answer." We
already concede it in the docs. Shipping the `--judge` arm *before* the launch
turns "planned" into "here it is, with transcripts" — and does it the honest way
(secondary signal, published prompt + model + raw judged transcripts, never
displacing the deterministic headline).

This is the highest-leverage next increment: it closes our own stated weakness,
it's net-additive (opt-in, off the deterministic path), and it's exactly the
kind of evidence the "pass engineering + Reddit scrutiny" bar demands.

## 2. What already exists

- `evals/public/run.py` — deterministic runner: per repo (`ensure_checkout`),
  per query (`run_query`), per backend (`BACKEND_ORDER`), assembling context and
  scoring `BackendResult(recall, found, tokens, …)`, rolled up by `_aggregate`
  and rendered by `render_markdown`. Headline = recall at N× fewer tokens.
- `evals/public/backends.py` — `RepoFiles`, `BackendResult`, the four backends.
  Each backend produces an **assembled context** (the text actually put in a
  model's window) plus the file list and token count.
- `evals/public/manifest.json` — pinned repos + pre-registered queries, each with
  an objective `gold_files` def-site oracle.
- `docs/benchmarks/public.md` — already promises this arm as a labeled secondary.

## 3. The gap (what v0.34.0 adds)

1. **`evals/public/judge.py`** — a thin, opt-in answerability scorer. For a given
   query it takes the **same assembled context** a backend already produced
   (`BackendResult.context` / the assembled text), sends `(question + that
   context)` to a Claude model, and asks the model to answer **only from the
   provided context**. A separate **judge call** (independent context, the
   published rubric) scores the answer against the query's gold facts on a small
   fixed scale, returning a structured verdict. No change to the recall metric.
2. **`--judge` flag on `python -m evals.public.run`** — off by default. When set
   (and `ANTHROPIC_API_KEY` present), runs the answerability arm *in addition to*
   the deterministic recall table and emits a **separately-labeled** section. The
   default run is byte-identical to today (no network, no key, CI-safe).
3. **Published provenance.** The judge **model id**, the **answerer prompt**, the
   **judge rubric prompt**, and the **raw judged transcripts** (question, context
   digest, answer, verdict, rationale) are committed under
   `bench/public/judge/` so a skeptic can audit or re-score. The model id is
   pinned (`claude-opus-4-8`) and printed in the output.
4. **Honest framing in the docs.** The arm is presented as a *secondary*
   signal with its caveats stated up front (LLM-judged, not deterministic;
   single judge model; answer-from-context-only constraint), and **never**
   replaces or outranks the recall headline.

## 4. Goals / non-goals

**Goals**
- An opt-in `--judge` arm that measures *answerability* (can the model answer the
  question from the backend's assembled context?) across the **same** pinned
  repos/queries, scored by a published rubric with committed transcripts.
- Apples-to-apples across backends: every backend's *own* assembled context is
  judged with the *same* answerer + judge prompts and the *same* pinned model.
- Zero impact on the deterministic path: default run unchanged, CI never calls an
  external model, fails closed (clean skip) without a key.

**Non-goals**
- Not the headline. Recall-at-N×-tokens stays primary; this is labeled secondary.
- Not an agentic loop — single answer turn from a fixed context, mirroring how
  the recall arm tests assembled context (no tool use, no multi-turn).
- Not gating CI (needs a paid model + key). Stays a separate opt-in flag, run
  out-of-band and committed, exactly like the competitor row.

## 5. Design

### 5.1 Answerer call (one per query × backend)
- Input: the backend's assembled context + the question.
- System prompt (published): instruct the model to answer **only** from the
  provided context, and to say "insufficient context" if the answer isn't there
  — this is what makes a low-recall backend score low rather than the model
  papering over a missing file from prior knowledge.
- `client.messages.create(model="claude-opus-4-8", max_tokens=1024,
  thinking={"type": "adaptive"}, system=ANSWERER_SYSTEM, messages=[…])`.
  (Adaptive thinking per the Claude API default for non-trivial reasoning;
  `budget_tokens` is removed on Opus 4.8.)

### 5.2 Judge call (one per answer)
- Input: question, the query's **gold facts** (derived from the def-site oracle /
  manifest), and the candidate answer. Independent context (no leakage from the
  answerer's reasoning).
- Structured verdict via `output_config={"format": {"type": "json_schema",
  "schema": …, additionalProperties: false}}` — fields: `score` (small fixed
  integer scale, e.g. 0/1/2), `grounded` (bool: answer used only provided
  context), `rationale` (string). Structured outputs guarantee a parseable
  verdict; no prefill (removed on Opus 4.8).
- Rubric prompt published verbatim in `bench/public/judge/RUBRIC.md`.

### 5.3 Aggregation & output
- Per backend: mean answerability score, % grounded, n judged. Rendered as its
  own clearly-labeled "Answerability (LLM-judged, secondary)" section beneath the
  recall table, repeating the "this is not the headline" framing.
- Raw transcripts → `bench/public/judge/raw/<repo>.json` (question, context
  digest/hash, answer, verdict, rationale, judge model id).

### 5.4 Cost, determinism, safety
- Off the default path; requires `ANTHROPIC_API_KEY`. Absent key → clean skip
  (print a one-line how-to), exactly like `competitor.py`'s fail-closed pattern.
- Pin the judge model (`claude-opus-4-8`); print it in the output and bake it
  into committed transcripts so the row is reproducible and auditable.
- Stream or cap `max_tokens` modestly; the arm is small (≈ #queries × #backends
  answerer calls + an equal number of judge calls) so cost is bounded and stated.
- Handle `stop_reason == "refusal"` defensively (check before reading content);
  a refusal on a query is recorded as a skipped/!grounded verdict, not a crash.

## 6. Fairness & honesty (the credibility crux)

| Risk | Mitigation |
|------|-----------|
| "An LLM judge is rigged / unfalsifiable." | Publish the **exact** answerer + judge prompts, the pinned model id, and **every** raw transcript. A skeptic can re-run or swap the model and re-score. Clearly labeled *secondary* to the deterministic recall headline. |
| "The model answered from prior knowledge, not your context." | Answerer is constrained to answer **only** from the provided context and to declare insufficiency; the judge separately scores `grounded`. Low-recall backends should score low. |
| "You judged your own backend favorably." | Identical answerer + judge prompts and the same pinned model across **all** backends (full-file, ripgrep, embedding-rag, neuralmind). Every backend's own assembled context is judged the same way; all verdicts committed, incl. where NeuralMind ties/loses. |
| "Single judge model is biased." | Disclosed as a known limitation; model id pinned + printed; transcripts committed so anyone can re-score with another model. Never the headline number. |

## 7. Acceptance criteria

- [ ] `evals/public/judge.py` — answerer + judge calls, pinned `claude-opus-4-8`,
      structured-output verdict, fails closed (clean skip) without a key.
- [ ] `--judge` flag on `python -m evals.public.run` — off by default; default run
      byte-identical (no network, CI-safe). With the flag + key, emits a
      separately-labeled secondary section.
- [ ] Real answerability arm produced across `requests` + `click` for all four
      backends; raw transcripts committed under `bench/public/judge/raw/`;
      `RUBRIC.md` + answerer/judge prompts committed.
- [ ] `docs/benchmarks/public.md` updated: the planned-arm paragraph becomes the
      shipped arm, with the secondary-signal framing and caveats; recall stays
      the headline.
- [ ] Hermetic tests: mock the Anthropic client (no network in CI); cover verdict
      parsing, fail-closed-without-key, refusal handling, aggregation.
- [ ] Docs + SEO per CLAUDE.md (release notes, README pointer, keywords like
      `answerability-benchmark`, `llm-judged-eval`).

## 8. Rollout

PRD → build on `claude/answerability-judge` → run the real arm out-of-band and
commit transcripts → CI green (judge tests hermetic) → hold for merge okay →
merge cuts **v0.34.0**. After this lands, the benchmark answers its own hardest
self-stated critique *with published transcripts* — exactly the evidence the
launch (Show HN + r/LocalLLaMA) needs in hand before posting.
