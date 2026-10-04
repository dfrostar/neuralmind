# Tier 2 Operator Guide — NeuralMind

**Last updated:** 2026-07-22  
**Version:** v1.7.0  
**Audience:** Operators who just ran `neuralmind onboarding` or `neuralmind wakeup .`

---

## What Tier 2 (Team) gives you

Tier 2 is the paid tier on top of the MIT core. **The MIT core's 12-50x token reduction is free forever**, and the tier2 feature set — governance, audit, self-hosted — runs under the auto-issued free 1-seat license too. A paid Team license buys **seats beyond one (5-50), priority support, and an annual invoice**, not hidden features.

| Feature | Free license (1 seat) | Team ($29/user/mo, 5-50 seats) |
|---------|-----------------------|--------------------------------|
| 12-50x token reduction | Yes | Yes |
| Synapse learning | Yes | Yes |
| MCP server | Yes | Yes |
| Memory publish/inherit | Yes | Yes |
| Governance (publish scope, weight threshold) | Yes, at 1 seat | Yes |
| Audit log (SHA-256 hash-chained) | Yes, at 1 seat | Yes |
| Self-hosted deployment | Yes, at 1 seat | Yes, with deployment support |
| Seats beyond one | No | Yes (up to 50) |
| Priority support + annual invoice | No | Yes |
| License validation (Ed25519 + 30-day grace) | Auto-issued free license | Signed Team license |

**You are paying for seats and support, not for features — everything is evaluable free at 1 seat.**

---

## Quick Start (first 5 minutes)

1. **Install + activate free tier:**
   ```bash
   pip install neuralmind
   cd /path/to/your-project
   neuralmind build .
   neuralmind wakeup .          # auto-issues free license
   ```

2. **Run the onboarding wizard:**
   ```bash
   neuralmind onboarding --quick   # skip prompts, defaults only
   ```
   Or just `neuralmind onboarding` for interactive mode. Walks through license activation, governance defaults, admin emails, and seat audit.

3. **Verify:**
   ```bash
   neuralmind team license status
   neuralmind team seats list
   ```

---

## Tier 2 Commands

### License

```bash
neuralmind team license status       # current tier, seats, expiry, issued-to
neuralmind team license activate <file>   # activate with Ed25519-signed license
```

The signed licence file comes from the vendor. If you are the vendor, the
issuing side — quoting, invoicing, `neuralmind license issue`, renewals —
is the [Billing Runbook](Billing-Runbook.md).

### Seats

```bash
neuralmind team seats list            # list all seats
neuralmind team seats add <email>     # invite a seat (idempotent, soft-delete aware)
neuralmind team seats remove <email>  # remove a seat (soft-delete)
```

### Governance

```bash
neuralmind team governance status
neuralmind team governance set-scope <personal|shared|both> --admin <email>
neuralmind team governance set-weight-threshold <0.0-1.0> --admin <email>
neuralmind team governance set-governance-enabled <true|false> --admin <email>
neuralmind team governance list-shared [--project PATH] [--json]
neuralmind team governance remove-edge SOURCE TARGET [--project PATH] --admin <email>
```

What each setting does *(enforced since v4.6.0; earlier versions recorded
scope and threshold without enforcing them)*:

| Setting | Effect on `neuralmind memory publish` |
|---|---|
| `set-scope personal` | Publishing is refused (exit 1): memory stays on each machine |
| `set-scope shared` | Only the team baseline (the `shared` namespace) is published |
| `set-scope both` *(default)* | Personal + shared memory is published |
| `set-weight-threshold 0.1` *(default)* | Synapse edges below the threshold are left out of the bundle (transitions aren't weight-filtered) |
| `set-governance-enabled false` | The scope and threshold gates are off; events are still audited |

Settings live in `~/.config/neuralmind/tier2.yaml` (per user, not per
repository). A config that exists but can't be read (unreadable, malformed
YAML, an invalid value) makes publish refuse rather than publish ungoverned
memory.

`remove-edge SOURCE TARGET` stops sharing one association: it is deleted from
the project's `shared` memory and review queue, dropped from
`.neuralmind-team-memory.json` and listed under that file's `retracted` key.
Commit the file: each teammate's next session deletes the pair from their own
shared memory, and no later publish re-adds it. `list-shared` shows what is in
shared memory now, strongest first. Walkthrough:
[Govern what your team's agents share](../use-cases/govern-team-memory.md).

### Audit

```bash
neuralmind team audit list            # recent audit events
neuralmind team audit export --format csv|json --output <file>
neuralmind team audit verify          # verify SHA-256 hash chain integrity
```

Recorded: governance configuration changes, seat and license actions, and
(since v4.6.0) every team-memory `publish` (including refused ones), `import`
of a teammate's bundle, `review_approve` / `review_reject`, and `remove`. The
actor is `NEURALMIND_ACTOR_EMAIL` (or `--admin` for admin commands), else the
repository's `git config user.email`.

### Self-hosted

```bash
neuralmind team self-hosted init      # initialize self-hosted data dir (0700 perms)
neuralmind team self-hosted status
neuralmind team self-hosted validate-license
```

---

## Honest scope (what Tier 2 does NOT do yet)

| Claim | Status | Honest framing |
|-------|--------|----------------|
| SSO/SAML/OIDC | Not shipped | PRD-scoped for future wave |
| Real-time cross-machine sync | Not shipped | Paid tier future |
| Customer self-serve dashboard | Not shipped | Decide later |
| License portal | Deferred | D12: defer until 3+ customers — the manual path is the [Billing Runbook](Billing-Runbook.md) |

**Do not market Tier 2 as SSO-enabled or multi-machine-synced.** Architecture is ready; features are not shipped.

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| "License not found" | `neuralmind wakeup .` auto-issues free tier on first run |
| "Downgrade guard triggered" | Fresh `tier2.yaml` should have `tier: free` (v1.7.0+). If not, delete and re-`wakeup` |
| "Seat limit exceeded" | `neuralmind team seats remove <email>` to free a seat |
| "Audit log empty" | Events fire on governance, seat and license operations and on team-memory publish/import/review/removal — and only once a tier2 config exists (`neuralmind onboarding`) |
| "Self-hosted data dir permission denied" | `neuralmind team self-hosted init` sets 0700 permissions |

---

## When to skip Tier 2

- Under 5K lines, free-tier, inline-only, prompt-caching already covering you
- No compliance/audit requirements
- Solo developer (1-seat free tier is sufficient)

The honest boundary is documented on the NeuralMind site at
https://neuralmind.uk/effectiveness/ — free-tier users whose codebases
fall below the sweet spot should verify their own reduction ratio
before purchasing.

---

*Wiki v1.0. Next review: after SSO/SAML ships.*
