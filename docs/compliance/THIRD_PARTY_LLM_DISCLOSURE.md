# Third-Party LLM Disclosure & Media Ingestion Scope

**Date:** 2026-08-31
**Version:** 1.0
**SOC 2 Controls:** CC6.1, CC7.1, P4.1, P6.1

---

## 1. Purpose

Give clients, their DPOs, and their compliance/procurement teams a precise,
code-cited answer to the two questions that come up whenever NeuralMind is
evaluated as (or must be contractually excluded as) a data processor or
subprocessor:

1. Can client media files (video, images, audio) ever reach any server —
   local or remote — through NeuralMind?
2. Does NeuralMind transmit any client content to a public-cloud LLM as
   part of normal operation?

This document exists because other compliance docs in this repository
(`COMPLIANCE-SUMMARY.md`, `SECURITY-GUIDE.md`) state "no external network
calls" / "no third-party processor" as unqualified absolutes. That framing
is correct for everything NeuralMind actually does, with exactly one
narrow, opt-in exception documented in §3.1. This doc is the precise,
citable version of the claim.

## 2. Media file scope — video (and all other media) is out of scope entirely

NeuralMind has no code path, in any deployment mode, that accepts video,
image, or audio files for indexing:

- **Structural indexing** (`neuralmind/graphgen.py`) dispatches files by
  extension through `SUPPORTED_SUFFIXES` — an allowlist covering ~10
  programming-language source extensions (Python, TypeScript, Go, Rust,
  Java, C, C++, C#, Ruby, PHP) plus Markdown. Anything else is skipped.
- **Free-form document ingestion** (`neuralmind/document_ingestion.py`,
  used by `neuralmind ingest-document` / `NeuralMind.ingest_document()`)
  accepts only PDF, Markdown, and plain text, capped at 10MB per file, and
  actively **rejects binary content presented under a text-like
  extension** via magic-byte sniffing — a guard built specifically to stop
  something that isn't text from entering the pipeline.
- **No dependency anywhere in `pyproject.toml`** performs video decoding,
  frame extraction, or computer vision (no ffmpeg, opencv, moviepy, or
  equivalent). There is no vision model in this codebase.

**Conclusion:** a video file handed to NeuralMind is either silently
skipped (unsupported extension in structural indexing) or explicitly
rejected (binary-content guard in document ingestion). It is never parsed,
embedded, chunked, or transmitted anywhere — local or remote — by any
existing code path. No configuration flag adds video support; this is not
a "disabled by default" feature, it does not exist in the codebase.

If your product requirement involves indexing video (e.g. transcripts,
frame-level metadata), that is new functionality NeuralMind does not have
today — do not represent it as available in a client-facing document.

## 3. Everything NeuralMind does process stays local, with one documented exception

NeuralMind's actual product surface is source code and text/PDF/Markdown
documents. The default data flow for that surface is:

```
Local files (code, .md, .pdf, .txt)
   → tree-sitter / document_ingestion parsing (local, in-process)
   → embeddings (local ONNX MiniLM model, or optional local ChromaDB)
   → SQLite graph + synapse store (.neuralmind/, graphify-out/, on disk)
   → served to the calling agent (Claude Code, Cursor, etc.) over local
     MCP stdio, or via the local graph-view server bound to 127.0.0.1
```

No step in that pipeline makes a network call. This is what
`COMPLIANCE-SUMMARY.md`'s "Outbound network at runtime: None" row and
`SECURITY-GUIDE.md`'s "No Calls Home" principle correctly describe for the
default configuration.

### 3.1 The one opt-in exception: documentation-synapse seeding via Anthropic

`neuralmind/synapses.py::seed_from_documentation()`, invoked from
`NeuralMind.ingest_document()` in `neuralmind/core.py`, sends the **text of
`README.md` and `docs/architecture.md`** — project documentation prose,
never source code, never client data files, never media — to the
Anthropic API, in order to extract architectural relationships (e.g. "the
embedder feeds the context selector") as synapse graph edges.

This path only runs when **both** conditions are met:

- `NEURALMIND_LLM_SEED=1` is explicitly set (default: unset → path returns
  immediately, no call attempted)
- `ANTHROPIC_API_KEY` is present in the environment (the operator's own
  key; NeuralMind ships none)

It is **fail-open**: any error (network failure, malformed response,
missing key) is caught and the function returns `0` — it never blocks or
fails indexing, and it never retries with client data as a fallback.

**For any organization operating under a DPA/BAA that prohibits
undisclosed subprocessors:** never set `NEURALMIND_LLM_SEED` or
`ANTHROPIC_API_KEY` in the environment where NeuralMind runs. This is the
default state — no action is needed unless someone has already opted in.
Verify with:

```bash
env | grep -E 'NEURALMIND_LLM_SEED|ANTHROPIC_API_KEY'   # should be empty
ss -tnp | grep python                                     # no connections, during neuralmind build/query
```

An egress firewall rule blocking the NeuralMind process/container from
reaching `api.anthropic.com` is effective defense-in-depth if you want a
belt-and-suspenders guarantee beyond the env-var gate.

### 3.2 Local-model path (Ollama) — local by default, operator-configurable

`neuralmind/local_client.py` (`OllamaClient`) is an optional local-model
query path, disabled unless `local_models.enabled` is set in
`~/.config/neuralmind/config.toml`. Its default endpoint is
`http://localhost:11434` — a local Ollama server, not a cloud endpoint.
The endpoint is operator-configurable (`local_models.endpoint`); if your
deployment sets it to anything other than a loopback/private address, that
becomes a real egress path and should go through the same review as any
other outbound connection.

### 3.3 Dead configuration — removed

`neuralmind/config.py` previously defined `LocalModelsConfig.fallback_to_api`
(default `True`) and an `ApiConfig(provider="openrouter")` section. As of
this review, no code path ever read either field — they were schema-only
and never caused a call to OpenRouter or any other API provider. They were
removed (not wired up) precisely because leaving a dead field named after a
hosted third-party API in the config schema is confusing for exactly the
audience this document serves: a client security reviewer grepping the
codebase for `openrouter` would find it and reasonably ask whether it does
something. `neuralmind/config.py` now only carries the local-Ollama section
described in §3.2.

### 3.4 Hugging Face — not a dependency of any kind

A natural follow-up to §3.3's OpenRouter finding: does NeuralMind depend on
Hugging Face the way some "local" AI tools quietly do (fetching model
weights from the HF Hub, or calling HF's hosted Inference API)? No. The
only Hugging-Face-authored package anywhere in `pyproject.toml` is
`tokenizers` (the fast-tokenizer library), and it runs entirely
in-process to prepare text for the local ONNX MiniLM model described in
§3 — it makes no network calls of its own. There is no `huggingface_hub` or
`transformers` dependency, and no `HF_API_KEY`/Inference API code path
anywhere in the codebase. The embedding model archive itself is fetched
from a pinned, SHA256-verified URL on Chroma's own S3 bucket
(`neuralmind/onnx_embedder.py`), not the HF Hub. Using a vendor's
open-source library locally (this project also uses OpenAI's `tiktoken`
the same way, for benchmark tokenization) is not the same as depending on
that vendor's hosted service — the distinction that made §3.3's OpenRouter
field worth removing in the first place.

## 4. Answering the specific question: client video files and LLM subprocessors

Given §2 and §3: **client video files cannot reach a public-cloud LLM
through NeuralMind, under any configuration, because NeuralMind never
ingests video files in the first place.** This is a stronger guarantee
than "video stays on-prem" — there is no video pipeline to confine.

For the content NeuralMind *does* index (source code, README/architecture
docs), the only third-party LLM transmission risk is the single, opt-in,
default-off path in §3.1, and it is scoped to documentation prose, not
arbitrary client files.

## 5. Relationship to other NeuralMind compliance documents

- [`../COMPLIANCE-SUMMARY.md`](../COMPLIANCE-SUMMARY.md) — one-page
  procurement summary; its "Outbound network" and GDPR rows should be read
  together with §3.1 above.
- [`../SECURITY-GUIDE.md`](../SECURITY-GUIDE.md) — "No Calls Home"
  principle; same caveat applies.
- [`../PRIVACY-POLICY.md`](../PRIVACY-POLICY.md) §6 — covers NeuralMind's
  own commercial/SaaS operations (license portal: Stripe, GitHub). That
  section is scoped to the paid-license/portal side of the business, not
  OSS-tool runtime behavior; this document is the runtime-behavior
  disclosure for the OSS tool itself.
- [`RISK_ASSESSMENT.md`](RISK_ASSESSMENT.md) R-03 — data exfiltration via
  MCP server; mitigation text updated to reference this document rather
  than assert "no network" unconditionally.

This document does not constitute legal advice or contract language for a
DPA, BAA, or service-provider addendum. It is a factual, code-verified
description of current behavior for your counsel to build contractual
language on.

---

*This disclosure is reviewed whenever a change touches LLM-call code paths
or media/document ingestion. Last reviewed: 2026-08-31.*
