# NeuralMind v0.21.0 — ChromaDB-free retrieval (owned embeddings + TurboVec)

**The headline:** NeuralMind can now do its entire vector-retrieval job — embed
*and* search — with **zero ChromaDB**. v0.20.0 moved the ANN search to
[TurboVec](https://github.com/RyanCodrai/turbovec) (Google Research's
**TurboQuant** compressed index). v0.21.0 moves the last ChromaDB-only
responsibility, **embedding generation**, into a bundled module — so the
`turbovec` backend is fully self-contained.

This is the foundation for retiring ChromaDB entirely: it drags in a large
transitive tree (FastAPI, kubernetes client, OpenTelemetry, grpcio, …) and the
recurring **CVE-2026-45829** advisory surface (see `SECURITY.md`).

## What's new

- **`neuralmind/onnx_embedder.py` — `OnnxMiniLMEmbedder`.** A ChromaDB-free
  `all-MiniLM-L6-v2` text embedder on just `onnxruntime` + `tokenizers` +
  `numpy`. It produces vectors **byte-identical** to ChromaDB's
  `DefaultEmbeddingFunction` — same model, same pipeline (tokenize → ONNX →
  attention-masked mean-pool → L2-normalize). Verified: cosine `1.0`, max
  elementwise diff `0.0`.
- **The `turbovec` backend is now ChromaDB-free end to end.** Vectors →
  TurboVec `IdMapIndex`; text + metadata + the node-id↔uint64 map → local
  SQLite; embeddings → `OnnxMiniLMEmbedder`. No ChromaDB import on this path.
- **Lazy backend factory.** `create_backend` now imports `GraphEmbedder`
  (ChromaDB) only when the chroma backend is actually selected, so choosing
  `turbovec` doesn't construct the Chroma stack.

## Why it matters

- **Retires a class of recurring problems** — the held `chromadb==1.5.8` pin,
  the CVE watcher, and the Dependabot overhang all exist because of ChromaDB.
- **Sharply smaller footprint** once ChromaDB is dropped — the MiniLM model is
  the same ~90 MB either way, but the dependency *tree* shrinks dramatically.
- **8–16× smaller vectors** via TurboQuant; memory headroom for large monorepos.
- **Stronger "100% local" story** — fewer moving parts, no server code anywhere.

## Parity (faithfulness gold set, identical embeddings; only the ANN differs)

| backend | fact recall | top-k hit@4 |
|---|---:|---:|
| chroma (float32 HNSW) | 0.744 | 0.759 |
| **turbovec (4-bit, owned embedder)** | **0.800** | 0.759 |
| turbovec (2-bit) | 0.744 | 0.759 |

At/above parity within the 0.10 gate tolerance, at 8–16× compression.

## How to enable it

Opt in per project with a `neuralmind-backend.yaml` at the repo root:

```yaml
backend: turbovec
```

Install the extra: `pip install "neuralmind[turbovec]"` (pulls `turbovec`,
`onnxruntime`, `tokenizers`, `numpy`). The MiniLM model is resolved in this
order, downloading only as a last resort:

1. `$NEURALMIND_ONNX_MODEL_DIR` (if it contains `model.onnx`);
2. NeuralMind's cache (`~/.cache/neuralmind/onnx_models/...`);
3. an existing ChromaDB cache (`~/.cache/chroma/onnx_models/...`) — reused with
   no refetch on a box that already has ChromaDB;
4. the same SHA256-verified archive ChromaDB downloads.

For air-gapped installs, pre-stage the model and point `NEURALMIND_ONNX_MODEL_DIR`
at it — no network needed.

## Per-agent expectations

| Agent | What changes in v0.21.0 |
|-------|--------------------------|
| **Claude Code** | Nothing by default — chroma stays the default backend. Opt in via `neuralmind-backend.yaml`. |
| **Cursor / Cline** | Same MCP tools, same retrieval. |
| **Generic MCP client** | No new tool; backend choice is config-only. |
| **Contributors / CI** | New `OnnxMiniLMEmbedder`; `turbovec` extra now includes onnxruntime + tokenizers; lazy chroma import in the factory. |

## Honest scope & what's next

- **ChromaDB is still the default and still a core dependency.** This release
  makes a complete ChromaDB-free *alternative*; it does not yet flip the default
  or remove the dependency. Importing the `neuralmind` package still touches
  ChromaDB (the `GraphEmbedder` export + a telemetry-silencing patch in
  `__init__`).
- **Next (v0.22):** make the whole package import without ChromaDB, flip the
  default to `turbovec` *with a chroma fallback* + a one-time reindex migration,
  then (v0.23) drop `chromadb` from the core dependency list. Staged on purpose
  so the new path bakes before it becomes everyone's default.
- Quantization is approximate; parity is gated on the reference fixture. A
  large-synthetic-repo memory/latency benchmark now ships as a standalone
  toolkit — see [`BENCHMARK_TURBOVEC.md`](BENCHMARK_TURBOVEC.md)
  (`benchmark_turbovec.py` + `report_turbovec.py`). It runs both backends in
  isolated spawn subprocesses on the same graph with identical queries and
  reports indexing latency, search p50/p95, on-disk size, peak RSS, and
  query-level parity (Jaccard/recall) with a one-line adopt/hold verdict.
