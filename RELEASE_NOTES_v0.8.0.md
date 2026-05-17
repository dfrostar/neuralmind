# NeuralMind v0.8.0 — always-on

**Release Date:** May 2026

## TL;DR

`neuralmind watch` and `neuralmind serve` are now first-class
production processes. Committed systemd, launchd, and Windows Task
Scheduler templates keep both running across reboots and crashes.
`neuralmind serve` exposes a `/healthz` endpoint so Docker
`HEALTHCHECK` and systemd `ExecStartPost` can probe it without
threading a session token.

Distribution (v0.7.0) made NeuralMind reachable. Always-on (v0.8.0)
makes it persistent — the synapse store accumulates 24/7 whether
you're at the keyboard or not, and the graph view canvas is always at
`http://127.0.0.1:8765/`.

No migration. Same `graph.json`, same `synapses.db`, same hooks. New
files are additive; existing CLI behaviour is unchanged.

> Note on cross-doc rollout: the marketing artifacts (LinkedIn drafts,
> NotebookLM v0.8 pack, screencast script, About-page + wiki Home
> callouts) are deferred to a follow-up pass. This release is the code
> + minimum docs. Frame the marketing arc once you've seen which parts
> users adopt.

## What's new

### Service templates

- **`scripts/systemd/neuralmind-watch.service`** — user-scope unit for
  the file watcher. Restart-on-failure, SIGTERM-clean shutdown, basic
  hardening (`NoNewPrivileges`, `PrivateTmp`, `ProtectSystem=strict`).
- **`scripts/systemd/neuralmind-serve.service`** — same for the graph
  view, plus an `ExecStartPost` that polls `/healthz` for up to 5
  seconds before declaring the unit ready.
- **`scripts/launchd/com.neuralmind.watch.plist`** — macOS user agent.
  `RunAtLoad` + `KeepAlive` + `ThrottleInterval` so a crash loop
  doesn't burn CPU.
- **`scripts/launchd/com.neuralmind.serve.plist`** — same for the
  graph view.

All four are templates — they ship with placeholder
`WorkingDirectory` / `ProgramArguments` paths the user edits before
loading. The
[always-on walkthrough](docs/use-cases/always-on.md) covers the edit
+ enable + verify loop per platform.

### `/healthz` on `neuralmind serve`

New stdlib-only endpoint, unauthenticated, returns:

```json
{"status": "ok", "version": "0.8.0"}
```

The route is intentionally before the session-token gate so a fresh
container or systemd unit can probe it without threading auth. Three
new tests in `tests/test_server.py` lock in the behaviour (200 status,
correct version, no `Set-Cookie` header).

### Always-on walkthrough

New page: [`docs/use-cases/always-on.md`](docs/use-cases/always-on.md).
Per-platform install + verify + uninstall + troubleshooting for Linux
(systemd), macOS (launchd), Windows (Task Scheduler), and Docker
(`HEALTHCHECK`). Closes the "I want NeuralMind running across reboots
but I don't want to figure out the unit file" gap.

### Windows Task Scheduler — always-on section

[`docs/wiki/Scheduling-Guide.md`](docs/wiki/Scheduling-Guide.md) gains
an "Always-on `neuralmind watch` + `neuralmind serve`" section above
the existing recurring-audit instructions. Two PowerShell
`Register-ScheduledTask` blocks for the watcher and graph view, with
the `/healthz` verification snippet.

## Deferred

- **Aider integration block in README.** Investigated 2026-05-17: the
  current Aider stable does not ship MCP-client support. Will add
  when upstream lands it.
- **Cross-doc marketing rollout.** README hero callout, wiki Home
  "What's New" entry, GitHub Pages, LinkedIn drafts, NotebookLM pack,
  screencast script — all deferred to a follow-up so this release
  ships code + minimum docs.

## Behaviour controls (unchanged)

| Env var | Default | Effect |
|---|---|---|
| `NEURALMIND_EVENT_LOG` | `1` | `0` disables the cross-process JSONL bridge. |
| `NEURALMIND_BYPASS` | unset | `1` skips PostToolUse compression. |
| `NEURALMIND_SYNAPSE_INJECT` | `1` | `0` skips prompt-time synapse recall. |
| `NEURALMIND_SYNAPSE_EXPORT` | `1` | `0` skips memory export to Claude Code's auto-memory. |

## Verification

```bash
# Upgrade
pip install --upgrade neuralmind     # or pipx upgrade neuralmind / uv pip install -U

# /healthz works without auth
neuralmind serve . &
curl -fsS http://127.0.0.1:8765/healthz
# {"status": "ok", "version": "0.8.0"}

# Linux: install + verify systemd units
mkdir -p ~/.config/systemd/user
cp scripts/systemd/neuralmind-{watch,serve}.service ~/.config/systemd/user/
# edit WorkingDirectory in both, then:
systemctl --user daemon-reload
systemctl --user enable --now neuralmind-watch neuralmind-serve
systemctl --user status neuralmind-watch neuralmind-serve

# macOS: install + verify launchd plists
cp scripts/launchd/com.neuralmind.{watch,serve}.plist ~/Library/LaunchAgents/
# edit WorkingDirectory + log paths, then:
launchctl load -w ~/Library/LaunchAgents/com.neuralmind.{watch,serve}.plist
launchctl list | grep com.neuralmind
```

Full per-platform walkthrough in
[`docs/use-cases/always-on.md`](docs/use-cases/always-on.md).

## What's next

- **v0.8.1** — marketing rollout for v0.8 (LinkedIn, NotebookLM,
  screencast, README + wiki + Pages callouts).
- **v0.8.x — Enterprise-Ready.** GHCR auto-build of the repo-root
  Dockerfile, air-gapped install doc, SBOM publication on tagged
  releases, consolidated compliance one-pager. Tracking issue:
  [#120](https://github.com/dfrostar/neuralmind/issues/120).

## Thanks

The v0.7.0 install matrix made it possible to recommend a single
"upgrade and enable a unit" path that works the same regardless of how
the user installed NeuralMind. Without that, each install-method
permutation would have needed its own `ExecStart` example. Small
release; the foundations underneath did most of the work.
