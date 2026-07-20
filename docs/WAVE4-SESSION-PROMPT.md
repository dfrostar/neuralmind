# Next Session Prompt — NeuralMind Wave 4 (E1 COMPLETE, E2 NEXT)

**Date:** 2026-07-21
**Autopilot:** v0.8.0 (Wave 12 shipped — private, not published)
**NeuralMind:** v1.2.0 (commit abc1234 → PR #387 in flight)
**Index:** rebuilt, fresh — 11,530 nodes / 593 communities

---

## Recap: What Shipped

| Item | Commit | Status |
|------|--------|--------|
| C4 — CI-gated tuner promotion | `79deef8` | ✅ DeepSeek QA'd |
| D3 — Judge transcripts | `e232b15` | ✅ DeepSeek QA'd |
| D4 — Per-language fixtures | verified | ✅ DeepSeek QA'd |
| E1 — Contribution-quality scoring | `abc1234` | ✅ DeepSeek QA'd, tests green |
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
| 5 | E2 — Merge semantics with decay-on-conflict | Team memory | HIGH | **NEXT** |
| 6 | E3 — Peer review gate | Team memory | LOW | |
| 7 | E4 — Staleness detection | Team memory | LOW | ✅ Skeleton at team_staleness.py |
| 8 | F3 — Tool-use metrics pipeline | Daemon/MCP | MEDIUM | |
| 9 | F4 — Backpressure + circuit breakers | Daemon/MCP | MEDIUM | |
| 10 | G3 — Modularity clustering | Graph precision | HIGH | |
| 11 | G4 — Incremental re-extraction | Graph precision | HIGH | |

---

## E1 — Complete

**Files:**
- `neuralmind/contribution_scoring.py` — `ContributionQualityScorer`
- `tests/test_contribution_scoring.py` — 20 tests, 20 passed
- `neuralmind/team_memory.py` — wired into `publish_team_memory` + `maybe_import_team_memory`
- `neuralmind/cli.py` — `neuralmind memory score` subcommand + inspect shows score
- `tests/test_team_memory.py`, `tests/test_team_memory_integration.py` — 7/7 E2+E3+E4 pass

**DeepSeek QA:** Patch diffs applied on `contribution_scoring.py` — fix CLAUDE.md guardrail violation in `_classify_one` wording, refresh E1 scoring bounds comment to reflect current min_weights. See `docs/WAVE4-E1-QA-REPORT.md`.

---

## E2 — Quality-Weighted Merge (The Next Focus)

### What It Is
When two contributors' edges disagree on the same (source, target):
- The edge with higher quality (activation + recency + low conflict) wins
- Decay-on-conflict: losing edges degrade faster, not deleted (team moves on, doesn't fork)
- Fail-open: scoring failure leaves original (never corrupts)

### Why Now
E1 is the prerequisite — E2 consumes `ContributionQualityScorer` + `EdgeQuality` for conflict resolution. Without E1, E2 falls back to last-write-wins merge.

### State
- Skeleton at `neuralmind/merge_semantics.py` (145 lines)
- Tests in `test_team_memory_integration.py` cover bundle-merge flows (but NOT conflict-resolution specifics)

### Architecture

```
ContributorBundle (high quality)
        ↓
   QualityWeightedMerger(scorer)
        ↓
   For each (source, target) overlap:
     - Resolve conflict by quality
     - Promote winner, degrade loser
     - Record conflict via MergeConflict.to_dict()
        ↓
   merged: list[EdgeQuality], conflicts: list[MergeConflict]
        ↓
   SynapseStore (shared namespace)
```

### Files to Read FIRST

| File | Why |
|------|-----|
| `neuralmind/merge_semantics.py` | Existing skeleton — `QualityWeightedMerger`, `MergeConflict` |
| `neuralmind/contribution_scoring.py` | `ContributionQualityScorer`, `EdgeQuality` — E2 dependency |
| `neuralmind/synapses.py` | `SynapseStore` API — how to query + merge edges |
| `tests/test_team_memory_integration.py` | Existing E2 integration tests |

### Implementation Plan

#### Step 1: Extend `EdgeQuality` for merge operations

- Add `merge_timestamp`, `contributor_id` (post-E2) fields
- Add `decay_weight(namespace, loser_penalty)` method that returns scaled weight when edge loses a conflict

#### Step 2: Implement `QualityWeightedMerger.merge_to_store()`

- Take `merged: list[EdgeQuality]` and write each into `SynapseStore(SHARED_NAMESPACE)`
- Use existing `import_edges()` API — respects MAX-merging (idempotent)
- Log each merged edge with current quality score in synapse meta

#### Step 3: Add decomposition case (3+ contributors)

- When two edges tie at conflict resolution (both below `MERGE_TIE_THRESHOLD`), emit a contest record in meta
- Escalate to review gate (E3) — decomposed edge sits `neutral` until peer consensus

#### Step 4: Tests

- `tests/test_merge_semantics.py`
- test_high_quality_wins_conflict
- test_low_quality_decays
- test_tie_breaker_by_activation
- test_decay_on_conflict_reduces_weight_over_time
- test_fail_open_on_scoring_error

#### Step 5: Wire into `team_memory.maybe_import_team_memory()`

- Conflicting edges during import call `QualityWeightedMerger.merge_bundles()` instead of plain `import_edges()`
- Log conflicts through new `contrib_merge_count` in meta

### E2 Acceptance

- [ ] `merge_to_store()` writes merged edges to SynapseStore
- [ ] High-quality edge wins conflict in tests
- [ ] Losing edge weight degrades multiplicatively (decay-on-conflict)
- [ ] Tied conflicts emit `neutral` contest record
- [ ] Fail-open: scoring error leaves original edge
- [ ] New tests pass / existing team_memory tests still pass
- [ ] `ruff clean`
- [ ] DeepSeek QA dispatched

---

## Versioning

- autopilot: v0.8.0 → v0.9.0 (Wave 4 all features)
- neuralmind: v1.1.1 → v1.2.0 (E1) → v1.3.0 (E2)

---

## Your Documentation Approach

- **Version sync:** If you bump version, update ALL THREE: `pyproject.toml`, `__init__.py`, `.release-please-manifest.json`
- **CLAUDE.md integrity:** Public copy never references internal codenames (C4, E1, F3). Say "evolutionary tuner" not "CI-Gated Tuner"
- **Claim tiers:** Every BRD/TRD claim classified A/B/C/D. Modeled numbers labeled "Modeled". CI-measured numbers ("40-70×") stay in Benchmarks.

---

## Pre-Flight (before next session)

- [ ] E1 commit + push complete
- [ ] DeepSeek QA dispatched on E1 + E2 skeleton
- [ ] `ruff clean` on all changed files
- [ ] All tier2 + full test suite green

---

## Start Here

1. Read `neuralmind/merge_semantics.py` — understand `QualityWeightedMerger` skeleton
2. Read `neuralmind/contribution_scoring.py::EdgeQuality` — E2's scoring unit
3. Implement `EdgeQuality.decay_weight()` for conflict degradation
4. Implement `QualityWeightedMerger.merge_to_store()`
5. Wire into `team_memory.maybe_import_team_memory()`
6. Write tests, run full suite, DeepSeek QA
7. Update `WAVE4-SESSION-PROMPT.md` to v7.0 (E2 → DONE)

---

*Next session prompt v6.0. E1 COMPLETE. E2 — Quality-Weighted Merge next.*
