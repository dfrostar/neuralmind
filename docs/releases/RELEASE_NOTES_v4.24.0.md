# NeuralMind v4.24.0 — lexical anchoring for the per-prompt block, behind a flag, and `neuralmind measure sessions`

**Type:** Minor release | **Theme:** two additions. The exact strings a prompt quotes can name the file to fix when the embedding search can't, off by default until a confirmation replay, with the pre-registration, the replay and its misses published. And a read-only meter over the sessions your agents already recorded, so "what do my agent's tokens go to?" has an answer for your sessions

On the 12 held-out [hermes-agent](https://github.com/NousResearch/hermes-agent)
bug-fix tasks of the task-outcome work, the block the `UserPromptSubmit` hook
adds to each prompt named a file the fix touched on 4 of 12, under every
ranking tried (v4.23.0's test ordering and tested-code credit included). The
file wasn't among the embedding hits at all. Yet on 6 of those 12 the prompt
quoted an exact string that lives in the file to fix: an error message, a
dict key, a constant, a function name.

This release adds that evidence to the block's ranking, behind
`NEURALMIND_RECALL_LEXICAL=1`. **With the flag unset, nothing changes:** the
block is byte-identical to v4.23.3's and no lookup runs.

## What the flag does

With it set, `recall()`:

- **extracts the prompt's exact identifiers:** each backticked span and each
  quoted span of 8 characters or more, whole and by identifier-like word;
  `--flags`; snake_case, CamelCase and UPPER_CASE names. Common words, URLs
  and spans made only of common words are dropped; at most 24 identifiers,
  in order of appearance;
- **looks each one up in the working tree** with one `git grep -l -F
  --untracked` per identifier, over the files the index holds code nodes for
  (tracked or untracked, not ignored). Test files give no lexical evidence
  unless the prompt names a test, the rule the ranking already applies to
  them; an identifier in more than 60 files is dropped as uninformative;
- **scores each file found** by the sum over its identifiers of
  1 / ln(1 + files holding the identifier): an identifier found in one file
  is worth 1.44, in two 0.91, in five 0.56; and adds half of that to the
  file's summed embedding score, through the file's own node, so a file no
  hit is in can still be listed, without a symbol;
- **leaves everything after that unchanged:** tests after the code, the
  reserved test slot, the tested-code credit, the excerpt's 2:1 margin, the
  linked section, the docs line and the hook's similarity gate.

The build's BM25 index isn't used: it holds each code node's symbol name and
path and the docstrings, not the source text, and the identifiers that find
a file are mostly string literals and constants.

## What it measured, offline

Pre-registered first, in the task-outcome spec's change log (2026-11-01):
the gate, the weight's tuning grid, and the sets. Then replayed through the
real `neuralmind _hook prompt-submit` on the same cached indexes as the
v4.23.0 study, so the flag is the only difference between the rows
(`bench/task_outcome/lexical-anchoring/`):

| | flag off | flag on | gate |
|---|---|---|---|
| Held out, 12 hermes-agent tasks: a file the fix changed is listed / listed first | 4 / 3 | **7 / 5** | ≥ 6 / ≥ 5 |
| Held out: test files among the files listed | 14 of 84 | 14 of 84 | not above |
| Pilot, 20 tasks on this repository: listed / first | 17 / 11 | **18 / 13** | ≥ 17 / ≥ 11 |
| Median hook time, hermes-agent / this repository | 9.32 s / 0.50 s | 9.82 s / 0.68 s | |

The gate held. The two new held-out firsts are one quoted string each, found
in exactly one file; one gold file went from absent to second; the three
firsts the hook already had held; five tasks stay unnamed, three of them
with no identifier in the file to fix at all. On the pilot the flag gains one
task listed and first and two firsts, and loses one first to the `cli.py`
the quoted flags live in. The hook times on hermes-agent are cold graph
loads (those indexes predate the graph cache); the flag's own cost is the
grep, about 0.1 s on this repository and 1–2 s on hermes-agent's 20,000
tracked files.

**What it doesn't show.** 12 tasks from one repository, with the first count
exactly on its threshold, and prompts written by an agent from each fix's
tests and diff, which may quote messages more faithfully than a user's
report would. Whether an agent does anything differently with the new block
is not measured. So the default stays off: the next step is confirmation on
12 new held-out tasks from the same seeded walk before any agent run, and
the flip, if it comes, with a persisted per-file token index so a large
repository doesn't pay the grep on every prompt.

## What the agent sees

| Agent | Default | With `NEURALMIND_RECALL_LEXICAL=1` |
|---|---|---|
| Claude Code (`UserPromptSubmit` hook) | Unchanged | The same block, with files the prompt's exact strings are in added to its ranking; a file named on lexical evidence alone has no symbol after it |
| Hermes Agent (plugin `pre_llm_call`) | Unchanged | Same as Claude Code; set the variable in the gateway's environment, where the hooks run |
| Cursor, Cline, generic MCP | Unchanged | Unchanged: the flag is for the prompt hook, not the MCP query path |

## Reference

- `NEURALMIND_RECALL_LEXICAL` (off): CLI reference, Environment Variables.
- `bench/task_outcome/lexical-anchoring/README.md`: the replay, task by
  task, and how to reproduce it; `replay_lexical.py` is the script.
- `docs/specs/TASK-OUTCOME-BENCHMARK-SPEC.md`, change log, 2026-11-01: the
  pre-registration and the result.

---

## Also in v4.24.0: `neuralmind measure sessions`

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

### What you see

For one developer's Claude Code sessions (the
[first field report](https://github.com/dfrostar/neuralmind/blob/main/bench/exploration-share/2026-11-01/README.md):
90 interactive sessions, 2026-10-02 to 2026-11-01, pass 6), in the layout the
command prints. Yours will differ:

```text
Exploration share of the token bill
Sessions started 2026-10-02 to 2026-11-01 (last 30 days). Claude Code: read; Hermes: not found.

Sessions: 90

Exploration share (reading and searching code):

Agent / source             Sessions  API calls  Exploration of context  of billed prompt  Median session
-------------------------  --------  ---------  ----------------------  ----------------  --------------
claude-code / interactive        90     13,236                   29.6%             19.0%           20.4%

What else the recorded context holds, and how much of the bill it covers:

Agent / source             Prompt tokens billed  Recorded / billed  NeuralMind block  Edits  Other shell
-------------------------  --------------------  -----------------  ----------------  -----  -----------
claude-code / interactive         3,900,183,630              64.2%              0.0%   4.5%        15.0%

Pre-registered reading (interactive sessions, share of recorded context):

  claude-code/interactive (90 sessions): 10% to 30%: the claim stands with the share beside it

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

### Options

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

### What the agent and your tools see after upgrading

Nothing, until you run it: no hook, no MCP tool and no prompt changes.

| Agent | Read by `measure sessions` |
|---|---|
| Claude Code | Yes: `~/.claude/projects/*/*.jsonl` (`$CLAUDE_CONFIG_DIR/projects` when set), the `usage` it recorded for each API call. Subagent transcripts (sidechain files, and `<session>/subagents/agent-*.jsonl`) are their own row. |
| Hermes-Agent | Yes: `state.db` in the Hermes home, opened read-only. Hermes bills per session, so its row is calibrated to the bill. |
| Cursor, Cline, Continue, Codex, other MCP clients | No. They keep their sessions elsewhere, in other formats, and there is no collector for them yet; nothing is read and nothing is reported. |

Stdout holds aggregates only: no paths, project names, prompts or session ids.
Claude Code's transcripts cover every project on the machine and are pooled; the
report has no per-project breakdown, because that would print project names.

### Under the hood

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
- **Definitions are unchanged.** The collectors are the code of the spec's pass 6,
  and the spec's pointers to the code now name `neuralmind/measure/`.

### Limits

- Presence after a compaction is modelled from the flags the agents keep, and
  the numerator's tokenizer is not the provider's. The first field report's
  Claude Code sessions are accounted for to 64.2% of their bill, and the
  shares are stated with that beside them.
- The first field report is one developer's two machines. Its Claude Code figure
  (29.6% of the context, 19.0% of the billed prompt) and its Hermes figure
  (10.5%) both sit within a few points of a threshold, so they are not a
  finding about the thresholds, and not a result for your sessions.
- A session still running when you run the command is included as far as it has
  got.

Walkthrough: [Measure what your agent's token bill goes to](../use-cases/measure-what-your-agent-spends.md).
Command reference: [`measure sessions`](../wiki/CLI-Reference.md#measure-sessions-v4240).
