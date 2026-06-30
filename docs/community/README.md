# Community pages

Honest, maintainer-published pages that summarize where developers discuss
NeuralMind — built to be the most *useful and accurate* answer to brand
queries like "neuralmind reddit", not to fake the discussion.

## What's here

- **[`reddit-roundup.html`](./reddit-roundup.html)** — summary of real Reddit
  discussion of NeuralMind, with linked threads, committed benchmarks, and
  acknowledged limitations.
  **Status: staging draft, unpublished** (`noindex`, not in `sitemap.xml`,
  not linked from nav/homepage). It goes live only when the publish gate
  below is met.

## Why a "reddit" page at all

Developers and LLMs search `neuralmind reddit` for unfiltered opinion. The
honest play is to *be* the best answer to that query on our own turf —
aggregating real threads with disclosure — rather than fabricating a forum.
The dishonest version (fake usernames, invented quotes, `DiscussionForumPosting`
schema, `/reddit/` impersonation URLs) gets deindexed by spam updates and
destroys trust the moment a developer checks one link. We don't do that.

## Hard rules (non-negotiable)

1. **Never fabricate** a quote, username, upvote count, date, or benchmark —
   not even as a "real-style" placeholder meant to look real. Placeholders
   must look like placeholders: `[[ ADD REAL THREAD ]]`.
2. **Every benchmark number traces to a committed source** in this repo
   (`benchmarks/public.md`, `HONEST-ASSESSMENT.md`) and is cited inline. If
   we haven't measured it, we don't claim it (e.g. no SWE-bench number).
3. **Criticism stays honest** — only real NeuralMind limitations (sourced from
   `HONEST-ASSESSMENT.md`), never invented competitor flaws.
4. **Disclosure stays visible** — published by the maintainer, not affiliated
   with Reddit, Inc. Every quote links to its original thread.
5. **`Article` + `FAQPage` schema only.** Never `DiscussionForumPosting` —
   that impersonates Reddit.

## Publish gate for `reddit-roundup.html`

Move it out of staging (remove `noindex`, add to `sitemap.xml`, link from nav
+ homepage footer) **only when both are true**:

1. At least ~3–5 **real** Reddit threads mention NeuralMind, each with a
   working `https://reddit.com/...` permalink.
2. Every quote on the page is a real quote with a real permalink and a real
   score read from the page on the date it was added.

Until then it stays unpublished — an empty "what Reddit says" page that's live
and indexed reads as fake, which is the exact failure we're avoiding.

### Seeding real threads (so the page has something honest to summarize)

The page can't summarize Reddit if there's no Reddit yet. Seed it the honest
way (the project already has draft launch material under
[`../launch/`](../launch/)):

- Post **genuine questions**, not promos (e.g. AST chunking vs full-file
  context benchmarks).
- **Answer support questions** on Reddit as the maintainer, with code.
- Run an **AMA after a major release**.

Those real threads then become the rows in `reddit-roundup.html`. Flywheel,
not astroturf.

## Publish checklist (when the gate is met)

Mirrors the docs + SEO checklist in the root `CLAUDE.md`:

- [ ] Replace every `[[ ADD REAL THREAD ]]` / `REPLACE-…` placeholder with real
      linked content; delete the staging `<!-- … -->` block, the visible
      `.staging` notice, and the `<meta name="robots" content="noindex…">` line.
- [ ] Set the visible "Last reviewed" date and JSON-LD `dateModified`.
- [ ] Add the URL to [`../sitemap.xml`](../sitemap.xml)
      (`community/reddit-roundup.html`, `changefreq monthly`).
- [ ] Link it from the homepage footer ("What developers say on Reddit →") and,
      optionally, the comparison index.
- [ ] Add brand keywords to `docs/index.html` `<meta name="keywords">` if not
      already covered (`neuralmind reddit`, `neuralmind review`).

## Reusable "What Reddit says" snippet for comparison pages

Devs also search `neuralmind vs <tool> reddit`. The honest way to capture that
is a short section on the relevant [`../comparisons/`](../comparisons/) page —
**only with real linked quotes**. Paste this block, then either fill it with a
real thread or leave the honest placeholder until one exists:

```markdown
## What developers say on Reddit

> **Honest note:** this section lists only real, linked threads comparing
> NeuralMind and <TOOL>. None populated yet — we don't invent quotes. Found one?
> [Open an issue.](https://github.com/dfrostar/neuralmind/issues)

<!-- When a real thread exists, replace the note above with:
> "actual quote" — u/realuser on [r/subreddit](https://reddit.com/r/.../comments/...)
-->
```

Live examples of this pattern: [`vs-github-copilot.md`](../comparisons/vs-github-copilot.md)
and [`vs-cursor-codebase.md`](../comparisons/vs-cursor-codebase.md).
