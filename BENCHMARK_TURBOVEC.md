# TurboVec vs. ChromaDB-free MiniLM — memory/latency benchmark

A two-script toolkit that answers the specific follow-up raised in the
[v0.21.0 release notes](RELEASE_NOTES_v0.21.0.md):

> "A large-synthetic-repo memory/latency benchmark is a follow-up."

It runs the two backends from `neuralmind.backend_manager.create_backend`
(`chroma` and `turbovec`) against the **same graph**, on the **same machine**,
with **identical queries**, and measures:

- **indexing latency** — `load_graph` → `embed_nodes(force=True)` wall time;
- **search latency** — p50 / p95 / mean over many warm repeats, plus a
  per-query breakdown so a single regressing query type is visible;
- **on-disk size** — bytes the backend's index directory occupies;
- **peak RSS** — `getrusage(RUSAGE_SELF).ru_maxrss`, the ground-truth "how much
  memory did this actually take" number;
- **tracemalloc peak** — Python-side allocation only (a hint, not the truth);
- **query-level parity** — each backend's top-k result ids, so the report can
  compute Jaccard@k and recall-of-chroma's-top-k.

## Why separate subprocesses

Each backend runs in its own **spawn-context subprocess** (the benchmark
re-invokes itself with a hidden `--_worker` flag), so:

- chroma's transitive import tree (FastAPI, kubernetes client, OpenTelemetry,
  grpcio, …) never inflates the turbovec memory measurement;
- a crash in one backend doesn't tank the other;
- `getrusage(RUSAGE_SELF)` reads the per-process high-water mark cleanly.

The parent process builds the synthetic repo and the shared `graph.json`
**once**; the workers only index and query.

## Install

```bash
pip install "neuralmind[turbovec]==0.21.0"
# the turbovec extra pulls turbovec, onnxruntime, tokenizers, numpy
pip install psutil   # used by the worker for live RSS sampling
```

First-time turbovec runs download the `all-MiniLM-L6-v2` ONNX model (~90 MB).
To skip that on subsequent fresh-machine runs, pre-stage it:

```bash
export NEURALMIND_ONNX_MODEL_DIR=/path/to/staged/onnx_model_dir
```

## Run on a synthetic 600-file repo (no setup)

```bash
python benchmark_turbovec.py --out results.json
python report_turbovec.py results.json --out report.md
```

The synthetic repo is generated in `/tmp/nm_bench_repo_<pid>`, indexed with the
built-in tree-sitter graph generator (no `graphify` required), and cleaned up at
the end (`--keep-repo` to keep it).

## Run on your own repo

```bash
# First time (no graph yet): pass --build to generate one via tree-sitter
python benchmark_turbovec.py --repo ~/code/my-project --build --out results.json

# Subsequent runs (graph already exists at graphify-out/graph.json)
python benchmark_turbovec.py --repo ~/code/my-project --out results.json

python report_turbovec.py results.json --out report.md
```

The repo should contain at least 500 source files (`.py`, `.ts`, `.go` — the
languages supported by NeuralMind's built-in extractors as of v0.16.0). Fewer
files only emits a warning; the benchmark still runs.

## Flags

`benchmark_turbovec.py`:

| flag | default | meaning |
|---|---|---|
| `--out` | `results.json` | output JSON path |
| `--repo` | _(synthetic)_ | benchmark a real repo instead of the synthetic one |
| `--build` | off | (with `--repo`) generate `graphify-out/graph.json` via tree-sitter |
| `--files` | `600` | synthetic repo file count |
| `--keep-repo` | off | don't delete the synthetic repo afterwards |
| `--top-k` | `10` | results requested per query |
| `--repeat` | `20` | timed repeats per query (for stable percentiles) |
| `--warmup` | `2` | unmeasured warm-up runs per query |
| `--backends` | `chroma,turbovec` | comma-separated backends to compare |
| `--queries-file` | _(built-in set)_ | newline-delimited custom queries |

`report_turbovec.py`:

| flag | default | meaning |
|---|---|---|
| `--out` | `report.md` | output Markdown path |

## What the report tells you

`report_turbovec.py` reads the JSON and writes a Markdown report with:

- **A one-line verdict** — 🟢 yes / 🟡 cautiously yes / 🛑 not yet / ⚪
  inconclusive — based on parity *and* performance signals.
- **Environment provenance** — versions of neuralmind, turbovec, chromadb,
  onnxruntime, tokenizers, numpy, Python, platform, CPU count, repo size.
- **Headline table** — indexing latency, search p50/p95/mean, on-disk size,
  peak RSS, tracemalloc peak, with signed-percent deltas (turbovec vs. chroma).
- **Parity section** — mean Jaccard@k, recall of chroma's top-k by turbovec, and
  a (collapsed) per-query overlap table.
- **Per-query latency table** — side-by-side ms so a single regressing query
  type is visible.
- **Caveats** — first-run model download, what tracemalloc does and doesn't
  capture, the experimental/POC label on turbovec.

The verdict thresholds: 🟢 needs mean Jaccard@k ≥ 0.70 **and** recall ≥ 0.80
with no performance regression; 🟡 if parity holds but latency/RSS/disk regress,
or if parity is only marginal (Jaccard ≥ 0.50, recall ≥ 0.60); 🛑 below that; ⚪
if either backend failed to complete.

## What's intentionally *not* in this benchmark

- **Faithfulness.** NeuralMind has its own gold-set eval (`evals/`) that scores
  fact recall and top-k hit@4; the v0.21.0 notes already report parity within
  the 0.10 gate tolerance there. The Jaccard signal here is a complementary
  query-level sanity check, not a replacement.
- **Recall vs. ground truth.** Without labelled (query → correct node) pairs for
  your repo, "recall" here is "recall vs. chroma", which assumes chroma is
  correct. Run `neuralmind eval` for ground-truth recall.
- **Concurrent-load behavior.** Single-threaded latency only. The TurboVec
  release claims SIMD wins under load; that's a separate exercise.
- **Cold-cache effects.** Both backends run warm. Cold-start time is dominated
  by the ONNX model load (~1–2 s), identical across both in v0.21.0 since they
  share the same MiniLM model.

## Caveats / known gotchas

- `getrusage().ru_maxrss` is in **KB on Linux, bytes on macOS** — the benchmark
  normalizes to MB before reporting.
- `tracemalloc` only sees **Python-side** allocations. numpy buffers,
  onnxruntime's session arena, and SQLite page cache show up in RSS but not in
  tracemalloc. Use RSS as the ground truth for memory and tracemalloc as a hint
  about how much of that was Python objects.
- If `psutil` isn't installed the worker fails at its `import psutil` line —
  install it first.
- The chroma backend triggers a chromadb telemetry-silencing patch on import
  (see `neuralmind/__init__.py`); the subprocess isolation keeps that from
  polluting the turbovec measurement.
