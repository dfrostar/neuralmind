# Next Session Prompt — NeuralMind Wave 4

**Date:** 2026-07-21
**Autopilot:** v0.8.0 (Wave 12 shipped — private, not published)
**NeuralMind:** v1.1.1 (Wave 12 tagged on GitHub)
**Index:** rebuilt, fresh

---

## Recap: What Wave 12 Closed

Wave 12 sold the first real seat. The operator can now:
- Issue real Stripe subscriptions (`issue_license(live_mode=True)`)
- Wire `require_admin()` into seat mutations (free tier bypasses limit)
- Documented customer handoff + webhook e2e ceremonies
- Synced version state (repo/manifest/PyPI all at 1.1.0+)

Tests: 130/130 autopilot, 40/40 neuralmind tier2 (2 expected skips). Full neuralmind suite also green.

---

## Goal: Wave 4 — Close the Loop

Wave 4 has 11 workstreams across 6 buckets. Per FUTURE-PROOFING-PLAN §9 sequence, the self-improvement loop (C4) is first — it closes the tuner promotion path.

| # | Item | Bucket | Depends on | Complexity |
|---|------|--------|------------|------------|
| 1 | C4 — CI-gated tuner promotion | Self-improvement | C3 + D | MEDIUM |
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

## Start Here

1. Read `/home/dtfrost/neuralmind/docs/FUTURE-PROOFING-PLAN.md` §9 (sequence) and §10 (decisions) — confirm Wave 4 scope
2. Read `/home/dtfrost/neuralmind/neuralmind/tuner.py` — understand current C3 population search (what C4 gates)
3. Read `/home/dtfrost/neuralmind/neuralmind/experiment_runner.py` + `promotion_engine.py` — understand the CI gate pathway
4. Read `/home/dtfrost/neuralmind/neuralmind/team_memory.py` — understand current bundle publish path
5. Read `/home/dtfrost/neuralmind/neuralmind/graphgen.py` — understand current community assignment
6. Run `PYTHONPATH=. python3 -m pytest tests/ -q` in both repos to confirm green state
7. Plan Wave 4 items into a prioritized BRD/TRD sequence — recommend C4 first, then D3/D4, then E1/E2/E4, then F3/F4, then G3/G4

---

## Pre-Flight (Before This Session's Work)

- [x] Wave 12 code committed and pushed
- [x] NeuralMind index rebuilt (fresh)
- [x] CI green
- [x] Release-please PR merged (1.1.0+)
- [x] NeuralMind upgraded to latest (v1.1.1 — `pip install --upgrade neuralmind`)
- [ ] DeepSeek QA on Wave 12 code (dispatched, pending results)
- [ ] `neuralmind build` (run again after any code changes)

---

*Next session prompt v1.0. Wave 4 — Close the Loop.*
