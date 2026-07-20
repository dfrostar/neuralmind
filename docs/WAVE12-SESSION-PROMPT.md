# Next Session Prompt — NeuralMind Wave 4

**Date:** 2026-07-21
**Autopilot:** v0.8.0 (Wave 12 shipped — private, not published)
**NeuralMind:** v1.1.0 (Wave 12 tagged on GitHub, PyPI publish pending)
**Index:** fresh, 11,488 nodes / 25,766 edges / 590 communities

---

## Recap: What Wave 12 Closed

Wave 12 sold the first real seat. The operator can now:
- Issue real Stripe subscriptions (`issue_license(live_mode=True)`)
- Wire `require_admin()` into seat mutations (free tier bypasses limit)
- Documented customer handoff + webhook e2e ceremonies
- Synced version state (repo/manifest/PyPI all at 1.1.0)

CI: all green. Tests: 130/130 autopilot, 1500+ neuralmind (1 pre-existing failure on Windows — `test_run_diagnostics_returns_all_checks` — may need recheck).

---

## Goal: Wave 4 — Close the Loop

Per FUTURE-PROOFING-PLAN §9, Wave 4 items are:

| # | Item | Bucket | Depends on | Complexity |
|---|------|--------|------------|------------|
| C4 | CI-gated tuner promotion | Self-improvement | C3 + D | MEDIUM |
| G3 | Modularity clustering (Louvain/Leiden) | Graph precision | G1+G2 | HIGH |
| G4 | Incremental re-extraction | Graph precision | G1+G2 | HIGH |
| E1 | Contribution-quality scoring | Team memory | D | MEDIUM |
| E2 | Merge semantics with decay-on-conflict | Team memory | A2 | HIGH |
| E3 | Peer review gate | Team memory | E1 | LOW |
| E4 | Staleness detection | Team memory | A4 | LOW |
| F3 | Tool-use metrics pipeline | Daemon/MCP | F2 | MEDIUM |
| F4 | Backpressure + circuit breakers | Daemon/MCP | F2 | MEDIUM |
| D3 | Populate judge transcripts | Quality harness | D1 | LOW |
| D4 | Per-language fixtures | Quality harness | D1 | MEDIUM |

**Critical path:** D → C1 → C2/C3 → A3/A4 → E1/E2/E4

C1-C3 and A3-A4 shipped (Waves 2-3). Focus Wave 4 on **C4 (CI-gated tuner promotion)** first — it closes the self-improvement loop. The tuner (C3) runs but never auto-promotes; C4 adds the CI gate that ships or rolls back tuned configs.

---

## Your Documentation Approach

Same workflow. Apply Wave 12 lessons:
- **Version sync:** If you bump version, update ALL THREE: `pyproject.toml`, `__init__.py`, `.release-please-manifest.json`
- **CI green before publish:** Merge release-please PR only after all jobs pass
- **Index freshness:** Run `neuralmind build` before tagging a release

---

## Versioning

- autopilot: v0.8.0 → v0.9.0 (Wave 4 features)
- neuralmind: v1.1.0 → v1.2.0 (Wave 4 features)

---

## Conventions (Honest, KISS/DRY, No Overclaim)

- **Claim tiers:** Every BRD/TRD claim classified A/B/C/D.
- **Honest framing:** Document what's NOT done yet.
- **Private repo discipline:** Autopilot stays private. NeuralMind Stripe code public (API interaction).
- **No phone-home:** All operations local. Stripe webhooks come TO us.
- **Fresh verification:** Run `pytest` before claiming done.
- **After 'approved'/'go':** work is done — don't re-summarize; move to next action.

---

## Skills to Load

1. `neuralmind-autopilot` — Wave 12 architecture + lessons
2. `autopilot-release` — release workflow
3. `deepseek-qa` — phase-gate QA dispatch
4. `tier2-dual-tier-license` — product-side validation patterns
5. `optional-heavy-dependency` — optional SDK integration pattern
6. `git-repo-cleanup` — pre-release hygiene checklist (NEW, Section 7: version drift)

---

## Start Here

1. Read `/home/dtfrost/neuralmind/docs/FUTURE-PROOFING-PLAN.md` §9 (sequence) and §10 (decisions) — confirm Wave 4 scope
2. Read `/home/dtfrost/neuralmind/neuralmind/tuner.py` — understand current C3 population search (what C4 gates)
3. Read `/home/dtfrost/neuralmind/neuralmind/experiment_runner.py` + `promotion_engine.py` — understand the CI gate pathway
4. Read `/home/dtfrost/neuralmind/docs/WAVE12-CUSTOMER-HANDOFF.md` + `WAVE12-WEBHOOK-E2E.md` — the runbooks are now operational; they may need updates if C4 changes the tuner behavior
5. Run the cleanup checklist from `git-repo-cleanup` skill to confirm repo state
6. Plan Wave 4 items into a prioritized BRD/TRD sequence — recommend C4 first, then D3/D4, then E1/E2/E4, then F3/F4, then G3/G4

---

## Pre-Flight (Before This Session's Work)

- [x] Wave 12 code committed and pushed
- [x] NeuralMind index rebuilt (11,488 nodes, fresh)
- [x] CI green (all 5 jobs)
- [x] Release-please PR #383 merged (1.1.0)
- [ ] PyPI publish (pending — separate action)
- [ ] `neuralmind build` (run again after any code changes)

---

*Next session prompt v1.0. Wave 4 — Close the Loop.*
