# Social preview card

Source of truth for the three social preview images:

| Output | Size | Goes to |
|--------|------|---------|
| `site/public/social-preview.png` | 2400×1260 | Served at `neuralmind.uk/social-preview.png` (the OG image `site/src/app/layout.tsx` declares). Deploys with the site on push to `main`. |
| `docs/assets/social-preview.png` | 2400×1260 | Served at `docs.neuralmind.uk/assets/social-preview.png` (the OG image `docs/_layouts/default.html` declares for every docs page). Deploys with the docs site. |
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

- Palette, type and mark are the site's (`site/DESIGN.md`): graphite in three
  steps, the engram mark, Host Grotesk for words, Atkinson Hyperlegible Mono
  for the measured figures. Amber means a person, blue means measured; don't
  add colours with no job.
- The background is a still frame of the site's liquid. `render.mjs` lifts
  the fragment shader out of `site/src/components/ui/LiquidBackground.tsx`
  and injects it, so the card and the site can't drift; it renders through
  SwiftShader, so no GPU is needed. Opened by hand, the card shows the plain
  ground.
- Absolute privacy claims are forbidden here exactly as in the docs guard:
  "local-first, no telemetry by default", never "code never leaves your
  machine".

## Fonts

`fonts/` vendors the latin woff2 subsets of Host Grotesk (variable, 300 to
800) and Atkinson Hyperlegible Mono 400, both SIL Open Font License 1.1, so
renders are hermetic: no network at render time, identical output everywhere.
