# NeuralMind v4.15.1 — `neuralmind team` and `onboarding` exit 1 when they fail

**Type:** Patch release | **Theme:** exit codes the Team commands computed and the CLI threw away

The `team` commands and `onboarding` work out their own exit code:
`team license activate` returns 1 when a license doesn't validate, `team seats
sync` returns 2 when it adds only some of a manifest's seats. But `neuralmind`
called each command and ignored what it returned. So
`neuralmind team license activate expired.json` printed
`License validation failed for expired.json: EXPIRED. Nothing was installed. …`
and exited 0, and so did every other `team` and `onboarding` failure. A
provisioning script under `set -e` carried on past a license that was never
installed. The CLI reference has said since v4.6.0 that a non-admin
`team governance remove-edge` exits 1; it never did.

This is the same class of bug v4.12.1 fixed in `doctor`: an exit code that was
documented and tested nowhere. Found on 2026-10-12 while activating an expired
license.

---

## What changed

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
| `team governance …`, `team seats …`, `team audit …` | 1 | No usable license (a Team license file is missing, corrupted or expired), `--admin` isn't an admin, a seat limit, an unknown seat, or an invalid value |
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

## What the agent actually sees

An agent that runs `neuralmind team …` or `neuralmind onboarding` as a shell
command now gets exit status 1 (2 for a partial `seats sync`) when the command
fails, with the same message as before. Before, the tool call reported success
while the output said nothing was installed. No hook, MCP tool, query result
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
- No rebuild, config change or hook re-install.

## Related

- [CLI reference: `team` exit codes](../wiki/CLI-Reference.md#team-license-seats-audit-self-hosted)
- [CLI reference: `onboarding`](../wiki/CLI-Reference.md#onboarding-v170)
- [Tier 2 operator guide](../wiki/Tier2-Operator-Guide.md)
- [v4.12.1 release notes](RELEASE_NOTES_v4.12.1.md): the same bug in `doctor`
