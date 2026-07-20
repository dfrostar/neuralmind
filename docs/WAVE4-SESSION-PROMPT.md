# Next Session Prompt — NeuralMind Wave 4 (C4 + D3 + D4 COMPLETE)

**Date:** 2026-07-20
**Autopilot:** v0.8.0 (Wave 12 shipped — private, not published)
**NeuralMind:** v1.1.1
**Index:** rebuilt, fresh

---

## Recap: What Shipped

### C4 — CI-gated tuner promotion (`79deef8`)
- `neuralmind/quality_harness.py` — independent validation gate
- `tuner.py` — `promote_with_harness()`, `_record_decision()`
- NaN-safe clamp (DeepSeek QA catch)
- 14/14 tests passing

### D3 — Judge transcripts (`7e7ff98`)
- `neuralmind/judge_transcripts.py` — loader + offline generator
- 76 offline transcripts generated from benchmark fixtures
- CLI: `--generate`, `--validate`, `--write`, `--list`

### D4 — Per-language fixtures (already existed)
- All 10 languages have `benchmark_queries_*.json`:
  go (19), java (19), rust (19), ts (19), c (10), cpp (10),
  csharp (5), ruby (4), php (4), python (19)
- `evals/quality/runner.py` has full suite registry
- 50+ total queries across 7+ suites

---

## Wave 4 Sequence (remaining)

| # | Item | Bucket | Complexity | Status |
|---|------|--------|------------|--------|
| 1 | C4 — CI-gated tuner promotion | Self-improvement | MEDIUM | ✅ DONE |
| 2 | D3 — Populate judge transcripts | Quality harness | LOW | ✅ DONE |
| 3 | D4 — Per-language fixtures | Quality harness | MEDIUM | ✅ DONE |
| 4 | E1 — Contribution-quality scoring | Team memory | MEDIUM | NEXT |
| 5 | E2 — Merge semantics with decay-on-conflict | Team memory | HIGH | |
| 6 | E3 — Peer review gate | Team memory | LOW | |
| 7 | E4 — Staleness detection | Team memory | LOW | |
| 8 | F3 — Tool-use metrics pipeline | Daemon/MCP | MEDIUM | |
| 9 | F4 — Backpressure + circuit breakers | Daemon/MCP | MEDIUM | |
| 10 | G3 — Modularity clustering | Graph precision | HIGH | |
| 11 | G4 — Incremental re-extraction | Graph precision | HIGH | |

**Critical path:** C4 → D3/D4 → E1/E2/E4 → F3/F4 → G3/G4

---

## Next Session: E1 — Contribution-Quality Scoring

### What It Is
Score each contributor's team-memory edges by their measured onboarding
lift (E1.5 eval). High contributors get higher initial weight in the
`shared` namespace; low contributors rely on reinforcement to persist.

### Files to Read
1. `neuralmind/team_memory.py` — current bundle import + publish
2. `neuralmind/entity_resolution.py` — A2 (E2 depends on this)
3. `neuralmind/synapses.py` — SynapseStore + namespace model
4. `tests/test_team_memory.py` — existing tests

### Approach
1. Add `ContributionScorer` class in new file `neuralmind/contribution_scoring.py`
2. Score function: reinforcement frequency + recency + conflict rate
3. Wire into `team_memory.publish()` — set initial weight on edges
4. Persist scores in synapse meta table
5. Write tests

### E1 Acceptance
- [ ] ContributionScorer evaluates a contributor's edges
- [ ] High-quality contributors get higher initial weight
- [ ] Scores persisted in synapse meta table
- [ ] Backward compatible: no scorer = current behavior
- [ ] Tests green

---

## Your Documentation Approach

- **Version sync:** If you bump version, update ALL THREE: `pyproject.toml`, `__init__.py`, `.release-please-manifest.json`
- **CI green before publish:** Merge release-please PR only after all jobs pass
- **Index freshness:** Run `neuralmind build` before tagging
- **Integration test gate:** Every cross-repo/module boundary test must use real implementations on both sides
- **Status flow tracing:** For every new Literal member, document producer + consumers

---

## Versioning

- autopilot: v0.8.0 → v0.9.0 (Wave 4 features)
- neuralmind: v1.1.1 → v1.2.0 (Wave 4 features)

---

## Conventions (Honest, KISS/DRY, No Overclaim)

- **Claim tiers:** Every BRD/TRD claim classified A/B/C/D
- **Honest framing:** Document what's NOT done yet
- **Private repo discipline:** Autopilot stays private
- **No phone-home:** All operations local
- **Fresh verification:** Run `pytest` before claiming done
- **After 'approved'/'go':** work is done — don't re-summarize

---

## Skills to Load

1. `neuralmind-autopilot` — Wave 12 architecture + lessons
2. `autopilot-release` — release workflow
3. `deepseek-qa` — phase-gate QA dispatch
4. `tier2-dual-tier-license` — product-side validation patterns
5. `optional-heavy-dependency` — optional SDK integration pattern
6. `git-repo-cleanup` — pre-release hygiene checklist

---

## Pre-Flight

- [x] Wave 12 code committed and pushed
- [x] CI green
- [x] Release-please PR merged (1.1.1)
- [x] C4 implementation + NaN fix pushed
- [x] D3 judge transcripts pushed
- [x] D4 per-language fixtures verified
- [ ] E1 implementation complete
- [ ] E1 tests green
- [ ] E1 DeepSeek QA

---

## Start Here

1. Read `neuralmind/team_memory.py` — understand publish() and bundle format
2. Read `neuralmind/entity_resolution.py` — will be needed for E2
3. Read `neuralmind/synapses.py` — SynapseStore + meta table
4. Plan E1 design: ContributionScorer class + scoring function
5. Implement `neuralmind/contribution_scoring.py`
6. Write tests, run full suite, DeepSeek QA

---

*Next session prompt v4.0. C4 + D3 + D4 COMPLETE. E1 — Contribution-Quality Scoring next.*
