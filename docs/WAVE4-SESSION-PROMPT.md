# Next Session Prompt — NeuralMind Wave 4 (E1+E2+E3+E4+F3+F4 COMPLETE, G3 NEXT)

**Date:** 2026-07-23
**Autopilot:** v0.7.0 (running — systemd service live)
**NeuralMind:** v1.6.0 (F4 shipped)
**Index:** rebuilt, fresh — 11,530 nodes / 593 communities

---

## Recap: What Shipped

| Item | Commit | Status |
|------|--------|--------|
| C4 — CI-gated tuner promotion | `79deef8` | ✅ DeepSeek QA'd |
| D3 — Judge transcripts | `e232b15` | ✅ DeepSeek QA'd |
| D4 — Per-language fixtures | verified | ✅ DeepSeek QA'd |
| E1 — Contribution-quality scoring | `2969e38`, `c7d5a86` | ✅ DeepSeek QA'd, tests green |
| E2 — Quality-weighted merge semantics | `43d4ef4` | ✅ DeepSeek QA'd, tests green |
| E3 — Peer review gate | `485687f` | ✅ DeepSeek QA'd, tests green |
| E4 — Staleness detection | `3fe5a61` | ✅ DeepSeek QA'd |
| F3 — Tool-use metrics pipeline | — | ✅ DeepSeek QA'd |
| F4 — Backpressure + circuit breakers | — | ✅ DeepSeek QA'd |
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
| 6 | E3 — Peer review gate | Team memory | LOW | ✅ DONE |
| 7 | E4 — Staleness detection | Team memory | LOW | ✅ DONE |
| 8 | F3 — Tool-use metrics pipeline | Daemon/MCP | MEDIUM | ✅ DONE |
| 9 | F4 — Backpressure + circuit breakers | Daemon/MCP | MEDIUM | ✅ DONE |
| 10 | G3 — Modularity clustering | Graph precision | HIGH | **NEXT** |
| 11 | G4 — Incremental re-extraction | Graph precision | HIGH | |

---

## F4 — Backpressure + Circuit Breakers (Complete)

**Files modified:**
- `neuralmind/backpressure.py` — three-state machine (CLOSED → OPEN → HALF_OPEN) with env-configurable thresholds
- `neuralmind/mcp_server.py` — `asyncio.Semaphore` wrapper on tool handlers
- `neuralmind/daemon_client.py` — per-session failure tracking
- `tests/test_f4_backpressure.py` — 7 tests (trip, recovery, concurrency cap, env config)

**Result:** All 51 daemon/backpressure tests pass. Ruff clean. DeepSeek QA'd.

**CLI commands:**
```
neuralmind metrics show --breakers    # Show circuit breaker states
neuralmind metrics show --concurrency  # Show current concurrency usage
```

---

## G3 — Modularity Clustering (Next)

### What It Is
Replace balanced-per-file clustering with Louvain/Leiden modularity optimization over structural edges. Communities match architectural boundaries (auth module, data layer) instead of file-level groupings.

### Why Now
G3 provides the community-quality signal for G4 (incremental re-extraction). Without accurate modularity, G4 re-extracts the wrong file sets. G3 is the last remaining graph-precision workstream.

### Research Already Done
See `docs/research/f4-g3-research-backlog.md`. Key findings:
- **BUG ALREADY FOUND:** `modularity.py` accepts `resolution` parameter but ignores it in `_modularity_gain` — always runs at γ=1.0 regardless of caller input
- **PERF ISSUE:** O(n²) nested loop in Phase 1 — should be O(n·k) with incremental community weight updates
- No stdlib-only Louvain implementation exists — ours is original
- Leiden provably better (connectivity guarantees) but requires `python-igraph` C dep
- Current pure-Python Louvain is only stdlib option

### Files to Read FIRST
| File | Why |
|------|-----|
| `neuralmind/modularity.py` | Existing implementation — fix the resolution bug, optimize Phase 1 |
| `neuralmind/graphgen.py` | `build_graph()` calls `_assign_communities()` — wiring point |
| `neuralmind/structural.py` | Structural edges that feed Louvain |
| `tests/test_modularity.py` | Existing tests — pass-through requirement |

### G3 Acceptance
- [ ] `resolution` parameter actually affects `_modularity_gain` result
- [ ] Phase 1 runs in O(n·k) or better (not O(n²))
- [ ] Deterministic output (seed or sorted tiebreaking)
- [ ] Communities validated against known architecture (auth, data layer)
- [ ] All existing modularity tests pass
- [ ] ruff clean
- [ ] DeepSeek QA dispatched

---

## G4 — Incremental Re-Extraction (After G3)

### What It Is
Re-extract symbols from changed files + their dependents. Uses structural index's reverse edges (`callers`/`importers`). Skips full-tree reparse for large repos.

### Research Already Done
Same `docs/research/f4-g3-research-backlog.md`:
- **Community ID stability bug:** `build_graph()` unconditionally renumbers ALL communities on every call. Docstring claims unchanged files keep IDs — false. Patch: carry `comm_of_file` from existing graph.
- **Dangling edge prune missing:** Incremental path preserves edges to non-existent nodes after a rename.

### Files to Read FIRST
| File | Why |
|------|-----|
| `neuralmind/graphgen.py` | `build_graph()` + `IncrementalExtractor` wiring |
| `neuralmind/incremental_extract.py` | `scan_files()` + `get_changed_with_dependents()` |
| `tests/test_incremental_extract.py` | Existing tests — pass-through requirement |

### G4 Acceptance
- [ ] Re-extraction scopes to changed files + dependents only
- [ ] Community IDs stable across incremental builds
- [ ] Dangling edges pruned when target node removed
- [ ] 10K-line repo, 1 change → <10% of full-build wall-clock
- [ ] All existing incremental tests pass
- [ ] ruff clean
- [ ] DeepSeek QA dispatched

---

## Versioning

- autopilot: v0.7.0 (running)
- neuralmind: v1.6.0 (F4) → v1.7.0 (G3/G4)

---

## Parallelization Strategy (validated)

### What works
- DeepSeek QA sweeps: dispatch production + docs in parallel (2 subagents, ~15 min each)
- Test-writing in main thread: write tests while code is fresh
- Parallel doc audit + code prep: dispatch doc review while reading skeleton
- max_concurrent_children=3: sufficient for our workflow

### When to dispatch vs build direct
| Build directly when | Dispatch subagent when |
|---------------------|----------------------|
| <200 lines, known seams | 5+ modules at once |
| Full context in window | Context not in main window |
| Same-file edits | Cross-file integration review |
| TDD test-writing (fast iteration) | DeepSeek QA (parallelize sweeps) |

---

## Research Required?

| Feature | Research needed? | Why |
|---------|------------------|-----|
| G3 — Modularity | **No** | Research done (`f4-g3-research-backlog.md`) |
| G4 — Incremental | **No** | Research done (same doc) |
| All Wave 4 research complete | — | — |

---

## Start Here

1. Read `neuralmind/modularity.py` — understand current implementation + resolution bug
2. Read `neuralmind/graphgen.py` — understand `_assign_communities()` wiring
3. Fix `resolution` parameter bug in `_modularity_gain`
4. Optimize Phase 1 from O(n²) to O(n·k)
5. Write tests, run full suite, DeepSeek QA
6. Move to G4 (incremental re-extraction)
7. Update `WAVE4-SESSION-PROMPT.md` to v12.0 (G3+G4 → DONE)

---

## Conventions (Honest, KISS/DRY, No Overclaim)

- **Claim tiers:** Every BRD/TRD claim classified A/B/C/D.
- **Honest framing:** Document what's NOT done yet.
- **Private repo discipline:** Autopilot stays private.
- **No phone-home:** All operations local.
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

*Next session prompt v11.0. E1+E2+E3+E4+F3+F4 COMPLETE. G3 — Modularity Clustering next.*
