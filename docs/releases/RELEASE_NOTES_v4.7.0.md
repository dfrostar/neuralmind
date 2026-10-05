# NeuralMind v4.7.0 — a new session starts with where the last one left off

**Type:** Minor release | **Theme:** session continuity

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
  root (a file outside the project shows as `~/…` or its full path). Only
  Edit and Write are recorded, so a file changed through a shell command isn't
  listed.
- **"Not instructions."** The block says so, so the agent doesn't pick an old
  task back up on its own. Ask "where were we?" or "carry on" and it has what
  it needs to answer.
- **The most recently active other session.** If two sessions run in the same
  project, whichever was active most recently counts as "where we left off".

## Per-agent expectations

| Agent | What changes |
|---|---|
| **Claude Code** (with `neuralmind install-hooks`) | A fresh or cleared session starts with the recap above. Resumed and compacted sessions don't get it. |
| **Cursor / Cline / generic MCP clients** | Nothing. These hosts don't run Claude Code hooks, so nothing is recorded and nothing is injected. |
| **Hermes-Agent and other agents with a shell** | Nothing automatic. An agent that can run commands can call `neuralmind recap` to read what the last Claude Code session in the project did. |

## Where it's stored, and what's redacted

- Recording happens only in a project where `neuralmind build` has run (it
  leaves `.neuralmind/build_status.json`, which no hook creates). Hooks
  installed globally fire in every repository, but they record no prompts in
  the ones NeuralMind hasn't built.
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

`pip install -U neuralmind`. Nothing to rebuild or reinstall. The first recap
appears in the session after the first one you work in on v4.7.0.

## Related

- Use case: [Pick up where you left off](../use-cases/pick-up-where-you-left-off.md)
- CLI reference: [`recap`](../wiki/CLI-Reference.md#recap-v470),
  [Environment Variables](../wiki/CLI-Reference.md#environment-variables)
