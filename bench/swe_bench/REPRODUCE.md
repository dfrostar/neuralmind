# SWE-bench retrieval — reproduce

This directory holds committed results from the SWE-bench **retrieval** eval
(`evals/swe_bench/`). It measures gold-patch-file recall@k / MRR — *not* an
end-to-end issue solve-rate. See [`evals/swe_bench/README.md`](../../evals/swe_bench/README.md)
for the honest scope.

## Status

No `results.json` is committed yet. By design, this harness derives its corpus
from the **canonical SWE-bench dataset at run time** rather than hardcoding
base-commit SHAs / gold files, so a real run on a machine with `datasets` + network
is what produces the numbers here. We do not commit fabricated or placeholder
metrics.

## Run it

```bash
pip install -e ".[dev]" datasets tiktoken
python -m evals.swe_bench.runner --run --dataset princeton-nlp/SWE-bench_Lite --limit 50
# writes bench/swe_bench/results.json
```

Each task is scored by cloning `github.com/<repo>` at the task's `base_commit`,
building a NeuralMind index, querying the `problem_statement`, and checking whether
the gold-patch files land in the retrieved context — via the same
`neuralmind.quality` scorer the public benchmark uses.

## Verify offline (no network, no dataset)

```bash
python -m evals.swe_bench.runner --selfcheck       # schema + parser + metric math
python -m unittest tests.test_swe_bench_harness     # hermetic unit tests
```

## What a committed `results.json` will contain

`harness`, `dataset`, `oracle: gold-patch-files`, `n_scored`, `n_skipped` (with
reasons), a `summary` (mean gold-file recall, found-rate, MRR, median tokens), and
per-task rows. Every skipped task is reported with its reason — no silent drops.
