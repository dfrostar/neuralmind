# NeuralMind v4.22.0 — doctor says whether anything calls NeuralMind, `install-mcp --client hermes`, a build that ends with the commands that wire it in, and a feature branch's calls stay on the branch

**Type:** Minor release | **Theme:** an installed index that no agent queries is visible, and each missing piece is one command away; and the call graph each build seeds follows the checkout, so a branch's calls no longer reach the default branch's recall

A Hermes Agent deployment sat installed but unused for 11 days, with 2 logged
queries. The daemon wasn't running, no Git hooks were installed, and the
Hermes plugin was never installed, while `neuralmind doctor` printed "Up and
running": every check it ran was about the index, and the index was fine.
Four commands fixed it (`uv tool upgrade neuralmind`,
`neuralmind install-hermes-plugin`, `neuralmind daemon start`,
`neuralmind init-hook <project>`). This release makes that state show up, in
`doctor` and at the end of a build, with the command for each missing piece.

That part changes no hook, MCP tool or prompt block: what changes is whether
the pieces that put context in front of the agent are connected, and whether
you can tell. The one change to what recall returns is
[a feature branch's calls stay on the branch](#also-in-v4220-a-feature-branchs-calls-stay-on-the-branch),
below.

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

### Also in v4.22.0: a feature branch's calls stay on the branch

Every build seeds the call and import edges it finds into the synapse layer,
so recall can follow the code's structure from the first query. Those seeds
went into the `shared` baseline, which every branch reads and nothing cleared.
A call you added on a feature branch was seeded there by the branch's build,
and after you switched back to `main` it was still recalled, at half weight,
until it decayed on the shared 60-day half-life. The same went for a call
deleted from the code.

Associations learned from use were never affected: they go into the branch's
own `branch:<name>` namespace, as they have since v0.24.0.

#### Call-graph seeds live in a `structural` namespace each build replaces

Seeds now go into a `structural` namespace that every build replaces with the
graph of the code checked out. After the `post-checkout` hook's rebuild (or any
build) on `main`, a feature branch's calls are gone from recall, and so is a
call deleted from the code.

- **Recall on a clean `main` doesn't change.** The merged read takes
  `structural` at 0.5, the weight the seeds had in `shared`. In a store an
  earlier release seeded, the old copies in `shared` add to it until they
  fade (below).
- **It doesn't decay**: the next build replaces it.
- **It isn't published.** `neuralmind memory publish` exports `personal` and
  `shared`, so the team bundle no longer carries call-graph seeds; each
  teammate's own build writes theirs.
- **It's never the active namespace.** `NEURALMIND_NAMESPACE` or
  `memory_namespace` naming `structural` is ignored, since a build would wipe
  anything learned there.
- `neuralmind memory inspect .` lists it as its own row.

#### Old copies in `shared`

The seeds earlier releases wrote to `shared` are left there. Their rows look
like team memory (an edge approved with `neuralmind memory review-approve` or
imported from a bundle is a single-activation `shared` row too), so deleting
them would delete approved memory. Builds no longer refresh them, so they fade
on the 60-day shared half-life. Until then, a call still in the code is
counted in both `shared` and `structural`, and a branch-only call already in
`shared` is still recalled.

#### Still open

The `SYNAPSE_MEMORY.md` file written for Claude Code at session start lists
the strongest associations from every namespace, other branches' included.
Recall doesn't read them; the agent does see the file.

### Also in v4.22.0: an SBOM for each platform it installs on

The release's SBOM workflow tries a native install of each release on six
runners (Linux x86_64 and arm64, macOS arm64 and Intel, Windows x86_64 and
ARM64) and publishes a CycloneDX SBOM for each install that succeeds, recording
any dependency pip built from source there
([#709](https://github.com/dfrostar/neuralmind/pull/709)). Run for v4.21.0,
five succeeded. On Windows ARM64 the install fails, building `cryptography`,
`chromadb` and `grpcio`, so there is no SBOM for it; use WSL 2 or the
`linux/arm64` container there
([#715](https://github.com/dfrostar/neuralmind/pull/715), which also fixed the
Windows x86_64 SBOM). The Linux x86_64 SBOM keeps the unsuffixed name, and
`/security` links the others.

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
- `tests/test_synapses.py`: a branch-only call is gone from the default
  branch's recall, and from every namespace, after switching back (on v4.21.0
  it was still recalled); a deleted call is dropped on rebuild; `structural`
  reads at the weight `shared` seeds had and doesn't decay; an empty graph
  empties it; seeding never deletes a `shared` row, approved edges included.
- `tests/test_synapse_namespaces.py`: a `structural` override falls through
  to branch detection.
- `tests/test_team_memory.py`: a published bundle carries no call-graph seeds.

---

## What the agent actually sees post-install

The wiring work adds nothing per turn or per tool call. What it changes is how
likely it is that the agent gets anything at all:

| Agent | Before v4.22.0 | From v4.22.0 |
|---|---|---|
| **Claude Code** | `doctor` checked its hooks and nothing else that calls NeuralMind | The Wiring section adds the daemon, the Git hooks, and the MCP entry in `.mcp.json` or `claude mcp add`'s scopes |
| **Hermes-Agent** | The plugin from `install-hermes-plugin`; the MCP server added to `config.yaml` by hand | `install-mcp --client hermes` (or `install-hermes-plugin --mcp`) adds the MCP server; doctor reports the plugin enabled, pinned or outdated, and the MCP entry |
| **Cursor / Cline / Claude Desktop / VS Code** | `install-mcp` | Unchanged; doctor shows each one registered, or installed without the entry |
| **Generic MCP client** | `install-mcp --print` | Unchanged; doctor's MCP line says when no known client has the entry, which is expected for a client registered by hand |

The call-graph fix changes what recall returns on the default branch:

| Agent | Before (to v4.21.0) | After |
|---|---|---|
| Claude Code (hooks + MCP) | Prompt-time recall on `main` could name a file linked only by a call that exists on a feature branch, until it decayed | Recall follows the call graph of the code checked out |
| Cursor / Cline / generic MCP | The same, in `neuralmind_query` and search results | The same fix |
| Hermes-Agent plugin | The same, in the per-turn block | The same fix |

## Upgrading

- **Run `neuralmind doctor .`** after upgrading. Its Wiring section names
  anything left behind: a plugin copy from an older release
  (`neuralmind install-hermes-plugin` updates it), or a daemon still running
  the old version (`neuralmind daemon restart`). A running MCP server keeps
  its code until its host restarts it; in Hermes, `/reload-mcp` does.
- **Scripts that read `doctor --json`** keep their `checks` list as it was.
  The top-level `status` can now be `warn` where it was `ok`, from wiring
  warnings; the exit code doesn't change.
- **Build once** (`neuralmind build .`, or let the Git hooks run it) to fill
  the `structural` namespace that holds the call graph. Nothing else to
  change.

## Use cases

- **Existing: [Hermes-Agent with code memory in every turn](../use-cases/hermes-agent.md).**
  Doctor's Wiring section shows whether the plugin is enabled and serving the
  project, and `install-mcp --client hermes` adds the tools beside it. The
  [Hermes pairing tips](../wiki/Tips-and-Tricks-Hermes-Pairing.md) cover
  verifying, upgrading and the switches.
- **Existing: [branch-isolated memory](../use-cases/branch-isolated-memory.md).**
  The call graph each build seeds now stays with the checkout too, so a
  feature branch's calls are gone from `main`'s recall after the next build.
- **New: a wiring check for any setup.** `neuralmind doctor --json` and its
  `wiring.state` tell a provisioning script or a CI job whether a machine's
  agents are connected to the index, not only whether the index is healthy.
