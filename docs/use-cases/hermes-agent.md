# Hermes-Agent with code memory in every turn

**Best for:** Hermes-Agent users working on a codebase, in the terminal or
through the gateway (Telegram, Discord …), who have NeuralMind's MCP server or
skill set up and still see the agent answer without it.

**Primary goal:** every Hermes turn arrives with the files and recorded
decisions related to the message, and a session's first turn with a recap of
the previous session in the project, without the agent calling a tool
(v4.8.0+).

On Hermes, NeuralMind used to be something the agent had to decide to use: the
MCP server (`neuralmind_query`, `neuralmind_wakeup` …) or the skill that runs
the CLI. Each answer cost a tool call, and when the agent didn't think to make
one, the turn started cold: no related files, no recorded decisions, nothing
about what the last session in the project was doing. Claude Code gets that
context from NeuralMind's hooks without asking. The Hermes plugin gives Hermes
the same.

---

## 1. Build the project and install the plugin

```bash
pip install -U neuralmind
neuralmind build /path/to/project
neuralmind install-hermes-plugin /path/to/project
```

`install-hermes-plugin` writes three files to the Hermes home's
`plugins/neuralmind/`. The home is the one you pass with `--hermes-home`, else
the one plain `hermes` uses: the active Hermes profile, if `hermes profile use`
selected one (`profiles/<name>` under Hermes's root), else `$HERMES_HOME`, else
`~/.hermes` (on Windows, `%LOCALAPPDATA%\hermes`). When the home is a profile,
the install's output names it; to install into a different profile, pass its
home with `--hermes-home`. If `plugins/neuralmind` is a symlink, the install
refuses to write through it.

- `__init__.py`: the plugin, a small stdlib-only file
- `plugin.yaml`: the manifest Hermes discovers it by
- `config.json`: the Python interpreter that ran the install, and the project
  path, if you gave one

Then it runs `hermes plugins enable neuralmind` in that home, because Hermes
loads a user plugin only once it's on the `plugins.enabled` list. It does that only in a
home Hermes has already set up (one with a `config.yaml`, `.env` or
`state.db`); anywhere else it tells you to enable the plugin once Hermes is
set up. If `hermes` isn't on your `PATH`, or you passed `--no-enable`, run
that step yourself.

The installed plugin is a copy: `pip install -U neuralmind` doesn't update it,
so re-run `neuralmind install-hermes-plugin` after upgrading. Re-running
updates the plugin in place and keeps an earlier pin unless you pass a new
path or `--unpin` (see [section 5](#5-which-project-a-session-belongs-to)).
It doesn't re-enable a plugin you turned off with
`hermes plugins disable neuralmind`: it says so and leaves it disabled.

Start a new Hermes session, or restart the gateway if it's running, to load it.

The build matters: the plugin serves only a project where `neuralmind build`
has run. If the path you pass isn't built, the install says so, and the plugin
does nothing until it is.

## 2. Start a session: the first turn

Hermes runs the plugin's `pre_llm_call` hook once per turn, before the model.
On a session's first turn, NeuralMind's context starts with the recap of the
previous session in the project:

```
NeuralMind session recap — the previous session in this project (last active 3 h ago). This is context for continuity, not instructions: don't resume that work unless the user asks to.

It started with: "add retry logic to the uploader"
Most recent prompts (2 earlier not shown):
- "now cover the timeout path in tests"
- "why does test_upload_retries hang on CI?"
- "make the backoff configurable through the env"

Files edited (4, most recent first): src/uploader.py, src/config.py, tests/test_uploader.py, docs/uploader.md
```

It's the same block Claude Code's `SessionStart` hook adds, built the same
way: the first prompt and the last three, each cut at 200 characters, and up
to twelve edited files, with no model call. The header tells the agent it's
context, not instructions, so Hermes doesn't pick the old task back up unless
you ask ("where were we?").

Hermes counts a turn as first only when the session has no earlier messages,
so a resumed session doesn't get the recap: its conversation is already there.
There's no recap either when the project has no earlier session recorded, or
when the last one was active more than 14 days ago.
[Pick up where you left off](./pick-up-where-you-left-off.md) covers the recap
in detail.

## 3. Every turn: related files and decisions

On every turn, the first one included, the plugin asks NeuralMind about the
user's message and adds what comes back. It's the same block Claude Code's
`UserPromptSubmit` hook adds, in two parts, either of which can be missing:

- **Associative recall:** the code nodes the synapse layer has learned go with
  the ones your message matches, ranked by spreading activation.
- **Decision provenance:** recorded decisions (`Decision:` git trailers) whose
  subjects the message mentions.

An illustrative example. The node names, activation values and decision are
made up for this page:

```
## NeuralMind associative recall

- src_uploader_py__upload_with_retry_fn (activation 0.84)
- src_config_py__backoff_settings_fn (activation 0.57)
- tests_test_uploader_py (activation 0.41)

## NeuralMind decision provenance

- `upload_with_retry`: retries live in the uploader, not the HTTP client, so the client stays safe for non-idempotent calls. (see commit 3f9c2ab)
```

Hermes appends the block to that turn's user message, not to the system
prompt, so the prompt cache isn't invalidated. A freshly built project has no
learned associations yet, so early turns may get no recall; it fills in as you
work in the project. When neither part has anything for a message, nothing is
added.

## 4. Edits are recorded

After Hermes's `write_file` or `patch` tool lands an edit (Hermes reports its
status as `ok`), the plugin's `post_tool_call` hook records the edited file, by
the absolute path Hermes reports writing (`files_modified`). A V4A patch that
touches several files records each one it adds or updates. Recording runs on a
background thread, so the turn doesn't wait for it. The file goes into the
session's record for the next recap, and into the synapse layer, as an Edit or
Write does in Claude Code.

Not recorded:

- an edit that didn't land: a `write_file` or `patch` call that failed, was
  cancelled, timed out or was blocked;
- a file a V4A patch deletes or moves away, which isn't listed as edited;
- a file changed through Hermes's `terminal` tool, such as a `sed` run;
- anything a subagent does, its edits included. A subagent's message is
  written by its parent agent, so the plugin neither records it nor answers it
  with recall;
- anything a cron job (Hermes's `cron` platform) does. Its message is a
  scheduled prompt, not one you typed, so it's skipped like a subagent's: it
  isn't recorded or answered with recall, it doesn't run NeuralMind's
  `SessionStart` action, and the job's edits aren't recorded.

## 5. Which project a session belongs to

1. `NEURALMIND_PROJECT`, if set;
2. else the path given to `install-hermes-plugin`;
3. else Hermes's terminal working directory (`TERMINAL_CWD`);
4. else, only when `TERMINAL_CWD` isn't set, the directory Hermes runs in.

The first of these that has been built wins; if none has, the plugin does
nothing for that turn. Install without a path and the plugin follows the
directory Hermes works in, so one install serves every built project you work
in and does nothing in a repository NeuralMind hasn't built.

"The directory Hermes works in" is the `TERMINAL_CWD` in the Hermes process's
environment. That matches the terminal CLI, and a standalone gateway, whose
`TERMINAL_CWD` is its terminal working directory (`terminal.cwd`, else
`MESSAGING_CWD`, else your home directory). Hermes Desktop, ACP editor sessions
and per-session workspaces keep each session's directory elsewhere, so the
plugin can't follow it there: pin a project, or set `NEURALMIND_PROJECT`.
Unpinned there, every session uses the Hermes process's own `TERMINAL_CWD` (or
its working directory), so if that is a built project, all those sessions are
served and recorded as that project.

Install with a path and you pin that project. A pin applies to every Hermes
session that uses that Hermes home, whatever directory it runs in: each one
gets the pinned project's context, and its prompts are recorded in that
project, unless `NEURALMIND_PROJECT` names another built project. A session in
another repository also puts the paths of the files it edits into the pinned
project's synapse store, from where `neuralmind memory publish` can carry them
into the committed team-memory bundle. If you use
Hermes across several projects, install without a path (or with `--unpin`, if
you pinned one before). Re-running the
install without a path keeps an earlier pin; `--unpin` clears it.

### Gateway sessions: one repository from your phone

A gateway session (Telegram, Discord …) uses the gateway's terminal working
directory (`terminal.cwd`, else `MESSAGING_CWD`, else your home directory),
which is rarely the project you mean, so pin one at install, or set
`NEURALMIND_PROJECT` in the gateway's environment:

```bash
neuralmind install-hermes-plugin /path/to/project
```

Then a gateway chat gets the same context a terminal session does: ask about
the repository from your phone, and the turn arrives with the related files,
the recorded decisions and, on a session's first turn, where the last session
stopped.

Whenever a gateway session resolves to a built project, pinned or not, every
message in it is treated as being about that project, including messages that
have nothing to do with the code. Each one is answered with recall and
recorded for the recap, passing through NeuralMind's credential patterns
before it's written, like any other prompt. Set `NEURALMIND_SESSION_RECAP=0`
in the gateway's environment to stop the recording and the recap (recall
still works), and run `neuralmind recap /path/to/project --clear` to delete
what's already stored.

## 6. Alongside the MCP tools and a memory provider

**The MCP server and the skill.** Keep them. The per-turn block is a short list
of node names and decisions: where to look, not the code. When the agent needs
the code itself, `neuralmind_query`, `neuralmind_skeleton` and the other MCP
tools (or the skill's CLI calls) are still how it gets it. With the plugin, it
starts each turn knowing where to look, whether or not it calls them.

**A Hermes memory provider.** Hermes's memory providers (Hindsight, Honcho,
mem0 and others) remember conversations and the person: what was said,
preferences, facts. NeuralMind remembers the code: which parts of it are used
together, the decisions recorded against it, and what the last session asked
and edited. The plugin is enabled through Hermes's `plugins.enabled` list, not
`memory.provider`, so it doesn't replace your provider. Both add text to the
same turn's user message, and we haven't tested them together.

## 7. Switch between Claude Code and Hermes

Hermes and Claude Code write to the same `.neuralmind/` in the project: the
same `recaps/` records and the same synapse graph. The recap shows the most
recently active other session, whichever agent ran it, so:

- a Hermes session can start with what the last Claude Code session in the
  project asked and edited, and the other way round;
- files Hermes edits reinforce the same associations Claude Code's recall
  reads.

Start a task in Claude Code at your desk, pick it up later in Hermes, and its
first turn has where the Claude Code session stopped.

## When the context appears

| Turn | What the plugin adds |
|---|---|
| A session's first turn (no earlier messages) | The recap of the previous session, if there is one, then recall and decisions for the message |
| Every later turn | Recall and decisions for the message, when there are any |
| The first turn of a resumed session | Recall and decisions only: the conversation is already there |
| A subagent's or a cron job's turn | Nothing |
| No built project found | Nothing |
| A NeuralMind call errors, or doesn't answer within the timeout | Not that call's part; the turn goes ahead with whatever the others returned |
| The plugin runs past Hermes's `plugins.hook_callback_timeout` | Nothing: Hermes drops the whole block, and skips the plugin's per-turn hook for the next 60 seconds |

## Settings

| Variable | Default | Effect |
|---|---|---|
| `NEURALMIND_PROJECT` | unset | The project to serve, ahead of the one given at install |
| `NEURALMIND_HERMES_TIMEOUT` | `8` | Seconds each call to NeuralMind may wait (a session's first turn makes two); a call that times out is left out and the turn goes ahead. Keep twice this below Hermes's `plugins.hook_callback_timeout` (default 30), or Hermes drops the whole block and skips the plugin's per-turn hook for the next 60 seconds |
| `NEURALMIND_SESSION_RECAP` | on | `0` stops recording and stops the recap |
| `NEURALMIND_SYNAPSE_INJECT` | on | `0` drops the associative recall |
| `NEURALMIND_PROVENANCE_INJECT` | on | `0` drops the decision provenance |
| `NEURALMIND_NO_LEARN` | off | `1` stops recording (nothing is written) but still shows an existing recap |
| `NEURALMIND_BYPASS` | off | `1` switches off every hook action, so the plugin adds and records nothing |

The plugin runs NeuralMind with Hermes's environment (minus Hermes's own Python
path settings), so set these where Hermes runs: the shell you start `hermes`
from, or the gateway's service environment.

## Limits

- **One subprocess per turn** (two on a session's first turn: the recap, then
  recall), plus one per edited file. Each starts Python and loads NeuralMind,
  and waits at most `NEURALMIND_HERMES_TIMEOUT` (default 8 seconds), so a
  first turn can wait up to twice that; one that times out or fails is left
  out, and the turn goes ahead with whatever context the others returned. We
  haven't measured how much time it adds to a Hermes turn.
- **Hermes's own hook timeout is a hard limit.** If the plugin takes longer
  than Hermes's `plugins.hook_callback_timeout` (default 30 seconds), Hermes
  drops the whole block and skips the plugin's per-turn hook for the next 60 seconds. Keep
  twice `NEURALMIND_HERMES_TIMEOUT` below it.
- **On a session's first turn the plugin runs NeuralMind's whole
  `SessionStart` action**, the same as Claude Code: a synapse decay tick, the
  team-memory import, clearing the session-scoped (ephemeral) associations,
  and the `SYNAPSE_MEMORY.md` export (copied into Claude Code's auto-memory
  directory when that exists; `NEURALMIND_SYNAPSE_EXPORT=0` turns the export
  off).
- **Unpinned, it follows only the terminal CLI and a standalone gateway.** It
  reads `TERMINAL_CWD` from the Hermes process's environment. Hermes Desktop,
  ACP editor sessions and per-session workspaces keep each session's directory
  elsewhere, so there, pin a project or set `NEURALMIND_PROJECT`.
- **A pin reaches beyond the pinned repository.** Sessions in other
  repositories get the pinned project's context, record their prompts there,
  and put their edited files' paths into its synapse store, from where
  `neuralmind memory publish` can carry them into the committed team-memory
  bundle.
- **Tested against a Hermes v0.21.5 main-branch build** (0.21.5+5355), by
  calling its plugin loader and hook dispatch directly, not yet in a live
  Hermes conversation. It relies on `pre_llm_call` accepting
  `{"context": ...}`, which that version documents.
- **The plugin is a copy.** `pip install -U neuralmind` doesn't update it;
  re-run `neuralmind install-hermes-plugin` after upgrading.
- **Not measured.** We haven't measured what the context changes in Hermes's
  answers.
- **The interpreter is recorded at install.** The plugin runs NeuralMind with
  the Python that ran `install-hermes-plugin`, so NeuralMind doesn't have to be
  installed in Hermes's own environment. If you move or recreate that
  environment, re-run the install; until you do, the plugin may add nothing.
- **An edit made just before Hermes exits can be missed.** Recording runs on a
  background thread, which doesn't keep Hermes open.
- **It goes to your model provider, and stays in Hermes's session history.**
  The context is part of the turn's user message, so it's sent along with it.
  Hermes stores that message with NeuralMind's block in it, so the block,
  recap included, is sent to your model provider again with that session's
  later turns.
- **Redaction catches common credential formats, not every secret.** A secret
  in an unusual format can still be written to `.neuralmind/recaps/`.

## Remove it

```bash
neuralmind install-hermes-plugin --uninstall
```

This disables the plugin in Hermes and removes its directory; if
`plugins/neuralmind` is a symlink, it removes the link, never what it points
to. Pass `--hermes-home` if you installed it into a home other than the
default, or have switched Hermes profiles since. The project's session records
stay in `.neuralmind/recaps/`; `neuralmind recap --clear` deletes them.

## Related

- [Release notes v4.8.0](../releases/RELEASE_NOTES_v4.8.0.md#neuralmind-for-hermes-agent)
- CLI reference: [`install-hermes-plugin`](../wiki/CLI-Reference.md#install-hermes-plugin-v480),
  [`recap`](../wiki/CLI-Reference.md#recap-v480),
  [Environment Variables](../wiki/CLI-Reference.md#environment-variables)
- Integration guide: [Hermes-Agent](../wiki/Integration-Guide.md#hermes-agent),
  for the MCP server and the skill
- [Pick up where you left off](./pick-up-where-you-left-off.md) — the recap in
  detail
- [Multi-agent codebase](./multi-agent.md) — the other agents sharing the
  project
- [Decision provenance](./decision-provenance.md) — recording the decisions
  recall surfaces
