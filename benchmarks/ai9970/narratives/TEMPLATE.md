# YYYY-MM — performance record

Copy this file to `YYYY-MM.md` (the month the rows are from). Only files named
that way are read; this one is not. Use exactly these three `##` headings and no
other headings: any other heading fails the site build, so nothing can sit in a
published block under a heading of its own. Every block is published.

Notes on how the rows were produced (reruns, excluded runs, rows withheld
because their baseline was not measured, open questions about a number) are
not part of a narrative. This repo is public on GitHub, so they go in the
private repo named in `site/claims.json` (`longitudinal_record.integrity_notes`):
dfrostar/neuralmind-marketing, `internal/performance-record/ai9970/YYYY-MM.md`.
A `## D` block or a heading that names them fails the build.

## A. Site

Rendered inline on https://neuralmind.uk/performance/. Paragraphs, `- ` bullet
lists, `inline code`, **bold** and [links](https://example.com) only. Quote a
ratio only if it is a measured row's `ratio_vs_indexed` or is listed in
`site/claims.json`; `tests/test_performance_record.py` checks.

## B. LinkedIn

Plain text, served verbatim at https://neuralmind.uk/performance/linkedin.txt
for copying into a post. Same claim rules as block A.

## C. What we are working on

- [moved] An area for improvement that changed since last month, and how.
- [stalled] One that did not, and why.
