# Session Accomplishments & Next-Session Plan — Site Redesign (benchmarks + wiki)

**Created:** 2026-07-13 12:20 UTC
**Author:** Claude Code session (benchmarks/wiki redesign)
**Predecessor:** `docs/plans/2026-06-06-onboarding-lift-eval-handoff.md`
**Purpose:** record what shipped this session, and hand off the one remaining
redesign increment — **`docs/about.html`** — with a copy-paste prompt to
resume in a fresh session.

---

## 1. What we accomplished this session

**PR #327 (merged, squash `801f34c`):** the live `neuralmind.uk/benchmarks/`
page and every `/wiki/*` page were still on pre-redesign styling — the old
light `#667eea` gradient theme (benchmarks) and the stock GitHub Pages Primer
theme (wiki). Both now render on the dark design system `docs/index.html`
established. CI was 19/19 green on the merged SHA.

| Surface | What shipped |
|---|---|
| `docs/benchmarks/index.html` | Full rebuild: shared nav/footer, gradient hero ("Benchmarks you can re-run yourself"), static headline stats band, and a **new public-benchmark section** — `requests`/`click` result tables with the `neuralmind` row highlighted, four method cards, the "read the losses too" note, and a copy-button repro block. The page now leads with the CI-verified proof instead of a two-row community table. |
| `docs/benchmarks/dashboard.css` | Rewritten against the shared dark tokens (was the old light palette). |
| `docs/benchmarks/dashboard.js` | Charts restyled for the dark card surface with a **CVD-validated categorical palette** (the old GitHub-linguist colors failed hard: Java↔C# ΔE 1.3 under protanopia). Fixed color slot per language — never cycled — plus distinct point shapes on the scatter as secondary encoding and per-bar `n=` sample-size tick lines. Column sorting implemented (the header had advertised it with `cursor: pointer` but had no handler). Chart failures are non-fatal: stat cards + table render from the JSON regardless. |
| `docs/benchmarks/chart.umd.min.js` | **Chart.js 4.4.1 vendored** — the dashboard makes zero third-party requests, matching its own "no server, no tracking" footer claim. |
| `docs/_config.yml` + `docs/_layouts/default.html` | New Jekyll layout wrapping **every rendered markdown page** (wiki, root docs like `HONEST-ASSESSMENT`, use-cases, `benchmarks/public.md`) in the dark chrome: sticky nav, docs subnav with active-page state, breadcrumbs, edit-on-GitHub link, dark rouge syntax tokens, tables that scroll inside their own box, shared footer. Wiki `.md` files stay **front-matter-free** so the `sync-wiki` GitHub-Wiki mirror is unaffected (layout assigned via config `defaults`; GitHub Pages' always-on `jekyll-optional-front-matter` does the rest). |
| Plumbing | Benchmarks added to the homepage nav (was footer-only); sitemap `lastmod` bumped for `/benchmarks/` + `/wiki/`; `Dataset` JSON-LD added on the benchmarks page (schema.org was a documented gap in CLAUDE.md). |

**Verification that held:** local Jekyll build with the exact plugin set GitHub
Pages enables (`jekyll-optional-front-matter`, `jekyll-relative-links`,
`jekyll-titles-from-headings`, `jekyll-default-layout`, `jekyll-readme-index`);
`index.html` / `about.html` / `benchmarks/index.html` passed through
**byte-identical** (diff-verified); Chromium screenshots at 1440px and 390px
with a clean console; palette validated programmatically (lightness band,
chroma floor, CVD separation, WCAG contrast) against the dark card surface
`#0e1626`.

**Known pre-existing quirk (untouched):** a cosmetic Liquid warning in
`wiki/Usage-Guide.md` from a GitHub Actions `hashFiles()` snippet — fires on
the live Pages build today too.

### Design-token reality (important for any future styling work)

The dark tokens are currently **copied inline in three places** — the `:root`
block of `docs/index.html`, the top of `docs/benchmarks/dashboard.css`, and the
`<style>` block of `docs/_layouts/default.html`. Keep them in sync when the
palette changes (or extract a shared stylesheet if a fourth copy is about to
appear):

```
--bg #070b15 · --bg-raised #0c1322 · --bg-card #0e1626
--border #1b2740 · --border-strong #28395c
--text #e7ecf5 · --text-dim #97a3ba · --text-faint #67748f
--accent #8b7cf8 · --accent-bright #a99cff · --accent-deep #6d5ae6
--green #4ade80 · --red #f87171 · --amber #fbbf24
fonts: Inter + JetBrains Mono
```

Validated chart palette (dark, fixed slot order): `#3987e5` `#199e70`
`#c98500` `#008300` `#9085e9` `#e66767` `#d55181` `#d95926`.

---

## 2. What's left

### 2.1 Post-deploy live checks (do these first, ~2 minutes)

GitHub Pages rebuilds from `main` after the merge. Verify on the live site:

- [ ] `https://neuralmind.uk/wiki/Home` renders with the dark layout (this is
      the one piece built by GitHub's Jekyll 3.10 rather than the local 4.4.1
      — the layout uses only basic Liquid, but confirm).
- [ ] `https://neuralmind.uk/benchmarks/` — charts draw, table sorts, no
      console errors.
- [ ] `https://neuralmind.uk/benchmarks/public.md` still resolves (linked from
      the homepage and the sitemap).
- [ ] Homepage nav shows the new Benchmarks link.

### 2.2 The remaining increment: `docs/about.html`

The **last page on the old light theme** (`#667eea`/`#764ba2` gradient,
~149 KB / 1,044 lines). Deliberately excluded from PR #327 because it's an
accumulated archive: per CLAUDE.md, every release adds a "What's New in
vX.Y.Z" section **above** the prior one and old sections are demoted, never
deleted. A redesign must restyle the shell without losing that content
contract — and ideally make the archive navigable (e.g. a version index or
collapsed older entries) rather than a 1,000-line scroll.

---

## 3. Copy-paste prompt for the next session

> The benchmarks + wiki redesign shipped in PR #327 (merged 2026-07-13).
> Read `docs/plans/2026-07-13-site-redesign-session-handoff.md` first.
>
> 1. Run the post-deploy live checks in §2.1 against neuralmind.uk and fix
>    anything that regressed.
> 2. Redesign `docs/about.html` onto the same dark design system used by
>    `docs/index.html`, `docs/benchmarks/`, and `docs/_layouts/default.html`
>    (tokens in §1 of the handoff). Preserve every "What's New" section —
>    demote, never delete — and make the archive navigable. Keep the
>    docs+SEO checklist in CLAUDE.md in mind (refresh `docs/about.html`
>    page-level `<meta>`, bump its sitemap `lastmod`).
> 3. Verify the same way as last session: local Jekyll build with the GitHub
>    Pages default plugins (confirm other pages pass through byte-identical),
>    Chromium screenshots at 1440px and 390px, clean console.
> 4. Ship as one PR; commit prefix `docs:` (never `feat:` — release-please
>    would cut a release).

---

## 4. Conventions that held this session (keep holding them)

- Docs/site-only changes use the `docs:` commit prefix; `CHANGELOG.md` and
  version numbers are release-please's, never hand-edited.
- Wiki `.md` files never get front matter (the GitHub-Wiki mirror would
  render it as literal text).
- Any new categorical chart palette gets validated for CVD separation and
  contrast against the actual surface color before shipping — never eyeballed.
- The site makes no third-party requests it doesn't have to (Chart.js is
  vendored; fonts are the one remaining external dependency).
- Draft PR, merged green, watched until merged.
