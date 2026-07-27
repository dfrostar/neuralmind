# Risk Assessment

**Date:** 2026-07-27
**Version:** 1.0
**SOC 2 Control:** CC2.1

---

## 1. Purpose

Identify, assess, and mitigate risks to NeuralMind's confidentiality, integrity, and availability.

## 2. Methodology

Risks are scored on two dimensions:
- **Likelihood:** How likely is this risk to occur? (1=rare, 5=almost certain)
- **Impact:** How severe would the impact be? (1=negligible, 5=catastrophic)

**Risk Score = Likelihood × Impact**

| Score | Level | Action Required |
|-------|-------|-----------------|
| 1-4 | LOW | Accept, monitor |
| 5-9 | MEDIUM | Mitigate within 3 months |
| 10-19 | HIGH | Mitigate within 1 month |
| 20-25 | CRITICAL | Mitigate immediately |

## 3. Risk Register

| ID | Risk | Likelihood | Impact | Score | Level | Mitigation | Owner |
|----|------|------------|--------|-------|-------|------------|-------|
| R-01 | Vulnerable dependency (Critical CVE) | 3 | 5 | 15 | HIGH | Automated Dependabot alerts, 72h patch SLA for critical | Maintainer |
| R-02 | Malicious code injection via PR | 2 | 5 | 10 | HIGH | Code review required, branch protection, CI gates | Maintainer |
| R-03 | Data exfiltration via MCP server | 1 | 5 | 5 | MEDIUM | Local-only by default, RBAC, audit logging, no network | Maintainer |
| R-04 | Index corruption / data loss | 2 | 4 | 8 | MEDIUM | SQLite WAL mode, `neuralmind build --verify`, local backups | Maintainer |
| R-05 | PyPI package compromise | 1 | 5 | 5 | MEDIUM | Trusted publishing (OIDC), 2FA on PyPI account, SBOM | Maintainer |
| R-06 | Key person dependency (solo maintainer) | 3 | 4 | 12 | HIGH | Documented runbooks, bus factor reduction plan, paid support option | Maintainer |
| R-07 | Audit log tampering | 1 | 4 | 4 | LOW | Append-only JSONL, git-backed evidence, Vanta monitoring | Maintainer |
| R-08 | Compliance failure (SOC 2 audit) | 2 | 3 | 6 | MEDIUM | Vanta engagement, documented controls, operating period | Maintainer |
| R-09 | Cloudflare Pages outage | 2 | 3 | 6 | MEDIUM | No data loss (static), easy to redeploy, 99.9% SLA | Cloudflare |
| R-10 | GitHub Actions disruption | 2 | 2 | 4 | LOW | Local fallback (`pytest`, `build`), no hard dependency on CI | GitHub |

## 4. Review Schedule

- **Monthly:** Review Dependabot alerts, update R-01
- **Quarterly:** Review all risks, update scores
- **Annually:** Full risk assessment, update this document
- **Trigger-based:** Review immediately after any security incident

## 5. Residual Risk Acceptance

The following risks are accepted (score ≤ 4):
- R-07: Audit log tampering — append-only design makes this unlikely, no further mitigation
- R-10: GitHub Actions disruption — local development workflow is fully functional without CI

---

*This risk assessment is reviewed quarterly. Last reviewed: 2026-07-27.*
