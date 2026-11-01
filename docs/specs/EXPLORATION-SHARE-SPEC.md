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
  de-duplicated by session id.

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
- **2026-11-01, the collectors ship as a command; definitions, thresholds and
  figures unchanged.** The collectors moved from `evals/exploration_share/` to
  `neuralmind/measure/` and run as `neuralmind measure sessions`, which anyone
  can point at their own Claude Code and Hermes sessions (last 30 days by
  default; aggregates only on stdout; exit 2 when no session started in the
  window). `evals/exploration_share/` re-exports the same modules, and the
  nightly job's commands are unchanged. On the Mac's and ai-9970's sessions
  started 2026-10-02 to 2026-10-25 (64 Claude Code and 649 Hermes sessions,
  characters ÷ 4), the moved code wrote rows byte-identical to the code before the
  move, and `report`'s Markdown identical. Additions only: the summary JSON gains
  `exploration_share_of_prompt` per group (the second share the pass-4 field report
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
