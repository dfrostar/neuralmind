# Faithfulness study — plan

Status: proposed (not started). 3–5 day scope.

## Question being answered

When NeuralMind hands an agent a compressed L0/L1/L2/L3 context for a code
question, does the agent reach the *same answer* it would with full source?
If not, where does it break?

## Scope

In: code Q&A on a fixed corpus, single-turn, single-file and cross-file
questions.

Out: multi-turn editing, agentic loops, latency, throughput. Those belong
in the end-to-end workload benchmark, not here.

## Setup

- **Corpus:** the bundled `neuralmind/demo_data/sample_project/` plus 1–2
  real OSS repos pinned to a SHA (candidates: `requests`, `flask`).
  Read-only.
- **Question set:** ~60 questions across 4 buckets — *definition lookup*,
  *call-site / usage*, *cross-file behavior*, *invariant / "why"*.
  Hand-written, with ground-truth: a free-text reference answer plus a
  citation set (file paths + line ranges that must appear in any correct
  answer).
- **Models:** one cheap (Haiku 4.5), one strong (Sonnet 4.6). Two runs
  each at temperature 0 to measure the non-determinism floor.

## Conditions (per question)

1. **Full-source baseline** — entire relevant file(s) in context.
2. **NeuralMind L0 only** — one-line summaries.
3. **NeuralMind L0+L1** — + signatures.
4. **NeuralMind L0+L1+L2** — + docstrings / key bodies.
5. **NeuralMind L0–L3** — full progressive disclosure, synapse recall on.
6. **L0–L3, synapse recall off** — isolates whether learned associations
   actually help.
7. **Naive top-k embedding retrieval** at matched token budget — controls
   for "is graph structure doing work, or just retrieval?"

## Metrics

- **Citation recall / precision** vs. ground-truth file:line ranges.
  Deterministic. **Primary metric.**
- **Answer correctness** — LLM-judge (Sonnet) with rubric. Human spot-check
  20% for calibration. Secondary.
- **Token cost** per condition (already instrumented).
- **Faithfulness / cost frontier** — correctness vs. tokens. Headline chart.

## Deliverables

- `evals/faithfulness/` runner: questions YAML, condition matrix, judge
  prompt, results JSONL.
- One results table + frontier plot.
- Short internal writeup of which question buckets degrade earliest —
  that's the actionable signal for tuning the context selector.

## Day plan

- **D1:** author ~20 questions + ground-truth citations on sample fixture.
- **D2:** runner, condition matrix, judge harness; smoke-run all 7
  conditions on the sample corpus.
- **D3:** extend corpus to one OSS repo, author ~40 more questions.
- **D4:** full run (2 models × 7 conditions × ~60 q ≈ 840 calls,
  cacheable), score, plot.
- **D5:** writeup. Decide whether the end-to-end workload benchmark is
  worth running given results.

## Risks / open decisions

- LLM-judge bias toward verbose answers — mitigated by using citation
  recall as the primary metric and the judge as secondary.
- 60 questions is small. The frontier shape should still be visible, but
  powering a per-bucket significance test would need ~150.
- Synapse recall needs warm-up traffic to be fair to condition 5. Plan a
  synthetic warm-up pass over the corpus before scoring.

## Explicitly not in this plan

- README or marketing changes.
- Regenerating `demo_data/.../graph.json` — graphify output is
  non-deterministic enough that re-running it would churn wheel contents.
- Merging `tests/fixtures/sample_project/` and
  `neuralmind/demo_data/sample_project/` — different lifecycles.
