---
name: github-issue-audit
description: Audit a GitHub repository's open issues for hygiene — stale issues, likely duplicates, missing/incorrect labels, and issues that are actually already fixed on main. Use when asked to triage the backlog, clean up issues, find duplicates, or report on issue health. Produces a ranked, actionable report; it never closes or edits issues on its own.
version: 0.1.0
author: dfrostar
license: MIT
tags:
  - github
  - triage
  - maintenance
  - project-management
triggers:
  - audit issues
  - triage the backlog
  - find duplicate issues
  - stale issues
  - issue hygiene
  - clean up issues
  - label the issues
  - issue health report
allowed_tools:
  - list_issues
  - search_issues
  - issue_read
  - get_label
  - list_commits
  - search_code
metadata:
  complexity: low
  category: developer-tools
---

# GitHub Issue Audit

Produce an honest, actionable audit of a repo's open issues. You **read and
recommend**; you do not close, relabel, or comment on issues unless the user
explicitly asks for that action after seeing the report.

## What "audit" means here

Four checks, run over every open issue, reported most-actionable first:

1. **Stale** — no activity for a long window (default 90 days). Distinguish
   *abandoned* (needs a close/ping) from *quietly-still-valid* (needs a
   label, not a close).
2. **Likely duplicate** — another open or recently-closed issue covers the
   same problem. Report the pair with a one-line reason; never assume — the
   maintainer confirms.
3. **Label hygiene** — missing a type label (bug/feat/docs), missing a
   priority, or a label that contradicts the body. Propose the corrected set.
4. **Already fixed** — the described bug looks resolved on `main`. Cross-check
   with `list_commits` / `search_code` before claiming this; a fixed-looking
   issue that's actually still open is the most embarrassing miss.

## Procedure

```
1. get_me                         confirm permissions/context
2. list_issues (state=open)       page in batches of 5-10, minimal_output
3. For each issue:
     issue_read                   full body + current labels + timeline
     classify into the 4 buckets above
4. For "already fixed" candidates only:
     search_code / list_commits   verify the fix actually landed
5. Emit the report (below). Stop. Do not mutate anything.
```

Be frugal with API calls — batch, use `minimal_output` when the full body
isn't needed, and only deep-read issues that a cheap signal already flagged.

## Report shape

A markdown table, then a short "recommended actions" list. Rank by
actionability (fixed > duplicate > mislabeled > stale), not by issue number.

```
| # | Title | Finding | Confidence | Suggested action |
|---|-------|---------|------------|------------------|
| 142 | "crash on empty repo" | already fixed in a1b2c3d | high | close w/ ref |
| 130 | "add --json flag" | dup of #98 | medium | link + close one |
```

Every "close" or "relabel" suggestion is a *proposal*. Confidence is honest:
`high` only when you verified (a commit ref, an exact-duplicate body);
`medium`/`low` otherwise, and say what would raise it.

## Acting on the audit (only when asked)

If the user says "go ahead and apply these" (or similar), then and only then:
mutate in small, reversible steps — relabel before closing, close with a
comment that references the duplicate/fix, and never bulk-close on `medium`
confidence without a second confirmation. Report what you changed.

## Anti-patterns

- **Don't** close an issue on a hunch. "Already fixed" needs a commit ref;
  "duplicate" needs the sibling issue number.
- **Don't** relabel to match a convention you assumed — check the repo's
  actual labels with `get_label` / the labeler config first.
- **Don't** dump all issues verbatim. The value is the *classification*, not
  a reprint of the backlog.
