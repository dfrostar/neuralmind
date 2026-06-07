# NeuralMind v0.22.0 — ChromaDB-optional import + auto backend selection

The next step of the ChromaDB → TurboVec migration (#204), staged to be
**non-breaking**: NeuralMind now **imports without ChromaDB** and **auto-selects
the ChromaDB-free backend when its deps are present** — without forcing the flip
on a backend that only shipped in v0.21.0.

## What's new

- **`import neuralmind` is ChromaDB-free.** The `GraphEmbedder` export is lazy
  (PEP 562 `__getattr__`) and the Posthog telemetry-silencing patch moved into
  the chroma backend, so merely importing the package no longer imports
  ChromaDB. Verified in CI: `import neuralmind` ⇒ `chromadb` not in
  `sys.modules`.
- **Default backend is now `auto`.** It resolves to:
  - **`turbovec`** (the ChromaDB-free path) when `turbovec`, `onnxruntime`, and
    `tokenizers` are importable — i.e. you installed `neuralmind[turbovec]`;
  - **`chroma`** otherwise.
  A bare `pip install neuralmind` has none of those, so it **stays on chroma —
  nothing changes**. An explicit `backend:` in `neuralmind-backend.yaml` always
  wins (`graph` / `chroma` / `turbovec` / `auto`).
- **Automatic, self-healing migration.** If auto-selection lands on a backend
  whose on-disk index doesn't exist yet, the index rebuilds on first use
  (`_ensure_built`), and a one-time log line explains why and how to pin the old
  backend.

## Why it's staged this way

You asked for "auto-prefer, no forced flip." TurboVec is excellent but only had
~a day of field exposure at v0.21.0, so betting *every* install's default on it
immediately would be reckless. This release makes the ChromaDB-free path the
effortless default **for anyone who opts into the extra**, lets it bake, and
keeps bare installs exactly as they were.

## Per-agent expectations

| Agent | What changes in v0.22.0 |
|-------|--------------------------|
| **Claude Code / Cursor / Cline** | Nothing for a bare install (still chroma). If you `pip install neuralmind[turbovec]`, retrieval auto-uses the ChromaDB-free backend; the index rebuilds once. |
| **Generic MCP client** | No new tool; backend choice is config/dep-driven. |
| **Library users** | `import neuralmind` works with ChromaDB uninstalled (if you use the turbovec backend). `neuralmind.GraphEmbedder` still imports it on demand. |
| **Contributors / CI** | New `auto` default + `resolve_backend_name`; a stdlib test asserts the ChromaDB-free import. CI doesn't install the turbovec extra, so it stays on chroma — numbers unchanged. |

## How to control the backend

```yaml
# neuralmind-backend.yaml at the repo root
backend: auto       # default: turbovec if its deps are installed, else chroma
# backend: turbovec # force the ChromaDB-free backend
# backend: graph    # force chroma (keep an existing chroma index)
```

## Honest scope & what's next

- **ChromaDB is still a core dependency** (the default for bare installs and the
  fallback). Dropping `chromadb` from the core deps — so the slim install is the
  *only* install — is **v0.23**, once turbovec has proven itself as the broad
  default.
- Switching backends triggers a one-time reindex (automatic). On a large repo
  that first build is slower; pin `backend: graph` if you'd rather not.
