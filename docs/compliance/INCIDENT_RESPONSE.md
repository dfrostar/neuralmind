# Incident Response Plan

**Date:** 2026-10-18
**Version:** 1.2
**SOC 2 Controls:** CC7.3, CC7.4, CC7.5

---

## 1. Purpose

Define how to detect, respond to, recover from, and learn from security incidents affecting NeuralMind.

NeuralMind has one maintainer. Version 1.1 promised a response within an hour
for a critical incident, which one person can't keep, and kept its records in
"private GitHub Issues", which GitHub doesn't have. The targets below are the
ones [`SECURITY.md`](../../SECURITY.md) publishes, and the records go in a draft
GitHub security advisory, which is private until published.

## 2. Scope

Covers incidents in:
- NeuralMind codebase (dfrostar/neuralmind)
- NeuralMind infrastructure (GitHub, Cloudflare Pages, PyPI, GHCR)
- NeuralMind data (`.neuralmind/` directories, `audit_events.jsonl`)

## 3. Severity Levels

| Level | Description | Examples | Target fix |
|-------|-------------|----------|------------|
| **CRITICAL** | Active exploitation, data breach | RCE in MCP server, exfiltration of user code | 24–72 hours |
| **HIGH** | Significant security impact | Bypass of RBAC, unauthorized access to index | 1 week |
| **MEDIUM** | Limited security impact | DoS of `neuralmind serve`, information disclosure in logs | 2–4 weeks |
| **LOW** | Minimal security impact | Outdated dependency with no known exploit | Next release |

Every report is acknowledged within 2 business days and triaged within 5
([`SECURITY.md`](../../SECURITY.md#response-timeline)). An incident the
maintainer finds, rather than one reported, starts at triage.

## 4. Incident Response Phases

### 4.1 Detection

Incidents may be detected via:
- GitHub Security Advisories (automated dependency scanning)
- User reports (GitHub private vulnerability reporting, email; a report in a
  public issue is moved to a draft advisory)
- Code review, CodeQL, bandit and `pip-audit` in CI

### 4.2 Triage

Within 5 business days of the report:
1. Confirm the incident is real (not a false positive)
2. Assign severity level
3. Document initial findings in a draft GitHub security advisory

### 4.3 Containment

For CRITICAL and HIGH:
1. Isolate affected component (disable MCP server, block access)
2. Preserve evidence (logs, artifacts)
3. Do NOT delete anything — evidence is needed for forensics

### 4.4 Eradication

1. Identify root cause
2. Implement the fix in the advisory's temporary private fork
3. Test the fix locally and in CI
4. Ask the reporter to confirm the fix, where there is one

### 4.5 Recovery

1. Deploy fix (see Change Management Policy)
2. Verify fix resolves the incident
3. Monitor for recurrence
4. Re-enable affected component

### 4.6 Post-Incident Review

Within 1 week of resolution:
1. Document timeline
2. Identify what went wrong
3. Identify what went right
4. Implement preventive measures
5. Update this plan if gaps were found

## 5. Communication

### 5.1 Internal

- Solo maintainer: document in the draft GitHub security advisory
- Future team: Slack/email notification to security team

### 5.2 External

For incidents affecting users:
1. GitHub Security Advisory published within 72 hours
2. Release notes describe the fix (without revealing exploit details)
3. Direct notification to affected paid customers

### 5.3 Coordination

- Follow GitHub's coordinated vulnerability disclosure process
- Credit reporters (unless anonymity requested)
- Coordinate with dependencies (ChromaDB, tree-sitter, etc.) if upstream issue

## 6. Runbooks

### 6.1 Vulnerable Dependency Detected

1. Assess exploitability in NeuralMind's usage
2. If exploitable: create private security advisory, implement fix
3. If not exploitable: dismiss with justification in Dependabot
4. Update `SECURITY.md` if advisory published

### 6.2 Unauthorized Access Detected

1. Identify affected scope (which project, which user)
2. Disable access (GitHub token revocation)
3. Rotate any exposed secrets
4. Preserve audit logs
5. Report to affected user if data accessed

### 6.3 Malicious Code Committed

1. Revert commit immediately
2. Identify how it bypassed review
3. Implement preventive controls
4. Review all commits from same author

## 7. Testing

This plan is to be tested annually by tabletop exercise:
- Scenario: critical vulnerability in dependency
- Validate: detection, triage, containment, communication
- Update plan based on findings

No exercise has been run or recorded yet.

---

*This plan is reviewed annually. Last reviewed: 2026-10-18.*
