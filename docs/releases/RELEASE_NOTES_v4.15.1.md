# NeuralMind v4.15.1 — the full 30-day grace period for an expired Team license, and `neuralmind team` exits 1 when it fails

**Type:** Patch release | **Theme:** two Team-tier fixes: the license grace period the agreement grants, and exit codes the Team commands computed and the CLI threw away

The [license agreement](../NEURALMIND-LICENSE-AGREEMENT.md#42-expiration)
(§4.2) grants a 30-day grace period after a Team license expires, during which
Team features keep working so you can renew without interruption. The license
check ended grace at whichever came first: 30 days after expiry, or 30 days
after the software last validated the license. A team that hadn't run
NeuralMind in the weeks before expiry got less than 30 days, and a machine
with no validation on record, such as a fresh install or a restored backup,
got none. Grace now runs 30 days from expiry.

The `team` commands and `onboarding` also work out their own exit code:
`team license activate` returns 1 when a license doesn't validate, `team seats
sync` returns 2 when it adds only some of a manifest's seats. But `neuralmind`
called each command and ignored what it returned. So
`neuralmind team license activate expired.json` printed
`License validation failed for expired.json: EXPIRED. Nothing was installed. …`
and exited 0, and so did every other `team` and `onboarding` failure. A
provisioning script under `set -e` carried on past a license that was never
installed. The CLI reference has said since v4.6.0 that a non-admin
`team governance remove-edge` exits 1; it never did. This is the same class of
bug v4.12.1 fixed in `doctor`: an exit code that was documented and tested
nowhere. Found on 2026-10-12 while activating an expired license.

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

### CLI

- **A command's exit code reaches the shell.** When a command returns a
  non-zero integer, `neuralmind` now exits with it. Commands that call
  `sys.exit` themselves are unchanged, and a command that returns nothing
  still exits 0. All 81 subcommand handlers were checked: the five `team`
  command groups and `onboarding` return a code, and every other handler
  returns nothing, so no other command's exit status changes.

| Command | Now exits | When |
|---|---:|---|
| `team license activate FILE` | 1 | The file is missing, or it doesn't validate (`EXPIRED`, `INVALID`, …). Nothing is installed |
| `team governance …`, `team seats …`, `team audit …` | 1 | No usable license (a Team license file is missing, corrupted, or past its 30-day grace period), `--admin` isn't an admin, a seat limit, an unknown seat, or an invalid value |
| `team seats sync MANIFEST` | 1 | The manifest is missing, malformed, the wrong version, expired, or not signed by the issuer |
| `team seats sync MANIFEST` | 2 | Applied only in part: the license's seat limit refused some seats (listed under `failed` in its JSON report) |
| `team audit verify` | 1 | The audit log's hash chain is broken |
| `team self-hosted init` | 1 | The data dir is refused or can't be created |
| `onboarding` | 1 | The license agreement was declined, or the free license couldn't be written |

- **Still exit 0:** `team license status`, `team license portal`,
  `team self-hosted status` and `team self-hosted validate-license` report the
  license's state in their output whatever it is. To gate on the license
  itself, read the `status` field of `team license status`.

### Tests

- `tests/test_cli_exit_codes.py` runs 15 failure cases and 2 successes through
  the CLI's entry point, each in a throwaway config directory with its own
  signing key. All 15 failures exited 0 on v4.15.0.

### Scripts and docs

- `scripts/e2e_team_tier.sh` (`set -euo pipefail`) added a second seat on the
  one-seat free license and carried on, because the refusal exited 0. It now
  requires that refusal to exit non-zero, and fails if the seat is added.
- The [CLI reference](../wiki/CLI-Reference.md#team-license-seats-audit-self-hosted)
  lists exit codes for `onboarding` and every `team` command, in a new section
  for `team license`, `seats`, `audit` and `self-hosted`. Its global table
  gains `seats sync`'s exit 2. The
  [Tier 2 operator guide](../wiki/Tier2-Operator-Guide.md) lists
  `team seats sync` and shows a provisioning script that stops on a refused
  license.
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

An agent that runs `neuralmind team …` or `neuralmind onboarding` as a shell
command now gets exit status 1 (2 for a partial `seats sync`) when the command
fails, with the same message as before. Before, the tool call reported success
while the output said nothing was installed. The grace period changes nothing
an agent sees: it decides whether the Team governance, seats and audit
commands run after a Team license expires, and an agent's context comes from
the MIT core, which doesn't check the license. No hook, MCP tool, query result
or index changed.

## Per-agent expectations

| Agent | What changes |
|---|---|
| Claude Code (hooks + MCP) | A `neuralmind team …` or `onboarding` command run through Bash reports its failure as one; no hook or MCP tool changed |
| Cursor / Cline / Continue (MCP) | Nothing: no MCP tool runs these commands |
| Hermes-Agent plugin | Nothing in the plugin; a command Hermes runs in its terminal behaves as under Claude Code |
| Generic MCP client | Nothing |

## Upgrading

- **`neuralmind team …` and `onboarding` can now exit non-zero.** A script
  that runs them under `set -e`, or reads their exit code, stops at a failure
  where it went on before. To keep going, append `|| true`.
- **`team seats sync` exits 2 on a partial sync.** If a partial sync is
  acceptable, allow it explicitly:
  `neuralmind team seats sync manifest.json --admin you@example.com || [ $? -eq 2 ]`.
- If v4.15.0 reported a license that expired within the last 30 days as
  `EXPIRED`, it now reports `OFFLINE_OK` until 30 days after expiry, and the
  Team governance, seats and audit commands work again.
- If your `tier2.yaml` sets `self_hosted.offline_grace_days`, you can delete
  it. It never had an effect.
- No rebuild, index format change or hook re-install.

## Related

- [CLI reference: `team` exit codes](../wiki/CLI-Reference.md#team-license-seats-audit-self-hosted)
- [CLI reference: `onboarding`](../wiki/CLI-Reference.md#onboarding-v170)
- [License agreement §4.2](../NEURALMIND-LICENSE-AGREEMENT.md#42-expiration)
- [Upgrade guide: downgrade flow](../wiki/Upgrade-Guide.md#downgrade-flow)
- [Tier 2 operator guide](../wiki/Tier2-Operator-Guide.md)
- [v4.15.0 release notes](RELEASE_NOTES_v4.15.0.md)
- [v4.12.1 release notes](RELEASE_NOTES_v4.12.1.md): the same exit-code bug in `doctor`
