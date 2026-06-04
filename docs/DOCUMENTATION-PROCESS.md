# Documentation Process

How NeuralMind keeps its docs current, consistent, and **interesting to
potential users** — as a repeatable standard, not tribal habit. This is the
operational companion to the "Shipping a feature — docs + SEO checklist" in
`CLAUDE.md`: that file says *what* surfaces exist; this file says *when*,
*who*, and *how we keep them honest over time*.

> **Why this exists.** Docs drift silently. A real example caught in June 2026:
> `docs/index.html`'s "Status & Future" block still advertised "v0.5.4
> (Current) / v0.5.5 (Next)" while the project was on v0.12 — a visitor's first
> impression was a project frozen seven releases ago. The cost of stale docs is
> paid entirely by the people we most want to reach: first-time visitors. This
> process makes that failure mode hard to repeat.

---

## The one rule

**Every user-facing change ships its documentation in the *same PR*, and every
doc answers one question: _"What does the user (or the agent) now see?"_**

Not "what does the code do" — what *changes in the experience*. That framing is
what makes docs interesting rather than a changelog. A new command isn't a
feature; it's a workflow someone is already searching for.

A change is **user-facing** if it adds or changes any of: a CLI command, an MCP
tool, a hook, an env var, agent-visible behavior, or a visible bug fix. Pure
internal refactors are exempt (note that in the PR).

---

## The five surfaces (propagate to all that apply)

| # | Surface | What to update | Notes |
|---|---|---|---|
| 1 | **`RELEASE_NOTES_v<X.Y.Z>.md`** | Canonical notes, written from the *"what the agent/user sees post-install"* angle. Include a per-agent expectations table (Claude Code / Cursor / Cline / generic MCP) when integrations are affected. | One per release. |
| 2 | **`README.md`** | Bump the top banner; demote the previous version into the history trail; add a row to the release-notes table; update any in-context sections the change touches. | Show what the agent sees, not just what the code does. |
| 3 | **`docs/index.html`** | Top banner block + earlier-releases trail + the **Status & Future** block (keep "Current/Next" honest). | Landing page — highest first-impression value. |
| 4 | **`docs/about.html`** | New "What's New in v<X.Y.Z>" section *above* the prior one. Never delete old sections — demote them. | Forward-looking direction goes in the "Where NeuralMind is going next" section. |
| 5 | **`docs/wiki/*.md` + `docs/use-cases/*.md`** | New commands/env vars in `CLI-Reference.md`; update touched use-cases AND add a new walkthrough if the change unlocks a new workflow. | **The wiki auto-syncs** from `docs/wiki/**` to the live GitHub Wiki via `sync-wiki.yml` on merge to `main` — edit the source, never the live wiki. |

**Do NOT edit `CHANGELOG.md`** — release-please owns it and writes it from the
`feat:`/`fix:` commit body. Do NOT hand-bump `pyproject.toml` /
`.release-please-manifest.json` versions.

---

## SEO (every release that adds a new noun to the product surface)

- **`pyproject.toml` keywords** — add 2–3 terms specific to the new surface so
  PyPI search picks them up.
- **`docs/index.html`** `<meta name="description">` / `<meta name="keywords">`
  — broaden when the positioning shifts.
- **`docs/about.html`** page-level `<meta>` — refresh if the feature is a
  positioning anchor.
- **`docs/sitemap.xml`** — add discoverable new URLs (release notes, new
  use-case walkthroughs). Only add URLs that resolve to a real page.
- **schema.org JSON-LD** (`SoftwareApplication` / `Article`) — consider for
  richer Google results (known gap).

---

## Discoverability — frame for the searcher

A feature mentioned in release notes should link to (or trigger creation of) a
**use-case walkthrough**, because that's what people actually search for.

- Describe both the *existing* use case the feature improves **and** the
  *potential* new use case it unlocks.
- Cross-link release notes ↔ use-case ↔ wiki.
- Title walkthroughs as workflows ("Prove retrieval quality on your repo"), not
  feature names ("The eval command").

---

## Cadence — three loops

1. **Per-PR (the default).** Docs for a user-facing change ship in the same PR.
   Enforced by the documentation section of the PR template. The reviewer blocks
   the PR if a user-facing change has no doc updates.
2. **Per-release.** Before merging the release-please PR, run the
   **release docs audit** below. The PM/maintainer owns this gate.
3. **Quarterly freshness sweep.** Catch slow drift the per-PR loop misses
   (stale "Current/Next", dead links, outdated screenshots, comparison pages
   that no longer match competitors). The PM agent owns scheduling this.

---

## Release docs audit (run before merging a release PR)

- [ ] `RELEASE_NOTES_v<X.Y.Z>.md` exists and is written from the user/agent-sees angle.
- [ ] README banner shows the new version; previous version demoted; release table row added.
- [ ] `docs/index.html` banner **and Status & Future block** reflect the new version (no stale "Current/Next").
- [ ] `docs/about.html` has a new "What's New" section above the prior one.
- [ ] `docs/wiki/CLI-Reference.md` documents any new command/env var; touched use-cases updated; new walkthrough added if a workflow was unlocked.
- [ ] SEO: keywords / meta / sitemap updated if a new noun entered the product surface.
- [ ] No manual edits to `CHANGELOG.md`, `pyproject.toml` version, or the release manifest.
- [ ] All doc links resolve (no 404s to renamed files).

> **Recommended automation (open).** A lightweight CI guard that fails when the
> latest `RELEASE_NOTES_v*.md` version is *not* referenced in `README.md`,
> `docs/index.html`, and `docs/about.html` would catch the stale-surface failure
> mode mechanically. Tracked as a future docs-tooling task.

---

## Quick reference

- **Where the canonical checklist lives:** `CLAUDE.md` → "Shipping a feature — docs + SEO checklist".
- **Wiki:** edit `docs/wiki/*.md`; it syncs to the live wiki automatically on merge to `main`.
- **Versioning:** release-please, driven by `feat:`/`fix:` commits — see `CONTRIBUTING.md` → Release Process and `docs/VERSION-STRATEGY.md`.
- **Forward-looking roadmap:** `ROADMAP.md` + `docs/NEXT-RELEASE-PLAN.md`.
