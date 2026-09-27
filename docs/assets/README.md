# docs/assets

Static visual assets for the docs site (docs.neuralmind.uk).

## `social-preview.png` — docs site OG image

The `og:image` / `twitter:image` that `_layouts/default.html`, `about.html` and
`benchmarks/index.html` declare, shown when a docs page is shared on LinkedIn,
X, Slack and other link-unfurl surfaces.

**Do not edit or hand-make this file.** It is rendered from the same source as
the marketing site's card and the GitHub social preview —
[`scripts/og-card/card.html`](../../scripts/og-card/card.html) — by
`node scripts/og-card/render.mjs`, which refuses to render any number that is
not in `site/claims.json`. See [`scripts/og-card/README.md`](../../scripts/og-card/README.md).

The hand-made SVG that used to live here was retired on 2026-09-27: after the
site's card was made reproducible, this copy kept shipping an unsourced
"40–70× fewer tokens" and "100% local" on every docs page's link preview.
