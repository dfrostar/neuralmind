# NeuralMind site design system

The site wears **Console**, a material from
[Hallmark](https://github.com/nutlope/hallmark) (MIT): a graphite ground in
three lightness steps, hairline panels cut from one surface, one face for
everything a person reads and a mono face only for what an instrument wrote,
and two signal colours with one meaning each. Console is a public theme, so
the material alone would make this one of many pages that look alike. Four
things are the site's own and are what to protect:

1. **The colourway, "NeuralMind graphite".** Console's amber for a person, and
   in place of its sky blue the blue this site has always had, now meaning
   only "measured".
2. **The engram** (`src/components/ui/Logo.tsx`), the mark below.
3. **The record** in the homepage hero: one public-benchmark query drawn from
   `bench/public/results.json` as Console's reading and diff.
4. **The liquid** (`src/components/ui/LiquidBackground.tsx`), the field behind
   every page.

The tokens live in [`tailwind.config.ts`](tailwind.config.ts); the rules that
need raw CSS (controls, surfaces, labels, readings, the data table, the
liquid) live in [`src/app/globals.css`](src/app/globals.css), whose `:root`
variables mirror the config and whose first lines carry the Hallmark stamp.
Change the config first, then the CSS mirror, then the docs site, which
copies the same tokens into three places: `docs/_layouts/default.html`
(every Markdown page), `docs/about.html` and
`docs/benchmarks/dashboard.css` (with the chart chrome in `dashboard.js`).
Those are static and can't import from here, so they are kept in step by
hand.

`tests/test_site_design_tokens.py` (stdlib-only) fails the build on an
arbitrary type value, a raw Tailwind palette colour, a radius outside the
three below, a class naming a colour the config doesn't define, or a token
missing from this file.

## Colour

Two colours do jobs; everything else is graphite. **Never swap them**: an
amber reading or a blue button is the system lying.

| Token | Value | Use |
|---|---|---|
| `electric` | `#F7B83D` | **Amber: a person.** The action you take (the primary button, one per view), the focus ring, a hovered link, the `$` a person types, the learned edge in the mark, the pointer's swirl in the liquid. |
| `electric-bright` | `#FFCC69` | Hover state of the primary button. |
| `electric-dim` | `#38280A` | Fills behind amber. |
| `proton` | `#92B3FB` | **Blue: an instrument.** A number that was measured, a CI-gated or reproducible badge, the NeuralMind row in a results table, a commit sha. Never decoration, never a link. |
| `proton-dim` | `#1F2B44` | Fills behind blue (the `.is-ours` row). |
| `iris` | `#9DA2A8` | Retained so stray references resolve (the `muted` value); don't use in new work. |

The names are legacy (`electric` was the old interactive blue, `proton` the
old evidence green); 300+ usages reference them, so the values were
repointed rather than the call sites renamed.

### Surfaces

A surface is a 1px rule with one step of graphite inside it. No shadow, glow,
blur or gradient, and panels that sit together are one surface divided by
1px rules.

| Token | Value | Use |
|---|---|---|
| `carbon` | `#0D1013` | The ground: `html`, the navbar (also the `theme-color` meta). |
| `carbon-card` | `#15191C` | Cards, panels, the ledger grids. One step up. |
| `carbon-raised` | `#06080B` | The deepest step, despite its name: code wells, inline code, terminal bars, a figure's caption band. |
| `carbon-border` | `#2D3135` | Hairlines, card borders, table row rules. |
| `carbon-line` | `#484E54` | The strong rule: table heads, outlines, the secondary button, the one call-to-action panel, link underlines. |

### Text

All four clear WCAG AA (4.5:1) on every surface and on the liquid, which is
clamped below the luminance where `faint` would fail. Ratios on `carbon` /
`carbon-card` / `carbon-raised`.

| Token | Value | Contrast | Use |
|---|---|---|---|
| `ink` | `#ECEFF2` | 16.5 / 15.3 / 17.4 | Page default, links, inline code, emphasis. Headings use `text-white`. |
| `body` | `#C3C8CC` | 11.3 / 10.5 / 11.9 | Running copy, table cells you should read. |
| `muted` | `#9DA2A8` | 7.4 / 6.9 / 7.8 | Ledes, labels, icons, table cells you scan. |
| `faint` | `#848A90` | 5.5 / 5.1 / 5.7 | Captions, legal lines. The floor: nothing dimmer carries text. |

### Verdicts

Console's ok and bad, for diffs and verdict tables only.

| Token | Value | Use |
|---|---|---|
| `danger` | `#F66D67` | Refuted, failing, a published loss, the minus row of a diff. |
| `warn` | `#F7B83D` | Modeled, mixed, aspirational, overclaim. Amber, because a deviation is something a person should look at, and a third signal colour is what the material forbids. |
| `success` | `#61CB7C` | A status that passes, checklist ticks, the plus row of a diff. |

A row graded **Measured** is evidence, so it takes `proton`, not `success`.

## Type

**Host Grotesk** for everything a person reads, heads included, at 400 for
reading and 500 for every head: the config maps `font-semibold` and
`font-bold` to 500, and `strong` is 600. **Atkinson Hyperlegible Mono**
(`font-mono`, `.metric`, `.reading`) only for what an instrument or the
system wrote: a measured figure, a command, a path, a version, a sha. Its
slashed zero and tailed one are the point. Never mono on a label, a head or a
button. `font-display` resolves to Host Grotesk; the class stays so the heads
that name it keep it.

Heads are one weight and one colour: no accented word inside a head, no
italic word in a roman one.

| Token | Size / line height | Use |
|---|---|---|
| `caption` | 13px / 20px | Labels (`.label`), table heads and row heads, terminal text, small print. |
| `body-sm` | 15px / 24px | Card ledes, mobile nav links. |
| `title-sm` | 17px / 24px | Card titles, the wordmark. |
| `stat` | 28px / 1 | The value in a `Stat`. |
| `display` | 44px / 1.05 | Page `h1` and section `h2` at `md:` and up. |
| `hero` | 56px / 1.05 | The homepage `h1` only, at `lg:`. |
| `code-inline` | 0.875em | `<code>` inside running text; relative, so it follows the paragraph. |

Line height `leading-display` (1.05) goes on display headings. Letter
spacing: `tracking-tighter` (-0.03em) on every display head.

**No eyebrows.** A small label over a heading, and any label in tracked
capitals, are gone from the site; each heading already says what its section
is. A label (a stat's name, a panel's name, a footer column) is `.label`: the
body face at `caption`, 500, sentence case, untracked, in `muted`.

## Radius

The config replaces Tailwind's radius scale, so these are the only ones that
generate CSS.

| Token | Value | Use |
|---|---|---|
| `control` | 6px | Anything you click or that sits inline: buttons, chips, badges, inline code, code wells, step numbers. |
| `card` | 10px | A surface: cards, panels, callouts, pre blocks, tables. |
| `pill` | full | Pill tags. Status dots are gone: a dot with no words is decoration. |

Hairline ledger grids (`StatGrid`, the feature and step grids) are square:
their cells draw their own bottom/right rules, which a radius would clip.
They take the `carbon-card` fill so the liquid never runs through data.

## Motion

A value changes when its source does, over `--dur-short` (140ms) on
`--ease-out`. No reveal, parallax or hover lift; `transform` and `opacity`
only, never `transition: all`. Every animation stops under
`prefers-reduced-motion`. The liquid, with the graph that condenses out of
it, is the one thing that moves on its own.

## The mark — `@/components/ui/Logo`

An engram: an activation pattern on a 4 by 4 grid. The two full columns are
two files your agent used together (`ink`); the two diagonal cells are the
association NeuralMind learned between them (`electric`, amber, because it was
learned from how a person works); the six cells that never fired stay drawn
in `carbon-line`. The lit cells spell the N. It takes no colour class: the
cells colour themselves.

`public/icon.svg`, `public/favicon.ico` (16 to 64px) and
`public/apple-touch-icon.png` (180px, opaque) draw the same grid on a `carbon`
tile; `public/social-preview.png` sets it beside the homepage headline and
three readings from `claims.json` over a still of the liquid. Change them with
the component.

The mark is a glyph, not a character: a mascot, when there is one, sits beside
it rather than replacing it.

## The liquid — `@/components/ui/LiquidBackground`

A fixed WebGL canvas behind every page, mounted once in `app/layout.tsx`: a
domain-warped noise field in the graphite steps, hairline currents along its
level sets, a faint `proton` sheen where it runs fast, and an `electric`
swirl where the pointer is. It flows on its own and drifts as the page
scrolls. It is the owner's addition over Console's no-texture rule, so it
carries the rule's reasons as constraints:

- **Contrast.** The shader clamps relative luminance to 0.014, under the
  0.0155 where `faint` drops below 4.5:1. Raise `CAP` and AA breaks.
- **Motion.** One still frame under `prefers-reduced-motion`; paused while
  the tab is hidden.
- **Cost.** Rendered at 0.55 canvas pixels per CSS pixel, at most 1100 on a
  side, every other frame.
- **Failure.** No WebGL or no JavaScript leaves the solid `carbon` ground. The
  canvas fades in only after its first frame.
- **Layering.** `body` has no background; the ground is on `html`, the canvas
  sits between them at `z-index: -1`. Panels and wells keep their solid steps
  on top.
- **Colour.** Read from the `:root` tokens at run time, never repeated.

### The graph — `@/components/ui/CondensingGraph`

Over the first screen, mounted after the liquid at the same `z-index`, ASCII
particles drift as a gas and condense into a code graph like the one `build`
makes: modules as clusters of nodes, calls as edges. The solid spreads from
one node along the edges, the way recall spreads, holds, evaporates, and
condenses into a new graph every 22 seconds. The gas is `ink`, the solid
`electric`: amber because, as in the mark, an association NeuralMind learned
is the person's colour.

It is part of the liquid, so the liquid's constraints apply, with two
specifics:

- **Contrast.** Each glyph colour is its token dimmed in linear light to at
  most the liquid's `CAP` (the gas to 0.8 of it). A glyph over the liquid is
  a mix of two colours under the cap, so it stays under it. The masks that
  fade it out below the first screen and halve it across the text column
  are for looks, not for AA.
- **Cost.** A 2D canvas at 15 frames a second, stopped when the tab is
  hidden or the layer is off screen.

## The mascot — The Pair

The pair programmer who sits in the corner of your editor: short, an
oversized `carbon-line` hoodie with the engram patch on the hood, silver-white
`ink` hair, `electric` amber eyes and drawstrings, headphones whose small LEDs
are the only `proton` blue on it. Its line is "Want me to remember that?".
It is built in VRoid Studio from [`mascot/SPEC.md`](mascot/SPEC.md), which
holds the palette, the build steps, the export settings and how to run the
build with a computer-use agent; the decals to import are in
`mascot/textures/`.

On the site it is `MascotSlot` (`@/components/ui/MascotSlot`), placed in the
hero so The Pair peeks over the record from behind it, at `lg:` and up:

- **It appears when the model does.** The slot checks at build time for
  `public/mascot/pair.vrm` and renders nothing without it; dropping the file
  in and rebuilding is the whole integration. An optional `pair.png` beside
  it is shown while the model loads.
- **`Mascot` draws it** with three.js and `@pixiv/three-vrm`, both fetched
  as their own chunk only once the box is on screen and the page has loaded.
  A box hidden by CSS never loads the model, so phones don't download it.
- **It behaves like a colleague:** blinks, breathes, its eyes and head follow
  the pointer (amber means a person, and the person is what it watches), and
  it smiles when a command is copied (`COPIED_EVENT` in `@/lib/events`, fired
  by `CommandLine`).
- **Under reduced motion it holds one still pose.** With no WebGL, or a model
  that fails to load, the box collapses and the page is as it was.
- **Budget:** the `.vrm` under 8 MB (Cloudflare Pages refuses files over
  25 MiB). The export settings in the spec get it there.

## Components

### Controls — `.btn-primary`, `.btn-secondary`, `.link`

CSS classes, applied to an `<a>` or `<Link>` (every button on the site
navigates). Primary is solid `electric` with dark ink, hover
`electric-bright`; secondary is a `carbon-card` panel in a `carbon-line`
outline. One primary per view. There is deliberately no `Button` component: a
second definition is how a page ends up with the old gradient.

`.link` is every link in running text: `ink`, underlined in `carbon-line`,
amber on hover. Link text carries no arrow.

### `Stat` and `StatGrid` — `@/components/ui/Stat`

```tsx
<StatGrid className="sm:grid-cols-3">
    <Stat label="Gold file found" value="40 of 40" note="…" evidence="reproducible" />
</StatGrid>
```

| Prop | Type | |
|---|---|---|
| `label` | string | The `.label` above the value (the `<dt>`). |
| `value` | node | The number, in `.metric text-stat`. Must be in `claims.json`. |
| `note` | node? | One or two sentences of context in `muted`. |
| `evidence` | `EvidenceLevel`? | Renders an `EvidenceBadge` under the note. |
| `figure` | boolean = true | `false` for a word rather than a number: set in the text face. |

`StatGrid` takes the column classes; any count closes cleanly.

### `EvidenceBadge` — `@/components/ui/EvidenceBadge`

`<EvidenceBadge level="ci-gated" />`, a chip in the label face. The levels
are the keys of `_evidence_levels` in [`claims.json`](claims.json), and the
badge's tooltip is that level's definition from the same file; a level added
there without a label here fails the TypeScript build.

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

### The record — `components/sections/Hero.tsx`

The homepage's signature, built from `publicQuery()` so nothing in it is
typed by hand: the question and its gold file, then Console's **reading**
(ripgrep's token count struck in `faint`, NeuralMind's set at display size in
`.reading`), then its **diff** (the gold file on a `success` or `danger` tint
with a plus or minus gutter, and the other files each retriever sent). It
shows the two counts and never a per-query ratio, which `claims.json` does not
list.

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

Head row in the label style over a `carbon-line` rule; cells in `muted` with
`carbon-border` rules; row heads in mono `caption`, because a backend's name
there is what the benchmark wrote. `.num` right-aligns on tabular figures and
sets the cell (not its head) in mono; `.is-ours` puts the measured subject's
row on `proton-dim` with its head in `proton`. Give the table a `min-w-*`
inside an `overflow-x-auto` box so a phone scrolls the table, not the page.

### Surfaces and text helpers

- `.card` — a surface you can click (border brightens on hover). `.panel` —
  the same surface, no hover. `.panel-accent` — the one call to action on a
  page, marked by the strong rule rather than a wash.
- `.label` — a label. `.metric` — mono, tabular, slashed zero: any measured
  number. `.reading` — one measured value set at display size.
  `SectionHeader` — a `display` title and a `muted` lede, used by every
  homepage section.

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
| `publicQuery(repo, id)` | One query's context files and tokens per backend (the homepage's record). |
| `retrievalEval` | The 150-question top-5 rate and miss count, counted from the raw ranks. |
| `disclosures` | The `disclosure` entries, for a `not-measured` `Callout`. |

Pass a figure's `evidence` straight to `Stat` or `EvidenceBadge`, so the badge
can't claim more than claims.json does. The module is server-only: its imports
are large, and a client component that imported it would ship them. Copy that
quotes a number literally still works and is still read by
`tests/test_site_claims.py`; prefer the module for anything in a stat or table.

### `CommandLine` — `@/components/ui/CommandLine`

A copyable shell command on the deepest step. `className` sizes the box
(`flex-1` to fill a row, so a stack of commands lines up).

## Not covered yet

- `site/public/graph-view.webp` is a real `neuralmind serve` capture of the
  psf/requests index in the graph view's own colours (re-capture it the same
  way, cropped above the sidebar's per-query ratios, which aren't in
  claims.json).
- The docs site has no liquid or mascot: it carries the tokens, type and mark,
  not the WebGL layers. The wiki pages' own emoji stay, because the same
  Markdown is mirrored into the GitHub Wiki.
- The Pair's model itself: until `public/mascot/pair.vrm` is committed, the
  hero renders without it. The slot was tested with pixiv's public VRM
  sample, which is not in the repo.
