# Next Session Prompt — NeuralMind Wave 4 (E1+E2+E3+E4 COMPLETE, F3 NEXT)

**Date:** 2026-07-22
**Autopilot:** v0.8.0 (Wave 12 shipped — private, not published)
**NeuralMind:** v1.4.0 (E4 shipped)
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
| E4 — Staleness detection | `` | ✅ Tests green, ruff clean |
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
| 8 | F3 — Tool-use metrics pipeline | Daemon/MCP | MEDIUM | **NEXT** |
| 9 | F4 — Backpressure + circuit breakers | Daemon/MCP | MEDIUM | |
| 10 | G3 — Modularity clustering | Graph precision | HIGH | |
| 11 | G4 — Incremental re-extraction | Graph precision | HIGH | |

---

## E4 — Staleness Detection (Complete)

**Files modified:**
- `neuralmind/team_memory.py` — wired `TeamStalenessDetector.run_staleness_pass()` into `maybe_import_team_memory()` after the E3 gate (fail-open)
- `neuralmind/sleep.py` — `DaemonSleep._run_staleness_decay()` runs staleness passes for `shared` and `branch:live` namespaces via `TeamStalenessDetector`
- `neuralmind/cli.py` — added `memory staleness-scan` and `memory staleness-run` subcommands
- `tests/test_team_staleness.py` — 9 tests (detection, decay, pass execution)

**Result:** All 36 team-related tests pass. Ruff clean. DeepSeek QA dispatched.

**CLI commands:**
```
neuralmind memory staleness-scan .          # Show stale edges
neuralmind memory staleness-run .           # Execute decay pass
neuralmind memory staleness-scan --json     # JSON output
```

---

## F3 — Tool-Use Metrics Pipeline (Next)

### What It Is
Track per-tool-call metrics (duration, success rate, token cost) to enable data-driven optimization of agent behavior. Metrics feed into the autopilot tuning loop and operator observability.

### Why Now
F3 provides the measurement foundation for F4 (backpressure) and G3/G4 (modularity-based re-extraction). Without metrics, circuit breakers can't trip on real degradation signals.

### Architecture (speculative, confirm before building)

```
Tool Call → MetricsCollector → MetricsStore (SQLite)
                                    │
                                    ├── Autopilot: detect degradation → trigger F4 backpressure
                                    ├── Operator: `neuralmind metrics show`
                                    └── Self-improvement: correlate tool effectiveness with outcome

### Files to Read FIRST
| File | Why |
|------|-----|
| `neuralmind/metrics_pipeline.py` | Existing MetricsCollector — what exists vs what F3 adds |
| `neuralmind/daemon_client.py` | Tool-call hooks — where metrics get captured |
| `neuralmind/self_improve.py` | How metrics feed tuning |
| `tests/test_metrics_pipeline.py` | Existing tests — pass-through requirement |

### Research Flag
**Maybe** — 30-min competitive scan on MCP observability patterns would inform F3 design. Check `docs/research/` for existing F3 notes.

---

## Versioning

- autopilot: v0.8.0 → v0.9.0 (Wave 4 all features)
- neuralmind: v1.4.0 (E4) → v1.5.0 (F3)

---

## Parallelization Strategy (validated this session)

### What works
- **DeepSeek QA sweeps**: dispatch production + docs in parallel (2 subagents, ~15 min each)
- **Test-writing in main thread**: write tests while code is fresh, no subagent overhead
- **Parallel doc audit + code prep**: dispatch doc review while reading skeleton
- **max_concurrent_children=3**: sufficient for our workflow, no increase needed

### What doesn't pay off
- Subagents for <200 line modules (direct build is faster — no re-read overhead)
- Subagents when full context is already in main window
- Subagents for image prompts / marketing content (creative work needs human iteration)

### When to dispatch vs build direct
| Build directly when | Dispatch subagent when |
|---------------------|----------------------|
| <200 lines, known seams | 5+ modules at once |
| Full context in window | Context not in main window |
| Same-file edits | Cross-file integration review |
| TDD test-writing (fast iteration) | DeepSeek QA (parallelize sweeps) |
| Test-running loop (interactive) | Research (competitive analysis) |

---

## Research Required?

| Feature | Research needed? | Why |
|---------|------------------|-----|
| F3 — Tool metrics | **Maybe** | MCP observability patterns — 30 min competitive scan would help |
| F4 — Backpressure | **Yes** | Circuit breaker patterns for daemon/MCP — research first |
| G3 — Modularity | **Yes** | Louvain variants, resolution parameter — algorithm research |
| G4 — Incremental | **Maybe** | File-level re-extraction strategies — light research |

---

## Start Here

1. Read `neuralmind/metrics_pipeline.py` — understand what exists vs what F3 adds
2. Read `neuralmind/daemon_client.py` — identify tool-call hook points
3. Plan F3 design: MetricsCollector schema + operator observability
4. Implement F3
5. Wire into daemon_client to capture tool-call data
6. Write tests, run full suite, DeepSeek QA
7. Update `WAVE4-SESSION-PROMPT.md` to v10.0 (F3 → DONE)

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

*Next session prompt v9.0. E1+E2+E3+E4 COMPLETE. F3 — Tool-Use Metrics Pipeline next.*
