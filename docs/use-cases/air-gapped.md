# Run NeuralMind air-gapped

> Goal: install and operate NeuralMind on a machine that has no
> outbound network access — no PyPI, no GitHub, no embedding-model
> downloads from S3 mid-build.

NeuralMind has always been local-first at runtime (zero data
exfiltration, fully offline once installed). The remaining
network dependencies are install-time only: the PyPI package
download, and ChromaDB's at-first-use embedding-model download. This
walkthrough covers both.

> If you only need offline *runtime* (you have internet during the
> initial install), regular `pip install neuralmind graphifyy` is
> already enough. This page is for the harder case: install *also*
> happens behind a firewall.

---

## TL;DR

```bash
# On a connected machine, with the same Python version as the target:
pip download neuralmind graphifyy --dest ./offline-bundle
python -c "from chromadb.utils import embedding_functions as ef; \
  ef.DefaultEmbeddingFunction()(['warm'])"        # warm the model cache
tar czf neuralmind-offline.tgz ./offline-bundle \
  -C ~/.cache/chroma onnx_models
# Move the tarball to the air-gapped machine, then:
tar xzf neuralmind-offline.tgz
pip install --no-index --find-links offline-bundle neuralmind graphifyy
mkdir -p ~/.cache/chroma && cp -r onnx_models ~/.cache/chroma/
neuralmind --help                          # works, offline.
```

---

## Step 1 — Bundle the wheels (on a connected machine)

`pip download` resolves the full transitive dependency tree and
downloads every wheel into a directory. The target machine then
installs via `--no-index --find-links` so PyPI is never reached.

```bash
mkdir -p offline-bundle
pip download neuralmind graphifyy \
  --dest offline-bundle \
  --python-version 3.12 \
  --platform manylinux_2_28_x86_64 \
  --only-binary=:all:
```

`--python-version` and `--platform` matter — they pin the wheels to
what the air-gapped machine will run. If your target is macOS arm64
substitute `--platform macosx_14_0_arm64`; for Windows
`--platform win_amd64`. Run `pip debug --verbose` on the target to
see what platform tags it accepts.

The resulting `offline-bundle/` contains every wheel: `neuralmind`,
`graphifyy`, `chromadb`, `mcp`, `pyyaml`, `toml`, plus all their
transitives (~50-80 wheels, ~150-250 MB depending on Python version).

---

## Step 2 — Pre-cache the ChromaDB embedding model

ChromaDB's `DefaultEmbeddingFunction` downloads an ONNX model on
first use, from S3 (`https://chroma-onnx-models.s3.amazonaws.com/`).
On an air-gapped machine, that download fails and `neuralmind build`
hangs or errors. Pre-cache the model on the connected machine:

```bash
# Force the model download into the standard cache location
python - <<'PY'
from chromadb.utils import embedding_functions
ef = embedding_functions.DefaultEmbeddingFunction()
ef(["warm the cache"])    # triggers the ONNX download
PY
```

The model lands at `~/.cache/chroma/onnx_models/all-MiniLM-L6-v2/`
(Linux/macOS) or `%USERPROFILE%\.cache\chroma\onnx_models\` (Windows).
Total size: ~85 MB.

> **ChromaDB-free option (v0.21.0+).** The opt-in `turbovec` backend
> (`backend: turbovec` in `neuralmind-backend.yaml`) owns embeddings via a
> bundled `OnnxMiniLMEmbedder` — same `all-MiniLM-L6-v2` model, no ChromaDB.
> For air-gapped use, pre-stage the extracted model folder anywhere and point
> `NEURALMIND_ONNX_MODEL_DIR` at it (it also auto-reuses an existing
> `~/.cache/chroma/...` model, so the cache you staged above already works):
>
> ```bash
> export NEURALMIND_ONNX_MODEL_DIR=/opt/models/all-MiniLM-L6-v2/onnx
> ```

If your target has a different cache directory convention (NFS home
mount, containerised cache, etc.), set `CHROMA_CACHE_DIR` on both
machines to a path you control end-to-end.

---

## Step 3 — Transfer to the air-gapped machine

Bundle both pieces into a single tarball for transfer:

```bash
tar czf neuralmind-offline.tgz \
  offline-bundle/ \
  -C ~/.cache/chroma onnx_models/
```

Move the tarball via your usual sneakernet path (USB, cross-domain
solution, signed package, etc.).

---

## Step 4 — Install on the air-gapped machine

```bash
tar xzf neuralmind-offline.tgz

# Install NeuralMind + graphify from the wheel bundle, no PyPI:
pip install \
  --no-index \
  --find-links offline-bundle/ \
  neuralmind graphifyy

# Restore the ChromaDB model cache:
mkdir -p ~/.cache/chroma
cp -r onnx_models ~/.cache/chroma/

# Verify
neuralmind --help
python -c "import neuralmind; print(neuralmind.__version__)"
```

If `pip install` complains about a missing wheel, the most common
cause is a platform-tag mismatch: re-run `pip download` on the
connected machine with the target's actual platform tag (run
`pip debug --verbose` there to see the supported tags).

---

## Step 5 — Verify offline operation end-to-end

```bash
cd /path/to/your-project
graphify update .
neuralmind build .
neuralmind wakeup .
```

Each command should complete without any outbound network requests.
Confirm with `ss -tnp` or `lsof -i` on the connected interface:

```bash
ss -tnp | grep -E 'python|neuralmind|chroma'   # should show nothing
```

---

## Docker, offline

If you're running NeuralMind via the repo-root `Dockerfile`, the same
bundle-and-transfer pattern works:

```bash
# On the connected machine
docker save ghcr.io/dfrostar/neuralmind:v0.9.0 \
  -o neuralmind-image.tar
gzip neuralmind-image.tar

# Sneakernet over

# On the air-gapped machine
gunzip neuralmind-image.tar.gz
docker load -i neuralmind-image.tar
# The image is pre-baked with all transitive deps — no PyPI needed at
# image-runtime. The ChromaDB model cache still needs the offline
# bundle from Step 2 above, mounted into the container at /home/
# neuralmind/.cache/chroma/.
docker run --rm \
  -v "$PWD/onnx_models:/home/neuralmind/.cache/chroma/onnx_models:ro" \
  -v "$PWD/your-project:/project" \
  ghcr.io/dfrostar/neuralmind:v0.9.0 \
  neuralmind build /project
```

The Dockerfile's runtime stage pre-installs all transitive wheels in
the builder stage, so the runtime container never reaches PyPI even
when network is available. See [`Dockerfile`](../../Dockerfile) for
the multi-stage layout.

---

## Updates

For each NeuralMind release, repeat Step 1 (re-bundle wheels) and
Step 3 (transfer). The ChromaDB model cache is stable across NeuralMind
versions — only re-do Step 2 if ChromaDB ships a new default embedding
model (rare; check the release notes when bumping `chromadb>=`).

---

## Troubleshooting

### `pip install` fails with "No matching distribution found for X"

The wheel for dep `X` wasn't in your bundle. Either:
- Re-run Step 1 with explicit `--platform` flags matching the target
- Add the missing wheel manually: `pip download X==<version> --dest offline-bundle/`

### ChromaDB still tries to download the model

`CHROMA_CACHE_DIR` mismatch between the two machines. Set it
explicitly on both to a known path you bundle:

```bash
export CHROMA_CACHE_DIR=/opt/neuralmind/chroma-cache
```

### `neuralmind build` hangs at "Embedding…"

Almost always the ChromaDB model not being found. Check that the
`onnx_models/all-MiniLM-L6-v2/` subdirectory exists under
`$CHROMA_CACHE_DIR` (or `~/.cache/chroma/`) and is readable.

---

## Compliance posture (for the auditor)

The air-gapped install is the strictest deployment posture NeuralMind
supports:

- **No outbound network at any phase** (install, build, runtime, query).
- **Wheel set is auditable** — every transitive dep is a file on disk
  you can hash, mirror, and review independently. See the [SBOM
  attached to each tagged release](https://github.com/dfrostar/neuralmind/releases)
  (`neuralmind-vX.Y.Z.sbom.json`, CycloneDX JSON) for the full graph
  with versions + licenses.
- **No telemetry, no remote logging, no automatic update checks.**
  See [`docs/SECURITY-GUIDE.md`](../SECURITY-GUIDE.md) and
  [`docs/COMPLIANCE-SUMMARY.md`](../COMPLIANCE-SUMMARY.md).
- **Data residency** is fully under operator control — synapse store
  (`.neuralmind/synapses.db`), ChromaDB index
  (`graphify-out/neuralmind_db/`), and event log
  (`.neuralmind/events.jsonl`) all live where you put them.

---

## Related

- [`Dockerfile`](../../Dockerfile) — multi-stage image with all
  transitive deps pre-wheeled
- [`docs/SECURITY-GUIDE.md`](../SECURITY-GUIDE.md) — threat model,
  encryption, secrets
- [`docs/COMPLIANCE-SUMMARY.md`](../COMPLIANCE-SUMMARY.md) — NIST AI
  RMF + SOC 2 + GDPR consolidation
- [`docs/use-cases/offline-regulated.md`](offline-regulated.md) —
  broader "regulated industry" walkthrough
