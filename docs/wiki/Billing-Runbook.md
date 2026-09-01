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
  --term 12
```

The licence is written to `~/.neuralmind/<sanitized-customer-name>.json` —
for the above, `~/.neuralmind/acmecorp.json`. **Licences are only ever
written inside `~/.neuralmind`.** `--output` can rename or relocate the file
*within* that directory; a path outside it is refused, because the same
guard stops a hostile customer name from escaping storage. Copy the file out
afterwards if you want it elsewhere.

Terms accepted: 1, 3, 6, 12, 24, 36 months. Expiry lands on the calendar —
a 12-month term issued on 28 August expires on 28 August the following
year.

This also appends an `issue` record to the audit log and records the
customer in `~/.neuralmind/customers.yaml` with `total_paid`. That YAML file
is your entire customer database right now; it lives on one machine and
nothing backs it up. Copy it somewhere durable.

### 6. Deliver

Send the customer that JSON file and the two commands that consume it:

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

A lapsed licence is revenue lost quietly, so this is the one part of the
path that does not rely on you remembering:

```bash
neuralmind license expiring              # anything due inside 60 days
neuralmind license expiring --within 90  # widen the window
```

It is read-only and needs **no issuer key**, so a scheduler can run it
without holding anything sensitive.

### Wiring it to a scheduler

The command is built to be consumed rather than read: the exit code alone
says whether anyone needs to act, so a caller never has to parse output to
decide whether to raise an alert.

| Exit | Meaning | What a scheduler should do |
|-----:|---------|----------------------------|
| 0 | Nothing due inside the window | Nothing |
| 6 | Renewals due | Notify — a conversation needs starting |
| 7 | Something already expired, or an expiry that cannot be read | Escalate — revenue or data is already broken |

`--quiet` prints nothing on exit 0, which is what makes it well behaved in
cron (silence unless there is news). `--json` emits the full report —
`expired`, `expiring` and `unknown` buckets, each sorted most-urgent first,
with `days_remaining` per customer — for anything that wants to route by
severity or render its own message.

Cron already mails whatever a job writes to stdout, so `--quiet` is the
whole recipe — no output on a clean week, a report when there is one:

```bash
MAILTO=you@example.com
0 9 * * 1  neuralmind license expiring --quiet
```

If you would rather call `mail` yourself, capture the report first. Piping
straight off `||` sends an empty message, because the report went to stdout
and `mail` inherits cron's empty stdin:

```bash
0 9 * * 1  report=$(neuralmind license expiring --quiet) || printf '%s\n' "$report" | mail -s "NeuralMind renewals" you@example.com
```

Exit 7 also covers a record whose `expires_at` cannot be parsed. That is
deliberate: an expiry you cannot read is not a licence you can trust to
alert on, so it escalates rather than passing silently.

### Doing the renewal

Anything the report names gets a renewal conversation; invoice and collect
exactly as above, then:

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
| No alert *delivery* | `license expiring` reports and signals via exit code, but nothing here sends the mail — a scheduler or autopilot owns delivery |
| Customer record is one YAML file on one machine | No backup, no history, no second operator |
| No receipts or dunning | Both are the invoicing tool's job |
| No self-serve seat purchase | Seat count changes mid-term mean a reissue and a conversation |

Renewal alerting used to head this list, because it was the one that lost
revenue silently; `license expiring` closes it. Of what remains, the
single-file customer record is the most exposed — one machine, no backup,
no second operator.

---

## See also

- [Tier2-Operator-Guide](Tier2-Operator-Guide.md) — the customer-facing Team commands
- [Upgrade-Guide](Upgrade-Guide.md) — the free → Team flow from the user's side
- [`commercial-terms.json`](../../commercial-terms.json) — canonical pricing and entity
- [`LICENSING.md`](../../LICENSING.md) — the MIT / commercial boundary
