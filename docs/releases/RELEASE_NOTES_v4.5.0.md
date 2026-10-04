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
  avg context 1,180 tokens · 6.2× vs gold files · 1,101.3× vs all indexed files (1,299,512 tokens, measured)
```

- **hit@1, hit@5, MRR** rank the files the answer drew on by their best hit
  score — the same relevance sidecar `query --relevance` returns.
- **Two reductions:** vs the gold files (what a perfect retriever would load)
  and vs every indexed file (the measured baseline below).
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

- `build` measures the **token count of every file the graph covers** (the
  context-budget tokenizer) and caches it in `.neuralmind/baseline.json`.
- `benchmark`, `savings`, `cost` and `build --dry-run` all divide by it, and
  say so: `Baseline: measured: 1,117,552 tokens in 341 indexed files`. So do
  the per-query ratios `query`, `query --explain`, `wakeup` and the MCP tools
  print.
- `--naive-50k` on each of them keeps the old fixed estimate, labelled, for
  comparison with older numbers. `benchmark --contribute` keeps it too, so the
  community table's rows stay comparable with each other.
- `benchmark` uses the questions in `.neuralmind.eval.yaml` when there is one,
  instead of five generic ones.

**Expect different ratios.** On a large repo the measured baseline is far
bigger than 50K, so ratios go up; on a small one they go down. Neither is a
change in retrieval — it's the denominator becoming true.

### Stable probe sampling

`probe` now ranks symbols by a hash of `(seed, node id)` and keeps the lowest
`--sample-size`, instead of a seeded random draw over the current index. An
unchanged symbol stays in the sample across rebuilds (two runs either side of
a 5% index change share ≥ 90% of their sample), and `--baseline` compares only
the symbols both runs sampled, reporting how many were added or dropped.

## 5. Decision search answers questions

Decision search required every word of the query, so `neuralmind decisions query`
found a decision for "sqlite wal" but not for "how do we handle sqlite wal?",
and agents send questions.

- **Any word of the query can match.** Common words such as "how" and "the"
  are ignored, and decisions matching more of the words, and rarer ones, rank
  first. This covers `decisions query`, the `neuralmind_query_decisions` and
  `neuralmind_memory_search` MCP tools, and the LIKE fallback used when SQLite
  lacks FTS5. A question nothing answers can still return partial matches, so
  check the titles.
- **Status filters are case-insensitive**, and `ALL` returns every status
  (over MCP, the advertised `"all"` used to match nothing). The CLI's
  `--status` also accepts `INVALIDATED`. An unknown status is an error,
  `invalid_request` over MCP, instead of an empty result.
- **`neuralmind decisions eval` leaves your decisions alone.** It used to delete
  the project's `.neuralmind/memory.db` and leave synthetic decisions with the
  author `eval-harness` behind; it now runs on a scratch store. The
  [Memory Layer wiki](../wiki/Memory-Layer.md#eval-harness) shows how to retire
  any it left. `--format md` no longer crashes.
- **`neuralmind decisions eval --queries FILE`** scores search against
  questions with known answers: recall@k and MRR as mean and range per query
  kind, with every miss and false positive listed. The committed query set and
  its measured results are in the
  [Memory Layer wiki](../wiki/Memory-Layer.md#eval-harness).
- **MCP errors say what to do.** A missing index is `code: "index_not_built"`
  with a hint to call `neuralmind_build`, not `security_denied`;
  `security_denied` carries `reason: "rbac"` or `"rate_limit"`. See
  [Troubleshooting](../wiki/Troubleshooting.md).

## What the agent actually sees post-install

| Agent | Before | After |
|---|---|---|
| **Claude Code** (MCP + hooks) | Indexed gitignored copies; every query and hook taught the synapse layer, including eval scripts | Index covers what git covers; `learn: false` and `NEURALMIND_NO_LEARN=1` give read-only queries; hooks skip learning under the env switch |
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

## Related

- Use case: [Measure retrieval on your own repo](../use-cases/measure-retrieval-on-your-repo.md)
- CLI reference: [`eval`](../wiki/CLI-Reference.md#eval-v0140-project-eval-v450), [`query`](../wiki/CLI-Reference.md#query), [`benchmark`](../wiki/CLI-Reference.md#benchmark), [`probe`](../wiki/CLI-Reference.md#probe-v0270), [`decisions`](../wiki/CLI-Reference.md#decisions)
