# Next Session Prompt — NeuralMind Licensing Management

Paste this into a new session:

---

## Session Goal

Build the NeuralMind licensing management system (autopilot) and push v1.0.0 to the public neuralmind repo — only after DeepSeek greenlights the architecture and a real Ed25519 keypair is generated.

## Current State (from last session)

**Tier 2 code:** Complete. 55 tests pass. E2E verified. All documentation written.
**Licensing autopilot:** Scaffolded. `signer.py`, `db.py`, `dashboard.py` written in `~/.autopilot/modules/licensing/`.
**Blocker:** Public key in `neuralmind/tier2/license.py` is a TEST placeholder (`0x...01`). Real keypair NOT generated yet.
**DeepSeek:** Dispatched analysis of licensing architecture. Results pending.
**No push to neuralmind** until licensing management is built + tested.

## Required Actions

### 1. Generate Ed25519 Keypair (one-time, take 30 seconds)

```bash
cd /home/dtfrost
python3 -c "from autopilot.modules.licensing.signer import *; pub_hex = generate_keypair(); print(f'Public key to embed in OSS: {pub_hex}')"
```

IMPORTANT: This generates `~/.autopilot/issuer_private.key` (chmod 600). BACK IT UP to a password manager or encrypted USB. Anyone with this key can issue licenses as you.

### 2. Replace public key placeholder

In `neuralmind/neuralmind/tier2/license.py`, replace:
```python
_ISSUER_PUBLIC_KEY_HEX = "0000000000000000000000000000000000000000000000000000000000000001"
```
with the actual public key generated in step 1.

### 3. Test the full loop

```bash
# Sign a test license (in autopilot/)
python3 -m autopilot.modules.licensing.signer --issue <EMAIL> --company "Test Co" --seats 15 --expiry 2027-07-19 --output /tmp/test_license.json

# Copy to neuralmind config
cp /tmp/test_license.json ~/.config/neuralmind/license.json

# Verify it validates
neuralmind --version
# Expected: neuralmind 1.0.0 (Team, 15 seats)

# Verify each command validates the license
neuralmind team license status
neuralmind team seats list
neuralmind team audit verify

# Revoke by changing the signature (make it invalid)
echo '{"tier":"team","seats":15,"issued_at":"2026-01-01T00:00:00Z","expires_at":"2027-01-01T00:00:00Z","issued_to":"<EMAIL>","signature":"invalid"}' > ~/.config/neuralmind/license.json
neuralmind --version
# Expected: error about expired or invalid license
```

### 4. Run the dashboard locally

```bash
cd /home/dtfrost/autopilot/modules/licensing
python3 dashboard.py
# Open http://127.0.0.1:5000/admin
# Try: issue a license via the web UI, check it shows in customers + audit log
```

### 5. DeepSeek QA on the full licenser system

Review these files together:
- `autopilot/modules/licensing/signer.py`
- `autopilot/modules/licensing/db.py`
- `autopilot/modules/licensing/dashboard.py`
- `neuralmind/tier2/license.py`

Dispatches per deepseek-qa skill (one subagent per file, inline code, patch diffs).

### 6. Greenlight public push

ONLY after:
- ✅ Ed25519 keypair generated, public key embedded in OSS
- ✅ Full sign → validate → revoke loop tested
- ✅ Dashboard issues real license that shows in UI
- ✅ DeepSeek QA on licenser returns 0 CRITICAL

---

## Files to load for context

| File | Why |
|------|-----|
| `~/.hermes/skills/tier2-dual-tier-license` | Tier architecture, anti-replication notes |
| `~/.hermes/skills/corporate-license-distribution` | Portal + PGP ladder, B2B procurement checklist |
| `~/.hermes/skills/deepseek-qa-phase-gate` | Dispatch pattern for QA |
| `neuralmind/neuralmind/tier2/license.py` | Current TEST public key needing replacement |
| `autopilot/modules/licensing/signer.py` | Ed25519 signing tool (already written) |
| `autopilot/modules/licensing/db.py` | SQLite schema (already written) |
| `autopilot/modules/licensing/dashboard.py` | Flask dashboard (already written) |

---

## What NOT to do

- ❌ Don't commit the autopilot repo (keep it private)
- ❌ Don't push neuralmind v1.0.0 until DeepSeek passes
- ❌ Don't embed a fake public key and pretend it works
- ❌ Don't use the TEST keypair `0x...01` in production — anyone can forge your licenses

---

## Success Criteria for This Session

- [ ] Real Ed25519 keypair generated at `~/.autopilot/issuer_private.key`
- [ ] Public key replaced in `neuralmind/neuralmind/tier2/license.py`
- [ ] Full sign → validate → install → revoke loop demonstrates correct behavior
- [ ] Dashboard at `:5000/admin` shows issued customer + audit log
- [ ] DeepSeek QA on licenser returns 0 CRITICAL findings
- [ ] Decision: greenlight or delay public push

---

## Background Decision: Free Tier Auto-Provisioning

Decision (made last session): Every install auto-issues a free license (`self-signed`, 1 seat, never expires) on first `neuralmind team` command. No separate code path — same validator. Paid tier swaps the file via Ed25519 signature from issuer keypair.

Revocation = non-renewal. No remote kill switch. Key expires, customer falls back to free.

---

## User Info

- Issuer: dfrostar (Darren Frost), Cheval-Volant LLC
- GitHub: dfrostar/neuralmind
- Target: Push v1.0.0 (no further delay beyond licensing gate)
- Business goal: Ship Team tier as revenue stream
- Risk tolerance: LOW — don't ship until DeepSeek + full e2e verified
