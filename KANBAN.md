# NeuralMind — Kanban Board (CANONICAL — `dfrostar/neuralmind`)

**Last updated:** 2026-10-01 21:02 UTC (verified: in sync with origin/main, HEAD `39617aa`; v4.3.5 shipped + SBOM)
**Repo:** `neuralmind` (dfrostar/neuralmind)
**Version:** v4.3.5 shipped (PyPI + GHCR + site + SBOM)
**Branch:** main (in sync with origin/main, HEAD `39617aac`)
**Last commit (main):** `39617aac` — chore(sbom): publish neuralmind-v4.3.5.sbom.json to the site (2026-09-28)
**Uncommitted:** KANBAN.md (this file)

---

## Status

### v4.3.5 Release Train (2026-09-28)

| Commit | Content |
|--------|---------|
| `39617aac` | chore(sbom): publish neuralmind-v4.3.5.sbom.json to the site |
| `33c11b5` | chore(main): release 4.3.5 (#540) |

### Merged post-release (2026-09-27 → 09-28)

| Commit | Content |
|--------|---------|
| `f69202c` | **docs: public-surface messaging + SEO overhaul; public benchmark regenerated at v4.3.4 (#539, merged 2026-09-28)** — homepage pain-to-promise hero + Problem section; REMOVED contradicted claims ("No cloud calls"/"100% local", "outperforms plain RAG", "$1,650/mo" math error, "12-50x measured in CI" → CI measures ~6x, 12-50x is field reports); /team page corrected to real `neuralmind team` CLI syntax (old page showed a `seats --email --org` syntax that never existed); /security "No Known Vulnerabilities" replaced with accurate disclosure status + network-egress section |
| `d972de9` | chore: update NeuralMind team memory snapshot [skip ci] (2026-09-28) |
| `24ee292` | **fix(synapses): stop decay() compounding on every call** (#422 → PR #536) — decay() multiplied weights by exp(-λ·age) on EVERY call; the SessionStart hook runs it once per session, so idle edges were charged their full age again at each session start, collapsing weights onto LTP_FLOOR or pruning them. Each tick now charges only time since MAX(last_activated, meta.last_decay). Transitions get the same fix. |
| `8ceda53` | **docs: close LLM-disclosure gap in air-gapped/offline-regulated use cases** (#512) — qualifies "no outbound network" absolutes in docs/use-cases/air-gapped.md + offline-regulated.md with the NEURALMIND_LLM_SEED egress path; cross-links THIRD_PARTY_LLM_DISCLOSURE.md; fixes dead links (about.html, SECURITY.md, VULNERABILITY-MANAGEMENT-POLICY.md) |

### Release Train (2026-09-25 → 09-26)

| Version | Content | Released |
|---------|---------|----------|
| **v4.3.0** | Memory Layer v4.3 — 3-layer progressive retrieval + session-bound hooks (#527) | 2026-09-25 16:17 UTC |
| **v4.3.1** | Book-mode misdetection fix, doctor per-scope probe, ingestion ignore guard (#532) | 2026-09-25 22:58 UTC |
| **v4.3.2** | Book auto-detection + content ingest ignores for package-layout Python repos (#528); Mem0/Zep + Codex CLI memory comparisons, `neuralmind_record_decision` MCP fix (#523) | 2026-09-26 04:17 UTC |
| **v4.3.3** | 🔒 Security: never ingest dot-files (.env secrets leak); correct gitignore semantics — **MERGED** (PR #535), SBOM published | 2026-09-26 05:33 UTC |

**Showcase cron** verified v4.3.3 public surfaces Saturday 9 AM.

### What Works (Verified)

| Component | Status | Tests |
|-----------|--------|-------|
| MedicalRetriever (standalone) | ✅ Built & tested | 22/22 pass |
| ChapterIndexer (standalone) | ✅ Built & tested | 12/12 pass |
| Pipeline integration (prose path) | ✅ Wired & tested | 12/12 pass |
| Memory system (decision layer, v4.2→v4.3) | ✅ Shipped | eval harness + MCP tools |
| Stale-decision guard (all public surfaces) | ✅ Shipped (v4.2.0) | incl. Windows path normalization |
| Cost Attribution Dashboard (`neuralmind cost`) | ✅ Shipped (`09318d5`) | — |
| Synapse-prose integration | ✅ Shipped (`ad51f53`, 2026-09-21) | Hebbian learning on book content |
| Synapse decay compounding fix | ✅ Merged (`24ee292`, PR #536, 2026-09-27) | relative-tolerance test `1659d40` |
| Output dir consolidation (`graphify-out/` → `.neuralmind/`) | ✅ Shipped (`62a44e8`) | legacy fallback |
| Public benchmark drift guard (`bench-public-drift.yml`) | ✅ Shipped (`78f9299`) | CI |
| Security: dot-file ingestion guard | ✅ Shipped (v4.3.3, PR #535) | CI |
| Air-gapped LLM-disclosure docs | ✅ Merged (`8ceda53`, PR #512, 2026-09-27) | — |
| v4.3.5 SBOM | ✅ Published (`39617aac`, 2026-09-28) | — |
| MCP stdio perf Phase 0 | ✅ Merged (`53bf6cc`, PR #538, 2026-09-27) | — |
| Public-surface messaging + SEO overhaul | ✅ Merged (`f69202c`, PR #539, 2026-09-28) | claims-guard CI |
| v4.3.5 release | ✅ Shipped (`33c11b5`, PR #540, 2026-09-28) | — |

### Benchmark Results (peptide book, 14 queries — v3.12 → v3.13)

| Metric | Before (v3.12) | After (v3.13) | Change |
|--------|----------------|---------------|--------|
| **Recall@1** | 64.3% | 78.6% | **+14 pts** |
| **Fact Recall** | 47% | 84% | **+37 pts** |
| MRR | 0.79 | 0.83 | +0.04 |
| Avg Latency | 1418ms | 921ms | 1.5x faster |

---

## Pending Work

### Next Sprint
- [ ] **Component A — Benchmark & Eval Harness** (`neuralmind memory eval`; contamination-blocked eval methodology, residual-context metric) — from `neuralmind-marketing/internal/plans/memory-layer-build-spec-v1.0.md`
- [ ] **Component D — Framework-aware invalidation edges** (FastAPI/Flask routes → precise staleness; TRD §7 / US-06 5-min staleness)
- [ ] Context Mode MCP integration for session continuity
- [ ] e5-large embedding upgrade (network blocked)
- Open docs PRs: #518 (performance & future-proofing research spec), #531 (release-please housekeeping) — still open; #512 merged 2026-09-27; #538 merged 2026-09-27; #539 merged 2026-09-28 |

### Known Limitations
- MiniLM-L6-v2 (384-dim) is the embedding ceiling (~67% recall@1)
- e5-large upgrade path documented but not yet available (network blocked)
- P95 latency 7.6s (first query cold start); subsequent queries <400ms

---

## Decisions Made (historical)

| Decision | Rationale |
|----------|-----------|
| Chapter-level indexing (one doc per chapter) | Eliminates duplicate chapter entries from 61 fragmented nodes |
| Hybrid scoring: 0.30 BM25 + 0.45 embedding + 0.25 heading match | Embedding carries semantic queries; heading match catches exact phrases |
| Claims Register downweight (0.4×) | Reference tables hijack BM25 with dense term repetition |
| Back-matter downweight (0.3×) | Glossary is lookup table, not clinical content |
| Confidence gating (HIGH≥0.70, MEDIUM≥0.40, LOW<0.40) | No silent low-confidence results for medical content |
| Lazy initialization | MedicalRetriever only builds on first prose query |
| Decay charges only since MAX(last_activated, last_decay) | SessionStart ran decay() per session → idle edges charged full age repeatedly, collapsing weights (PR #536) |
| Remove contradicted marketing claims (PR #539) | Site claimed things the product/docs contradict — "100% local" (first build downloads a model), "outperforms plain RAG" (benchmark shows parity), "$1,650/mo" (docs mark it a math error) |

---

## 📊 Repo State (2026-10-01 21:02 UTC)

| Field | Value |
|-------|-------|
| Branch | main |
| HEAD | `39617aa` (2026-09-28) — in sync with origin/main |
| Uncommitted | KANBAN.md only |
| Stale days | 3 days (last commit 2026-09-28) |
| Latest tag | v4.3.5 (2026-09-28) |
| pyproject version | 4.3.5 |