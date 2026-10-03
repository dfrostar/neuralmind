# NeuralMind v4.6.0 — one keyword index for docs and code, measured before it shipped

**Type:** Minor release | **Theme:** retrieval ranking, measured

v4.5.0 gave every project a way to measure retrieval on its own questions.
v4.6.0 pointed that measurement at NeuralMind's own ranking: six candidate
changes to how the four L3 search slots are spent, 30 questions on each of six
repositories — pre-registered and committed for the five public repositories,
plus a private 383-file repository — and a keep rule written down before the
first run. One change passed it.

1. **One BM25 index for docs and code, on by default.** Mean hit@5 across the
   six repositories went from **72.8% to 79.4%** (MRR 0.589 → 0.654).
2. **The public 4-repo benchmark's gold-file recall went from 93.75% to 95%**,
   at 46–263× fewer tokens than pasting every source file.
3. **Five more ranking changes (six flags — the intent pool is a variant of
   the intent rules) were measured and not kept.** They ship off by default,
   behind flags, with the numbers that sank them.

**Evidence:** reproducible on demand, not a CI gate. The raw output is
committed in [`bench/retrieval/`](https://github.com/dfrostar/neuralmind/blob/main/bench/retrieval/README.md);
`pip install -e . tiktoken`, then
`NEURALMIND_ORT_THREADS=1 python -m evals.retrieval.run --public-benchmark`
re-runs it. The question sets for the five public repositories are
pre-registered and committed; the private 383-file repository uses its own
local question set, which readers can't re-run. On the five public
repositories alone, mean hit@5 went from 75.3% to 80.7% (MRR 0.614 → 0.664).

Run `neuralmind build` once after upgrading: the build writes the new index,
and a query never builds anything.

## 1. One BM25 index for docs and code

L3 fuses vector search with a BM25 keyword list by Reciprocal Rank Fusion. On
the default turbovec backend, that keyword index held only **document** nodes.
A question whose words appeared in a README or a wiki page gave the docs a
second signal that code never got — so on "how does X work" questions a doc
kept taking a slot the implementation should have had.

- `neuralmind build` now writes `.neuralmind/bm25_unified_index.json`: every
  node — doc text, symbol names, file paths, docstrings — in one BM25 index.
  Queries fuse that instead of the docs-only list.
- The ChromaDB backend's BM25 index already covered every node; the unified
  index makes both backends behave the same.
- **Cost:** one BM25 lookup per query, and 1.1% more context tokens on
  average across the six repositories.
- **Opt out:** `NEURALMIND_BM25_UNIFIED=0` restores v4.5.0's docs-only keyword
  list.

Against v4.5.0 — hit@5 / MRR, 30 questions per repository
([`bench/retrieval/vs-v4.5`](https://github.com/dfrostar/neuralmind/blob/main/bench/retrieval/vs-v4.5/report.md)):

| Repository | v4.5.0 | v4.6.0 (unified BM25) |
|---|---:|---:|
| `requests` | 90% / 0.76 | 87% / 0.75 |
| `click` | 93% / 0.69 | 93% / 0.79 |
| `flask` | 73% / 0.63 | 83% / 0.71 |
| `rich` | 80% / 0.71 | 80% / 0.60 |
| `neuralmind` (this repository, docs indexed) | 40% / 0.27 | 60% / 0.47 |
| a private 383-file repository | 60% / 0.47 | 73% / 0.60 |
| **mean** | **72.8% / 0.589** | **79.4% / 0.654** |

### The losses, published

- **`requests` loses one question** (hit@5 90% → 87%). The keep rule says no
  repository drops by more than one question; it is still a drop.
- **`rich`'s MRR falls from 0.71 to 0.60.** Its hit@5 holds at 80%, but the
  gold file ranks lower.
- **`click` has a new public-benchmark miss.** `echo-util` (gold `utils.py`)
  now retrieves `termui.py` and `core.py`, and `click` fell from 100% to
  85.71% on the public benchmark. The benchmark's total still rose, from
  93.75% to 95%.
- **The private repository's target is not met.** The work started from its
  60% hit@5; the target was hit@5 ≥ 80% and MRR ≥ 0.65. v4.6.0 reaches
  73% / 0.60.

## 2. `query --explain` says which intent L3 ranked with

L3 re-weights its hits by query intent — a `docs` question multiplies doc hits
by 2.0 and code hits by 0.7 — and nothing showed which intent a query got.
`--explain` now prints it, and how it was decided:

```
  Query intent     : docs (by classifier)
```

- `classifier` — the v3.9.0 pattern classifier decided.
- `keywords` — the classifier called the question `hybrid`, so the older
  keyword count decided.
- `question shape` — the opt-in intent rules (`NEURALMIND_INTENT_RULES=1`)
  matched, e.g. `code (by question shape)`.

The `Top search hits` list now shows each hit's label and file; it printed raw
node ids before.

## 3. How the decision was made — `python -m evals.retrieval.run`

A multi-repo retrieval eval ships in the source tree, with its raw output
committed in [`bench/retrieval/`](https://github.com/dfrostar/neuralmind/blob/main/bench/retrieval/README.md).

- **Pre-registered questions.** 30 per repository for `requests`, `click`,
  `flask` and `rich` (at the public benchmark's pinned commits) and for this
  repository, committed in `evals/retrieval/questions/` before any ranking
  change was tried. A sixth repository — a private 383-file repository — came
  in through `--private PATH` and is reported only in aggregate: no
  per-question ranks, no question text.
- **The keep rule**, fixed before the runs:
  - mean hit@5 across repositories goes up, and it goes up on at least 3;
  - no repository drops by more than one question;
  - average context tokens rise by at most 10%;
  - the public 4-repo benchmark's gold-file recall doesn't drop.
- **Read-only, one scorer.** Every flag configuration runs through the same
  scorer as `neuralmind eval`, so the harness's hit@5 on a repository is the
  number `neuralmind eval .` prints there (for this repository, with its docs
  indexed — the harness overrides its `.neuralmindignore`).
- **Three rounds.** Round 1 measured the five work items against v4.5.0, with
  BM25 switched off as a reference. Round 2 tried three variants designed after
  seeing round 1 — the unified index among them; the public benchmark's 40
  queries, written long before, are the holdout that keeps that honest. Round 3
  re-ran every remaining item on top of the new default
  ([`bench/retrieval/on-v4.6`](https://github.com/dfrostar/neuralmind/blob/main/bench/retrieval/on-v4.6/report.md)).
- **Contamination, found and fixed.** The public benchmark queries with
  learning on, and it was running against the same pinned clones the eval
  used: its queries trained the eval's indexes, and the flags-off baseline
  moved between runs. Now every run builds fresh indexes, each public-benchmark
  run gets its own fresh copy of the clones, and the baseline runs again after
  every configuration — the report says whether it reproduced. In both
  committed runs it reproduced exactly on all six repositories.

## 4. Measured and not kept

Each stays available behind its flag, off by default:

| Flag | What it does | Why it wasn't kept |
|---|---|---|
| `NEURALMIND_L3_PER_FILE=2` | at most N L3 hits per file | +1.1 pts mean hit@5, 2 repos up, none down on hit@5, but mean MRR fell 0.654 → 0.629 (`requests` 0.75 → 0.69, `flask` 0.71 → 0.65); public recall 96.25% — the rule needs 3 repos |
| `NEURALMIND_DOC_HANDOFF=1` | a doc hit that names code pulls that code in | helps only where docs name code (private +3, `neuralmind` +1 question vs v4.5.0); a wash on top of v4.6.0 |
| `NEURALMIND_HUB_DAMPEN=1` | down-weights files returned far more often than chance | cost `click` 3–4 questions |
| `NEURALMIND_INTENT_RULES=1` | "how does X… / where is X… / which X is…" → code intent | moves MRR (0.654 → 0.672), never hit@5: it only re-orders the 4 hits L3 already chose |
| `NEURALMIND_INTENT_POOL=1` (with `NEURALMIND_INTENT_RULES=1`) | intent ranks all 10 candidates | `click` −8 questions, public recall 83.75% (vs v4.5.0) |
| `NEURALMIND_BM25_CODE=1` | a separate code-only keyword list | `requests` −3 (vs v4.5.0); `rich` −4, `click` −3 (on v4.6.0) |

One finding is worth keeping even though its fix wasn't. The intent
classifier — still the default, since the intent rules weren't kept — sends
many "how does X…" and "where is X…" behaviour questions to **docs** intent,
which multiplies doc hits ×2.0 and code ×0.7. Four such shapes are now
regression tests that the intent rules must send to code
([`tests/test_l3_slots_v460.py`](https://github.com/dfrostar/neuralmind/blob/main/tests/test_l3_slots_v460.py)): "How does
the session pick which adapter sends a request?", "Where is the redirect
followed after a POST?", "Which hook runs before a request is sent?" and "How
does the cache avoid storing the same response twice?". Sending questions like
these to code intent instead only re-orders the four hits L3 already chose,
which is why the intent rules moved MRR and never hit@5.

## 5. The public benchmark, regenerated

[`bench/public/results.json`](https://github.com/dfrostar/neuralmind/blob/main/bench/public/results.json) was regenerated
on v4.6.0 (tiktoken o200k_base; reproduce with
`NEURALMIND_ORT_THREADS=1 python -m evals.public.run`):

- **95% gold-file recall**, the query-weighted mean over all 40 queries (was
  93.75%), **85.71–100% per repo** (was 85–100%):
  `click` 85.71%, `flask` 95%, `requests` 96.43%, `rich` 100%.
- **92.5% found-rate** — 37 of 40 (was 90%).
- **3 misses of 40** (was 4): `requests` `xfile-status-codes` (partial),
  `click` `echo-util` (new), `flask` `xfile-dispatch-context` (partial).
- **46–263× fewer tokens** than pasting every source file (was 45–261×):
  `requests` 46.6×, `flask` 78×, `click` 121.7×, `rich` 262.1×.
- **`embedding-rag` still leads on recall**, at 98.75% mean. NeuralMind trails
  a bare vector-RAG baseline on findability, as it did before.

## What the agent actually sees post-install

- **Code can now win an L3 slot on keywords too**, not only on vector
  similarity — across the eval's six repos mean hit@5 rose 72.8% → 79.4%,
  though `requests` lost a question and `rich`'s gold files rank lower. The
  default intent classifier still treats many "how does X…" questions as docs
  questions; `query --explain` shows which it chose.
- **Learned recall only takes a slot for a file the hits don't already show.**
  Synapse recall swaps the weakest L3 hits for nodes your team co-edits. With
  the stronger keyword ranking, those swaps started trading the only hit from a
  second relevant file for more of the first, and the CI onboarding gate's lift
  went negative: −0.009 on the fixture, where v4.5.0 measured +0.046. Recall now
  skips neighbours from files already in the hits; the gate measures +0.046
  again, and faithfulness on the same fixture moves from −0.001 to +0.027.
- **`neuralmind query --explain` shows the intent** the query was ranked with,
  and why.
- **Nothing changes until `neuralmind build` runs once.** An index built before
  v4.6.0 keeps the docs-only keyword list.

| Agent | Before (v4.5.0) | After (v4.6.0) |
|---|---|---|
| **Claude Code** (MCP + hooks) | `neuralmind_query` ranked L3 with a keyword list only docs were in | Same tool and the same four slots, ranked with one keyword index over docs and code after the next build; hooks unchanged |
| **Cursor** (MCP) | Same as Claude Code | Same change through `neuralmind_query`; `neuralmind_search` (plain vector search) is unchanged |
| **Cline / Continue** (MCP) | Same as Claude Code | Same as Cursor |
| **Generic MCP client** | — | No schema change: same tools, same arguments, re-ranked L3 hits |
| **CI** | `neuralmind eval .` scored v4.5.0 ranking | Same command; run it with and without `NEURALMIND_BM25_UNIFIED=0` to see what v4.6.0 changed on your repo |

## Environment variables

| Variable | Default | Effect |
|---|---|---|
| `NEURALMIND_BM25_UNIFIED` | on | One BM25 index over docs and code, written by `build`. `0` restores v4.5.0's docs-only keyword list |
| `NEURALMIND_L3_PER_FILE` | off | `N` caps L3 hits per file (measured at `2`), refilling from the next-best candidates |
| `NEURALMIND_DOC_HANDOFF` | off | `1`: a doc hit that names a code file or symbol brings that code into contention |
| `NEURALMIND_HUB_DAMPEN` | off | `1`: down-weights files returned far more often than chance |
| `NEURALMIND_INTENT_RULES` | off | `1`: "how does X… / where is X… / which X is…" questions get code intent; questions that name a document or ask how to install get docs |
| `NEURALMIND_INTENT_POOL` | off | `1`: intent ranks all 10 candidates instead of re-ordering the four L3 chose; measured with `NEURALMIND_INTENT_RULES=1` |
| `NEURALMIND_BM25_CODE` | off | `1`: a second, code-only keyword list fused by RRF |

Five more ranking changes (six flags — the intent pool is a variant of the
intent rules) were measured and not kept. Those flags are research settings:
each one lost on the eval above. Measure one on your own repository before turning it on — see
[A/B-test a ranking change on your own repo](https://github.com/dfrostar/neuralmind/blob/main/docs/use-cases/ab-test-a-ranking-change.md).

## Upgrade notes

- **Run `neuralmind build` once.** Read paths never build (v4.4.0), so until a
  build writes `bm25_unified_index.json`, queries keep v4.5.0's keyword list.
  Running `neuralmind eval .` before and after the build shows what the change
  did on your repository.
- **Rankings move.** Expect different top hits on code questions, and note
  `rich`: an MRR can fall while hit@5 holds. If your own eval drops,
  `NEURALMIND_BM25_UNIFIED=0` restores v4.5.0 ranking — and an issue with your
  `neuralmind eval . --report` table helps the next round.
- **No API, MCP schema or config-file changes.** The one new file is
  `.neuralmind/bm25_unified_index.json`, rewritten on every build.

## Related

- Use case: [A/B-test a ranking change on your own repo](https://github.com/dfrostar/neuralmind/blob/main/docs/use-cases/ab-test-a-ranking-change.md)
- Use case: [Measure retrieval on your own repo](https://github.com/dfrostar/neuralmind/blob/main/docs/use-cases/measure-retrieval-on-your-repo.md)
- Raw eval output and how to reproduce it: [`bench/retrieval/`](https://github.com/dfrostar/neuralmind/blob/main/bench/retrieval/README.md)
- Public benchmark: [methodology and results](https://github.com/dfrostar/neuralmind/blob/main/docs/benchmarks/public.md)
- CLI reference: [`query`](https://github.com/dfrostar/neuralmind/blob/main/docs/wiki/CLI-Reference.md#query), [`eval`](https://github.com/dfrostar/neuralmind/blob/main/docs/wiki/CLI-Reference.md#eval-v0140-project-eval-v450), [environment variables](https://github.com/dfrostar/neuralmind/blob/main/docs/wiki/CLI-Reference.md#environment-variables)
