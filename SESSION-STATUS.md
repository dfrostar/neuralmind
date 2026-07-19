# SESSION-STATUS.md — Updated 2026-07-19 (Post-DeepSeek)

## Latest DeepSeek Analysis

Full report: `/home/dtfrost/neuralmind-licensing-analysis.md`

### Critical Findings Summary

**DeepSeek verdict:** Architecture is sound for solo OSS. Build it, but fix gaps first.

| Area | Finding | Action |
|------|---------|--------|
| **Key storage** | Raw hex on disk. YubiKey or encrypted keyfile needed. | Use YubiKey or encrypt with passphrase |
| **Key rotation** | No plan. If compromised, all licenses forgeable. | Document rotation ceremony NOW |
| **Privacy Policy** | **GDPR violation if missing.** Fines start at €10M. | Write before ANY EU customer |
| **Pricing** | $29/user/mo is aggressive for unproven brand. | Launch at $19-24, raise after case studies |
| **Billing** | Annual-only creates friction. | Offer monthly at $34/mo + annual discount |
| **Free trial** | No trial = broken funnel. | 14-day free trial, no credit card |
| **expires_at** | If OSS doesn't check it, licenses work forever. | CONFIRMED: `tier2/license.py` DOES check |
| **Webhook security** | Stripe webhook must verify signature. | Add `Stripe-Signature` verification |
| **Kill switch** | DeepSeek says don't build it. Conflicts with OSS + bypassable. | Document: non-renewal is sufficient |
| **Single point of failure** | Entire system depends on dfrostar. | Document backup procedure + break-glass |

### Recommended Pricing Adjustment

DeepSeek suggests: **$19-24/user/mo annual, $34/mo monthly**. Was: $29 annual only.

### Compliance Requirements Before Launch

1. Privacy Policy (publish at neuralmind.uk/privacy) — DONE
2. Terms of Service
3. Right-to-deletion process
4. Stripe DPA (Stripe provides this)
5. Cookie consent if portal uses analytics

### Audit Log Enhancement

Add to `AuditLog`:
- `ip_address` of actor
- `user_agent` (if via portal)
- `before_state` / `after_state` (JSON)

---

## Updated Task List

| Task | Priority | Status |
|------|----------|--------|
| Generate Ed25519 keypair | CRITICAL | **DONE** |
| Replace public key placeholder | CRITICAL | **DONE** |
| Write Privacy Policy | CRITICAL | **DONE** |
| Add Stripe signature verification | CRITICAL | **DONE** |
| Key rotation document | HIGH | **DONE** |
| Add IP + user_agent to AuditLog | MEDIUM | Pending |
| 14-day free trial | HIGH | Pending |
| Monthly billing option | HIGH | Pending |
| YubiKey/encrypted key storage | HIGH | Pending |
| Automated DB backup | HIGH | Pending |

---

## Completion Evidence

### Ed25519 Keypair
- **Fingerprint:** `d23aeb5ae460fede`
- **Private key:** `~/.autopilot/issuer_private.key` (chmod 600)
- **Public key in OSS:** `neuralmind/neuralmind/tier2/license.py` line 31
- **Canonical test:** Issued `<EMAIL>` license → validated as `VALID` → confirmed sign→verify loop works

### Privacy Policy
- **Location:** `/home/dtfrost/neuralmind/docs/PRIVACY-POLICY.md`
- **Coverage:** GDPR Articles 6, 15-22, 33; DPA reference; right-to-deletion process; data retention; sub-processor disclosure; international transfer disclosure; cookie policy; security measures

### Stripe Webhook Security
- **Location:** `/home/dtfrost/autopilot/modules/licensing/dashboard.py` `/stripe/webhook`
- **Verified:** `stripe.Webhook.construct_event()` with `STRIPE_WEBHOOK_SECRET` env var
- **Idempotency:** Event ID dedup via `_PROCESSED_EVENT_IDS` set
- **Error handling:** Specific `ValueError` and `SignatureVerificationError` (no catch-all)
- **Events handled:** `checkout.session.completed`, `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.payment_failed`

### Key Backup Procedure
- **Location:** `/home/dtfrost/neuralmind/docs/KEY-BACKUP-PROCEDURE.md`
- **Contents:** Backup copy locations (USB + paper), quarterly verification, rotation ceremony, break-glass, recovery scenarios

### New Skills Created
1. `gdpr-compliance-preflight` — pre-launch GDPR checklist for SaaS
2. `ed25519-key-management` — keypair lifecycle for OSS signing
3. `stripe-webhook-security` — secure payment webhook handling

### Lessons Learned
- **Location:** `/home/dtfrost/neuralmind/docs/LESSONS-LEARNED-LICENSING.md`

---

*All prior status (55 tests, e2e, docs, skills) still applies. See git log for full commit history.*
