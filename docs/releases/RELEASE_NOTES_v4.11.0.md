# NeuralMind v4.11.0 — prompt recall that names the files a prompt is about and stays quiet when the prompt isn't about the code, and a session's own record back after compaction

**Type:** Minor release | **Themes:** prompt-time recall ([a gate, and a seeding fix](#prompt-recall-that-knows-when-to-add-nothing); [files and symbols, from the first turn](#prompt-recall-names-files-from-the-first-turn)) · compaction ([the session's own record back](#after-compaction-the-sessions-own-record)) · `query` ranking ([the project's code before its tests, examples and docs](#query-finds-the-projects-code-not-its-tests-examples-and-docs))

Two of the most common complaints about agent context are that tools inject
too much, and that compaction makes the agent forget. Both applied to
NeuralMind's Claude Code hooks, and so did a third, that what does get
injected isn't what the agent needed:

1. **Prompt-time recall fired on prompts that had nothing to do with the
   code.** Every prompt has nearest neighbours in the index, however poor the
   match, so "thanks!", "continue" and "what's the capital of France" each got
   up to eight code nodes. Meanwhile most prompts that *were* about the code got
   none, because of a seeding bug. v4.11.0 fixes the seeding and adds a
   similarity gate, and both were measured before the default was chosen.
2. **Compaction dropped what NeuralMind had already recorded.** Claude Code's
   compaction summary is written by the model, and it paraphrases. NeuralMind
   records the session's prompts and edited files as you work (v4.8.0), but gave
   them back only to the *next* session. After a compaction, the session now gets
   its own record back: its prompts as written, up to 200 characters each, and
   the files it edited.
3. **On a freshly built project, prompt recall named documentation headings,
   not code.** Asked which files in Click parse command-line options, it
   listed eight `docs_*` node ids, six of them at activation 0.00. The block
   now names the files and symbols the prompt matches, the code linked to them,
   and matching docs, as paths. It does this for Hermes too, since the plugin
   runs the same hook action.

No new hooks and no re-install: all three ride on the `UserPromptSubmit`
and `SessionStart` hooks NeuralMind already registers. The hook block's version
is unchanged.

## Prompt recall that knows when to add nothing

### What was wrong

Measured on this repository's own index (6,894 nodes) and synapse store, with
15 prompts about the NeuralMind code and 15 off-topic ones: short replies
("yes", "continue", "looks good, commit it"), general questions, other domains.

| | On-topic prompts with recall | Off-topic prompts with recall |
|---|---|---|
| Before v4.11.0 (measured on v4.9.1) | 5 of 15 | 10 of 15 (9 of them got all 8 nodes) |
| Seeding fix only | 15 of 15 | 15 of 15 |
| **v4.11.0** (seeding fix + gate at 0.35) | **15 of 15** | **1 of 15** |

Two separate problems:

- **The seeding bug.** Spreading activation starts from the prompt's four best
  semantic matches. Those are often a function's *rationale* node
  (`<id>__rationale`, its docstring or comment), which matches prose best. But
  synapses form between the code nodes the agent reads and edits, so the
  rationale node has no edges, and recall from it returned nothing. In this
  store, 5 of the 4,826 nodes with synapse edges were rationale nodes. Recall
  now seeds from the code node a rationale belongs to, found through its
  `rationale_for` edge, so a graphify graph's rationale ids (`<id>_rationale`,
  `<file>_rationale_<n>`) map too. This also changes what the
  MCP `neuralmind_synaptic_neighbors` tool returns.
- **No relevance gate.** Fixing the seeding alone made recall fire on every
  off-topic prompt too. The hook now abstains when the prompt's best match in
  the code scores below `NEURALMIND_RECALL_MIN_SIMILARITY` (default `0.35`).

### Why similarity, and why 0.35

On-topic prompts scored **0.371–0.645** best-match similarity, and off-topic
prompts **0.145–0.364**. At 0.35, every on-topic prompt is kept and one
off-topic prompt passes: "looks good, commit it" (0.364). At 0.37 none pass,
but the lowest on-topic prompt is only 0.001 above it, so 0.35 keeps a margin.

The strength of the activation doesn't separate the two sets. "continue" ranked
among the strongest activations in the whole run. So similarity is the only
gate.

### Reproduce it, or calibrate your own

The harness is in this repository's `tests/`, which the PyPI package doesn't
include, so run it from a source checkout:

```bash
git clone https://github.com/dfrostar/neuralmind && cd neuralmind
neuralmind build .
python -m tests.benchmark.recall_gate .          # this repo's prompt sets
python -m tests.benchmark.recall_gate . --json
python -m tests.benchmark.recall_gate /path/to/project --prompts my_prompts.json
```

`--prompts` takes a JSON file with `on_topic` and `off_topic` lists. It prints
each prompt's similarity, how many files the block would name without the gate
(the "Seeding fix only" row) and a sweep from 0.25 to 0.40: on-topic prompts
kept against off-topic prompts let through (0.35 is the v4.11.0 row). It runs
the current code only, so it can't rerun the first row: v4.9.1's recall
reports no similarity.

### Count what it does

Each prompt's outcome is logged to `.neuralmind/metrics/` as a number, never
the prompt text, and `neuralmind metrics` shows the totals:

```
Prompts seen by recall........          212
Recall injected...............          131
Abstained: low similarity.....           81
Abstained: nothing to name....            0
Abstain rate..................        38.2%
```

(Illustrative numbers.) "Nothing to name" means the prompt matched well
enough, but none of its matches belongs to a file. Since the block names the
matches themselves ([below](#prompt-recall-names-files-from-the-first-turn)),
that's rare. Nothing is logged under `NEURALMIND_NO_LEARN=1`.

## Prompt recall names files, from the first turn

### What was wrong

`neuralmind build` doesn't leave the synapse graph empty: it seeds it with the
code's structural edges (calls, imports, inheritance) and links each doc
heading to its page. On [Click](https://github.com/pallets/click) (2,801 nodes,
4,635 seeded edges), "which files in this repo handle parsing command-line
options?" got this from v4.9.2:

```
## NeuralMind associative recall

- docs_parameters_md (activation 0.05)
- docs_arguments_md (activation 0.05)
- docs_parameters_md__h3 (activation 0.00)
- docs_parameters_md__h20 (activation 0.00)
- docs_parameters_md__h32 (activation 0.00)
- docs_arguments_md__h3 (activation 0.00)
- docs_arguments_md__h24 (activation 0.00)
- docs_arguments_md__h64 (activation 0.00)
```

`src/click/parser.py` and `src/click/core.py` are the answer. In a live Hermes
turn, that block was all the model got, and it answered from what it already
knew about Click. Three causes:

- **Recall listed only neighbours.** It searched for the prompt's four nearest
  nodes and listed what spreading activation reached from them. Spreading
  activation never returns its seeds, so the code that matched best was never
  named. `core.py`'s `make_parser()` was the fifth-best match and
  `parser.py`'s `_OptionParser` the ninth.
- **Doc headings crowded out code.** Click's docs are thorough, so headings
  were two of the four nearest nodes, and the only edges a heading has lead to
  its page and the page's other headings.
- **Node ids aren't paths.** `src_click_core_py__command_cls__make_parser_fn`
  still has to be turned into a file to open.

The seeding fix [above](#prompt-recall-that-knows-when-to-add-nothing) helps
when a docstring matches best, but on its own it still named neither
`parser.py` nor `core.py` for this prompt.

### What the agent sees now

The same prompt, the same fresh index:

```
## NeuralMind associative recall

Code matching this prompt:
- src/click/core.py: make_parser() L1256, Parameter L2241
- src/click/parser.py: _OptionParser L224, parse_args() L298
- examples/repo/repo.py: cli() L44
- src/click/_termui_impl.py: _less_uses_raw_mode() L520
Docs: docs/parameters.md, docs/arguments.md, docs/complex.md
```

- **Code matching this prompt:** up to 4 files, each with up to 3 matching
  symbols and the line they start on. The hook reads the 16 nearest nodes, not
  4, and a docstring match counts as its function. Files rank by the summed
  scores of their matching symbols, so a file with several matches outranks
  one stray match. Test files come after the code they test, unless the prompt
  mentions tests, because they repeat the code's vocabulary and match about as
  well.
- **Connected to it in the synapse graph:** up to 3 files in other places that
  the graph links directly to the listed code: it spreads from up to 4 of the
  listed files' matches, each file's best first, then their next best.
  Structural edges on a fresh index, co-edits as you work. A hub, like Click's `echo()`
  that 305 nodes link to, is damped the way spreading activation already damps
  a hub's outgoing energy, and a link carrying under 5% of the best match's
  score is dropped. On the fresh Click index this part is empty
  for this prompt. After five simulated sessions that edited `parser.py`
  together with `shell_completion.py` and `testing.py`, it reads:

  ```
  Connected to it in the synapse graph:
  - src/click/testing.py: ExceptionInfo L29, EchoingStdin L32
  - src/click/shell_completion.py: shell_complete() L19, CompletionItem L67
  ```

  v4.9.2 and the seeding fix alone named neither file on that graph.
- **Docs:** one line, up to 3 documentation files.

When none of a prompt's matches is code (a book indexed with
`ingest-content`, or a question only the docs answer), its matching documents
are the main list. Everything else is as before: the
heading, the similarity gate, `NEURALMIND_SYNAPSE_INJECT=0`, and the opt-in
cohesion check (`NEURALMIND_SYNAPSE_OUTLIERS=1`), which now reads the linked
nodes.

### Measured

Each prompt has the files that answer it, chosen by reading the code before
anything ran. A prompt counts as *named* when the block names any of them, and
*first* when the first code file it lists is one of them. Fresh indexes, no
usage; tokens are tiktoken `o200k_base`, per injected block.

| | Click, 14 prompts: named | first | tokens, mean (max) | NeuralMind, 15 prompts: named | first | tokens, mean (max) |
|---|---|---|---|---|---|---|
| v4.9.2 | 3 | 3 | 124 (177) | 4 | 1 | 155 (167), 6 prompts got a block |
| Seeding fix + gate only | 8 | 7 | 137 (183) | 14 | 6 | 153 (172) |
| **v4.11.0** | **14** | **11** | **120 (173)** | **14** | **10** | **132 (189)** |

The raw runs behind this table, every block included, are in
[`tests/benchmark/prompt_recall_results.json`](https://github.com/dfrostar/neuralmind/blob/main/tests/benchmark/prompt_recall_results.json):
one fresh index per set, built by v4.11.0, with each release's hook run on it.
The warm-graph and timing figures below come from runs whose data isn't
committed.

The Click set is the one the ranking was tuned on (summed scores, tests after
code). The NeuralMind set, the on-topic prompts of `recall_gate` above at
commit `edbc239c`, was held out. Its one miss, "fix the claims guard test for
site numbers", has no test file among its 16 nearest nodes; its best match
scores 0.375, just over the gate. On the simulated warm Click graph, v4.11.0
named an answering file for 14 of 14 prompts, against 4 for v4.9.2 and 8 for
the seeding fix alone.

The hook isn't slower. Loading the index, searching and spreading takes a
median 133–171 ms per prompt across these three indexes, against 132–190 ms
for the seeding fix alone, on an M3 MacBook (two runs each). Linking one hop
out instead of two keeps a prompt about a much co-edited file fast: on the
warm graph the 90th percentile is 154–199 ms, against 278–372 ms. Two hops
never named an answering file that one hop missed, and on the warm graph they
lost one (13 of 14). The MCP `neuralmind_synaptic_neighbors` tool still
spreads two hops and returns node ids.

### Reproduce it

From a NeuralMind source checkout (the harness is in `tests/`, which the PyPI
package doesn't include):

```bash
git clone https://github.com/pallets/click
git -C click checkout 2247b35ea1c47c727d7a06e51fa280e12a863ff6
neuralmind build click
python -m tests.benchmark.prompt_recall click --prompts tests/benchmark/prompt_recall_click.json
# The NeuralMind set, on a built checkout of the commit it names:
python -m tests.benchmark.prompt_recall . --prompts tests/benchmark/prompt_recall_neuralmind.json -v
```

It runs the hook's own function and reads both the new block and the old
node-id lines, so `PYTHONPATH=<older checkout> python tests/benchmark/prompt_recall.py …`
measures an earlier release. `-v` prints every block.

## After compaction, the session's own record

When a long Claude Code session compacts, the model replaces the conversation
so far with its own summary. Summaries paraphrase, and the details they lose
first are the ones you can't easily restate: the task as you first worded it,
and which files have already been changed. NeuralMind already had both in
`.neuralmind/recaps/`, each prompt as written up to 200 characters. Now the
session gets them back.

- **`SessionStart`** with source `compact` injects that session's own record,
  found by its `session_id`. It's the same fields as the v4.8.0 recap, under a
  different heading.
- **Only its own.** If the session came back under a different `session_id`
  (Claude Code's documentation doesn't say whether that can happen), it gets
  no record: nothing in the hook payloads links the two ids, and a guess could
  hand it another session's prompts. The previous session's recap isn't
  injected either.
- **Compacting isn't activity.** Nothing is written at compaction, so
  compacting an old session doesn't make it the "previous session" a fresh
  start recaps.

`NEURALMIND_SESSION_RECAP=0` turns this off along with the recap.
`NEURALMIND_NO_LEARN=1` records nothing, so a session run with it gets back only
what was recorded before it was set.

## `query` finds the project's code, not its tests, examples and docs

`neuralmind build .` indexes a checkout from its root, so a repository's tests,
example scripts and docs are in the index next to its code. They competed with
it for the four search results `query` returns (L3), and often took all four.
On a freshly built index of [pallets/click](https://github.com/pallets/click)
(commit `2247b35`), "which files in this repo handle parsing command-line
options?" returned an example script, a test docstring and a doc heading, and
listed `examples/imagepipe` and `examples/inout` as the relevant code areas.
`src/click/core.py`, which builds the option parser, was the 5th and 8th
result of the search, and never reached the answer. `neuralmind search` found
it, because `search` doesn't pick four.

### Why tests, examples and docs won

Three causes, each found on that index:

1. **L3 picked its four hits before ranking them by intent.** The four slots
   go to the top four of the fused vector and keyword search. The intent
   multipliers (×3 for code when the question asks for code) only re-order
   those four, so when all four were tests, examples and docs, nothing after
   could bring the code back. v4.6.0's eval measured the same limit from the
   other side: the intent rules "only re-order the four hits L3 already
   chose".
2. **Tests and examples were scored as the code itself.** A test repeats the
   names of the code it tests, and the code-signal boost multiplies a code hit
   by up to 10 for sharing the question's identifiers, so
   `test_suggest_possible_options()` outranked the code that works out the
   suggestions. An example script uses the words of a question about the
   feature it demonstrates; a doc heading is a short, question-like match.
3. **L2 listed each cluster's first members in path order.** `examples/`
   sorts before `src/`, so a 390-node cluster with three nodes from
   `examples/inout/inout.py` was shown as `inout.py`, and the 963-node cluster
   holding `core.py` as `examples/completion/completion.py`. That is where
   `imagepipe` and `inout` came from.

### What changed in ranking

`query` now tells a hit's role apart, by its path inside the project: the
project's own code; a test or example (a `test`, `tests`, `spec`,
`__tests__`, `example(s)`, `demo(s)` or `sample(s)` directory, or a test
file's name: `test_*.py`, `*_test.go`, `*.test.ts`, `*.spec.js`,
`conftest.py`); or a doc (a doc node or file, an ingested `document_pdf`
chunk included). Only the part of the path inside the project counts, so a
checkout at `~/work/examples/app` doesn't make its own code an example, even
when the graph stores absolute paths.

- **The project's code is owed L3 slots.** When fewer than two of the four
  hits are the project's code (one, for a question classified `docs`) and
  ranks 5–10 of the same search hold some, the weakest test, example or doc
  hits give their slots to it, a file not yet shown first. It swaps hits and
  never adds one, so the answer's size doesn't grow. Structural and synapse
  recall run next and may displace weak hits too, so the floor is checked
  again on what they leave.
- **Tests and examples count a third** when ranking, under every intent,
  unless the question names them ("how do I test …", "an example of …") or
  names a test (`test_parse_option()`, `parse_test.go`, `UserServiceTest`).
  Under `code` intent they are scored like docs, which are about the code,
  instead of getting the code's ×3 and identifier boosts. Docs count a third
  under `code` intent too, so a docstring of the code ranks above a doc heading.
- **L2 lists a cluster's own code first**, and test and example hits count a
  third toward a cluster's relevance. It reads past a cluster's first ten
  members only when one of them isn't the project's code, and remembers the
  order until the index changes.
- **`--trace` shows the swap:** `[L3/roles] 2 slot(s) from tests/examples/docs
  to the project's code`.
- **`NEURALMIND_L3_ROLES=0`** turns it all off and gives v4.10.0's ranking back.

**Nothing changes when only the project's code is indexed.** Where every hit
is the project's code, as on an index of a library's source directory, there
is nothing to swap or weigh, and L2's sort is stable. That is also why the
[public benchmark](../benchmarks/public.md), which indexes each library's
source directory only, never showed this. Its result is unchanged, to the byte
(below).

### What `query` returns now

`neuralmind query click "which files in this repo handle parsing
command-line options?"` on that index, abridged. Before:

```
## Relevant Code Areas
### Cluster 45 (relevance: 1.57)
- imagepipe.py (code) — imagepipe.py
- cli() (code) — imagepipe.py
### Cluster 46 (relevance: 0.96)
- inout.py (code) — inout.py
- cli() (code) — inout.py
…
## Search Results
1. **Repo is a command line tool that showcases how to build complex …** (score: 0.15)
   File: examples/repo/repo.py
2. **Raw-mode detection parses the option tokens from ``LESS`` …** (score: 0.14)
   File: tests/test_termui.py
3. **Copies one or multiple files to a new location. …** (score: 0.09)
   File: examples/repo/repo.py
4. **Options** (score: 0.08)
   File: docs/parameters.md
```

After (1,085 tokens, down from 1,238):

```
## Relevant Code Areas
### Cluster 45 (relevance: 0.52)
- utils.py (code) — utils.py
…
### Cluster 42 (relevance: 0.48)
- core.py (code) — core.py
…
## Search Results
1. **Commands are the basic building block of command line interfaces in Click. …** (score: 0.07)
   File: src/click/core.py
2. **Creates the underlying option parser for this command.** (score: 0.06)
   File: src/click/core.py
3. **Raw-mode detection parses the option tokens from ``LESS`` …** (score: 0.05)
   File: tests/test_termui.py
4. **Options** (score: 0.03)
   File: docs/parameters.md
```

With `--trace`, the swap is one line:
`[L3/roles] 2 slot(s) from tests/examples/docs to the project's code`.
The second `core.py` hit is the docstring of `make_parser()`, which builds
the option parser. `parser.py` itself still isn't named (see below).

### Measured: roles on vs off

Every number here is reproducible on demand, not a CI gate. "Before" is the
same build with `NEURALMIND_L3_ROLES=0`, which ranks as v4.10.0 did; every
run is read-only. hit@5 / MRR, from the scorer `neuralmind eval` uses:

| Question set | Index | Before | After | Tokens |
|---|---|---:|---:|---:|
| 14 Click questions, **the set this was tuned on** ([`bench/retrieval/roles-v4.11.0/click-2247b35.md`](https://github.com/dfrostar/neuralmind/blob/main/bench/retrieval/roles-v4.11.0/click-2247b35.md)) | `click` @ `2247b35`, whole repository | 64% / 0.49 | **100% / 0.80** | +1.8% |
| 30 pre-registered questions per repo, **held out** ([`bench/retrieval/roles-v4.11.0/full-repo`](https://github.com/dfrostar/neuralmind/blob/main/bench/retrieval/roles-v4.11.0/full-repo/report.md)) | `requests`, `click`, `flask`, `rich` at the public benchmark's commits, whole repository | 77.5% / 0.615 | **79.2% / 0.672** | +1.6% |
| the same 30, this repository, **held out** ([`bench/retrieval/roles-v4.11.0/source-dir`](https://github.com/dfrostar/neuralmind/blob/main/bench/retrieval/roles-v4.11.0/source-dir/report.md)) | `neuralmind`, docs indexed | 57% / 0.45 | **70% / 0.55** | +1.8% |
| the same 30 per repo | `requests`, `click`, `flask`, `rich`, source directory only | identical | identical | identical |
| the public benchmark, 40 queries | source directory only | — | **`results.json` byte-identical** | identical |

- **The tuning set.** The 14 questions and their gold files come from the
  prompt-recall benchmark of
  [#607](https://github.com/dfrostar/neuralmind/pull/607), whose gold files
  were chosen by reading the code before any run. An answering file is in the
  results for all 14, up from 9; hit@1 rose from 5 to 10. Reproduce it with
  `neuralmind eval click --questions tests/benchmark/query_recall_click.eval.yaml`
  (the file has the clone command), and again with `NEURALMIND_L3_ROLES=0`.
- **Held out, whole repository.** The pre-registered questions from v4.6.0's
  eval, run against each repository indexed from its root
  (`python -m evals.retrieval.run --full-repo`, new in this release). Of 120
  questions, 18 rank their gold file higher and **none lower**; hit@1 went from
  59 to 69. hit@5 rose on `click` only (77% → 83%, two questions); MRR rose on
  all four (`requests` 0.69 → 0.72, `click` 0.64 → 0.76, `flask` 0.65 →
  0.72, `rich` 0.48 → 0.50). Tokens rose most on `flask`, 3.8%.
- **Held out, this repository.** With its docs indexed, hit@5 rose from 57%
  to 70% (17 to 21 of 30) and MRR from 0.45 to 0.55; seven questions rank
  their gold file higher and none lower, and the six that a doc answers kept
  their ranks. On 15 more prompts about this repository, from #607's held-out set, an
  answering file is in the results for 11, up from 6.
- **Source directories: no change, by construction.** The four libraries'
  source directories hold only the library's code, so there is nothing to swap
  or weigh: per question, every rank and token count is the same. The public
  benchmark indexes the same directories: run on one machine, this release's
  code and v4.10.0's produce byte-identical `results.json` files, so the
  published figures stand.

**Where it still loses.** On the tuning set, four answers rank docs above the
code: "how are environment variables mapped to options?", "how do command
groups dispatch to subcommands?" and "where are the built-in parameter types
like IntRange and Choice defined?" put `core.py` or `types.py` third, and
"how can I test a click command and capture its output?" puts `testing.py`
fourth. Each is a question the intent classifier calls `docs` or `hybrid`,
where docs keep their full weight. And `parser.py`, the other answer to the
parsing question, is never named: it isn't in the search's top ten, so
there is nothing to swap in. On `rich`, 10 of 30 held-out questions still miss
on the whole repository, as they did before.

**By spec 7's keep rule, this would not pass.** The rule v4.6.0 used to pick
defaults asks for hit@5 to rise on at least three repositories. This change
is a no-op wherever only the project's code is indexed, which is four of the
five repositories in the standard eval, and on whole repositories it raised
hit@5 on one of four. It ships on by default because it was written for the
case those runs don't cover, a repository indexed from its root, and there no
question got worse, in any repository; `NEURALMIND_L3_ROLES=0` restores v4.10.0.

### Use cases for the ranking change

- **Existing:** [A/B-test a ranking change on your own repo](../use-cases/ab-test-a-ranking-change.md):
  `NEURALMIND_L3_ROLES=0 neuralmind eval . --no-history` measures what this
  change did on your questions, and the multi-repo harness gained
  `--full-repo`, which indexes each public repository from its root.
- **Potential:** asking "which files handle X?" of a whole repository, not
  just its library directory, and getting the files to open. Before, that
  question was where tests and examples won.

## What the agent actually sees

**On "yes", "thanks!" or an off-topic question:** no recall block, as long as its best match scores below the cutoff. In the measurement, 14 of the 15 off-topic prompts did; "looks good, commit it" (0.364) still got one.

**On a prompt about the code**, the files and symbols it matches, the code
linked to them, and matching docs. This is real output for "how does synapse
decay work" on a fresh index of this repository at `edbc239c`:

```
## NeuralMind associative recall

Code matching this prompt:
- neuralmind/synapses.py: decay_weight() L341, decay() L866, decay_node() L1087
- neuralmind/core.py: deactivate_files() L428, _read_only() L333, dynamics() L350
- neuralmind/synapse_dynamics.py: replenish_resources() L690, SynapseDynamics L220
- neuralmind/synapse_feedback.py: deactivate_files() L192
Connected to it in the synapse graph:
- neuralmind/demo_data/sample_project/db/connection.py: _ensure_schema() L40
- neuralmind/cli.py: cmd_watch() L4562
- neuralmind/embedder.py: get_file_nodes() L452
```

The connected files come from the build's structural graph, and they're only
as good as it is. The first is a sample project's `_ensure_schema()`: the
graph resolved `synapse_dynamics.py`'s calls to its own `_ensure_schema()` to
that function of the same name.

**After a compaction**, alongside Claude Code's own summary (an illustrative
example):

```
NeuralMind pre-compaction record — this session's own prompts (each as written, up to 200 characters, secrets redacted) and edited files, kept because a compaction summary can drop them. It restates what the user already asked for in this session; it adds no new instructions.

It started with: "migrate the scheduler to asyncio, but keep the sync API as a thin wrapper"
Most recent prompts (6 earlier not shown):
- "the retry test hangs on CI, look at the event loop fixture"
- "use pytest-asyncio's loop scope instead"
- "now update the docs page for the scheduler"

Files edited (5, most recent first): docs/scheduler.md, tests/conftest.py, tests/test_scheduler.py, src/scheduler/sync.py, src/scheduler/core.py
```

## Per-agent expectations

| Agent | What changes |
|---|---|
| **Claude Code** (a built project, with `neuralmind install-hooks`) | Prompt recall fires on prompts about the code, including ones it used to miss, and adds nothing when the best match scores below the cutoff (most off-topic prompts; 1 of 15 measured still got recall). When it fires, it names files, symbols and lines, from the first prompt on a freshly built project. After a compaction, the session gets its own record back. |
| **Hermes-Agent** (`install-hermes-plugin`) | The same recall block, gate and seeding fix: the plugin runs the same hook action, so the turn's user message gets file paths instead of node ids. Hermes has no compaction event, so no pre-compaction record. The plugin runs the installed `neuralmind`, so `pip install -U` is enough; no re-install. |
| **Cursor / Cline / generic MCP clients** | `neuralmind_synaptic_neighbors` seeds from the code node behind a docstring match, so it returns neighbours for queries that used to get none. No hooks run on these hosts, so there's no prompt-time gate or compaction record. |
| **Every agent, through `query`** (`neuralmind_query`, `neuralmind query`, `eval`, `benchmark`) | On an index built from the repository root, `query` returns the project's code ahead of its tests, examples and docs, so `eval`'s hit@5 on a whole repository can rise after upgrading. The hooks' prompt recall, recap and wake-up context don't use L3, so the ranking change doesn't touch them. |

## Settings

| Variable | Default | Effect |
|---|---|---|
| `NEURALMIND_RECALL_MIN_SIMILARITY` | `0.35` | Prompt-time recall adds nothing below this best-match similarity. `0` never abstains |
| `NEURALMIND_SYNAPSE_INJECT` | on | `0` turns prompt-time recall off entirely, as before |
| `NEURALMIND_SESSION_RECAP` | on | `0` stops the recap and the pre-compaction record |
| `NEURALMIND_NO_LEARN` | off | `1` logs no recall outcomes, and records no prompts or edits for the pre-compaction record (as for the recap) |
| `NEURALMIND_L3_ROLES` | on | `0` turns off the `query` ranking change and gives v4.10.0's ranking back |

## Not measured

- **The threshold comes from one repository**, 30 prompts and the default
  embedder. Another codebase, another embedding model, or a different style of
  prompting can put the boundary somewhere else; `--prompts` is there to check.
- **Answer quality.** We measured whether recall fires, and whether the block
  names the files that answer the prompt, not whether the agent answers better
  with it.
- **The file ranking comes from one tuning set.** Summed scores and tests after
  code were chosen on 14 Click prompts and checked on 15 held-out prompts about
  this repository. Test files are recognised by path (`tests/`, `test_*.py`,
  `*_test.go`, `*.test.ts` and similar), and a prompt counts as about tests
  when it says "test", "spec", "pytest" or "unittest".
- **Learned links were checked on a simulated graph.** Five scripted
  co-editing sessions on Click, not real use.
- **The compaction record's effect.** We haven't measured how often an agent
  repeats work or loses the original task after compaction, with or without the
  record. Whether Claude Code keeps the `session_id` across a compaction isn't
  documented either; if it doesn't, a compacted session gets no record rather
  than a guessed one.

## Upgrading

`pip install -U neuralmind`. The hook block is unchanged, so an existing
`neuralmind install-hooks` setup picks up all three changes. The recall
block's heading is unchanged, but its lines are now
`- <path>: <symbol> L<n>, …` instead of `- <node_id> (activation 0.05)`: a
script that parsed the old lines needs updating. If you rely on recall for
short follow-up prompts, set `NEURALMIND_RECALL_MIN_SIMILARITY=0` to keep
recall on for every prompt.
The `query` ranking change reads the index you have; restart a running
NeuralMind daemon or MCP server to pick it up.

## Related

- Use case: [Pick up where you left off](../use-cases/pick-up-where-you-left-off.md#after-compaction-v4110)
- Use case: [Hermes-Agent with code memory in every turn](../use-cases/hermes-agent.md)
- CLI reference: [`recap`](../wiki/CLI-Reference.md#recap-v480),
  [`install-hooks`](../wiki/CLI-Reference.md#install-hooks),
  [Environment Variables](../wiki/CLI-Reference.md#environment-variables)
- The `query` ranking change: [Code/document scoring](../use-cases/code-doc-scoring.md#tests-and-examples-are-not-the-code-v4110) ·
  [`NEURALMIND_L3_ROLES`](../wiki/CLI-Reference.md#environment-variables) ·
  raw output in [`bench/retrieval/roles-v4.11.0`](https://github.com/dfrostar/neuralmind/blob/main/bench/retrieval/README.md)
- Previous release: [v4.10.0](RELEASE_NOTES_v4.10.0.md) · [v4.9.2](RELEASE_NOTES_v4.9.2.md) · [v4.9.1](RELEASE_NOTES_v4.9.1.md)
