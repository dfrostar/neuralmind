# PRD: ChromaDB-free by default (packaging)

**Status:** Draft · **Owner:** dfrostar · **Created:** 2026-06-18
**Tracking branch:** `claude/codebase-memory-mcp-review-3r2mri`

## 1. Background & motivation

The competitive review of `DeusData/codebase-memory-mcp` found NeuralMind's two
real (commodity) disadvantages were **language breadth** (addressed in
v0.27/v0.28 — Rust + Java) and **packaging weight**. This PRD closes the
packaging gap.

Today a plain `pip install neuralmind` pulls **ChromaDB** as a base dependency —
which drags in a large transitive tree (FastAPI, grpcio, OpenTelemetry,
kubernetes client, …) and sits behind the recurring **chromadb CVE** advisory
the project already watches (`.github/workflows/chromadb-cve-watch.yml`). The
ChromaDB-free `turbovec` path (TurboQuant compressed index + bundled ONNX
MiniLM embedder, vectors byte-identical to ChromaDB's) has existed since
v0.21 and become the auto-preferred backend *when installed* (v0.22) — but it's
an **opt-in extra**, so the default install still gets ChromaDB and never uses
turbovec unless the user knows to ask for it.

This PRD makes the lean path the **default install** and demotes ChromaDB to an
opt-in extra — finishing the migration v0.21/v0.22 started.

## 2. Why this is lower-risk than it looks

The hard parts already shipped:

- **`import neuralmind` is already ChromaDB-free** — `GraphEmbedder` (the only
  module with a top-level `import chromadb`) is lazily exposed via
  `neuralmind/__init__.py:__getattr__`, and `create_backend` lazy-imports it
  only when the chroma backend is selected (`backend_manager.py:93`).
- **Backend auto-selection already prefers turbovec** — `resolve_backend`
  returns `turbovec` when its deps import, else `graph` (chroma)
  (`backend_manager.py:37`). Flipping the *installed* deps flips the default
  with no logic change.
- **The chroma→turbovec migration already exists** — on the first build after
  the default flips, `core.py:_maybe_announce_turbovec_migration` announces a
  one-time reindex *from `graph.json`* (not from the chroma index), and leaves
  the old ChromaDB index in place as a selectable fallback. Nothing is deleted.

So the change is concentrated in **packaging + CI + error UX + docs**, not core
retrieval logic.

## 3. The honest trade-off (must be in the release notes)

"ChromaDB-free" is **not** unambiguously "smaller." The turbovec path pulls
`onnxruntime` (a heavy native wheel — the same one behind the slow ~10-min
Windows CI builds). The win is precise and should be framed as such:

- **Removed from the default install:** the ChromaDB dependency tree
  (FastAPI/grpcio/OpenTelemetry/kubernetes/…) **and its CVE surface**.
- **Added to the default install:** `onnxruntime` + `tokenizers` + `numpy`.
- **Net:** a leaner, CVE-watched-dependency-free default with **one** focused
  native dep instead of ChromaDB's sprawl — not a claim of "fewer megabytes."

Overclaiming "lighter install" would be dishonest; we claim "ChromaDB-free,
CVE-tree-free default."

## 4. Goals / non-goals

**Goals**
- `pip install neuralmind` installs the **turbovec/ONNX** stack and uses it by
  default — zero ChromaDB.
- `pip install "neuralmind[chromadb]"` restores the ChromaDB backend for users
  who want it; `backend: graph` keeps working for them.
- Upgrading an existing chroma-indexed project **just works** via the existing
  one-time auto-reindex, with the old index retained as a fallback.
- A user who selects the chroma backend without installing it gets an
  **actionable error**, never an opaque `ImportError`.
- CI proves *both* the ChromaDB-free default **and** the ChromaDB opt-in.

**Non-goals**
- Removing the ChromaDB backend (it stays, as an opt-in).
- Changing retrieval behaviour or vectors (turbovec vectors are byte-identical
  to ChromaDB's `all-MiniLM-L6-v2`; parity already gated).
- A true single static binary (out of scope; onnxruntime precludes it).

## 5. Design / changes

**`pyproject.toml`**
- `dependencies`: remove `chromadb`; add `turbovec>=0.7`, `numpy>=1.20`,
  `onnxruntime>=1.16`, `tokenizers>=0.15` (promote the `[turbovec]` extra to
  base).
- `optional-dependencies`:
  - `chromadb = ["chromadb>=0.4.0"]` — the opt-in ChromaDB backend.
  - `turbovec = []` — kept as an empty back-compat alias so existing
    `pip install "neuralmind[turbovec]"` commands in docs/blogs/CI keep
    resolving (same pattern already used for the `mcp` extra).
  - `all` includes `chromadb` so `[all]` still exercises every backend.

**`neuralmind/backend_manager.py`**
- In `create_backend`, when the chroma backend is selected but `chromadb` isn't
  importable, raise a clear `ModuleNotFoundError`/`RuntimeError`:
  *"the 'graph'/chroma backend needs ChromaDB — `pip install
  neuralmind[chromadb]`, or use the default ChromaDB-free turbovec backend."*

**CI (`.github/workflows/ci.yml`, `ci-benchmark.yml`)**
- **Test** jobs install `".[dev,chromadb]"` so both backends are exercised
  (turbovec is base; chromadb opt-in).
- **Fresh Install** job keeps `pip install .` (now ChromaDB-free) and adds an
  assertion: `import neuralmind` works, `neuralmind build`+`query` succeed on
  turbovec, **and** `chromadb` is *not* importable — proving the default is
  genuinely ChromaDB-free.
- Benchmark job runs on the (now default) turbovec backend.

**Tests**
- Guard ChromaDB-specific tests with `pytest.importorskip("chromadb")` so the
  suite passes on a ChromaDB-free install while still running fully in the
  `[dev,chromadb]` CI job.

**Docs + SEO**
- `RELEASE_NOTES_v0.29.0.md` with the honest trade-off framing + a per-agent
  table; README banner/trail/row; `docs/index.html` + `docs/about.html`
  (+ meta); `docs/wiki/CLI-Reference.md` (install matrix, `backend:` options,
  the new `[chromadb]` extra); `docs/use-cases/chromadb-free-local.html` refresh;
  `pyproject.toml` keywords (`chromadb-optional`, `lean-default-install`,
  `cve-free-default`).

## 6. Acceptance criteria

- [ ] `pip install neuralmind` then `python -c "import chromadb"` **fails**;
      `neuralmind build . && neuralmind query . "…"` **succeeds** on turbovec.
- [ ] `pip install "neuralmind[chromadb]"` + `backend: graph` uses ChromaDB.
- [ ] Selecting chroma without it installed prints the actionable install hint.
- [ ] Upgrading a chroma-indexed project auto-reindexes once into turbovec,
      old index retained (existing migration test still green).
- [ ] CI: Test job (`[dev,chromadb]`) green on both backends; Fresh Install job
      proves the ChromaDB-free default.
- [ ] `neuralmind doctor` reports the resolved backend correctly on a
      ChromaDB-free install.
- [ ] Docs + SEO shipped in the same PR; release notes carry the honest
      trade-off.

## 7. Risks & mitigations

| Risk | Mitigation |
|------|-----------|
| A module imports chromadb at top level on the default path | Audited: only `embedder.py`, lazy-loaded; `import neuralmind` verified ChromaDB-free. Fresh-install CI assertion locks it in. |
| Users with `backend: graph` set but no `[chromadb]` | Actionable error with the exact `pip install` fix. |
| Existing chroma indexes "lost" on upgrade | Not deleted — auto-reindex from `graph.json`, old index kept as fallback (existing v0.22 behaviour + test). |
| `onnxruntime` install weight / slow wheels | Honest framing (not "lighter"); it was already the auto path when present. |
| Third-party code importing `neuralmind.embedder` directly | Still works **if** `[chromadb]` installed; documented in release notes. |

## 8. Rollout

Single `feat:` PR → release-please cuts **v0.29.0**. This is a **default-install
change**, called out prominently in the release notes with the one-line upgrade
note (`pip install "neuralmind[chromadb]"` to keep ChromaDB). Semver: additive
+ backward-compatible at the API level (only the *default dependency set*
changes), so a minor bump is correct.

## 9. Success metric

A default `pip install neuralmind` is **ChromaDB-free and CVE-tree-free** out of
the box, using turbovec/ONNX, with ChromaDB one `[chromadb]` extra away — closing
the packaging half of the competitive gap while keeping every existing setup
working.
