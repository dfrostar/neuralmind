# Privacy Policy — NeuralMind

**Effective Date:** July 19, 2026
**Last Updated:** July 19, 2026

---

## 1. Data Controller

Cheval-Volant LLC (operating as NeuralMind)
Operator: Darren Frost (dfrostar)
Email: <EMAIL>
Location: Texas, USA

For all inquiries regarding this Privacy Policy or your personal data, contact: <EMAIL>

---

## 2. Data We Collect

### 2.1 Data You Provide
- **Email address** — when you purchase a Team tier license or create an account
- **Company name** — optional, when associated with a license
- **Seat assignments** — email addresses of team members you add to your license (each member can request deletion)

### 2.2 Data Collected Automatically
- **IP address** — recorded in audit logs when you interact with our systems (license issuance, management actions)
- **User agent** — recorded when you access the license portal via browser
- **Stripe customer ID** — stored after purchase for payment reconciliation
- **License metadata** — tier, seats, expiry, signature hash (stored for license validation)

### 2.3 Data We Do NOT Collect
- No payment card data (handled entirely by Stripe)
- No usage data from the OSS tool (NeuralMind OSS operates entirely locally)
- No telemetry, analytics, or tracking pixels
- No cookies except session cookies for portal authentication

---

## 3. Legal Basis for Processing (GDPR Article 6)

We process your personal data under the following legal bases:

| Purpose | Legal Basis |
|---------|-------------|
| License issuance and renewal | Performance of contract (6.1.b) |
| Audit logging (IP, actor, action) | Legitimate interest — fraud prevention, security, dispute resolution (6.1.f) |
| Billing and payment processing | Performance of contract (6.1.b) |
| Customer support | Performance of contract (6.1.b) |
| GDPR/similar regulation compliance | Legal obligation (6.1.c) |

For users in the EU/EEA: You have the right to object to processing based on legitimate interest. Contact <EMAIL> to discuss.

---

## 4. Why We Process Your Data

| Data | Purpose |
|------|---------|
| Email | License identification, renewal reminders, security alerts |
| Company name | License attribution (optional) |
| Stripe customer ID | Payment reconciliation, subscription management |
| IP address (audit logs) | Security monitoring, dispute resolution, fraud prevention |
| License metadata | License validation, renewal processing |

We do NOT use your data for marketing without separate consent.

---

## 5. Data Retention

| Data Category | Retention Period |
|---------------|------------------|
| Active license data | Duration of license + 3 years after expiry |
| Audit logs (with IP) | 3 years after creation, then anonymized |
| Financial records (Stripe) | 7 years (required for tax compliance) |
| Deleted customer records | Anonymized immediately; financial records retained per above |

After the retention period, we anonymize (not delete) financial records to comply with tax law, and delete personal data entirely.

---

## 6. Third-Party Processors (Sub-Processors)

We use the following processors to deliver our service:

| Processor | Data Accessed | Purpose | DPA Available |
|-----------|---------------|---------|---------------|
| **Stripe** | Email, payment data, billing address | Payment processing, subscription management | https://stripe.com/privacy |
| **GitHub** | Username (via GitHub login, if used) | Community forum, issue tracking | https://docs.github.com/en/site-policy |

We do not share your data with any other third parties. We do not sell your data. We do not use your data for advertising.

If a new sub-processor is added, we will update this Policy and notify existing customers via email 30 days before the new processor begins processing.

---

## 7. International Data Transfers

Your data is processed in the United States (where we and Stripe operate). For EU/EEA residents:

- Stripe relies on Standard Contractual Clauses (SCCs) for EU-US data transfers
- We rely on SCCs where required for any supplemental data flows
- Post-Schrems II, data transfers to the US are a legal gray area — consult your legal advisor if this concerns you

We will migrate to EU-hosted infrastructure if EU revenue becomes a significant portion of total revenue.

---

## 8. Your Rights (GDPR Articles 15-22)

You have the right to:

1. **Access** — Receive a copy of your personal data
2. **Rectification** — Correct inaccurate data
3. **Erasure ("right to be forgotten")** — Request deletion of your personal data
4. **Restriction** — Request we limit processing in certain circumstances
5. **Portability** — Receive your data in a structured, machine-readable format
6. **Object** — Object to processing based on legitimate interests
7. **Withdraw consent** — Where processing relies on consent, withdraw at any time

**To exercise any right:** Email <EMAIL>. We respond within 30 days.

**Deletion process:**
1. We verify your identity
2. We delete your Customer record
3. We anonymize (not delete) LicenseIssuance records — financial/tax records must be retained
4. We delete AuditLog entries containing your personal data
5. We confirm completion via email

**Exception:** Financial records (Stripe customer ID, license hash, signature, transaction amount) are retained in anonymized form for 7 years per US tax law (26 USC 6501).

---

## 9. Cookie Policy

The license portal uses one session cookie (`session`) for authentication:

- **Purpose:** Maintain your logged-in session during portal use
- **Type:** Strictly necessary (session cookie, no tracking)
- **Duration:** Session-only (deleted when browser closes)
- **Third parties:** None

We do NOT use analytics cookies, advertising cookies, or social media cookies. No cookie consent banner is required because all cookies are strictly necessary for service delivery.

If we add analytics in the future, we will update this Policy and implement a cookie consent mechanism.

---

## 10. Security

We implement the following security measures:

- **Ed25519 signing** for license integrity (cryptographic proof of issuance)
- **Hash-chained audit logs** (tamper-evident: any modification breaks the chain)
- **Encrypted key storage** for signing keys (private key never stored in repo)
- **Stripe** for all payment processing (PCI-DSS Level 1 certified)
- **SQLite with WAL mode** for local data durability
- **All data in transit** encrypted via TLS 1.3

We will notify affected customers within 72 hours of becoming aware of a personal data breach, as required by GDPR Article 33.

---

## 11. Children's Privacy

NeuralMind is a developer tool. We do not knowingly collect data from anyone under 16. If you believe a child under 16 has provided personal data, contact <EMAIL> for immediate deletion.

---

## 12. Changes to This Policy

We may update this Policy to reflect legal, technical, or business changes. We will:

- Update the "Last Updated" date at the top
- Notify existing customers via email 30 days before material changes take effect
- Post the updated Policy at this same URL

Non-material changes (clarifications, formatting) take effect on posting.

---

## 13. Contact

**Data Controller:** Cheval-Volant LLC / NeuralMind
**Email:** <EMAIL>
**GitHub:** https://github.com/dfrostar/neuralmind
**Response time:** Within 72 hours for data inquiries; 30 days for formal rights requests

**Right to lodge complaint:** If you are in the EU/EEA and believe we have violated your rights, you have the right to lodge a complaint with your local Data Protection Authority.

---

## 14. Terms of Service

This Policy works in conjunction with our Terms of Service. Together they form the basis for how we handle your data and your rights and obligations as a customer.

---

*This Privacy Policy is for informational purposes and is not legal advice. Consult a qualified attorney for legal advice specific to your jurisdiction.*
