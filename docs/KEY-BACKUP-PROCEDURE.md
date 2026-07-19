# Ed25519 Issuer Keypair — Backup & Recovery

**Generated:** 2026-07-19
**Key Fingerprint:** `d23aeb5ae460fede`
**Private key location:** `~/.autopilot/issuer_private.key` (chmod 600)
**Public key embedded in:** `neuralmind/neuralmind/tier2/license.py` (`_ISSUER_PUBLIC_KEY_HEX`)

---

## Backup Procedure

### Backup Copy #1 (Encrypted USB)

- Format a USB drive with LUKS encryption (minimum) or VeraCrypt
- Copy `~/.autopilot/issuer_private.key` to the encrypted drive
- Store in a physically secure location (fireproof safe, safety deposit box, or trusted offsite)
- Update quarterly: verify the backup is still readable
- Rotate annually: generate a new backup after 12 months of operation

### Backup Copy #2 (Paper — Cold Storage)

- Print the private key hex on archival paper
- Store in a sealed, tamper-evident envelope
- Label: "NeuralMind Issuer Private Key — CONFIDENTIAL"
- Store separately from the USB backup (different physical location)

### Backup Verification (Quarterly)

```bash
# Verify backup matches current key
diff ~/.autopilot/issuer_private.key <(cat /media/encrypted-usb/issuer_private.key)
# Expected: no output (files identical)

# Verify public key derivation still matches
python3 -c "
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
priv_hex = open('/home/dtfrost/.autopilot/issuer_private.key').read().strip()
priv = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(priv_hex))
pub_hex = priv.public_key().public_bytes_raw().hex()
assert pub_hex == '62a59c47bdef4c3b9dfeea6a74c90d42f966157f6d0969310ea7deb3bfcd365b'
print('Key integrity verified')
"
```

---

## Recovery Procedure

### Scenario A: Machine Failure (Private Key Intact on Backup)

1. Set up new machine, install OS
2. Restore `~/.autopilot/issuer_private.key` from USB backup
3. Verify: `chmod 600 ~/.autopilot/issuer_private.key`
4. Verify key integrity: derive public key, confirm matches embedded key
5. Resume operations — no customer impact

### Scenario B: Both Primary Key AND All Backups Lost

1. Acknowledge disaster: all existing licenses are now unverifiable until key is replaced
2. Generate new keypair (see "Rotation Ceremony" for dual-key approach)
3. Embed BOTH old and new public keys in OSS `license.py`
4. Re-sign all active licenses with new key
5. Push OSS update with new public key
6. Customers re-download updated licenses from portal
7. After all old licenses expire, remove old public key from OSS
8. Notify customers of rotation via email

### Scenario C: Key Suspected Compromised

1. Immediately rotate key per "Rotation Ceremony" below
2. Re-sign ALL licenses (revoke all licenses signed with old key)
3. Issue new licenses to all active customers
4. Push OSS update with new key
5. Investigate breach vector
6. If customer data was exposed, follow GDPR breach notification (72 hours)

---

## Rotation Ceremony (Scheduled or Emergency)

**When:** Every 24 months OR immediately upon suspected compromise OR operator departure

**Procedure:**

```python
# Step 1: Generate new keypair (use generate_issuer_keypair() from signer.py)
# Step 2: Embed BOTH keys in license.py
_ISSUER_PUBLIC_KEY_CURRENT = "new_key_here"     # For new licenses
_ISSUER_PUBLIC_KEY_PREVIOUS = "old_key_here"    # Validate existing licenses

# Step 3: In _verify_signature, try both keys
def _verify_signature(self, lic):
    for pk in [self.public_key_hex, os.environ.get("ISSUER_PUBLIC_KEY_PREVIOUS", "")]:
        if not pk:
            continue
        try:
            # verify with pk
            return True
        except:
            continue
    return False

# Step 4: Re-issue all active licenses with new key
# Step 5: After max_license_duration, remove ISSUER_PUBLIC_KEY_PREVIOUS from OSS
```

**Audit log entry:**
```
action: key_rotated
old_fingerprint: d23aeb5ae460fede
new_fingerprint: <new>
licenses_resigned: <count>
reason: scheduled_rotation | compromise | operator_change
```

---

## Break-Glass: Operator Unavailable

If the sole operator (dfrostar) becomes unavailable:

1. **Designated successor:** Contact [your designated person here]
2. **Key access:** Keypair backup location is documented separately (not in this file for security)
3. **OSS key update:** Follow CONTRIBUTING.md to submit a PR replacing `_ISSUER_PUBLIC_KEY_HEX` in `license.py`
4. **Emergency contact for GitHub:** [your backup method here]
5. **Customer notification:** Post an issue on the neuralmind GitHub explaining the situation and expected response time

---

## Security Rules

1. **NEVER** commit the private key to git (even accidentally)
2. **NEVER** store the private key in cloud storage without client-side encryption
3. **NEVER** email the private key to anyone
4. **NEVER** share the private key with customers or community members
5. **ALWAYS** verify the backup restores correctly after creation
6. **ALWAYS** log key operations in the audit log

---

## Key Fingerprint Verification

Before signing any license, verify the loaded key matches the expected fingerprint:

```python
import hashlib
pub_hex = "62a59c47bdef4c3b9dfeea6a74c90d42f966157f6d0969310ea7deb3bfcd365b"
assert hashlib.sha256(pub_hex.encode()).hexdigest()[:16] == "d23aeb5ae460fede"
```
