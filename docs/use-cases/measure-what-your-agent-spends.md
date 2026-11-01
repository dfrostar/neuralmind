# Measure what your agent's token bill goes to

> Goal: find out, from the sessions your agents already recorded on this
> machine, what share of the prompt tokens they were billed for went to
> *reading and searching code* (exploration), and what share went to everything
> else. No claim attached: it is a meter.

**Who this is for:** anyone who pays for an AI coding agent by the token and
wants to know what the tokens went to before deciding where to look. Also
anyone weighing a retrieval tool, NeuralMind included: a tool that changes how
much code an agent reads can only matter to a bill as far as reading code is
part of that bill, and that share differs by developer, by agent and by kind of
work. **Needs:** `pip install neuralmind` (*v4.24.0+*), and Claude Code or
Hermes-Agent sessions on this machine. It needs no project, no index and no
build.

## 1. Run it

```bash
neuralmind measure sessions
```

It looks for `~/.claude/projects` (Claude Code, or `$CLAUDE_CONFIG_DIR/projects`)
and for `state.db` in your Hermes home (usually `~/.hermes/state.db`), reads
the sessions that started in the last 30 days, and prints this. The figures
here are the first field report's for one developer's Claude Code sessions
(87 interactive sessions, 2026-10-02 to 2026-11-01, computed before the spec's
pass-5 classifier fixes), in the layout the command prints; yours will differ:

```text
Exploration share of the token bill
Sessions started 2026-10-02 to 2026-11-01 (last 30 days). Claude Code: read; Hermes: not found.

Sessions: 87

Exploration share (reading and searching code):

Agent / source             Sessions  API calls  Exploration of context  of billed prompt  Median session
-------------------------  --------  ---------  ----------------------  ----------------  --------------
claude-code / interactive        87     12,691                   30.6%             19.6%           21.0%

What else the recorded context holds, and how much of the bill it covers:

Agent / source             Prompt tokens billed  Recorded / billed  NeuralMind block  Edits  Other shell
-------------------------  --------------------  -----------------  ----------------  -----  -----------
claude-code / interactive         3,752,452,025              63.8%              0.0%   4.5%        15.2%

Pre-registered reading (interactive sessions, share of recorded context):

  claude-code/interactive (87 sessions): 30% or more: a material part of the bill

Tokenizer: o200k_base
```

(Below that it prints a short note on what each column means and a link to the
spec.) Nothing is installed, indexed or changed by running it, and it writes no
file unless you ask for one with `--rows`.

## 2. Read the table

- **Exploration of context** is the headline. Each API call carries a context:
  the system prompt, your messages, the agent's, every tool call and every tool
  result still in the window. This is the exploration tool results in those
  contexts (Claude Code's `Read`, `Grep`, `Glob`; Hermes's `read_file`,
  `search_files`; and shell commands that only read: `cat`, `rg`, `git log`,
  `sed` without `-i`, with nothing redirected to a file), plus the arguments of
  those calls, as a share of everything the transcripts record those contexts
  holding. A result counts once for every call that carried it, until a
  compaction or the agent's own trimming dropped it.
- **of billed prompt** divides the same exploration tokens by the prompt tokens
  the provider reported. The transcripts don't hold the system prompt, the tool
  schemas or the hidden parts of a prompt, so they account for only part of
  what was billed: **Recorded / billed** says how much (63.8% above; Hermes
  bills per session and its row is calibrated to the bill, so it reads 100%).
  The unrecorded part of a prompt holds no tool results, so this share is the
  first one times that ratio. When the two differ, the second is the one that
  speaks to a bill.
- **Median session** is the middle of the per-session exploration shares, so one
  long session can't set it.
- **NeuralMind block**, **Edits**, **Other shell** are other categories of the
  same recorded context, for comparison. The block is what NeuralMind's own
  per-prompt hook adds to a session, so it is also what NeuralMind costs; it
  reads 0.0% above because the sessions were mostly in projects without it.
- **Sessions, API calls, Prompt tokens billed** are counts. Automated,
  subagent and benchmark sessions (Hermes cron, Claude Code sidechains and the
  like) get their own rows and are never read against the thresholds.

## 3. Read the reading

The thresholds were fixed in the
[spec](../specs/EXPLORATION-SHARE-SPEC.md) before the first share was computed.
They apply to interactive sessions' share of the recorded context:

| Exploration of context | The spec's reading |
|---|---|
| under 10% | "arithmetic, not felt on a bill": whatever a tool changes about how much code an agent reads, it changes a small part of what you are billed for. |
| 10% to 30% | "the claim stands with the share beside it": a per-question token ratio is quoted with this share next to it. |
| 30% or more | "a material part of the bill". |

The command prints the line that applies, with the number of sessions it rests
on. A reading from a handful of sessions is an anecdote, and one close to a
threshold is not a finding about the threshold: the first field report's two
readings sit within a few points of one.

## 4. Narrow it, script it, keep the rows

```bash
neuralmind measure sessions --since-days 7          # a shorter window
neuralmind measure sessions --claude-root ~/backup/claude/projects
neuralmind measure sessions --hermes-db ~/backup/state.db
neuralmind measure sessions --json | jq '.groups["claude-code/interactive"].exploration_share_of_prompt'
neuralmind measure sessions --rows sessions.jsonl   # per-session rows, for your own analysis
neuralmind measure sessions --estimate              # characters / 4, no tiktoken
```

- **Exit 0** after printing a report, **exit 2** when no session started in the
  window (the message says which of Claude Code and Hermes it found) or an
  argument is wrong, so a cron job can tell "nothing to measure" from a result.
  **Exit 1** means the `--rows` file couldn't be written.
- **Tokens are counted with tiktoken's `o200k_base`** when tiktoken is installed
  and its vocabulary is available, the tokenizer of NeuralMind's public
  benchmark; otherwise with characters ÷ 4, and the report says which. tiktoken
  fetches its vocabulary the first time it is used; `--estimate` skips tiktoken
  entirely. Both sides of every share use the same count, so the ratio does not
  depend on it.
- **Stdout is aggregates only:** no paths, project names, prompts or session ids.
  `--rows` writes one JSON line per session (its id, source label, model,
  timestamps, and token counts by kind) to the path you give, replacing the file;
  it holds no prompt text or paths. Claude Code's transcripts cover every
  project on the machine, and the report pools them: there is no per-project
  breakdown, because that would print project names.
- **Hermes's `state.db` is opened read-only.** A transcript or database it
  can't read is reported on stderr and skipped, and the other source is still
  measured.

## 5. What it does and doesn't tell you

It tells you where the tokens of your recorded sessions went, under a model of
what each API call carried that the
[spec](../specs/EXPLORATION-SHARE-SPEC.md) defines and its limits section
qualifies: presence after a compaction is modelled from the flags the agents
keep, and the numerator's tokenizer is not the provider's (hence the
*Recorded / billed* column).

It does not tell you what any tool would change. A share of exploration bounds
what retrieval could affect; it is not what NeuralMind affects: a block that
names the right file replaces some reads, not all of them, and the block itself
costs tokens on every call. The per-question side of that comparison is
[`neuralmind benchmark`](./benchmark-your-repo.md) and the
[public benchmark](../benchmarks/public.md); whether an agent does better with
it is what [the task-outcome pilot](./check-what-your-agent-is-handed.md) measures. This
page is the denominator for both. It covers Claude Code and Hermes-Agent;
other agents keep their sessions in other formats, and there is no collector
for them yet.

## Existing and new workflows

- **Existing:** [Cost optimization](./cost-optimization.md) prices the queries
  NeuralMind answered. This measures the other side: what the agent's own
  sessions spent, whether or not NeuralMind was involved.
- **New:** run it before you adopt any retrieval tool, to see whether reading and
  searching is a large enough part of your bill for such a tool to matter, and
  again a month after, on the same command, to see whether the share moved. The
  second run is a measurement of your sessions, not of the tool.

## The first field report, and the code

The first result, one developer's Claude Code and Hermes sessions over 30 days,
with every revision of the method it went through and the misses:
[`bench/exploration-share/2026-11-01/`](https://github.com/dfrostar/neuralmind/blob/main/bench/exploration-share/2026-11-01/README.md).
The same collectors run nightly on a Hermes host through
`python -m evals.exploration_share` in a source checkout, which also appends to a
rows file and writes summaries; `neuralmind measure sessions` is the same code
(`neuralmind/measure/`), installed with the package.
