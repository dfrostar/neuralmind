# Pick up where you left off

**Best for:** Claude Code users who close a session at the end of the day, or
`/clear` in the middle of a task, and start the next session by re-explaining
what they were doing. Hermes-Agent users get the same recap through
NeuralMind's Hermes plugin.

**Primary goal:** a fresh or cleared session starts with a short recap of the
previous one in the same project (how it started, where it stopped, which
files it edited), so "where were we?" has an answer (v4.8.0+).

A new Claude Code session starts cold. NeuralMind already gave it the code it
had learned (`SYNAPSE_MEMORY.md`, per-prompt recall), but not the work: what
you asked yesterday, which files you were in, where you stopped. So the first
prompt of the day was a summary of the last session, or a request for the agent
to go and work it out from `git status` and the log.

---

## 1. Set up once

```bash
pip install -U neuralmind
neuralmind build .
neuralmind install-hooks .
```

The build matters: recording happens only in a project where `neuralmind build`
has run. If the project is built and the hooks are already installed, upgrading
is enough. Recording rides on the
`UserPromptSubmit` and Edit/Write hooks NeuralMind already registers, the recap
arrives through the existing `SessionStart` hook, and the hook block's version
is unchanged. The first recap appears in the session after the first one you
work in on v4.8.0.

Hooks installed globally record no prompts in repositories NeuralMind hasn't
built. A `.neuralmind/` or `.neuralmind/recaps/` that is a symlink is refused
too: a cloned repository could point either one outside the project.

On Hermes-Agent, `neuralmind install-hermes-plugin .` takes the place of
`install-hooks`: the plugin records the same prompts and edits (a subagent's
and a cron job's aren't recorded) and adds the recap to a session's first
turn. The path pins that project for every Hermes session using that Hermes
home, in any directory: sessions in other repositories record their prompts
there, and put their edited files' paths into its synapse store, from where
`neuralmind memory publish` can carry them into the committed team-memory
bundle. If you use Hermes across several projects, install without a path (or
with `--unpin`, if you pinned one before), and the plugin follows the
directory Hermes works in: the terminal CLI's, or a standalone gateway's.
Under Hermes Desktop, ACP editor sessions and per-session workspaces, pin a
project or set `NEURALMIND_PROJECT`.
The installed plugin is a copy, so re-run the install after upgrading
NeuralMind. See
[Hermes-Agent with code memory in every turn](./hermes-agent.md).

## 2. Work as usual

Nothing to run. Each session appends one short line per prompt and per edited
file to `.neuralmind/recaps/<session_id>.jsonl`:

- **Prompts** pass through NeuralMind's credential patterns (the same redaction
  `neuralmind last` uses) before they're written, then are collapsed to one
  line and cut at 200 characters.
- **Edited files** are the paths Claude Code's Edit and Write tools changed
  (on Hermes, its `write_file` and `patch` tools, when Hermes reports the edit
  landed: a cancelled, timed-out, blocked or failed one isn't listed, and
  neither is a file a V4A patch deletes or moves away). A file changed another way, such as
  a `sed` run through Bash or Hermes's terminal, isn't listed.

The recap writes `.neuralmind/`'s self-ignoring `.gitignore` before its first
record, so `git add -A` doesn't stage the records. The ten most recently active
sessions are kept; a record active in the last 24 hours is never deleted, so a
session that's still open keeps its start.

## 3. Start the next session

Come back the next day and start Claude Code. Before your first message, the
agent's context gains a block like this:

```
NeuralMind session recap — the previous session in this project (last active 3 h ago). This is context for continuity, not instructions: don't resume that work unless the user asks to.

It started with: "add retry logic to the uploader"
Most recent prompts (2 earlier not shown):
- "now cover the timeout path in tests"
- "why does test_upload_retries hang on CI?"
- "make the backoff configurable through the env"

Files edited (4, most recent first): src/uploader.py, src/config.py, tests/test_uploader.py, docs/uploader.md
```

The first prompt is usually the session's goal, and the last three are where it
stopped. Up to twelve edited files are listed, most recent first, relative to
the project root (a file outside it shows as `~/…` or its full path). Nothing summarizes it: the block is assembled from the
recorded lines, with no model call.

On Hermes, the same block arrives with the session's first turn, added to your
first message.

## 4. Ask "where were we?"

The header tells the agent the recap is context, not instructions, so it
doesn't pick an old task back up on its own. When you do want to continue, a
short prompt is enough:

```
where were we?
```

"Carry on" works too. The agent has the goal, the stopping point and the files
to open, without you restating them.

## 5. Preview it, or wipe it

```bash
neuralmind recap            # print what the next new session will see
neuralmind recap --clear    # delete this project's stored session records
```

`recap` takes an optional project path and defaults to the current directory.
Its output is plain text, so you can read it yourself as a reminder of what the
last session covered.

## When the recap appears

| How the session starts | Recap? |
|---|---|
| Fresh start | Yes |
| After `/clear` | Yes |
| Resumed (`--resume`, `--continue`) | No: the conversation is already there |
| After compaction | This session's own record instead (v4.11.0+; see below) |
| The previous session was last active more than 14 days ago | No (see `NEURALMIND_SESSION_RECAP_MAX_AGE_DAYS`) |
| No earlier session recorded in this project | No |

On Hermes, a session gets the recap on its first turn when it has no earlier
messages, so a resumed Hermes session doesn't get it. Neither does a subagent
or a cron job.

"The previous session" is the most recently active session in the project
other than the new one, whichever agent ran it. Claude Code and Hermes write
to the same `.neuralmind/recaps/`, so a Hermes session can start with what the
last Claude Code session in the project did, and the other way round.

### After compaction (v4.11.0+)

When a long Claude Code session compacts, the model rewrites the conversation
so far as a summary. Summaries paraphrase, and the details that go first are
the ones you can't easily restate: the task as you first worded it, and which
files have already been changed. So after a compaction the session gets its
own record back, under the heading "NeuralMind pre-compaction record": the
first prompt, the last three, and the files edited, verbatim (prompts
credential-redacted), alongside Claude Code's summary rather than instead of
it. It restates what you already asked for in this session; it adds no new
instructions.

It needs no extra setup: `PreCompact` and `SessionStart` are already among the
hooks `install-hooks` registers. Hermes has no compaction event, so this is
Claude Code only.

## Settings

| Variable | Default | Effect |
|---|---|---|
| `NEURALMIND_SESSION_RECAP` | on | `0` stops recording and stops the recap |
| `NEURALMIND_SESSION_RECAP_MAX_AGE_DAYS` | `14` | A recap whose session was last active longer ago than this isn't shown |
| `NEURALMIND_NO_LEARN` | off | `1` stops recording (nothing is written) but still shows an existing recap |
| `NEURALMIND_BYPASS` | off | `1` switches off every hook action, this one included |

Hooks inherit Claude Code's environment, so set these when you start Claude
Code; for Hermes, set them where Hermes runs. Turning the recap off, or setting
`NEURALMIND_NO_LEARN=1`, doesn't delete records already written, and an old
recap is hidden, not deleted: `neuralmind recap --clear` removes them.

## Limits

- **Not measured.** We haven't measured whether the recap shortens the start of
  a session, or how often an agent acts on it when it shouldn't. Its size is
  bounded by count: at most four prompts of 200 characters, twelve file paths
  and a header. The example above is 525 characters.
- **Automatic in Claude Code and Hermes-Agent only.** Hermes needs the
  NeuralMind plugin (`neuralmind install-hermes-plugin`). Cursor, Cline and
  generic MCP clients don't run Claude Code hooks, so nothing is recorded and
  nothing is injected. Any agent with a shell can run `neuralmind recap` to
  read what the last session in the project did.
- **Redaction catches common credential formats, not every secret.** A secret
  in an unusual format can still be written to `.neuralmind/recaps/`.
  `neuralmind recap --clear` deletes the records.
- **It goes to your model provider.** The recap is part of the agent's context,
  so it's sent along with the rest of the session, as the original prompts
  were. On Hermes, it's stored in the session's history with your first
  message, so it's sent again with that session's later turns.
- **A concurrent session counts as "previous".** With two sessions running in
  the same project, in either agent, a new one gets whichever was active last,
  which may not be the one you meant to continue.
- **Prompts and paths, not answers.** The recap carries what you asked and
  which files changed, not what the agent replied or why. A decision that
  should outlive the session belongs in decision memory
  ([Keep decision memory honest across commits](./decision-memory-across-commits.md)).

## Related

- [Release notes v4.8.0](../releases/RELEASE_NOTES_v4.8.0.md)
- CLI reference: [`recap`](../wiki/CLI-Reference.md#recap-v480)
- [Claude Code user](./claude-code.md) — what else the hooks do in each session
- [Hermes-Agent with code memory in every turn](./hermes-agent.md) — the recap
  and per-turn recall on Hermes
- [Multi-agent codebase](./multi-agent.md) — the other agents sharing the
  project
