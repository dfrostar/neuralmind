# NeuralMind v4.21.0 — an agent that can see NeuralMind: MCP server instructions, a six-tool default list, and the leading file's code in the prompt block; and Intel macOS and Windows ARM work again out of the box

**Type:** Minor release | **Theme:** getting what NeuralMind finds in front of the agent, measured before and after; and the default backend falls back to ChromaDB where turbovec has no wheel

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

This release changes both, and the agent's behaviour on those 20 tasks didn't
change: an exploratory rerun with this release found the agent still called
no NeuralMind tool, and searched as much before its first edit as without
NeuralMind ([measured after](#measured-after-the-agents-behaviour-didnt-change)).
What the release does change, and what it doesn't, is below.

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
| `all` | all 28, as before v4.21.0 |
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

| Of 20 tasks | v4.21.0 |
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
an estimate.

### Measured after: the agent's behaviour didn't change

An [exploratory rerun](https://github.com/dfrostar/neuralmind/blob/main/bench/task_outcome/exploratory-agent-uptake/README.md)
(not pre-registered) ran the pilot's 20 tasks again, 3 times each, with this
release in the NeuralMind arm. Same model, Claude Code version, prompts and
budget, against the pilot's baseline runs:

| Per task, 60 runs each | Without NeuralMind | v4.15.1 (pilot) | v4.21.0 |
|---|---|---|---|
| Runs calling a NeuralMind tool | 0 | 0 | 0 |
| Search or read calls before the first edit (median) | 4.0 | 4.2 | 4.0 |
| Turns (median) | 10.3 | 10.8 | 10.3 |
| Runs solved | 53 | 55 | 55 |

- **The instructions reached the model and didn't change its choice.** Asked,
  it names `neuralmind_search`; given a real bug, it used Grep and Read in all
  60 runs and never called ToolSearch, which a deferred tool needs first.
- **The excerpt didn't replace the agent's own search.** On the 9 tasks where
  the block quoted code, the agent made a median of 4.0 search or read calls
  before its first edit, against 3.0 without NeuralMind.
- **Cost:** median −2.1% per task against the baseline (95% CI −6.9% to
  +6.5%, p = 0.34), 18 of 20 tasks solved in each arm. No difference shown.

On these tasks an agent finds the file to fix in about four searches with or
without help, which leaves little to save. Whether NeuralMind changes the
outcome on a larger, unfamiliar repository with harder fixes is not measured
yet.

### Also: an idle association's decay rate relaxes back to the default

Each learned association has a half-life of its own, learned from how often it
was reinforced: between 3 and 120 days, beside the namespace default of 30 days
for personal and branch memory and 60 for the team's shared baseline. The
design blends that learned rate back toward the default the longer an
association sits idle, but the blend was computed only by `reinforce()`, at
the moment it set the last-activation time, where it changes nothing. So an
idle association kept its learned rate for as long as it stayed idle.

What that did, on the schedules `tests/test_learned_decay.py` replays:

| Association | Before | Now |
|---|---|---|
| Used three times, a month apart (learns a half-life under 15 days) | Pruned after two idle months | Kept after two idle months, pruned within five |
| Used every day for ten days (learns one over 60 days) | Kept its long half-life however long it sat | Slides toward 30 days while idle; still above 80% of full weight after two idle weeks |
| Used five or more times | Held at the long-term floor | Unchanged |

`decay()` now integrates the blend over the idle time. The integral has a
closed form (`learned_decay.blended_decay_factor`, mirrored in the SQL), so a
decay pass still charges only the time since the previous one, and many passes
still decay a weight exactly as much as one pass at the end. The code index is
unaffected: this changes how long learned associations steer recall, not what
search can find.

Tests: in `tests/test_learned_decay.py`, `blended_decay_factor` matches a
numerical integral of the blended rate, composes exactly across passes and
reduces to the plain half-life when the rates agree; `decay()` computes the
same factor in SQL for personal, branch and shared memory
(`TestDecayAppliesTheBlend`, which fails on v4.20.0);
`TestForgettingInPractice` replays the schedules above.

---

## Intel macOS and Windows ARM work again out of the box

turbovec publishes wheels for Linux, Apple Silicon macOS and 64-bit Windows.
On every other platform, notably Intel macOS and Windows ARM, `pip install
neuralmind` installs ChromaDB in its place. That has been the design since the
default install went ChromaDB-free (#251): the default backend was `auto`,
which used turbovec where it was installed and ChromaDB where it wasn't.

v0.46.0 made the default a fixed `turbovec` and dropped that fallback, but
left the install markers as they were. From v0.46.0 to v4.20.0, on those
platforms, a default install selected a backend it didn't have: `neuralmind
build`, and everything that builds, failed with `No module named 'turbovec'`
unless the project set `backend: graph`. `neuralmind demo` failed the same
way. Some of our docs described setting `backend: chroma` there as required.

v4.21.0 restores the fallback. Nothing changes where turbovec is
installed.

### The default backend falls back to ChromaDB where turbovec isn't installed

With no backend configured, or with `backend: auto` or `backend: turbovec`,
NeuralMind uses turbovec when its stack (`turbovec`, `onnxruntime`,
`tokenizers`) imports, and ChromaDB when it doesn't and ChromaDB does. That is
the install you get on Intel macOS and Windows ARM.

- **No deprecation warning for it.** Choosing `backend: graph` or `chroma`
  yourself still warns that ChromaDB is deprecated; the fallback doesn't,
  since you didn't choose it.
- **`neuralmind doctor` shows it.** Its *Backend* line reports the backend in
  use, `graph (auto-selected; turbovec stack not installed)` on those
  platforms. It also stops calling a project with no
  `neuralmind-backend.yaml` "pinned via neuralmind-backend.yaml", which it
  had done since v0.46.0, and says so when a file names `turbovec` but
  ChromaDB serves it.
- **An existing `backend: chroma` keeps working** and can stay or go: the
  default now selects the same backend there.

### A missing backend says what to install

If neither turbovec nor ChromaDB is installed (say, both were uninstalled),
NeuralMind used to fail deep inside a build with a bare `ModuleNotFoundError`.
It now stops when it creates the backend, with what to install:

```
the turbovec backend needs turbovec, which isn't installed. Install it with
`pip install turbovec onnxruntime tokenizers`; where turbovec has no wheel
(Intel macOS, Windows ARM), install ChromaDB instead with
`pip install "neuralmind[chromadb]"`.
```

### `neuralmind demo` on ChromaDB

The demo's bundled index and question vectors (v4.19.0) are turbovec's. On a
ChromaDB install the demo now builds the sample's index with the embedding
model instead, which downloads it once, and says so:

```
[demo] this install uses the ChromaDB backend (turbovec has no wheel for this
platform), so the demo builds the sample's index with the embedding model,
which downloads it once.
```

Offline, it exits 1 with one line saying the model couldn't be downloaded, not
a traceback. With no vector backend at all it exits 1 with the install hint
above. The demo runs offline, with nothing downloaded, where turbovec is
installed: Linux, Apple Silicon macOS and 64-bit Windows.

### What the agent sees on Intel macOS and Windows ARM

On Linux, Apple Silicon macOS and 64-bit Windows, this part changes nothing.

On Intel macOS and Windows ARM, every integration works without a
`neuralmind-backend.yaml`:

| Agent | Before (v0.46.0 to v4.20.0) | After |
|---|---|---|
| Claude Code (hooks + MCP) | Anything that built or read the index failed with `No module named 'turbovec'` until `backend: graph` was set | Works on the default install |
| Cursor / Cline / generic MCP | The same failure on every tool that reads the index | Works on the default install |
| Hermes-Agent plugin | The same failure; no context from the index | Works on the default install |

The first build on those platforms downloads ChromaDB's embedding model once.
For an air-gapped install, stage ChromaDB's model cache as the
[air-gapped walkthrough](../use-cases/air-gapped.md) describes.

### Tests

- `tests/test_backend_manager.py`: the default and `turbovec` resolve to
  ChromaDB when only ChromaDB is installed, with no deprecation warning; stay
  turbovec when its stack is installed or when nothing is; explicit backends
  are never rerouted; a missing turbovec names what to install.
- `tests/test_doctor.py`: no config file reads as auto-selected, on either
  backend; a `turbovec` pin served by ChromaDB says so.
- `tests/test_cli.py::TestCLIDemoWithoutTurbovec`: on ChromaDB the demo says
  it is building with the model and exits 1 with one line when offline; with
  no backend it exits 1 with the install hint.

---

## What the agent actually sees post-install

| Agent | Before v4.21.0 | From v4.21.0 |
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
- **On Intel macOS and Windows ARM** you can delete a `backend: chroma` line you added only to make NeuralMind run; it is harmless to keep.

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
