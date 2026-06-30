# SWE-bench retrieval eval

**Does NeuralMind's retrieval surface the files a real bug-fix actually edits?**

This harness answers the most-requested benchmark question — "how does it do on
SWE-bench?" — at the layer NeuralMind actually operates: **retrieval**. For each
SWE-bench task it takes the issue text (`problem_statement`) and scores whether
NeuralMind puts the **gold-patch files** (the files the maintainer's accepted fix
touches) into the context window — objective gold, no LLM judge, deterministic.

```bash
python -m evals.swe_bench.runner --selfcheck            # offline gate (no net, no deps)
pip install datasets                                    # for the real corpus
python -m evals.swe_bench.runner --run --limit 20       # score retrieval on real tasks
python -m evals.swe_bench.runner --run --json           # machine-readable report
```

## What it measures — and what it doesn't

| | This harness | The full SWE-bench leaderboard |
|---|---|---|
| **Question** | Did the right *files* reach the window? | Did the issue get *fixed*? |
| **Oracle** | Gold-patch files (objective) | Test suite pass/fail |
| **Needs an LLM?** | No | Yes (a full coding agent) |
| **What it isolates** | NeuralMind's *retrieval* | An agent's *whole* solve loop |

NeuralMind is a context layer, not an agent. Retrieval recall is the honest thing
*it* controls; issue solve-rate depends on whichever agent consumes the context.
So this harness scores recall@k / MRR of the gold-patch files — the same metric,
from the same `neuralmind.quality` scorer, that gates the public benchmark.

**The end-to-end solve-rate arm is intentionally not built yet** (it needs an
`ANTHROPIC_API_KEY` and a sandboxed agent loop). Its interface — a future
`--solve` flag that wraps NeuralMind's context behind an agent and runs the
SWE-bench test harness — is sketched here so it can be added without reshaping the
runner. We will not publish a solve-rate number we haven't actually run.

## Why there are no committed leaderboard numbers (yet)

By design. The corpus is **derived from the canonical SWE-bench dataset at run
time** (`princeton-nlp/SWE-bench_Lite` via HuggingFace `datasets`), and gold files
are parsed from each task's `patch`. We deliberately **don't hardcode** base-commit
SHAs or gold-file lists in the repo — that's exactly the kind of stale, possibly
mis-stated data the project avoids. The only committed data is
[`fixture.json`](fixture.json), a tiny **synthetic** set that the offline
`--selfcheck` and the hermetic test ([`tests/test_swe_bench_harness.py`](../../tests/test_swe_bench_harness.py))
use to verify the patch parser and the metric math without a network.

Real numbers land in [`bench/swe_bench/`](../../bench/swe_bench/REPRODUCE.md) when
the harness is run with `datasets` installed and network access. Contributions of
real runs — including disappointing ones — are welcome.

## How it's wired (reuses the public-benchmark seam)

- `gold_files_from_patch(patch)` — parse the unified diff's `+++ b/…` post-images
  to basenames (the gold key). Pure stdlib, unit-tested.
- `_checkout_task(repo, base_commit, dest)` — single-commit fetch of
  `github.com/<repo>` at the exact SHA, fail-closed (reuses `evals/public/run.py`
  git helpers).
- scoring — `evals/public/backends.run_neuralmind` + `neuralmind.quality`, identical
  to every other NeuralMind retrieval measurement.
