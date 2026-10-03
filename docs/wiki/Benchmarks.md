# Benchmarks & Results

Everything here is **measured and reproducible** — no hand-picked or hardcoded
numbers. Every figure is produced by code in the repo. The fixture-based
figures are **gated in CI**, so they can't silently regress; the public
benchmark on real OSS repos and the multi-repo
[retrieval eval](#retrieval-eval-v460) are **reproducible on demand**
(deterministic, one command, raw data committed) but are not CI gates. Where a number is an
estimate or a real-repo extrapolation, it says so. One labeled exception: the
[field report](#field-report-a-real-world-rebuild-not-ci-gated) below is a
one-repo, maintainer-measured case study — reproducible in method, not gated
in CI.

> Reproduce locally: `python -m tests.benchmark.run` (token reduction + learning
> + synapse A/B), `python -m evals.faithfulness.runner --run` (answer quality),
> `python -m evals.onboarding.runner --run` (onboarding lift),
> `python -m evals.parity.run` (backend parity),
> `NEURALMIND_ORT_THREADS=1 python -m evals.retrieval.run --public-benchmark` (multi-repo
> retrieval eval; needs `pip install -e . tiktoken`).

## What the data shows, losses included (the short version)

NeuralMind is more than token reduction; the numbers below cover **four**
benefits. Two run on **real, pinned OSS repos** (`requests`, `click`, `flask`,
`rich`) and are fully reproducible — `python -m evals.public.run`
([methodology](https://github.com/dfrostar/neuralmind/blob/main/docs/benchmarks/public.md)) — and two are committed A/Bs on the bundled **reference
fixture** (real but smaller-scope): **(1) Cheaper context** — **85.71–100%
gold-file recall (95% mean, 92.5% found-rate across 40 queries) at 46–263×
fewer tokens** than pasting files, beating `ripgrep` on cost on every repo and
on recall on three of four (tying on the fourth); **(2) Finds the right code** — 100% gold-file recall, **MRR
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
cheaper on raw tokens, three repos have gold-file misses — 3 of 40 queries (see
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

## Retrieval eval (v4.6.0)

*Evidence level: reproducible on demand — one command, raw output committed in
[`bench/retrieval/`](https://github.com/dfrostar/neuralmind/blob/main/bench/retrieval/README.md);
not a CI gate.*

v4.6.0 asked which ranking changes earn a default, and answered it with a
multi-repo eval instead of one repo's anecdote. `python -m evals.retrieval.run`
asks **30 questions per repository** — pre-registered and committed in
`evals/retrieval/questions/` (before any ranking change was tried) for the five
public repositories, plus a private 383-file repository with its own local
question set that readers can't re-run — under every flag configuration,
read-only. The repositories: `requests`, `click`, `flask`
and `rich` at the public benchmark's pinned commits, this repository (with its
docs indexed), and a private 383-file repository, reported only in aggregate.

**The keep rule**, fixed before the runs:

- mean hit@5 across repos goes up, and it goes up on at least 3 repos;
- no repo drops by more than one question;
- average context tokens rise by at most 10%;
- the public 4-repo benchmark's gold-file recall doesn't drop.

**What was kept: one BM25 index over docs and code.** The default turbovec
backend's keyword index held only document nodes, so the hybrid fusion gave
docs a keyword signal code never got. v4.6.0 indexes every node (doc text,
symbol names, file paths, docstrings) in one BM25 index, on by default
(`NEURALMIND_BM25_UNIFIED=0` restores v4.5.0). Against v4.5.0
([`bench/retrieval/vs-v4.5`](https://github.com/dfrostar/neuralmind/blob/main/bench/retrieval/vs-v4.5/report.md)),
hit@5 / MRR:

| Repo | v4.5.0 | v4.6.0 (unified BM25) |
|---|---:|---:|
| `requests` | 90% / 0.76 | 87% / 0.75 |
| `click` | 93% / 0.69 | 93% / 0.79 |
| `flask` | 73% / 0.63 | 83% / 0.71 |
| `rich` | 80% / 0.71 | 80% / 0.60 |
| `neuralmind` (docs indexed) | 40% / 0.27 | 60% / 0.47 |
| a private 383-file repository | 60% / 0.47 | 73% / 0.60 |
| **mean** | **72.8% / 0.589** | **79.4% / 0.654** |

On the five public repositories alone, mean hit@5 / MRR goes from
75.3% / 0.614 to 80.7% / 0.664. Context tokens rose 1.1%, and the public
benchmark's gold-file recall went from 93.75% to 95%. The losses, published:
`requests` drops one question (90% → 87%), `rich`'s MRR falls from 0.71 to
0.60, and on the public benchmark `click` gains a miss (`echo-util`), falling
from 100% to 85.71%. The private 383-file repository's 60% baseline is the
figure the work started from; its target (hit@5 ≥ 80%, MRR ≥ 0.65) is
**not met** — it reaches 73% / 0.60.

**What was measured and not kept.** Each stays available behind its flag, off
by default:

| Flag | What it does | Why it wasn't kept |
|---|---|---|
| `NEURALMIND_L3_PER_FILE=2` | at most N L3 hits per file | +1.1 pts mean hit@5, 2 repos up, none down on hit@5 — but mean MRR fell 0.654 → 0.629 (`requests` 0.75 → 0.69, `flask` 0.71 → 0.65); public recall 96.25%; the rule needs 3 repos |
| `NEURALMIND_DOC_HANDOFF=1` | a doc hit that names code pulls that code in | helps only where docs name code (private +3, `neuralmind` +1 question vs v4.5.0); a wash on top of v4.6.0 |
| `NEURALMIND_HUB_DAMPEN=1` | down-weights files returned far more often than chance | cost `click` 3–4 questions |
| `NEURALMIND_INTENT_RULES=1` | "how does X… / where is X… / which X is…" → code intent | moves MRR (0.654 → 0.672), never hit@5: it only re-orders the 4 hits L3 already chose |
| `NEURALMIND_INTENT_POOL=1` (with `INTENT_RULES=1`) | intent ranks all 10 candidates | `click` −8 questions, public recall 83.75% (vs v4.5.0) |
| `NEURALMIND_BM25_CODE=1` | a separate code-only keyword list | `requests` −3 (vs v4.5.0); `rich` −4, `click` −3 (on v4.6.0) |

One finding worth keeping even though its fix wasn't: the old intent classifier
(still the default, since the intent rules weren't kept) sends many questions
about how the project behaves — "how does X…", "where is X…", "which X is…" —
to **docs** intent, which multiplies doc hits ×2.0 and code ×0.7. Four questions
of those shapes are now regression tests
([`tests/test_l3_slots_v460.py`](https://github.com/dfrostar/neuralmind/blob/main/tests/test_l3_slots_v460.py)).
Run `neuralmind query --explain` to see which intent L3 ranked a query with,
and why.

```bash
pip install -e . tiktoken
NEURALMIND_ORT_THREADS=1 python -m evals.retrieval.run --public-benchmark --out bench/retrieval/on-v4.6
python -m evals.retrieval.run --private ~/work/your-repo   # add your own repo, locally
```

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
| Avg token reduction (`neuralmind benchmark`) | **48.8×** (~1,033 tokens/query vs 50K+ naive) |
| Personal synapse edges across the rebuild | **36 → 135** — the learning layer tracked the new code |
| Shared edge weight | **+5.4%** (denser cross-links after a new shared layer) |
| Full `--force` rebuild / incremental after | **326 s** / **~30 s** |

Full table, interpretation, and a step-by-step recipe for the same
before/after measurement on your own refactor:
[Measure memory across a major refactor](https://github.com/dfrostar/neuralmind/blob/main/docs/use-cases/measure-memory-across-a-refactor.md).

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
