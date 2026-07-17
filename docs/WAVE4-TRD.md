# Wave 4 — Technical Requirements Document (TRD)

**Date:** 2026-07-17
**Approved by:** dfrostar (v2.0 plan, Wave 4 approved during execution)
**Source:** `docs/FUTURE-PROOFING-PLAN.md` §4,§5,§6,§9

---

## 1. Scope

Wave 4 implements 11 workstreams across the C/G/E/F/D buckets of the v2.0 future-proofing plan. It requires completion of Waves 1-3 (all shipped in v0.47.x).

This document specifies interfaces, shared contracts, and per-module requirements.

---

## 2. Shared Architecture Rules

| Rule | Rationale |
|------|-----------|
| Local-first | No cloud, no phone-home |
| Fail-open | A failure in any subsystem must never break query/build/search |
| Stdlib-only where it counts | The synapse layer, structural index, IR, and new graph/memory code are stdlib-only — they run without the embedding deps |
| IR is the contract (after B1) | New features consume `index_ir.json`, not `graph.json` |
| Public commands byte-compatible | `neuralmind query`, `search`, `build`, `benchmark`, `probe` output shape unchanged |
| Synapse meta-table keys | `self_improve:*` prefix reserved; document key collisions |
| Backpressure integration | New long-running operations (tuner, sleep, metrics) must check backpressure before mutating store |

---

## 3. Per-Module Requirements

### C4 (`neuralmind/ci_tuner.py`)

| Interface | Requirement |
|-----------|-------------|
| `CIGatedTuner(project_path)` | Wraps `PopulationTuner`; project_path optional |
| `run_ci_eval() → PromotionVerdict` | Runs tuner generation + promotion check |
| `promote(params) → bool` | Persists incumbent to synapse meta |
| `run_ci_gated_promotion(project_path, verbose) → dict` | CLI entry point |
| Fail-open | Returns VERDICT(promoted=False) on any error |

**Synapse meta keys:**
- `self_improve:tuner_incumbent_config` (existing)
- `self_improve:tuner_incumbent_fitness` (existing)
- `self_improve:tuner_promoted_at` (existing)
- `self_improve:ci_hysteresis` (new, tunable)

**Bounds:**
- `CI_MIN_FAITHFULNESS`: 0.0–1.0 (default 0.70)
- `CI_MIN_SESSION_HEALTH`: 0.0–1.0 (default 0.50)
- `CI_HYSTERESIS`: 0.01–0.50 (default 0.05)

---

### G3 (`neuralmind/modularity.py`)

| Interface | Requirement |
|-----------|-------------|
| `louvain_clustering(adj, resolution=1.0, max_iterations=10) → {node: community_id}` | Stdlib-only, deterministic output, recursive Phase 2 |
| `detect_structural_communities(graph, min_edge_weight=0.0) → {node_id: community_id}` | Consumes `graph['nodes']` + `graph['links']` |

**Algorithm properties:**
- ΔQ formula: `k_i,in / (2m) − Σ_tot * k_i / (4m²)` per Blondel et al. 2008
- Singleton-fallback for empty graphs
- Final labels are contiguous integers (deterministic mapping from arbitrary strings)

**Edge cases handled:**
- Empty graph → `{}`
- Single node → `{node: 0}`
- Disconnected graph → all nodes in community 0
- Self-loops → skipped in adjacency build

---

### G4 (`neuralmind/incremental_extract.py`)

| Interface | Requirement |
|-----------|-------------|
| `IncrementalExtractor(project_path)` | Loads/persists `.neuralmind/extraction_cache.json` |
| `scan_files(root, suffixes) → (added, modified, deleted)` | Three-list diff vs cache |
| `get_changed_with_dependents(root, suffixes, importer_index) → list[str]` | Adds transitive importers |
| `update_cache(file_paths, root)` | Persists fresh SHA-256 hashes |
| `remove_from_cache(file_paths)` | Removes deleted files |

**File cache format:**
```json
{"files": [{"path": "a.py", "mtime": 1234567890.0, "content_hash": "sha256...", "extracted_at": 1234567890.0}, ...], "saved_at": 1234567890.0}
```

**Race-condition handling:**
- Files that disappear between `stat()` and `read_bytes()` silently skip (fail-open)
- `update_cache` overwrites; concurrent appends to cache are safe because cache is per-project

---

### E1 (`neuralmind/contribution_scoring.py`)

| Interface | Requirement |
|-----------|-------------|
| `ContributionQualityScorer(quality_high=0.70, quality_low=0.30)` | Scoring with configurable thresholds |
| `score_edge(source, target, namespace, activation_count, created_at, last_activated, conflict_count, total_comparisons) → EdgeQuality` | Per-edge scoring |
| `score_bundle(bundle) → list[EdgeQuality]` | Batch scoring |
| `classify_bundle(bundle) → (promote, neutral, decay)` | Three-bucket classification |

**Scoring formula:**
```
reinforcement = min(1.0, log1p(activations) / log1p(30))
recency       = exp(−0.693 * days_since_last / 30)
conflict_rate = conflict_count / max(1, total_comparisons)
combined      = 0.40 × reinforcement + 0.35 × recency − 0.25 × conflict_rate
score         = clamp(combined, 0.0, 1.0)
```

**Promotion rules:**
- `score ≥ 0.70` → `should_promote=True`
- `score < 0.30` → `should_decay=True`

---

### E2 (`neuralmind/merge_semantics.py`)

| Interface | Requirement |
|-----------|-------------|
| `QualityWeightedMerger(scorer)` | Takes a scorer or uses default |
| `resolve_conflict(edge_a, edge_b) → MergeConflict` | Quality-weighted winner selection |
| `merge_bundles(bundle_a, bundle_b, target_namespace) → (merged, conflicts)` | Full-bundle merge |

**Merge semantics:**
- Overlapping (source, target) pairs trigger `resolve_conflict`
- Higher `edge.score` wins
- Exact tie → higher `activation_count` wins
- Non-overlapping edges pass through
- Fail-open: scoring failure for one edge → that edge stays separate

**Limitation documented:** Currently O(n+m) with dict-based overlap detection; fine for bundles under 50K edges.

---

### E3 (`neuralmind/peer_review.py`)

| Interface | Requirement |
|-----------|-------------|
| `PeerReviewGate(auto_promote=0.75, reject=0.15)` | Configurable thresholds |
| `decide(edge) → ReviewDecision` | Classify single edge |
| `gate_bundle(bundle) → (auto_promoted, review_required, rejected)` | Full-bundle gating |

**Decision rules:**
- `score ≥ auto_promote` → `auto_promote`
- `score < reject` → `reject`
- Otherwise → `review_required` with reviewer_hint listing low axes

---

### E4 (`neuralmind/team_staleness.py`)

| Interface | Requirement |
|-----------|-------------|
| `TeamStalenessDetector(stale_days_shared=30, stale_days_branch=14, fast_decay=5.0)` | Namespace-aware thresholds |
| `is_stale(last_activated_ts, namespace)` | Per-namespace staleness check |
| `detect_stale_in_store(store, namespace) → list[StaleEdge]` | Query synapse store |
| `mark_fast_decay(store, stale_edges) → int` | Apply accelerated decay |
| `run_staleness_pass(store, namespace) → (count, stale_edges)` | Full pass |

**Thresholds applied:**
- `shared` namespace → 30 days
- `branch:*` namespaces → 14 days
- `personal` / other → 60 days

**Fast decay formula:** `weight × 2^(−fast_decay)` ≈ `weight × 0.03125` for `fast_decay=5`

**Transactional:** Multiple edge updates run in a single BEGIN/COMMIT.

---

### F3 (`neuralmind/metrics_pipeline.py`)

| Interface | Requirement |
|-----------|-------------|
| `MetricsCollector(project_path, retention_days=30, max_bytes=10MB)` | Per-project collection |
| `log_query_metrics(session_id, query, latency_ms, retrieval_reuse_rate, tool_calls, tool_successes, tokens_used, synapses_activated)` | Per-query event |
| `log_build_metrics(duration_s, files_processed, synapse_edges, graph_edges)` | Per-build event |
| `rotate() → int` | Purge old files + truncate oversized |
| `summarize(days=7, event_type=None) → dict` | Aggregate stats |

**File layout:** `<project>/.neuralmind/metrics/metrics_<YYYY-MM-DD>.jsonl`

**Retention:** Files older than retention_days deleted; oversized files truncated to 1000 most recent lines.

**Fail-open:** Failed writes silently dropped; metrics must never break query path.

---

### F4 (`neuralmind/backpressure.py`)

| Interface | Requirement |
|-----------|-------------|
| `CircuitBreaker(name, failure_threshold=3, recovery_timeout=30.0)` | State machine |
| `cb.record_success() / cb.record_failure()` | State transitions |
| `cb.allow_request() → bool` | Fast-path check |
| `cb.state → CircuitState` | Cached with OPEN → HALF_OPEN timeout check |
| `ProjectBackpressure.for_project(project_path, max_concurrent=2)` | Singleton-per-project |
| `bp.acquire(timeout=0.0) → bool` | Non-blocking (fail-fast) or blocking with timeout |
| `bp.release()` | Return slot |
| `ProjectLock(project_path, backpressure)` | Combined lock + backpressure |

**Circuit Breaker state machine:**
| Current | Condition | Next |
|---------|-----------|------|
| CLOSED | consecutive_failures ≥ failure_threshold | OPEN |
| OPEN | recovery_timeout elapsed | HALF_OPEN |
| HALF_OPEN | next request succeeds | CLOSED |
| HALF_OPEN | next request fails | OPEN |

**Thread safety:** All state mutations under `_lock`; `state` property lazily transitions OPEN→HALF_OPEN.

---

### D3 (`neuralmind/judge_transcripts.py`)

| Interface | Requirement |
|-----------|-------------|
| `populate_judge_transcripts() → dict[str, Path]` | Write fixture files |
| `load_judge_transcripts() → dict[str, dict]` | Load all + manifest |

**Output location:** `bench/public/judge/`

**Transcript format:**
```json
{"query": "...", "reference_answer": "...", "source_files": ["..."], "category": "architecture"}
```

---

### D4 (Languages registered in `evals/quality/runner.py`)

New SUITES entries registered:
- `csharp` → `tests/fixtures/sample_project_csharp`
- `ruby` → `tests/fixtures/sample_project_ruby`
- `php` → `tests/fixtures/sample_project_php`

Golden query files committed at `tests/fixtures/benchmark_queries_{csharp,ruby,php}.json`.

---

## 4. Key Dependencies Between Workstreams

```
E1 (scoring) ──────────────┐
E2 (merge, uses E1) ───────┤
E3 (review, uses E1) ──────┤→ Team memory flywheel
E4 (staleness, uses A4) ───┘

G3 (modularity) ───────────→ G4 (incremental uses modularity)

C4 (CI-gated, uses C3) ───→ F3 (metrics feeds C4 fitness)

F4 (backpressure) ─────────→ All concurrent operations
```

## 5. Key Risks & Mitigations

1. **`update_learned_half_life` in learned_decay.py**: existing code has a bug (SQL parameter count mismatch) — Wave 4 modules don't call it, so unaffected.
2. **`detect_stale_in_store` uses raw SQL**: matches existing patterns in `DaemonSleep` and `SynapseStore`.
3. **Phase 2 Louvain simplified**: single aggregation pass; adequate for v1, documented limitation.
4. **Bund merge max 50K edges**; `importer_index` in G4 can be large but acceptable for typical repos (<100K files).

---

Signed-off-by: Hermes, from the v2.0 plan (TRD)
