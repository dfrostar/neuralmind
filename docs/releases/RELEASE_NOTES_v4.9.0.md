# NeuralMind v4.9.0 — Hermes-Agent gets NeuralMind's context in every turn, without a tool call

**Type:** Minor release | **Theme:** Hermes-Agent integration

v4.8.0 gave Claude Code a [session recap](RELEASE_NOTES_v4.8.0.md): a new
session starts with where the last one left off. Claude Code already got
NeuralMind's related files with every prompt, through its hooks. Hermes-Agent
got neither unless the agent decided to call a tool. v4.9.0 adds a Hermes
plugin that gives Hermes both, before the model runs, with no tool call.

## NeuralMind for Hermes-Agent

On Hermes, NeuralMind was something the agent had to decide to use: an MCP
server, or a skill that runs the CLI. Each answer cost a tool call, and when
the agent didn't think to call it, nothing happened. v4.9.0 adds a Hermes
plugin that puts NeuralMind's context into every turn before the model runs,
the way the hooks already do in Claude Code.

```bash
neuralmind build /path/to/project
neuralmind install-hermes-plugin /path/to/project
```

The command writes the plugin into the Hermes home's `plugins/neuralmind/`:
the one `--hermes-home` names, else the one plain `hermes` uses: the active
Hermes profile's, if `hermes profile use` selected one
(`<root>/profiles/<name>`), else `$HERMES_HOME`, else Hermes's default
`~/.hermes` (on Windows, `%LOCALAPPDATA%\hermes`). When that's a profile, the output names it. The
command then runs `hermes plugins enable neuralmind` in that same home, but
only in a home Hermes has already set up (one with a `config.yaml`, `.env` or
`state.db`); anywhere else it tells you to enable the plugin once Hermes is
set up. Start a new Hermes session, or restart the gateway, to load it.

- **Every turn** (Hermes's `pre_llm_call` hook): the files and recorded
  decisions related to the user's message, the same block Claude Code's
  `UserPromptSubmit` hook adds. Hermes appends it to that turn's user message,
  not to the system prompt, so the prompt cache isn't invalidated.
- **A session's first turn** also starts with the [session recap](RELEASE_NOTES_v4.8.0.md) (v4.8.0). Hermes counts
  a turn as first only when the session has no earlier messages, so a resumed
  session doesn't get it.
- **After `write_file` and `patch`** (Hermes's `post_tool_call` hook): each
  file the edit wrote is recorded, by the absolute path Hermes reports
  (`files_modified`), on a background thread, for the recap and the synapse
  layer. Only an edit that landed counts: Hermes has to report its status as
  `ok`, so a failed, cancelled, timed-out or blocked edit isn't recorded. A
  file a V4A patch deletes or moves away isn't listed as edited, a patch that
  changes nothing isn't recorded, and neither is a file
  changed through the terminal.
- **Subagents and cron jobs are skipped.** A subagent's message is written by
  its parent agent, and a cron job's (Hermes's `cron` platform) is a scheduled
  prompt, not one you typed. Neither is recorded or answered with recall,
  neither runs the `SessionStart` action, and their edits aren't recorded
  either.
- **One record for both agents.** Hermes and Claude Code write to the same
  `.neuralmind/recaps/`, so a Hermes session can start with what the last
  Claude Code session in the project did, and the other way round.

How it works: the plugin is a small stdlib-only file. Each action runs
`python -m neuralmind _hook <action>` with the payload Claude Code would send,
using the Python interpreter that ran the install. Hermes gets the same
behavior and the same switches (`NEURALMIND_BYPASS`,
`NEURALMIND_SYNAPSE_INJECT`, `NEURALMIND_SESSION_RECAP` …), and NeuralMind
doesn't have to be installed in Hermes's own environment. The subprocess runs from
the plugin's own directory with `PYTHONSAFEPATH=1`, so a repository you work in
can't put its own `neuralmind` module ahead of the installed one.

Which project a Hermes session belongs to:

1. `NEURALMIND_PROJECT`, if set;
2. else the path given to `install-hermes-plugin`;
3. else Hermes's terminal working directory (`TERMINAL_CWD`);
4. else, only when `TERMINAL_CWD` isn't set, the directory Hermes runs in.

The first of these that has been built wins; if none has, the plugin does
nothing. `TERMINAL_CWD` is read from the Hermes process's environment, so a
`cd` the agent runs later in a session doesn't change the project. That's the
directory the terminal CLI and a standalone gateway work in. A gateway
session (Telegram, Discord …) uses the gateway's terminal working directory
(`terminal.cwd`, else `MESSAGING_CWD`, else your home directory), which is
rarely the project you mean, so pin one at install or set
`NEURALMIND_PROJECT`. Hermes Desktop, ACP editor sessions and per-session
workspaces keep each session's directory elsewhere, not in `TERMINAL_CWD`, so
with those, too, pin a project or set `NEURALMIND_PROJECT`. Whenever a gateway
session resolves to a built project, pinned or not, every message in it is
recorded for the recap, redacted like any other prompt;
`NEURALMIND_SESSION_RECAP=0` turns that off.

A pin applies to every Hermes session that uses that Hermes home, whatever
directory it runs in: each one gets the pinned project's context, and its
prompts are recorded in that project. A session in another repository also
puts the paths of the files it edits into the pinned project's synapse store,
from where `neuralmind memory publish` can carry them into the committed
team-memory bundle. If you use Hermes across several projects, install
without a path (or with `--unpin`, if you pinned one before), so the plugin
follows the directory Hermes works in (in the terminal CLI and a standalone
gateway, as above) and does nothing in a repository NeuralMind hasn't built.
Re-running the install without a path keeps an earlier pin; `--unpin` clears
it.

Limits:

- **One subprocess per turn** (two on a session's first turn: the recap, then
  recall), plus one per edited file. Each waits at most
  `NEURALMIND_HERMES_TIMEOUT` (default 8 seconds), so a first turn can wait up
  to twice that; one that times out or fails is left out, and the turn goes
  ahead with whatever context the others returned. Keep twice the timeout
  below Hermes's `plugins.hook_callback_timeout` (default 30 seconds): a
  plugin that runs past it loses its whole block, and Hermes skips the plugin's per-turn hook for the
  next 60 seconds.
- **The context stays in Hermes's session history.** Hermes stores the turn's
  message with NeuralMind's block in it, so the block, recap included, is sent
  to your model provider again with that session's later turns.
- **On a session's first turn the plugin runs NeuralMind's whole
  `SessionStart` action**, the same as Claude Code, including a synapse decay
  tick, the team-memory import, clearing the session-scoped (ephemeral)
  associations, and the `SYNAPSE_MEMORY.md` export (copied into Claude
  Code's auto-memory directory when that exists;
  `NEURALMIND_SYNAPSE_EXPORT=0` turns the export off).
- **Tested against a Hermes v0.21.5 main-branch build** (0.21.5+5355), by
  calling its plugin loader and hook dispatch directly, not yet in a live
  Hermes conversation. It relies on `pre_llm_call` accepting
  `{"context": ...}`, which that version documents.
- **The plugin is a copy.** `pip install -U neuralmind` doesn't update it;
  re-run `neuralmind install-hermes-plugin` after upgrading. A re-run doesn't
  turn back on a plugin you switched off with `hermes plugins disable
  neuralmind`: it says so and leaves it disabled.
- **Not measured.** As with the recap, we haven't measured what the context
  changes in Hermes's answers.

`neuralmind install-hermes-plugin --uninstall` disables it in that same home
and removes it. If `plugins/neuralmind` is a symlink, it removes the link,
never what it points to; the install refuses to write through one.

## Also in this release

- **`ghcr.io/dfrostar/neuralmind:latest` follows the newest release.** The
  Docker workflow moved `:latest` to whichever version it built last, so
  rebuilding an older tag pointed it back at that version. On 2026-10-06 a
  re-pushed `v1.16.0` tag pointed `:latest` at v1.16.0's image.
  `:latest` now moves only for the highest `vX.Y.Z` tag; a
  rebuild of an older version pushes just its own `:vX.Y.Z`. To pin, pull
  `:v4.9.0` rather than `:latest`.
- **The session recap no longer depends on directory order.** Two sessions
  whose last activity shares a timestamp (writes inside one clock tick, about
  15.6 ms on Windows) were decided by whichever file the directory listed
  first. The recap now goes to the one modified last.

## Per-agent expectations

| Agent | What changes |
|---|---|
| **Hermes-Agent** (a built project, with `neuralmind install-hermes-plugin`) | Every turn gets NeuralMind's related files and decisions, and a session's first turn starts with the recap. Subagent and cron turns are skipped. |
| **Claude Code** | Nothing new: its hooks already do this. Hermes and Claude Code share `.neuralmind/recaps/`, so each can start with what the other did. |
| **Cursor / Cline / generic MCP clients** | Nothing. These hosts run neither Claude Code hooks nor Hermes plugins. |
| **Other agents with a shell** | Nothing automatic. An agent that can run commands can call `neuralmind recap` to read what the last session in the project did. |

## Settings

| Variable | Default | Effect |
|---|---|---|
| `NEURALMIND_PROJECT` | unset | Hermes plugin: the project to serve, ahead of the one given at install |
| `NEURALMIND_HERMES_TIMEOUT` | `8` | Hermes plugin: seconds each call to NeuralMind may wait (a session's first turn makes two); a call that times out is left out and the turn goes ahead. Keep twice this below Hermes's `plugins.hook_callback_timeout` (default 30), or Hermes drops the whole block |

The plugin runs the same hook actions as Claude Code's hooks, so their switches
apply to it too: `NEURALMIND_BYPASS`, `NEURALMIND_SYNAPSE_INJECT`,
`NEURALMIND_SESSION_RECAP`, `NEURALMIND_NO_LEARN` and the rest.

## Upgrading

`pip install -U neuralmind`, then run `neuralmind install-hermes-plugin [path]`
once. The installed plugin is a copy, so run it again after later upgrades; a
re-run keeps an earlier pin and leaves a plugin you disabled disabled.

## Related

- Use case: [Hermes-Agent with code memory in every turn](../use-cases/hermes-agent.md)
- Use case: [Pick up where you left off](../use-cases/pick-up-where-you-left-off.md)
- Integration guide: [Hermes-Agent](../wiki/Integration-Guide.md#hermes-agent)
- CLI reference: [`install-hermes-plugin`](../wiki/CLI-Reference.md#install-hermes-plugin-v490),
  [Environment Variables](../wiki/CLI-Reference.md#environment-variables)
- Previous release: [v4.8.1](RELEASE_NOTES_v4.8.1.md) · [v4.8.0](RELEASE_NOTES_v4.8.0.md)
