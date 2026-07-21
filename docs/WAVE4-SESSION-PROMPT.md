# Next Session Prompt — NeuralMind Wave 4 (E1+E2+E3+E4+F3+F4+G3 COMPLETE, G4 NEXT)

**Date:** 2026-07-23
**Autopilot:** v0.7.0 (running — systemd service live)
**NeuralMind:** v1.4.0 (G3 shipped + DeepSeek QA clean)
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
| G3 — Modularity clustering | `c7523d6` | ✅ 1582 tests green, ruff clean, DeepSeek QA: 0 CRITICAL, 3 WARNINGs patched, v1.4.0 released, public copy live |
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

## Conventions (Honest, KISS/DRY, No Overclaim)

- **Claim tiers:** Every BRD/TRD claim classified A/B/C/D.
- **Honest framing:** Document what's NOT done yet.
- **Private repo discipline:** Autopilot stays private.
- **No phone-home:** All operations local.
- **Fresh verification:** Run `pytest` before claiming done.
- **After 'approved'/'go':** work is done — don't re-summarize; move to next action.

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

## Versioning
- autopilot: v0.7.0 (running)
- neuralmind: v1.4.0 (G3) → v1.5.0 (G4)

---

## Skills to Load

1. `neuralmind-autopilot` — Wave 12 architecture + lessons
2. `autopilot-release` — release workflow
3. `deepseek-qa` — phase-gate QA dispatch
4. `tier2-dual-tier-license` — product-side validation patterns
5. `optional-heavy-dependency` — optional SDK integration pattern
6. `git-repo-cleanup` — pre-release hygiene checklist
7. `neuralmind-modularity` — Louvain clustering API + pitfalls (new, G3)
8. `neuralmind-graphgen` — community assignment + G3 integration pitfalls

---

## Release Status

- Code: merged to `main` (`c7523d6`)
- Public-facing: README.md, wiki Home, RELEASE_NOTES_v1.4.0.md all live with v1.4.0 content
- PyPI: publish triggered via CI on `main` push (will resolve when tag lands)
- Tag `v1.4.0`: remote rule violations blocking direct tag push — release-please flow needed
- DeepSeek QA: CLEAN (0 CRITICAL, 3 WARNINGs — all patched inline in `8e1a15f`)

---

*Next session prompt v13.0. E1+E2+E3+E4+F3+F4+G3 COMPLETE. G4 — Incremental Re-Extraction next.*
