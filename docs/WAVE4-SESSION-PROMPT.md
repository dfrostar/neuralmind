# Next Session Prompt — NeuralMind Wave 4 (C4 COMPLETE)

**Date:** 2026-07-21
**Autopilot:** v0.8.0 (Wave 12 shipped — private, not published)
**NeuralMind:** v1.1.1 (Wave 12 tagged on GitHub, pip upgraded)
**Index:** rebuilt, fresh (11,530 nodes, 593 communities, IR v1 valid)

---

## Recap: What Wave 12 Closed

Wave 12 sold the first real seat. The operator can now:
- Issue real Stripe subscriptions (`issue_license(live_mode=True)`)
- Wire `require_admin()` into seat mutations (free tier bypasses limit)
- Documented customer handoff + webhook e2e ceremonies
- Synced version state (repo/manifest/PyPI all at 1.1.0+)

DeepSeek QA on Wave 12 (`seats.py` + `cli.py`): 1 CRITICAL + 7 WARNING patched.
Tests: 130/130 autopilot, 40/40 tier2, full neuralmind suite all green.

---

## C4 — IMPLEMENTED & COMMITTED (7e7ff98)

`/home/dtfrost/neuralmind/quality_harness.py` — independent quality validation gate
- `QualityHarness.evaluate()` — runs retrieval with candidate params against fixture queries, scores with quality.py
- `QualityHarness.decide()` — promote/rollback/hold gate (harness pass + hysteresis beat)
- Fail-open: no fixtures/embedder returns `passed=True` with `fitness=0.0`
- Tuner wiring: `promote_with_harness()`, `_record_decision()` in `self_improve:tuner_last_decision`
- Backward compatible: `harness=None` preserves hysteresis-only behavior
- 13/13 new tests passing, ruff clean
- DeepSeek QA dispatched (separate subagent, results pending)

---

## Wave 4 Sequence (After C4)

| # | Item | Bucket | Depends on | Complexity |
|---|------|--------|------------|------------|
| 1 | ~~C4 — CI-gated tuner promotion~~ | ~~Self-improvement~~ | C3 + D | **DONE** |
| 2 | D3 — Populate judge transcripts | Quality harness | D1 | LOW |
| 3 | D4 — Per-language fixtures | Quality harness | D1 | MEDIUM |
| 4 | E1 — Contribution-quality scoring | Team memory | D | MEDIUM |
| 5 | E2 — Merge semantics with decay-on-conflict | Team memory | A2 | HIGH |
| 6 | E3 — Peer review gate | Team memory | E1 | LOW |
| 7 | E4 — Staleness detection | Team memory | A4 | LOW |
| 8 | F3 — Tool-use metrics pipeline | Daemon/MCP | F2 | MEDIUM |
| 9 | F4 — Backpressure + circuit breakers | Daemon/MCP | F2 | MEDIUM |
| 10 | G3 — Modularity clustering (Louvain/Leiden) | Graph precision | G1+G2 | HIGH |
| 11 | G4 — Incremental re-extraction | Graph precision | G1+G2 | HIGH |

**Critical path:** C4 → D3/D4 → E1/E2/E4 → F3/F4 → G3/G4

---

## Your Documentation Approach

Same workflow. Apply all lessons:
- **Version sync:** If you bump version, update ALL THREE: `pyproject.toml`, `__init__.py`, `.release-please-manifest.json`
- **CI green before publish:** Merge release-please PR only after all jobs pass
- **Index freshness:** Run `neuralmind build` before tagging a release
- **Integration test gate:** Every cross-repo/module boundary test must use real implementations on both sides
- **Status flow tracing:** For every new Literal member, document producer + consumers

---

## Versioning

- autopilot: v0.8.0 → v0.9.0 (Wave 4 features)
- neuralmind: v1.1.1 → v1.2.0 (Wave 4 features)

---

## Conventions (Honest, KISS/DRY, No Overclaim)

- **Claim tiers:** Every BRD/TRD claim classified A/B/C/D.
- **Honest framing:** Document what's NOT done yet.
- **Private repo discipline:** Autopilot stays private. NeuralMind Stripe code public.
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
6. `git-repo-cleanup` — pre-release hygiene checklist

---

## Pre-Flight (Before This Session's Work)

- [x] Wave 12 code committed and pushed
- [x] NeuralMind index rebuilt (fresh)
- [x] CI green
- [x] Release-please PR merged (1.1.0+)
- [x] NeuralMind upgraded to latest (v1.1.1 — `pip install --upgrade neuralmind`)
- [x] DeepSeek QA on Wave 12 code completed (all patched)
- [x] C4 design approved
- [x] C4 implementation complete + committed (7e7ff98) + pushed
- [x] C4 tests green (13/13)
- [ ] C4 DeepSeek QA (dispatched, separate subagent, results pending)
- [ ] D3 — Populate judge transcripts
- [ ] D4 — Per-language fixtures

---

## Start Here

1. Read `/home/dtfrost/neuralmind/docs/FUTURE-PROOFING-PLAN.md` §9 (sequence) and §10 (decisions) — confirm D3/D4 scope
2. Read `/home/dtfrost/neuralmind/neuralmind/ragas.py` — D1 judge (already built)
3. Read `/home/dtfrost/neuralmind/neuralmind/quality.py` — D2 retrieval metrics (already built)
4. Read `/home/dtfrost/neuralmind/neuralmind/fixtures.py` — fixture loader (already built)
5. Read `/home/dtfrost/neuralmind/neuralmind/quality_harness.py` — C4 freshly shipped
6. Check DeepSeek QA results on C4 (separate subagent dispatched, may already be in inbox)
7. Plan D3 + D4 into a single BRD/TRD
8. Implement D3 (judge transcripts) — LOW complexity, quick win
9. Implement D4 (per-language fixtures) — MEDIUM complexity
10. Run DeepSeek QA on D3/D4
11. Commit, push, append to `WAVE4-BRD.md` + `WAVE4-TRD.md`

---

*Next session prompt v3.0. C4 COMPLETE. D3/D4 next.*
