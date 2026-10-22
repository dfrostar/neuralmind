# NeuralMind site design system

The tokens live in [`tailwind.config.ts`](tailwind.config.ts); the few rules
that need raw CSS (buttons, surfaces, the data table) live in
[`src/app/globals.css`](src/app/globals.css), whose `:root` variables mirror
the config. The docs site (`docs/_layouts/default.html`) copies the same
values into its own `:root`. Change the config first, then the CSS mirror,
then the docs layout.

`tests/test_site_design_tokens.py` (stdlib-only) fails the build on an
arbitrary type value, a raw Tailwind palette colour, a radius outside the
three below, a class naming a colour the config doesn't define, or a token
missing from this file.

## Colour

Two colours do jobs; everything else is neutral.

| Token | Value | Use |
|---|---|---|
| `electric` | `#5B8CFF` | **Interactive.** Links, focus rings, the primary button. If it's blue you can click it. |
| `electric-bright` | `#93B4FF` | Hover state of the above; inline code and commands. |
| `electric-dim` | `#1B2742` | Borders and fills behind electric (`panel-accent`). |
| `proton` | `#4FD1A5` | **Evidence.** A number that was measured, a CI-gated or reproducible badge, the NeuralMind row in a results table. Never decoration, never generic "success". |
| `proton-dim` | `#16302A` | Fills behind proton. |
| `iris` | `#8A93A3` | Retained so stray references resolve; don't use in new work. |

### Surfaces

| Token | Value | Use |
|---|---|---|
| `carbon` | `#0A0B0D` | Page background (also the `theme-color` meta). |
| `carbon-raised` | `#0F1114` | Bands, terminal chrome, code wells inside a card. |
| `carbon-card` | `#131518` | Cards and panels. |
| `carbon-border` | `#22262C` | Hairlines, card borders, table row rules. |
| `carbon-line` | `#2E333B` | Stronger rules: table heads, secondary button border. |

### Text

All four clear WCAG AA (4.5:1) on every surface; the ratios are on
`carbon` / `carbon-card`.

| Token | Value | Contrast | Use |
|---|---|---|---|
| `ink` | `#E8EAED` | 16.3 / 15.2 | Page default, emphasis inside body copy. Headings use `text-white`. |
| `body` | `#C9CED6` | 12.5 / 11.6 | Running copy, table cells you should read. |
| `muted` | `#9AA3AF` | 7.7 / 7.2 | Secondary copy: ledes, notes, table cells you scan. |
| `faint` | `#7E8794` | 5.4 / 5.0 | Captions, labels, eyebrows, legal lines. The floor: nothing dimmer. |

### Verdicts

For tables that grade claims (refuted / modeled / passing). Each clears 6.6:1
on every surface.

| Token | Value | Use |
|---|---|---|
| `danger` | `#F27B7B` | Refuted, failing, a published loss. |
| `warn` | `#E5B567` | Modeled, mixed, aspirational, overclaim. |
| `success` | `#6CCB86` | A status that passes (no open reports) and checklist ticks. |

A row graded **Measured** is evidence, so it takes `proton`, not `success`.

## Type

Inter for text, Inter Tight (`font-display`) for headings, JetBrains Mono
(`font-mono`) for code, labels and measured numbers (`.metric`). Tailwind's
own steps (`text-xs` … `text-5xl`) are fine; these fill the gaps so no page
needs `text-[…]`.

| Token | Size / line height | Use |
|---|---|---|
| `eyebrow` | 11px / 16px | Uppercase mono labels and table heads, with `tracking-eyebrow`. The `.eyebrow` class bundles it. |
| `caption` | 13px / 20px | Table row heads, terminal text, small print. |
| `body-sm` | 15px / 24px | Card ledes, mobile nav links. |
| `title-sm` | 17px / 24px | Card titles, the wordmark. |
| `stat` | 28px / 1 | The value in a `Stat`. |
| `display` | 44px / 1.05 | Page `h1` and section `h2` at `md:` and up. |
| `hero` | 56px / 1.05 | The homepage `h1` only, at `lg:`. |
| `code-inline` | 0.875em | `<code>` inside running text; relative, so it follows the paragraph. |

Line height `leading-display` (1.05) goes on display headings at every
breakpoint. Letter spacing: `tracking-tightest` (-0.045em, `h1`),
`tracking-tighter` (-0.03em, other headings), `tracking-eyebrow` (0.14em).

## Radius

The config replaces Tailwind's radius scale, so these are the only ones that
generate CSS.

| Token | Value | Use |
|---|---|---|
| `control` | 6px | Anything you click or that sits inline: buttons, badges, inline code, code wells nested in a card, step numbers. |
| `card` | 12px | A surface: cards, panels, callouts, pre blocks, tables. |
| `pill` | full | Status dots and pill tags. |

Hairline ledger grids (`StatGrid`, the feature and step grids) are square:
their cells draw their own bottom/right rules, which a radius would clip.

## Components

### Buttons — `.btn-primary`, `.btn-secondary`

CSS classes, applied to an `<a>` or `<Link>` (every button on the site
navigates). Primary is solid `electric` with dark text, hover
`electric-bright`; secondary is transparent with a `carbon-line` border. One
primary per view. There is deliberately no `Button` component: a second
definition is how a page ends up with the old gradient.

### `Stat` and `StatGrid` — `@/components/ui/Stat`

```tsx
<StatGrid className="sm:grid-cols-3">
    <Stat label="Gold file found" value="40 of 40" note="…" evidence="reproducible" />
</StatGrid>
```

| Prop | Type | |
|---|---|---|
| `label` | string | Eyebrow above the value (the `<dt>`). |
| `value` | node | The number, in `.metric text-stat`. Must be in `claims.json`. |
| `note` | node? | One or two sentences of context in `muted`. |
| `evidence` | `EvidenceLevel`? | Renders an `EvidenceBadge` under the note. |
| `figure` | boolean = true | `false` for a word rather than a number: set in the display face. |

`StatGrid` takes the column classes; any count closes cleanly.

### `EvidenceBadge` — `@/components/ui/EvidenceBadge`

`<EvidenceBadge level="ci-gated" />`. The levels are the keys of
`_evidence_levels` in [`claims.json`](claims.json), and the badge's tooltip is
that level's definition from the same file; a level added there without a
label here fails the TypeScript build.

| `level` | Label | Look |
|---|---|---|
| `ci-gated` | CI-gated | `proton`, filled |
| `reproducible` | Reproducible | `proton`, outline |
| `field-report` | Field report | `body`, neutral outline |
| `community` | Community | `muted`, neutral outline |
| `pilot` | Pilot | `body`, neutral outline — pre-registered and measured, but exploratory |
| `disclosure` | Not measured | `faint`, dashed |

`children` replaces the label ("Field report — not CI-gated").

### `Callout` — `@/components/ui/Callout`

`<Callout variant="not-measured">…</Callout>` renders an `<aside role="note">`
in `card` radius.

| `variant` | Look | Use |
|---|---|---|
| `note` (default) | card surface | Context the reader can skip. |
| `evidence` | `proton` border and label | Points at a measured result. |
| `caution` | `warn` border and label | A limit or a known loss. |
| `not-measured` | dashed, `faint`, titled "Not measured" | What the site does not measure. Pair it with a `disclosure` entry in `claims.json`. |

`title` overrides the label.

### Data table — `.data-table`

```tsx
<div className="overflow-x-auto">
    <table className="data-table min-w-[34rem]">
        <thead><tr><th scope="col">Backend</th><th scope="col" className="num">Recall</th></tr></thead>
        <tbody>
            <tr className="is-ours"><th scope="row">neuralmind</th><td className="num">1.00</td></tr>
        </tbody>
    </table>
</div>
```

Head row in the eyebrow style over a `carbon-line` rule; cells in `muted`
with `carbon-border` rules; row heads in mono `caption`. `.num` right-aligns
on tabular figures; `.is-ours` tints the measured subject's row with
`proton`. Give the table a `min-w-*` inside an `overflow-x-auto` box so a
phone scrolls the table, not the page.

### Surfaces and text helpers

- `.card` — a surface you can click (border brightens on hover). `.panel` —
  the same surface, no hover. `.panel-accent` — a panel washed with
  `electric`, for the one call to action on a page.
- `.eyebrow` — section label. `.metric` — mono, tabular, tight: any measured
  number. `SectionHeader` — eyebrow + `display` title + `muted` lede, used by
  every homepage section.

### Numbers — `@/lib/evidence`

A page doesn't type a measured number. It asks `lib/evidence.ts`, which reads
`site/claims.json`, the committed public-benchmark run
(`bench/public/results.json`) and the 150-question retrieval eval at build
time:

| Export | Gives |
|---|---|
| `ratio(48.8)`, `ratioRange(31, 67)` | `{ text, evidence, source, reproduce }`. Throws, failing `next build`, when claims.json doesn't list the value. |
| `headline('ripgrep (query keywords')` | A non-ratio claim by a phrase from its text, with its evidence level. |
| `publicBenchmark` | Per-repo tables, `found('ripgrep')` → "32 of 40", token ranges. Each per-repo ratio is checked against claims.json. |
| `publicQuery(repo, id)` | One query's context files and tokens per backend (the homepage's side-by-side). |
| `retrievalEval` | The 150-question top-5 rate and miss count, counted from the raw ranks. |
| `disclosures` | The `disclosure` entries, for a `not-measured` `Callout`. |

Pass a figure's `evidence` straight to `Stat` or `EvidenceBadge`, so the badge
can't claim more than claims.json does. The module is server-only: its imports
are large, and a client component that imported it would ship them. Copy that
quotes a number literally still works and is still read by
`tests/test_site_claims.py`; prefer the module for anything in a stat or table.

### `CommandLine` — `@/components/ui/CommandLine`

A copyable shell command. `className` sizes the box (`flex-1` to fill a row,
so a stack of commands lines up).

## Not covered yet

- Hero stats now use `Stat`; `site/public/graph-view.webp` is a real
  `neuralmind serve` capture of the psf/requests index (re-capture it the same
  way, cropped above the sidebar's per-query ratios, which aren't in
  claims.json).
- `docs/about.html` carries a third palette (light background, the
  violet template gradient) and its own markup; it is left for the docs IA
  rework rather than restyled piecemeal.
- `docs/index.html` (a redirect) and `docs/benchmarks/index.html` keep their
  own inline styles.
