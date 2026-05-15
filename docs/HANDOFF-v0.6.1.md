# NeuralMind v0.6.1+ — Release Handoff

> **For the next Claude Code (or any agent) session.** Hand this file URL to
> a fresh session and it has everything it needs to drive Phase 0 cleanup,
> ship v0.6.1, plan v0.7, and frame v0.7.x — including the marketing arc
> that ties them together.
>
> Stable URL (after this branch lands):
> `https://github.com/dfrostar/neuralmind/blob/main/docs/HANDOFF-v0.6.1.md`
>
> Predecessor: [`docs/HANDOFF-v0.6.0.md`](HANDOFF-v0.6.0.md). The v0.6.0
> handoff is the **template** for how this kind of multi-step release work
> gets shipped successfully — read it once, then come back here.

## TL;DR

v0.6.0 shipped on PyPI on 2026-05-15. The next batch of work is a
**4-phase plan** that turns "we shipped a feature release" into "we have
five install paths and three audience-specific marketing moments queued
up." The North Star: **"NeuralMind installs wherever you work."**

| Phase | Target | Theme | Tracking issue |
|-------|--------|-------|----------------|
| **0** | immediate | Hygiene cleanup (branches, About-box, topics) | [#117](https://github.com/dfrostar/neuralmind/issues/117) |
| **1** | v0.6.1 | Install Anywhere — pipx, uv, Docker, verify, keywords | [#118](https://github.com/dfrostar/neuralmind/issues/118) |
| **2** | v0.7 | Always-On — systemd/launchd, Aider, healthcheck, Windows | [#119](https://github.com/dfrostar/neuralmind/issues/119) |
| **3** | v0.7.x | Enterprise-Ready — Docker Hub, air-gapped, SBOM, compliance | [#120](https://github.com/dfrostar/neuralmind/issues/120) |

Plus two deferred review-feedback patches that should also land in v0.6.1:

- [#115](https://github.com/dfrostar/neuralmind/issues/115) — `event_log`
  rotation seek-from-zero (P2 correctness bug)
- [#116](https://github.com/dfrostar/neuralmind/issues/116) — `/api/queries`
  route test coverage gap

---

## 0. First action for the new session

```
mcp__github__list_pull_requests state=open
mcp__github__list_issues state=open labels=v0.6.1
```

Then check the four tracking issues to see what's already been done. If
the v0.6.0 handoff doc taught us anything: **never assume state from
context — always confirm via the issue tracker first.** That session
spent ~10 minutes recovering from a wrong assumption about which PRs
were merged when.

If [#117](https://github.com/dfrostar/neuralmind/issues/117) (Phase 0
hygiene) is unchecked → start there. It's the foundation everything else
sits on, and it's the only phase that gates on maintainer UI work.

If Phase 0 is done → start [#118](https://github.com/dfrostar/neuralmind/issues/118)
(Phase 1 install matrix).

---

## 1. Phase 0 — Hygiene cleanup ([#117](https://github.com/dfrostar/neuralmind/issues/117))

No public-facing marketing. Pure "make the repo look maintained."

Most of these need the **maintainer's hands** because GitHub UI auth is
the gate (branch deletion via MCP returns 403 in this environment; we
hit this twice in the v0.6.0 session). The agent can prepare a checklist
and confirm completion, but the user clicks.

### Checklist (lives in #117)

- Delete `claude/dispatch-release-v0.6.0` + `claude/v0.6.0-handoff-doc`
- Audit ~30 stale `claude/*` + `copilot/*` branches; delete the merged
  ones via `git for-each-ref --merged main` (the user-actioned step).
- Triage stale open PRs: #100, #93, #94, #95.
- Rewrite repo About-box.
- Add 7 repo topics: `graph-view`, `code-visualization`, `synapse`,
  `hebbian-learning`, `obsidian`, `force-directed-graph`, `code-graph`.
- Verify PyPI trusted publisher is still pinned to `release.yml`.

### What the agent can do here

- Open this checklist as the body of #117 (already done at handoff
  authoring time).
- Generate a delete-merged-branches shell script the user can paste:
  ```bash
  git fetch --prune origin
  git for-each-ref --merged origin/main --format='%(refname:short)' \
    refs/remotes/origin/claude/ refs/remotes/origin/copilot/ | \
    sed 's|^origin/||' | xargs -I {} git push origin :{}
  ```
- Triage the stale PRs (`mcp__github__pull_request_read` for each)
  and recommend keep/close/rebase.

---

## 2. Phase 1 — v0.6.1 "Install Anywhere" ([#118](https://github.com/dfrostar/neuralmind/issues/118))

**This is the headline phase.** The first marketing moment after
v0.6.0. Whole frame: *"NeuralMind installs wherever you work."*

### What ships

- `README.md` install matrix with five paths: `pip`, `pipx`, `uv pip`,
  `docker run`, source.
- `Dockerfile` in repo root (multi-stage, slim runtime).
- `docs/use-cases/install-paths.md` walkthrough.
- README "Verify install" snippet (the 4-line smoke test the v0.6.0
  session validated against PyPI).
- `pyproject.toml` keywords bump.
- Wiki `Setup-Guide.md` rewrite.

### Marketing artifacts to draft (gate on maintainer approval for publish)

- New v0.6.1 LinkedIn block in `docs/LINKEDIN-POST-DRAFT.md` — voice
  matches the feature-tour Draft B style.
- `docs/notebooklm/v0.6.1/` source pack — same 3-doc structure as
  v0.6.0; one of the three is "install anywhere".
- `docs/SCREENCAST-v0.6.1.md` — 60-sec script. Three beats:
  1. `pipx install neuralmind` — show the global CLI being available
  2. `docker run ghcr.io/dfrostar/neuralmind ...` — show the same in a
     container
  3. `neuralmind serve` in both — show the canvas working identically
- Add "Install methods" row to `docs/comparisons/*` pages.

### Execution plan (suggested)

1. Branch: `claude/v0.6.1-install-anywhere`
2. One PR with: Dockerfile + README diff + install-paths.md + comparisons
   row + keywords bump + Setup-Guide update + LinkedIn block + screencast
   script + NotebookLM pack
3. Single PR keeps the v0.6.1 narrative cohesive in review. ~2 hours of
   focused work.
4. Once merged → release-please proposes v0.6.1 → merge it → dispatch
   release.yml (same gotcha as v0.6.0; use the one-shot dispatch trick
   from `docs/HANDOFF-v0.6.0.md` §1c if needed).

---

## 3. Phase 2 — v0.7 "Always-On" ([#119](https://github.com/dfrostar/neuralmind/issues/119))

Second marketing moment. Audience: ops/SREs and developers who want
NeuralMind running across reboots.

### What ships

- `scripts/systemd/neuralmind-{watch,serve}.service` templates
- `scripts/launchd/com.neuralmind.{watch,serve}.plist` templates
- Windows Task Scheduler doc note (Scheduling-Guide.md already has the
  scaffolding)
- `neuralmind serve` `/healthz` endpoint — 200 + JSON. Stdlib-only,
  ~10 lines + ~3 tests.
- `docs/use-cases/always-on.md` walkthrough
- Aider MCP integration block in README (verify Aider supports stdio
  MCP first; reject if not)

### Marketing artifacts

- LinkedIn post: *"NeuralMind runs as a service now."* Showcases the
  live activity feed + multi-agent shared brain in a "set it and forget
  it" framing.
- v0.7 NotebookLM pack with always-on as one of the three docs.
- Screencast showing systemd + canvas pulsing as you save files on a
  real project.

### Execution plan

- ~1 day of work
- Two PRs would be reasonable: one for the templates + docs (low-risk),
  one for the `/healthz` endpoint (touches production code)

---

## 4. Phase 3 — v0.7.x "Enterprise-Ready" ([#120](https://github.com/dfrostar/neuralmind/issues/120))

Third marketing moment. Audience: CTOs, security teams, regulated
industries. By this phase we have the full procurement story.

### What ships

- GHCR (or Docker Hub) auto-built image from main on tag push.
  Recommend GHCR — free, integrates with GitHub Actions, no separate
  auth dance.
- Multi-platform (linux/amd64, linux/arm64).
- `docs/use-cases/air-gapped.md` — PyPI mirror + chromadb model
  pre-download script.
- SBOM auto-publication on tagged releases (`cyclonedx-py` or `syft`).
- `docs/COMPLIANCE-SUMMARY.md` consolidating NIST AI RMF + SOC 2 +
  GDPR claims already scattered across `docs/SECURITY-GUIDE.md` and
  `docs/ENTERPRISE.md`.

### Marketing artifacts

- LinkedIn post targeted at CTOs / Security.
- Optional Hacker News submission. Higher variance; the right audience
  for this phase, but be prepared for tough comments.
- Pinned Discussions thread for regulated-industry deployment Q&A.

### Execution plan

- ~2-3 days across docs + workflows + Docker build verification
- Multiple PRs makes sense here: image build workflow, air-gapped doc,
  SBOM workflow, compliance summary

---

## 5. Outstanding v0.6.1 review-feedback patches

These are the two non-blocking review items the v0.6.0 merge train
deferred. They should land **with** the Phase 1 install-anywhere PR (or
as a small companion PR) so v0.6.1 closes the v0.6.0 review thread audit
trail.

### [#115](https://github.com/dfrostar/neuralmind/issues/115) — `fix(event_log)`: reopen rotated logs from offset 0

- ~5 lines + 1 test
- The fix is in the issue body verbatim
- P2 correctness gap; cheap to close

### [#116](https://github.com/dfrostar/neuralmind/issues/116) — `test(server)`: add `/api/queries` route coverage

- ~30 lines, test-only, zero production code
- Test cases listed verbatim in the issue body
- Closes a CI safety-net gap

---

## 6. Cross-phase marketing arc

The whole point of the 4-phase plan is **three LinkedIn moments over
6-8 weeks** instead of one big bang. Each phase's post reaches a
different audience.

| Phase | Audience | Post angle | Pair with |
|-------|----------|-----------|-----------|
| 0 | (internal) | — | (no marketing) |
| 1 | Python developers, AI tooling early adopters | "Install five ways" | Screencast: pipx + docker side-by-side |
| 2 | Ops/SREs, dev tooling power users | "Runs as a service" | Screencast: systemd + canvas pulsing across saves |
| 3 | CTOs, security teams, regulated industries | "Containerized + SBOM + NIST" | Compliance one-pager + HN submission |

### Cross-phase tie-ins

- **`docs/LINKEDIN-POST-DRAFT.md`** grows with each phase. Same file,
  new block per release. v0.6.0 already has three drafts; add a v0.6.1
  block (Phase 1) and so on. Easier to A/B test voice if all drafts
  live in one place.
- **`docs/notebooklm/`** gets a new subdirectory per phase. Same
  3-doc structure that worked for v0.6.0. The NotebookLM video format
  is replicable per release.
- **`docs/SCREENCAST-*.md`** scripts: one per phase. All 60 seconds.
  All three beats. The structure scales.
- **Wiki Setup-Guide.md** becomes the single canonical landing page
  for "how do I install this." Every phase adds rows; nothing gets
  rewritten.
- **Comparisons table** gets the "Install methods" row in Phase 1; the
  "Always-on capable" row in Phase 2; the "Container + SBOM" row in
  Phase 3. Same table, increasing differentiation.

---

## 7. Repo conventions (reference)

Same as v0.6.0. Not repeating in detail — see
[`docs/HANDOFF-v0.6.0.md`](HANDOFF-v0.6.0.md) §6. Highlights worth
re-stating because they bit us last time:

- **Branch naming:** `claude/<short-descriptor>`.
- **Conventional commits:** `feat(scope): ...`, `fix(scope): ...`,
  `docs(scope): ...`, `test(scope): ...`, `chore(scope): ...`. The
  `feat`/`fix` distinction matters for release-please bump logic.
- **release-please bumps `0.x` on `feat(...)` as minor** (we merged
  PR #114 to make this explicit during the v0.6.0 train).
- **PR merges land via `merge` commit method** for code PRs, `squash`
  for release-please. Don't use `rebase` — release-please needs the
  merge commit shape.
- **`docs/wiki/**` auto-mirrors to the public Wiki via
  `.github/workflows/sync-wiki.yml`.** Edit the local copies.
- **`neuralmind/web/*` is read-only at runtime.** Edit directly.
- **PyPI publish requires manual `release.yml` dispatch** — the
  GITHUB_TOKEN limitation that killed v0.5.4's first attempt is still
  active. v0.6.0 dispatched via the one-shot trigger workflow approach
  documented inline at the time (see chat history). Reuse that pattern
  for v0.6.1 if `gh workflow run` from the maintainer's laptop isn't
  available.

### Things that changed since v0.6.0 handoff

- `event_bus.py` and `event_log.py` are production modules now. Any
  Architecture / API Reference docs that reference them are valid
  cross-links (see wiki/Architecture.md for the example pattern).
- `neuralmind serve` is the **headline feature**, not a side feature.
  Frame v0.6.1 and beyond around it.
- The synapse store is shared across all agents talking to the same
  project — Phase 1+ docs should reinforce this (multi-agent.md is
  already the canonical page for this story).

---

## 8. Phase D backlog (carried over from v0.6.0)

Items that didn't ship in v0.6.0 and aren't on the v0.6.1+ roadmap
above, but should stay tracked:

- Saved named graph views (Obsidian-style localStorage-backed presets)
- Right-click context menu on graph nodes (open-in-editor, pin/unpin,
  focus, copy id)
- PNG / SVG canvas export
- Time-based edge filter (complementing v0.6.0's min-weight slider)
- Unify `neuralmind watch` with the in-process bus (so single-process
  serve+watch doesn't need the JSONL bridge)

These are pure frontend wins. They could roll into Phase 1 or Phase 2
if there's appetite, or stay queued as v0.8 candidates.

---

## 9. Open questions for the user

Things the agent should ask before acting on, per the v0.6.0 handoff
doc's pattern:

1. **Cadence**: spread (one phase per 1-2 weeks, three LinkedIn moments
   over 6-8 weeks) or sprint (all 4 phases in one weekend)? The
   recommendation is *spread* — gives v0.6.0 time to land naturally,
   builds anticipation, lets us measure which install paths actually
   convert (PyPI download stats, GitHub stars). But "sprint" is valid
   if there's a conference or pitch deadline driving urgency.

2. **Docker registry**: GHCR (free, GitHub-integrated, no separate
   auth) or Docker Hub (more discoverable for non-GitHub users, but
   another account to maintain)? Recommendation: **both** — GHCR as
   the canonical, Docker Hub as a mirror. But Phase 3 can ship GHCR
   only and add Docker Hub later if there's demand.

3. **HN submission timing**: with v0.7.x as recommended, or earlier
   (e.g. with v0.6.0's live activity feed, which is genuinely novel)?
   The trade-off: earlier means less polish on the enterprise story
   but more excitement about the headline feature. v0.6.0 missed the
   HN window already (now ~24h post-publish). v0.7.x with the
   complete "5-phase distribution" story is a stronger HN pitch.

4. **Aider integration**: are we OK adding an integration block to
   README if Aider's MCP support requires a specific version that
   isn't yet stable? Or wait for it to ship in their stable release?
   Recommend wait — README integrations should be verified working.
