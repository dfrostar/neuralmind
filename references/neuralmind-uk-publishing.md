# NeuralMind.uk Publishing Workflow

**Source:** User direction, 2026-07-19
**Purpose:** Hermes needs to know how to update neuralmind.uk when features ship.

---

## How neuralmind.uk works

Both `neuralmind.uk` and `docs.neuralmind.uk` serve the **same** GitHub Pages site, built from `docs/` on the `main` branch of `dfrostar/neuralmind`.

- **No separate site repo.** The site IS this repo's `docs/` directory.
- **No separate deploy step.** Push to `main` → GitHub Pages rebuilds automatically.
- **No Render/Vercel.** Pure GitHub Pages.

---

## How to update neuralmind.uk (when a feature ships)

1. Edit the relevant file(s) under `docs/`:
   - `docs/index.html` — homepage, top banner, release trail
   - `docs/about.html` — "What's New" section above prior one
   - `docs/wiki/CLI-Reference.md` — new commands, env vars
   - `docs/use-cases/*.md` — updated or new walkthroughs
   - `docs/sitemap.xml` — new discoverable URLs

2. **Commit and push to `main`** (or merge a PR).

3. GitHub Pages auto-rebuild — live in ~1-2 min.

---

## Same PR as the feature — never a follow-up

The established pattern (v0.7→v0.10, see commit `fdfa35e`):

> Documentation + SEO ships in the **same PR as the feature**, not a follow-up. The moment the version lands, the surfaces match.

If you ship a feature, you **must** update the docs in that commit/PR. No exceptions.

---

## Full shipping checklist (from CLAUDE.md)

When a release introduces a new command, hook, env var, or agent-visible behavior:

**Documentation:**
- [ ] `RELEASE_NOTES_v<X.Y.Z>.md` at repo root
- [ ] `README.md` — banner bump, release-notes row, in-context sections
- [ ] `docs/index.html` — banner + trail
- [ ] `docs/about.html` — new "What's New" section above prior
- [ ] `docs/wiki/CLI-Reference.md` — new commands, env vars table
- [ ] `docs/use-cases/*.md` — updated + new walkthroughs
- [ ] **NEVER edit `CHANGELOG.md`** — release-please owns it

**SEO (when new noun added):**
- [ ] `pyproject.toml` keywords — add 2-3 terms
- [ ] `docs/index.html` meta description + keywords
- [ ] `docs/about.html` page-level meta
- [ ] `docs/sitemap.xml` — new URLs
- [ ] Consider schema.org JSON-LD

---

## Pricing note

Per-seat pricing was deliberately withdrawn from customer-facing docs in favor of per-org assurance pricing. `docs/index.html` does NOT contain per-seat/team pricing. Maintain this.

---

## Reference

- CLAUDE.md — root of repo, checked into git
- `neuralmind-release` skill — pipeline + tag + push scripts
- `.github/workflows/release.yml` — CI → PyPI + GHCR on tag
