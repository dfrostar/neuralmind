# Exploration share of the token bill — measurement spec

**Status:** pre-registered 2026-11-01, before any share was computed (see "Prior
exposure" below for exactly what had been seen).
**Owner:** Darren Frost. **Analyst:** Claude (Fable 5.1), session `ba588627`.
**Code:** `neuralmind/measure/`, shipped as `neuralmind measure sessions`;
`evals/exploration_share/` re-exports it and runs the nightly job. **Nightly job:** Hermes cron
`neuralmind-exploration-share` on ai-9970 (no-agent script).

## The question

What share of what an agent's sessions cost in prompt tokens is *exploration*:
reading and searching code before changing it? NeuralMind's measured effect is
on exactly that content (its assembled context costs 51–242× fewer tokens than
the files themselves on the public benchmark, `docs/benchmarks/public.md`). The
share decides whether that effect is something a bill can feel, or arithmetic.

## Definitions, fixed before the first number

- **Session.** A Hermes session (`~/.hermes/state.db`, `sessions` table) or a
  Claude Code transcript (`~/.claude/projects/<project>/<session>.jsonl`).
- **API call.** Hermes: one `assistant` row in `messages`. Claude Code: one
  distinct `requestId` among `assistant` lines (a response is written as several
  lines that repeat the same `usage`; it is counted once).
- **Prompt tokens, billing side.** What the provider reported: Hermes
  `input_tokens + cache_read_tokens + cache_write_tokens` per session; Claude
  Code `input_tokens + cache_read_input_tokens + cache_creation_input_tokens`
  per API call. Reported as the calibration denominator, not the headline.
- **Content tokens.** tiktoken `o200k_base` over message text, the same
  tokenizer as the public benchmark. Where tiktoken is unavailable the row is
  computed as characters ÷ 4 and says so (`tokenizer` field). Hermes's
  `token_count` column is unpopulated and is not used.
- **Tool categories.**
  - *exploration*: Hermes `read_file`, `search_files`, and `terminal` with a
    read-only command; Claude Code `Read`, `Grep`, `Glob`, `LS`,
    `NotebookRead`, and `Bash` with a read-only command. A command is read-only
    when every stage of its pipeline (`|`, `&&`, `;`, `||`), after any `cd …`,
    variable assignments, `sudo`, `time` or `nohup` prefix, starts with a word
    on the read-only list in `neuralmind/measure/classify.py` (`cat`,
    `head`, `grep`, `rg`, `find`, `ls`, `wc`, `diff`, `sed` without `-i`, `git`
    with `log`/`show`/`diff`/`status`/`blame`/`grep`/`ls-files`/`rev-parse`,
    …), and it writes to no file (`>`/`>>` other than to `/dev/null` or
    `2>&1` disqualify it).
  - *edit*: Hermes `patch`, `write_file`; Claude Code `Edit`, `Write`,
    `MultiEdit`, `NotebookEdit`.
  - *web*: `web_search`, `web_extract`, `WebFetch`, `WebSearch` (not code
    exploration; excluded from the share).
  - *shell*: any other `terminal`/`Bash` command (tests, installs, builds).
  - *other*: everything else (MCP tools, `Task`/`Agent`, tool search, …).
- **First-time exploration tokens.** Content tokens of exploration tool results,
  plus the arguments of those calls, counted once.
- **Billed exploration tokens.** The sum over API calls of the exploration
  tool-result tokens *present in that call's context*. A message is present for
  every call after it until it is dropped: Hermes rows with `compacted = 1` or
  `active = 0` are dropped at the first `_compressed_summary` row after them
  (or never, if none follows); Claude Code messages are dropped at the next
  `isCompactSummary` line. This is a model of context composition, not a
  record: both agents keep only final-state flags.
- **Context tokens, estimated.** The same sum over all present messages (the
  system prompt, user text, assistant text and tool calls, every tool result).
- **The headline share** = billed exploration tokens ÷ estimated context
  tokens. Both sides use the same tokenizer and the same presence model, so the
  ratio does not depend on either. Beside it: the billing-side denominator and
  the *calibration ratio* (estimated context ÷ billing-side prompt tokens),
  which says how far the model is from what was billed.
- **NeuralMind block.** Hermes: `api_content` minus `content` on a user row
  whose `api_content` begins with its `content` (the plugin appends the block).
  Claude Code: a user text block containing `Code matching this prompt`. Its
  first-time and billed tokens are reported like exploration's: it is what
  NeuralMind itself costs a session.
- **Sources.** *interactive*: Hermes `cli`, `desktop`, `local`, `telegram`;
  Claude Code sessions that are not sidechains. *automated*: Hermes `cron`,
  `oneshot`, `a2a`, `api_server`. *subagent*: Hermes `subagent`; Claude Code
  sidechain files. *benchmark*: Hermes `tool` (the task-outcome harness). The
  headline is **interactive only**.
- **Window.** Retrospective: sessions started 2026-10-02T00:00Z to
  2026-11-01T23:59Z, on ai-9970 (Hermes) and on the Mac (Claude Code). Then
  nightly on ai-9970: every session ended since the previous run, appended,
  de-duplicated by session id; a session that has written since its row was
  recorded is collected again and its row replaced.

## Pre-registered reading of the result

On interactive sessions, pooled over the window and as the per-session median:

| Billed exploration share | Reading |
|---|---|
| under 10% | The token saving is arithmetic: real per question, not felt on a bill. Keep the ratio claims only with the share stated beside them. |
| 10% to 30% | The claim stands, with the measured share quoted next to it. |
| 30% or more | Exploration is a material part of the bill; the per-question ratio has a real denominator. |

Reported without thresholds: the block's billed share (NeuralMind's own cost),
the edit and shell shares, and every figure by source. Automated, subagent and
benchmark sessions are reported, never pooled into the headline.

## Prior exposure

Before these thresholds were fixed, the analyst had seen one week of raw
ai-9970 volumes (sessions started 2026-10-25 to 2026-11-01): `read_file` and
`search_files` results of about 24M characters ÷ 4 against about 790M prompt
tokens processed, a week dominated by benchmark sessions (261 of 559), i.e. a
first-time share near 3% for benchmark traffic. No billed share had been
computed, and nothing at all for interactive sessions or for Claude Code.

## Limits

- Presence after compaction is modelled from final-state flags.
- The numerator's tokenizer is not the provider's; the headline is therefore
  tokenizer-consistent by construction (both sides `o200k_base`) and the
  calibration ratio is published beside it.
- Claude Code transcripts on the Mac cover every project on that machine. Only
  per-source aggregates leave the machine: no paths, no project names, no
  prompts.
- The share bounds what retrieval can save; it is not what NeuralMind saves. A
  block that names the file replaces some reads, not all, and the block itself
  costs tokens on every call.

## Change log

- **2026-11-01, pass 2: the presence model is calibrated to billing.** The
  first pass (the model above, as first written) produced per-session
  calibration ratios from 0.23 to 7.4 on the Mac's Claude Code sessions: the
  transcript holds no system prompt or tool schemas (so sessions with many
  short calls were under-estimated), and it keeps every tool result at full
  size although Claude Code trims old results between compactions (so long
  sessions with no compaction line were over-estimated several-fold). Pass 1's
  pooled figures were 72.3% (Claude Code, 87 interactive sessions) and 11.3%
  (Hermes, 66 interactive sessions, chars/4); they are kept in the data folder
  as `*.pass1.*` and are not the result. Pass 2 adds two steps, applied before
  the shares were re-read: (a) the context size the provider billed for a call
  caps what the model may hold at that call, dropping the oldest droppable
  messages first (Claude Code: per call, from `usage`; Hermes: the session's
  mean prompt size per call, since it bills per session); (b) whatever the
  billing exceeds the transcript by is counted as `system` overhead (Claude
  Code: fixed from the first call; Hermes: spread over the calls). Claude Code
  `attachment` lines (CLAUDE.md, memory and hook output rendered as
  system-reminders) are now counted, which is where NeuralMind's block appears.
  The thresholds are unchanged.
- **2026-11-01, pass 3: three defects found in code review (Codex, PR #765),
  fixed after pass 2's figures had been read.** Pass 2 read 22.5% pooled /
  14.6% median for Claude Code interactive and 7.6% / 3.8% for Hermes
  interactive (48.3% benchmark); those files are kept as `*.pass2.*`. The
  fixes: (a) pipeline stages are now split quote-aware (shlex with operator
  characters), so `rg 'foo|bar' src` or `git log --format='%h;%s'` is
  exploration rather than failing to parse and being counted as shell, and an
  unquoted newline separates stages like `;`; (b) a compaction summary is
  droppable, so the next compaction replaces it instead of charging every
  earlier summary to every later call; (c) a session still active at the
  window's end (ended after it, or not ended and still writing) is deferred
  to a later run rather than recorded half-way and then skipped for good, and
  an explicit `--until` is capped at now minus `--lag-hours`. (a) can only
  raise the exploration share, (b) can only lower the denominator; neither
  direction was chosen with the thresholds in view, and the thresholds are
  unchanged.
- **2026-11-01, pass 4: four more defects from code review (Copilot, PR
  #765), fixed after pass 3's figures had been read** (27.4% / 19.7% Claude
  Code interactive; 9.7% / 4.9% Hermes interactive; 51.7% benchmark; files kept
  as `*.pass3.*`). (a) The arguments of a tool call (a path, a pattern, a
  command) are counted with the call's category, as "First-time exploration
  tokens" above says, instead of as assistant text. (b) Whether a message is
  removed by a compaction and whether the billing cap may trim it are separate
  flags: Hermes rows that are active and uncompacted were immune to the cap, so
  a tool result larger than the session's mean prompt was charged in full. (c)
  `git branch`, `tag`, `remote` and `worktree` count as exploration only in
  their listing forms (`git branch feature`, `git tag v1`, `git worktree add`
  are shell). (d) A timestamp given to the CLI with an explicit offset keeps
  it; one without is UTC. Also from that review: the field report states
  exploration's share of the recorded context and its share of the billed
  prompt as two figures, not as a range (the unrecorded part of the prompt
  holds no tool results, so the billed-prompt share is the recorded share
  times the calibration ratio, not a bound), and track 1's task list no
  longer counts three held-out tasks twice. Thresholds unchanged.
- **2026-11-01, review 3: two more findings from code review (Codex, PR
  #765), fixed after pass 4's figures had been read** (Claude Code interactive
  30.6% of recorded context, 19.6% of billed prompt; Hermes interactive
  10.4%). Neither fix has been re-run on either machine: the committed
  summaries are still pass 4's, and the figures will move. (a) `git -C <path>
  diff` and `git -c <name>=<value> log`: git's global options that take an
  operand were read as the subcommand, so those reading commands counted as
  shell. The subcommand is now found past them. This can only raise the
  exploration share; in the Mac's transcripts it flips 22 of 13,585 Bash calls
  in the window, all `git -C`, and what their output adds has not been
  measured. (b) A session was recorded once, by id, even while it was still
  running (with `--lag-hours 0` the window ends at the run, so a running
  session's last message is inside it), and every later run skipped it: any
  session that spanned a collection stayed half-counted. A row now holds the
  session's latest activity (`last_activity`), and a later run collects a
  session again when it has written something newer, replacing its row; rows
  from before the field fall back to `ended_at`, and one with neither is
  collected once more. This can move a share either way. Whether any row in
  the pass 4 summaries was recorded early is not known from the aggregates.
  Thresholds unchanged.
- **2026-11-01, review 4: three more classifier findings (Copilot, PR #766's
  view of this code), fixed before any re-run.** (a) `env` was on the read-only
  list, so `env PYTHONPATH=. python -m pytest` counted as exploration; `env` is
  now a prefix like `sudo` (the command it runs is classified; on its own it
  prints the environment and still reads). (b) An unquoted comment swallowed the
  newline after it, so `cat a.py # note` followed by `pytest` on the next line
  was one stage; comments are now dropped before tokenizing and their newline
  kept. (c) A quoted argument made only of operator characters (`grep -F '>'
  a.py`, `rg ";" src`) was read as the operator, so the command counted as
  shell, or a quoted `|` split a stage; operator characters inside quotes are
  now masked before tokenizing. (a) and (b) can only lower the exploration
  share, (c) only raise it. In the Mac's transcripts, of about 13,640 Bash
  calls in the window, these three flip 2 to exploration and 7 to shell against
  review 3's classifier; with review 3's `git -C` fix, 24 flip to exploration
  and 7 to shell against pass 4's. What those calls' output adds in tokens has
  not been measured, and the summaries are still pass 4's. Thresholds unchanged.
- **2026-11-01, pass 5: the review-3 and review-4 fixes, re-run from scratch on
  both machines.** Pass 4's summaries are kept as `*.pass4.*`. Claude Code
  interactive (88 sessions): 30.72% of recorded context, 19.67% of billed
  prompt, median session 21.1%; Hermes interactive (67 sessions): 10.42%,
  median 5.4%. What the fixes carry in tokens, measured: the pass-4 and the
  pass-5 classifier run on the same 87 Mac sessions give 30.66% / 19.62% and
  30.69% / 19.64%, so all the classifier and collector changes since pass 4
  together move the pooled shares by 0.03 and 0.02 points. The movement
  between passes comes from which sessions a run can read (a session still
  writing when its file is read is deferred; others kept growing between
  runs), about half a point on the headline. The Mac's headline is 0.7 points
  over the "30% or more" threshold and Hermes interactive 0.4 points over the
  10% line; the report says both are within noise of the line. Thresholds
  unchanged.
- **2026-11-01, review 5: four more findings from code review (Copilot on
  PR #767, which carries a copy of this code), fixed before any re-run.** (a)
  `git branch -d -v feature` and `git tag -l -d v1` counted as exploration:
  a listing flag rescued a mutating option. Mutating options (`-d -D -m -M -c
  -C -f -u -t` and their long forms, in short-option clusters too) are
  rejected first for `branch` and `tag`. (b) `git reflog expire` and `delete`
  counted as exploration; only bare `reflog`, `show` and `exists` read.
  (c) A backslash-escaped operator outside quotes (`rg \> src`) was read as
  an operator, and a backslash-newline was read as a word; the escaped
  character is masked like a quoted one and a line continuation is dropped.
  The same class of hole, found while fixing these: `find` with `-delete`,
  `-exec`, `-execdir`, `-ok`, `-fprint*`, `sort -o` and `yq -i` counted as
  exploration; they are shell now. (d) Claude Code subagent transcripts live at
  `<project>/<session>/subagents/agent-<id>.jsonl`, which the file discovery
  (`*/*.jsonl`) never reached: 33 files against 94 top-level ones on the Mac,
  and the Claude Code "subagent" row was empty. They are collected as
  `subagent` sessions with an id of their own (`<session>/<agent file>`; the
  file carries its parent's sessionId, so one id would collapse siblings into
  one row). They add a row; the interactive headline is unchanged by (d).
  (a), (b) and (c) can only lower the exploration share, apart from the
  quoted-operator case in (c), which raises it. **Freeze.** The classifier and
  collectors are frozen for PR #765 after this entry: the last four rounds of
  review findings moved the Mac's pooled share by 0.03 points between them, so
  further classification edge cases go to a follow-up change, which re-runs
  both machines and adds a change-log entry of its own, not to this PR.
  Thresholds unchanged.
- **2026-11-01, pass 6: one transcript file is one session.** The spec's
  definition of a Claude Code session is a transcript file, but the CLI rewrite
  in review 3 keyed rows by the `sessionId` inside the file, so when a resumed
  conversation wrote several files under one id only one of them was recorded:
  the last in path order after review 3 (30.17% on one fixed snapshot of the
  Mac) and the first after the fix to that (30.65%). One Mac id has three files
  (701, 346 and 288 transcript lines, same start). Rows are now keyed by the
  file (`<file stem>`, and `<session folder>/<agent file stem>` for subagent
  transcripts), which is the spec's definition and removes the choice. It
  counts the history that resumed files share once per file; how else to count
  it moves the Mac headline within the same noise band as everything else
  (same rows, pass-4 classifier: keep first 30.62%, keep longest 30.14%, each
  file 29.77%, drop the id 30.83%; figures by the site session). The rule was
  chosen by following the registered definition, not by its effect on the
  reading; it puts the Mac headline just under the 30% line and the report
  says the headline is 30% within about a point. Thresholds unchanged.
- **2026-11-01, the collectors ship as a command; definitions, thresholds and
  figures unchanged.** The collectors moved from `evals/exploration_share/` to
  `neuralmind/measure/` and run as `neuralmind measure sessions`, which anyone
  can point at their own Claude Code and Hermes sessions (last 30 days by
  default; aggregates only on stdout; exit 2 when no session started in the
  window). `evals/exploration_share/` re-exports the same modules, and the
  nightly job's commands are unchanged. On the Mac's own Claude Code and Hermes
  sessions started 2026-10-02 to 2026-10-25 (90 Claude Code, nested subagent transcripts included, and 649 Hermes
  sessions, characters ÷ 4), the moved code (pass 6, `ed6cbe60`) wrote rows byte-identical to
  the code before the move. Additions only: the summary JSON gains
  `exploration_share_of_prompt` per group (the second share the field report
  states, billed exploration tokens over the provider's prompt tokens), and the
  collectors read transcripts as UTF-8 whatever the locale and pass the Hermes
  database path to SQLite as a percent-encoded URI. The command prints the
  pre-registered reading beside each interactive group's session count; the
  thresholds are unchanged.

## Outputs

- Per-session rows, local only: ai-9970
  `~/nm-bench/tracks/t2-exploration-share/sessions.jsonl`; Mac
  `~/neuralmind-tracking/exploration-share/sessions.jsonl`.
- Aggregates, committed as a field report: `bench/exploration-share/<date>/`
  (`summary.json`, `README.md`), one per window; a `site/claims.json`
  `field-report` entry when a figure is quoted on the site.
- The nightly job's stdout is one line (date, sessions added, interactive
  share to date); it is delivered `local` and kept in Hermes's cron log.
