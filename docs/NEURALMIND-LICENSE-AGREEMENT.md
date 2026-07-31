# NeuralMind Team License Agreement

**Version:** 1.0
**Effective Date:** 2026-07-30

---

## 1. Parties

This License Agreement ("Agreement") is between:

**Licensor:** Cheval-Volant LLC, a Texas limited liability company d/b/a NeuralMind ("Provider," "We," "Us")
**Licensee:** The entity identified in the License File ("Customer," "You," "Your")

---

## 2. License Grant

Subject to the terms of this Agreement and payment of applicable fees, Provider grants Customer a non-exclusive, non-transferable license to use NeuralMind Team ("Software") during the License Term.

---

## 3. License Scope

### 3.1 Seats
Customer may install and use the Software on up to the number of licensed seats specified in the License File.

### 3.2 Authorized Users
"Authorized Users" means employees or contractors of Customer who are authorized to access the Software under this Agreement.

### 3.3 Restrictions
Customer shall NOT:
- (a) Distribute, sublicense, or transfer the Software to third parties
- (b) Reverse engineer, decompile, or disassemble the Software (except as permitted by law)
- (c) Remove or alter proprietary notices
- (d) Use the Software to develop a competing product
- (e) Exceed the licensed seat count

---

## 4. License Term and Renewal

### 4.1 Term
The License Term is specified in the License File (1, 3, 6, 12, 24, or 36 months).

### 4.2 Expiration
Upon expiration:
- The Software will enter a 30-day grace period with reduced functionality
- After grace period, the Software will cease to function until renewed
- Customer data is preserved for 90 days post-expiration, then deleted

### 4.3 Renewal
Customer may renew by:
- Issuing a new license file with extended expires_at
- Paying the applicable renewal fee
- Accepting the then-current Agreement version

---

## 5. Fees and Payment

### 5.1 Pricing
Fees are based on:
- Number of licensed seats
- License term (monthly, quarterly, annual, biennial)
- Selected tier (Team)

### 5.2 Payment Terms
- Payment is due before license issuance
- All fees are non-refundable except as required by law
- Provider reserves the right to modify pricing with 30 days notice for renewals

---

## 6. Intellectual Property

Provider retains all intellectual property rights in the Software. This Agreement does not transfer any ownership rights to Customer.

---

## 7. Data and Privacy

### 7.1 Customer Data
Customer retains all rights to data they input into the Software.

### 7.2 Provider Data
Provider may collect anonymized usage statistics for product improvement.

### 7.3 Confidentiality
Both parties agree to protect confidential information disclosed under this Agreement.

---

## 8. Warranties and Disclaimer

### 8.1 Limited Warranty
Provider warrants that the Software will perform substantially as described in documentation for 30 days after issuance.

### 8.2 Disclaimer
EXCEPT AS STATED ABOVE, THE SOFTWARE IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND.

---

## 9. Limitation of Liability

TO THE MAXIMUM EXTENT PERMITTED BY LAW, PROVIDER SHALL NOT BE LIABLE FOR ANY INDIRECT, INCIDENTAL, SPECIAL, OR CONSEQUENTIAL DAMAGES.

---

## 10. Termination

### 10.1 Termination for Cause
Either party may terminate for material breach if the breach is not cured within 30 days.

### 10.2 Termination by Provider
Provider may terminate if:
- Customer exceeds licensed seat count
- Customer fails to pay fees
- Customer breaches restrictive covenants

### 10.3 Effect of Termination
Upon termination, Customer must cease using the Software and destroy all copies.

---

## 11. Governing Law

This Agreement is governed by the laws of the State of Texas, USA (Licensor’s registered jurisdiction — confirm venue with counsel before execution), without regard to conflict of law principles.

---

## 12. Miscellaneous

### 12.1 Entire Agreement
This Agreement constitutes the entire agreement between the parties.

### 12.2 Amendments
Provider may amend this Agreement with 30 days notice.

### 12.3 Severability
If any provision is found unenforceable, the remaining provisions remain in effect.

---

## 13. Acceptance

By installing or using the Software, Customer agrees to be bound by this Agreement.

**Agreement Version:** 1.0
**Last Updated:** 2026-07-30

---

## License File Format

When issuing a license, the following JSON file is delivered:

```json
{
  "tier": "team",
  "seats": 15,
  "issued_at": "2026-07-30T12:00:00+00:00",
  "expires_at": "2027-07-30T12:00:00+00:00",
  "issued_to": "Acme Corporation",
  "signature": "<ed25519_hex_signature>",
  "agreement_version": "1.0",
  "accepted_at": "2026-07-30T12:00:00+00:00",
  "license_id": "lic_<random_id>",
  "partner_id": "partner_<id>"
}
```

---

## CLI Commands

```bash
# Issue a new license
neuralmind issue-license \
  --customer "Acme Corporation" \
  --seats 15 \
  --term 12 \
  --output ./acme-license.json

# Renew a license
neuralmind renew-license \
  --customer "Acme Corporation" \
  --term 12

# Revoke a license
neuralmind revoke-license \
  --customer "Acme Corporation" \
  --reason "non-payment"

# Check status
neuralmind license-status --customer "Acme Corporation"

# List all licenses
neuralmind license-list
```

---

## Contact

For questions about this Agreement, contact: legal@neuralmind.uk
