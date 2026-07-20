# Next Session Prompt — NeuralMind Wave 4 (E1+E2+E3+E4+F3+F4+G3 COMPLETE, G4 NEXT)

**Date:** 2026-07-23
**Autopilot:** v0.7.0 (running — systemd service live)
**NeuralMind:** v1.7.0 (G3 shipped)
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
| G3 — Modularity clustering | `f49b535` | ✅ 1582 tests green, ruff clean |
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
| 10 | G3 — Modularity clustering | Graph precision | HIGH | ✅ DONE |
| 11 | G4 — Incremental re-extraction | Graph precision | HIGH | **NEXT** |

---

## G3 — Modularity Clustering (Complete)

**Files modified:**
- `neuralmind/modularity.py` — resolution param now applied in `_modularity_gain`; O(n·k) incremental community weight updates
- `neuralmind/graphgen.py` — `_assign_communities(b, existing_graph)` wires Louvain over per-file structural edges; carries over community IDs from existing_graph for incremental stability; falls back to per-file grouping on collapse
- `tests/test_modularity.py` — 11 tests (was 5, +6 new: resolution contrast, determinism, perf-bound)

**Result:** 1582 tests pass. Ruff clean. QA report at `docs/G3-QA-REPORT.md`.

**CLI commands:**
```
neuralmind build  # now uses Louvain modularity for community assignment
```

---

## G4 — Incremental Re-Extraction (Next)

### What It Is
Re-extract symbols from changed files + their dependents. Uses structural index's reverse edges (`callers`/`importers`). Skips full-tree reparse for large repos.

### Research Already Done
See `docs/research/f4-g3-research-backlog.md`. Key findings:
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
- neuralmind: v1.7.0 (G3) → v1.8.0 (G4)

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
| G4 — Incremental | **No** | Research done (`f4-g3-research-backlog.md`) |
| All Wave 4 research complete | — | — |

---

## Start Here

1. Read `neuralmind/graphgen.py` — understand `build_graph()` + `IncrementalExtractor` wiring
2. Read `neuralmind/incremental_extract.py` — understand `scan_files()` + `get_changed_with_dependents()`
3. Patch community ID stability bug (carry `comm_of_file` from existing graph)
4. Patch dangling edge prune (drop edges to non-existent nodes after rename)
5. Write tests, run full suite, DeepSeek QA
6. Update `WAVE4-SESSION-PROMPT.md` to v13.0 (G4 → DONE)

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

*Next session prompt v12.0. E1+E2+E3+E4+F3+F4+G3 COMPLETE. G4 — Incremental Re-Extraction next.*
