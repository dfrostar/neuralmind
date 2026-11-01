# NeuralMind v4.24.0 — `neuralmind measure sessions`: what your agent's token bill goes to, measured on your machine

**Type:** Minor release | **Theme:** a read-only meter over the sessions your agents already recorded, so the question "what do my agent's tokens go to?" has an answer for your sessions, not only for ours

NeuralMind quotes a token ratio per question: its assembled context costs
51–242× fewer tokens than the source files themselves on the
[public benchmark](../benchmarks/public.md). Whether a ratio like that shows on
a bill depends on how much of the bill is code being read and searched, and
nothing told you that for your own sessions. This release adds the command:

```bash
neuralmind measure sessions
```

It reads the transcripts Claude Code keeps (`~/.claude/projects`) and the
`state.db` Hermes-Agent keeps (`~/.hermes/state.db`), on this machine,
read-only. For the sessions that started in the last 30 days it reports what
share of the context each API call carried, and of the prompt tokens the
provider billed, was *exploration*: `Read`, `Grep`, `Glob`, `read_file`,
`search_files`, and shell commands that only read. It needs no project, no
index and no build, and it writes nothing unless you pass `--rows`.

**It measures; it does not promise.** The share bounds what a retrieval tool
could affect on a bill. It is not what NeuralMind affects: a block that names
the right file replaces some reads, not all of them, and the block itself costs
tokens on every call, which the report shows as its own column.

## What you see

For one developer's Claude Code sessions (the
[first field report](https://github.com/dfrostar/neuralmind/blob/main/bench/exploration-share/2026-11-01/README.md):
88 interactive sessions, 2026-10-02 to 2026-11-01, pass 5), in the layout the
command prints. Yours will differ:

```text
Exploration share of the token bill
Sessions started 2026-10-02 to 2026-11-01 (last 30 days). Claude Code: read; Hermes: not found.

Sessions: 88

Exploration share (reading and searching code):

Agent / source             Sessions  API calls  Exploration of context  of billed prompt  Median session
-------------------------  --------  ---------  ----------------------  ----------------  --------------
claude-code / interactive        88     12,540                   30.7%             19.7%           21.1%

What else the recorded context holds, and how much of the bill it covers:

Agent / source             Prompt tokens billed  Recorded / billed  NeuralMind block  Edits  Other shell
-------------------------  --------------------  -----------------  ----------------  -----  -----------
claude-code / interactive         3,736,688,230              64.0%              0.0%   4.5%        14.8%

Pre-registered reading (interactive sessions, share of recorded context):

  claude-code/interactive (88 sessions): 30% or more: a material part of the bill

Tokenizer: o200k_base
```

Below that it prints what each column means and a link to the
[spec](../specs/EXPLORATION-SHARE-SPEC.md). Two shares are reported because
they answer different questions. **Of context** is the spec's headline:
exploration tool results over everything the transcripts record the API calls
carrying, with one tokenizer and one model of what stays in the window until a
compaction or the agent's own trimming drops it. **Of billed prompt** divides the
same tokens by what the provider billed. The transcripts don't hold the system
prompt or the tool schemas, so *Recorded / billed* says how much of the bill
they account for. The unrecorded part holds no tool results, so the second share
is the first times that ratio.

The reading is the spec's, fixed before the first share was computed: under 10%
is "arithmetic, not felt on a bill", 10% to 30% is "the claim stands with the
share beside it", 30% or more is "a material part of the bill". It is printed
with the number of sessions it rests on, for interactive sessions only;
automated, subagent and benchmark sessions get rows and are never read against
it.

## Options

```text
neuralmind measure sessions [--since-days N] [--claude-root PATH] [--hermes-db PATH]
                            [--json] [--rows PATH] [--estimate]
```

| Option | What it does |
|---|---|
| `--since-days N` | Sessions that started in the last N days (default 30). |
| `--claude-root PATH`, `--hermes-db PATH` | Where the sessions are, when not at the defaults (`$CLAUDE_CONFIG_DIR/projects` or `~/.claude/projects`; the Hermes home's `state.db`, which follows `$HERMES_HOME` and the active profile). A path that isn't there is an error. |
| `--json` | The aggregate as JSON: the groups, the reading, the window and which sources were read. |
| `--rows PATH` | Per-session rows, one JSON line each (id, source label, model, timestamps, token counts by kind), to a file you name, replacing it. They hold no prompt text or paths. |
| `--estimate` | Count characters ÷ 4 instead of tiktoken's `o200k_base`. Without `--estimate`, tiktoken is used when it is installed and its vocabulary is available (it fetches the vocabulary the first time it runs); otherwise the report counts characters ÷ 4 and says so. |

**Exit codes:** `0` after printing a report; `1` when the `--rows` file can't be
written; `2` when no session started in the window, or an argument is wrong (including a
`--rows` that names a transcript or the database it reads, which it would replace)
(`tests/test_cli_exit_codes.py` runs all three).
A transcript or database that can't be read is reported on stderr and skipped,
and the other source is still measured.

## What the agent and your tools see after upgrading

Nothing, until you run it: no hook, no MCP tool and no prompt changes.

| Agent | Read by `measure sessions` |
|---|---|
| Claude Code | Yes: `~/.claude/projects/*/*.jsonl` (`$CLAUDE_CONFIG_DIR/projects` when set), the `usage` it recorded for each API call. Sidechain (subagent) files are their own row. |
| Hermes-Agent | Yes: `state.db` in the Hermes home, opened read-only. Hermes bills per session, so its row is calibrated to the bill. |
| Cursor, Cline, Continue, Codex, other MCP clients | No. They keep their sessions elsewhere, in other formats, and there is no collector for them yet; nothing is read and nothing is reported. |

Stdout holds aggregates only: no paths, project names, prompts or session ids.
Claude Code's transcripts cover every project on the machine and are pooled; the
report has no per-project breakdown, because that would print project names.

## Under the hood

- **The collectors moved into the package.** `neuralmind/measure/` holds them
  (stdlib only, tiktoken optional), and `evals/exploration_share/` re-exports the
  same modules, so the spec's nightly job (`python -m evals.exploration_share
  hermes …`) and `tests/test_exploration_share.py` run unchanged. The shipped
  package doesn't import from `evals/`; a test checks that.
- **The summary JSON gained `exploration_share_of_prompt`**, the second share
  above, per group. Nothing was renamed or removed.
- **Two fixes to the collectors, for the shipped command.** Transcripts and
  rows files are read as UTF-8 whatever the locale (Windows's default would raise
  on them), and the Hermes database path is passed to SQLite as a percent-encoded
  URI, so a `?`, `#` or `%` in it can't end it early. Neither changes a figure on
  the machines the field report ran on.
- **Definitions are unchanged.** The collectors are the code of the spec's pass 5,
  and the spec's pointers to the code now name `neuralmind/measure/`.

## Limits

- Presence after a compaction is modelled from the flags the agents keep, and
  the numerator's tokenizer is not the provider's. The first field report's
  Claude Code sessions are accounted for to 64.0% of their bill, and the
  shares are stated with that beside them.
- The first field report is one developer's two machines. Its Claude Code figure
  (30.7% of the context, 19.7% of the billed prompt) and its Hermes figure
  (10.4%) both sit within a few points of a threshold, so they are not a
  finding about the thresholds, and not a result for your sessions.
- A session still running when you run the command is included as far as it has
  got.

Walkthrough: [Measure what your agent's token bill goes to](../use-cases/measure-what-your-agent-spends.md).
Command reference: [`measure sessions`](../wiki/CLI-Reference.md#measure-sessions-v4240).
