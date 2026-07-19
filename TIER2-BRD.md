# Tier 2 (Team) — Business Requirements Document (BRD)

**Product:** NeuralMind
**Tier:** Team ($29/user/mo, annual contract)
**Version:** v0.52.0 → v1.0.0 (Tier 2 launch)
**Author:** Darren Frost
**Date:** 2026-07-19

---

## 1. Executive Summary

NeuralMind Tier 2 ("Team") is the paid tier for engineering teams of 5-50 seats. It adds governance, audit, self-hosted deployment, and priority support on top of the free MIT product.

This BRD defines the business requirements. The TRD defines technical implementation. The Test Plan defines acceptance criteria. DeepSeek QA defines the review gate.

---

## 2. Stakeholders

| Segment | Need | Pain if missing |
|---------|------|-----------------|
| **Engineering Manager** | Team-wide memory governance | Can't control what gets published to shared namespace; no audit trail |
| **CISO / Security** | Audit log, self-hosted option | Can't deploy in regulated environments; no compliance posture |
| **Individual Dev (Team)** | Priority support | Stuck waiting on community issues |
| **Finance / Procurement** | Annual invoicing, seat management | Can't buy with PO; no seat revocation |

---

## 3. Business Goals

| Goal | Metric | 90-day target |
|------|--------|---------------|
| Paid tier conversion | Teams signed up | 5 teams |
| ARR | Monthly recurring revenue | $52,200 ARR (5 teams × 15 seats × $29 × 12) |
| Free-to-paid conversion | Free waitlist → Tier 2 | 10% |
| Churn | Monthly team churn | <5% |

---

## 4. Feature Requirements

### 4.1 Team Memory Governance

**Description:** Admin controls over what gets published to the shared namespace.

**Requirements:**

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-01 | Team admin can enable/disable team memory publishing per repo | P0 |
| FR-02 | Team admin can set publishing scope (personal only vs shared vs both) | P0 |
| FR-03 | Team admin can view what's in the shared namespace | P0 |
| FR-04 | Team admin can expire/remove specific edges from shared namespace | P1 |
| FR-05 | Team admin can set edge weight threshold for auto-publish (only strong edges) | P1 |
| FR-06 | Team admin can configure auto-decay policy (half-life defaults) | P2 |
| FR-07 | Team admin can view team memory dashboard (node count, edge count, active contributors) | P1 |

**User story:**
> As an engineering manager, I want to control what gets published to my team's shared namespace so that we don't accidentally propagate stale or sensitive associations.

---

### 4.2 Audit Log

**Description:** Immutable record of who did what in the shared namespace.

**Requirements:**

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-08 | Log every publish event (who, when, what repo, edge count) | P0 |
| FR-09 | Log every remove event (admin expiration, manual removal) | P0 |
| FR-10 | Log every namespace config change | P0 |
| FR-11 | Export audit log as CSV / JSON for compliance | P0 |
| FR-12 | Audit log is append-only (no editing or deletion of audit records) | P0 |
| FR-13 | Audit log retained for minimum 90 days | P1 |
| FR-14 | Audit log searchable by actor, date range, action type | P1 |

**User story:**
> As a CISO, I want an immutable audit trail of every action in the shared namespace so that I can demonstrate governance to auditors.

---

### 4.3 Self-Hosted Deployment

**Description:** On-prem / private cloud deployment option.

**Requirements:**

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-15 | Docker compose file for self-hosted deployment (one command) | P0 |
| FR-16 | Self-hosted mode persists data in mounted volume (no cloud calls) | P0 |
| FR-17 | Self-hosted admin CLI for seat management | P1 |
| FR-18 | License key validation for self-hosted (offline-capable) | P1 |
| FR-19 | Health check endpoint for monitoring | P1 |
| FR-20 | Upgrade path (data migration between versions) | P2 |

**User story:**
> As a platform engineer, I want to deploy NeuralMind in our private cloud so that our code never leaves our network.

---

### 4.4 Seat Management & Billing

**Description:** Team admin can manage seats and billing.

**Requirements:**

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-21 | Admin can add/remove seats | P0 |
| FR-22 | Seats cost $29/user/mo on annual contract | P0 |
| FR-23 | Admin can assign/revoke seats via email invite | P0 |
| FR-24 | Admin can view usage per seat (active vs inactive) | P1 |
| FR-25 | Annual renewal reminder 30 days before expiry | P1 |
| FR-26 | Grace period after expiry (14 days) before feature lock | P1 |
| FR-27 | Free trial (14 days, no credit card) | P0 |

---

### 4.5 Priority Support

**Description:** Faster response times for Team customers.

**Requirements:**

| ID | Requirement | Priority |
|----|-------------|----------|
| FR-28 | Dedicated support email (team@neuralmind.uk) | P0 |
| FR-29 | 48-hour SLA for issue response | P0 |
| FR-30 | GitHub issue priority labeling | P1 |

---

## 5. Non-Functional Requirements

| ID | Requirement |
|----|-------------|
| NFR-01 | All data encrypted at rest (AES-256) |
| NFR-02 | Audit log tamper-proof (append-only, no edit/delete) |
| NFR-03 | Self-hosted deployment supports air-gapped networks |
| NFR-04 | API rate limiting per seat (1000 req/min) |
| NFR-05 | Team memory publish is idempotent (content-hash gated) |
| NFR-06 | Self-hosted upgrade preserves existing data |
| NFR-07 | License key works offline for 30 days before re-validation |

---

## 6. Out of Scope (Tier 2)

These are Tier 3 (Enterprise) features — NOT in Tier 2:

- SAML / SSO
- RBAC (role-based access control)
- Compliance exports (SOC 2 report templates)
- Custom model fine-tuning
- On-prem with dedicated infrastructure
- Audit log > 90 days retention
- Admin dashboard web UI (Tier 2 gets CLI + YAML config)

---

## 7. Acceptance Criteria (summary)

| Feature | Acceptance |
|---------|------------|
| Team memory governance | Admin can disable publishing, set weight threshold, view shared namespace |
| Audit log | Every publish/remove/config change logged; exportable as CSV/JSON |
| Self-hosted | One-command Docker compose deploy; data persists across restarts |
| Seat management | Admin can add/remove seats; usage visible |
| Support | 48-hour SLA met in testing |

---

## 8. Pricing

| Tier | Price | Billing | Seats |
|------|-------|---------|-------|
| Free | $0 | n/a | 1 |
| Team | $29/user/mo | Annual contract | 5-50 |
| Enterprise | $79/user/mo | Annual, minimum 50 | 51+ |

---

*BRD complete. Next: TRD → Test Plan → DeepSeek QA → Kickoff prompt.*
