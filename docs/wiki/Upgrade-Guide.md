# Upgrade Guide — Free to Team

**Last updated:** 2026-10-12  
**Version:** v1.7.0  
**Audience:** Free users who want Team tier (governance, audit, seats)

---

## Why upgrade?

The MIT core is **free forever** — token-efficient retrieval (51–242× fewer tokens than pasting every source file on the public benchmark), synapse learning, MCP server, ten tree-sitter languages plus JavaScript. You do NOT upgrade for more savings.

You upgrade for:
- **Governance** — control what AI agents can publish/shared memory
- **Audit log** — SHA-256 hash-chained, append-only, exportable
- **Seat management** — add/remove engineers, soft-delete, idempotent
- **Self-hosted deployment** — air-gapped, docker-compose, data persists

**Price:** $29/user/mo, annual contract, 5-50 seats.

---

## Upgrade flow (5 minutes)

### Step 1: Verify you're on free tier

```bash
neuralmind team license status
```

Output should show: `tier: free`, `seats: 1`, `expires: never`.

If you see `tier: team` already — you're done.

### Step 2: Run onboarding

```bash
neuralmind onboarding
```

Walks through:
1. License activation (or keep free tier)
2. Governance defaults (scope, weight threshold)
3. Admin email setup
4. Team seat audit
5. Verification

For defaults-only: `neuralmind onboarding --quick`

### Step 3: Activate Team license

Purchase a Team license key (.json file), then:

```bash
neuralmind team license activate <path-to-license.json>
```

The license is Ed25519-signed and checked locally, with no licensing server to contact, so it works offline or air-gapped for its whole term. After it expires, a 30-day grace period keeps Team features working while you renew.

### Step 4: Verify

```bash
neuralmind team license status
```

Output should now show: `tier: team`, `seats: N`, `expires: <date>`.

### Step 5: Add seats

```bash
neuralmind team seats add <employee1@company.com>
neuralmind team seats add <employee2@company.com>
```

Seats are idempotent — adding an existing seat errors softly.

---

## Downgrade flow

There's no downgrade guard. If you stop paying:

1. License expires at end of annual term
2. For 30 days after the expiry date, `neuralmind team license status` shows `OFFLINE_OK` and the governance, seats and audit commands keep working (the [license agreement](../NEURALMIND-LICENSE-AGREEMENT.md#42-expiration), §4.2). This doesn't depend on when NeuralMind last ran (v4.15.1+; earlier versions could end it sooner)
3. From day 31 it shows `EXPIRED`, and those commands stop until you activate a renewed license with `neuralmind team license activate`
4. To drop to the free tier instead, run `neuralmind onboarding`: once the license has expired, its first step offers to replace it with a free license

No data loss. The MIT core doesn't check license status.

---

## What the upgrade CTA looks like

After 10 wakeup/query calls, the CLI prints:

```
NeuralMind Team: $29/user/mo — shared memory, governance, seat management.
See neuralmind.uk/pricing or run `neuralmind onboarding`.
```

This fires exactly once. To re-trigger: `neuralmind onboarding` directly.

---

## Honest scope (what does NOT change on upgrade)

| Free tier | Team tier |
|-----------|-----------|
| Token-efficient retrieval | Same — no additional compression |
| Synapse learning | Same synapse store |
| MCP server | Same tools |
| Memory publish/inherit | Same bundle |
| — | + Governance, audit, seats, self-hosted |
| 1 seat | 5-50 seats |

**You are paying for compliance, not compression.**

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| "License invalid" | Expired or corrupted | `neuralmind team license activate <file>` |
| "Seat limit exceeded" | Over 50 seats | `neuralmind team seats remove <email>` |
| "Governance not enabled" | Free tier | Upgrade to Team tier |
| "Self-hosted data dir missing" | Not initialized | `neuralmind team self-hosted init` |

---

*Wiki v1.0. Next review: after Enterprise tier ships.*
