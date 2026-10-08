# NeuralMind v4.11.1 — No turbovec store on a ChromaDB project

**Type:** Patch release | **Themes:** Two turbovec checks that ran on every backend · `query` ranking: [the project's code before its tests, examples and docs](#query-finds-the-projects-code-not-its-tests-examples-and-docs)

`neuralmind build` and `neuralmind doctor` each check whether the turbovec
index was quarantined, which happens when the installed turbovec can't read
it. Both checks opened the turbovec store to do it, whatever backend the
project uses, and opening it creates the file. So on a project with ChromaDB
pinned, every build left an empty `.neuralmind/neuralmind_turbovec/store.sqlite`
next to the real index in `.neuralmind/neuralmind_db/`, and `doctor` called
that empty store "Index version compatible". Both checks now run only when
the project's backend is turbovec.

---

## What changed

### CLI

- **`neuralmind build` skips the turbovec check on other backends.** When
  `neuralmind-backend.yaml` sets `backend: graph`, `chroma`, `chromadb` or
  `in_memory`, the build no longer creates
  `.neuralmind/neuralmind_turbovec/store.sqlite`. If the project has never
  used turbovec, the `neuralmind_turbovec/` directory an earlier build left
  behind holds no vectors, and you can delete it.
- **`neuralmind doctor` says the check doesn't apply.** On those backends the
  *Turbovec compatibility* line reads
  `not applicable: the chroma backend keeps no turbovec index` (naming the
  configured backend), with status `ok`, instead of reporting an index that
  doesn't exist as compatible.
- **Turbovec projects are checked as before.** With no backend configured,
  or with `backend: turbovec`, `turboquant` or `auto`, a quarantined
  `index.tvim.stale` still makes `build` print its warning before embedding
  and makes `doctor` fail the check.

Both checks resolve the backend the same way `neuralmind build` does: the
`backend:` in `neuralmind-backend.yaml`, where `auto`, an empty value or no
file all mean turbovec.

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
- **`NEURALMIND_L3_ROLES=0`** turns it all off and gives v4.11.0's ranking back.

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
same build with `NEURALMIND_L3_ROLES=0`, which ranks as v4.11.0 did; every
run is read-only. hit@5 / MRR, from the scorer `neuralmind eval` uses:

| Question set | Index | Before | After | Tokens |
|---|---|---:|---:|---:|
| 14 Click questions, **the set this was tuned on** ([`bench/retrieval/roles-v4.11.1/click-2247b35.md`](https://github.com/dfrostar/neuralmind/blob/main/bench/retrieval/roles-v4.11.1/click-2247b35.md)) | `click` @ `2247b35`, whole repository | 64% / 0.49 | **100% / 0.80** | +1.8% |
| 30 pre-registered questions per repo, **held out** ([`bench/retrieval/roles-v4.11.1/full-repo`](https://github.com/dfrostar/neuralmind/blob/main/bench/retrieval/roles-v4.11.1/full-repo/report.md)) | `requests`, `click`, `flask`, `rich` at the public benchmark's commits, whole repository | 77.5% / 0.615 | **79.2% / 0.672** | +1.6% |
| the same 30, this repository, **held out** ([`bench/retrieval/roles-v4.11.1/source-dir`](https://github.com/dfrostar/neuralmind/blob/main/bench/retrieval/roles-v4.11.1/source-dir/report.md)) | `neuralmind`, docs indexed | 57% / 0.45 | **70% / 0.55** | +1.8% |
| the same 30 per repo | `requests`, `click`, `flask`, `rich`, source directory only | identical | identical | identical |
| the public benchmark, 40 queries | source directory only | — | **`results.json` byte-identical, on vs off** | identical |

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
  code produces byte-identical `results.json` files with the roles pass on and
  with `NEURALMIND_L3_ROLES=0`, and both match the committed
  `bench/public/results.json` byte for byte, so the published figures stand.

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
question got worse, in any repository; `NEURALMIND_L3_ROLES=0` restores v4.11.0.

### Use cases for the ranking change

- **Existing:** [A/B-test a ranking change on your own repo](../use-cases/ab-test-a-ranking-change.md):
  `NEURALMIND_L3_ROLES=0 neuralmind eval . --no-history` measures what this
  change did on your questions, and the multi-repo harness gained
  `--full-repo`, which indexes each public repository from its root.
- **Potential:** asking "which files handle X?" of a whole repository, not
  just its library directory, and getting the files to open. Before, that
  question was where tests and examples won.

## What the agent actually sees post-install

| Agent | Before | After |
|-------|--------|-------|
| **Claude Code** (MCP + hooks) | No change | Same |
| **Cursor / Cline / Claude Desktop** (MCP) | No MCP tool changed | Same |
| **Generic MCP client** | No MCP tool changed | Same |
| **Agents that run the CLI** (Hermes skill, scripts) | On a ChromaDB or in-memory project, `doctor --json` reported `"Turbovec compatibility"` as `ok` with `"Index version compatible"`, and `build` created an empty turbovec store | The same check is `ok` with `"not applicable: the <backend> backend keeps no turbovec index"`, and `build` creates no turbovec store |
| **Every agent, through `query`** (`neuralmind_query`, `neuralmind query`, `eval`, `benchmark`) | Tests, examples and docs could take all four search results on an index built from the repository root | The project's code comes first; `eval`'s hit@5 on a whole repository can rise. Hooks don't use L3, so they're unchanged |

An agent that gates on `doctor --json`'s `status` sees no difference: the
check was `ok` before and is `ok` now. Only its `detail` text changed.

## Environment variables

`NEURALMIND_L3_ROLES` (added, on by default): `0` turns off the `query` ranking
change and gives v4.11.0's ranking back. Nothing else added or changed.

## Upgrade notes

None. No stored data changes shape, and no command takes new arguments. The
`query` ranking change reads the index you have; restart a running NeuralMind
daemon or MCP server to pick it up.

## Related

- [CLI reference: doctor](../wiki/CLI-Reference.md#doctor-v0120)
- The `query` ranking change: [Code/document scoring](../use-cases/code-doc-scoring.md#tests-and-examples-are-not-the-code-v4111) ·
  [`NEURALMIND_L3_ROLES`](../wiki/CLI-Reference.md#environment-variables) ·
  raw output in [`bench/retrieval/roles-v4.11.1`](https://github.com/dfrostar/neuralmind/blob/main/bench/retrieval/README.md)
- [v4.11.0 release notes](RELEASE_NOTES_v4.11.0.md)
