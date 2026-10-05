# NeuralMind v4.7.0 — a new session starts where the last one left off, and Hermes gets context without asking

**Type:** Minor release | **Themes:** session continuity (the session recap) · Hermes-Agent gets every turn's context from a plugin

A new Claude Code session used to start cold. NeuralMind gave it the code it
had learned (`SYNAPSE_MEMORY.md`, per-prompt recall), but not the work: what
you were doing yesterday, which files you had open, what you asked last. You
re-explained it, or asked the agent to go and find out.

v4.7.0 records each session's prompts and edited files as you work. The next
fresh or cleared session starts with a short recap of the most recent one:

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
the agent didn't think to call it, nothing happened. v4.7.0 adds a Hermes
plugin that puts NeuralMind's context into every turn before the model runs,
the way the hooks already do in Claude Code.

```bash
neuralmind build /path/to/project
neuralmind install-hermes-plugin /path/to/project
```

The command writes the plugin to `~/.hermes/plugins/neuralmind/` (or under
`$HERMES_HOME`) and runs `hermes plugins enable neuralmind`. Start a new Hermes
session, or restart the gateway, to load it.

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
  agent, so it's neither recorded nor answered with recall.
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
4. else the directory Hermes runs in.

The first of these that has been built wins; if none has, the plugin does
nothing. A gateway session (Telegram, Discord …) has no project directory, so
pin one at install. Every message in a pinned gateway session is then recorded
for the recap, redacted like any other prompt; `NEURALMIND_SESSION_RECAP=0`
turns that off.

Limits:

- **One subprocess per turn**, plus one per recorded edit. If NeuralMind
  doesn't answer within `NEURALMIND_HERMES_TIMEOUT` (default 8 seconds), the
  turn goes ahead without its context. Any error does the same.
- **Tested with Hermes v0.21.5**, through Hermes's own plugin loader and hook
  dispatch. It relies on `pre_llm_call` accepting `{"context": ...}`, which
  that version documents.
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
| `NEURALMIND_HERMES_TIMEOUT` | `8` | Hermes plugin: seconds to wait for NeuralMind before a turn goes ahead without it |

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
session after the first one you work in on v4.7.0.

## Related

- Use case: [Pick up where you left off](../use-cases/pick-up-where-you-left-off.md)
- Use case: [Hermes-Agent with code memory in every turn](../use-cases/hermes-agent.md)
- Integration guide: [Hermes-Agent](../wiki/Integration-Guide.md#hermes-agent)
- CLI reference: [`recap`](../wiki/CLI-Reference.md#recap-v470),
  [`install-hermes-plugin`](../wiki/CLI-Reference.md#install-hermes-plugin-v470),
  [Environment Variables](../wiki/CLI-Reference.md#environment-variables)
