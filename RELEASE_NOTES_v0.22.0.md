# NeuralMind v0.22.0 — turbovec becomes the default (when available)

**The headline:** v0.21.0 made a complete **ChromaDB-free** retrieval path
(the `turbovec` backend: TurboQuant compressed index + a bundled
`OnnxMiniLMEmbedder`). v0.22.0 starts switching everyone onto it — safely. The
package now **imports without ChromaDB**, and the default backend is **`auto`**:
prefer turbovec when its deps are installed, otherwise fall back to chroma.

This is the staged middle step promised in the v0.21.0 notes ("flip the default
to turbovec *with a chroma fallback* + a one-time reindex migration"). It's
deliberately conservative: nothing breaks for a plain install, and the old
ChromaDB index is never deleted.

## What's new

- **`import neuralmind` no longer requires ChromaDB.** The eager
  `GraphEmbedder` import and the chromadb telemetry monkey-patch were the last
  two things pulling ChromaDB in at package-import time. `GraphEmbedder` is now
  exposed via PEP 562 module-level `__getattr__` (so
  `from neuralmind import GraphEmbedder` still works, lazily), and the telemetry
  patch moved next to the only `import chromadb`, in `embedder`. Verified:
  `import neuralmind` succeeds with ChromaDB **entirely absent**.

- **The default backend is now `auto`.** `backend_manager.resolve_backend`
  resolves `auto` (and an unset config) to **turbovec when its stack
  (`turbovec` + `onnxruntime` + `tokenizers`) is importable, else chroma**. An
  explicit `backend:` in `neuralmind-backend.yaml` always wins, so pinning
  chroma is a one-liner.

- **One-time auto-reindex, with a notice.** When `auto` lands on turbovec for a
  project that still has a legacy ChromaDB index and no turbovec index yet, the
  normal build path reindexes from `graph.json` and prints a one-line notice
  (with a rough time estimate). The old ChromaDB index is left untouched as a
  fallback — nothing is deleted.

- **`neuralmind doctor` now shows the resolved backend.** A new **Backend**
  check reports the configured value, what it resolves to, and whether the
  turbovec stack is installed — so the per-environment default is never a
  silent mystery.

## Why it matters

- **Real adoption, zero breakage.** A plain `pip install neuralmind` (no
  `[turbovec]` extra) resolves `auto` → chroma, so existing installs and CI are
  unchanged. Users who added the extra get the ChromaDB-free path by default,
  letting it bake before v0.23 makes it universal.
- **Smaller, faster, leaner where it lands.** On a 600-file / 10k-node
  synthetic repo, turbovec searched ~5× faster, used ~7× less disk, and — after
  the v0.21.x indexing-memory fix — lower peak RSS than chroma too.
- **One step closer to retiring ChromaDB** and the recurring
  **CVE-2026-45829** advisory surface behind it.

## Per-agent expectations

| Agent | What changes in v0.22.0 |
|-------|--------------------------|
| **Claude Code** | If the `[turbovec]` extra is installed, new/queried projects auto-use turbovec (one-time reindex, with a notice). Otherwise unchanged (chroma). Pin with `backend: graph`. |
| **Cursor / Cline** | Same MCP tools, same retrieval; backend auto-selected per install. |
| **Generic MCP client** | No new tool; backend is resolved automatically (or via `neuralmind-backend.yaml`). |
| **Contributors / CI** | `import neuralmind` no longer needs chromadb; default config backend is `"auto"`; `resolve_backend`/`turbovec_available` are the new seams; `neuralmind doctor` gains a **Backend** check. |

## How to control it

```yaml
# neuralmind-backend.yaml — pin explicitly to override the auto default
backend: graph      # force ChromaDB
# backend: turbovec # force the ChromaDB-free path (requires the [turbovec] extra)
```

Install the ChromaDB-free path: `pip install "neuralmind[turbovec]"`. Check what
you're running: `neuralmind doctor` (see the **Backend** line).

## Honest scope & what's next

- **The flip is "soft" until v0.23.** Because `turbovec` is still an optional
  extra, `auto` only resolves to turbovec for users who installed it — the same
  people who could already opt in. That's intentional staging.
- **ChromaDB is still a core dependency.** This release removes the
  *import-time* requirement and makes turbovec the preferred default; it does
  not yet remove `chromadb` from the install.
- **Next (v0.23):** fold the turbovec deps into core, make the flip universal,
  and drop `chromadb` from the core dependency list.
