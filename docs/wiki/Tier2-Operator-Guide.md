# Tier 2 Operator Guide — NeuralMind

**Last updated:** 2026-07-22  
**Version:** v1.7.0  
**Audience:** Operators who just ran `neuralmind onboarding` or `neuralmind wakeup .`

---

## What Tier 2 (Team) gives you

Tier 2 is the paid tier on top of the MIT core. **The MIT core's 40-70x token reduction is free forever** — Tier 2 adds engineering-team governance, audit, and seat management.

| Feature | MIT core (free) | Team ($29/user/mo) |
|---------|-----------------|---------------------|
| 40-70x token reduction | Yes | Yes |
| Synapse learning | Yes | Yes |
| MCP server | Yes | Yes |
| Memory publish/inherit | Yes | Yes |
| Governance (publish scope, weight threshold) | No | Yes |
| Audit log (SHA-256 hash-chained) | No | Yes |
| Seat management (add/remove/list) | No | Yes |
| Self-hosted deployment | No | Yes |
| License validation (Ed25519 + 30-day grace) | No | Yes |

**You are paying for compliance and control, not for the compression.**

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

### Seats

```bash
neuralmind team seats list            # list all seats
neuralmind team seats add <email>     # invite a seat (idempotent, soft-delete aware)
neuralmind team seats remove <email>  # remove a seat (soft-delete)
```

### Governance

```bash
neuralmind team governance status
neuralmind team governance set-scope <personal|shared|both>
neuralmind team governance set-weight-threshold <0.0-1.0>
neuralmind team governance set-governance-enabled <true|false>
neuralmind team governance list-shared
neuralmind team governance remove-edge <edge_id>
```

### Audit

```bash
neuralmind team audit list            # recent audit events
neuralmind team audit export --format csv|json
neuralmind team audit verify          # verify SHA-256 hash chain integrity
```

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
| License portal | Deferred | D12: defer until 3+ customers |

**Do not market Tier 2 as SSO-enabled or multi-machine-synced.** Architecture is ready; features are not shipped.

---

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| "License not found" | `neuralmind wakeup .` auto-issues free tier on first run |
| "Downgrade guard triggered" | Fresh `tier2.yaml` should have `tier: free` (v1.7.0+). If not, delete and re-`wakeup` |
| "Seat limit exceeded" | `neuralmind team seats remove <email>` to free a seat |
| "Audit log empty" | Audit events only fire on Team-tier governance/seat operations |
| "Self-hosted data dir permission denied" | `neuralmind team self-hosted init` sets 0700 permisssions |

---

## When to skip Tier 2

- Under 5K lines, free-tier, inline-only, prompt-caching already covering you
- No compliance/audit requirements
- Solo developer (1-seat free tier is sufficient)

For the honest boundary, see `docs/HONEST-ASSESSMENT.md`.

---

*Wiki v1.0. Phase 2 doc (WAVE15). Next review: after SSO/SAML ships.*
