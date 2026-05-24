# NeuralMind

Adaptive semantic code intelligence for AI coding agents. Reduces tokens
on code questions by 40-70x via progressive context disclosure, plus a
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

## Local conventions

- Tests live in `tests/`. The synapse layer's tests are stdlib-only
  so they run without the full dep set.
- Generated state lives in `<project>/.neuralmind/` — never committed.
- Behavior toggles via env vars: `NEURALMIND_BYPASS=1` skips
  compression, `NEURALMIND_SYNAPSE_INJECT=0` skips prompt-time
  recall, `NEURALMIND_SYNAPSE_EXPORT=0` skips memory export.

## Shipping a feature — docs + SEO checklist

Every user-facing change ships with documentation propagated across
all five surfaces and SEO refreshed to match. Established pattern
from v0.7→v0.8→v0.9→v0.10 (see commit `fdfa35e` for the canonical
shape). When a release introduces a new command, hook, env var, or
agent-visible behavior:

**Documentation (every surface):**
- [ ] `RELEASE_NOTES_v<X.Y.Z>.md` at repo root — canonical notes
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
