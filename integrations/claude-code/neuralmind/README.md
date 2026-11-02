# NeuralMind for Claude Code

A Claude Code plugin that wires [NeuralMind](https://github.com/dfrostar/neuralmind)
into every session with one install: the `neuralmind-mcp` server and the
lifecycle hooks `neuralmind install-hooks` writes. It packages commands the
`neuralmind` Python package provides. It doesn't install that package.

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

On Claude Code 2.1.275 or later, one command does both:
`/plugin install neuralmind --marketplace dfrostar/neuralmind`. From a shell,
the same commands run as `claude plugin marketplace add …` and
`claude plugin install …`. Start a new session to load it.

## What it adds

| Piece | What it is |
|-------|------------|
| MCP server `neuralmind` | `neuralmind-mcp` over stdio, started in the session's directory. Its tools appear as `mcp__plugin_neuralmind_neuralmind__*` |
| `SessionStart` | Decay tick, `SYNAPSE_MEMORY.md` export, and the previous session's recap on a fresh or cleared session |
| `UserPromptSubmit` | The files, symbols and decisions the prompt matches, when its best match clears the similarity cutoff |
| `PreToolUse` (Edit, Write) | Recorded decisions that went stale for the file about to change |
| `PostToolUse` (Read, Bash, Grep, Edit, Write) | Read dedup, `neuralmind last`, edit activity for the synapse layer |
| `PreCompact`, `Stop`, `SessionEnd` | Hub normalisation, the summary cadence, the session digest |

Every hook does nothing in a directory without a `.neuralmind/` index, so
enabling the plugin for all projects changes nothing in the ones you haven't
built: `neuralmind build .` is how a project opts in. `NEURALMIND_BYPASS=1`
switches every hook action off.

## Alongside `install-hooks` and `install-mcp`

You don't need to remove an earlier setup. Claude Code runs a plugin's hook
beside an identical one from a settings file, so with both, each action would
happen twice. From v4.25.0, `neuralmind` sees which copy is calling it, and the
plugin's copy does nothing for an action that `.claude/settings.json`,
`.claude/settings.local.json` or the user's `settings.json` already registers.
An older `neuralmind` on PATH runs both copies: upgrade it, or run
`neuralmind install-hooks --uninstall` (and `--global` if you used it).

A project `.mcp.json` entry that starts `neuralmind-mcp` takes precedence:
Claude Code then doesn't start the plugin's server, and the tools keep their
`mcp__neuralmind__*` names.

`neuralmind doctor` counts the enabled plugin as both the Claude Code hooks
and the Claude Code MCP registration.

## Updating

The plugin's version follows NeuralMind's releases. Claude Code doesn't
auto-update third-party marketplaces unless you turn that on under
`/plugin` > Marketplaces. To update by hand, run
`claude plugin marketplace update neuralmind`, then
`claude plugin update neuralmind@neuralmind`, and restart. Upgrade the Python
package separately (`pipx upgrade neuralmind`).

## Source

The plugin's files are copies of what the package writes: `hooks/hooks.json`
holds `neuralmind.hooks._hook_block()` and `.mcp.json` holds
`neuralmind.mcp_install.server_entry()`. `tests/test_claude_code_plugin.py`
fails when either copy drifts, or when the version stops matching the
release; release-please bumps the version with every release.
