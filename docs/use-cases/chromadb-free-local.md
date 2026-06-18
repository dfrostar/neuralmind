# Slim & sovereign: a ChromaDB-free local stack

**Best for:** security-sensitive teams, minimal-footprint installs, and anyone
who wants fewer moving parts. **Goal:** run NeuralMind's full vector retrieval —
embedding *and* search — with **zero ChromaDB**.

*The turbovec/ONNX stack is the **default** since v0.29.0; it has existed since v0.21.0.*

## Why you'd want this

As of **v0.29.0 the default install is ChromaDB-free** — the `turbovec` backend
ships out of the box and ChromaDB is an opt-in extra. Historically ChromaDB was
the default; it works well, but pulls in a large transitive dependency tree (a
web server, a kubernetes client, OpenTelemetry, gRPC, …) and has carried the
recurring **CVE-2026-45829** advisory. The `turbovec` backend replaces it
entirely:

| Concern | ChromaDB (opt-in `[chromadb]`) | `turbovec` (ChromaDB-free, **default**) |
|---|---|---|
| ANN search | ChromaDB HNSW | Google **TurboQuant** compressed index |
| Embeddings | ChromaDB's MiniLM | bundled `OnnxMiniLMEmbedder` (**byte-identical** vectors) |
| Metadata store | ChromaDB | local SQLite (stdlib) |
| Vector size on disk/in RAM | 1× | **~8–16× smaller** |
| Advisory surface | CVE-2026-45829 | gone on this path |
| Retrieval quality | baseline | **at/above parity** (fact recall 0.744 → 0.800) |

Vectors are **byte-identical** to the default backend (same `all-MiniLM-L6-v2`
model; verified cosine 1.0), so you give up nothing in answer quality — you just
shed dependencies and shrink the index.

## Step 1 — Install the self-contained extra

```bash
pip install "neuralmind[turbovec]"
# pulls: turbovec, onnxruntime, tokenizers, numpy — no ChromaDB needed
```

## Step 2 — Select the backend

Drop a `neuralmind-backend.yaml` at your repo root:

```yaml
backend: turbovec
```

That's it — `neuralmind build` and every query now use the ChromaDB-free path.
Other accepted values: `graph`/`chroma` (default), `in_memory` (offline tests).

## Step 3 — Build and query as usual

```bash
neuralmind build .
neuralmind query "where is JWT verification handled?"
```

The index lands in `<project>/.neuralmind/` (a TurboVec `index.tvim` + a SQLite
`store.sqlite`), 8–16× smaller than the equivalent ChromaDB collection.

## Air-gapped / no-network installs

The embedder needs the `all-MiniLM-L6-v2` ONNX model (~90 MB) once. Pre-stage it
and point an env var at it — no download at runtime:

```bash
export NEURALMIND_ONNX_MODEL_DIR=/opt/models/all-MiniLM-L6-v2/onnx
```

It also transparently reuses an existing `~/.cache/chroma/...` model if you have
one. Full offline walkthrough: [air-gapped](./air-gapped.md).

## How it's verified

This isn't a claim — it's gated. The backend parity job
(`python -m evals.parity.run`) and the faithfulness eval run on every PR; the
embedder's byte-for-byte equivalence to ChromaDB is checked directly. See
[Benchmarks](../wiki/Benchmarks.md) for the numbers and how to reproduce them.

## What's next

ChromaDB stays the *default* for now; `turbovec` is the opt-in path while it
bakes. Flipping the default (with a one-time reindex migration) and dropping
ChromaDB from the core dependencies are the staged next steps — see issue #204.
