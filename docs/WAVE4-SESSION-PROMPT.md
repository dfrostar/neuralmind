# Next Session Prompt — NeuralMind Wave 4 (E1+E2+E3+E4+F3 COMPLETE, F4 NEXT)

**Date:** 2026-07-23
**Autopilot:** v0.8.0 (Wave 12 shipped — private, not published)
**NeuralMind:** v1.5.0 (F3 shipped)
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
| E4 — Staleness detection | tests green | ✅ DeepSeek QA'd |
| F3 — Tool-use metrics pipeline | tests green | ✅ DeepSeek QA'd |
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
| 9 | F4 — Backpressure + circuit breakers | Daemon/MCP | MEDIUM | **NEXT** |
| 10 | G3 — Modularity clustering | Graph precision | HIGH | |
| 11 | G4 — Incremental re-extraction | Graph precision | HIGH | |

---

## F3 — Tool-Use Metrics Pipeline (Complete)

**Files modified:**
- `neuralmind/metrics_pipeline.py` — `MetricsCollector` captures per-tool-call duration, success rate, token cost
- `neuralmind/daemon_client.py` — tool-call hooks wired into dispatch path
- `neuralmind/self_improve.py` — metrics feed into autopilot tuning loop
- `neuralmind/cli.py` — `neuralmind metrics show` subcommand
- `tests/test_f3_metrics.py` — 8 tests (capture, aggregation, degradation detection)

**Result:** All 44 daemon/metrics tests pass. Ruff clean. DeepSeek QA'd.

**CLI commands:**
```
neuralmind metrics show                  # Show per-tool metrics summary
neuralmind metrics show --json           # JSON output
neuralmind metrics show --days 7         # Last 7 days
```

---

## F4 — Backpressure + Circuit Breakers (Next)

### What It Is
Circuit breaker pattern for daemon/MCP tool calls — prevent cascade failures when a tool degrades. Three-state machine (CLOSED → OPEN → HALF_OPEN) with env-configurable thresholds.

### Why Now
F3 metrics provide the signal; F4 provides the safety. Without circuit breakers, a degrading tool wastes tokens and slows the agent loop. F4 closes the degradation-response loop honestly.

### Research Already Done
See `docs/research/f4-g3-research-backlog.md`. Key findings:
- MCP Python SDK has NO built-in concurrency control (GitHub issue #1698 closed as not planned)
- Must implement at app level with `asyncio.Semaphore`
- Existing `backpressure.py` matches Resilience4j/Hystrix canonical patterns
- Recommended: per-session tool-level circuit breakers + global concurrency cap

### Architecture (speculative, confirm before building)

```
Tool Call → CircuitBreaker.check() → [CLOSED: pass through]
                                    → [OPEN: reject fast]
                                    → [HALF_OPEN: trial call]
                                    ↓
                              MetricsCollector (F3)
                                    │
                                    ├── Trip breaker on N consecutive failures
                                    ├── Reset on success
                                    └── Alert operator via `neuralmind metrics show`
```

### Files to Read FIRST
| File | Why |
|------|-----|
| `neuralmind/backpressure.py` | Existing circuit breaker — what exists vs what F4 adds |
| `neuralmind/mcp_server.py` | Tool handler wrapping point |
| `neuralmind/daemon_client.py` | Per-session failure tracking |
| `tests/test_backpressure.py` | Existing tests — pass-through requirement |

### F4 Acceptance
- [ ] `asyncio.Semaphore` wrapper on tool handlers
- [ ] Per-session circuit breakers trip on N consecutive failures
- [ ] HALF_OPEN recovery after cooldown
- [ ] Env-configurable thresholds (failure count, cooldown, concurrency cap)
- [ ] All existing backpressure tests pass
- [ ] ruff clean
- [ ] DeepSeek QA dispatched

---

## Versioning

- autopilot: v0.8.0 → v0.9.0 (Wave 4 all features)
- neuralmind: v1.5.0 (F3) → v1.6.0 (F4)

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
| F4 — Backpressure | **No** | Research done (`f4-g3-research-backlog.md`) |
| G3 — Modularity | **Yes** | Louvain variants, resolution parameter — algorithm research |
| G4 — Incremental | **Maybe** | File-level re-extraction strategies — light research |

---

## Start Here

1. Read `neuralmind/backpressure.py` — understand existing circuit breaker
2. Read `neuralmind/mcp_server.py` — identify tool handler wrapping points
3. Plan F4 design: `asyncio.Semaphore` + per-session breakers + HALF_OPEN recovery
4. Implement F4
5. Wire into daemon_client to track per-session failures
6. Write tests, run full suite, DeepSeek QA
7. Update `WAVE4-SESSION-PROMPT.md` to v11.0 (F4 → DONE)

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

*Next session prompt v10.0. E1+E2+E3+E4+F3 COMPLETE. F4 — Backpressure + Circuit Breakers next.*
