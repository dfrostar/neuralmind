# PRD: Team memory — agents inherit the team's learned associations

**Status:** Draft · **Owner:** dfrostar · **Created:** 2026-06-18
**Tracking branch:** `claude/team-memory` · **Target:** v0.30.0

## 1. Background & strategic motivation

The competitive review (`DeusData/codebase-memory-mcp`, 6.6k★, and 100+ similar
MCP code-graph servers) established that **breadth and packaging are commodity**
— now closed in v0.27–v0.29 (Rust, Java, ChromaDB-free). The real, un-clonable
differentiator is NeuralMind's **learned synapse layer**: it remembers *what
goes with what* from how you actually work. A static-AST competitor has no
learned signal to share.

This release turns that differentiator into a **team feature**: a team's learned
memory becomes a committed, versioned artifact that **every engineer's agent
inherits automatically on `git clone` + first session** — so a new hire's agent
starts already knowing "the auth handlers go with the JWT utils and the user
store," instead of relearning it from scratch.

Positioning shift: from "another code-graph MCP" → "the one that gives your
**team's** agents shared, earned intuition." Nobody with a static index can copy
this.

## 2. What already exists (the on-ramp)

v0.24 (memory namespaces) + the PRD-8 on-ramp already shipped the primitives:

- **Portable bundles** — `export_synapse_bundle(store, namespace)` /
  `import_synapse_bundle(store, data, namespace=...)` in `neuralmind/ir.py`
  (versioned `SYNAPSE_BUNDLE_VERSION`); import is **idempotent and merges
  weights by MAX** — exactly right for unioning multiple engineers' memory.
- **The `shared` namespace** — merged-read weighting already blends the active
  namespace + `personal` (0.8×) + `shared` (0.5×) transparently
  (`neuralmind/synapses.py`).
- **CLI** — `neuralmind memory {inspect,reset,export,import}`.
- **The proof metric** — `neuralmind eval --onboarding` measures the top-k
  retrieval lift a cold agent gets from inherited memory (`evals/onboarding/`).
- **A `SessionStart` hook** that already warms the store + runs a decay tick —
  the natural seam to auto-import a committed bundle.

So this release is a **thin workflow layer**, not new core machinery. Low risk.

## 3. The gap (what 0.30.0 adds)

The primitives require manual `export`/`import` and an out-of-band file. The
missing piece is the **zero-effort, committed, auto-inherited workflow**:

1. **A committed convention.** Today `.neuralmind/` is fully git-ignored. Define
   one **committed** path — `.neuralmind/team-memory.json` (un-ignored via a
   `.gitignore` negation) — as the canonical team bundle that lives *in the
   repo* and travels with `git clone`.
2. **`neuralmind memory publish`** — a one-command wrapper that exports the
   project's learned memory (the `personal` + `shared` namespaces, union) to the
   committed path, stamped with provenance (tool version, timestamp, a content
   hash), ready to `git commit`.
3. **Auto-import on session start / build** — if a committed team bundle exists
   and its content hash hasn't been imported yet, import it once into `shared`
   (idempotent, tracked in the synapse store's `meta` table so it never
   re-imports the same bundle). This is the "inherit on day one" magic: clone →
   first agent session → the team's associations are already live.
4. **Surface the value** — `neuralmind memory publish` (and a `--lift` flag, or
   `neuralmind memory lift`) reports the onboarding-lift number the bundle buys
   a cold agent, so the benefit is legible, not abstract.

## 4. Goals / non-goals

**Goals**
- `git clone` + `neuralmind build` (or first Claude Code session) → the agent's
  recall is seeded with the team's committed memory, **no manual step**.
- `neuralmind memory publish` produces a committed, provenance-stamped bundle;
  re-publishing + re-importing is idempotent (MAX-merge, content-hash-gated).
- Opt-out and safety: env flag to disable auto-import; the committed bundle only
  ever writes the `shared` namespace (never pollutes `personal`/branch memory).
- The onboarding-lift number is reportable on demand.

**Non-goals**
- A hosted registry / network sync (bundles travel via git — 100% local, no
  server; consistent with the project's zero-exfiltration promise).
- Changing merged-read weighting or core synapse math.
- Cross-repo memory (a bundle is per-project).

## 5. Design

**Committed path + gitignore.** `.neuralmind/team-memory.json`, un-ignored via a
`!.neuralmind/team-memory.json` negation that `neuralmind install-hooks` / the
project bootstrap writes into the project `.gitignore` (idempotent). Everything
else under `.neuralmind/` stays ignored (per-machine state).

**`memory publish`** (`cli.py`): `export_synapse_bundle` over the union of
`personal` + `shared`, wrapped with a header `{tool_version, created_at,
content_hash, source_namespaces, counts}`; written to the committed path.
Prints the lift and a `git add … && git commit` hint.

**Auto-import seam.** A `maybe_import_team_memory(project_path, store)` helper
(new, in `memory.py` or `synapse_memory.py`): if the committed bundle exists and
`store.meta["team_bundle_hash"] != bundle.content_hash`, call
`import_synapse_bundle(store, bundle, namespace="shared")` and record the hash.
Called from: the `SessionStart` hook (Claude Code) and `neuralmind build`
(everyone else, incl. Cursor/Cline/generic MCP via the build path). Idempotent,
fail-open, gated by `NEURALMIND_TEAM_MEMORY=0`.

**Provenance/trust.** The bundle header carries who/when/version + a content
hash. Import remains MAX-merge so a bad bundle can only *raise* weights of pairs
it asserts — and per-namespace decay erodes stale shared edges over time.

## 6. Acceptance criteria

- [ ] `neuralmind memory publish` writes `.neuralmind/team-memory.json` (committed
      path), provenance-stamped, and reports the onboarding lift.
- [ ] A fresh clone with a committed bundle + `neuralmind build` (or a
      `SessionStart`) imports it once into `shared`; a second run is a no-op
      (content-hash gated, verified by `meta`).
- [ ] Auto-import only ever writes `shared`; `personal`/branch namespaces
      untouched (test).
- [ ] `NEURALMIND_TEAM_MEMORY=0` disables auto-import; the hook stays fail-open
      (exit 0) if the bundle is missing/corrupt.
- [ ] `.gitignore` gets the negation idempotently; everything else in
      `.neuralmind/` stays ignored.
- [ ] Onboarding-lift eval still green; a test shows lift ≥ 0 from a published
      bundle on the reference fixture.
- [ ] Docs + SEO propagated (release notes, README, both HTML, CLI-Reference
      `memory publish`, a new "team memory" use-case walkthrough, keywords).

## 7. Risks & mitigations

| Risk | Mitigation |
|------|-----------|
| A committed bundle balloons the repo | Cap exported synapses (top-N by weight); bundle is compact JSON; doc the size. |
| Stale/bad shared memory degrades recall | MAX-merge can only raise asserted pairs; per-namespace decay erodes unused shared edges; `memory reset shared` clears it; weighted at 0.5× in reads. |
| Auto-import surprises users | Off-switch (`NEURALMIND_TEAM_MEMORY=0`), one-time per hash, only writes `shared`, announced once like the v0.22 migration notice. |
| Privacy (memory leaks intent) | Bundle is synapse pairs (node-id associations) + counts — no source, no prose; 100% local via git, no network. Documented. |

## 8. Rollout

Single `feat:` PR → release-please cuts **v0.30.0**. Headline: "your team's
agents inherit each other's intuition — committed to the repo, zero setup."
Lead the release notes with the **onboarding-lift number** on a real example.

## 9. Success metric

A new engineer who clones a repo with committed team memory gets a measurable
**top-k retrieval lift on their first queries** (the onboarding eval's number),
with **zero manual steps** — a capability no static-index competitor can offer.
