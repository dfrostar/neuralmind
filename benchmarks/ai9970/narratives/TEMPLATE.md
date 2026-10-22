# YYYY-MM — performance record

Copy this file to `YYYY-MM.md` (the month the rows are from). Only files named
that way are read; this one is not. Use exactly these four `##` headings and no
other headings: any other heading fails the site build, so a block can't be
mis-nested into a published one.

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

## D. Integrity

Never published. Anything about how the rows were produced that should not be
on the site: reruns, excluded runs, rows withheld because their baseline was not
measured, open questions about a number.
