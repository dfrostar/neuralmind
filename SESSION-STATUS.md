# SESSION-STATUS.md — Updated 2026-07-19 (Post-Rebuild + DeepSeek QA)

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
4. `nas-full-backup` — full system backup to NAS (hermes + neuralmind + autopilot)

### Lessons Learned
- **Location:** `/home/dtfrost/neuralmind/docs/LESSONS-LEARNED-LICENSING.md`

---

## Backup Status

| Artifact | GitHub (hermesdellbackup) | NAS (/mnt/media/backups/) |
|----------|--------------------------|--------------------------|
| Hermes state | ✅ encrypted, pushed | ✅ encrypted, synced |
| NeuralMind repo | ❌ | ✅ full copy (867MB) |
| Autopilot repo | ❌ | ✅ full copy (56KB) |

**Last backup:** 2026-07-19 12:49 UTC
**NAS free:** 762G / 916G

---

## Next Session Priorities

1. **Add IP + user_agent + before_state/after_state to AuditLog** — MEDIUM, ~1 hour
2. **14-day free trial flow** — HIGH, ~2 hours
3. **Monthly billing option ($34/mo)** — HIGH, ~2 hours
4. **YubiKey/encrypted key storage** — HIGH, ~1 hour
5. **Automated DB backup** — HIGH, ~1 hour
6. **Terms of Service** — MEDIUM, ~2 hours
7. **Right-to-deletion process** — MEDIUM, ~1 hour
8. **Stripe DPA** — LOW (Stripe provides template)

---

## Wave 6/7/8 Documentation (NEW — 2026-07-19)

### Wave 6 — Metrics CLI + Team Memory Integration
- **BRD:** `docs/WAVE6-BRD.md`
- **TRD:** `docs/WAVE6-TRD.md`
- **Commit:** `f31037a feat(v0.50.0): metrics CLI, /api/metrics endpoint, team memory integration test`
- **Acceptance:** `neuralmind metrics --summary` prints in <500ms, 10 integration tests pass

### Wave 7 — Impact Tool
- **BRD:** `docs/BRD-IMPACT-TOOL.md`
- **TRD:** `docs/TRD-IMPACT-TOOL.md`
- **Commit:** `63a0f3f feat(v0.52.0): impact tool — reverse-dependency blast-radius lookup`
- **Acceptance:** `neuralmind impact <symbol>` returns ranked blast-radius in <500ms

### Wave 8 — Autopilot Integration + Deploy
- **BRD:** `/home/dtfrost/neuralmind-autopilot/docs/WAVE8-BRD.md`
- **TRD:** `/home/dtfrost/neuralmind-autopilot/docs/WAVE8-TRD.md`
- **Commit:** `b6ad8e5 feat(v0.4.0): Wave 8 — integration tests + real deploy path + pause/resume`
- **Acceptance:** 56 tests pass (2 new integration tests), systemd timer enabled

---

## Doc-Code Coupling (NEW — 2026-07-19)

### What Changed
- `neuralmind/graphgen.py` — added `_add_doc_code_coupling()` function
- `neuralmind/doctor.py` — added `_check_doc_code_alignment()` check
- Schema version bumped: 1 → 2

### How It Works
- File-level document nodes link to file-level code nodes in the same directory
- Capped at 50 edges total to prevent noise explosion
- Confidence score 0.8 for same-directory coupling
- Doctor now reports: "526 doc files co-indexed with code (structural edges built)"

### Why
- Co-indexing (vector proximity) was already the default — 3,083 document + 1,718 rationale nodes alongside 4,245 code nodes
- But explicit `describes` edges make the doc→code relationship queryable as a first-class structural signal
- This is the leading practice: structural doc-code coupling + drift detection, not just "same vector space"

---

## DeepSeek QA — Wave 4 Team Memory (NEW — 2026-07-19)

### Files Reviewed
- `neuralmind/contribution_scoring.py` (E1)
- `neuralmind/merge_semantics.py` (E2)
- `neuralmind/peer_review.py` (E3)
- `neuralmind/team_staleness.py` (E4)

### Findings

| Severity | Count | Description |
|----------|-------|-------------|
| CRITICAL | 1 | E4 fast_decay compounding (post-fix regression) |
| WARNING | 1 | E4 `age_days` semantic aliasing |
| INFO | 1 | E2 `target_namespace` unused |

### Patches Applied
1. **team_staleness.py** — Fixed compounding decay: changed from `2^(-5 * days_past / 30)` (growing each pass) to `2^(-5 / 30)` constant per-pass factor. After 30 days: 0.03125 = exactly 1/32 as intended.
2. **team_staleness.py** — Clarified `age_days` comment: "Approximate edge age by staleness (synthetic lower bound)"
3. **merge_semantics.py** — Documented `target_namespace` as reserved for future use

### Test Verification
All **26 tests pass** after patching:
- `tests/test_contribution_scoring.py` (4 tests) ✅
- `tests/test_merge_semantics.py` (2 tests) ✅
- `tests/test_peer_review.py` (4 tests) ✅
- `tests/test_team_staleness.py` (6 tests) ✅
- `tests/test_team_memory_integration.py` (10 tests) ✅

---

## Index Health (NEW — 2026-07-19)

| Metric | Value |
|--------|-------|
| Total nodes | 11,432 |
| Code nodes | 4,245 |
| Document nodes | 3,083 |
| Rationale nodes | 1,718 |
| File-level doc nodes | 232 |
| File-level code nodes | 356 |
| Describes edges | 26 (capped at 50) |
| Schema version | 2 |
| Doc files co-indexed | 526 |
| Synapse edges | 0 (watcher not running) |
| Reduction ratio | 48.5x |

---

*All prior status (55 tests, e2e, docs, skills) still applies. See git log for full commit history.*
