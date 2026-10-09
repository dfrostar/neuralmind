# A/B-test a ranking change on your own repo

**Best for:** anyone about to turn on one of NeuralMind's research flags,
contributors changing how retrieval ranks, and teams upgrading NeuralMind who
want to know what the new ranking did on *their* code.

**Primary goal:** a before/after hit@5 and MRR on your repository's own
questions — and, for a change you'd ship to everyone, a verdict across six
repositories against a keep rule written down before you look (v4.6.0+).

A ranking change that wins on the question you had in mind can lose on the
ones you didn't. v4.6.0 is the worked example: six candidate changes to how the
four L3 search slots are spent, 30 questions on each of six repositories —
pre-registered and committed for the five public repositories, plus a private
383-file repository — and one change that passed. Five more ranking changes
(six flags — the intent pool is a variant of the intent rules) were measured
and not kept. This walkthrough runs the same measurement on your repository.

---

## The existing use case this improves

"Did the upgrade help on my repo?" used to mean re-reading a few answers and
forming an impression. With v4.5.0's `neuralmind eval .` you had a number; with
v4.6.0 every ranking change ships behind an environment variable, so the
comparison is one variable away — same index, same questions, read-only.

## 0. Before you start

- **A questions file.** `.neuralmind.eval.yaml` at the repo root, each question
  with the file that answers it — see
  [Measure retrieval on your own repo](./measure-retrieval-on-your-repo.md).
- **Enough questions to see a loss.** With ten questions, one question is ten
  points of hit@5. v4.6.0 used 30 per repository; even there, a single question
  is the difference between `requests`' 90% and 87%.
- **Questions first, change second.** Write and commit the questions *before*
  you try the change. Questions written after you've seen what a change does
  will drift toward the ones it gets right.
- **A keep rule, written down now.** v4.6.0's was:
  - mean hit@5 across repositories goes up, and it goes up on at least 3;
  - no repository drops by more than one question;
  - average context tokens rise by at most 10%;
  - the public 4-repo benchmark's gold-file recall doesn't drop.

  Since v4.12.0 the multi-repo harness applies a **paired** rule instead,
  pooled over every question: the change wins more hit@5 questions than it
  loses, with an exact McNemar p < 0.05; no repository drops by more than two
  questions; tokens rise by at most 10%. The old rule, with one question worth
  3.3 points, rejected a change that raised two repositories and lowered none.

  On a single repository, a reasonable version is "hit@5 up, MRR not down,
  tokens up by at most 10%". Whatever yours is, decide it before the first run.

## 1. Build once

```bash
neuralmind build .
```

Every ranking flag is read when a query runs, so one build serves the baseline
and every variant. The build also writes the v4.6.0 keyword index
(`.neuralmind/bm25_unified_index.json`); an index built before v4.6.0 still
ranks the v4.5.0 way until you rebuild.

## 2. Run the baseline and each variant, read-only

```bash
neuralmind eval .                                          # today's default — kept in the history
NEURALMIND_BM25_UNIFIED=0 neuralmind eval . --no-history   # v4.5.0's keyword index
NEURALMIND_L3_PER_FILE=2 neuralmind eval . --no-history    # at most two L3 hits per file
NEURALMIND_DOC_HANDOFF=1 neuralmind eval . --no-history    # a doc that names code pulls that code in
neuralmind eval . --no-history                             # the baseline again: it should match the first run
```

- **`eval` is read-only.** It reads the learned synapse layer but writes
  nothing back, so no variant trains the index the next one reads.
- **`--no-history` keeps variants out of your trend.** Each history row records
  the date, commit and NeuralMind version, but not the flags — a variant row
  would read later as a regression or a win of the default.
- **Re-run the baseline last.** If it doesn't match the first run exactly,
  something other than the flag moved — a rebuild, or your agent's hooks
  learning from a session in between — and the deltas aren't the flag's. Run
  the comparison between sessions, or on a copy of the repository.

The flags you can try, and what they did on v4.6.0's eval:

| Flag | What it does | On v4.6.0's eval |
|---|---|---|
| `NEURALMIND_BM25_UNIFIED=0` | v4.5.0's docs-only keyword index | the v4.6.0 default beat it: mean hit@5 72.8% → 79.4% |
| `NEURALMIND_L3_PER_FILE=2` | at most N L3 hits per file | +1.1 pts mean hit@5, 2 repos up, none down on hit@5, but mean MRR fell 0.654 → 0.629 (`requests` 0.75 → 0.69, `flask` 0.71 → 0.65); public recall 96.25% — the rule needs 3 |
| `NEURALMIND_DOC_HANDOFF=1` | a doc hit that names code pulls that code in | helps only where docs name code; a wash on v4.6.0 |
| `NEURALMIND_HUB_DAMPEN=1` | down-weights files returned far more often than chance | cost `click` 3–4 questions |
| `NEURALMIND_INTENT_RULES=1` | "how does X… / where is X… / which X is…" → code intent | moved MRR (0.654 → 0.672), never hit@5 |
| `NEURALMIND_INTENT_POOL=1` (with `NEURALMIND_INTENT_RULES=1`) | intent ranks all 10 candidates | `click` −8 questions (vs v4.5.0) |
| `NEURALMIND_BM25_CODE=1` | a separate code-only keyword list | `rich` −4, `click` −3 on v4.6.0 |

A flag that lost across six repositories can still win on yours — the doc
hand-off, for one, helped only where the docs name code: against v4.5.0 it
added three questions on the private repository and one on `neuralmind`; on
top of v4.6.0 it was a wash (`neuralmind` +2, private −1). That is why you
measure it on yours rather than trust either result.

## 3. Read the result like a keep rule, not a headline

Put the runs side by side and check every clause, not just the mean:

| Run | hit@1 | hit@5 | MRR | Avg tokens | Keep? |
|---|---:|---:|---:|---:|---|
| baseline | | | | | — |
| `NEURALMIND_L3_PER_FILE=2` | | | | | |

Two of v4.6.0's own results show why:

- **hit@5 alone hides rank.** On `rich`, the unified index held hit@5 at 80%,
  but MRR fell from 0.71 to 0.60 — the gold file was still in the top five,
  just lower. A hit@5-only rule calls that neutral.
- **A mean hides a repository.** The six-repository mean rose from 72.8% to
  79.4% while `requests` lost a question (90% → 87%). The keep rule says no
  repository drops by more than one question; it still goes in the release
  notes.

## 4. For a change you'd ship to everyone: the multi-repo harness

One repository can't tell you whether a change generalises. From a source
checkout, `python -m evals.retrieval.run` runs the same scorer as
`neuralmind eval` across `requests`, `click`, `flask` and `rich` (at the public
benchmark's pinned commits), this repository, and — with `--private` — yours:

```bash
git clone https://github.com/dfrostar/neuralmind && cd neuralmind
pip install -e . tiktoken
python -m evals.retrieval.run --private ~/work/your-repo --configs baseline,per_file,handoff
NEURALMIND_ORT_THREADS=1 python -m evals.retrieval.run --private ~/work/your-repo --public-benchmark   # also gate on the public benchmark
```

- **Your repository stays yours.** It must be a git repository with its own
  `.neuralmind.eval.yaml`; the harness copies the files git covers into
  `.bench-work/private` (gitignored), so your own `.neuralmind/` is never
  touched. It is reported only in aggregate, as `private`, and `--out` writes
  no per-question ranks for it.
- **Fresh indexes, checked baseline.** Every run rebuilds each repository's
  index from nothing and runs the baseline again after every configuration.
- **It applies the keep rule for you** — since v4.12.0 the paired rule
  above, with the mean MRR change and a bootstrap 95% interval, and p50/p95
  query latency, in the report.
- **It compares two releases.** `python -m evals.retrieval.run --compare
  old/results.json new/results.json` pairs two runs question by question. That
  is how v4.12.0 was checked against v4.11.1: hit@5 80.0% → 93.3% over 150
  questions, 21 won and 1 lost (exact McNemar p < 0.0001)
  ([`bench/retrieval/vs-v4.11`](https://github.com/dfrostar/neuralmind/blob/main/bench/retrieval/vs-v4.11/report.md)).
- **v4.6.0's run, under the rule it used then.** Two rows from it
  ([`bench/retrieval/vs-v4.5`](https://github.com/dfrostar/neuralmind/blob/main/bench/retrieval/vs-v4.5/report.md)):

```
| Config | Δ mean hit@5 | Repos improved | Worst repo (questions) | Δ tokens | Public recall | Keep |
|---|---:|---:|---:|---:|---:|---|
| per_file | +1.1% | 2 | +0 | +0.4% | 95.00% | no |
| bm25_unified | +6.7% | 3 | -1 | +1.1% | 95.00% | yes |
```

Every option is in the
[CLI reference](../wiki/CLI-Reference.md#eval-v0140-project-eval-v450).

## 5. Your own change

Put it behind an environment variable the way the shipped flags are — read
when a query runs, today's behaviour when unset — then register it in
`evals/retrieval/run.py`:

```python
FLAGS = (..., "NEURALMIND_MY_CHANGE")          # the harness clears these between configurations
CONFIGS["my_change"] = {"NEURALMIND_MY_CHANGE": "1"}
```

```bash
NEURALMIND_ORT_THREADS=1 python -m evals.retrieval.run --configs baseline,my_change --public-benchmark --private ~/work/your-repo
```

Two things catch people out:

- **A variable missing from `FLAGS` leaks.** The harness resets only the
  variables listed there, so an unlisted one stays set for every configuration
  that runs after yours.
- **The harness builds once, with every flag unset.** If your change needs
  something the build writes, compute it lazily at query time while it's
  behind its flag — the harness's single build won't produce it otherwise.

## 6. The worked example: how v4.6.0 chose its default

1. **The goal.** Spend the four L3 slots better: on "how does X work"
   questions, docs kept taking slots the code should have had.
2. **Pre-registration.** 30 questions per repository for `requests`, `click`,
   `flask`, `rich` and this repository were committed in
   `evals/retrieval/questions/` before any change was tried, plus a private
   383-file repository through `--private`.
3. **Round 1: five work items, none kept.** The biggest lift on the private
   repository came from a separate code-only keyword list: it lifted three
   repositories, but cost `requests` three questions and dropped public recall
   from 93.75% to 92.50%. That pointed at the keyword index itself: on the default
   backend it held only documents, so docs got a keyword signal code never
   did.
4. **Round 2: one index for both.** Three variants designed after seeing round
   1; only one BM25 index over docs and code passed: mean hit@5 72.8% → 79.4%,
   MRR 0.589 → 0.654, tokens +1.1%. Because the variants were designed after
   seeing results, the public benchmark — 40 queries written long before — was
   the holdout: gold-file recall 93.75% → 95%.
5. **Contamination, found mid-run.** The public benchmark queries with learning
   on, and it ran against the same clones as the eval, so it was training the
   eval's indexes and the baseline moved. Every run now builds fresh indexes,
   each public-benchmark run gets its own copy, and the baseline is re-checked
   after every configuration. Both committed runs reproduced it exactly on all
   six repositories.
6. **Round 3: everything else, on top of the new default.** Nothing else
   passed. The per-file cap came closest — +1.1 pts mean hit@5, two
   repositories up, none down on hit@5, public recall 96.25% — but mean MRR
   fell 0.654 → 0.629 (`requests` 0.75 → 0.69, `flask` 0.71 → 0.65), and the
   rule then asked for three repositories up, so it stayed off.
7. **The losses went in the release notes:** `requests` −1 question, `rich`
   MRR 0.71 → 0.60, a new `click` miss on the public benchmark, and the private
   repository at 73% / 0.60 against its target of 80% / 0.65 — not met.

The fix the misses seemed to call for — routing "how does X…" questions to
code intent — only re-ordered the four hits L3 had already chosen: it moved MRR
and never hit@5. The change that worked wasn't on the round 1 list at all. And
one repository would have picked the wrong winner: on the private repository
alone, the code-only keyword list looked best (80% hit@5 against the unified
index's 73%), while across six it cost `requests` three questions and, on top
of v4.6.0, `rich` four.

---

## The potential use case: ranking changes that arrive with their evidence

Because the harness runs read-only on committed questions and prints the keep
rule's verdict, a pull request that changes ranking can carry its own evidence:
the flag, the per-repository table, and the keep-rule row — paste the report
into the PR description. A team running NeuralMind on a large private codebase
can do the same before turning a research flag on for everyone: run it on the
repository with `--private`, read the row, and only then change the default in
the team's environment.

Related: [Release notes v4.12.0](../releases/RELEASE_NOTES_v4.12.0.md) ·
[Release notes v4.6.0](../releases/RELEASE_NOTES_v4.6.0.md) ·
[Raw eval output](https://github.com/dfrostar/neuralmind/blob/main/bench/retrieval/README.md) ·
[Measure retrieval on your own repo](./measure-retrieval-on-your-repo.md) ·
[Does it work on your codebase?](./benchmark-your-repo.md)

---

[← Back to use-case index](./README.md) · [Main README](../../README.md)
