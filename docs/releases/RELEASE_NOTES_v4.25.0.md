# NeuralMind v4.25.0 — a Claude Code plugin: the MCP server and the hooks in one install

**Type:** Minor release | **Theme:** Claude Code integration. NeuralMind's MCP server and lifecycle hooks ship as a Claude Code plugin from this repository's marketplace, and a project that already has `install-hooks` doesn't get every hook twice

Wiring NeuralMind into Claude Code took two commands per project:
`neuralmind install-mcp --client claude-code` for the tools and
`neuralmind install-hooks` for the session recap, the per-prompt block and the
stale-decision guard (or `--global`, which a teammate had to know about). This
release packages both as a Claude Code plugin, so `/plugin install` wires
every project you open.

## Install

```bash
pipx install neuralmind        # or pip / uv: the commands must be on PATH
cd your-project && neuralmind build .
```

Then, in Claude Code:

```
/plugin marketplace add dfrostar/neuralmind
/plugin install neuralmind@neuralmind
```

On Claude Code 2.1.275 or later, `/plugin install neuralmind --marketplace
dfrostar/neuralmind` does both. The plugin lives in
[`integrations/claude-code/neuralmind/`](https://github.com/dfrostar/neuralmind/tree/main/integrations/claude-code/neuralmind),
and the marketplace file is `.claude-plugin/marketplace.json` at the
repository root.

## What's in it

| Piece | Same as |
|-------|---------|
| MCP server `neuralmind` (`neuralmind-mcp`, stdio) | `neuralmind install-mcp --client claude-code` |
| `SessionStart`, `UserPromptSubmit`, `PreToolUse`, `PostToolUse`, `PreCompact`, `Stop`, `SessionEnd` hooks | `neuralmind install-hooks` |

The files are copies of what those commands write, and
`tests/test_claude_code_plugin.py` fails when either copy drifts from the
package. It also fails when the plugin's version stops matching the release:
Claude Code keeps users on the copy it cached until that version string
changes, so release-please now bumps it with every release.

## What the agent sees after installing

The same as with `install-mcp` and `install-hooks`. A fresh or cleared session
opens with the previous session's recap, a prompt about the code arrives with
the files and symbols it matches, and an edit to a file with a stale decision
gets that decision first. The MCP server sends the same instructions and lists
the same six tools. Only their names differ: plugin tools are
`mcp__plugin_neuralmind_neuralmind__neuralmind_search` and so on, not
`mcp__neuralmind__neuralmind_search`. A permission rule or a hook matcher
written for the old names doesn't match them.

Every hook does nothing in a directory without a `.neuralmind/` index, so
enabling the plugin everywhere changes nothing in projects you haven't built.

## Alongside an existing setup

Claude Code runs a plugin's hook beside an identical one from a settings file,
not instead of it. In a test project with both the plugin and `install-hooks`,
on Claude Code 2.1.309, every NeuralMind hook ran twice, and the recap store
recorded each prompt twice. Left alone, that would also double the recall
block and every synapse update.

Claude Code exports `CLAUDE_PLUGIN_ROOT` to a plugin's hooks and not to a
settings file's. Now, when `neuralmind _hook` runs from the plugin and
`.claude/settings.json`, `.claude/settings.local.json` or the user's
`settings.json` (under `CLAUDE_CONFIG_DIR` when that's set) has a handler
that fires the same action for this event, the plugin's copy exits at once and
the settings copy does the work. "For this event" includes the matcher: a
settings handler for `Edit` alone doesn't run on `Write`, so the plugin's
`Write` hook still records the written file. In the same test project, the
prompt was recorded once with both installed, and once with the plugin alone.
An action an older `install-hooks` block lacks (a v3 block had no `Stop`)
still runs from the plugin.

MCP needed nothing: when a project `.mcp.json` already starts
`neuralmind-mcp`, Claude Code doesn't start the plugin's server ("duplicates
manually-configured"), and the tools keep their `mcp__neuralmind__*` names.

## `doctor` and `build`

`neuralmind doctor` reads `enabledPlugins` in the user, project and project
local settings files, where `/plugin install` records the plugin, and counts
it as both the Claude Code hooks and the Claude Code MCP registration.
A later scope overrides an earlier one, so a project that switches the plugin
off isn't counted. Before, a plugin user saw "Claude Code hooks: not
installed", and `neuralmind build` offered `neuralmind install-hooks`.

## Per-agent expectations

| Agent | What changes |
|-------|--------------|
| **Claude Code** (plugin installed) | One install wires the MCP server and the hooks for every project, with the tools under `mcp__plugin_neuralmind_neuralmind__*`. Behaviour is the same as `install-mcp` plus `install-hooks`. |
| **Claude Code** (`install-hooks` / `install-mcp`, no plugin) | Nothing. Those commands keep working and stay supported. |
| **Claude Code** (both) | Each hook action runs once, from the settings file. The project's MCP entry wins over the plugin's. |
| **Claude Desktop / claude.ai** | Nothing. Claude Code plugins don't load there; Claude Desktop keeps `neuralmind install-mcp --client claude-desktop`. |
| **Cursor / Cline / Hermes-Agent / generic MCP** | Nothing. |

## Limits

- **The plugin needs the Python package.** It registers commands, it doesn't
  ship them. If `neuralmind` isn't on the PATH Claude Code starts with, each
  hook fails with Claude Code's non-blocking "command not found" notice and
  the MCP server doesn't connect.
- **An older `neuralmind` runs both copies.** The guard is in the CLI, so
  with v4.24.0 or earlier on PATH, a project with `install-hooks` still gets
  every hook twice. Upgrade, or run `neuralmind install-hooks --uninstall`.
- **No skill.** The portable [`skills/neuralmind`](https://github.com/dfrostar/neuralmind/blob/main/skills/neuralmind/SKILL.md)
  is written for Hermes, OpenClaw and Agent Zero, and the MCP server's
  instructions already tell Claude Code when to call each tool. Whether a
  skill would change how often the agent calls them isn't measured.
- **Updates aren't automatic.** Claude Code doesn't auto-update third-party
  marketplaces unless you turn it on under `/plugin` > Marketplaces.
- **Checked headless, not in a conversation.** On Claude Code 2.1.309 on
  macOS, installed from a local copy of the marketplace: the server connected
  and listed its six tools, all seven hook events fired, and the guard
  behaved as described above. No model turn used the plugin's tools, and
  Windows hasn't been tried.

## Upgrading

`pipx upgrade neuralmind` (or `pip install -U neuralmind`), then install the
plugin as above. To update the plugin later:
`claude plugin marketplace update neuralmind` and
`claude plugin update neuralmind@neuralmind`, then restart.

## Related

- Plugin: [README](https://github.com/dfrostar/neuralmind/blob/main/integrations/claude-code/neuralmind/README.md)
- Use case: [Claude Code](../use-cases/claude-code.md)
- Integration guide: [Claude Code](../wiki/Integration-Guide.md#claude-code)
- CLI reference: [`install-hooks`](../wiki/CLI-Reference.md#install-hooks)
- Previous release: [v4.24.0](RELEASE_NOTES_v4.24.0.md)
