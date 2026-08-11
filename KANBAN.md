# NeuralMind — Kanban Board (v3.1.3+)

**Last updated:** 2026-08-11
**Repo:** `neuralmind-fresh` (dfrostar/neuralmind)
**Version:** 3.1.3+

---

## ✅ COMPLETE: P0 Fixes (2026-08-09)

| # | Issue | Fix | Commit |
|---|-------|-----|--------|
| 1 | Role-gated MCP tools | Added analytics tools to builder role | `b113b24` |
| 2 | No auto-rebuild | Post-build hint → `init-hook` / `watch` | `aded3fd` |
| 4 | No incremental build | Regenerate graph on every build (graphgen reuses by hash) | `986db53` |

## ✅ COMPLETE: P1 Fixes (2026-08-09)

| # | Issue | Fix | Commit |
|---|-------|-----|--------|
| 3 | No `.neuralmindignore` | `.gitignore`-style exclusion in `_iter_files()` | `594dcd0` |
| 8 | Markdown bloat | Same fix as #3 | `594dcd0` |

## ✅ COMPLETE: Gap Closure (2026-08-09)

| ID | Task | Commit |
|----|------|--------|
| G-03 | `SynapseStore.penalize()` | `d5b9699` |
| G-04 | `feedback good/bad` CLI | `d5b9699` |
| G-05 | `status` dashboard | `d5b9699` |

## ✅ COMPLETE: P2 Fixes (2026-08-09)

| # | Issue | Fix | Commit |
|---|-------|-----|--------|
| 5 | Unknown edge relations | Added `describes` to EDGE_RELATIONS | `c2a420f` |
| 6 | No audit trail query | Added `audit recent` subcommand | `a91ecd2` |
| 7 | SOC2 compliance | Added SOC2 regex pattern | `05c8a24` |
| 9 | Query --type filter | Added `--type code/docs/auto` flag | `efead21` |
| 10 | Cross-project query | Added `--projects` flag | `ff90512` |

## ✅ COMPLETE: P3 Fixes (2026-08-09)

| # | Issue | Fix | Commit |
|---|-------|-----|--------|
| 11 | Synapse pruning | Added `synapse prune/stats` commands | `ce58ce7` |
| 12 | Health check | Added `health` CLI + MCP tool | `d1b3fdb` |

## ✅ COMPLETE: Code/Document Scoring (2026-08-11)

| ID | Task | Status | Commit |
|----|------|--------|--------|
| CD-01 | Create TRD | ✅ | `neuralmind-autopilot/docs/specs/CODE-DOC-SCORING-TRD.md` |
| CD-02 | Query intent detection | ✅ | `04ed8be` |
| CD-03 | Type-aware boosting | ✅ | `04ed8be` |
| CD-04 | CLI --type flag integration | ✅ | `efead21` + fix |

## ✅ COMPLETE: QA Fixes (2026-08-11)

| ID | Severity | Issue | Fix |
|----|----------|-------|-----|
| C1 | CRITICAL | `penalize()` destroys LTP edges | Added LTP guard to DELETE |
| C2 | CRITICAL | `prune_stale()` wipes LTP edges | Added LTP guard to DELETE |
| C3 | CRITICAL | `neuralmind_health` MCP tool denied by RBAC | Added to `builder` + `reader` |
| H1 | HIGH | `--type` filter no-ops via daemon path | Fall back to direct mode when type set |
| H2 | HIGH | `--type` filter doesn't filter context | Pass `query_type` to context selector |
| W1 | WARNING | `penalize()` bumps `last_activated` | Removed from UPDATE |
| W2 | WARNING | `penalize()` bulk DELETE collateral | Scope to penalized pair set |
| W3 | WARNING | `core.py` force builds clobber graphify | Restore graphify-protection guard |
| W5 | WARNING | `_apply_intent_boost` boolean precedence | Make code/doc mutually exclusive |
| M5 | MEDIUM | Feedback strength hardcoded | Derive from `LEARNING_RATE` |

---

## 📋 BACKLOG

| # | Issue | Priority |
|---|-------|----------|
| 14 | Logos training transformers incompatibility | P1 |

---

## ✅ SHIPPED: Pre-v3.1.2 (Confirmed Working)

| Feature | Version | Date |
|---------|---------|------|
| Hebbian co-activation (undirected) | v0.11.0 | 2026-07-17 |
| Directional transitions | v0.11.0 | 2026-07-17 |
| Memory namespaces | v0.11.0 | 2026-07-17 |
| Learned half-life | v0.11.0 | 2026-07-17 |
| Reuse-detection feedback | v0.38.0 | 2026-07-31 |
| Periodic decay (`watch`) | v3.1.2 | 2026-08-09 |
| `audit export/verify` CLI | v3.1.2 | 2026-08-09 |
| `compliance` CLI | v3.1.2 | 2026-08-09 |
| `feedback good/bad` CLI | v3.1.2+ | 2026-08-09 |
| `status` dashboard | v3.1.2+ | 2026-08-09 |
| `penalize()` method | v3.1.2+ | 2026-08-09 |
| `.neuralmindignore` support | v3.1.2+ | 2026-08-09 |
| `health` check endpoint | v3.1.2+ | 2026-08-09 |
| `synapse prune/stats` | v3.1.2+ | 2026-08-09 |
| `audit recent` | v3.1.2+ | 2026-08-09 |
| Query `--type` filter | v3.1.2+ | 2026-08-09 |
| Cross-project query | v3.1.2+ | 2026-08-09 |
| Code/doc intent detection | v3.1.3+ | 2026-08-11 |
| LTP-guarded penalize/prune | v3.1.3+ | 2026-08-11 |
| RBAC for health tool | v3.1.3+ | 2026-08-11 |

---

*Next: run tests, create PR, merge to main.*
