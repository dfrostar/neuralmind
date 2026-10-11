# NeuralMind v4.12.1 — `neuralmind doctor` exits 1 when a check fails, as documented

**Type:** Patch release | **Theme:** a v0.55.0 regression in `doctor`'s exit code, and a false failure it would have exposed

The CLI reference, the [install-paths walkthrough](../use-cases/install-paths.md)
(`neuralmind doctor . && neuralmind wakeup .`) and the v0.12.0 release notes
all say `neuralmind doctor` exits non-zero when a check fails, so a script or
CI step can gate on it. From v0.55.0 through v4.12.0 it always exited 0. This
release restores the exit code, and fixes a check that would otherwise have
failed such a gate on a working index.

---

## What changed

### CLI

- **`doctor` exits 1 when a check fails again.** v0.12.0 shipped it that way.
  In v0.55.0 the Tier 2 checks were inserted between the report and the
  `sys.exit(1)`, which ended up unreachable inside the new helper, and a lint
  pass later deleted it. So `neuralmind doctor . && neuralmind wakeup .` ran
  `wakeup` on a project with no graph. It now exits 1 when any check fails,
  with or without `--json` (the JSON report is printed first); warnings still
  exit 0. Regression tests run it on an unbuilt project.
- **`doctor` no longer fails on a repaired turbovec index.** When turbovec
  can't read an index, NeuralMind keeps it as `index.tvim.stale` and rebuilds
  it, and nothing removes the backup. The Turbovec compatibility check failed
  whenever that file existed, so it kept failing after the rebuild worked:
  with the exit code above, a gate on `doctor` would have stopped there. It
  now loads the live index (read-only, with turbovec's own loader) and fails
  only when that load fails. A leftover backup is named in an `ok` line, and
  you can delete it once you no longer need it.

### Scripts and docs

- `scripts/install-team.sh` waited on `doctor` for its container. The compose
  service has no long-running process yet, so there is no server to wait
  for; the script now checks that the CLI runs in a one-off container and
  stops if it doesn't.
- `scripts/e2e_team_tier.sh` captures `doctor`'s output before grepping it,
  so exit 1 under `pipefail` doesn't hide the Tier 2 check.
- [UPGRADING](../UPGRADING.md), the [FAQ](../wiki/FAQ.md), the
  [deployment guide](../DEPLOYMENT-GUIDE.md) and `docker-compose.yml` said
  doctor always exits 0. They now describe the exit code; the deployment
  guide and compose file point a liveness probe at `health`, which checks
  only the index.

## What the agent actually sees

Nothing new in its context. An agent or provisioning script that runs
`neuralmind doctor` as a shell command now sees exit status 1 when a check
fails, alongside the same `[FAIL]` line and fix it printed before.

## Per-agent expectations

| Agent | What changes |
|---|---|
| Claude Code (hooks + MCP) | Nothing in hooks or MCP tools; `neuralmind doctor` run as a command exits 1 on a failed check |
| Cursor / Cline / Continue (MCP) | Same: no tool, argument or response field changed |
| Hermes-Agent plugin | Same |
| Generic MCP client | Same |

## Upgrading

- **`neuralmind doctor` can now exit 1.** A script that runs it under
  `set -e`, or reads its exit code, stops on a failed check where it went on
  before. To keep going, run `neuralmind doctor . || true`, or read
  `--json`'s `status` field (`ok` / `warn` / `fail`), which works on every
  version.
- No rebuild, index format change or hook re-install.

## Related

- [CLI reference: `doctor`](../wiki/CLI-Reference.md#doctor-v0120)
- [v4.12.0 release notes](RELEASE_NOTES_v4.12.0.md)
