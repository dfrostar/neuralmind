# Lessons Learned — NeuralMind Team Tier Licensing Architecture

**Date:** 2026-07-19
**Duration:** 1 session (multi-day build with DeepSeek)
**Phase:** Team Tier v1.0.0 + Licensing Architecture Analysis

---

## 1. What Broke

| # | Issue | Impact | Time to Fix |
|---|-------|--------|-------------|
| 1 | Public key placeholder `0x...01` left in `license.py` | Anyone can forge licenses; OSS accepts any properly-formatted JSON | Discovered pre-launch; never fixed |
| 2 | email normalization bug in `seats.py` | `add_seat('Alice')` and `add_seat('alice')` created two seats against same person | 30 min (patch + test) |
| 3 | DeepSeek found missing `expires_at` validation edge case | Licenses with `expires_at='never'` should not expire — was correctly handled but not tested | 1 hour (add tests) |
| 4 | Autopilot dashboard `issue_license` used unverified customer email | Could issue license to anyone without payment verification | Discovered; deferred to webhook fix |
| 5 | No Stripe webhook signature verification | Anyone POSTing to webhook gets free license | Pre-launch blocker |

## 2. How It Was Fixed

| # | Issue | Fix | Verification |
|---|-------|-----|--------------|
| 1 | Placeholder key | **NOT YET FIXED** — this session | — |
| 2 | Email normalize | Lowercase before storage AND lookup in `SeatManager.add_seat`, `is_active_seat`, `remove_seat` | `test_tier2_seats.py` (7 tests pass) |
| 3 | Expires_at edge case | `_is_expired` checks `== 'never'` return False immediately | `test_license_valid`, `test_license_expired` pass |
| 4 | Unverified webhook | **NOT YET FIXED** — pending Stripe signature verification | — |
| 5 | Webhook security | **NOT YET FIXED** | — |

## 3. Root Causes

| # | Issue | Root Cause | Prevention |
|----|-------|------------|------------|
| 1 | Placeholder key still in code | Build sequence: Tier2 OSS built first, autopilot signer built second, keypair never generated because session ended at v1.0.0 tagging | **Generate keypair in same session as signer.py build** — never ship without it |
| 2 | Email duplicate seats | No normalization on `is_active_seat` or `remove_seat`, only on `add_seat` | Always write tests for BOTH paths (add + lookup + remove) before declaring "done" |
| 3 | DeepSeek caught `expires_at` gap in review | Developer assumed "it's checked" but didn't test the `'never'` edge case | Trust but verify: write a test for every branch you claim exists |
| 4 | Pre-launch security gaps | Built features in order: UX → backend → signing → compliance. GDPR and webhook security are LAST, after the "fun" parts | **Compliance is not a feature** — it's a launch gate. Run it in parallel with the first module, not after the last |

## 4. Process Improvements Identified

- [ ] **Compliance-first build order**: Privacy Policy + keypair generation = Day 1, not Day N. These are 30-second tasks that become blockers if deferred.
- [ ] **Keypair generation as part of signer module**: Signer `__init__` should FAIL if no key exists; don't let the module load in a "broken but silent" state.
- [ ] **Webhook signature verification = mandatory**: No webhook handler ships without `Stripe-Signature` check. This is table stakes, not a "hardening" task.
- [ ] **Audit log fields at creation**: `ip_address`, `user_agent`, `before_state`, `after_state` should be in the FIRST migration, not a later ALTER.
- [ ] **Lessons learned extraction at phase end, not project end**: This post-mortem should have been written before v1.0.0 was tagged, not after.
- [ ] **DeepSeek review of compliance risks**: The licensing analysis was incredibly valuable. This pattern (pre-build review of licensing/security/compliance architecture) should be standard for any paid tier.

## 5. New Skills Created

| Skill | Trigger | Why |
|-------|---------|-----|
| `gdpr-compliance-preflight` | "privacy policy", "GDPR", "compliance", "launch check" | SaaS teams launching paid tiers need a pre-flight checklist; recurring pattern across projects |
| `ed25519-key-management` | "generate keypair", "signing key", "Ed25519", "license signing" | Keypair generation, rotation, backup ceremony — reusable signing infrastructure pattern |
| `stripe-webhook-security` | "stripe webhook", "webhook signature", "payment webhook" | Webhook security is table stakes for any payment integration; recurring pattern |

## 6. Reusable Patterns

| Pattern | Where It Applies | How to Reuse |
|---------|-----------------|--------------|
| Ed25519 key separation (OSS holds public only) | Any OSS + paid tier (license signing, API key signing, update verification) | Load `ed25519-key-management` skill |
| Hash-chained audit log | Any system needing tamper evidence (license, config, financial) | Pattern from `audit.py` — use as template |
| OS-chdir umask bounding | Any directory creation needing exact permissions | From `self_hosted.py:init_data_dir` — reusable for secure tmp/file ops |
| DeepSeek pre-build compliance review | Any paid tier / B2B SaaS / licensing architecture | Load `deepseek-qa` with "compliance risk" scope |
| Dual-formatter CI gate (black + ruff) | Any Python repo with both formatters configured | Load `formatter-gate` skill |
| License JSON canonicalization (`sort_keys`, no whitespace) | Any signed-JSON-license pattern | From `license.py:_verify_signature` — prevents malleability |

## 7. Next Steps

- [ ] Generate real Ed25519 keypair now (30 seconds)
- [ ] Replace `_ISSUER_PUBLIC_KEY_HEX` placeholder in `license.py`
- [ ] Add Stripe webhook signature verification to autopilot dashboard
- [ ] Write Privacy Policy (GDPR-compliant, hosted at neuralmind.uk/privacy)
- [ ] Document key backup + rotation ceremony
- [ ] Add `ip_address` + `user_agent` + `before_state`/`after_state` to AuditLog schema
- [ ] Update SESSION-STATUS.md with completion evidence
- [ ] Schedule keypair regeneration ceremony in 12 months (calendar reminder)

---

## Notes

The DeepSeek licensing analysis was the single most valuable pre-launch action. It caught:
- No Privacy Policy (GDPR violation, €10M+ fines)
- No `expires_at` confirmation in OSS validator (confirmed present)
- No key rotation plan
- No Stripe webhook signature verification (CRITICAL — anyone can forge licenses)
- Pricing too high for unproven brand ($29 → $19-24 launch)
- Annual-only billing friction

Five of five were actionable. Four of five are still pending. The analysis paid for itself 100x over — the cost was one subagent dispatch, the avoided risk is existential.

This is the template for pre-launch review of any paid SaaS feature.
