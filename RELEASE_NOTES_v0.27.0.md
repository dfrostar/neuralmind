# NeuralMind v0.27.0 — prove retrieval finds *your* code

**The headline:** a new **`neuralmind probe`** command answers the one question
the existing benchmarks couldn't: *on my codebase, can the agent actually find
the right file when it asks about a symbol?* It runs **label-free** — no golden
fixtures, no hand annotation — so it works on any built project, and it reports
**recall@k / MRR / answerability** plus a **blind-spot list**: the symbols your
index can't retrieve from a natural-language description.

## Why this exists

NeuralMind already had two kinds of measurement, and both had a gap:

- **`neuralmind benchmark`** proves NeuralMind is *cheap* — it measures token
  reduction. It says nothing about whether the compressed context is *right*.
- **`neuralmind benchmark --quality`** proves the ranking is *good* — but only
  against a committed **golden suite** of hand-labeled `expected_modules` that
  ships with the source repo. It's a contributor/CI self-test; you can't point
  it at your own codebase, because nobody has labeled yours.

So there was no way for a *user* to get a retrieval-quality number on their own
repo. `neuralmind probe` fills that gap. The idea is borrowed from long-context
"needle-in-a-haystack" evals (e.g. S-NIAH in the *Recursive Language Models*
paper): instead of measuring cost, it measures whether the right node still
surfaces as the index grows — the retrieval analog of *context rot*.

## How it works

For a deterministic sample of indexed symbols, the probe:

1. **Synthesizes a natural-language query from the symbol's own identity** — the
   *humanized* label, never its node id. `authenticate_user` becomes
   `"authenticate user"`; `HTTPServerFactory` becomes `"http server factory"`.
   This mimics how a developer actually asks, and tests the embedding's ability
   to bridge plain English to a code symbol.
2. **Retrieves the top-k hits** from the real index and projects them to source
   files.
3. **Scores** whether the symbol's own source file came back, reusing the exact
   metric math (`neuralmind.quality`) behind the golden-suite eval:
   **recall@1/3/5, MRR, answerability@k**.

The most actionable output is the **blind-spot list** — sampled symbols whose
own file the index never retrieved. Those are the places an agent would come up
empty, named with the query that missed so you can reproduce it.

```bash
# Probe your codebase (builds the index first if needed)
neuralmind probe .

# Tighter test: the right file must be the #1 hit
neuralmind probe . --k 1

# Stable, comparable runs (same seed = same sample); save a baseline…
neuralmind probe . --sample-size 100 --json > probe-baseline.json
# …then later, after a refactor, see if retrieval moved
neuralmind probe . --sample-size 100 --baseline probe-baseline.json
```

Sample output:

```
Retrieval self-probe — my-project
Sampled 50 of 1240 indexed symbols, retrieval depth k=10
============================================================
  answerability  : 92%  (file found in top-10)
  MRR            : 0.810
  recall@1/3/5   : 0.740 / 0.860 / 0.900
  blind spots    : 4
------------------------------------------------------------
Symbols the index couldn't retrieve from their own description (4 total):
  - parseConfig  (cfg/loader.py)   query: "parse config"
  - RetryPolicy  (net/retry.py)    query: "retry policy"
  …
```

## Per-agent expectations

| Agent | What changes in v0.27.0 |
|-------|--------------------------|
| **Claude Code** | A new CLI you run yourself: `neuralmind probe .`. No hook or session behavior changes — retrieval, compression, and memory are untouched. The probe is read-only (it never writes the index or the synapse store). |
| **Cursor / Cline** | No tool-surface change. The probe is a CLI diagnostic; normal MCP queries are unaffected. |
| **Generic MCP client** | Same — no new tool, no behavior change in `query`/`search`. |
| **Contributors / CI** | New stdlib-only module `neuralmind/probe.py` (query synthesis, sampling, scoring — testable without the vector stack). New `NeuralMind.retrieval_probe()` method. New `neuralmind probe` CLI with `--sample-size`, `--k`, `--seed`, `--baseline`, `--json`. Reuses `neuralmind.quality`; no new metric math. You can gate CI on `probe --json` recall/MRR if you want a per-repo floor. |

## Design notes

- **Label-free and deterministic.** No fixtures to maintain. A fixed `--seed`
  gives the same sample every run, so a probe number is stable and comparable
  over time and across branches.
- **Read-only and fail-soft.** The probe never mutates the index or memory; a
  retrieval error on any sample degrades to an empty result for that sample
  rather than crashing the run.
- **Reuses the quality metrics.** recall/precision/MRR/answerability come
  straight from `neuralmind.quality` — the same math the golden-suite eval and
  CI gate already use — so a probe number means exactly what those do.
- **Blind-spot list is capped** (25 shown, full count always reported) so a
  pathological index can't produce an unbounded blob.

## Why it matters

Token reduction tells you NeuralMind is cheap. The golden suite tells the
maintainers it's good on a fixture. **`neuralmind probe` tells *you* it's good
on *your* code** — and, when it isn't, names exactly which symbols fall through.
Run it after a big refactor, when you switch backends, or as a CI floor, and you
get an honest, per-repo answer to "can my agent find this?" — the question that
actually matters when you're trusting an agent with your codebase.
