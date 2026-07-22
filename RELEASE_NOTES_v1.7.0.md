# Release Notes — v1.7.0 (2026-07-22)

**Campaign:** Free Tier Shipped  
**Tagline:** `pip install neuralmind && neuralmind wakeup .` now auto-provisions free tier on first run.

---

## What shipped

### Free tier auto-provision

When a stranger runs `neuralmind wakeup .` for the first time, NeuralMind checks if `~/.config/neuralmind/license.json` exists. If not, it calls `issue_free_license()` and prints:

```
✓ Free tier activated — run `neuralmind onboarding` to configure,
  `neuralmind team license status` to view.
```

This eliminates the signup wall — identity is created on first meaningful action.

### Default tier fix

`Tier2Config.tier` default flipped from `"team"` to `"free"` (`neuralmind/tier2/config.py:95`). Previously, a fresh `tier2.yaml` triggered the downgrade guard at `tier2/cli.py:127`, silently blocking free-tier auto-issue.

### Upgrade CTA at call 10

`_increment_wakeup_count()` (new in `neuralmind/cli.py`) fires on every `cmd_wakeup` and `cmd_query`. At call 10, it prints a one-liner:

> NeuralMind Team: $29/user/mo — shared memory, governance, seat management.
> See neuralmind.uk/pricing or run `neuralmind onboarding`.

Fires exactly once (sentinel at count == 10).

---

## Acceptance

| Criterion | Status |
|-----------|--------|
| `pip install neuralmind && neuralmind wakeup .` creates license.json with `tier: "free"` | Pass |
| Second `wakeup` is idempotent (no overwrite, no error) | Pass |
| `Default tier` is "free" in fresh `tier2.yaml` | Pass |
| After 10 wakeup/query calls, user sees Team CTA one-liner | Pass |
| CTA fires only once | Pass |
| 21/21 tier2 tests pass | Pass (191/191 total) |
| Ruff clean on `cli.py` and `config.py` | Pass |

---

## Missing (Phase 2, not blocking)

- Wiki `Tier2-Operator-Guide.md`
- `neuralmind onboarding` entry in `CLI-Reference.md`
- `wiki/Upgrade-Guide.md` for free → team flow
- Memory opt-in from `cmd_wakeup` (currently query-only)

---

## Files changed

| File | Change |
|------|--------|
| `neuralmind/cli.py` | Auto-issue license in `cmd_wakeup`, `_increment_wakeup_count()` for CTA |
| `neuralmind/tier2/config.py` | `Tier2Config.tier` default: `"team"` → `"free"` |
| `tests/test_tier2_free_tier.py` | `TestCmdWakeupLicenseAutoIssue` (2 tests), `TestUpgradeCTA` (3 tests), imports updated |
| `tests/test_tier2_config.py` | Default tier assertion: `"team"` → `"free"` |

---

## Marketing uses

- **LinkedIn About:** Replace aspirational $15/mo Enterprise with shipped $29/mo Team + free-tier auto-provision
- **LinkedIn DMS:** 3-part sequence (value-first insight, methodology share, peer deep-dive)
- **README:** v1.7.0 section at top of release notes
- **Wiki:** v1.7.0 added to "What's New"
- **Website Hero:** "Free Tier — Auto-provisioned" stat
- **Website Features:** "Free Tier — Auto-Provisioned" card (v1.7.0 badge)
- **Website FAQ:** New entry explaining auto-provision
- **Codex publication:** New `/publications/codex-setup` page

---

*v1.7.0 — Free tier auto-provision + upgrade funnel. Not a feature launch — a journey completion.*
