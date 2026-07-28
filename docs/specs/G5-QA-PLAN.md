# G5 — Structural Gap Detection, QA Plan

**Date:** 2026-07-27
**Module:** `neuralmind/structural_gaps.py` + `neuralmind/cli.py` + `neuralmind/mcp_server.py`
**Commit:** pending
**Claim tier:** B+
**Parent specs:** `docs/specs/G5-BRD.md` · `docs/specs/G5-TRD.md` · `docs/specs/G5-TEST-PLAN.md`

---

## 1. QA Strategy

**Two-gate release process:**

1. **Gate 1: Automated CI** — all unit + integration tests must pass, coverage targets met
2. **Gate 2: DeepSeek QA** — per-module code review via deepseek-v4-pro, risk checklist

G5 does NOT ship until both gates pass. No exceptions.

---

## 2. Gate 1 — Automated Test Acceptance

### 2.1 Test Count Gate

| Layer | Tests | Minimum Pass |
|-------|-------|--------------|
| Unit — betweenness | 8 | 8 |
| Unit — bridge candidates | 5 | 5 |
| Unit — gap detection | 6 | 6 |
| Unit — Gap dataclass | 4 | 4 |
| Unit — formatting | 4 | 4 |
| Unit — edge weights | 3 | 3 |
| Unit — robustness | 5 | 5 |
| Integration — CLI | 4 | 4 |
| Integration — MCP | 3 | 3 |
| **Total new** | **45** | **43** |
| Existing regression | All | 100% |

### 2.2 Coverage Gate

| Module | Target | Minimum |
|--------|--------|---------|
| `structural_gaps.py` | 95% | 90% |
| `cli.py` (new code) | 100% | 90% |
| `mcp_server.py` (new code) | 100% | 90% |

### 2.3 Performance Gate

| Graph Size | Target | Max |
|------------|--------|-----|
| 1K nodes | < 500ms | < 1s |
| 5K nodes | < 2s | < 5s |
| 10K nodes | < 5s | < 15s |

### 2.4 Fail-Open Gate

| Scenario | Expected |
|----------|----------|
| Missing graph.json | Warning + empty result, no crash |
| Empty graph | Empty result |
| Single community | "Need ≥3 communities" message |
| Corrupt JSON | Warning + empty result |
| Missing community field | Louvain inline, info log |

---

## 3. Gate 2 — DeepSeek QA

### 3.1 Review Dispatch

| Batch | Module | Risk | Provider |
|-------|--------|------|----------|
| 1 | `structural_gaps.py` | HIGH | deepseek-v4-pro |
| 2 | `cli.py` (new code) | HIGH | deepseek-v4-pro |
| 3 | `mcp_server.py` (new code) | MEDIUM | deepseek-v4-pro |
| 4 | `test_structural_gaps.py` | LOW | deepseek-v4-pro |

### 3.2 Risk Checklist (per module)

| Risk | Question | Pass Criteria |
|------|----------|---------------|
| Algorithm correctness | Does Brandes compute correct betweenness on star graph? | Center CB = 1.0 |
| Edge cases | Division by zero? Negative weights? NaN? | Handled |
| Performance | O(VE) documented? Sampling fallback works? | Yes |
| Dependency creep | Any non-stdlib import? | None |
| Fail-open | All error paths return empty + warning? | Yes |
| Deterministic | Same graph → same output? | Yes |
| Memory | Large graph doesn't OOM? | Sampling fallback |

### 3.3 QA Findings Format

```
🔴 CRITICAL — must patch before ship
⚠️ WARNING — should patch before ship
ℹ️ INFO — nice-to-have, can defer
```

### 3.4 Verification Protocol

1. Dispatch DeepSeek review (parallel batches)
2. Collect findings
3. Verify each finding before patching (~20% false positive rate)
4. Patch 🔴 CRITICAL + ⚠️ WARNING
5. Re-run test suite after patching
6. Report: what was patched + test counts

---

## 4. Pre-Release Checklist

### 4.1 Code Quality

- [ ] All new code has inline docstrings
- [ ] Type hints on all public functions
- [ ] No `@ts-nocheck` or equivalent
- [ ] No `// TODO` comments
- [ ] No placeholder implementations
- [ ] No workaround patterns (real fix, not patch)

### 4.2 Documentation

- [ ] `G5-BRD.md` committed
- [ ] `G5-TRD.md` committed
- [ ] `G5-TEST-PLAN.md` committed
- [ ] `G5-ADR.md` committed
- [ ] `G5-QA-PLAN.md` (this document) committed
- [ ] `WAVE8-SESSION-KICKOFF.md` committed
- [ ] `ROADMAP.md` updated with G5
- [ ] `RELEASE_NOTES_G5.md` drafted

### 4.3 Test Infrastructure

- [ ] 10 test fixtures generated deterministically
- [ ] Fixture generator script committed
- [ ] `conftest.py` updated if needed
- [ ] CI passes on latest commit

### 4.4 Integration

- [ ] `neuralmind gaps --structural` works on real project
- [ ] `neuralmind gaps --structural --json` valid JSON
- [ ] MCP tool registered + callable
- [ ] No changes to `build()`, `query()`, `synapses`

### 4.5 Performance

- [ ] 1K nodes < 500ms
- [ ] 10K nodes < 5s
- [ ] Memory < 500MB on 10K graph

---

## 5. Honest Self-Assessment (Pre-Release)

### What's SOTA

| Component | Status | Evidence |
|-----------|--------|----------|
| Brandes betweenness | ✅ Exact | Brandes algorithm, pure Python, tested on 4 synthetic topologies |
| Bridge detection | ✅ Working | Two-community fixture correctly identifies bridge |
| Gap scoring | ✅ Working | Inverse-degree penalty filters hubs |
| CLI integration | ✅ Working | `neuralmind gaps --structural` |
| MCP tool | ✅ Working | Registered + callable |

### What's Placeholder (Deferred to G6)

| Component | Status | Why |
|-----------|--------|-----|
| Gap visualization | ❌ None | Frontend work (Sigma.js/D3) |
| AI-powered gap resolution | ❌ None | LLM integration |
| Temporal gap tracking | ❌ None | Requires gap history store |
| Synapse integration | ❌ None | Design question |
| Incremental betweenness | ❌ None | Approximate algorithms |

---

## 6. Ship Declaration

```
I declare G5 ship-ready when:
  ✅ 43+/45 new tests pass
  ✅ Zero regressions in existing test suite
  ✅ Gate 1 (automated CI) green
  ✅ Gate 2 (DeepSeek QA) findings patched or deferred with rationale
  ✅ All 6 docs committed (BRD, TRD, TEST-PLAN, ADR, QA-PLAN, SESSION-KICKOFF)
  ✅ ROADMAP.md updated
  ✅ RELEASE_NOTES_G5.md drafted

Sign-off: Hermes (product strategy + engineering)
Date: 2026-07-27
```

---

## 7. Post-Ship

### 7.1 Marketing Claim Audit

After ship, run marketing claim audit:
- Extract all claims from G5 docs
- Verify each against actual code
- Fix mismatches
- Create `G5-MARKETING-CLAIM-AUDIT.md`

### 7.2 Co-Indexation

After ship, re-index NeuralMind:
```bash
cd /home/dtfrost/neuralmind
neuralmind build .
neuralmind query . "G5 structural gap detection"
```

### 7.3 User Feedback

Monitor:
- False positive rate (users reporting "this isn't a real gap")
- Performance complaints
- Feature requests (visualization, AI suggestions → G6)

---

*Generated by Hermes. G5-QA-PLAN — v1.0. Claim tier: B+.*
