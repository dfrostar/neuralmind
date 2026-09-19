# Social preview card

Source of truth for the two social preview images:

| Output | Size | Goes to |
|--------|------|---------|
| `site/public/social-preview.png` | 2400×1260 | Served at `neuralmind.uk/social-preview.png` (the OG image `site/src/app/layout.tsx` declares). Deploys with the site on push to `main`. |
| `scripts/og-card/github-social-preview.png` | 2560×1280 | Uploaded **manually** at repo Settings → Social preview → Edit. GitHub has no API for this slot, so re-upload after every re-render. |

## Render

```bash
npm i --no-save playwright-core
node scripts/og-card/render.mjs
```

Chromium is resolved from `$OG_CHROME`, then `$PLAYWRIGHT_BROWSERS_PATH`
(pre-set on Claude Code on the web), then Playwright's default install.

## The claims gate

`render.mjs` refuses to render if any number in `card.html`'s visible text is
missing from `site/claims.json`. This is deliberate and load-bearing: the
previous hand-made image shipped **"40-70x token reduction"** — a figure with
no source anywhere in the repo — because images are the one claim surface
`tests/test_site_claims.py` cannot scan. Numbers enter this card the same way
they enter the homepage: `claims.json` first, copy second.

If you change the card's copy, update `REQUIRED_CANON` in `render.mjs` to
match. If the render fails on a number you just added, that's the gate doing
its job — add the measured claim to `claims.json` before shipping it.

## Design constraints

- Palette and type are the site's design tokens (`site/tailwind.config.js`):
  carbon neutrals, `electric` #5B8CFF as the single interactive accent,
  `proton` #4FD1A5 reserved for measured numbers, Inter Tight for display,
  JetBrains Mono for figures. Blue means "clickable", green means "measured" —
  don't add colors with no job.
- Absolute privacy claims are forbidden here exactly as in the docs guard:
  "local-first · no telemetry", never "code never leaves your machine".

## Fonts

`fonts/` vendors the latin woff2 subsets of Inter, Inter Tight and JetBrains
Mono (all SIL Open Font License 1.1) so renders are hermetic — no network at
render time, identical output everywhere.
