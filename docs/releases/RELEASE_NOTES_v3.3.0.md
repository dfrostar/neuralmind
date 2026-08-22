# NeuralMind v3.3.0 — the surfaces people judge you on

Two of NeuralMind's outward-facing surfaces were quietly producing wrong
output. The marketing site rendered every heading in the browser's default
serif because the fonts it declared were never actually loaded. The
compliance scanner reported 147 SOC 2 controls on this repository, of which
129 were version strings and SVG path data. v3.3.0 is the release that
fixes both — the page a prospect evaluates you on, and the evidence an
auditor would be handed.

Neither was a regression. Both had been wrong since the code was written.

## What's in this release

| Change | Was | Now |
|--------|-----|-----|
| **Marketing site design system** | Fonts declared, never imported — 113 headings in Times New Roman | Self-hosted Inter / Inter Tight / JetBrains Mono, no runtime font fetch |
| **SOC 2 annotation matching** | 147 "controls" found on this repo, 129 of them noise | Marker required and word-anchored; noise eliminated |
| **Document-only projects** | `build` refused a repo with no code | Books and doc sets build a graph |
| **`content_category`** | Dropped on re-embed; the N-13 type filter missed nodes | Preserved through re-embed and carried in node metadata |

## 1. The marketing site had no webfonts

`tailwind.config.ts` mapped `font-display` and `font-mono` to Inter Tight
and JetBrains Mono. Nothing ever imported them. Next.js only emits
`@font-face` rules for fonts loaded through `next/font`, so the browser
fell through the entire stack to its default serif — **113 `font-display`
headings across 25 files**, every one of them rendering in Times New Roman
on a page that had been designed around a geometric sans.

The fix is `site/src/lib/fonts.ts`, which loads all three families through
`next/font/google` and exports the CSS variables the Tailwind config was
already pointing at. Because `next/font` self-hosts, the built site makes
**no runtime request to `fonts.gstatic.com`** — the fonts ship in the
static export.

Landing alongside it:

- **A real icon set.** Twenty SVG icons on a 24×24 grid, stroke 1.5,
  `currentColor`, replacing the emoji the pages had been using as
  iconography. Emoji render differently on every platform and carry a
  vendor's visual language, not yours.
- **Contrast fixed to WCAG AA.** Nine pages carried body text below the
  4.5:1 floor. The token set was repointed — a neutral ramp for surfaces,
  one accent reserved for interactive elements and one for measured
  evidence — with an AA-safe muted tone added rather than dimming the
  existing one further.
- **Mobile overflow.** A CSS grid child defaults to `min-width: auto`,
  which refuses to shrink below its content and pushed the page wider than
  the viewport. Fixed where it occurred.
- **An undefined Tailwind class** used in three places, internal footer
  links opening in new tabs, and a timer in the animated command line that
  stacked rather than reset.

## 2. SOC 2 annotations: 96 matched, 7 were real

The SOC 2 pattern treated its framework marker as *optional*. What remained
was "one to three letters, digits, a dot, digits" — a shape that matches
far more than a Trust Services Criterion.

Run both matchers over the same corpus (the v3.2.1 tree, across the file
types the scanner reads):

```
                                        before   after
  total SOC 2 matches                       96       7

  genuine — docs/compliance/*.md             7       7
  version strings — v0.13, v2.0             55       0
  eval milestone ids — E1.4                 17       0
  SVG path data — M13.5, A1.5                5       0
  python3.10, TLSv1.2, llama3.1              5       0
  control ids in prose tables, unmarked      7       0
```

`M`, `L`, `C`, `A` and `S` are SVG path verbs, so any inline icon in the
codebase read as a control reference. Eighty-two of the ninety-six were
noise of that kind, and all of it flowed into `neuralmind export
--controls`, which users submit as compliance evidence.

The last row is the one worth reading twice: seven matches were genuine
control ids (`CC6.1`, `CC7.1`, `PI1.4`) sitting in prose tables in
`docs/COMPLIANCE-SUMMARY.md` and `docs/SECURITY-GUIDE.md` with no marker on
their line. Those no longer match, deliberately — a bare `CC6.1` in running
text is not distinguishable from a version string. If you keep annotations
in that shape, add a marker to the line.

The marker is now required, and anchored on word boundaries — without the
boundary, `noncompliance: CC6.1` matches on the tail of "noncompliance", a
word that appears constantly in compliance prose. Intervening words are
still allowed, so the documented form `**SOC 2 Control:** CC6.1` keeps
working. NIST had required its prefix for exactly this reason since it was
written; SOC 2 and ISO 27001 now match that standard.

## 3. Document-only projects build

`neuralmind build .` on a repository containing only prose refused to
produce a graph. A book, a policy set, or a docs-only repo is a legitimate
target for the document ingestion path added in v1.11.0, and now builds.

## 4. `content_category` survives a re-embed

The category assigned at ingestion was dropped when a node was re-embedded,
which meant the N-13 type filter silently stopped matching nodes it had
matched on the previous build. The category is now preserved through
re-embed and included in node metadata, so `--type` filtering is stable
across rebuilds.

## What the agent actually sees post-install

| Agent | What changes | How to use it |
|-------|--------------|---------------|
| **Claude Code** | `neuralmind compliance .` and the `neuralmind_compliance_report` MCP tool stop reporting version strings as controls. `--type` filters keep working after a rebuild. | Nothing to configure — re-run `neuralmind build .` to pick up preserved categories |
| **Cursor / Cline** | Same, via the MCP tool | Nothing agent-specific |
| **Generic MCP / CLI** | `neuralmind compliance [path]`, `neuralmind export --controls` | See [CLI-Reference](../wiki/CLI-Reference.md#compliance-v314) for the annotation syntax each framework requires |

Nothing in this release changes a command signature, adds an env var, or
alters the graph format. A rebuild is worthwhile for the
`content_category` fix but is not required.

## Honest scope

- **The SOC 2 fix is a tightening, and tightening loses things.** An
  annotation written without a `SOC 2` or `Compliance:` marker on the same
  line no longer matches. That is the intended behavior — the previous
  match was indistinguishable from a version string — but if you had
  unmarked annotations, they are now invisible and need the marker added.
- **`Compliance:` is a SOC 2 / ISO 27001 marker, not a universal one.**
  NIST, CMMC, SOX and HIPAA each require their own prefix. `# Compliance:
  AC-1: …` matches nothing.
- **The site work is visual and structural, not a claims change.** No
  performance number on the site moved; `site/claims.json` is unchanged.
- **This release does not fix the compliance *scan scope*.** On this
  repository `neuralmind compliance .` still reported zero annotations
  after v3.3.0, because the CLI and MCP entry points could not read
  markdown files at all. That is fixed in v3.3.1.

## Upgrade

```
pip install --upgrade neuralmind
neuralmind build .    # optional — picks up the content_category fix
```
