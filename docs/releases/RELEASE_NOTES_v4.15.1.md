# NeuralMind v4.15.1 — an expired Team license gets the full 30-day grace period

**Type:** Patch release | **Theme:** the license grace period the agreement grants, and a config setting that never did anything

The [license agreement](../NEURALMIND-LICENSE-AGREEMENT.md#42-expiration)
(§4.2) grants a 30-day grace period after a Team license expires, during which
Team features keep working so you can renew without interruption. The license
check ended grace at whichever came first: 30 days after expiry, or 30 days
after the software last validated the license. A team that hadn't run
NeuralMind in the weeks before expiry got less than 30 days, and a machine
with no validation on record, such as a fresh install or a restored backup,
got none. Grace now runs 30 days from expiry.

---

## What changed

### Licensing

- **Grace runs 30 days from the expiry date.** Until then,
  `neuralmind team license status` reports `OFFLINE_OK` and
  `neuralmind team governance`, `team seats` and `team audit` keep working,
  however long ago the software last ran. A license last validated 20 days
  before it expired got 10 days of grace in v4.15.0, and gets 30 now. From
  day 31 it reports `EXPIRED` and those commands stop until you activate a
  renewed license with `neuralmind team license activate`, which works
  throughout.
- **A clock set back still gets no grace.** Each successful validation
  records its time beside the license file (`license.last_valid`). If that
  time is later than the current time, the system clock has been moved back,
  and an expired license reports `EXPIRED`. The old 30-days-after-last-run
  limit protected nothing beyond that, because a clock set back to before
  the expiry date makes the license valid outright.
- **`self_hosted.offline_grace_days` is gone.** `tier2.yaml` accepted the
  setting and validated it, but nothing read it, so grace was always 30 days.
  Grace is fixed by the agreement, so it isn't configurable. A config that
  still has the key loads as before; the key is ignored and is dropped the
  next time NeuralMind saves the config.

### Docs

- The [upgrade guide](../wiki/Upgrade-Guide.md) described grace as offline
  use: the license "keeps working for 30 days without phoning home". The
  license check is local, with no licensing server to contact, so a license
  works offline for its whole term, and the 30 days follow expiry. Its
  downgrade steps named `neuralmind license status`, the issuer's command,
  where a customer runs `neuralmind team license status`. They also said the
  free tier comes back by itself after expiry. It doesn't:
  `neuralmind onboarding` offers to replace an expired license with a free
  one.

## What the agent actually sees

Nothing changes. Grace decides whether the Team governance, seats and audit
commands run after a Team license expires. An agent's context comes from the
MIT core, which doesn't check the license.

## Per-agent expectations

| Agent | What changes |
|---|---|
| Claude Code (hooks + MCP) | Nothing; no hook or MCP tool changed |
| Cursor / Cline / Continue (MCP) | Nothing |
| Hermes-Agent plugin | Nothing |
| Generic MCP client | Nothing |

## Upgrading

- No action needed. If v4.15.0 reported a license that expired within the
  last 30 days as `EXPIRED`, it now reports `OFFLINE_OK` until 30 days after
  expiry, and the Team governance, seats and audit commands work again.
- If your `tier2.yaml` sets `self_hosted.offline_grace_days`, you can delete
  it. It never had an effect.
- No rebuild, index format change or hook re-install.

## Related

- [License agreement §4.2](../NEURALMIND-LICENSE-AGREEMENT.md#42-expiration)
- [Upgrade guide: downgrade flow](../wiki/Upgrade-Guide.md#downgrade-flow)
- [Tier 2 operator guide](../wiki/Tier2-Operator-Guide.md)
- [v4.15.0 release notes](RELEASE_NOTES_v4.15.0.md)
