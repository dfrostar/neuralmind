# Next Session Prompt — NeuralMind Wave 4 (E1 NEXT)

**Date:** 2026-07-20
**Autopilot:** v0.8.0 (Wave 12 shipped — private, not published)
**NeuralMind:** v1.1.1
**Index:** rebuilt, fresh

---

## Recap: What Shipped

| Item | Commit | Status |
|------|--------|--------|
| C4 — CI-gated tuner promotion | `79deef8` | ✅ DONE |
| C4 — NaN-safe fitness clamp | `79deef8` | ✅ DeepSeek QA'd |
| D3 — Judge transcripts | `e232b15` | ✅ DONE |
| D4 — Per-language fixtures | verified | ✅ DONE |

---

## Wave 4 Sequence (remaining)

| # | Item | Bucket | Complexity | Status |
|---|------|--------|------------|--------|
| 1 | C4 — CI-gated tuner promotion | Self-improvement | MEDIUM | ✅ DONE |
| 2 | D3 — Populate judge transcripts | Quality harness | LOW | ✅ DONE |
| 3 | D4 — Per-language fixtures | Quality harness | MEDIUM | ✅ DONE |
| 4 | E1 — Contribution-quality scoring | Team memory | MEDIUM | **NEXT** |
| 5 | E2 — Merge semantics with decay-on-conflict | Team memory | HIGH | |
| 6 | E3 — Peer review gate | Team memory | LOW | |
| 7 | E4 — Staleness detection | Team memory | LOW | |
| 8 | F3 — Tool-use metrics pipeline | Daemon/MCP | MEDIUM | |
| 9 | F4 — Backpressure + circuit breakers | Daemon/MCP | MEDIUM | |
| 10 | G3 — Modularity clustering | Graph precision | HIGH | |
| 11 | G4 — Incremental re-extraction | Graph precision | HIGH | |

---

## E1 — Contribution-Quality Scoring (The Linchpin)

### What It Is
Score each contributor's team-memory edges by their measured value:
- Do their edges get reinforced by other team members?
- Do their edges survive decay (signal of lasting value)?
- Conflict rate — how often their edges get down-weighted in merges.

High contributors get higher initial weight in the `shared` namespace;
low contributors start at neutral and rely on their own reinforcement to persist.

### Why Now
E1 is the prerequisite for E2 (merge semantics), E3 (peer review), and E4 (staleness).
All three downstream features need a quality signal to weight against. Without E1,
E2 is just last-write-wins merge. E1 closes the E1.5 loop honestly.

### Architecture

```
ContributorEdges → Scorer → quality_score (0.0–1.0)
                                    │
                                    ▼
                     initial_weight = base * (0.5 + 0.5 * quality_score)
                                    │
                                    ▼
                     SynapseStore (shared namespace)
```

### Files to Read FIRST

| File | Why |
|------|-----|
| `neuralmind/team_memory.py` | publish_team_memory + maybe_import_team_memory — where scoring wires in |
| `neuralmind/entity_resolution.py` | norm_label + thresholds — E2 depends on this |
| `neuralmind/synapses.py` | SynapseStore API — how to query per-contributor edges + reinforcement |
| `neuralmind/ir.py` | export_synapse_bundle — bundle format (contributor metadata lives here) |
| `tests/test_team_memory.py` | existing tests — pass-through requirement |

### Implementation Plan

#### Step 1: Create `neuralmind/contribution_scoring.py`

```python
# neuralmind/contribution_scoring.py

class ContributionScorer:
    """Scores a contributor's edges by measured value to the team."""
    
    def __init__(self, store: SynapseStore):
        self.store = store
    
    def score_contributor(self, contributor_id: str) -> float:
        """Return quality score in [0.0, 1.0].
        
        Signals:
        - reinforcement_rate: fraction of edges reinforced by others
        - survival_rate: fraction of edges still above decay floor
        - conflict_rate: fraction of edges down-weighted in merges
        """
        ...
    
    def score_edge(self, edge: dict) -> float:
        """Score a single edge by its reinforcement history."""
        ...
```

#### Step 2: Wire into `team_memory.py`

- In `publish_team_memory()`: tag each edge with contributor provenance
- In `maybe_import_team_memory()`: apply scorer to set initial weight on imported edges
- Persist scores in synapse meta table (`contributor_scores`)

#### Step 3: Add CLI visibility

- `neuralmind team memory status` — show top contributors + scores
- `neuralmind team memory publish` — already exists, add scoring output

#### Step 4: Write tests

- `tests/test_contribution_scoring.py`
- test_scorer_returns_float_in_range
- test_high_reinforcement_scores_higher
- test_low_survival_scores_lower
- test_score_persisted_in_meta
- test_backward_compat_no_scorer

### E1 Acceptance

- [ ] ContributionScorer.score_contributor() returns float in [0.0, 1.0]
- [ ] High-reinforcement contributors score higher than low-reinforcement
- [ ] Scores persisted in synapse meta table
- [ ] Wired into team_memory.publish_team_memory()
- [ ] Backward compatible: no scorer = current behavior (score = 0.5 neutral)
- [ ] All existing team_memory tests pass
- [ ] ruff clean
- [ ] DeepSeek QA dispatched

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

- **Claim tiers:** Every BRD/TRD claim classified A/B/C/D.
- **Honest framing:** Document what's NOT done yet.
- **Private repo discipline:** Autopilot stays private.
- **No phone-home:** All operations local.
- **Fresh verification:** Run `pytest` before claiming done.
- **After 'approved'/'go':** work is done — don't re-summarize.

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

1. Read `neuralmind/team_memory.py` — understand publish_team_memory + bundle format
2. Read `neuralmind/synapses.py` — SynapseStore API for querying edges + reinforcement
3. Read `neuralmind/entity_resolution.py` — norm_label + thresholds (E2 prep)
4. Plan E1 design: ContributionScorer class + scoring function
5. Implement `neuralmind/contribution_scoring.py`
6. Wire into `team_memory.py`
7. Write tests, run full suite, DeepSeek QA

---

*Next session prompt v5.0. C4 + D3 + D4 COMPLETE. E1 — Contribution-Quality Scoring next.*
