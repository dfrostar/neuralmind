# NeuralMind v4.10.0 — Hermes can install the NeuralMind plugin itself, and the plugin says why when it can't work

**Type:** Minor release | **Theme:** Hermes-Agent plugin, ready for Hermes's own installer

v4.9.0 gave Hermes-Agent [NeuralMind's context in every turn](RELEASE_NOTES_v4.9.0.md)
through a plugin, installed with `neuralmind install-hermes-plugin`. Three things
stood between that plugin and a Hermes user finding and installing it the
Hermes way:

- **Only NeuralMind's command could install it.** Its manifest was generated
  at install, so a clone of its directory wasn't a plugin Hermes could load.
- **It went quiet when it couldn't work.** Without a NeuralMind it could run,
  or with one too old to give the recap, turns simply got no context, or no
  recap, and nothing said why.
- **Uninstalling, then installing again, left it off.** `--uninstall`
  disabled the plugin before removing it, which left it on Hermes's
  `plugins.disabled` list, and the next install respected that.

v4.10.0 fixes all three.

## Hermes can install it

The plugin's directory, `neuralmind/hermes_plugin/`, now carries its own
`plugin.yaml` and a [README](https://github.com/dfrostar/neuralmind/blob/main/neuralmind/hermes_plugin/README.md),
so Hermes's own installer can install it from a clone of this repository:

```bash
pip install -U neuralmind                       # the plugin runs NeuralMind; it doesn't bundle it
neuralmind build /path/to/project
hermes plugins install dfrostar/neuralmind#neuralmind/hermes_plugin --enable
```

- **Hermes owns the code.** `hermes plugins update neuralmind` updates it.
- **It runs the `neuralmind` command on Hermes's PATH.** It looks only in
  absolute PATH entries, never the working directory, so a repository you work
  in can't supply its own `neuralmind`. Where Hermes's PATH doesn't include it
  (a gateway run as a service, Hermes Desktop), also run
  `neuralmind install-hermes-plugin`: on a plugin Hermes installed, it writes
  only the interpreter and the project to the plugin's `config.json`, and
  leaves the code alone. If Hermes's install records
  (`plugins/.install-metadata.json`) can't be read, it leaves the code alone
  too, and says so.
- **The manifest declares `requires_hermes: ">=0.21.5"`**, the version it's
  tested with, so an older Hermes skips it.
- **The README lists what the plugin does on your machine**: the subprocess it
  runs, what it reads and writes in the project's `.neuralmind/`, what it
  copies into Claude Code's memory directory, its network use, and what
  reaches your model provider.
- **Hermes's catalog check passes.** `hermes plugins validate` on the
  directory passes every check, the install security scan included.

`neuralmind install-hermes-plugin` works as before and stays the simplest way
in: it copies the plugin, records the Python interpreter that has NeuralMind,
and enables it.

## It says why when it can't work

When the plugin can't start NeuralMind, finds one older than 4.9, or a call
times out, it logs one warning per Hermes process, naming the fix:

```bash
hermes logs --level WARNING | grep -i neuralmind
# WARNING hermes_plugins.neuralmind: NeuralMind plugin: /home/you/.local/bin/neuralmind is
#   NeuralMind 4.3.5, too old for this plugin: turns get no session recap. Install NeuralMind
#   4.9 or later so the `neuralmind` command is on Hermes's PATH, or run
#   `neuralmind install-hermes-plugin` to point the plugin at it.
```

An older NeuralMind still answers, so before this the only sign was a missing
recap. The version check runs once per Hermes process, in the background, off
the turn's path. As before, nothing breaks the turn: it goes ahead without
NeuralMind's context.

## Fixed: a reinstall after an uninstall stays on

`neuralmind install-hermes-plugin --uninstall` now runs Hermes's own
`hermes plugins remove neuralmind`, which removes the directory and every entry
naming the plugin in that home's `config.yaml`, so installing it again later
turns it back on. A fresh install also enables the plugin whatever an earlier
one left on the disabled list; only a re-run over an existing install respects
a `hermes plugins disable neuralmind` you ran. Hermes won't remove a symlinked
`plugins/neuralmind`, so for one the command still disables the plugin and
removes the link, never what it points to. If `hermes plugins remove` fails,
even after it has already deleted the directory, the command disables the
plugin instead and says Hermes's config may still name it.

The install's last line also stopped saying "Each Hermes turn now gets
NeuralMind's related files…" when the plugin wasn't enabled (left disabled,
`--no-enable`, Hermes not set up yet, or `hermes` not on PATH). It now reads
"Once it's enabled, each Hermes turn gets …" in those cases.

## What the agent sees

Nothing new in a turn: the same recap and recall v4.9.0 added, appended to the
user message. What changes is that more installs actually deliver it, and when
one doesn't, Hermes's log says why. Tested against Hermes v0.21.5 (a
0.21.5+5355 main-branch build) in live `hermes chat` sessions: the first-turn
recap, recall, edits made with `patch` and `write_file`, a resumed session
(recall only), a subagent (skipped), a directory that hasn't been built
(nothing), both ways of installing, and uninstalling. What the context changes
in Hermes's answers still isn't measured.

## Per-agent expectations

| Agent | What changes |
|---|---|
| **Hermes-Agent** | It can install the plugin itself (`hermes plugins install dfrostar/neuralmind#neuralmind/hermes_plugin`), and update it with `hermes plugins update neuralmind`. When the plugin can't run NeuralMind, finds an old one, or times out, Hermes's log says so. Uninstalling and installing again leaves it enabled. |
| **Claude Code** | Nothing. |
| **Cursor / Cline / generic MCP clients** | Nothing. |
| **Other agents with a shell** | Nothing. |

## Use cases

- **Existing:** [Hermes-Agent with code memory in every turn](../use-cases/hermes-agent.md).
  The install step gains the Hermes-native route, and the limits section says
  where to look when turns get no context.
- **Potential:** a Hermes user who manages everything through
  `hermes plugins` can now add NeuralMind the same way as any other plugin,
  and keep it updated with the rest. Listing it in Hermes's curated plugin
  catalog, so `hermes plugins install neuralmind` finds it by name, is the
  next step; it takes a pull request to Hermes pinned to this release.

## Settings

No new settings for the plugin. `NEURALMIND_PROJECT` and `NEURALMIND_HERMES_TIMEOUT` work as
in v4.9.0, and a timeout is now logged.

## Upgrading

`pip install -U neuralmind`, then re-run `neuralmind install-hermes-plugin`:
the plugin it installed is a copy, and a re-run keeps an earlier pin and leaves
a plugin you disabled disabled. A plugin Hermes installed is updated with
`hermes plugins update neuralmind` instead.

## Related

- Plugin README: [neuralmind/hermes_plugin/README.md](https://github.com/dfrostar/neuralmind/blob/main/neuralmind/hermes_plugin/README.md)
- Use case: [Hermes-Agent with code memory in every turn](../use-cases/hermes-agent.md)
- Integration guide: [Hermes-Agent](../wiki/Integration-Guide.md#hermes-agent)
- CLI reference: [`install-hermes-plugin`](../wiki/CLI-Reference.md#install-hermes-plugin-v490)
- Previous release: [v4.9.1](RELEASE_NOTES_v4.9.1.md) · [v4.9.0](RELEASE_NOTES_v4.9.0.md)

---

## Also in v4.10.0: `query` finds the project's code, not its tests, examples and docs

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

`query` now tells a hit's role apart, by layout: the project's own code; a
test or example (a `test`, `tests`, `spec`, `__tests__`, `example(s)`,
`demo(s)` or `sample(s)` directory, or a test file's name: `test_*.py`,
`*_test.go`, `*.test.ts`, `*.spec.js`, `conftest.py`); or a doc.

- **The project's code is owed L3 slots.** When fewer than two of the four
  hits are the project's code (one, for a question classified `docs`) and
  ranks 5–10 of the same search hold some, the weakest test, example or doc
  hits give their slots to it, a file not yet shown first. It swaps hits and
  never adds one, so the answer's size doesn't grow.
- **Tests and examples count a third** when ranking, under every intent,
  unless the question names them ("how do I test …", "an example of …").
  Under `code` intent they are scored like docs, which are about the code,
  instead of getting the code's ×3 and identifier boosts. Docs count a third
  under `code` intent too, so a docstring of the code ranks above a doc heading.
- **L2 lists a cluster's own code first**, and test and example hits count a
  third toward a cluster's relevance.
- **`--trace` shows the swap:** `[L3/roles] 2 slot(s) from tests/examples/docs
  to the project's code`.
- **`NEURALMIND_L3_ROLES=0`** turns it all off and gives v4.9's ranking back.

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
same build with `NEURALMIND_L3_ROLES=0`, which ranks as v4.9 did; every run is
read-only. hit@5 / MRR, from the scorer `neuralmind eval` uses:

| Question set | Index | Before | After | Tokens |
|---|---|---:|---:|---:|
| 14 Click questions, **the set this was tuned on** | `click` @ `2247b35`, whole repository | 64% / 0.49 | **100% / 0.80** | +1.8% |
| 30 pre-registered questions per repo, **held out** ([`bench/retrieval/roles-v4.10/full-repo`](https://github.com/dfrostar/neuralmind/blob/main/bench/retrieval/roles-v4.10/full-repo/report.md)) | `requests`, `click`, `flask`, `rich` at the public benchmark's commits, whole repository | 77.5% / 0.615 | **79.2% / 0.672** | +1.6% |
| the same 30, this repository, **held out** ([`bench/retrieval/roles-v4.10/source-dir`](https://github.com/dfrostar/neuralmind/blob/main/bench/retrieval/roles-v4.10/source-dir/report.md)) | `neuralmind`, docs indexed | 57% / 0.45 | **70% / 0.55** | +1.8% |
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
  their ranks.
  On 15 more prompts about this repository, from #607's held-out set, an
  answering file is in the results for 11, up from 6.
- **Source directories: no change, by construction.** The four libraries'
  source directories hold only the library's code, so there is nothing to swap
  or weigh: per question, every rank and token count is the same. The public
  benchmark indexes the same directories: run on one machine, this release's
  code and v4.9's produce byte-identical `results.json` files, so the
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
question got worse, in any repository; `NEURALMIND_L3_ROLES=0` restores v4.9.

### Per-agent expectations for the ranking change

| Agent | What changes |
|---|---|
| **Any MCP client** (Claude Code, Cursor, Cline, Codex, Hermes …) | `neuralmind_query` returns the project's code ahead of its tests, examples and docs on an index built from the repository root. |
| **CLI and scripts** | `neuralmind query`, `neuralmind eval` and `neuralmind benchmark` rank the same way, so `eval`'s hit@5 on a whole repository can rise after upgrading. |
| **Claude Code hooks, the Hermes plugin** | Nothing: prompt-time recall, the session recap and the wake-up context don't use L3. |

### Use cases for the ranking change

- **Existing:** [A/B-test a ranking change on your own repo](../use-cases/ab-test-a-ranking-change.md):
  `NEURALMIND_L3_ROLES=0 neuralmind eval . --no-history` measures what this
  change did on your questions, and the multi-repo harness gained
  `--full-repo`, which indexes each public repository from its root.
- **Potential:** asking "which files handle X?" of a whole repository, not
  just its library directory, and getting the files to open. Before, that
  question was where tests and examples won.

### The setting

`NEURALMIND_L3_ROLES` (on by default; `0` turns the roles pass off). Nothing to
rebuild: it reads the index you have.
