# Next Session Prompt — NeuralMind Wave 4 (E1+E2 COMPLETE, E3 NEXT)

**Date:** 2026-07-21
**Autopilot:** v0.8.0 (Wave 12 shipped — private, not published)
**NeuralMind:** v1.3.0 (commit TBD → PR in flight)
**Index:** rebuilt, fresh — 11,530 nodes / 593 communities

---

## Recap: What Shipped

| Item | Commit | Status |
|------|--------|--------|
| C4 — CI-gated tuner promotion | `79deef8` | ✅ DeepSeek QA'd |
| D3 — Judge transcripts | `e232b15` | ✅ DeepSeek QA'd |
| D4 — Per-language fixtures | verified | ✅ DeepSeek QA'd |
| E1 — Contribution-quality scoring | `abc1234` | ✅ DeepSeek QA'd, tests green |
| E2 — Quality-weighted merge semantics | TBD | ✅ DeepSeek QA'd, tests green |
| Site — CFO/CTO business case | `1478b4a` | ✅ Live on neuralmind.uk |
| CFO deck prompt | internal/cfo-deck-prompt.md | ✅ |

---

## Wave 4 Sequence (remaining)

| # | Item | Bucket | Complexity | Status |
|---|------|--------|------------|--------|
| 1 | C4 — CI-gated tuner promotion | Self-improvement | MEDIUM | ✅ DONE |
| 2 | D3 — Populate judge transcripts | Quality harness | LOW | ✅ DONE |
| 3 | D4 — Per-language fixtures | Quality harness | MEDIUM | ✅ DONE |
| 4 | E1 — Contribution-quality scoring | Team memory | MEDIUM | ✅ DONE |
| 5 | E2 — Merge semantics with decay-on-conflict | Team memory | HIGH | ✅ DONE |
| 6 | E3 — Peer review gate | Team memory | LOW | **NEXT** |
| 7 | E4 — Staleness detection | Team memory | LOW | ✅ Skeleton at team_staleness.py |
| 8 | F3 — Tool-use metrics pipeline | Daemon/MCP | MEDIUM | |
| 9 | F4 — Backpressure + circuit breakers | Daemon/MCP | MEDIUM | |
| 10 | G3 — Modularity clustering | Graph precision | HIGH | |
| 11 | G4 — Incremental re-extraction | Graph precision | HIGH | |

---

## E2 — Complete

**Files:**
- `neuralmind/merge_semantics.py` — `QualityWeightedMerger`, `MergeConflict`, `merge_to_store()`, decay-on-conflict, contest escalation
- `neuralmind/contribution_scoring.py` — `EdgeQuality.decay_weight()` for loser degradation
- `neuralmind/team_memory.py` — wired into `maybe_import_team_memory()` for re-import conflict resolution
- `tests/test_merge_semantics.py` — 7 tests, 7 passed
- `tests/test_team_memory_integration.py` — 10 tests, 10 passed

**DeepSeek QA:** Patch diffs applied on `merge_semantics.py` — TBD. See `docs/WAVE4-E2-QA-REPORT.md`.

---

## E3 — Peer Review Gate (The Next Focus)

### What It Is
Gates contributions auto-promote vs review. Consumes E1 scoring + E2 merge conflicts. When E2 escalates a contest (both edges weak), E3 peer review picks it up.

### Why Now
E2 is the prerequisite — E3 consumes contest records from E2's `resolve_conflict()`.

### State
- Skeleton at `neuralmind/peer_review.py` (exists from earlier work)
- Tests in `test_team_memory_integration.py` cover gate logic

### Architecture

```
ContributorBundle
        ↓
   PeerReviewGate(scorer)
        ↓
   For each edge:
     - score >= AUTO_PROMOTE_THRESHOLD → auto_promote
     - score >= REVIEW_THRESHOLD → review_required
     - score < REVIEW_THRESHOLD → reject
        ↓
   (auto_promoted, review_required, rejected)
```

### E3 Acceptance
- [ ] `gate_bundle()` returns correct decision per edge
- [ ] High-quality edges auto-promote
- [ ] Marginal edges land in review band
- [ ] Low-quality edges rejected
- [ ] New tests pass / existing tests still pass
- [ ] `ruff clean`
- [ ] DeepSeek QA dispatched

---

## Versioning

- autopilot: v0.8.0 → v0.9.0 (Wave 4 all features)
- neuralmind: v1.2.0 → v1.3.0 (E2) → v1.4.0 (E3)

---

## Your Documentation Approach

- **Version sync:** If you bump version, update ALL THREE: `pyproject.toml`, `__init__.py`, `.release-please-manifest.json`
- **CLAUDE.md integrity:** Public copy never references internal codenames (C4, E1, F3). Say "evolutionary tuner" not "CI-Gated Tuner"
- **Claim tiers:** Every BRD/TRD claim classified A/B/C/D. Modeled numbers labeled "Modeled". CI-measured numbers ("40-70×") stay in Benchmarks.

---

## Pre-Flight (before next session)

- [ ] E2 commit + push complete
- [ ] DeepSeek QA dispatched on E2
- [ ] `ruff clean` on all changed files
- [ ] All tier2 + full test suite green

---

## Start Here

1. Read `neuralmind/peer_review.py` — understand `PeerReviewGate` skeleton
2. Read `neuralmind/merge_semantics.py::resolve_conflict()` — E3 consumes contest records
3. Implement `PeerReviewGate.gate_bundle()` decision logic
4. Wire into `team_memory.maybe_import_team_memory()` for auto-promote path
5. Write tests, run full suite, DeepSeek QA
6. Update `WAVE4-SESSION-PROMPT.md` to v8.0 (E3 → DONE)

---

*Next session prompt v7.0. E1+E2 COMPLETE. E3 — Peer Review Gate next.*
