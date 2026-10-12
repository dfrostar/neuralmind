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
the Hermes-Agent plugin's `pre_llm_call` / `post_tool_call` hooks,
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
- `neuralmind/hermes_plugin/` — Hermes-Agent plugin (runs the same `_hook` actions), installed by `neuralmind install-hermes-plugin` via `neuralmind/hermes_install.py`
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

### `site/claims.json` is canon for site numbers

Same contract as `commercial-terms.json`: **change the JSON first, then the
copy**. Every performance ratio quoted on the homepage sections, `page.tsx`,
or `layout.tsx` metadata must have an entry there naming where it was measured
and the command that reproduces it. CI enforces it
(`tests/test_site_claims.py`, stdlib-only), along with two rules the docs
guard already applied everywhere *except* the site — no absolute privacy
claims, and no naming a private client whose field report the docs anonymize.

Rules that follow from it:

- **No number without a measurement.** If the copy wants to say something the
  repo can't measure, write the benchmark first
  (`tests/benchmark/latency.py` exists because the site was quoting a query
  latency nothing produced). Mechanism claims — "a local index lookup, not
  another model call" — are fine unquantified; invented figures are not.
- **Say which kind of evidence it is.** CI-gated, reproducible-on-demand, a
  one-repo field report, and a community submission are not the same strength
  of claim, and the site says which is which.
- **Quote the mean and the range, publish the misses.** The public benchmark
  finds the gold file on 40 of 40 queries at v4.12.0, and the site still says
  "40 of 40", not "100% recall": 40 queries is a small sample, and the
  150-question retrieval eval misses 10, which the site quotes beside it. The
  docs already report where NeuralMind loses; the site must not round that
  away.
- **A headline needs its raw data committed.** The public-benchmark figures
  are recomputed in CI from `bench/public/results.json`; re-running the
  benchmark means committing that file (`--out bench/public`) and updating
  `site/claims.json` in the same change.
- A page that quotes a forbidden phrase in order to *disown* it (the
  effectiveness page's list of overclaims) marks the line
  `claims-guard:allow`.

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

## `docs/` is a public website

GitHub Pages builds https://docs.neuralmind.uk/ from `main:/docs` (legacy
Jekyll build, domain in `docs/CNAME`) on every push to `main`, without waiting
for CI. A file committed under `docs/` goes public within minutes, so only
docs-site file types belong there: Markdown, HTML, site assets, images, and the
site's own data files. CI enforces the type allowlist
(`scripts/check_docs_site_allowlist.py`, stdlib-only). Scripts, datasets, and
other projects' files go in their own repos. To add a new file type, edit the
allowlist in the same change.

## Local conventions

- Tests live in `tests/`. The synapse layer's tests are stdlib-only
  so they run without the full dep set.
- Generated state lives in `<project>/.neuralmind/` — never committed.
- Behavior toggles via env vars: `NEURALMIND_BYPASS=1` switches
  off every hook action, `NEURALMIND_SYNAPSE_INJECT=0` skips
  prompt-time recall, `NEURALMIND_SYNAPSE_EXPORT=0` skips memory
  export. The Read/Bash/Grep PostToolUse hooks inject nothing:
  Claude Code adds `additionalContext` beside a tool result rather
  than replacing it (see `docs/benchmarks/compression.md`). The one
  exception is opt-in: `NEURALMIND_BASH_REPLACE=1` replaces allowlisted
  noisy logs via `updatedToolOutput`, and any change to it must keep
  the benchmark's retention gates passing
  (`tests/test_compression_benchmark.py`).

## Behaviour contracts — keep code, docs and tests in step

`neuralmind doctor`'s documented `exit 1` was lost in v0.55.0: a new helper
left it unreachable, a lint pass deleted it, and three months later a docs
change described the regression as the design. These rules prevent a repeat:

- **A documented exit code has a test.** Exit codes are an interface scripts
  gate on. When you document one, add a row to `tests/test_cli_exit_codes.py`
  (or a test next to the feature, named in that file's docstring). The same
  file holds the CLI reference's global "Exit Codes" table to codes the CLI
  actually emits.
- **Lint and style commits never delete code.** If code looks dead, find out
  why it is dead and remove it in its own commit that says so.
  `scripts/check_unreachable.py` (CI Lint job) fails on statements after a
  `return`/`raise`/`sys.exit`, so stranded code is caught where it's stranded.
- **When code and docs disagree, read the history before "aligning" either.**
  `git log -S'<the line>'` shows which side changed last and why. Aligning the
  docs to a regression makes the bug permanent.
- **Every script in `scripts/` runs somewhere or goes.** CI shellchecks every
  `scripts/*.sh`. A script no workflow runs and nobody can run as written is
  deleted rather than left to mislead.

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
- **The Hermes plugin with a pinned project does NOT isolate** — a pin given at install (`neuralmind install-hermes-plugin <path>`) applies to every Hermes session on that Hermes home, in any directory, and `NEURALMIND_PROJECT` to every Hermes process started with it in its environment: each gets the pinned project's context, has its prompts recorded in that project's `.neuralmind/recaps/`, and puts its edited files' paths into that project's synapse store, from where `neuralmind memory publish` can carry them into the committed team-memory bundle — autopilot sessions included. For several projects, install without a path (a re-run without a path keeps an old pin; `--unpin` clears it), so the plugin follows the directory Hermes works in and does nothing in an unbuilt repo like autopilot. Pin only for a single-project setup or the gateway (its terminal working directory is `terminal.cwd`, else `MESSAGING_CWD`, else your home directory). Following reads `TERMINAL_CWD` from the Hermes process's environment, which matches the terminal CLI and a standalone gateway only: Hermes Desktop, ACP editor sessions and per-session workspaces keep each session's directory elsewhere, so there pin a project or set `NEURALMIND_PROJECT`, and all of the above applies. In Hermes Desktop and ACP editor sessions the plugin can't see each session's directory: pin or set `NEURALMIND_PROJECT` there, since unpinned every session is served and recorded as whatever the Hermes process's own `TERMINAL_CWD` (or working directory) is, if that's built.

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
  the "After install, your agent:" list) with the new
  behavior. Show what the agent actually sees, not just what the
  code does.
- [ ] `docs/index.html` is a redirect to `wiki/Home` now, with no banner:
  only refresh its `<meta>` description and keywords (see SEO below).
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
