# NeuralMind v3.4.0 — indexing a book without indexing the repo

A user indexed a book with `neuralmind ingest-content chapters`. It worked
— 1,054 chunks, 318 synapses — but only after they hand-wrote a fake index
file to stop NeuralMind walking up to the git root and indexing the entire
repository alongside the prose:

```bash
mkdir -p .neuralmind
echo '{"is_content_project": true}' > .neuralmind/index_ir.json
```

That file isn't a valid IR. It worked because the resolver only checked
whether the path *existed*. Everything else in their report followed from the
same place: 70.6 seconds of silence with no way to tell a working embed from a
hung one, a full re-index on every run, no way to preview a corpus before
paying for it, and a code-graph build for a folder that contains no code.

v3.4.0 is the release for people pointing NeuralMind at prose.

## What's in this release

| Change | Was | Now |
|--------|-----|-----|
| **Project root resolution** | cwd checked before the ingest target — a book folder inside a repo resolved to the repo | Target checked first; `--project-path` pins it; an unindexed git root is called out, not silently used |
| **Code-graph build** | Always ran, even for a Markdown-only folder, and needed a throwaway `_content_seed.py` | `--content-only` skips it; a valid empty IR marks the directory instead |
| **Re-runs** | Re-parsed and re-embedded the whole corpus every time | Incremental by content hash; only changed files are re-embedded |
| **Long embeds** | No output for 70 seconds | TTY progress bar with ETA; milestone lines off a terminal |
| **Previewing a corpus** | Run the full ingest to find out | `--dry-run` prints files, sizes, chunk counts, status |
| **Diagnosing a hang** | Nothing to look at | `--verbose`: resolved root, chunk params, per-file timings |
| **A run that overruns** | Hangs indefinitely | `--timeout N` stops between files and keeps what it indexed |
| **`neuralmind status`** | Synapse edges only | Index nodes, last build, content files/chunks, last ingest |
| **Chunk settings** | Retyped on every invocation | `NEURALMIND_CHUNK_SIZE` / `NEURALMIND_OVERLAP` |
| **Content in keyword search** | Missing from BM25 on the default backend until a full rebuild | Refreshed on every content ingest |

## 1. Where the index goes

`_resolve_project_path` checked the current directory for a project marker
*before* it looked at the path being ingested. Running from anywhere inside a
git repo, that meant the repo root won — so `ingest-content book/chapters`
indexed the codebase. Ingesting into project B while sitting in project A had
the same failure.

The order is now: explicit `--project-path` → the nearest marker walking up
**from the target** → the cwd. A directory carrying its own `.neuralmind/` is
its own project, even inside a larger repo.

When resolution still lands on a git root that NeuralMind has never indexed —
the book-in-a-monorepo case on a first run — it says so instead of doing it
quietly:

```
Note: indexing into /repo — the nearest project marker above /repo/book/chapters
      (a git root, with no NeuralMind index of its own).
      To keep this corpus self-contained, re-run with --project-path /repo/book/chapters
```

## 2. `--content-only`

The old path built the project's code graph first, and because `build` needed
*something* parseable, it wrote a `_content_seed.py` stub into the user's book
folder to give tree-sitter a file.

`--content-only` skips graph generation entirely. An *existing* graph is still
loaded — a cheap JSON read — so a mixed project's code nodes stay in the
keyword index. For a pure corpus it writes a valid empty IR to
`.neuralmind/index_ir.json`, which is what the hand-rolled
`{"is_content_project": true}` was reaching for. No seed file, and the next run
resolves the directory as a project on its own.

## 3. Incremental re-runs

Every embedded file's SHA-256, size, and chunk parameters are recorded in
`<project>/.neuralmind/content_manifest.json`. A re-run re-embeds only what
changed. On the reporter's 34-file corpus, a no-op re-run drops from a full
re-embed to nothing:

```
Ingested 1 file(s) → 9 chunks → 9 nodes (33 unchanged, skipped)
Corpus: 34 file(s), 306 chunks
Wall time: 0.6s | Embed time: 0.46s
```

Chunk ids are positional, so incremental indexing creates a hazard the old
full-rebuild path didn't have: a chapter that *shrinks* leaves orphaned chunks
in the vector store, still searchable. The manifest records each file's node
ids, so shortened files have the difference evicted, and files deleted from the
corpus are evicted entirely. A timed-out run never prunes — files it hasn't
reached yet are queued, not deleted.

Changing `--chunk-size` or `--overlap` invalidates the manifest by itself: new
parameters mean new chunk boundaries and new node ids, so identical bytes are
still stale. `--force` re-embeds everything.

## 4. Progress, verbosity, and timeouts

`neuralmind/progress.py` renders progress two ways, chosen from the destination
stream. On a terminal: an in-place bar with a percentage and an ETA. Off one —
CI logs, an agent shell, a redirect — plain milestone lines, so a long embed
shows movement instead of looking hung. Output goes to **stderr**, so `--json`
on stdout stays parseable.

Every terminal probe is guarded. `isatty()` raises on a closed or detached
stream, which is the same class of failure behind the `tcsetattr: Inappropriate
ioctl for device` noise in the original report; every write is best-effort, so a
broken pipe can't kill the work the bar is only describing. The onboarding
wizard's prompts got the same treatment — they now take their defaults on a
non-TTY instead of blocking on a question nobody can answer.

`--verbose` puts the resolved project root, the chunk parameters in effect,
per-file chunk counts and embed timings, and every eviction on stderr.
`--timeout N` stops between files, writes the manifest for what did land, and
exits `1` with `"timed_out": true` — the next run resumes rather than starting
the corpus over.

## 5. `--dry-run`

```
FILE       BYTES  CHUNKS  STATUS
ch1.md      3662       9  would-index
ch2.md      3662       9  unchanged
ch3.md      3768       9  would-index

Dry run: 2 of 3 file(s) would be embedded (18 of 27 chunks). Nothing was written.
```

Parses each file but never embeds, never opens a backend, and never writes a
manifest. `--json` gives the same data as a `files` array.

## 6. `neuralmind status` reports the index

`status` covered the synapse layer only, so "did my ingest actually land, and
how stale is the index?" had no answer short of running a query. It now leads
with the index half:

```
═══ NeuralMind Status — book ═══
  Code nodes:   0 (0 edges) — content-only project
  Last build:   0.4h ago
  Disk:         2.1 MB
  Content:      34 file(s), 306 chunks, 306 nodes
  Last ingest:  2026-08-23T13:19:14+00:00

  Status:       🟢 active
  Edges:        318 (12 LTP-protected)
```

Both halves are reported even when only one exists. It reads the IR and the
manifest straight off disk and never constructs a vector backend, so it stays a
glance rather than a load.

## 7. A bug found on the way

`TurboVecEmbedder.embed_content()` never refreshed the BM25 keyword index —
unlike `embed_nodes()`, and unlike the ChromaDB backend's own `embed_content()`.
On the default backend since v0.46.0, that meant freshly ingested content was
invisible to keyword search, and so to hybrid retrieval, until the next full
`build`. A content-only corpus feels that hardest: it may never run one.

Now refreshed on every content ingest.

## What the agent sees after upgrading

| Agent | What changes |
|-------|--------------|
| **Claude Code** | Nothing at prompt time. `ingest-content` gains flags; hooks, MCP tools, and retrieval are unchanged. Ingested prose now reaches BM25 immediately, so hybrid retrieval over a docs corpus stops needing a rebuild first. |
| **Cursor / Cline** | Same. The MCP tool surface is unchanged. |
| **Generic MCP** | Unchanged. |
| **CI / scripts** | `ingest-content --json` gains `files_skipped`, `chunks_embedded`, `orphans_removed`, `timed_out`, `project_path`, `content_only`, `incremental`. Existing keys keep their meaning, except `files_processed`, which now counts files actually embedded rather than files seen — `files_total` is the old number. `status --json` gains `index` and `content` objects; its synapse keys are untouched. |

## Compatibility

- **`--chunk-size` / `--overlap` defaults are unchanged** (500 / 50). They now
  fall through to `NEURALMIND_CHUNK_SIZE` / `NEURALMIND_OVERLAP` when the flags
  are absent.
- **An overlap ≥ the chunk size now exits `2`** with both values named, instead
  of surfacing the chunker's `ValueError` per file mid-run.
- **Project-root resolution changed order.** A directory carrying its own
  `.neuralmind/` now wins over the cwd. If you relied on running from a project
  root to redirect an ingest elsewhere, pass `--project-path`.
- The first `--content-only` run on a bare directory writes
  `.neuralmind/index_ir.json`. If you created that file by hand with
  `{"is_content_project": true}`, replace it — it isn't a loadable IR. Deleting
  it and re-running `--content-only` writes a valid one.

## Upgrading

```bash
pip install --upgrade neuralmind
```

No rebuild required. The first `ingest-content` run after upgrading writes a
manifest, so it re-embeds as usual; every run after that is incremental.
