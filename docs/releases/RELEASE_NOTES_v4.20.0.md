# NeuralMind v4.20.0 — an agent that can see NeuralMind: MCP server instructions, a six-tool default list, and the leading file's code in the prompt block

**Type:** Minor release | **Theme:** getting what NeuralMind finds in front of the agent, measured before and after

The [task-outcome pilot](../specs/TASK-OUTCOME-BENCHMARK-SPEC.md) ran the same
agent on 20 real bug fixes with and without NeuralMind: 120 runs. NeuralMind
made no difference: median cost per task +0.0% (95% CI −5.2% to +8.6%), 18 of
20 tasks solved either way. Replaying what NeuralMind gave the agent in those
runs, with no agent and no API cost, showed why:

- **The agent never saw what the tools were for.** Claude Code defers MCP
  tools: the model sees their names and has to look a tool up before it can
  call it. It saw 28 names, no descriptions and no word on when to use any of
  them, and called none in 60 runs.
- **The prompt block named the right file and the agent searched anyway.**
  The `UserPromptSubmit` hook named the file the fix changed in 17 of 20
  tasks. The agent made a median of 4 search or read calls before its first
  edit, with NeuralMind or without it.

This release changes both. It doesn't claim the agent now costs less: that
takes the outcome benchmark's confirmatory run, on new tasks. What it does
measure is below.

---

## What changed

### The MCP server says what it's for

The server now sends **instructions** in its `initialize` reply. Claude Code
shows a server's instructions to the model even while that server's tools
are deferred. They say: to find where something is implemented, or the code
behind a bug from its symptom, call `neuralmind_search` before Grep or Glob;
`neuralmind_query` to understand how a part works; `neuralmind_skeleton`,
`neuralmind_impact` and `neuralmind_query_decisions` for structure,
dependents and recorded decisions; and to start from a prompt's NeuralMind
block when it has one.

Asked, before calling anything, which tool it would use to find the code
behind a bug, Claude Code 2.1.287 on Sonnet 5.5 answered "NONE" with v4.15.1's
server, and "neuralmind_search", quoting the instructions, with this one.

### `tools/list` offers six tools by default

`neuralmind_search`, `neuralmind_query`, `neuralmind_skeleton`,
`neuralmind_impact`, `neuralmind_wakeup` and `neuralmind_query_decisions`.
The other 22 (build, stats, benchmark, savings, the synapse tools, health,
review, compliance report, document ingestion, and the rest of the decision
tools) are still served: a client that calls one by name gets the same answer
as before. They're just not in the list an agent chooses from.

| `NEURALMIND_MCP_TOOLS` | `tools/list` offers |
|---|---|
| unset, empty or `core` | the six above |
| `all` | all 28, as before v4.20.0 |
| `name,name,…` | those tools (unknown names are ignored) |

### The prompt block shows the leading file's code

When one file clearly leads the prompt's matches (their summed score is at
least twice the next file's), the block the `UserPromptSubmit` hook adds (and
the Hermes plugin's `pre_llm_call` hook) now quotes that file's best-matching
function or class:

````
Code matching this prompt:
- neuralmind/secret_scan.py: redact_text() L479, scan_text() L402, …
- neuralmind/output_cache.py: …
Most matches are in neuralmind/secret_scan.py. Its best match, L348-L377 (read the file before you edit it):
```
def _scan_line(…):
    …
```
````

- **From the working tree,** so it is what the agent would read; from the
  symbol's first line to the line before the next symbol the graph records in
  that file, at most 40 lines.
- **Secrets are redacted** with the same scanner `neuralmind last` uses.
- **No lead, no code:** with no file 2:1 ahead, the block is the file list as
  before. `NEURALMIND_RECALL_EXCERPT=0` turns the excerpt off.

### `evals/task_outcome/replay.py`: the hook, scored offline, in CI

It exports each of the pilot's 20 tasks at the fix's parent commit, builds the
index, sends the task's prompt through `neuralmind _hook prompt-submit`, and
scores the block against the fix's own diff. A new workflow,
**Prompt-recall replay**, runs it on every pull request that touches the
recall path and fails below its floors. Measured on this release:

| Of 20 tasks | v4.20.0 |
|---|---|
| The block names a file the fix changed | 17 |
| …and names it first | 10 |
| The block quotes code | 9 |
| …from a file the fix changed | 7 of 9 |
| …covering lines the fix changed | 2 of 9 |

The last row is the honest limit of the excerpt. The best-matching symbol is
usually in the right file, and usually not the function the fix touched: a
symptom reads like what the code is *about*, not where it breaks. The
excerpt's gate was set on these same 20 prompts, so 7 of 9 is a ceiling, not
an estimate. Whether it changes what the agent does is for the outcome
benchmark to say.

---

## What the agent actually sees post-install

| Agent | Before v4.20.0 | From v4.20.0 |
|---|---|---|
| **Claude Code** | 28 deferred tool names, nothing saying when to use one; a list of file names on each prompt | Six deferred tool names and the server's instructions on when to call them; on a prompt where one file clearly leads, that file's best match as code |
| **Cursor / Cline / Continue** | All 28 tools with descriptions in the tool list | The six core tools, with the server's instructions where the client shows them; `NEURALMIND_MCP_TOOLS=all` in the server's environment restores the full list |
| **Hermes-Agent plugin** | A list of file names on each turn (`pre_llm_call`) | The same block, with the leading file's code when one leads |
| **Generic MCP client** | 28 tools | Six listed; all 28 still answer when called by name |

## Upgrading

- **If an agent or script relies on a tool outside the six**, by name, it
  keeps working. If an agent needs to *see* it to choose it (Cursor's tool
  picker, say), set `NEURALMIND_MCP_TOOLS=all`, or name the tools, in the MCP
  server's environment.
- Nothing to rebuild: the excerpt reads the index you have.

## New environment variables

| Variable | Default | Effect |
|---|---|---|
| `NEURALMIND_MCP_TOOLS` | `core` | Which tools `tools/list` offers: `core` (six), `all`, or a comma-separated list of names |
| `NEURALMIND_RECALL_EXCERPT` | on | `0` leaves the leading file's code out of the prompt block |

## Use cases

- **Existing: [NeuralMind in Claude Code](../use-cases/claude-code.md).** The
  agent gets the tool it should reach for named in the server's instructions
  and, on prompts where NeuralMind is confident, the code itself.
- **New: [check what your agent is handed](../use-cases/check-what-your-agent-is-handed.md)
  before paying for agent runs.** `python -m evals.task_outcome.replay` scores
  what the hook shows for a set of bug-fix tasks against their real fixes,
  offline. The harness that measures the outcome (`evals/task_outcome/run.py`)
  can then measure whether it mattered.
