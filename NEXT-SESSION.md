# NeuralMind + Autopilot — Next Session Prompt

> **START HERE.** Copy this entire document into a new Hermes session to continue NeuralMind + Autopilot work. All context is inline.

---

## CONTEXT (where we are)

### NeuralMind (`/home/dtfrost/neuralmind`)

**Version:** v0.53.0 (released), v0.54.0 (code-complete, untagged)
**Branch:** main
**Index:** 11,432 nodes (4,245 code + 3,083 document + 1,718 rationale), schema v2

**Waves shipped:**
- Wave 1 (D/B1/G1) — Quality harness, IR migration, dynamic imports
- Wave 2 (C1/A1/A2/B2/B3/G2) — Fitness, traces, entity resolution, sparse/reranker/scip
- Wave 3 (C3) — Population tuner (DeepSeek QA: 2 patches applied)
- Wave 4 (C4/G3/G4/E1-E4/F3/F4/D3/D4) — Team memory (DeepSeek QA: 3 patches applied)
- Wave 5 (T1/T2) — Tuner faithfulness + incremental extraction
- Wave 6 (A/B) — Metrics CLI + team memory integration test
- Wave 7 — Impact tool (blast radius naming)
- Tier 2 v1.0.0 — Team tier ($org/mo), governance, audit, seats, self-hosted
- Tier 2 v0.53.0 — Free tier auto-provisioning + upgrade path
- v0.54.0 — Doc-code coupling v2 (`describes` edges, 26 surgical links)

**Docs drafted:** WAVE6-BRD.md, WAVE6-TRD.md

**Documentation.site:** neuralmind.uk = GitHub Pages from `docs/` on main. No separate repo. Auto-rebuild on push.

**Memory stores (this profile):**
- neuralmind.uk = GitHub Pages, auto-rebuild
- CLAUDE.md checklist = 5 surfaces + SEO same PR
- Autopilot: code mature (55 tests), deployed as systemd timer (autopilot-update.timer, 15 min)

---

### Autopilot (`/home/dtfrost/neuralmind-autopilot`)

**Version:** v0.4.0
**Status:** Code-mature, deployed, not fully wired
**Tests:** 55 pass

**Module status:**
| Module | Status |
|--------|--------|
| signals.py (Page-Hinkley) | Clean |
| correlator.py (root cause) | CWD default warning |
| bandit.py (Thompson sampling) | Clean |
| experiment_runner.py (Welch's t-test) | Clean |
| promotion_engine.py (ship_callable) | Clean |
| engine.py (orchestrator) | Wired, untested live |
| self_play.py (adversarial) | Clean |
| war_room.py (Telegram) | Pause/resume wired, bot no-op |
| health_dashboard.py | Raw listing, no trends |

**Deploy status:**
- `autopilot-update.timer` loaded + active (systemd --user, 15 min)
- First tick ran ~15:00 UTC 2026-07-19
- Metrics feed: reads stale JSONL (NOT live benchmark)
- Telegram: stub (no creds configured)

**Honest gaps (from DeepSeek + self-review):**
1. Metrics feed reads `metrics/*.jsonl` not live `neuralmind benchmark`
2. `correlator.py` defaults `neuralmind_path=Path.cwd()` (wrong if not launched from NM dir)
3. `health_dashboard.py` has no trend analysis
4. `war_room.py` Telegram bot is unconfigured
5. No live integration test (`test_full_tick_loop` exists but is unit-level)
6. Connection leak in `experiment_runner.py` (no try/finally on `conn.close()` — verified present in code, but DeepSeek flags it as latent risk)

---

## BLOCKERS

### 1. Site update requires pricing confirmation

Site update drafted at `/home/dtfrost/neuralmind/references/site-update-v0530-draft.md`.

**Decision needed:** Is final pricing "per-org assurance, custom contracts, no published per-seat numbers"? Or do you want a published Team price on the site?

**Files to edit (same PR):**
- `docs/index.html` — banner + meta description + keywords
- `docs/about.html` — new v0.53.0 + v0.54.0 sections, demote v0.52.0, update JSON-LD
- `docs/sitemap.xml` — new URLs
- `pyproject.toml` — keywords
- `README.md` — banner bump, release-notes row, in-context updates
- `RELEASE_NOTES_v0.53.0.md` + `v0.54.0.md` — write canonical notes
- **DO NOT TOUCH** `CHANGELOG.md` (release-please owns it)

### 2. 29 modified files, 9 new files uncommitted

No git tag for the doc-code coupling feature (should be v0.54.0).

---

## WORKSTREAMS (priority order)

### A. Site push (blocked on pricing)

When pricing confirmed:
1. Apply edits from `references/site-update-v0530-draft.md`
2. Commit + push to main
3. GitHub Pages auto-rebuilds (~1-2 min)
4. Verify at https://docs.neuralmind.uk

### B. CLI E2E verification on rebuilt index

Verify these work against the clean 11K-node graph:
```
neuralmind build --force .
neuralmind query "How does the synapse layer learn?"
neuralmind benchmark . --json
neuralmind metrics --summary
neuralmind impact fitness --depth 3
neuralmind structural fitness.py --blast-radius
neuralmind doctor
```

Expected: 48.5x reduction, no errors, doctor "Doc-code alignment: 526 doc files"

### C. Autopilot: live metrics feed

**Problem:** `engine.run_tick()` reads stale JSONL from `metrics/`. Real signal is `neuralmind benchmark --json`.

**Work:**
1. Add `neuralmind benchmark --json` subprocess to `EngineOrchestrator.run_tick()`
2. Parse JSON output → feed to `SignalDetector.process_metrics()`
3. Verify synthetic drop fires signal within 1 tick
4. Add `test_full_tick_loop` with live benchmark

### D. Git commit + tag ritual

```
git add -A
git commit -m "feat(v0.54.0): doc-code coupling v2, free tier, site docs"
git tag v0.54.0
git push origin main
git push origin v0.54.0
```

Pre-tag gate: CI green (1,374+ tests), version triple-aligned, DeepSeek QA complete.

### E. Autopilot: remaining honest gaps

| Gap | Effort | Impact |
|-----|--------|--------|
| Metrics feed → live benchmark | 2h | Loop becomes real |
| correlator CWD default → explicit path | 30 min | Correctness |
| health_trend() with week-over-week deltas | 1h | Observability |
| Telegram bot wiring | 2h | Operator visibility |
| Connection leak fix (exp_runner) | 30 min | Stability |

---

## ACCEPTANCE GATES

**Before declaring v0.54.0 done:**
- [ ] Site push live at docs.neuralmind.uk (v0.53.0 + v0.54.0 sections visible)
- [ ] CLI E2E passes (all 6 commands above)
- [ ] Autopilot live metrics feed fires on synthetic drop
- [ ] 1,374+ tests CI green (--tb=no)
- [ ] Version triple-aligned (pyproject.toml 0.54.0, __init__.py 0.54.0, manifest 0.54.0, tag v0.54.0)
- [ ] CHANGELOG.md has v0.54.0 section (auto-written by release-please)

---

## REFERENCE FILES

- Site update draft: `/home/dtfrost/neuralmind/references/site-update-v0530-draft.md`
- Docs workflow: `/home/dtfrost/neuralmind/references/neuralmind-uk-publishing.md`
- WAVE6 docs: `docs/WAVE6-BRD.md`, `docs/WAVE6-TRD.md`
- Autopilot architecture: `/home/dtfrost/neuralmind-autopilot/ARCHITECTURE.md`
- Autopilot TRD: `/home/dtfrost/neuralmind-autopilot/docs/TRD.md`
- Current docs state: `docs/index.html`, `docs/about.html`, `docs/sitemap.xml`

---

## FIRST ACTION IN NEW SESSION

1. Read this file to load context
2. Ask user: "Pricing confirmed? (per-org only, or publish Team price?)"
3. If confirmed → execute Site Push (Workstream A)
4. Then run CLI E2E (Workstream B)
5. Then proceed to Autopilot live metrics (Workstream C)

---

*Handoff by Hermes. 2026-07-19. NeuralMind v0.53.0 → v0.54.0, Autopilot v0.4.0 deployed.*
