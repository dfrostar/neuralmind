# SOC 2 Readiness — Test Plan

**Date:** 2026-07-27
**Version:** 1.0
**Related TRD:** `docs/specs/compliance/2026-07-27-SOC2-TRD.md`

---

## 1. Test Scope

### 1.1 In Scope

| Component | What to Test | Priority |
|-----------|--------------|----------|
| Vanta integration | GitHub + Cloudflare connected, evidence auto-collected | HIGH |
| Evidence collection script | `/healthz` check, audit log summary, index integrity | HIGH |
| Health check monitor | GitHub Actions cron fires, collects evidence | MEDIUM |
| Backup test | Backup + recovery simulation passes | HIGH |
| Policy documents | All required policies committed, accurate | HIGH |

### 1.2 Out of Scope

- SOC 2 audit itself (conducted by external auditor in Month 10-12)
- Vanta platform internals (vendor responsibility)
- Cloudflare Pages uptime (vendor SLA)

---

## 2. Test Cases

### TC-01: Vanta GitHub Integration

| Field | Value |
|-------|-------|
| **Objective** | Verify Vanta can connect to GitHub repo and collect evidence |
| **Prerequisites** | Vanta account created, GitHub integration enabled |
| **Steps** | 1. Sign into Vanta<br>2. Navigate to Integrations<br>3. Select GitHub<br>4. Authorize Vanta OAuth<br>5. Select `dfrostar/neuralmind` repo<br>6. Wait for initial scan |
| **Expected Result** | Vanta dashboard shows repo, auto-collects PR history, branch protection, CI status |
| **Pass Criteria** | All GitHub evidence green in Vanta dashboard |
| **Evidence** | Vanta dashboard screenshot |

### TC-02: Vanta Cloudflare Integration

| Field | Value |
|-------|-------|
| **Objective** | Verify Vanta can connect to Cloudflare and collect Pages evidence |
| **Prerequisites** | Cloudflare account with Pages access |
| **Steps** | 1. Navigate to Vanta Integrations<br>2. Select Cloudflare<br>3. Enter API token<br>4. Wait for initial scan |
| **Expected Result** | Vanta shows neuralmind-marketing.pages.dev, SSL/TLS status |
| **Pass Criteria** | Cloudflare evidence green in Vanta dashboard |
| **Evidence** | Vanta dashboard screenshot |

### TC-03: Evidence Collection Script

| Field | Value |
|-------|-------|
| **Objective** | Verify `scripts/collect-evidence.py` runs and produces valid output |
| **Prerequisites** | Python 3.12, NeuralMind installed, indexed project |
| **Steps** | 1. `cd /home/dtfrost/neuralmind`<br>2. `python3 scripts/collect-evidence.py`<br>3. `cat evidence/*.json` |
| **Expected Result** | Script exits 0, produces JSON with health, audit_log, index_integrity |
| **Pass Criteria** | All three sections present, health.status = "healthy", index_integrity.status = "valid" |
| **Evidence** | Script output, evidence JSON |

### TC-04: Health Check Monitor Workflow

| Field | Value |
|-------|-------|
| **Objective** | Verify GitHub Actions cron triggers and collects evidence |
| **Prerequisites** | monitor.yml committed to `.github/workflows/` |
| **Steps** | 1. Push to main<br>2. Wait for next cron trigger<br>3. Check Actions tab |
| **Expected Result** | Workflow runs every 6 hours, produces artifact |
| **Pass Criteria** | Workflow completes successfully, evidence artifact uploaded |
| **Evidence** | GitHub Actions run log |

### TC-05: Backup Test Script

| Field | Value |
|-------|-------|
| **Objective** | Verify backup and recovery of `.neuralmind/` data |
| **Prerequisites** | Bash, .neuralmind/ directory exists |
| **Steps** | 1. `cd /home/dtfrost/neuralmind`<br>2. `bash scripts/backup-test.sh` |
| **Expected Result** | Script exits 0, prints "=== Backup test PASSED ===" |
| **Pass Criteria** | Exit code 0, backup created and verified, recovery simulated |
| **Evidence** | Script output |

### TC-06: Policy Documents Committed

| Field | Value |
|-------|-------|
| **Objective** | Verify all required SOC 2 policies are committed to repo |
| **Prerequisites** | Policy docs written |
| **Steps** | 1. `ls docs/compliance/`<br>2. `grep -l "SOC 2\|Trust Service Criteria" docs/compliance/*.md` |
| **Expected Result** | CHANGE_MANAGEMENT.md, INCIDENT_RESPONSE.md, RISK_ASSESSMENT.md, ACCESS_CONTROL.md, SDLC_POLICY.md, DATA_RETENTION.md, DATA_DELETION.md all present |
| **Pass Criteria** | All 7 policy files exist, each references at least one SOC 2 control |
| **Evidence** | `ls` output, grep results |

### TC-07: Change Management Policy Accuracy

| Field | Value |
|-------|-------|
| **Objective** | Verify CHANGE_MANAGEMENT.md accurately describes actual practice |
| **Prerequisites** | CHANGE_MANAGEMENT.md committed |
| **Steps** | 1. Read document<br>2. Compare to actual GitHub workflow (PR → review → merge) |
| **Expected Result** | Document matches reality: branch protection, PR reviews, CI gates |
| **Pass Criteria** | No discrepancies between documented and actual change process |
| **Evidence** | Review notes |

### TC-08: Incident Response Policy Completeness

| Field | Value |
|-------|-------|
| **Objective** | Verify INCIDENT_RESPONSE.md covers all required elements |
| **Prerequisites** | INCIDENT_RESPONSE.md committed |
| **Steps** | 1. Read document<br>2. Check for: roles, severity levels, communication plan, escalation, post-incident review |
| **Expected Result** | All elements present and actionable |
| **Pass Criteria** | Document addresses all 5 required elements |
| **Evidence** | Checklist completion |

### TC-09: Risk Assessment Completeness

| Field | Value |
|-------|-------|
| **Objective** | Verify RISK_ASSESSMENT.md includes risk register with scoring |
| **Prerequisites** | RISK_ASSESSMENT.md committed |
| **Steps** | 1. Read document<br>2. Check for: risk categories, scoring matrix, mitigation strategies, owner assignment |
| **Expected Result** | ≥ 5 risks identified, each scored (likelihood × impact), each with mitigation |
| **Pass Criteria** | Risk register has ≥ 5 entries with complete scoring |
| **Evidence** | Risk register table |

### TC-10: Access Control Policy Alignment

| Field | Value |
|-------|-------|
| **Objective** | Verify ACCESS_CONTROL.md matches actual RBAC implementation |
| **Prerequisites** | ACCESS_CONTROL.md committed, `neuralmind/mcp_security.py` exists |
| **Steps** | 1. Read policy<br>2. Compare to actual RBAC roles in code (admin/builder/reader)<br>3. Verify access review frequency documented |
| **Expected Result** | Policy matches code (3 roles), access review quarterly |
| **Pass Criteria** | No discrepancies between documented and actual access controls |
| **Evidence** | Side-by-side comparison |

---

## 3. Test Schedule

| Phase | Test Cases | Timing |
|-------|------------|--------|
| Foundation | TC-01, TC-02 | Week 1-2 |
| Policy Docs | TC-06, TC-07, TC-08, TC-09, TC-10 | Week 3-4 |
| Automation | TC-03, TC-04, TC-05 | Month 2 |

---

## 4. Pass/Fail Criteria

### Overall Pass

- ≥ 8 of 10 test cases pass
- TC-01, TC-02, TC-03, TC-06 MUST pass (critical)
- No HIGH severity findings open

### Per-Test Pass

- All expected results observed
- All pass criteria met
- Evidence captured

---

## 5. Risks

| Risk | Mitigation |
|------|------------|
| Vanta integration fails | Use manual evidence collection as fallback |
| Policy docs inaccurate | Review against actual code before committing |
| Backup test fails on CI | Run locally, capture screenshot as evidence |

---

*This test plan follows SOTA standard. Next: Test Results after execution.*
