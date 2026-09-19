# Run NeuralMind air-gapped

> Goal: install and operate NeuralMind on a machine that has no
> outbound network access — no PyPI, no GitHub, no embedding-model
> downloads from S3 mid-build.

**Does NeuralMind put any of my code on the wire? No.** That is the
question this page exists to answer, so it is answered first and exactly,
rather than with a slogan. Note the scope: this is about what *NeuralMind*
sends. Your agent still forwards whatever context it selects to its own
model, and nothing on this page changes that.

Never transmitted by NeuralMind: your source, file paths, query text,
results, or any identifier. There is no telemetry, no remote logging and no
update check. Every outbound-capable path in the package, in full:

| Path | Target | Carries your data? |
|---|---|---|
| `neuralmind/onnx_embedder.py` | one fixed HTTPS URL, `GET`, SHA256-pinned | **No.** It downloads a public model. The request carries nothing about your repository. |
| `neuralmind/daemon_client.py` | `127.0.0.1` | **No.** A loopback socket to NeuralMind's own daemon — it is not an external connection at all. |
| `neuralmind/local_client.py` | `http://localhost:11434` (Ollama default) | Loopback, unless you repoint `endpoint` yourself. |

So there is exactly one request that reaches the internet, it is a plain
file download, and an observer learns only that this host fetched a public
model — nothing about your codebase. It is also avoidable, which is what
the rest of this page is for. The remaining network dependencies are
install-time only: the PyPI package download, and NeuralMind's own
first-use embedding-model download.

<!-- claims-guard:allow — names the retired phrase in order to retire it. Note
     it currently also escapes FORBIDDEN by being line-wrapped, which is the
     guard's line-by-line matching hole; this marker keeps the disavowal legal
     once that hole is closed. -->
> **On wording, for anyone quoting this page.** That fetch is NeuralMind's
> own code calling `urllib`, not a dependency's, so "NeuralMind makes no
> network calls of its own" is false on a cold install and should not be
> used. "No repository content is transmitted" is true, and is the
> stronger claim anyway. Note also the boundary this page cannot move:
> your agent still sends whatever context it selects to whatever model you
> point it at.

> If you only need offline *runtime* (you have internet during the
> initial install), regular `pip install neuralmind` is
> already enough. This page is for the harder case: install *also*
> happens behind a firewall.

---

## TL;DR

```bash
# On a connected machine, with the same Python version as the target:
pip download neuralmind --dest ./offline-bundle   # append graphifyy for the optional graphify backend
python -c "from neuralmind.onnx_embedder import OnnxMiniLMEmbedder as E; E()(['warm'])"
tar czf neuralmind-offline.tgz ./offline-bundle \
  -C ~/.cache/neuralmind onnx_models
# Move the tarball to the air-gapped machine, then:
tar xzf neuralmind-offline.tgz
pip install --no-index --find-links offline-bundle neuralmind
mkdir -p ~/.cache/neuralmind && cp -r onnx_models ~/.cache/neuralmind/
neuralmind --help                          # works, offline.
```

> Earlier revisions warmed the cache through
> `chromadb.utils.embedding_functions`. That no longer works on a default
> install: the default stack has been ChromaDB-free since v0.29.0, so
> importing `chromadb` raises `ImportError` on Linux, macOS arm64 and
> Windows x64. Use the command above.

---

## Step 1 — Bundle the wheels (on a connected machine)

`pip download` resolves the full transitive dependency tree and
downloads every wheel into a directory. The target machine then
installs via `--no-index --find-links` so PyPI is never reached.

```bash
mkdir -p offline-bundle
pip download neuralmind \
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
`turbovec`, `onnxruntime`, `tokenizers`, `numpy`, `mcp`, `pyyaml`,
`toml`, the tree-sitter grammars, plus all their transitives (~50-80 wheels, ~150-250 MB depending on Python
version). Append `graphifyy` to the download command if you want the
optional graphify backend in the bundle.

---

## Step 2 — Pre-cache the embedding model

On the first embed with no cached model, `neuralmind/onnx_embedder.py`
downloads the `all-MiniLM-L6-v2` ONNX archive over HTTPS from
`https://chroma-onnx-models.s3.amazonaws.com/` and verifies it against a
SHA256 pinned in that file. On an air-gapped machine that request fails
and `neuralmind build` errors at the embedding step. Pre-cache it on the
connected machine:

```bash
# Force the model download into the standard cache location
python -c "from neuralmind.onnx_embedder import OnnxMiniLMEmbedder as E; E()(['warm the cache'])"
```

The model lands at `~/.cache/neuralmind/onnx_models/all-MiniLM-L6-v2/onnx/`
(Linux/macOS) or `%USERPROFILE%\.cache\neuralmind\onnx_models\`
(Windows). Size is unchanged from earlier releases — it is the same
artifact ChromaDB ships, ~85 MB extracted.

**Where it looks, in order.** Pre-seeding any of the first three removes
the download entirely:

1. `$NEURALMIND_ONNX_MODEL_DIR`, if it holds both `model.onnx` and `tokenizer.json`
2. `~/.cache/neuralmind/onnx_models/all-MiniLM-L6-v2/onnx/`
3. `~/.cache/chroma/onnx_models/all-MiniLM-L6-v2/onnx/` — so a machine
   that already has a ChromaDB-warmed model reuses it with no refetch
4. otherwise, download into (2)

For a read-only, shared or containerised mount, stage the extracted
folder wherever you like and point at it explicitly. This is the most
robust option and the one to prefer:

```bash
export NEURALMIND_ONNX_MODEL_DIR=/opt/models/all-MiniLM-L6-v2/onnx
```

> **If you deliberately run the ChromaDB backend**, the steps above stage
> the wrong cache and the air-gapped build will still fail. ChromaDB does
> not consult `~/.cache/neuralmind/`; the resolution order in this section
> is NeuralMind's embedder's, not ChromaDB's. ChromaDB reads
> `~/.cache/chroma/onnx_models/` only.
>
> This applies on platforms with no turbovec wheel (notably Intel macOS and
> Windows ARM), where ChromaDB is the automatic fallback, and wherever
> `backend: chroma` is set explicitly. Warm and stage that tree as well:
>
> ```bash
> # On the connected machine, in addition to the step above:
> python -c "from chromadb.utils import embedding_functions as ef; ef.DefaultEmbeddingFunction()(['warm'])"
> tar czf neuralmind-offline-chroma.tgz -C ~/.cache/chroma onnx_models
>
> # On the air-gapped machine:
> mkdir -p ~/.cache/chroma && tar xzf neuralmind-offline-chroma.tgz -C ~/.cache/chroma
> ```
>
> `CHROMA_CACHE_DIR` relocates ChromaDB's cache and is the right switch on
> that backend. It has **no effect** on the default path, where
> `onnx_embedder.py` hardcodes `~/.cache/chroma` as its third candidate —
> there, use `NEURALMIND_ONNX_MODEL_DIR`.
>
> Staging both trees is harmless and makes the bundle backend-agnostic.

---

## Step 3 — Transfer to the air-gapped machine

Bundle both pieces into a single tarball for transfer:

```bash
tar czf neuralmind-offline.tgz \
  offline-bundle/ \
  -C ~/.cache/neuralmind onnx_models/
```

Move the tarball via your usual sneakernet path (USB, cross-domain
solution, signed package, etc.).

---

## Step 4 — Install on the air-gapped machine

```bash
tar xzf neuralmind-offline.tgz

# Install NeuralMind from the wheel bundle, no PyPI:
pip install \
  --no-index \
  --find-links offline-bundle/ \
  neuralmind

# Restore the model cache:
mkdir -p ~/.cache/neuralmind
cp -r onnx_models ~/.cache/neuralmind/

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
neuralmind build .
neuralmind wakeup .
```

Each command should complete without any outbound network requests.
Confirm with `ss -tnp` or `lsof -i` on the connected interface:

```bash
ss -tnp | grep -E 'python|neuralmind'   # should show nothing
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
# image-runtime. The model cache still needs the offline bundle from
# Step 2 above, mounted at /home/neuralmind/.cache/neuralmind/ (or point
# NEURALMIND_ONNX_MODEL_DIR at a mount of your choosing).
docker run --rm \
  -v "$PWD/onnx_models:/home/neuralmind/.cache/neuralmind/onnx_models:ro" \
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
Step 3 (transfer). The model cache is stable across NeuralMind versions —
the artifact is pinned by SHA256 in `onnx_embedder.py`, so Step 2 only
needs redoing if that pin changes (rare; it is a one-line diff there).

---

## Troubleshooting

### `pip install` fails with "No matching distribution found for X"

The wheel for dep `X` wasn't in your bundle. Either:
- Re-run Step 1 with explicit `--platform` flags matching the target
- Add the missing wheel manually: `pip download X==<version> --dest offline-bundle/`

### It still tries to download the model

The staged folder is not where the resolver looks, or is incomplete. It
requires **both** `model.onnx` and `tokenizer.json`; a folder holding only
one is skipped silently and the download proceeds. Check the candidates:

```bash
ls "$NEURALMIND_ONNX_MODEL_DIR" \
   ~/.cache/neuralmind/onnx_models/all-MiniLM-L6-v2/onnx/ 2>&1
```

Setting `CHROMA_CACHE_DIR` will not help on the default backend — see the
note in Step 2.

### `neuralmind build` fails at the embedding step

Same cause. With no network the download raises after three attempts
rather than hanging. Confirm the model folder resolves, and prefer
`NEURALMIND_ONNX_MODEL_DIR` over relying on a cache path.

---

## Compliance posture (for the auditor)

The air-gapped install is the strictest deployment posture NeuralMind
supports:

- **No outbound network at any phase** (install, build, runtime, query)
  once wheels and model are staged per this page.
- **No repository content transmitted, even before staging.** The sole
  outbound request is a `GET` for a public, hash-pinned model artifact and
  carries no source, paths, query text or identifiers — see the table at
  the top of this page.
- **Wheel set is auditable** — every transitive dep is a file on disk
  you can hash, mirror, and review independently. See the [SBOM
  attached to each tagged release](https://github.com/dfrostar/neuralmind/releases)
  (`neuralmind-vX.Y.Z.sbom.json`, CycloneDX JSON) for the full graph
  with versions + licenses.
- **No telemetry, no remote logging, no automatic update checks.**
  See [`docs/SECURITY-GUIDE.md`](../SECURITY-GUIDE.md) and
  [`docs/COMPLIANCE-SUMMARY.md`](../COMPLIANCE-SUMMARY.md).
- **Data residency** is fully under operator control — synapse store
  (`.neuralmind/synapses.db`), the vector index
  (`graphify-out/neuralmind_turbovec/` by default, or
  `graphify-out/neuralmind_db/` on the ChromaDB backend), and event log
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
