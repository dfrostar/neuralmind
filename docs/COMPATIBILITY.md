# NeuralMind Compatibility Matrix

**Last Updated:** 2026-07-08
**Next Review:** 2026-10-08
**Current release:** v0.41.0

> This matrix describes the **current** release line. NeuralMind ships frequent
> minor releases (see `CHANGELOG.md` and the per-release `RELEASE_NOTES_v*.md`);
> there is no formal multi-version LTS programme — the latest release is the
> supported one, and upgrading is a `pip install -U neuralmind`. Breaking-change
> policy lives in [`VERSION-STRATEGY.md`](VERSION-STRATEGY.md).

---

## Python Version Support

| Python | Status | Notes |
|--------|--------|-------|
| 3.12 | ✅ Supported | Recommended; CI-tested on Linux, macOS, Windows |
| 3.11 | ✅ Supported | CI-tested on Linux |
| 3.10 | ✅ Supported | Minimum version (`requires-python = ">=3.10"`); CI-tested on Linux |
| ≤ 3.9 | ❌ Unsupported | — |

`pyproject.toml` declares classifiers for 3.10 / 3.11 / 3.12. Python 3.13 is not
yet in the tested matrix.

---

## Platform Support

| OS | Status | Default backend | Notes |
|----|--------|-----------------|-------|
| Linux (glibc, x86_64 / aarch64) | ✅ Full | turbovec/ONNX (ChromaDB-free) | CI-verified every PR (Python 3.10–3.12) |
| macOS (Apple Silicon, arm64) | ✅ Full | turbovec/ONNX (ChromaDB-free) | CI-verified every PR (Python 3.12) |
| macOS (Intel, x86_64) | ✅ Full | ChromaDB fallback | No turbovec wheel; resolves to the `chromadb` backend automatically |
| Windows (x86_64 / AMD64) | ✅ Full | turbovec/ONNX (ChromaDB-free) | CI-verified every PR (Python 3.12); fresh-install job still ⚠️ experimental on Windows |
| Windows (ARM) | ◐ Fallback | ChromaDB fallback | No turbovec wheel; resolves to the `chromadb` backend automatically |
| Linux (musl / Alpine, or pre-2.28 glibc) | ⚠️ Caveat | — | Env markers can't distinguish musl from glibc, so these still resolve to turbovec and need a toolchain, or `pip install "neuralmind[chromadb]"`. Prefer a glibc base image (`python:slim`), not `python:alpine`. |
| Docker | ✅ Full | as per base image | Multi-arch (`linux/amd64` + `linux/arm64`) images published to GHCR per release |

---

## Embedding Backend Compatibility

As of **v0.29.0** the default install is **ChromaDB-free**: a base
`pip install neuralmind` resolves to the TurboQuant/ONNX stack
(`turbovec` + `onnxruntime` + `tokenizers`) on platforms where turbovec
publishes wheels, and to ChromaDB only as the fallback elsewhere. The `auto`
backend prefers turbovec when present, else ChromaDB.

| Backend | Min version | Status | How to select |
|---------|-------------|--------|---------------|
| turbovec / ONNX | `turbovec>=0.7`, `onnxruntime>=1.16` | ✅ Default (where wheels exist) | Automatic; base dependency (the `[turbovec]` extra is a back-compat no-op) |
| ChromaDB | `chromadb>=0.4.0` | ✅ Fallback / opt-in | Automatic fallback on unsupported platforms, or `pip install "neuralmind[chromadb]"` + `backend: graph` in `neuralmind-backend.yaml` (or `backend="graph"`) |

> **ChromaDB security note.** The pinned `chromadb==1.5.8` is held back due to
> **CVE-2026-45829 / GHSA-f4j7-r4q5-qw2c** (critical, pre-auth RCE) which affects
> the ChromaDB *server* HTTP API. NeuralMind uses only the embedded
> `PersistentClient` (no server, no `trust_remote_code`), so the vulnerable path
> is unreachable. Every published chromadb version through 1.5.9 is affected, so
> there is no fixed version to bump to yet. See
> [`SECURITY.md`](../SECURITY.md) and
> [`.github/workflows/chromadb-cve-watch.yml`](../.github/workflows/chromadb-cve-watch.yml).

There is no pgvector or LanceDB backend. Alternate vector backends are tracked
as a durability idea in
[`docs/plans/2026-07-future-proofing-review.md`](plans/2026-07-future-proofing-review.md),
not shipped.

---

## Graph Backend Compatibility

Since **v0.15.0** NeuralMind ships a **built-in tree-sitter graph backend**
(`neuralmind/graphgen.py`) that parses a project into a graphify-compatible
`graph.json` with **no external graphify install**. Ten languages are bundled
out of the box:

Python · TypeScript · Go · Rust · Java · C · C++ · C# · Ruby · PHP

(plus OpenAPI/AsyncAPI, SQL DDL, and Protocol Buffers as `document` nodes since
v0.40.0). The `SUPPORTED_SUFFIXES` seam registers additional extensions.

| Graph producer | Status | Notes |
|----------------|--------|-------|
| Built-in tree-sitter (`graphgen.py`) | ✅ Default | No external tool; bundled grammars are runtime deps (`tree-sitter-*>=0.21`, PHP `>=0.22`) |
| External `graphify` | ◐ Optional | Still consumable — anything downstream of `graph.json` is unchanged — but no longer required |

---

## MCP Server Compatibility

| MCP SDK | NeuralMind | Notes |
|---------|-----------|-------|
| `mcp>=1.27.2` | v0.41.x | Base dependency. The server uses the low-level `mcp.server.Server` + `stdio_server` API. The `[mcp]` extra is a back-compat no-op (mcp is a base dependency). |

Agent-client registration (`neuralmind install-mcp`) writes config for Claude
Code (`.mcp.json`), Cursor (`.cursor/mcp.json`), Claude Desktop, VS Code
(`settings.json`, native MCP since VS Code 1.99), and Cline. See the
[Integration Guide](wiki/Integration-Guide.md).

---

## Testing Matrix

| Test type | Frequency | Coverage |
|-----------|-----------|----------|
| Unit + integration | Per PR | 967 tests across `tests/`; Python 3.10–3.12 on Linux, 3.12 on macOS + Windows |
| Fresh-install smoke | Per PR | `pip install` in a clean venv, `pip check`, import + CLI smoke (Windows deferred) |
| Type check (mypy) | Per PR | Gating (baseline flags) |
| Lint / format | Per PR | ruff + black |
| Token-reduction benchmark | Per PR | Regression-gated |
| Faithfulness / retrieval eval | Per PR | `neuralmind eval`, regression-gated |
| SBOM | Per release | CycloneDX |

---

## How to Report Compatibility Issues

1. Check this matrix and [Limits & Failure Modes](wiki/Limits-and-Failure-Modes.md).
2. Run `neuralmind doctor` — it reports each install component with a status + fix.
3. Open an issue with:
   - NeuralMind version: `neuralmind --version`
   - Python version: `python --version`
   - OS, architecture, and (on Linux) glibc vs musl
   - Which backend resolved (`neuralmind doctor` shows it)
   - Exact error and reproduction steps
