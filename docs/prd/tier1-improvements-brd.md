# BRD: Tier 1 Synapse & Retrieval Improvements

**Status:** Approved for build · **Owner:** dfrostar · **Created:** 2026-07-17
**Source:** `polymarket-research/neuralmind-brutal-analysis.md` + `neuralmind-v0.46-feedback-plan.md`
**Target:** v0.46.0 · **Branch:** `feature/tier1-structural-decay-migration`

---

## 1. Problem

The brutal analysis (verified on polymarket, 1779 nodes / 2240 edges) found:

| Finding | Impact |
|---------|--------|
| Synapse layer has 21 edges, all weight=0.15, all from one session | "Learned cognitive map" is hollow — marketing oversells 2-3× |
| Structural edges exist in graph.json (339 calls, 12 inherits, 253 imports) but are never persisted | Recalls "what calls this?" only via in-memory index that vanishes on rebuild |
| Synapse decay is tick-based (multiplicative per-session), not time-based | Files edited daily 6 months ago carry the same weight as yesterday |
| No version stamp in `ir_meta.json` | Upgrading NeuralMind → silent 44s reindex on first query |

## 2. Business requirements

| ID | Requirement | Success criterion |
|----|-------------|-------------------|
| BR1 | Persist structural edges (calls/imports/inherits) to a `structural_edges` synapse table on build | Table is populated on `neuralmind build`; survives process restart |
| BR2 | ~~Retrieval uses structural edges as a prior~~ | **Deferred** — table persisted in Tier 1 for durability and standalone query surface; retrieval integration deferred to Tier 2+ (the in-memory `StructuralIndex` already drives L3 retrieval via `_apply_structural_expansion()` when `NEURALMIND_STRUCTURAL_RECALL=1`) |
| BR3 | Synapse weights decay by wall-clock half-life, not per-session tick | A 60-day-old edge has half the weight of a 1-day-old edge |
| BR4 | Version mismatch warning on `build`/`query` | User sees "indexed with v0.41, v0.45 needs reindex" instead of 44s silence |
| BR5 | Zero regression on 60× benchmark and all existing tests | Benchmark ≥60×, all 214 relevant tests green |

## 3. Scope

### In scope (Tier 1)
- `structural_edges` table in `neuralmind/synapses.py`
- Persistence logic in `neuralmind/core.py` build()
- Exponential half-life decay in `synapses.py`
- `neuralmind_version` stamp in `ir_meta.json`
- Version mismatch warning in `cli.py`

### Out of scope (Tier 2+)
- BR2 (Retrieval uses structural edges as a prior) — retrieval integration deferred; table persisted for durability
- Skip vendor files in watcher
- Single default backend migration
- README honest-first rewrite

## 4. Approach

### 4.1 Structural edges table

Add a directed `structural_edges` table to `synapses.db`. On `neuralmind build`, extract calls/imports/inherits from `embedder.edges` (already loaded). Store with caller→callee direction and edge type. Unlike the in-memory `StructuralIndex`, this table persists across sessions.

**Retrieval note:** The existing in-memory `StructuralIndex` (built from the same edges) already drives L3 retrieval via `_apply_structural_expansion()` when `NEURALMIND_STRUCTURAL_RECALL=1`. The `structural_edges` table provides durability and a standalone query surface for CLI/MCP tools — it does not replace the in-memory index for retrieval.

### 4.2 Half-life decay

Replace the fixed `DECAY_RATE * weight` tick with `weight * exp(-λ * age_days)` where `λ = ln(2) / half_life_days` and `age_days` is derived from the existing `last_activated` SQL column. This uses SQLite's native `EXP()` function for batch efficiency. LTP floor and per-namespace policies are preserved.

A pure-Python `decay_weight()` helper is exposed for testing and callers that need single-edge decay math.

### 4.3 Migration check

In `core.py._materialize_ir()`, add `neuralmind_version` to the metadata summary (which is already written to `ir_meta.json`). In `cli.py cmd_build()` and `cmd_query()`, read `ir_meta.json` and warn on version mismatch vs the running `__version__`.

## 5. Test plan

| Test | File | What it verifies |
|------|------|-----------------|
| `test_persist_basic` | `tests/test_tier1.py` | Table populated after `persist_structural_edges()` |
| `test_persist_idempotent` | `tests/test_tier1.py` | Re-upsert increments call_count, not rows |
| `test_persist_skip_unknown_relations` | `tests/test_tier1.py` | Unknown relations dropped |
| `test_persist_survives_reopen` | `tests/test_tier1.py` | Data persists across store reopen |
| `test_decay_weight_half_life_math` | `tests/test_tier1.py` | `decay_weight()` returns correct decayed values |
| `test_time_decay_reduces_old_edges` | `tests/test_tier1.py` | Edges decay by wall-clock age, not call count |
| `test_time_decay_ltp_floor_preserved` | `tests/test_tier1.py` | LTP edges floor at LTP_FLOOR after time decay |
| `test_time_decay_prunes_weak_old_edges` | `tests/test_tier1.py` | Old weak edges pruned |
| `test_time_decay_fresh_edges_unchanged` | `tests/test_tier1.py` | Fresh edges unaffected by decay tick |
| `test_migration_warning_fires_on_version_mismatch` | `tests/test_tier1.py` | CLI warns when `ir_meta.json` version ≠ running version |
| `test_no_warning_when_versions_match` | `tests/test_tier1.py` | No warning on matching versions |
| `test_no_warning_without_ir_meta` | `tests/test_tier1.py` | No warning when ir_meta.json absent |

## 6. Risks

| Risk | Mitigation |
|------|-----------|
| Schema bump breaks existing DBs | New table is purely additive (`CREATE TABLE IF NOT EXISTS`) — no migration needed |
| SQLite `EXP()` not available on all platforms | Available in every SQLite build since 3.35 (2021); verified on this system |
| Slow build on large graphs | Structural edges already extracted by graphify; we just persist what's loaded |
| Time-decay feels wrong if user is inactive for months | Half-life is 30 days; after 90 days edges are ~12% — still recoverable on next activation |
