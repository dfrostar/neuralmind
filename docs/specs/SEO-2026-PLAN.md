# SEO Plan — 2026

Status: proposed
Scope: `site/` (neuralmind.uk) and `docs/` (docs.neuralmind.uk)
Author: audit + plan, September 2026

---

## TL;DR

The reference material this plan was built against is a content and authority
playbook: backlinks, digital PR, information gain, query fan-out, topical
authority. That playbook is sound and this plan adopts it.

But an audit of the live site first found two **indexability defects in
production** that make the content work premature. Six pages — including both
commercial-intent pages — tell Google they are duplicates of the homepage, and
the entire FAQ answer body is absent from the served HTML.

Content strategy cannot move a page that is telling the index not to rank it.
Fix the foundation (P0), then run the playbook (P1–P3).

| Phase | What | Effort | Why now |
|-------|------|--------|---------|
| **P0** | Indexability: canonicals, FAQ HTML, sitemap | ~1 day | Blocks everything else |
| **P1** | Topical authority: heal the two-domain split | ~1 week | Authority is currently split across two hosts |
| **P2** | Information gain: surface the benchmark corpus | ~1 week | This is the project's unfair advantage |
| **P3** | Digital PR / links: RAIDS on the benchmark study | ongoing | Only pays off after P0–P2 |

---

## P0 — Foundation: the site is suppressing its own pages

### P0.1 — Six pages canonicalize to the homepage `[CRITICAL]`

**Reproduce:**

```bash
curl -sS https://neuralmind.uk/pricing/ | grep -o '<link rel="canonical"[^>]*>'
# <link rel="canonical" href="https://neuralmind.uk/"/>
```

`site/src/app/layout.tsx` sets `alternates: { canonical: '/' }` at the root.
Next.js App Router merges metadata **shallowly on top-level keys** — a page that
does not set its own `alternates` inherits the parent's object wholesale. Only
`/services`, `/publications/*` and `/field-reports/*` override it.

Everything else emits `rel=canonical` pointing at the homepage:

| Page | Emitted canonical | Sitemap priority |
|------|-------------------|------------------|
| `/pricing/` | `https://neuralmind.uk/` | 0.8 |
| `/effectiveness/` | `https://neuralmind.uk/` | 0.8 |
| `/security/` | `https://neuralmind.uk/` | 0.5 |
| `/privacy/` | `https://neuralmind.uk/` | 0.5 |
| `/terms/` | `https://neuralmind.uk/` | 0.5 |
| `/team/` | `https://neuralmind.uk/` | *(absent from sitemap)* |

The site submits `/pricing/` and `/effectiveness/` in its sitemap at priority
0.8 while the pages themselves declare they are duplicates of `/`. A
self-referencing canonical is the strongest signal that a URL is the indexable
original; pointing it elsewhere is a direct instruction to drop the page.

The same inheritance also gives all six pages, **plus `/services/`**, the
homepage's `og:url`, `og:title` and `og:description` — so every social share of
the pricing page previews as the homepage.

**Fix.** Add an explicit self-referencing `alternates.canonical` to every route,
and page-level `openGraph.url` / `title` / `description`. Note `trailingSlash:
true` in `next.config.js` — canonicals must carry the trailing slash to match
the served URL.

**Prevent regression.** Add `tests/test_site_seo.py` (stdlib-only, matching the
existing `test_site_claims.py` pattern) asserting that every built
`site/out/**/index.html` emits a canonical equal to its own URL. This repo
already enforces its invariants in CI; canonical coverage should be one of them.

### P0.2 — The FAQ has no answers in the HTML `[HIGH]`

**Reproduce:**

```bash
curl -sS https://neuralmind.uk/ | grep -c "RAG stores chunks and retrieves by similarity"
# 0
```

`site/src/components/sections/FAQ.tsx` renders answers behind
`{openIndex === i && (…)}`. The answer text only enters the DOM on click, so the
static export contains **11 questions and zero answers**.

This is the most valuable content on the homepage and it is invisible. The
questions map almost exactly onto high-intent fan-out sub-queries a buyer or an
AI assistant would generate — *"How is this different from RAG?"*, *"Does any
code leave my machine?"*, *"What languages does it support?"*, *"Is NeuralMind
free?"* — and the answers are already written, specific, and first-hand.

**Fix.** Render every answer into the HTML and toggle visibility instead of
existence. Native `<details>`/`<summary>` is the cheapest option: crawlable,
accessible, keyboard-navigable, and needs no client JS — which would also let
the component drop `'use client'`.

**On FAQ schema:** do *not* add `FAQPage` structured data expecting rich
results. Google deprecated FAQ rich results on 7 May 2026 and is removing the
Search Console reporting through August 2026. The markup is harmless but earns
nothing. The fix that matters is putting the prose in the HTML.

### P0.3 — Sitemap hygiene `[MEDIUM]`

`site/public/sitemap.xml` is hand-maintained and has drifted:

- `/team/` is missing entirely.
- The five `/publications/*` entries and `/publications/` omit the trailing
  slash, so **sitemap URLs do not match the canonicals the pages emit**.
- `lastmod` values are stale (latest 2026-08-07).

**Fix.** Generate it. Next.js `app/sitemap.ts` emits a correct `sitemap.xml` on
every static export, derives URLs from the route tree, and cannot drift. Delete
the static file.

### P0.4 — Preview domain is crawlable `[LOW]`

`neuralmind-marketing.pages.dev` serves the full site with `Allow: /`. Its
canonicals are absolute and point at `neuralmind.uk`, so Google should
consolidate — but it burns crawl budget. Serve `X-Robots-Tag: noindex` on the
`*.pages.dev` host.

*(Verified correct, no action: `www.neuralmind.uk` → apex 301; Google Search
Console verification present; `SoftwareApplication` + `WebSite` JSON-LD in the
root layout with the version resolved from the GitHub API at build time.)*

---

## P1 — Topical authority: heal the two-domain split

The topical-authority model is hub-and-spoke: one topical map, every page with
a declared role (hub / supporting / definitional / question), every spoke
linking home and laterally. Measured by content coverage ratio, internal link
depth, ranking breadth, and citation frequency.

NeuralMind **already has the corpus** — and it is genuinely large:

- 16 comparison pages (`docs/comparisons/`) — `vs-rag`, `vs-long-context`,
  `vs-prompt-caching`, `vs-cursor-codebase`, `vs-github-copilot`, …
- 24 use-case walkthroughs (`docs/use-cases/`)
- A full wiki (`docs/wiki/`)
- 5 publications + a field report on the marketing site

**The structural problem: the corpus is on a different host from the hub.**

`neuralmind.uk` is the commercial hub with 15 pages. `docs.neuralmind.uk` holds
~61 sitemap URLs of supporting and definitional content. They are separate
registrable hosts, so authority does not consolidate, and the hub links to the
docs corpus exactly **once** — a single "Docs" nav item pointing at the wiki
home.

Forty pages of on-topic supporting content are doing nothing for the pages that
need to convert.

**Options, in order of preference:**

1. **Merge `docs.` into `neuralmind.uk/docs/`.** One host, one authority
   surface, internal links become real internal links. The `_redirects` file
   shows the docs site was *moved off* the apex, so this reverses a prior
   decision — needs an owner's call on why it moved.
2. **Keep the split, link it properly.** Cross-link every comparison and
   use-case page from the relevant hub section, with descriptive anchors, and
   link each spoke back to the hub. Cheaper, recovers less.

**Assign every page a role** in a topical map committed to the repo. The four
roles: hub (owns the head term), supporting (depth on one sub-topic),
definitional (anchors vocabulary and entities), question (catches long-tail
fan-out queries). The comparison pages are already textbook definitional/
supporting content — they have simply never been wired to a hub.

**Track the four proxies** (no tool reports "topical authority" as a score):
coverage ratio of mapped sub-topics with a live page; internal link depth
(every cluster page within 3 clicks of the hub); ranking breadth in Search
Console filtered to the topic; AI citation frequency, logged monthly.

---

## P2 — Query fan-out and information gain

### Query fan-out

AI Mode decomposes a prompt into 20–50 parallel sub-queries and cites whoever
answers the most of them. Google states plainly that there are **no additional
requirements** to appear in AI Overviews or AI Mode — no `llms.txt`, no special
schema, no rewrite. It is standard SEO pointed at the whole question.

Practical work:

1. **Map the fan** for the head terms — *"memory for AI coding agents"*,
   *"reduce Claude Code token usage"*, *"alternative to pasting files into
   Cursor"*. Ask an assistant what it would research before answering; the reply
   is the fan.
2. **Audit pages against it.** Every unanswered sub-question is a query a rival
   gets cited for.
3. **Lead with the answer.** Answer-first headings and opening sentences; AI
   lifts clean self-contained passages it can quote unedited.
4. **Fix the FAQ (P0.2).** The single largest fan-coverage win available, and it
   is a one-component change.

### Information gain — the unfair advantage

Google's *Contextual estimation of link information gain* patent
(US 11,354,342) scores a document by what it adds **beyond** what the reader has
already seen. Restate the consensus and gain is zero. The five sources that
count: first-hand experience, original data, a defensible contrarian view,
process detail, fresh synthesis.

NeuralMind scores unusually well here and does not exploit it. It owns:

- A public benchmark over 40 pre-registered queries on four pinned OSS repos,
  with committed raw traces.
- `site/claims.json` — every published ratio bound to where it was measured and
  the command that reproduces it, enforced by `tests/test_site_claims.py`.
- A published **"Where NeuralMind loses"** section. Reporting a bare vector-RAG
  baseline that ties or beats you is a defensible contrarian position almost
  nobody in this category takes, and it is exactly the citable, high-gain
  material the model rewards.
- Per-repo variance published rather than rounded away (93.75% mean, 79–100%
  range, `click` named as the weakest repo).

**The gap is packaging, not substance.** This material is in
`docs/benchmarks/public.md` and a JSON file. It is not a linkable, quotable,
citable asset on the marketing site.

**Do:** promote the benchmark to a first-class page on the hub — methodology,
per-repo table, the losses, the reproduction command, raw traces. Keep the
existing claims discipline (evidence level stated, mean *and* range, misses
published) since that discipline is itself the differentiator. Add
`Dataset` / `ScholarlyArticle` JSON-LD.

---

## P3 — Links and digital PR

The one test that decides a link: **would this link exist if search engines did
not?** If no, stop.

The tactics that still earn their time, ranked: digital PR, original data,
video, genuinely free resources, being the obvious answer. NeuralMind is
strongest on the middle three and does nothing with the first.

**Non-negotiables first** (cheap, do immediately): claim and fully complete
every profile — PyPI, GHCR, GitHub topics, Libraries.io, AlternativeTo, Awesome
lists for MCP servers and AI coding tools. An empty profile is a dead profile.

**The RAIDS campaign** — one per quarter, on the benchmark study:

- **Recon** — the story: *what it actually costs to ask an AI agent a question
  about your codebase, measured across four public repos.*
- **Analyze** — the data exists and is committed. Publish the anomalies,
  including where NeuralMind loses.
- **Infiltrate** — 20–30 reporters and newsletter authors covering AI dev tools
  and inference cost. Short list, checked against what they wrote in the last
  12 months.
- **Deploy** — two-sentence intro, three facts, a dataset link. One follow-up
  at day 5–7, then stop.
- **Score** — log every coverage link the day it lands: outlet, URL, linked or
  unlinked, date.

**Genuinely free resources** already shipped and under-promoted: the MIT core,
the reproducible benchmark harness, the SBOM archive. These are linkable
because people *use* them — the strongest link class available and it needs no
outreach.

**Never:** bought links, PBNs, profile farms, bulk press-release syndication,
paid `.gov`/`.edu` placements.

---

## Corrections to the source material

Three points where the reference screenshots needed checking against current
guidance — two hold up, one is a trap:

| Claim | Verdict |
|-------|---------|
| Google patent US 11,354,342 on information gain | **Confirmed.** *Contextual estimation of link information gain*, Google LLC, filed 2018. |
| "No `llms.txt`. No AI markup. No rewrite." for AI Mode | **Confirmed by Google's own docs.** No special schema or files are required. |
| Ahrefs 75,000-brand study; video the strongest AI-visibility signal | **Confirmed.** Q1 2026 AI Search Benchmark Report; YouTube mentions ≈0.737 Spearman vs AI visibility, above branded web mentions (0.66–0.71); Domain Rating only 0.27–0.33. |
| Adding `FAQPage` schema for rich results | **Trap.** Deprecated 7 May 2026. Write the FAQ; skip the markup-for-snippets rationale. |

On `llms.txt`: `docs/llms.txt` already exists and should stay, but for the right
reason. Adoption is ~10% of domains and AI crawlers essentially ignore it
(~408 of 500M bot visits in one 90-day sample); Google has said on the record it
does not support it. It is not a ranking lever. It *is* a legitimate
agent-readiness artifact — and for a product whose users are coding agents,
that is on-brand. Keep it; do not count it as SEO.

---

## Measurement

Baseline before P0 ships, then monthly:

- **Indexed page count** in Search Console — the P0.1 fix should recover six
  pages. This is the cleanest possible before/after.
- **Impressions and clicks on `/pricing/` and `/effectiveness/`** — currently
  suppressed by their own canonicals.
- **Ranking breadth** filtered to the topic cluster.
- **AI citation frequency** — query the major assistants monthly on the mapped
  fan, log who gets cited.
- **Coverage links** from P3, logged the day they land.

## Sequencing

1. **Week 1** — P0 in one PR: canonicals, FAQ, generated sitemap, CI guard.
2. **Weeks 2–3** — P1 decision on the domain split, then the topical map.
3. **Weeks 3–4** — P2 benchmark page.
4. **Ongoing** — P3, one RAIDS campaign per quarter.

P0 is a self-contained change with a measurable outcome and should not wait on
the strategy decisions in P1.

---

## Repo routing

This plan covers surfaces owned by this repo (`site/`, `docs/`) and names files
in it, so it lives here per `CLAUDE.md`. If the P3 outreach work grows into
campaign material — media lists, pitch drafts, competitive positioning — that is
internal strategy and belongs in `dfrostar/neuralmind-marketing/internal/`.
