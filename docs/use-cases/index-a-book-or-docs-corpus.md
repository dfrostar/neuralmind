# Index a book or docs corpus *(v3.4.0+)*

**Best for:** anyone pointing NeuralMind at prose — a book manuscript, a
handbook, an ADR archive, a research folder — rather than at code.

**Primary goal:** a searchable index of the corpus, scoped to the corpus, that
re-indexes in seconds as you write.

---

## The problem

`neuralmind build .` is built for code. Point the ingest at a folder of
Markdown that lives inside a git repo and two things go wrong:

1. **The index lands in the wrong place.** The project root is resolved from
   the nearest marker, and a git root is a marker — so `book/chapters` inside a
   repo resolves to the repo, and the whole codebase gets indexed next to your
   prose.
2. **You pay for a code graph you don't have.** The build generates a
   tree-sitter graph first, which for a folder containing zero code files is
   pure cost.

Then you write another chapter and pay the whole embedding cost again.

## The walkthrough

A manuscript laid out like this:

```
my-book/                 ← a git repo
├── .git/
├── scripts/build_epub.py
└── manuscript/
    └── chapters/        ← 34 .md files, ~150k words
```

### 1. Preview before you pay for it

`--dry-run` parses each file and reports what an ingest would do. Nothing is
embedded, no backend is opened, nothing is written:

```bash
neuralmind ingest-content manuscript/chapters --dry-run
```

```
FILE            BYTES  CHUNKS  STATUS
ch01-intro.md   14203      31  would-index
ch02-setup.md   11890      26  would-index
...
Dry run: 34 of 34 file(s) would be embedded (306 of 306 chunks). Nothing was written.
```

Use it to sanity-check chunking before committing to it: `--chunk-size 1200
--overlap 120 --dry-run` shows what larger chunks do to the count.

### 2. Index the prose, and only the prose

```bash
neuralmind ingest-content manuscript/chapters \
    --content-only \
    --project-path manuscript
```

- `--project-path manuscript` puts the index at `manuscript/.neuralmind/`,
  scoped to the book. Without it you'd get a note telling you it resolved to
  the repo root, and naming this flag.
- `--content-only` skips the code-graph build entirely. `scripts/` is never
  parsed. On a first run it writes a valid empty IR to mark the directory as a
  project, so subsequent runs resolve it without the flag.

While it works you get a progress bar with an ETA on a terminal, and plain
milestone lines when output is redirected — a long embed never looks like a
hang:

```
Ingesting [████████████░░░░░░░░░░░░] 17/34  50.0% · 34s elapsed, ~34s left · ch18-recall.md — 9 node(s)
```

### 3. Check it landed

```bash
neuralmind status manuscript
```

```
═══ NeuralMind Status — manuscript ═══
  Code nodes:   0 (0 edges) — content-only project
  Last build:   0.1h ago
  Disk:         2.1 MB
  Content:      34 file(s), 306 chunks, 306 nodes
  Last ingest:  2026-08-23T13:19:14+00:00
```

`--json` gives the same as `index` and `content` objects, for a CI check.

### 4. Query it

```bash
neuralmind query manuscript "what does the book say about spaced repetition?"
```

Content nodes are searched alongside anything else in the index, through both
vector and BM25 keyword retrieval.

### 5. Keep writing

Edit one chapter, re-run the same command:

```
Ingested 1 file(s) → 9 chunks → 9 nodes (33 unchanged, skipped)
Corpus: 34 file(s), 306 chunks
Wall time: 0.6s | Embed time: 0.46s
```

Only the changed file is re-embedded. Unchanged files are matched by SHA-256
against `manuscript/.neuralmind/content_manifest.json`.

Deleting a chapter or cutting one down evicts its stale chunks, so a query can't
surface prose you removed. `--force` re-embeds everything when you want a clean
slate.

## Wire it into your writing loop

```bash
# In a file watcher, a git hook, or a Makefile target
neuralmind ingest-content manuscript/chapters --content-only --quiet
```

Because re-runs are incremental, this is cheap enough to run on every save. For
a scripted or CI context:

```bash
neuralmind ingest-content manuscript/chapters --content-only --json \
  | jq -e '.success and .errors == []'
```

If a corpus is large enough that a full first pass might overrun a CI job's
budget, `--timeout 600` stops cleanly at the deadline and records what it
indexed; the next run resumes from there rather than starting over.

## Tuning chunk size

Prose and code want different chunk sizes. Set them once instead of retyping
the flags:

```bash
export NEURALMIND_CHUNK_SIZE=1200   # bigger chunks — more context per hit
export NEURALMIND_OVERLAP=120       # must stay below the chunk size
```

Changing either invalidates the manifest on its own: new parameters mean new
chunk boundaries, so every file is re-embedded. Preview the effect with
`--dry-run` before committing to a re-index.

## When something looks wrong

`--verbose` puts the resolved project root, the chunk parameters actually in
effect, per-file chunk counts and embed timings, and every eviction on stderr:

```bash
neuralmind ingest-content manuscript/chapters --content-only --verbose
```

```
  · project root: /my-book/manuscript (explicit)
  · chunk size 500, overlap 50, timeout none
  · manifest: 34 file(s) previously indexed
  · ch18-recall.md: 9 chunks → 9 nodes in 0.43s
```

Diagnostics go to stderr, so `--verbose --json` still produces parseable stdout.

## Related

- [CLI reference: `ingest-content`](../wiki/CLI-Reference.md#ingest-content-v340)
- [CLI reference: `status`](../wiki/CLI-Reference.md#status-v314-index-reporting-v340)
- [`learn` — mixing documents into a *code* project's graph](../wiki/CLI-Reference.md#learn-document-ingestion-v1110)
- [v3.4.0 release notes](../releases/RELEASE_NOTES_v3.4.0.md)
