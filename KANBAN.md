# NeuralMind — Kanban Board (v3.1.2)

**Last updated:** 2026-08-09
**Repo:** `neuralmind-fresh` (dfrostar/neuralmind)
**Version:** 3.1.2 (pyproject.toml / `__init__.py`)

---

## ✅ COMPLETE: P0 Dogfood Fixes (2026-08-09)

| # | Issue | Status | Fix | Commit |
|---|-------|--------|-----|--------|
| 1 | Role-gated MCP tools | ✅ FIXED | Added savings, compliance_report, structural_gaps, synapse_stats, synapse_decay, export_synapse_memory, feedback to builder role | `b113b24` |
| 2 | No auto-rebuild | ✅ FIXED | Post-build hint directing to `init-hook` and `watch` | `aded3fd` |
| 4 | No incremental build | ✅ FIXED | `_maybe_generate_builtin_graph` now regenerates on every build (graphgen reuses unchanged nodes by hash) | `986db53` |

---

## ✅ COMPLETE: Gap Closure (Forward-ported to v3.1.2)

| ID | Task | Effort | Evidence |
|----|------|--------|----------|
| G-01 | `LEARNING_RATE` 0.30 (already in v3.1.2) | — | `synapses.py:63` |
| G-02 | `STRUCTURAL_BASE_WEIGHT` 0.25 (already in v3.1.2) | — | `synapses.py:175` |
| G-03 | `SynapseStore.penalize()` — anti-Hebbian with auto-prune | 30 min | `synapses.py:665-722` |
| G-04 | `neuralmind feedback good/bad` CLI | 30 min | `cli_feedback_status.py` |
| G-05 | `neuralmind status` dashboard + diagnostic | 45 min | `cli_feedback_status.py` |
| G-06 | Wire to CLI parser + imports | 10 min | `cli.py` |
| G-07 | README: learning rate, feedback, status | 10 min | `README.md` |

---

## 🔨 ACTIVE: P1 Fixes

| # | Issue | Status | Priority | Notes |
|---|-------|--------|----------|-------|
| 3 | No `.neuralmindignore` | 🔴 REPRODUCED | P1 | 680/1080 nodes are markdown docs. Add `.gitignore`-style exclusion. |
| 6 | No audit trail query | 🔴 REPRODUCED | P1 | `audit.py` exists but no CLI/MCP tool to query it. |

---

## 📋 BACKLOG: P2-P3

| # | Issue | Status | Priority | Notes |
|---|-------|--------|----------|-------|
| 5 | 176 unknown edge relations | 🔴 REPRODUCED | P2 | Tree-sitter method edges not mapped to IR. |
| 7 | Compliance ingestion (SOC2/ISO) | ⚠️ PARTIAL | P2 | `compliance_matcher.py` exists; check SOC2/ISO 27001 coverage. |
| 8 | Markdown bloat in ranking | 🔴 REPRODUCED | P2 | Same root cause as #3. |
| 9 | No cross-project query | 🔴 REPRODUCED | P2 | Can't answer "which repo handles auth?" |
| 10 | Synapse pruning | ❓ UNCHECKED | P3 | Check `watch` decay behavior. |
| 11 | Health check | ❓ UNCHECKED | P3 | `doctor` exists; check synapse coverage. |
| 12 | Unknown | ❓ UNCHECKED | P3 | Not yet dogfood-checked. |

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
| `feedback good/bad` CLI | v3.1.2+ | 2026-08-09 (this work) |
| `status` dashboard | v3.1.2+ | 2026-08-09 (this work) |
| `penalize()` method | v3.1.2+ | 2026-08-09 (this work) |

---

## 📊 Success Metrics

| Metric | Before | After |
|--------|--------|-------|
| `LEARNING_RATE` | 0.15 | 0.30 ✅ |
| `STRUCTURAL_BASE_WEIGHT` | 0.18 | 0.25 ✅ |
| Explicit feedback | None | `feedback good/bad` ✅ |
| Status observability | `stats` (embedder only) | `status` (synapse health + learning diagnostic) ✅ |
| Anti-Hebbian penalization | None | `penalize()` with auto-prune ✅ |
| Builder role analytics | Denied | Full access ✅ |
| Incremental build | Full 77s rebuild | Delta embedding ✅ |
| Auto-rebuild suggestion | None | Post-build hint ✅ |

---

*Next: tackle P1 items (#3 `.neuralmindignore`, #6 audit trail query).*
