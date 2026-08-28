# Billing Runbook — quote to cash, manually

How a Team deal actually gets from an inbound email to a signed license
file on the customer's machine.

**There is no payment processor integrated, and that is deliberate.** Team
is $29/user/mo across 5–50 seats on an annual contract — $1,740 to $17,400
a year per deal, sold by email. That is a signed-contract motion, not a
self-serve one, and a checkout page would be machinery serving nobody until
inbound volume justifies it. The pluggable payment broker is on
[ROADMAP.md](../../ROADMAP.md); the licence portal is deferred until 3+
customers (see the honest-scope table in
[Tier2-Operator-Guide](Tier2-Operator-Guide.md)).

Until then this page *is* the billing system. Every step below is either a
command in this repo or a click in a tool you already have.

> Canonical terms — entity, price, contact — live in
> [`commercial-terms.json`](../../commercial-terms.json) and are CI-gated.
> If a number here ever disagrees with that file, the file wins and this
> page is the bug.

---

## Prerequisites (once, before the first deal)

| What | Where | Check |
|------|-------|-------|
| Issuer private key | `NEURALMIND_ISSUER_PRIVATE_KEY_HEX` in your shell, never in the repo | The snippet below prints `MATCH` |
| Its public half | Already embedded in the shipped package (`neuralmind/tier2/license.py`, fingerprint `d23aeb5ae460fede`) | — |
| An invoicing tool | Stripe Invoicing, Wave, or your accountant's system — dashboard only, no integration | You can send an invoice from the entity's name |
| Sales-tax position | Confirmed with your accountant, not guessed | See [Tax](#tax-confirm-before-the-first-invoice) |

Confirm your private key is the one the shipped package will verify
against — a mismatch here means every licence you issue fails activation:

```bash
python -c "
import os
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from neuralmind.tier2.license import _ISSUER_PUBLIC_KEY_HEX
pub = Ed25519PrivateKey.from_private_bytes(
    bytes.fromhex(os.environ['NEURALMIND_ISSUER_PRIVATE_KEY_HEX'])
).public_key().public_bytes_raw().hex()
print('MATCH' if pub == _ISSUER_PUBLIC_KEY_HEX else f'MISMATCH: {pub}')
"
```

The private key is the single point of failure for every paid customer:
lose it and nobody can be renewed, leak it and anyone can mint licences
against a public key that is already inside every installed copy. Keep it
offline, keep a backup, and treat rotation as a planned exercise —
`LicenseValidator` accepts a *list* of public keys precisely so a rotation
can overlap.

---

## The path

### 1. Qualify

Team buys **seats beyond one (5–50), priority support, and an annual
invoice**. It does not unlock features — governance, audit and self-hosted
all run on the free 1-seat licence. So the honest opener is: *evaluate
everything first, on the free tier, then buy seats when you have more than
one person.*

Under 5 seats, there is nothing to sell. Say so.

### 2. Quote

Prices come from the pricing table, not from memory:

```bash
python -c "
from neuralmind.tier2.pricing import load_pricing, calculate_price
p = load_pricing()
print(calculate_price(p, 'team', seats=12, term_months=12))
"
```

`calculate_price` returns the total for **all seats over the whole term**.
Twelve seats on an annual term is `29 × 12 × 12 = $4,176`. There are no
volume discounts in the table and none should be invented in an email — if
a discount is genuinely warranted, change the table and say why.

### 3. Agreement

Send [`LICENSE-COMMERCIAL.md`](../../LICENSE-COMMERCIAL.md) as the
template. It has to be executed before a licence is issued — the licence
file records an `agreement_version` and an `accepted_at` timestamp on the
assumption that it was.

### 4. Invoice

Raise the invoice in your invoicing tool, from **Cheval-Volant LLC (d/b/a
NeuralMind)**, Texas. Net terms are yours to set; annual-in-advance is what
the tier is built around.

Nothing in this repo generates, sends, or reconciles an invoice. Do not
issue the licence yet.

### 5. Issue — only after payment clears

```bash
export NEURALMIND_ISSUER_PRIVATE_KEY_HEX=...   # from your password manager

neuralmind license issue \
  --customer "Acme Corp" \
  --seats 12 \
  --term 12 \
  --output ./acme-corp.json
```

Terms accepted: 1, 3, 6, 12, 24, 36 months. Expiry lands on the calendar —
a 12-month term issued on 28 August expires on 28 August the following
year.

This writes the signed licence, appends an `issue` record to the audit log,
and records the customer in `~/.neuralmind/customers.yaml` with
`total_paid`. That YAML file is your entire customer database right now;
it lives on one machine and nothing backs it up. Copy it somewhere durable.

### 6. Deliver

Send the customer the JSON file and the two commands that consume it:

```bash
neuralmind team license activate ./acme-corp.json
neuralmind team license status          # confirms tier, seats, expiry
```

Then seats, which they administer themselves:

```bash
neuralmind team seats add someone@acme.com
neuralmind team seats list
```

If activation reports anything other than the expected tier and seat count,
the file was altered in transit — reissue rather than debug it.

### 7. File

Keep, alongside the invoice: the executed agreement, the `license_id` from
step 5, and the seat count. `~/.neuralmind/audit_log.jsonl` is the
append-only record of every issue, renew and revoke, and it is the thing
you would hand an auditor.

---

## Renewals

**Nothing warns you that a licence is expiring.** No cron, no email, no
dashboard. Until that exists, this is a calendar reminder plus one command:

```bash
neuralmind license list                          # all customers, status, expiry
neuralmind license status --customer "Acme Corp" # includes days_remaining
```

Run it monthly. Anything inside 60 days gets a renewal conversation; invoice
and collect exactly as above, then:

```bash
neuralmind license renew --customer "Acme Corp" --term 12
```

Renewal extends from the **old expiry**, not from today, so a customer who
pays late does not silently gain free months — and one who pays early does
not lose any.

A revoked licence cannot be renewed. Issue a new one.

---

## Non-payment

```bash
neuralmind license revoke --customer "Acme Corp" --reason "non-payment, 60d past due"
```

This sets expiry to now and writes the reason to the audit log. It is not
reversible by renewal, so use it when the relationship is actually over, not
as a dunning nudge — for a late invoice, chase the invoice.

---

## Tax — confirm before the first invoice

A Texas LLC invoicing software subscriptions, potentially to customers in
the EU and UK, has a sales-tax and VAT position to establish. This is an
accountant question, not a code question, and it is much cheaper to answer
before the first invoice than to unwind afterwards. Nothing in this repo
computes or collects tax.

---

## What not to promise

From the `do_not_market` list in
[`commercial-terms.json`](../../commercial-terms.json):

- **No trials.** There is no trial issuance mechanism. The free 1-seat
  tier is the evaluation path, and it never expires — that is the answer to
  "can we try it first?"
- **SSO / SAML** and **real-time cross-machine sync** are roadmap only.
  Label them as roadmap or leave them out.
- **No self-serve checkout.** The CTA is contact-based, and the pricing
  page says so.

---

## Known gaps

| Gap | Consequence today |
|-----|-------------------|
| No payment processor | Invoicing and reconciliation happen entirely outside this repo |
| No renewal alerting | A licence can lapse unnoticed; the monthly check above is the mitigation |
| Customer record is one YAML file on one machine | No backup, no history, no second operator |
| No receipts or dunning | Both are the invoicing tool's job |
| No self-serve seat purchase | Seat count changes mid-term mean a reissue and a conversation |

The first of these to hurt should be the first one built — most likely
renewal alerting, since it is the one that loses revenue silently.

---

## See also

- [Tier2-Operator-Guide](Tier2-Operator-Guide.md) — the customer-facing Team commands
- [Upgrade-Guide](Upgrade-Guide.md) — the free → Team flow from the user's side
- [`commercial-terms.json`](../../commercial-terms.json) — canonical pricing and entity
- [`LICENSING.md`](../../LICENSING.md) — the MIT / commercial boundary
