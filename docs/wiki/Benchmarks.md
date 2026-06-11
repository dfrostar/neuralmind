# Benchmarks & Results

Everything here is **measured and reproducible** — no hand-picked or hardcoded
numbers. Every figure is produced by code in the repo and **gated in CI**, so it
can't silently regress. Where a number is an estimate or a real-repo
extrapolation, it says so.

> Reproduce locally: `python -m tests.benchmark.run` (token reduction + learning
> + synapse A/B), `python -m evals.faithfulness.runner --run` (answer quality),
> `python -m evals.onboarding.runner --run` (onboarding lift),
> `python -m evals.parity.run` (backend parity).

## The honest headline

**On code questions, NeuralMind sends the agent the few entities that matter
instead of whole files — so the same answer costs 40–70× fewer tokens on real
repositories.** That real-repo range is the product's positioning; the number we
**measure in CI** is deliberately conservative, on a tiny 500-line fixture where
there's little to prune, and it still clears a wide margin.

| What | Measured (CI, 500-line fixture) | On real repos |
|------|---:|---|
| Token reduction on code questions | **6.2×** | **40–70×** (more files to prune ⇒ larger ratio) |
| Regression floor (CI fails below) | 4.0× | — |

The fixture number is the *floor of a floor*: small repo, conservative gate. The
mechanism is what scales — the bigger the codebase, the more whole-file context
you avoid.

## Does the memory make answers *better*, not just shorter?

Yes, and it's measured. The **faithfulness eval** compares NeuralMind's selected
context against naive truncation **at the same token budget** — the honest
comparison, not "small context vs the whole repo."

| Metric (built-in backend, gold set) | NeuralMind | Matched-budget naive | Delta |
|---|---:|---:|---:|
| Expected-fact recall | **0.717** | 0.574 | **+0.143** |
| Grounding (right modules cited) | **1.000** | — | — |

A positive delta means smart selection beats dumb truncation **at equal cost**.
Gated in CI at delta ≥ 0.

## The learned memory layer (the differentiator)

NeuralMind's moat is usage memory: a Hebbian **synapse layer** that learns what
your team edits together and surfaces it on future queries. Both effects are
measured by isolated A/Bs:

| Effect | Off | On | Lift |
|---|---:|---:|---:|
| **Synapse recall** — top-k retrieval hit rate (same warm graph) | 72% | **83%** | **+12 pts** |
| **Onboarding lift** — top-k module hit-rate from a committed team baseline | — | — | **+6.5 pts** |

Both are **budget-neutral by design**: recalled nodes *displace* the weakest hits
rather than adding tokens. The onboarding lift is the answer to "does an agent
that inherits a committed team memory retrieve better on its *first* queries than
a cold agent?" — gated in CI at lift ≥ 0.

## v0.21.0 — ChromaDB-free retrieval, at parity

The opt-in `turbovec` backend (Google **TurboQuant**) can embed *and* search with
**zero ChromaDB**, and it does so without giving up quality:

| Backend | Fact recall | Top-k hit@4 | Vector size |
|---|---:|---:|---|
| chroma (float32 HNSW, default) | 0.744 | 0.759 | 1× |
| **turbovec (4-bit, ChromaDB-free)** | **0.800** | 0.759 | **~8–16× smaller** |

- The bundled embedder produces vectors **byte-identical** to ChromaDB's
  (`all-MiniLM-L6-v2`): verified **cosine 1.0, max elementwise diff 0.0** — so
  retrieval quality is unchanged; only the index representation differs.
- 8–16× smaller vectors means real memory headroom on large monorepos, and it
  **retires the dependency behind the recurring CVE-2026-45829 advisory**.

## Multi-language & precision (structural parity, gated)

| Language | graphify symbols | built-in covers | dangling edges |
|---|---:|---:|---:|
| Python | (gold-fact eval above) | — | — |
| TypeScript | 54 | **54 (100%)** | 0 |
| Go | 45 | **45 (100%)** | 0 |

The built-in tree-sitter backend matches graphify symbol-for-symbol on the
reference fixtures; an optional SCIP pass replaces heuristic call edges with
compiler-accurate ones. All gated by `evals/parity/run.py`.

## What we *don't* claim

- The CI numbers come from a **deliberately tiny fixture** — they prove the
  mechanism and catch regressions, not a real-repo ceiling. Point it at your own
  repo with [`benchmark-your-repo`](https://github.com/dfrostar/neuralmind/blob/main/docs/use-cases/benchmark-your-repo.md).
- TurboQuant is an **approximate** (quantized) index; parity is gated on the
  reference fixture, and the compression win only matters at scale.
- The 40–70× figure is a real-repo range, not a fixed guarantee — your ratio
  depends on repo size and question shape.

## Reproduce every number

```bash
pip install -e ".[dev]" tiktoken
python -m tests.benchmark.run            # reduction + learning + synapse A/B
python -m evals.faithfulness.runner --run   # answer-quality delta
python -m evals.onboarding.runner --run     # onboarding lift
python -m evals.parity.run               # backend parity (incl. turbovec)
```

Each prints a report and exits non-zero if it falls below its gate — the same
checks that run on every PR.
