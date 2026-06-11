# Run NeuralMind as a service

> Goal: `neuralmind watch` and `neuralmind serve` survive reboots,
> crashes, and tmux closes. The synapse layer accumulates 24/7 instead
> of only while you're actively coding, and the graph view canvas is
> always at `http://127.0.0.1:8765/` when you want to look at it.

> **Why always-on matters more in v0.11.0+.** The directional
> transition signal (`neuralmind next <file>`, `neuralmind_next_likely`
> MCP tool) needs a long observation window to converge — you might
> edit ten files together but only get nine ordered pairs between them,
> so transitions accumulate slower than co-activation. Running the
> watcher as a service means every edit during deep-work sessions feeds
> the transition graph, not just the edits that happen while a query
> is open.

Three platforms, same shape: pick the template, point it at your
project, enable it. The templates live in [`scripts/systemd/`](../../scripts/systemd/)
and [`scripts/launchd/`](../../scripts/launchd/) in this repo.

### No checkout? Fetch the templates directly

The PyPI wheel doesn't include the repo's `scripts/` directory — it
ships only the importable `neuralmind` package. If you installed via
`pip` / `pipx` / `uv` / Docker, pull the templates straight from
GitHub:

```bash
# Linux — systemd
mkdir -p ~/.config/systemd/user
curl -fsSL https://raw.githubusercontent.com/dfrostar/neuralmind/main/scripts/systemd/neuralmind-watch.service \
  -o ~/.config/systemd/user/neuralmind-watch.service
curl -fsSL https://raw.githubusercontent.com/dfrostar/neuralmind/main/scripts/systemd/neuralmind-serve.service \
  -o ~/.config/systemd/user/neuralmind-serve.service

# macOS — launchd
curl -fsSL https://raw.githubusercontent.com/dfrostar/neuralmind/main/scripts/launchd/com.neuralmind.watch.plist \
  -o ~/Library/LaunchAgents/com.neuralmind.watch.plist
curl -fsSL https://raw.githubusercontent.com/dfrostar/neuralmind/main/scripts/launchd/com.neuralmind.serve.plist \
  -o ~/Library/LaunchAgents/com.neuralmind.serve.plist
```

The `cp scripts/...` commands below assume you have a repo checkout —
substitute one of the `curl` lines above if you don't.

NeuralMind ships a `/healthz` endpoint on the graph-view server
(`GET /healthz` → `{"status": "ok", "version": "..."}`, no auth). The
systemd unit uses it in `ExecStartPost` to fail fast if `serve` didn't
come up; Docker `HEALTHCHECK` and any external monitor can probe the
same endpoint.

---

## Linux — systemd user units

User-scope (no root). The unit lives in `~/.config/systemd/user/` and
is enabled per-login user.

```bash
# 1. Copy the templates
mkdir -p ~/.config/systemd/user
cp scripts/systemd/neuralmind-watch.service ~/.config/systemd/user/
cp scripts/systemd/neuralmind-serve.service ~/.config/systemd/user/

# 2. Edit the WorkingDirectory line in both files to your project path:
#    WorkingDirectory=%h/your-project
$EDITOR ~/.config/systemd/user/neuralmind-watch.service
$EDITOR ~/.config/systemd/user/neuralmind-serve.service

# 3. Enable + start
systemctl --user daemon-reload
systemctl --user enable --now neuralmind-watch
systemctl --user enable --now neuralmind-serve

# 4. Verify both are up and /healthz responds
systemctl --user status neuralmind-watch neuralmind-serve
curl -fsS http://127.0.0.1:8765/healthz
# {"status": "ok", "version": "0.8.0"}

# The graph view canvas itself requires the per-session token. The
# tokenized URL prints to journalctl on every startup:
journalctl --user -u neuralmind-serve | grep -F "http://127.0.0.1:8765/"
# (or pass --no-auth in ExecStart if you understand the implications)

# 5. Tail logs
journalctl --user -u neuralmind-watch -f
journalctl --user -u neuralmind-serve -f
```

User units don't run when no user session is active by default. If
you need it across logouts, enable lingering:

```bash
sudo loginctl enable-linger "$USER"
```

To uninstall:

```bash
systemctl --user disable --now neuralmind-watch neuralmind-serve
rm ~/.config/systemd/user/neuralmind-{watch,serve}.service
```

---

## macOS — launchd user agents

The plists live in `~/Library/LaunchAgents/` and run under your user
session — RunAtLoad + KeepAlive together mean "start at login, restart
if it crashes."

```bash
# 1. Copy the templates
cp scripts/launchd/com.neuralmind.watch.plist ~/Library/LaunchAgents/
cp scripts/launchd/com.neuralmind.serve.plist ~/Library/LaunchAgents/

# 2. Edit both files — replace YOUR_USERNAME and the project path:
#    WorkingDirectory → /Users/YOUR_USERNAME/your-project
#    StandardOutPath  → /Users/YOUR_USERNAME/Library/Logs/...
#    StandardErrorPath → /Users/YOUR_USERNAME/Library/Logs/...
$EDITOR ~/Library/LaunchAgents/com.neuralmind.watch.plist
$EDITOR ~/Library/LaunchAgents/com.neuralmind.serve.plist

# 3. Load
launchctl load -w ~/Library/LaunchAgents/com.neuralmind.watch.plist
launchctl load -w ~/Library/LaunchAgents/com.neuralmind.serve.plist

# 4. Verify
launchctl list | grep com.neuralmind
curl -fsS http://127.0.0.1:8765/healthz

# 5. Tail logs
tail -f ~/Library/Logs/neuralmind-watch.out.log
tail -f ~/Library/Logs/neuralmind-serve.out.log
```

The `which neuralmind` path matters — if you installed via `pipx`,
your binary is in `~/.local/bin/neuralmind`, not `/usr/local/bin/neuralmind`.
Update the `ProgramArguments` array's first element accordingly. If
you use `pyenv` or a per-project venv, point at the absolute path of
that venv's `neuralmind` binary, not the system one.

To unload:

```bash
launchctl unload -w ~/Library/LaunchAgents/com.neuralmind.{watch,serve}.plist
rm ~/Library/LaunchAgents/com.neuralmind.{watch,serve}.plist
```

---

## Windows — Task Scheduler

Run-at-startup tasks for `neuralmind watch` and `neuralmind serve`.

The [Scheduling Guide](../wiki/Scheduling-Guide.md#always-on-neuralmind-watch--neuralmind-serve-v08)
has the full PowerShell script + Task Scheduler GUI walkthrough.
Short version:

```powershell
# Register the always-on watcher (replaces the file polling daemon).
# ExecutionTimeLimit = 0 disables Task Scheduler's default 72-hour cap.
Register-ScheduledTask -TaskName "NeuralMind-Watch" `
  -Action (New-ScheduledTaskAction `
    -Execute "neuralmind" `
    -Argument "watch C:\path\to\your-project --quiet") `
  -Trigger (New-ScheduledTaskTrigger -AtLogOn) `
  -Settings (New-ScheduledTaskSettingsSet -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Seconds 0) `
    -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1))

# Register the always-on graph view. --no-browser keeps it from
# spawning a browser on every login.
Register-ScheduledTask -TaskName "NeuralMind-Serve" `
  -Action (New-ScheduledTaskAction `
    -Execute "neuralmind" `
    -Argument "serve C:\path\to\your-project --port 8765 --no-browser") `
  -Trigger (New-ScheduledTaskTrigger -AtLogOn) `
  -Settings (New-ScheduledTaskSettingsSet -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Seconds 0) `
    -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1))

# Verify
Get-ScheduledTask NeuralMind-*
Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8765/healthz
```

---

## Docker — HEALTHCHECK

If you run NeuralMind via the repo-root Dockerfile, add a `HEALTHCHECK`
that probes `/healthz`:

The repo-root `Dockerfile` is `python:slim`-based and does not
include `curl`. Use a stdlib Python probe instead so the HEALTHCHECK
works without adding a package:

```dockerfile
HEALTHCHECK --interval=30s --timeout=3s --start-period=60s --retries=3 \
  CMD python -c "import urllib.request, sys; r = urllib.request.urlopen('http://127.0.0.1:8765/healthz', timeout=2); sys.exit(0 if r.status == 200 else 1)" || exit 1
```

`--start-period=60s` matches the systemd template's readiness window
— `neuralmind serve` builds the embedding index before binding the
HTTP socket, and first runs on large projects can take a while.

The shipped Dockerfile doesn't bake this in by default because the
default container command is `neuralmind --help`, not `serve`. Add
the directive in your downstream image when you do run `serve` as
the container entrypoint.

---

## What "always-on" actually buys you

The synapse store is shared across all processes that touch the same
project. With `neuralmind watch` running 24/7:

- **Every file save** while you're working (editor, git operations,
  formatters, generators) becomes a `file_activity` event that the
  graph view's canvas pulses on and the synapse layer reinforces.
- **Every agent tool call** from any agent (Claude Code, Cursor,
  Cline, Continue, OpenClaw, Hermes-Agent, Agent Zero) that points at
  the same project reinforces the same synapse store.
- The brain accumulates whether you're at the keyboard or not.

With `neuralmind serve` running 24/7:

- **`http://127.0.0.1:8765/`** is always there. No "wait, I need to
  start the canvas first" friction when you want to debug a retrieval.
- The canvas shows the union of every agent's activity — your editor,
  every running session, the watcher daemon — in real time.

Pair with the v0.6.0 [multi-agent walkthrough](multi-agent.md) for the
full "one brain, many agents" story.

---

## Troubleshooting

### `/healthz` returns 404

You're on NeuralMind < v0.8. The endpoint shipped in v0.8. Upgrade:

```bash
pip install --upgrade neuralmind     # or pipx upgrade / uv pip install -U
```

For the systemd unit: remove the `ExecStartPost` line or drop the
probe loop until you upgrade.

### systemd unit starts then immediately exits

Check the logs for the root cause:

```bash
journalctl --user -u neuralmind-watch --since "5 minutes ago"
```

Common causes:
- `neuralmind` binary not on the PATH for the systemd `Service` env.
  Pass an explicit absolute path in `ExecStart` (e.g.
  `/home/$USER/.local/bin/neuralmind`).
- `WorkingDirectory` doesn't exist or doesn't have a `graphify-out/`
  yet. Run `neuralmind build .` in the
  project first.

### launchd "Could not find service"

You loaded the plist with the wrong path or the file has a typo. Try:

```bash
plutil -lint ~/Library/LaunchAgents/com.neuralmind.watch.plist
```

If `plutil` reports OK and `launchctl load -w ...` still fails, check
that the `Label` inside the plist matches the filename
(`com.neuralmind.watch`).

### Graph view canvas is blank

Check `/healthz` first — if that returns OK, the server is up but the
graph isn't indexed yet. Run `neuralmind build .` in the project.
