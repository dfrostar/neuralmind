# NeuralMind v3.8.0 — unified content+code search for book-like projects

**Release Date:** 2026-09-02

## Summary

`v3.4.0` added `neuralmind ingest-content` for book-like projects (prose
indexed without walking into an enclosing repo's code). v3.8.0 adds the
query-side counterpart: `--mode=unified` searches content and code scopes
together and merges the results, with a scope bias and chapter filtering
for corpora organized that way.

## What's new

- **`neuralmind query --mode=unified`** — searches both the content scope
  and the code scope for a project and merges results, rather than
  querying one scope by default.
- **`--scope-bias=content|code|balanced`** — weights which scope's hits
  rank higher in the merged results (default `balanced`).
- **`--chapter=<name>`** — filters unified results to a specific chapter
  (e.g. `--chapter="Chapter 2 — The Corner Pub"`), for corpora that tag
  content nodes by chapter.

## Fixes

- **benchmark:** reverted a change that had silently changed which
  benchmark mode ran, restoring the recall gate and publishing the mode it
  had been hiding — so the reported number is the one the gate actually
  checked.
- **docs:** replaced absolute network-claim wording ("no network calls",
  unqualified) that predated the v3.7.1 disclosure work, and brought the
  a0-plugins/Agent Zero ecosystem debut posts onto the integration branch.
- Restored the community-benchmark README markers that a prior change had
  disturbed.

## What the agent sees post-install

New CLI surface: `--mode=unified`, `--scope-bias`, and `--chapter` on
`neuralmind query`, useful for a book/documentation project that also
contains some code (or vice versa) and wants a single query to search
both without picking a scope up front. No new MCP tools, hooks, or env
vars.

**Documentation gap found and closed while writing this note:** these three
flags were never added to
[`docs/wiki/CLI-Reference.md`](../wiki/CLI-Reference.md) at release time —
backfilled as part of the same documentation-freshness pass that produced
this file.

## Upgrading

```bash
pip install --upgrade neuralmind
neuralmind query . "how does the corner pub scene end?" --mode=unified --scope-bias=content
```
