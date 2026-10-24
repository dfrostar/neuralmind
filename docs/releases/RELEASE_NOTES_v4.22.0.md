# NeuralMind v4.22.0 — doctor says whether anything calls NeuralMind, `install-mcp --client hermes`, and a build that ends with the commands that wire it in

**Type:** Minor release | **Theme:** an installed index that no agent queries is visible, and each missing piece is one command away

A Hermes Agent deployment sat installed but unused for 11 days, with 2 logged
queries. The daemon wasn't running, no Git hooks were installed, and the
Hermes plugin was never installed, while `neuralmind doctor` printed "Up and
running": every check it ran was about the index, and the index was fine.
Four commands fixed it (`uv tool upgrade neuralmind`,
`neuralmind install-hermes-plugin`, `neuralmind daemon start`,
`neuralmind init-hook <project>`). This release makes that state show up, in
`doctor` and at the end of a build, with the command for each missing piece.

No hook, MCP tool or prompt block changes. What an agent sees on each turn is
the same as in v4.21.0; what changes is whether the pieces that put it there
are connected, and whether you can tell.

---

## What changed

### `neuralmind doctor`: a Wiring section, first

Before the existing checks, doctor now reports whether anything calls
NeuralMind for the project:

| Line | States |
|---|---|
| **Daemon** | running on `host:port` (pid, version) · not running · alive but not answering · running an older version than the one installed · off under `NEURALMIND_NO_DAEMON=1` |
| **Git hooks** | full / partial / none, for `init-hook`'s four rebuild hooks and the pre-commit drift guard. A hook without its executable bit doesn't count (git skips it), nor does a block serving another project in the same repository, nor any of them while `core.hooksPath` points git at another directory |
| **Hermes plugin** | not installed · installed but not on Hermes's `plugins.enabled` list, or on `plugins.disabled` · enabled, pinned to this project or following `TERMINAL_CWD` · pinned to another project · plugin code older than the installed NeuralMind |
| **MCP registration (*client*)** | one line per client that has NeuralMind registered (Claude Code's `.mcp.json` and `claude mcp add`'s scopes in `~/.claude.json`, Cursor's project or user-wide `mcp.json`, Cline, Claude Desktop, VS Code, Hermes) or looks installed without it; *can't tell* for a config doctor can't parse; one line when no known client has it |

Every line is `ok` or `warn`, never `fail`, and a warning carries the command
that fixes it, unless no single command can (a symlinked Hermes config, say,
where the line says what to do instead). When no agent host is wired (no
Claude Code hooks, no enabled Hermes plugin, no MCP registration), the closing
line reads **"Installed but not wired"** instead of "Up and running". A host
doctor couldn't read keeps it from saying so: the verdict is then `partial`.
Each probe is guarded on its own, so a malformed file one of them reads costs
that line, not the section.

The exit code is unchanged: `0` with warnings, `1` only when a core check
fails. `--json` adds a `wiring` object beside the `checks` list, which is
unchanged:

```json
{"status": "warn", "wiring": {"state": "inert", "checks": [...]}, "checks": [...]}
```

`state` is `inert` (no agent host wired), `partial` or `wired`, for a script
to gate on. The top-level `status` now counts wiring warnings, so a setup that
read `ok` before can read `warn`. Doctor stays read-only: every probe reads
files or asks `git rev-parse`, and a probe that fails reports what it couldn't
see.

### `neuralmind install-mcp --client hermes`

Hermes-Agent reads MCP servers from `mcp_servers:` in the YAML `config.yaml`
of its home, so `install-mcp` couldn't register NeuralMind there. Now:

```bash
neuralmind install-mcp --client hermes
```

adds the launch spec every other client gets (`command: neuralmind-mcp`,
`args: []`) to the Hermes home plain `hermes` uses: its active profile, else
`$HERMES_HOME`, else `~/.hermes` (`%LOCALAPPDATA%\hermes` on Windows).
`--all` includes Hermes once its `config.yaml` exists.

Hermes keeps comments in that file, so the entry is added as text, under an
existing block-style `mcp_servers:` or as a new section at the end. The file
is written only when the result parses to the old config plus that entry,
atomically and with its mode kept (Hermes keeps it `0600`). Otherwise it isn't
touched, and the command prints the entry to paste: no `config.yaml` yet
(writing one would make Hermes skip its first-run setup), a symlinked config,
flow-style `mcp_servers: {...}`, a `neuralmind` entry that starts something
else, or invalid YAML. NeuralMind already registered under another key counts
as present, so Hermes doesn't start a second server, and an entry with
`enabled: false` is reported, not switched back on.

`neuralmind install-hermes-plugin --mcp` does the same for the home it
installs into: one implementation, two ways to reach it. The plugin alone
still adds no tools: per-turn context needs none, and every MCP tool adds its
schema to each request. An install into a home with a `config.yaml` and no
entry ends with the command that adds it.

A running Hermes reloads its MCP servers when `config.yaml` changes (or on
`/reload-mcp`, when `mcp.auto_reload_on_config_change` is off); restart the
gateway if one is running. `hermes mcp test neuralmind` checks it.

### After a build: the commands that wire it in

A successful `neuralmind build` used to close with an `init-hook` hint and a
`watch --reindex` hint, whatever was already set up. It now prints, in at most
three lines, the commands for whatever isn't wired yet:

```
  Next, wire it in (`neuralmind doctor` shows what's wired):
    neuralmind daemon start && neuralmind init-hook .
    neuralmind install-hermes-plugin && neuralmind install-mcp --client hermes
```

The first command line keeps the index fresh; the second wires the agent:
with Hermes set up on the machine, the plugin and its MCP entry. Without
Hermes, and with no agent host wired, it's `neuralmind install-hooks <project>`
when Claude Code is set up, `neuralmind install-mcp <project> --all` when
another MCP client looks installed, else `neuralmind install-mcp --print`.
Commands that take a project name the one just built, quoted for the
platform's shell. A pin to another project, Git hooks serving another project
in the same repository, a disabled MCP entry and a `core.hooksPath` setup are
never offered for changing. With room left, the `watch --reindex` hint follows; once
everything is wired it's the only line. `NEURALMIND_NO_INIT_HINT` still turns
them off.

### Checked against a live Hermes

On Hermes Agent v0.22.5 with its gateway running, `install-mcp --client hermes`
added four lines to a 347-line `config.yaml` and changed nothing else (the
parsed config was the old one plus the entry), kept its `0600` mode, and a
second run reported `already-present`. `hermes mcp list` showed the entry
enabled, and `hermes mcp test neuralmind` connected over stdio in 2.2 s and
discovered the six default tools. Doctor's Hermes MCP line then read `ok`.
That is one machine; the YAML cases it didn't meet are covered by tests.

### Also in v4.22.0: one SBOM per platform

The release's SBOM workflow installs each release natively on six runners
(Linux x86_64 and arm64, macOS arm64 and Intel, Windows x86_64 and ARM64) and
publishes one CycloneDX SBOM per platform, each recording any dependency pip
built from source there ([#709](https://github.com/dfrostar/neuralmind/pull/709)).
The Linux x86_64 SBOM keeps the unsuffixed name, and `/security` links the
others.

### Tests

- `tests/test_wiring.py` (new): every daemon, Git hook, Hermes plugin and MCP
  state, the `inert`/`partial`/`wired` summary and the build's next steps,
  against a fake `HOME`, `APPDATA`, `LOCALAPPDATA`, Hermes home and daemon
  discovery file. No Hermes code runs.
- `tests/test_doctor.py`: an inert install with healthy core checks exits 0
  and never prints "Up and running"; the JSON shape; a core failure still
  exits 1; the section fails open.
- `tests/test_mcp_install.py`: Hermes YAML cases (comments and mode kept,
  idempotent, every refusal leaves the file byte-identical, no config created,
  a disabled entry under another name).
- `tests/test_hermes_plugin.py`: `install-hermes-plugin --mcp` end to end.

---

## What the agent actually sees post-install

Nothing new per turn or per tool call. What changes is how likely it is that
the agent gets anything at all:

| Agent | Before v4.22.0 | From v4.22.0 |
|---|---|---|
| **Claude Code** | `doctor` checked its hooks and nothing else that calls NeuralMind | The Wiring section adds the daemon, the Git hooks, and the MCP entry in `.mcp.json` or `claude mcp add`'s scopes |
| **Hermes-Agent** | The plugin from `install-hermes-plugin`; the MCP server added to `config.yaml` by hand | `install-mcp --client hermes` (or `install-hermes-plugin --mcp`) adds the MCP server; doctor reports the plugin enabled, pinned or outdated, and the MCP entry |
| **Cursor / Cline / Claude Desktop / VS Code** | `install-mcp` | Unchanged; doctor shows each one registered, or installed without the entry |
| **Generic MCP client** | `install-mcp --print` | Unchanged; doctor's MCP line says when no known client has the entry, which is expected for a client registered by hand |

## Upgrading

- **Run `neuralmind doctor .`** after upgrading. Its Wiring section names
  anything left behind: a plugin copy from an older release
  (`neuralmind install-hermes-plugin` updates it), or a daemon still running
  the old version (`neuralmind daemon restart`). A running MCP server keeps
  its code until its host restarts it; in Hermes, `/reload-mcp` does.
- **Scripts that read `doctor --json`** keep their `checks` list as it was.
  The top-level `status` can now be `warn` where it was `ok`, from wiring
  warnings; the exit code doesn't change.
- Nothing to rebuild.

## Use cases

- **Existing: [Hermes-Agent with code memory in every turn](../use-cases/hermes-agent.md).**
  Doctor's Wiring section shows whether the plugin is enabled and serving the
  project, and `install-mcp --client hermes` adds the tools beside it. The
  [Hermes pairing tips](../wiki/Tips-and-Tricks-Hermes-Pairing.md) cover
  verifying, upgrading and the switches.
- **New: a wiring check for any setup.** `neuralmind doctor --json` and its
  `wiring.state` tell a provisioning script or a CI job whether a machine's
  agents are connected to the index, not only whether the index is healthy.
