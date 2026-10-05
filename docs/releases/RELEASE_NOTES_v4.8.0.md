# NeuralMind v4.8.0 — a new session starts with where the last one left off

**Type:** Minor release | **Theme:** session continuity

A new Claude Code session used to start cold. NeuralMind gave it the code it
had learned (`SYNAPSE_MEMORY.md`, per-prompt recall), but not the work: what
you were doing yesterday, which files you had open, what you asked last. You
re-explained it, or asked the agent to go and find out.

v4.8.0 records each session's prompts and edited files as you work. The next
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
| **Hermes-Agent and other agents with a shell** | Nothing automatic. An agent that can run commands can call `neuralmind recap` to read what the last Claude Code session in the project did. |

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

## Related

- Use case: [Pick up where you left off](../use-cases/pick-up-where-you-left-off.md)
- CLI reference: [`recap`](../wiki/CLI-Reference.md#recap-v480),
  [Environment Variables](../wiki/CLI-Reference.md#environment-variables)

---

# Fixes in v4.8.0: installers that can't destroy your config, and the bug-hunt fixes

This release fixes eight bugs found by testing v4.7.0 end to end. Two of them
could destroy user configuration. A third left credentials in plaintext in
the Bash output cache, under a header that said they had been redacted.

1. **`install-hooks` and `install-mcp` no longer overwrite a config they
   can't parse.** One trailing comma in `~/.claude/settings.json` was enough
   for `install-hooks --global` to replace the file with a bare `hooks` block,
   losing `permissions`, `model` and `env`. `--uninstall` deleted the file.
   `install-mcp` did the same to Cursor, Cline and Claude Desktop configs,
   removing every other MCP server along with the tokens in their `env`.
2. **The Bash output cache redacts what the AWS CLI prints.** It also redacts
   JSON password keys and a few other common shapes it used to miss.
3. **Hooks do nothing in a project you haven't built.** With a global install,
   the prompt hook used to run a full first-time build in whatever directory a
   session opened in. That took minutes on a real repository, far past the
   hook timeout.

The other five: one non-UTF-8 doc no longer fails the build, rebuilds no longer
duplicate doc edges, `watch --reindex` stops serving deleted symbols, and
`neuralmind export .` works without `--output`.

---

## What changed

### Installers refuse a config they can't round-trip

- **`install-hooks` (project or `--global`) and `install-hooks --uninstall`**
  now refuse when `settings.json` is not valid JSON, has a top level that isn't
  an object, or has a `hooks` value that isn't an object. The error names the
  file, says why, and leaves the file untouched. Exit code is 1:

  ```text
  Error: Refusing to modify ~/.claude/settings.json: it is not valid JSON
  (Expecting property name enclosed in double quotes: line 5 column 1 (char 94)).
  Fix the file (often a trailing comma), then re-run.
  ```

  An empty file still counts as no settings.
- **`install-mcp`** applies the same rule to every client: Claude Code, Cursor,
  Cline, Claude Desktop and VS Code. The VS Code path already worked this way.
  A config with comments or a trailing comma is reported as `skipped-jsonc`,
  and one whose top level isn't an object as `skipped-not-object`. Either way
  the file is not modified, and the command prints the entry to add by hand:

  ```text
  ✗ claude-desktop: skipped-jsonc → …/claude_desktop_config.json is not strict JSON
  (comments or a trailing comma?); left untouched. Add this entry by hand:
  { "mcpServers": { "neuralmind": { "command": "neuralmind-mcp", "args": [] } } }
  ```

  A skipped client no longer prints ✓ or "Restart the client".

### Secret redaction

These apply wherever redaction runs: the automatic Bash output cache behind
`neuralmind last`, `scan-for-secrets`, and `build --redact-secrets`.

- **AWS CLI JSON.** `aws sts get-session-token` and
  `aws configure export-credentials` print `"SecretAccessKey": "…"` and
  `"SessionToken": "…"`. Only the access-key ID used to be redacted. The
  secret key pattern now accepts quoted keys and the `SecretAccessKey`
  spelling, and a new `aws-session-token` pattern covers `SessionToken` /
  `AWS_SESSION_TOKEN`.
- **Quoted keys in the generic rule.** `{"password": "…"}` and
  `{'api_key': '…'}` are detected. The placeholder and entropy guards are
  unchanged, so `{"password": "changeme"}` and `{"api_key": "${API_KEY}"}`
  still aren't.
- **No leaked tail on bare values.** `DB_PASSWORD=Ab9xQ2mZpL;TAILSECRET99`, as
  `env` prints it, used to keep `;TAILSECRET99` after the marker. A bare value
  now continues through `,` or `;` unless whitespace or a new `key=` follows.
  `password=…,next=x` and `Server=db;Password=…;Database=app` still stop at
  the next key.
- **New high-confidence shapes:** GitLab personal access tokens (`glpat-`),
  Hugging Face tokens (`hf_`), and passwords in `http(s)://user:password@host`
  URLs, the form git remotes carry tokens in.

### Hooks act only in a built project

Every hook action now returns at once, writing nothing, unless the session's
directory already has `.neuralmind/`. That directory exists once
`neuralmind build` has run. Before, a globally installed hook would:

- build a full index from the prompt hook (graph, IR and vectors) in any
  directory with source files;
- create `.neuralmind/` from the session-start, edit, stale-guard, Bash-cache
  and pre-compact actions.

Read dedup already followed this rule. Prompt-time recall also no longer builds
an index in a project that has `.neuralmind/` but no index yet (for example,
one with only decision memory). It loads the existing index or injects nothing.

### Indexing and retrieval

- **A non-UTF-8 Markdown, SQL, OpenAPI or proto file no longer fails the
  build.** It used to abort the whole build and wrongly tell you to install
  tree-sitter. These files are now decoded like code files: undecodable bytes
  become U+FFFD and the file is still indexed. A UTF-8 BOM no longer hides the
  first heading.
- **Incremental rebuilds no longer duplicate doc and schema edges.** Each
  no-change `neuralmind build` used to append another copy of every edge from
  Markdown and schema files (links 18 → 20 → 22 on a four-file project), and a
  renamed heading kept its old node. Doc and schema files are rebuilt from
  scratch on each build, so repeated builds produce the same graph. Rebuild
  once (`neuralmind build`) to drop duplicates already in your graph.
- **`watch --reindex` no longer serves deleted symbols.** An incremental
  `update_files` removed deleted symbols from the vector store but left the
  keyword (BM25) index and its generation stamp alone. A removed function kept
  coming back at the top of results, in every process, and each load printed a
  false "Index out of step… Run: neuralmind build". It now rewrites the keyword
  index and records the updated graph, as a full build does.
- **`neuralmind export .` works without `--output`.** The default invocation,
  and `--format pdf` without `--output`, crashed with `TypeError`. They now
  write `neuralmind_export.csv` / `.pdf` in the current directory, as
  documented.

## What the agent actually sees post-install

| Agent | Before | After |
|-------|--------|-------|
| **Claude Code** (MCP + hooks) | With global hooks, the first prompt in an unbuilt repo could block on a full index build until the hook timed out, and `.neuralmind/` appeared in every directory a session ran in. `neuralmind last` could replay AWS session credentials | In an unbuilt repo the hooks do nothing and add no context. In a built one, nothing changes except that recall never triggers a build. AWS CLI credentials are redacted in the cache |
| **Cursor / Cline / Claude Desktop** (MCP) | `install-mcp` on a config with a trailing comma removed every other server | The config is left untouched, and the command prints the entry to paste |
| **VS Code** (MCP) | JSONC was already left untouched. A config whose top level wasn't an object was overwritten | Both are left untouched |
| **Generic MCP client** | Unchanged | Unchanged |

## Environment variables

None added or changed.

## Upgrade notes

- **If you rely on hooks in a project you never built,** run `neuralmind build`
  there once. Hooks now treat `.neuralmind/` as the opt-in.
- **To clear doc-edge duplicates** left by earlier incremental builds, run
  `neuralmind build` once after upgrading.
- **If `install-hooks` or `install-mcp` now refuses a file,** it has a syntax
  error (usually a trailing comma). Fix the file and re-run, or paste the
  printed entry by hand.

## Related

- [CLI reference: install-hooks](../wiki/CLI-Reference.md#install-hooks) ·
  [install-mcp](../wiki/CLI-Reference.md#install-mcp-v0190) ·
  [scan-for-secrets](../wiki/CLI-Reference.md#scan-for-secrets)
- [Security Guide: Secret Management](../SECURITY-GUIDE.md#secret-management)
- [v4.7.0 release notes](RELEASE_NOTES_v4.7.0.md)
