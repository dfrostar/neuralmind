# Benchmarks & Results

Everything here is **measured and reproducible** — no hand-picked or hardcoded
numbers. Every figure is produced by code in the repo. The fixture-based
figures are **gated in CI**, so they can't silently regress; the public
benchmark on real OSS repos is **reproducible on demand** (deterministic, one
command, raw data committed) but is not a CI gate. Where a number is an
estimate or a real-repo extrapolation, it says so. One labeled exception: the
[field report](#field-report-a-real-world-rebuild-not-ci-gated) below is a
one-repo, maintainer-measured case study — reproducible in method, not gated
in CI. On the public benchmark, "reproducible" means gold-file recall,
found-rate and MRR have come back identical on every machine compared, while
per-repo mean tokens have varied by up to 1.3% between machines
([details](https://github.com/dfrostar/neuralmind/blob/main/docs/benchmarks/public.md#how-exactly-a-re-run-reproduces)).

> Reproduce locally: `python -m tests.benchmark.run` (token reduction + learning
> + synapse A/B), `python -m evals.faithfulness.runner --run` (answer quality),
> `python -m evals.onboarding.runner --run` (onboarding lift),
> `python -m evals.parity.run` (backend parity).

## What the data shows, losses included (the short version)

NeuralMind is more than token reduction; the numbers below cover **four**
benefits. Two run on **real, pinned OSS repos** (`requests`, `click`, `flask`,
`rich`) and are fully reproducible — `python -m evals.public.run`
([methodology](https://github.com/dfrostar/neuralmind/blob/main/docs/benchmarks/public.md)) — and two are committed A/Bs on the bundled **reference
fixture** (real but smaller-scope): **(1) Cheaper context** — **85–100%
gold-file recall (93.75% mean, 90% found-rate across 40 queries) at 45–261×
fewer tokens** than pasting files, beating `ripgrep` on cost on every repo and
on recall on two of four (tying on the other two); **(2) Finds the right code** — 100% gold-file recall, **MRR
0.96**, beating the incumbent `codebase-memory-mcp` on retrieval ranking (0.96
vs 0.23) — a separate, off-by-default eval on `requests`/`click` only, not yet
re-verified against the current `flask`/`rich`-expanded corpus; **(3) Learns
how you work** — the Hebbian synapse layer lifts top-k hit-rate, **budget-neutral**
(reference fixture; +3.5 to +14 points across runs, CI gates the direction);
**(4) Answer grounding vs. naive truncation — currently a loss** — at a matched
budget, truncation keeps slightly more gold facts on the prose-heavy reference
fixture (delta −0.054 at v4.3.4; earlier releases +0.013 to +0.143; CI fails
below −0.10). We report where NeuralMind *doesn't* win
too — a well-tuned vector RAG ties or beats it on pure findability and is
cheaper on raw tokens, two repos have gold-file misses — 4 of 40 queries (see
the public benchmark's "Where NeuralMind loses" section), and the competitor row is *pure
retrieval ranking*, not their LLM-agent loop. Full tables and reproduction
commands below.

## The honest headline

**On code questions, NeuralMind sends the agent the few entities that matter
instead of whole files — so the same answer costs 12-50× fewer tokens on real
repositories.** That real-repo range is the product's positioning; the number we
**measure in CI** is deliberately conservative, on a tiny 500-line fixture where
there's little to prune, and it still clears a wide margin.

| What | Measured (CI, 500-line fixture) | On real repos |
|------|---:|---|
| Token reduction on code questions | **5.1×** (v4.3.4) | **12-50×** (more files to prune ⇒ larger ratio) |
| Regression floor (CI fails below) | 4.0× | — |

The fixture number is the *floor of a floor*: small repo, conservative gate. The
mechanism is what scales — the bigger the codebase, the more whole-file context
you avoid.

## Does the memory make answers *better*, not just shorter?

Not on this measure, right now — and we publish that. The **faithfulness eval**
compares NeuralMind's selected context against naive truncation **at the same
token budget** — the honest comparison, not "small context vs the whole repo."

| Metric (built-in backend, gold set) | What CI enforces | Measured |
|---|---|---|
| Expected-fact recall vs matched-budget naive | mean delta **≥ −0.10** (3 runs) | **−0.054** at v4.3.4 (0.451 vs 0.505); earlier releases +0.013 to +0.143 |
| Grounding (right modules cited) | not gated | 0.843 at v4.3.4 |

A positive delta would mean smart selection beats plain truncation **at equal
cost**. At v4.3.4 it doesn't: the reference fixture mixes code with prose chapter
summaries, and on prose a matched-budget truncation can keep more of the expected
facts — which is why `ci-benchmark.yml` gates at −0.10 rather than 0. The gate
catches a real regression; it does not guarantee a win. The size of the delta
moves with retrieval changes, so read the current value from the CI benchmark
comment on any pull request.

## The learned memory layer (the differentiator)

NeuralMind's moat is usage memory: a Hebbian **synapse layer** that learns what
your team edits together and surfaces it on future queries. Both effects are
measured by isolated A/Bs:

| Effect | What CI enforces | Observed across runs |
|---|---|---|
| **Synapse recall** — top-k retrieval hit rate (same warm graph) | recall-on **≥** recall-off, at a neutral token budget | **+3.5 to +14 pts** |
| **Onboarding lift** — top-k module hit-rate from a committed team baseline | lift **≥ 0**, averaged over 3 runs | **+0.9 to +11.6 pts** |

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
| Rust | 49 | **49 (100%)** | 0 |
| Java | 52 | **52 (100%)** | 0 |
| C | 47 | **47 (100%)** | 0 |
| C++ | 51 | **51 (100%)** | 0 |
| C# | 52 | **52 (100%)** | 0 |
| Ruby | 46 | **46 (100%)** | 0 |
| PHP | 54 | **54 (100%)** | 0 |

The built-in tree-sitter backend matches graphify symbol-for-symbol on the
reference fixtures for **all ten bundled languages** (Python plus the nine above);
an optional SCIP pass replaces heuristic call edges with compiler-accurate ones.
All gated by `evals/parity/run.py` (coverage floor 90%, zero dangling edges) — the
numbers above are emitted live by the parity gate on every PR. Per-language *answer
quality* (vs structural coverage) is still Python-first; see
[Limits & Failure Modes](Limits-and-Failure-Modes#3-language-support-matrix).

## Field report: a real-world rebuild (not CI-gated)

Unlike everything above, this is a **field report**: the maintainer ran
NeuralMind across a major internal rebuild of a private, mid-size TypeScript
SaaS platform (~9,300 nodes) and recorded before/after numbers with the
shipped CLI (`neuralmind stats` / `benchmark`, a timed `build --force`). One
repo, one developer, anonymized — reproducible in *method* on your own
codebase, but not a CI-gated claim.

| Headline | Value |
|---|---|
| Avg token reduction (`neuralmind benchmark`) | **48.8×** (~1,033 tokens/query vs the fixed 50K-token estimate the CLI used before v4.5.0) |
| Personal synapse edges across the rebuild | **36 → 135** — the learning layer tracked the new code |
| Shared edge weight | **+5.4%** (denser cross-links after a new shared layer) |
| Full `--force` rebuild / incremental after | **326 s** / **~30 s** |

Full table, interpretation, and a step-by-step recipe for the same
before/after measurement on your own refactor:
[Measure memory across a major refactor](https://github.com/dfrostar/neuralmind/blob/main/docs/use-cases/measure-memory-across-a-refactor.md).

## Tool-output compression (measured, and withdrawn)

Through v4.4.0, `install-hooks` registered PostToolUse hooks that handed Claude
compressed copies of `Read`, `Bash` and `Grep` output. The
[compression benchmark](https://github.com/dfrostar/neuralmind/blob/main/docs/benchmarks/compression.md) drives the real hook with Claude Code-shaped
payloads and applies each response the way Claude Code's documented hook
protocol does.

| Tool call | Tokens, no hook | v4.3.4 hooks | Hooks now |
|---|---:|---:|---:|
| Bash (16 real commands) | 32,581 | 38,296 (+17.5%) | +0.0% |
| Grep, content mode (48 searches) | 55,800 | 68,113 (+22.1%) | +0.0% |
| Read (136 whole files) | 597,002 | +0.0% (never fired) | +0.0% |

Claude Code adds a hook's `additionalContext` next to the tool result rather
than replacing it, so the copies cost tokens. The hooks now inject nothing. The
compressors themselves would cut 66–87% if they replaced a result, but they
keep 0% of a file's source lines and 0% of a diff's changed lines. CI
recomputes the Bash results on every PR (`tests/test_compression_benchmark.py`).

## What we *don't* claim

- The CI numbers come from a **deliberately tiny fixture** — they prove the
  mechanism and catch regressions, not a real-repo ceiling. Point it at your own
  repo with [`benchmark-your-repo`](https://github.com/dfrostar/neuralmind/blob/main/docs/use-cases/benchmark-your-repo.md).
- TurboQuant is an **approximate** (quantized) index; parity is gated on the
  reference fixture, and the compression win only matters at scale.
- The 12-50× figure is a real-repo range, not a fixed guarantee — your ratio
  depends on repo size and question shape.
- The field report above is a single private-repo measurement by the
  maintainer — treat it as an existence proof consistent with the 12-50×
  range, not an independent benchmark.

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
