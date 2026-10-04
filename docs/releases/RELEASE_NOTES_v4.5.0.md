# NeuralMind v4.5.0 — numbers you can trust, measured on your project

**Type:** Minor release | **Theme:** measurement

v4.4.0 made the index trustworthy. v4.5.0 makes the numbers NeuralMind prints
about a project mean something, and keeps them comparable from run to run:

1. **The index covers what git covers.** `.gitignore` is honoured by default.
2. **Measuring doesn't train.** Queries can be read-only, and every measurement
   command is.
3. **One eval, one baseline.** `neuralmind eval .` scores retrieval against gold
   answers you write for your repo, keeps a history, and every reduction ratio
   now divides by the measured size of your code instead of a fixed 50K guess.

It also stops a cost a new benchmark turned up: through v4.4.0, the Read, Bash
and Grep hooks sold as tool-output compression added tokens instead of saving
them (section 5).

## 1. `.gitignore` is honoured by default

On a real repository, gitignored `projects/` copies of `examples/` were indexed:
the same symbols ranked twice and pushed real hits out of the four-slot search
layer.

- Inside a git repo the file list comes from git itself
  (`git ls-files --cached --others --exclude-standard`), so nested
  `.gitignore` files, `.git/info/exclude` and your global excludes apply
  exactly as git applies them.
- **Tracked files that match an ignore rule are excluded too.** On that repo
  the copies had been force-added (`git add -f`), so a listing of what git
  *tracks* would still have included them. The ignore rule states the intent.
- Outside git, the top-level `.gitignore` is applied with the same pattern
  rules (`!` negation, `/` anchoring, `**`).
- **`.neuralmindignore` now uses gitignore semantics.** `docs/` matches a
  directory at any depth, `/docs/` only at the root, `!docs/keep.md`
  re-includes, and `src/*.py` no longer matches `src/deep/a.py`.
- A built-in graph drops nodes from files that are now excluded on the next
  build (the v4.4.0 orphan purge then removes their vectors).
- `build --dry-run` shows the effect before you build:
  `Excluded by .gitignore: ~300 nodes in 30 files (projects/ 30)`.
- The first build after upgrading says what changed, once:
  `Honoring .gitignore (new in v4.5.0): 30 files (projects/ 30) kept out of the index. …`

Opt out or widen it in `.neuralmind.yaml`:

```yaml
respect_gitignore: false          # index ignored files again (v4.4 behaviour)
include_ignored:                  # or pull specific ignored paths back in
  - "generated/api/**"
```

> Git can't re-include a file under an excluded *directory*. To ignore a
> directory except one file, write `projects/*` then `!projects/keep.py`, not
> `projects/` — NeuralMind follows git here, exactly.

## 2. Read-only queries

Every query normally reinforces the synapse layer. That is the point in daily
use, and exactly wrong for measurement: an eval run weekly would strengthen the
very edges it measures.

- `NeuralMind.query(..., learn=False)` / `search(..., learn=False)`, CLI
  `neuralmind query --no-learn`, MCP `learn: false` on `neuralmind_query` and
  `neuralmind_search`, and `NEURALMIND_NO_LEARN=1` for a whole process (CLI,
  MCP server and hooks).
- A read-only query **reads** the learned layer — synapse recall still shapes
  the result, so it gets exactly the context a normal query would — but
  reinforces nothing, writes no query logs, and opens the synapse database
  with SQLite's `mode=ro`, so even a bug can't write. It never builds: on a
  project with no index it says so instead.
- `benchmark`, `probe` and `eval` are read-only with no flag.
- The audit trail still records read-only queries (marked `"learn": false`),
  and `savings` no longer counts them as usage.

Verified: 100 read-only queries leave `synapses.db` and its WAL byte-identical,
and return the same context as a learning query on the same database.

## 3. `neuralmind eval .` — your questions, your gold files

Write the questions your team actually asks, with the file that answers each,
in `.neuralmind.eval.yaml` at the repo root, and commit it:

```yaml
- q: How are refunds issued when an order is cancelled?
  gold: [app/refunds.py]
```

```bash
neuralmind eval .                    # run it (read-only), append to the history
neuralmind eval . --report           # the history as a markdown table
neuralmind eval . --show-questions   # include each question, gold file and rank
neuralmind eval . --suggest --write  # draft 10 questions to edit
```

Example output (illustrative numbers):

```
NeuralMind eval — myrepo (10 questions, read-only)
  hit@1 40% · hit@5 60% · MRR 0.50
  avg context 1,180 tokens · 6.2× vs gold files · 1,101.3× vs all indexed code (1,299,512 tokens, measured)
```

- **hit@1, hit@5, MRR** rank the files the answer drew on by their best hit
  score — the same relevance sidecar `query --relevance` returns.
- **Two reductions:** vs the gold files (what a perfect retriever would load)
  and vs all the code the index covers (the measured baseline below).
- **History:** each run appends date, commit, NeuralMind version, node count
  and the metrics to `.neuralmind/eval_history.jsonl`. `--report` prints
  metrics and the question count only, so questions that name internal code
  stay out of pasted issues unless you pass `--show-questions`.
- The questions file is tracked (a shared team baseline); the history lives in
  the untracked `.neuralmind/` because it is machine-specific.
- `--suggest` drafts questions from module docstrings and README headings,
  with the defining file as gold — a starting point for a human to edit.
- The faithfulness and onboarding self-tests that `neuralmind eval` used to run
  are `neuralmind eval --suite faithfulness|onboarding`; `--onboarding`,
  `--selfcheck` and a bare `neuralmind eval` still run them.

## 4. One baseline everywhere

Before v4.5.0, on the same repo, `benchmark` divided by a fixed 50,000-token
guess (on a ~1.3M-token repo), `build --dry-run` used a lines × 25 estimate, and
`probe` resampled whenever the index changed: three commands, three
baselines, no two runs comparable.

- `build` measures the **token count of the code the graph covers** and
  caches it in `.neuralmind/baseline.json`:
  - **Code only.** Markdown, reStructuredText and plain text are left out
    whenever the index holds code — on `psf/requests` its `HISTORY.md`
    changelog alone was 15,088 tokens, 14% of an all-files count — so prose
    can't pad a ratio, and `build --dry-run` (which always counted code only)
    now agrees with `build`. An index with no code (a book, a docs corpus, a
    set of SQL, Protobuf or OpenAPI schemas) is measured over its documents.
  - **In the context's own units.** It is counted at the ~4 chars/token every
    context layer is counted in, so the ratio is a ratio of characters. With
    tiktoken installed it used to switch tokenizers and read `psf/requests`'
    code 8.5% lower than the context's units — one index, two ratios,
    depending on an optional package.
  - **Only inside the project.** A graph path that resolves outside it
    (`../`, an absolute path, a symlink out) is never opened, and images or
    PDFs a graphify graph names are never read as text.
- `benchmark`, `savings`, `cost` and `build --dry-run` all divide by it, and
  say so: `Baseline: measured: 94,069 tokens in 36 indexed code files` on
  `psf/requests` v2.32.3. So do the per-query ratios `query`,
  `query --explain`, `wakeup` and the MCP tools print. An index built before
  v4.5.0 has nothing cached; `benchmark` measures it on the spot (writing
  nothing) and the rest use the fixed estimate until the next `build`.
- `benchmark` prints the old ratio beside the new one —
  `Legacy reduction: 41.8x (vs the fixed 50K-token estimate used before v4.5.0)` —
  and `--json` carries both: `full_codebase_tokens` (the measured code) and
  `legacy_avg_reduction_ratio` against `estimated_full_codebase_tokens`
  (always 50,000).
- `--naive-50k` on each of them keeps the old fixed estimate, labelled, for
  comparison with older numbers.
- `benchmark --contribute` writes a **v2** community entry: `avg_reduction_ratio`
  stays on the fixed estimate every row of the table compares on, and
  `measured_avg_reduction_ratio` + `full_codebase_tokens` add the ratio against
  your code. Its `verification_command` now carries `--naive-50k`, so a
  reviewer re-running it gets the submitted number; and it fills `nodes` and
  whole-number `avg_query_tokens`, without which no entry it printed had
  passed the schema.
- `benchmark` uses the questions in `.neuralmind.eval.yaml` when there is one,
  instead of five generic ones.

**Expect different ratios.** On a large repo the measured baseline is far
bigger than 50K, so ratios go up; on a small one they go down. Neither is a
change in retrieval — it's the numerator becoming true. On `psf/requests`
v2.32.3 the same five questions read 41.8× against the fixed estimate and
78.6× against the 94,069 tokens of code the index covers.

### Stable probe sampling

`probe` now ranks symbols by a hash of `(seed, node id)` and keeps the lowest
`--sample-size`, instead of a seeded random draw over the current index. An
unchanged symbol stays in the sample across rebuilds (two runs either side of
a 5% index change share ≥ 90% of their sample), and `--baseline` compares only
the symbols both runs sampled, reporting how many were added or dropped.

## 5. The Read, Bash and Grep hooks stop adding tokens

The Read, Bash and Grep PostToolUse hooks were described as compressing tool
output "before the agent sees it". A new benchmark that follows Claude Code's
documented hook protocol shows they never did: Claude Code **adds** a hook's
`additionalContext` next to the tool result rather than replacing it, so Claude
got the full output *plus* NeuralMind's compressed copy.

| Tool call | Calls | Tokens, no hook | Tokens, v4.3.4 hooks | Change |
|---|---:|---:|---:|---:|
| Read (whole file) | 136 | 597,002 | 597,002 | +0.0% |
| Bash | 16 | 32,581 | 38,296 | +17.5% |
| Grep, content mode | 48 | 55,800 | 68,113 | +22.1% |
| Grep, files_with_matches (default) | 48 | 2,062 | 2,062 | +0.0% |

Measured on v4.3.4; v4.3.5 and v4.4.0 shipped the same hooks.

- **Bash:** every successful command got a second copy. It was the whole output
  again when nothing was compressed (`pip list`, a short `pytest -q`: +100%), and
  errors plus the tail when it was.
- **Read:** the hook never fired. Claude Code's Read payload nests the text
  under `file.content`, which the hook didn't read.
- **Failed commands** fire `PostToolUseFailure`, not `PostToolUse`, so the Bash
  hook never saw a failing test run, lint error or crash. Those are the outputs
  its "errors + summary" design was built for.

Method, per-command results and raw data:
[docs/benchmarks/compression.md](../benchmarks/compression.md) ·
`bench/compression/results-v4.3.4.json`.

### What changed

- `neuralmind _hook compress-read`, `compress-bash`, `cap-search` and `offload`
  return nothing. Claude sees exactly the tool result.
- The Bash hook still writes the latest successful command's output,
  credentials redacted, to `.neuralmind/last_output.json`, so `neuralmind last`
  works as before. A failing command fires `PostToolUseFailure`, so its output
  never reached this hook, then or now.
- Every other hook is unchanged: session memory (SessionStart), prompt-time
  recall (UserPromptSubmit), the stale-decision guard (PreToolUse), reuse
  feedback (PostToolUse on Edit/Write), and the session digest (Stop,
  SessionEnd).

### Not changed

- The compressor functions (`compress_bash`, `compress_read`,
  `cap_search_results`, `offload_if_large`) stay in the Python API. The
  benchmark measures them too: they would cut 66–87% of tokens if they replaced
  a result, but keep 0% of a file's source lines and 0% of a diff's changed
  lines. That is why nothing replaces tool output until a design keeps what the
  agent needs, measured by the same benchmark.
- `NEURALMIND_BASH_TAIL`, `NEURALMIND_BASH_MAX_CHARS` and `NEURALMIND_BASH_SMALL`
  now only tune those Python functions. `NEURALMIND_BYPASS=1` still switches off
  every NeuralMind hook action.

### New in the repo

- `evals/compression/`: the benchmark. It drives the real hook with payloads
  shaped like Claude Code's (Agent SDK `sdk-tools.d.ts`) and applies each
  response per the documented protocol. The Bash corpus is 16 real command
  outputs with pre-registered must-keep lines.
- `tests/test_compression_benchmark.py`: recomputes the Bash results on every
  CI run and fails if the hooks stop doing what `bench/compression/results.json`
  records, or if the benchmark page stops quoting it.
- Docs, README, site and `llms.txt` no longer describe tool-output compression
  as a feature.

## What the agent actually sees post-install

| Agent | Before | After |
|---|---|---|
| **Claude Code** (MCP + hooks) | Indexed gitignored copies; every query and hook taught the synapse layer, including eval scripts; Bash and content-mode Grep results were followed by a system reminder holding NeuralMind's copy of the same output | Index covers what git covers; `learn: false` and `NEURALMIND_NO_LEARN=1` give read-only queries; hooks skip learning under the env switch; the Read/Bash/Grep hooks add nothing to a tool result |
| **Cursor / Cline / Continue** (MCP) | Same indexing; no way to query without training | Same indexing fix; `learn: false` on `neuralmind_query` / `neuralmind_search` |
| **Generic MCP client** | `neuralmind_query` always wrote | Read-only on request; the tool schema documents `learn` |
| **CI** | `benchmark` numbers against a fixed 50K; evals trained on themselves | `neuralmind eval .` read-only with history; `NEURALMIND_NO_LEARN=1` for the whole job |

## Upgrade notes

- **Results change for repos with gitignored code.** The first build prints
  what was excluded. To keep v4.4 behaviour: `respect_gitignore: false`.
- **`.neuralmindignore` semantics tightened** to gitignore's: a pattern with a
  `/` in the middle is anchored to the root, and `*` no longer crosses
  directories. Most files mean the same thing; check any `src/*.py`-style line.
- **Reduction ratios change** as described above. `--naive-50k` reproduces the
  old numbers.
- **`neuralmind eval <path>`** now runs the project eval; the old suites are
  under `--suite`.
- **The hook change needs no reinstall.** The registered hooks are the same;
  they just stop returning context. `neuralmind last` works as before.

## Related

- Use case: [Measure retrieval on your own repo](../use-cases/measure-retrieval-on-your-repo.md)
- Benchmark: [Tool-output compression](../benchmarks/compression.md)
- CLI reference: [`eval`](../wiki/CLI-Reference.md#eval-v0140-project-eval-v450), [`query`](../wiki/CLI-Reference.md#query), [`benchmark`](../wiki/CLI-Reference.md#benchmark), [`probe`](../wiki/CLI-Reference.md#probe-v0270)
