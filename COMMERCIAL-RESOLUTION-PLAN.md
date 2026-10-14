# NeuralMind → cmmc20 Commercial Resolution Plan
**Created:** 2026-10-14 | **Owner:** Hermes Agent | **Status:** READY FOR EXECUTION

---

## Prioritization Framework

| Priority | Criteria |
|----------|----------|
| **P0 — Ship Blocking** | Directly blocks cmmc20 deploy, compliance features, or revenue |
| **P1 — High Value** | Enables competitive differentiation, reduces risk, improves reliability |
| **P2 — Quality** | Technical debt, polish, developer experience |
| **P3 — Nice to Have** | Future features, language support, benchmarks |

---

## P0 — Ship Blocking (Do First)

### #660 `feat(security): security.profile: cui — CUI-enclave posture`
**Business Impact:** Core "No-CUI Enforcement Layer" marketing claim — must work for cmmc20 compliance scans
**Definition of Done:** 
- [ ] Single `security.profile: cui` setting enforces: no CUI in prompts, no CUI in index, audit log only hashes
- [ ] CI gate fails if CUI detected in any compliance scan
- [ ] Documented in `neuralmind/compliance.py` and cmmc20 integration tests
**Effort:** 3-5 days | **Owner:** Backend lead | **Target:** Before cmmc20 launch

### #662 `feat(audit): signed, anchored audit checkpoints`
**Business Impact:** Tamper-evident audit log — already marketed, must be bulletproof
**Definition of Done:**
- [ ] Hash-chain truncation detected and reported
- [ ] Recomputed chain detection (replay attack prevention)
- [ ] Integration test in cmmc20 neuralmind-service `/api/compliance/verify`
- [ ] Performance: <50ms overhead per audit event
**Effort:** 2-3 days | **Owner:** Rust/backend lead | **Target:** Before cmmc20 launch

---

## P1 — High Value (Next Sprint)

### #640 `Field report: 12-repo audit on 4.12.0 — follow-ups`
**Business Impact:** Adversarial QA findings — credibility risk if unaddressed
**Action:** 
- [ ] Triangulate with our cmmc20 adversarial QA findings (qa-findings.db)
- [ ] Create tracked tasks for each follow-up
- [ ] Close loop: every finding has fix or accepted risk documented

### #632 `[BUG] Graph builder skips __init__.py`
**Business Impact:** Compliance scans miss package-level code (where CUI often lives)
**Definition of Done:**
- [ ] `__init__.py` parsed and indexed
- [ ] Symbol exports from `__init__.py` searchable
- [ ] Regression test added

### #631 `[BUG] Stale/legacy index silent at query time`
**Business Impact:** False confidence — compliance scan says "clean" but index is stale
**Definition of Done:**
- [ ] Index version/checksum validated at query time
- [ ] Clear error if index older than configured TTL
- [ ] Auto-rebuild trigger documented

### #638 `[DOCS] Licensing: GitHub detects NOASSERTION`
**Business Impact:** Enterprise/compliance buyers check SPDX — blocker for gov sales
**Definition of Done:**
- [ ] All crates/packages have SPDX identifiers
- [ ] `cargo deny` / `pip-licenses` pass in CI
- [ ] `LICENSE` files match SPDX

---

## P2 — Quality (Ongoing)

### #658 `chore(deps): bump github-actions`
### #655 `chore(deps): bump mcp 2.2.0 → 2.3.0`
### #654 `chore(deps): bump black 26.5.1 → 26.10.0`
### #650 `ci: cancel superseded PR runs, cache pip, merge-queue`

**Batch Approach:** Single "Dependency & CI Hardening" sprint
- [ ] Update all in one PR with green CI
- [ ] Run full test suite + adversarial QA
- [ ] Tag release 4.16.0 (#661)

### #639 `[BUG] doctor: status tags mixed case`
### #636 `[DOCS] README hero: lead with ripgrep comparison`

**Batch:** Polish sprint — UX + landing page

---

## P3 — Deferred (Post-Launch)

| Issue | Reason |
|-------|--------|
| #637 End-to-end agent-task benchmark | Research, not product |
| #633 Dart/Flutter support | No cmmc20 demand |
| #634 build --dry-run underestimates | Known limitation, documented |

---

## Execution Model

### Sprint 1 (Week 1): P0 Only
```
Mon-Tue: #660 CUI-enclave posture
Wed-Thu: #662 Signed audit checkpoints  
Fri:     Integration test in cmmc20 neuralmind-service
```

### Sprint 2 (Week 2): P1 Critical
```
Mon:     #640 Triangulate QA follow-ups
Tue-Wed: #632 __init__.py indexing
Thu:     #631 Stale index detection
Fri:     #638 SPDX licensing
```

### Sprint 3 (Week 3): Release 4.16.0
```
Mon-Tue: Dependency/CI batch (#658, #655, #654, #650)
Wed:     Polish batch (#639, #636)
Thu:     Full regression + adversarial QA
Fri:     Tag 4.16.0, update cmmc20 neuralmind-service
```

---

## Quality Gates (Every PR)

1. **Adversarial QA** — runs automatically on PR (cron + git hook)
2. **Contract Tests** — cmmc20 neuralmind-service integration must pass
3. **Security Scan** — `cargo audit`, `pip-audit`, `npm audit`
4. **Performance** — audit event <50ms, index query <200ms
5. **Documentation** — updated for any user-facing change

---

## cmmc20 Integration Checklist (Post 4.16.0)

- [ ] Update `neuralmind-service/requirements.txt` → `neuralmind>=4.16.0`
- [ ] Rebuild `neuralmind-4.16.0-py3-none-any.whl`
- [ ] Rebuild `l2l_audit` wheel if Rust changed
- [ ] Update `neuralmind-service/Dockerfile` with new wheels
- [ ] Deploy to Render (auto-deploy on push)
- [ ] Verify `/api/compliance/*` endpoints on production
- [ ] Run cmmc20 full test suite against live neuralmind-service

---

## Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| CUI-enclave breaks existing scans | Medium | High | Feature flag, gradual rollout |
| Audit checkpoint perf regression | Low | High | Benchmark in CI, alert on >50ms |
| Dependency updates break build | Medium | Medium | Pin versions, test in isolation |
| QA follow-ups reveal deeper issues | Medium | High | Timebox investigation, escalate |

---

## Sign-Off

| Role | Name | Date |
|------|------|------|
| Product Owner | Darren Frost | |
| Engineering Lead | | |
| QA Lead | | |
| Security Review | | |

---
*This plan aligns neuralmind development with cmmc20 commercial requirements. Execute Sprint 1 immediately upon GitHub PAT availability.*