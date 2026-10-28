# NeuralMind v4.23.1 — the Hermes plugin serves each session's own project under Hermes 0.22's gateway

**Type:** Patch release | **Theme:** an unpinned Hermes plugin gives CLI, TUI and Desktop sessions their project's context again on Hermes 0.22.2 and later

Since Hermes 0.22.2, the hooks of every local session (CLI, TUI and Desktop)
run in one Hermes gateway process, not in the `hermes` command you start. That
process's own working directory and environment belong to no session. Hermes's
plugin guide says so, and gives plugins `ctx.session_cwd()` for the calling
session's working directory instead.

The NeuralMind plugin didn't ask for it. Unpinned, it served the first built
project among `NEURALMIND_PROJECT`, `TERMINAL_CWD` and the current directory,
all read from the gateway's own environment. On a 32-core Linux machine running
Hermes 0.22.5, the gateway's `TERMINAL_CWD` was the user's home directory,
which isn't a built project. So every `hermes chat` turn in a built
hermes-agent checkout got **no NeuralMind context at all**: no recall block,
and no recap on a session's first turn. The plugin also wrote nothing for the
session and logged no warning. Setting `NEURALMIND_PROJECT` on the command
didn't help: the variable stayed in the client process.

---

## What changed

### Under the gateway, the plugin follows the session's working directory

- **Which project, in order:**
  1. `NEURALMIND_PROJECT`, if set where the plugin runs;
  2. else the project pinned at install;
  3. else the directory Hermes works in for the session.

  The first of these that has been built wins, as before.
- **"The directory Hermes works in" is now `ctx.session_cwd()`** whenever
  Hermes provides it (0.22.2 and later). That's where the CLI, TUI or Desktop
  session was started, or, for a messaging chat, the profile's terminal
  working directory.
- **A session with no working directory gets nothing.** Hermes reports that
  as an empty string. The plugin then doesn't fall back to the gateway's own
  directory or `TERMINAL_CWD`, which are shared by every session.
- **Recorded edits and reads** that Hermes reports by a relative path resolve
  against the same session directory.
- **Older Hermes is unchanged.** It runs hooks in the client process, where
  `TERMINAL_CWD`, else the current directory, is still the rule.

### `NEURALMIND_PROJECT` counts only where the hooks run

Under the gateway, setting `NEURALMIND_PROJECT` (or any NeuralMind switch, such
as `NEURALMIND_SYNAPSE_EXPORT`) on the `hermes` command you start doesn't reach
the plugin. Only the gateway's own environment does, and there it applies to
every session, like a pin. The docs that said to set it for Desktop, ACP and
per-session workspaces now say this instead.

---

## What the agent sees post-install

| Agent | Before v4.23.1 | From v4.23.1 |
|---|---|---|
| **Hermes-Agent plugin**, Hermes 0.22.2+, unpinned | No NeuralMind block or recap in CLI, TUI and Desktop sessions, unless the gateway's own `TERMINAL_CWD` or working directory was a built project, and then every session got *that* project's | Each session gets its own project's block, and its recap on its first turn, when its working directory is built |
| **Hermes-Agent plugin**, older Hermes, or pinned | Unchanged | Unchanged |
| **Claude Code / Cursor / Cline / generic MCP** | Unchanged | Unchanged |

## Measured

Checked on one machine and one Hermes version, not benchmarked: a 32-core
Linux laptop running Hermes 0.22.5, with the plugin installed unpinned. The
session ran in a built clone of hermes-agent, and the model was a local
`gpt-oss:20b-64k` served by Ollama.

| | v4.23.0 plugin | This change |
|---|---|---|
| NeuralMind hook processes a `hermes chat` turn started in its first 40 s | 0 | 2: `session-start` at 2.6 s, `prompt-submit` at 10.6 s |
| A recap file for the session in the clone's `.neuralmind/recaps/` | none | written |
| The NeuralMind block in the user message Hermes sent the model | absent (2 turns checked) | present (1 full turn, 582 s on CPU) |

- **The gateway kept the old plugin code until it reloaded its plugins.**
  `hermes plugins disable neuralmind && hermes plugins enable neuralmind` did
  that; replacing the plugin file alone didn't.
- **The first turn's `session-start` call was stopped at 8 s once.** That was
  the gateway, running with the memory export on: `NEURALMIND_SYNAPSE_EXPORT=0`
  had been set only on the `hermes` command.
  [#741](https://github.com/dfrostar/neuralmind/pull/741), which moves that
  hook's slow work out of the call, covers that. The plugin logs each kind of warning once per process, so the
  log can't show whether the later full turn's call was stopped too.
- **This change is about delivery, not ranking.** For the full turn's wording
  ("which file in this repo decides whether it is a rate limit or a context
  overflow?") the block listed `agent/auxiliary_client.py` first and not
  `agent/error_classifier.py`, the file the real fix changed. The model named
  the file the block listed.

## Tests

`tests/test_hermes_plugin.py` checks that:
- `register()` keeps Hermes's plugin context;
- under the gateway, the session's working directory is the project, ahead of
  a built `TERMINAL_CWD` and a built gateway working directory;
- a session with no working directory (`""`, blank or `None`), or whose
  `session_cwd()` raises, gets no project and no hook call;
- `NEURALMIND_PROJECT` and a pin still come first;
- relative edit and read paths resolve against the session's directory.

The existing tests run as on older Hermes, where the plugin context has no
`session_cwd`.

## Upgrading

The installed plugin is a copy, so:

```bash
pip install -U neuralmind
```

```bash
neuralmind install-hermes-plugin
```

A gateway that's already running keeps the plugin code it loaded. Reload it:

```bash
hermes plugins disable neuralmind && hermes plugins enable neuralmind
```

That printed *Gateway reloaded plugins* on Hermes 0.22.5; restarting the
gateway works too. If you had set `NEURALMIND_PROJECT` on the command you start
Hermes with, to work around this, you can drop it.

## Use cases

- **Existing: [NeuralMind in Hermes](../use-cases/hermes-agent.md).** One
  unpinned install serves every built project you open a Hermes session in, on
  Hermes 0.22.2 and later. Before, it usually served none.
- **Potential: one Hermes setup across several repositories.** The gateway
  serves each session from that session's own directory, so, per Hermes's
  plugin docs, a TUI in one repository and a Desktop session in another each
  get their own project's context. Only `hermes chat` was checked live. Before,
  pins and `NEURALMIND_PROJECT` were the only way to get any context there,
  and both apply to every session.
