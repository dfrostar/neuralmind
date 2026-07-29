# NeuralMind v0.29.0 — ChromaDB-free by default

**Release Date:** June 2026

## TL;DR

On mainstream platforms, `pip install neuralmind` no longer pulls **ChromaDB**.
The default install now uses the **ChromaDB-free turbovec/ONNX** backend
(TurboQuant compressed index + a bundled MiniLM embedder whose vectors are
byte-identical to ChromaDB's), removing ChromaDB's large transitive dependency
tree — and the recurring **chromadb CVE** surface the project already tracks —
from the default install.

```bash
pip install neuralmind                 # ChromaDB-free (turbovec/ONNX) on wheel-covered platforms
pip install "neuralmind[chromadb]"     # force the ChromaDB backend anywhere
```

## Platform coverage (the install never breaks)

The vector backend is **platform-gated by wheel availability**, so a base
`pip install neuralmind` always resolves to *prebuilt wheels* (no Rust/C++
toolchain needed) and a working backend on every platform:

| Platform | Default backend |
|---|---|
| Linux x86_64 / aarch64 (glibc ≥ 2.28) | **turbovec/ONNX** (ChromaDB-free) |
| macOS arm64 (Apple Silicon) | **turbovec/ONNX** (ChromaDB-free) |
| Windows x86_64 | **turbovec/ONNX** (ChromaDB-free) |
| macOS x86_64 (Intel), Windows ARM | **ChromaDB** (auto-installed fallback — turbovec has no wheel) |

`auto` backend selection prefers turbovec when present, else ChromaDB — so the
fallback is transparent. **Caveat:** PEP 508 markers can't distinguish musl from
glibc, so **Alpine/musl** (and pre-2.28-glibc) Linux still resolve to turbovec
and need a build toolchain or `pip install "neuralmind[chromadb]"` — use a glibc
base image (`python:slim`) rather than `python:alpine`.

Everything that was already true stays true: retrieval behaviour is unchanged
(turbovec vectors are at/above ChromaDB parity on the gold set), and an explicit
`backend: graph` in `neuralmind-backend.yaml` still selects ChromaDB.

## The honest trade-off

"ChromaDB-free" is **not** a claim of "smaller install." The turbovec path pulls
`onnxruntime` (a heavy native wheel). The win is precise:

- **Removed from the default install:** the ChromaDB dependency tree
  (FastAPI / grpcio / OpenTelemetry / kubernetes client / …) **and its CVE
  surface**.
- **Added to the default install:** `onnxruntime` + `tokenizers` + `numpy`.
- **Net:** a CVE-tree-free default with one focused native dependency instead of
  ChromaDB's sprawl — not fewer total megabytes.

## What the agent / user actually sees

- A fresh `pip install neuralmind` resolves the backend to **turbovec**
  automatically (`neuralmind doctor` reports it). Building and querying work with
  zero ChromaDB on disk.
- **Upgrading a project that was indexed with ChromaDB:** the first build after
  upgrading performs a **one-time auto-reindex from `graph.json`** into turbovec
  (the existing v0.22 migration). Your old ChromaDB index is **not deleted** — it
  stays as a selectable fallback if you install `[chromadb]` and set
  `backend: graph`.
- **Selecting the ChromaDB backend without installing it** now raises an
  **actionable error** — *"the 'graph' (ChromaDB) backend needs ChromaDB … `pip
  install "neuralmind[chromadb]"`"* — instead of an opaque `ModuleNotFoundError`.

### Per-agent expectations

| Agent | What changes in v0.29.0 |
|-------|--------------------------|
| **Claude Code** | Default install is ChromaDB-free; build/query/hooks unchanged. A previously chroma-indexed repo auto-reindexes once into turbovec. |
| **Cursor / Cline** | Same MCP tools; the bundled backend is now turbovec out of the box. |
| **Generic MCP client** | No tool or contract change; the default vector backend is turbovec. |
| **Contributors / CI** | `pip install -e ".[dev,chromadb]"` to run the full suite (both backends); the chroma-specific tests skip cleanly on a ChromaDB-free install. |

## Why this was low-risk

The migration was staged across v0.21 (the turbovec/ONNX backend) and v0.22
(`import neuralmind` made ChromaDB-free via a lazy `GraphEmbedder` export, and
`auto` made to prefer turbovec when present). v0.29.0 simply flips which
dependency set is installed by default:

- `import neuralmind` was already ChromaDB-free (regression-guarded).
- The `auto` backend already preferred turbovec when its deps imported.
- The chroma→turbovec one-time auto-reindex already existed.

## What ships

- **`pyproject.toml`** — `turbovec`/`onnxruntime`/`tokenizers` are base deps
  **gated by platform markers** (where wheels exist); `chromadb` is a
  marker-conditional **fallback** base dep on uncovered platforms (Intel macOS,
  Windows ARM) *and* the opt-in **`[chromadb]`** extra everywhere; `[turbovec]`
  kept as an empty back-compat alias.
- **`neuralmind/backend_manager.py`** — actionable error when the chroma backend
  is selected without the `[chromadb]` extra.
- **CI** — the test matrix installs `[dev,chromadb]` (both backends exercised);
  the Fresh Install job asserts the default install is ChromaDB-free, resolves to
  turbovec, and that selecting chroma without the extra raises the install hint.
- **Tests** — chroma-specific tests/fixtures guarded so the suite passes on a
  ChromaDB-free install while running fully under `[dev,chromadb]`.
- **`docs/prd/chromadb-free-by-default.md`** — the PRD this release executes.

## Upgrade

```bash
pip install --upgrade neuralmind
```

- **Want to keep ChromaDB?** `pip install --upgrade "neuralmind[chromadb]"` and
  set `backend: graph` in `neuralmind-backend.yaml`.
- **Otherwise:** nothing to do — the first build auto-reindexes into turbovec and
  retrieval is unchanged. Existing `pip install "neuralmind[turbovec]"` commands
  still resolve (the extra is now an empty alias).
