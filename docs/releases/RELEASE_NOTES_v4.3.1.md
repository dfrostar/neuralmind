# NeuralMind v4.3.1

**Date:** 2026-09-25 | **Type:** Patch release | **PR:** [#532](https://github.com/dfrostar/neuralmind/pull/532)

A one-root-cause, three-symptom fix. All three trace to `_is_book_project()`
comparing a **recursive** `**/*.md` glob against a **root-only** code glob —
so any code repo whose code lives in a package subdirectory (including
NeuralMind itself) with three or more `.md` files anywhere was misclassified
as a **book project**.

## What that caused

| Symptom | Before v4.3.1 |
|---------|---------------|
| Runaway build | Book-mode ingested the **entire repo** as "chapters" (on this repo: ~28K chunks, ~875 ONNX child processes, multi-hour build) |
| False doctor failure | `neuralmind doctor` reported `[FAIL] no nodes embedded` on a healthy scoped build — it probed only the default-scope `store.sqlite` while book builds write `store.code.sqlite` |
| Junk ingestion | `ingest_directory()` had no ignore handling — vendored corpora (`.bench-work`, `node_modules`) and state dirs were swept into the content store |

## Fixes

1. **`_is_book_project()` same-basis counting** (`cli.py`) — both markdown and
   code files counted via `os.walk`, with vendored/state dirs pruned from BOTH
   counts. A code repo with a package subdir is no longer a "book".
2. **Doctor per-scope probe** (`doctor.py`) — when the default-scope store is
   empty, doctor sums the per-scope stores (`store.{code,content,docs}.sqlite`),
   so a healthy scoped build reports its real node count. Uses
   `Path.as_uri()` for Windows-safe read-only URIs.
3. **Ingestion ignore guard** (`document_ingestion.py`) —
   `INGEST_IGNORED_DIRS` frozenset + dot-dir skip in `_walk()`; vendored
   corpora and state dirs are never ingested as content.

## Verification

- Classification matrix: code repo → `False`, real book (26 chapters) →
  `True`, doc-heavy repo with `src/` → `False`, pure-prose → `True`
- `neuralmind doctor` on this repo: `[ ok ] Semantic index: 5848 nodes
  embedded` (was FAIL)
- 110 tests passing across book-indexing, doctor, document-ingestion,
  ingest-content, and skill-manifest suites; 21/21 CI checks green
  (ubuntu/macos/windows, Python 3.10–3.12)
- Adversarial QA: Qwen 3.8 Flash parallel review — 4 findings triaged,
  3 prompt-artifact false positives rejected after re-reading the code,
  1 genuine (Windows URI portability) fixed via `as_uri()`

## Upgrade notes

No action needed — behavior only changes for projects that were previously
misrouted into book mode. If you *intentionally* build a book-like project
whose auto-detection now differs, pass `--content-type book` explicitly.
