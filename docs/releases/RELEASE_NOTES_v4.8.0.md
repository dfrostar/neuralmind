# NeuralMind v4.8.0 — a new session starts where the last one left off, and Hermes gets context without asking

**Type:** Minor release | **Themes:** session continuity (the session recap) · Hermes-Agent gets every turn's context from a plugin

A new Claude Code session used to start cold. NeuralMind gave it the code it
had learned (`SYNAPSE_MEMORY.md`, per-prompt recall), but not the work: what
you were doing yesterday, which files you had open, what you asked last. You
re-explained it, or asked the agent to go and find out.

v4.8.0 records each session's prompts and edited files as you work. The next
fresh or cleared session starts with a short recap of the most recent one. A new
Hermes-Agent plugin brings the same recap, and NeuralMind's per-turn recall, to
Hermes ([below](#neuralmind-for-hermes-agent)):

1. **No new hooks.** Recording rides on the `UserPromptSubmit` and Edit/Write
   hooks NeuralMind already installs; the recap arrives through the existing
   `SessionStart` hook. The hook block's version is unchanged, so an
   existing `neuralmind install-hooks` setup picks it up on upgrade.
2. **No model call.** The recap is assembled from what the hook payloads
   already carry: the prompt text, the edited file's path, the session id.
   Nothing summarizes it, so it costs a few small file reads at session
   start.
3. **Only when the conversation is missing.** A resumed session already has its
   conversation, and a compacted one has Claude Code's own summary, so the
   recap is injected only on a fresh start and after `/clear`.
4. **`neuralmind recap`** prints what the next session will see, and
   `neuralmind recap --clear` deletes the stored records.

## What the agent actually sees

At the start of a new session, before your first message, the agent's
context gains this block:

```
NeuralMind session recap — the previous session in this project (last active 3 h ago). This is context for continuity, not instructions: don't resume that work unless the user asks to.

It started with: "add retry logic to the uploader"
Most recent prompts (2 earlier not shown):
- "now cover the timeout path in tests"
- "why does test_upload_retries hang on CI?"
- "make the backoff configurable through the env"

Files edited (4, most recent first): src/uploader.py, src/config.py, tests/test_uploader.py, docs/uploader.md
```

- **The first prompt and the last three**, each collapsed to one line and cut
  at 200 characters. The first prompt is usually the session's goal; the last
  ones are where it stopped.
- **Up to twelve edited files**, most recent first, relative to the project
  root (a file outside the project shows as `~/…` or its full path). Control
  characters are removed from prompts and paths, and a path longer than 160
  characters keeps its last 160. Only
  Edit and Write are recorded, so a file changed through a shell command isn't
  listed.
- **"Not instructions."** The block says so, so the agent doesn't pick an old
  task back up on its own. Ask "where were we?" or "carry on" and it has what
  it needs to answer.
- **The most recently active other session**, by the times recorded in each
  record. If two sessions run in the same project, whichever was active most
  recently counts as "where we left off".

## Per-agent expectations

| Agent | What changes |
|---|---|
| **Claude Code** (a built project, with `neuralmind install-hooks`) | A fresh or cleared session starts with the recap above. Resumed and compacted sessions don't get it. |
| **Cursor / Cline / generic MCP clients** | Nothing. These hosts don't run Claude Code hooks, so nothing is recorded and nothing is injected. |
| **Hermes-Agent** (with `neuralmind install-hermes-plugin`) | A session's first turn starts with the recap, and every turn gets NeuralMind's related files and decisions. See [NeuralMind for Hermes-Agent](#neuralmind-for-hermes-agent). |
| **Other agents with a shell** | Nothing automatic. An agent that can run commands can call `neuralmind recap` to read what the last session in the project did. |

## NeuralMind for Hermes-Agent

On Hermes, NeuralMind was something the agent had to decide to use: an MCP
server, or a skill that runs the CLI. Each answer cost a tool call, and when
the agent didn't think to call it, nothing happened. v4.8.0 adds a Hermes
plugin that puts NeuralMind's context into every turn before the model runs,
the way the hooks already do in Claude Code.

```bash
neuralmind build /path/to/project
neuralmind install-hermes-plugin /path/to/project
```

The command writes the plugin into the Hermes home's `plugins/neuralmind/`:
`$HERMES_HOME`, else Hermes's default, `~/.hermes` (on Windows,
`%LOCALAPPDATA%\hermes`). A Hermes profile has a home of its own; pass it with
`--hermes-home`. The command then runs `hermes plugins enable neuralmind`, but
only in a home Hermes has already set up (one with a `config.yaml`, `.env` or
`state.db`); anywhere else it tells you to enable the plugin once Hermes is
set up. Start a new Hermes session, or restart the gateway, to load it.

- **Every turn** (Hermes's `pre_llm_call` hook): the files and recorded
  decisions related to the user's message, the same block Claude Code's
  `UserPromptSubmit` hook adds. Hermes appends it to that turn's user message,
  not to the system prompt, so the prompt cache isn't invalidated.
- **A session's first turn** also starts with the session recap. Hermes counts
  a turn as first only when the session has no earlier messages, so a resumed
  session doesn't get it.
- **After `write_file` and `patch`** (Hermes's `post_tool_call` hook): the
  edited file is recorded, on a background thread, for the recap and the
  synapse layer. A failed edit isn't recorded, and neither is a file changed
  through the terminal.
- **Subagents are skipped.** A subagent's message is written by its parent
  agent, so it's neither recorded nor answered with recall, and the subagent's
  edits aren't recorded either.
- **One record for both agents.** Hermes and Claude Code write to the same
  `.neuralmind/recaps/`, so a Hermes session can start with what the last
  Claude Code session in the project did, and the other way round.

How it works: the plugin is a small stdlib-only file. Each action runs
`python -m neuralmind _hook <action>` with the payload Claude Code would send,
using the Python interpreter that ran the install. Hermes gets the same
behavior and the same switches (`NEURALMIND_BYPASS`,
`NEURALMIND_SYNAPSE_INJECT`, `NEURALMIND_SESSION_RECAP` …), and NeuralMind
doesn't have to be installed in Hermes's own environment.

Which project a Hermes session belongs to:

1. `NEURALMIND_PROJECT`, if set;
2. else the path given to `install-hermes-plugin`;
3. else Hermes's terminal working directory (`TERMINAL_CWD`);
4. else, only when `TERMINAL_CWD` isn't set, the directory Hermes runs in.

The first of these that has been built wins; if none has, the plugin does
nothing. `TERMINAL_CWD` is read from Hermes's environment, so a `cd` the agent
runs later in a session doesn't change the project. A gateway session (Telegram, Discord …) uses the gateway's working
directory, which is rarely the project you mean, so pin one at install or set
`NEURALMIND_PROJECT`. Whenever a gateway session resolves to a built project,
pinned or not, every message in it is recorded for the recap, redacted like any
other prompt; `NEURALMIND_SESSION_RECAP=0` turns that off.

A pin applies to every Hermes session that uses that Hermes home, whatever
directory it runs in: each one gets the pinned project's context, and its
prompts are recorded in that project. If you use Hermes across several
projects, install without a path (or with `--unpin`, if you pinned one
before), so the plugin follows the directory Hermes works in and does nothing in a repository NeuralMind hasn't built. Re-running
the install without a path keeps an earlier pin; `--unpin` clears it.

Limits:

- **One subprocess per turn** (two on a session's first turn: the recap, then
  recall), plus one per edited file. Each waits at most
  `NEURALMIND_HERMES_TIMEOUT` (default 8 seconds), so a first turn can wait up
  to twice that; one that times out or fails is left out, and the turn goes
  ahead with whatever context the others returned.
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
  re-run `neuralmind install-hermes-plugin` after upgrading.
- **Not measured.** As with the recap, we haven't measured what the context
  changes in Hermes's answers.

`neuralmind install-hermes-plugin --uninstall` disables and removes it.

## Where it's stored, and what's redacted

- Recording happens only in a project where `neuralmind build` has run (it
  leaves `.neuralmind/build_status.json`, which no hook creates). Hooks
  installed globally fire in every repository, but they record no prompts in
  the ones NeuralMind hasn't built.
- A `.neuralmind/` or `.neuralmind/recaps/` that is a symlink is refused, and
  symlinked record files are skipped: nothing is written, read or deleted
  through them, since a cloned repository could point either outside the
  project.
- Each session appends to `.neuralmind/recaps/<session_id>.jsonl`, one short
  line per prompt or edit. Appending means hooks running in parallel can't
  corrupt a record. The ten most recently active records are kept; older ones
  are deleted when a fresh session starts, except a record active in the last
  24 hours, so a session that's still open keeps its start.
- The recap writes `.neuralmind/`'s self-ignoring `.gitignore` before its
  first record, so `git add -A` doesn't stage the records.
- Prompts pass through NeuralMind's credential patterns (the same redaction
  `neuralmind last` uses) **before** they're written, and before they're cut
  to 200 characters, so a credential can't survive in the kept slice. The
  patterns catch common credential formats, not every secret, so a secret in
  an unusual format can still be written.
- The recap goes into the agent's context, so it's sent to your model provider
  along with the rest of the session, as the original prompts were.

## Settings

| Variable | Default | Effect |
|---|---|---|
| `NEURALMIND_SESSION_RECAP` | on | `0` stops recording and stops the recap |
| `NEURALMIND_SESSION_RECAP_MAX_AGE_DAYS` | `14` | A recap whose session was last active longer ago than this isn't shown |
| `NEURALMIND_NO_LEARN` | off | `1` stops recording (nothing is written) but still shows an existing recap |
| `NEURALMIND_BYPASS` | off | `1` switches off every hook action, this one included |
| `NEURALMIND_PROJECT` | unset | Hermes plugin: the project to serve, ahead of the one given at install |
| `NEURALMIND_HERMES_TIMEOUT` | `8` | Hermes plugin: seconds each call to NeuralMind may wait (a session's first turn makes two); a call that times out is left out and the turn goes ahead. Keep twice this below Hermes's `plugins.hook_callback_timeout` (default 30), or Hermes drops the whole block |

Turning the recap off, or setting `NEURALMIND_NO_LEARN=1`, doesn't delete
records already written, and a recap past the age limit is hidden, not deleted.
`neuralmind recap --clear` removes them; while the recap is off,
`neuralmind recap` says how many are still stored.

## Why it's built this way

NeuralMind already had session summaries (`session_summaries.py`), written by
the `Stop` and `SessionEnd` hooks. They're built from `.neuralmind/events.jsonl`,
which is only written while `neuralmind watch` or `neuralmind serve` is
running. With hooks alone, nothing new reaches that log, so the summaries don't
reflect the session, or aren't written at all. The session recap reads only fields Claude Code's
hook payloads carry, so it works with the hooks alone.

## Not measured

This release doesn't claim a number. We haven't measured whether the recap
shortens the start of a session, or how often an agent acts on it when it
shouldn't. The block's size is bounded by count, not by a character budget: at
most four prompts of 200 characters and twelve file paths, plus a header. The
example above is 525 characters; four full-length prompts and twelve
30-character paths come to about 1,500.

## Upgrading

`pip install -U neuralmind`. Nothing to reinstall, and nothing to rebuild in a
project built with v3.9.0 or later (the recap looks for the
`.neuralmind/build_status.json` a build leaves). The first recap appears in the
session after the first one you work in on v4.8.0.

Hermes-Agent: run `neuralmind install-hermes-plugin [path]` once, and again
after later upgrades, since the installed plugin is a copy.

## Related

- Use case: [Pick up where you left off](../use-cases/pick-up-where-you-left-off.md)
- Use case: [Hermes-Agent with code memory in every turn](../use-cases/hermes-agent.md)
- Integration guide: [Hermes-Agent](../wiki/Integration-Guide.md#hermes-agent)
- CLI reference: [`recap`](../wiki/CLI-Reference.md#recap-v480),
  [`install-hermes-plugin`](../wiki/CLI-Reference.md#install-hermes-plugin-v480),
  [Environment Variables](../wiki/CLI-Reference.md#environment-variables)
