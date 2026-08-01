# NeuralMind

Adaptive semantic code intelligence for AI coding agents. Reduces tokens
on code questions by 12-50× via progressive context disclosure, plus a
brain-like synapse layer that learns associations between code nodes
from how you actually use the codebase.

## Architecture

Two cooperating brains:

- **Claude (or any agent) = cortex.** Stateless reasoning over a
  working-memory window. NeuralMind never tries to reason here.
- **NeuralMind = hippocampus + associative cortex.** Persistent
  weighted graph of code nodes. Learns by Hebbian co-activation,
  decays unused edges, runs spreading activation for recall.

Communication channels: MCP tools, Claude Code lifecycle hooks
(`SessionStart`, `UserPromptSubmit`, `PreCompact`, `PostToolUse`),
and the file activity watcher.

## Layout

- `neuralmind/core.py` — orchestrator, public API
- `neuralmind/embedder.py` — graphify graph → ChromaDB embeddings
- `neuralmind/context_selector.py` — L0/L1/L2/L3 progressive disclosure
- `neuralmind/synapses.py` — SQLite-backed Hebbian synapse store
- `neuralmind/synapse_memory.py` — markdown export to Claude Code memory
- `neuralmind/watcher.py` — file activity → synapse co-activation
- `neuralmind/event_bus.py` — process-local pub/sub for live activity events
- `neuralmind/server.py` — local graph-view HTTP server + `/api/events` SSE
- `neuralmind/hooks.py` — Claude Code hook registration + runtime
- `neuralmind/mcp_server.py` — MCP tools for any agent
- `neuralmind/cli.py` — `neuralmind {build,query,watch,serve,install-hooks,…}`
- `editors/vscode/` — VS Code extension: status bar, command palette, graph panel, hover provider
- `site/` — public marketing site (neuralmind.uk), Next.js static export

## Marketing site — single repo, single source of truth

The public marketing site (`neuralmind.uk` /
`neuralmind-marketing.pages.dev`) is operated **from this repo only**, under
`site/`. It is a Next.js 14 static export (`output: 'export'` → `site/out`)
deployed to the Cloudflare Pages project `neuralmind-marketing` by
`.github/workflows/deploy-site.yml` (on push to `main` touching `site/**`, on
every published release, or manual dispatch). Because deploy is a wrangler
direct-upload to that project, the live URL is unchanged no matter which repo
builds it.

- **Never hardcode the version** on the `/security` page (or anywhere
  user-facing). It reads the latest release from the GitHub API at build
  time so it can't drift out of sync with the actual release — the exact bug
  that a hardcoded `v0.42.0` caused. Same rule for SBOM/tarball/release
  links: derive them from the release tag, don't pin a literal version.

## Internal docs — routed to the marketing repo

Pure internal strategy material (BRDs, TRDs, competitive analysis) lives in
**`dfrostar/neuralmind-marketing`**, NOT in this repo. Anything that supports
the public product or site — including release notes, which are canonical
public changelog content the "Shipping a feature" checklist below requires
in `docs/releases/` — stays here.

When a new document is authored, file it in the right repo:

| If it is… | Put it in… |
|-----------|------------|
| BRD / TRD / strategy doc | `dfrostar/neuralmind-marketing/internal/plans/` |
| Competitive analysis / market research | `dfrostar/neuralmind-marketing/internal/` |
| Release notes | `dfrostar/neuralmind/docs/releases/RELEASE_NOTES_v*.md` (here — see the shipping checklist) |
| CLI reference / wiki | `dfrostar/neuralmind/docs/wiki/` (here) |
| Use-case walkthrough | `dfrostar/neuralmind/docs/use-cases/` (here) |
| Marketing site page | `dfrostar/neuralmind/site/` (here) or `…-marketing/src/app/` |
| Consulting deck / private material | `dfrostar/neuralmind-marketing/consulting/` |

**Do NOT** move private business material (`consulting/`, `internal/`) into
this public repo. Both repos deploy to `neuralmind.uk`; only this one
(`neuralmind`) publishes to PyPI and GHCR.

## Local conventions

- Tests live in `tests/`. The synapse layer's tests are stdlib-only
  so they run without the full dep set.
- Generated state lives in `<project>/.neuralmind/` — never committed.
- Behavior toggles via env vars: `NEURALMIND_BYPASS=1` skips
  compression, `NEURALMIND_SYNAPSE_INJECT=0` skips prompt-time
  recall, `NEURALMIND_SYNAPSE_EXPORT=0` skips memory export.

## Commercial terms — single source of truth

**`commercial-terms.json` (repo root) is canon** for entity, pricing, and
contact: Cheval-Volant LLC (d/b/a NeuralMind, Texas), $0 free / $29 per
user/mo Team (5–50 seats, annual) / Enterprise custom,
hello@neuralmind.uk. Never write a different price, entity name, or
contact on any surface — site, legal docs, README, wiki, marketing. To
change the terms, change the JSON first, then propagate. CI enforces
this (`scripts/check_commercial_terms.py`, stdlib-only): any term on the
JSON's `superseded_terms` list — the old draft entity, prices, contact,
and governing law — fails the build anywhere outside `docs/releases/`
and `CHANGELOG.md` (historical record, exempt). The
JSON's `do_not_market` list mirrors the Tier2 operator guide — SSO/SAML
and cross-machine sync are roadmap-only; no trial CTAs (no issuance
mechanism exists).

## Multi-project scoping (operator rule)

When working on the NeuralMind codebase alongside other projects (cmmc20, lingogame, autopilot):

- **NeuralMind isolates automatically** — `.neuralmind/` is per-project. `build .` in repo A never touches repo B.
- **memU does NOT isolate** — single flat store. Scope every retrieve query: `memu-hermes retrieve "[neuralmind] seed_from_documentation"` not `memu-hermes retrieve "synapse"`.
- **Hermes memory does NOT isolate** — tag every entry with `[project]` prefix.
- **session_search does NOT isolate** — include project name in every query.
- **Autopilot is NEVER indexed** (contains secrets). NeuralMind + autopilot don't mix.

End users running NeuralMind on a single project need no scoping — `.neuralmind/` isolation is built-in. For operators, see `docs/wiki/Multi-Project-Scoping.md`.

## Shipping a feature — docs + SEO checklist

Every user-facing change ships with documentation propagated across
all five surfaces and SEO refreshed to match. Established pattern
from v0.7→v0.8→v0.9→v0.10 (see commit `fdfa35e` for the canonical
shape). When a release introduces a new command, hook, env var, or
agent-visible behavior:

**Documentation (every surface):**
- [ ] `docs/releases/RELEASE_NOTES_v<X.Y.Z>.md` — canonical notes
  with a "what the agent actually sees post-install" angle and a
  per-agent expectations table (Claude Code / Cursor / Cline /
  generic MCP) when the change affects integrations.
- [ ] `README.md` — bump the top banner, demote the previous
  version into the history trail, add the new release-notes row
  to the bottom table, and update any in-context sections (e.g.
  "PostToolUse hooks — what happens automatically") with the new
  behavior. Show what the agent actually sees, not just what the
  code does.
- [ ] `docs/index.html` — top banner block + earlier-releases trail.
- [ ] `docs/about.html` — new "What's New in v<X.Y.Z>" section above
  the prior one; never delete old sections, demote them.
- [ ] `docs/wiki/CLI-Reference.md` — add new commands, document any
  new env vars in the Environment Variables table.
- [ ] `docs/use-cases/*.md` — update existing use-case walkthroughs
  the change touches, AND consider whether the change unlocks a
  potential new use case worth its own walkthrough. Existing and
  potential both count.
- [ ] **Don't edit `CHANGELOG.md`** — release-please owns it and
  writes from the `feat:`/`fix:` commit body automatically.

**SEO (every release that adds a new noun to the product surface):**
- [ ] `pyproject.toml` keywords — add 2-3 terms specific to the new
  surface so PyPI search picks them up (e.g. v0.10.0 should add
  `tool-output-recovery`, `bash-output-cache`, `agent-ergonomics`).
- [ ] `docs/index.html` `<meta name="description">` and `<meta
  name="keywords">` — broaden when the positioning shifts.
- [ ] `docs/about.html` page-level `<meta>` — refresh if the new
  feature is a positioning anchor.
- [ ] `docs/sitemap.xml` — add discoverable new URLs (release notes,
  new use-case walkthroughs).
- [ ] Consider adding schema.org JSON-LD (`SoftwareApplication` /
  `Article`) for richer Google results. Existing gap as of v0.10.0.

**Use cases — frame for discovery:**
- Always describe both the *existing* use case the feature improves
  and the *potential* new use case it unlocks. A new CLI command
  isn't just a feature — it's a new workflow someone is searching for.
- Cross-link: a new feature mentioned in release notes should link
  to (or trigger creation of) a use-case walkthrough.

**Release flow:**
- `feat:` commits trigger release-please to open a release PR that
  bumps `pyproject.toml`, `.release-please-manifest.json`, and
  writes `CHANGELOG.md`. Never bump these manually.
- The release PR merging tags `v<X.Y.Z>` which fires PyPI + GHCR
  publish via `release.yml`.
- Documentation + SEO ships in the *same PR as the feature*, not
  a follow-up, so the moment the version lands the surfaces match.

## Learned associations

@.neuralmind/SYNAPSE_MEMORY.md
