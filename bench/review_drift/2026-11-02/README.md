# `neuralmind review` and `neuralmind drift` on real commits — 2026-11-02

**Pre-registered, and not a product claim.** The questions, sets, procedure
and decision rule are in
[`docs/specs/REVIEW-DRIFT-EVAL-SPEC.md`](../../../docs/specs/REVIEW-DRIFT-EVAL-SPEC.md),
written before the harness. **Both commands fail their gate.** `review`
clears its floor but does not beat ranking files by git co-change history;
`drift` fires on 5% of bug fixes and 5% of non-fix commits alike.

## Setup

- Tool under test: `neuralmind 4.24.0` from the checkout at `d35bfbc5`
  (`summary.json` → `tool`), run from a venv with an editable install.
- Repositories: requests, click, flask and rich at the public-benchmark
  commits (`evals/public/manifest.json`), each indexed cold from the
  repository root at every parent commit: 319 builds, none failed, median
  5.0 s. Every build seeded the `structural` synapse namespace only; there are
  no learned associations anywhere in this run.
- Selection (`sets.json`): walking back 600 non-merge commits from each
  pinned commit; review set = commits with 2–6 source files under the
  manifest subdir (cap 40; requests has 1); fix set = subject matching
  `fix|bug|regress`, 1–6 source files (cap 40); control set = as many
  non-matching commits. hermes-agent: the 17 task-outcome tasks whose indexes
  were cached, drift only.
- Harness: `evals/review_drift/` (`select`, `run`, `analyze`). Raw per-pair
  and per-commit records: [`records.jsonl`](records.jsonl); the computed
  tables: [`summary.json`](summary.json).

## Review: can it name the file your diff forgot?

For each of 119 commits (2 more were dropped because fewer than 2 of their
changed files existed in the parent's index), every ground-truth file was held
out in turn (430 pairs), the other files took the commit's version, and
`neuralmind review . --json --top-k 10` was asked for co-break candidates.
The same pairs were ranked by two baselines a reviewer already has.

| Set | Pairs | Method | hit@5 | hit@10 | MRR@10 |
|---|---|---|---|---|---|
| **pooled** | 430 | **review** | **0.449** | **0.628** | 0.275 |
| pooled | 430 | git co-change (300 commits before the parent) | 0.551 | 0.649 | 0.359 |
| pooled | 430 | structural adjacency (direct call/import/inherits edges) | 0.400 | 0.533 | 0.237 |
| pooled | 430 | random, expected | 0.057 | 0.114 | — |
| click | 123 | review | 0.561 | 0.789 | 0.402 |
| click | 123 | co-change | 0.675 | 0.797 | 0.412 |
| click | 123 | adjacency | 0.447 | 0.602 | 0.281 |
| flask | 166 | review | 0.488 | 0.693 | 0.267 |
| flask | 166 | co-change | 0.572 | 0.651 | 0.367 |
| flask | 166 | adjacency | 0.392 | 0.530 | 0.200 |
| rich | 137 | review | 0.307 | 0.409 | 0.170 |
| rich | 137 | co-change | 0.423 | 0.518 | 0.307 |
| rich | 137 | adjacency | 0.372 | 0.474 | 0.245 |
| requests | 4 | review | 0.250 | 0.500 | 0.275 |
| requests | 4 | co-change | 0.250 | 0.500 | 0.156 |
| requests | 4 | adjacency | 0.250 | 0.500 | 0.150 |

Every method is scored to the same depth: review lists at most ten entries,
so a baseline's rank beyond ten counts as a miss in hit@10 and in MRR@10.
The baselines were re-scored after review of the harness gave the co-change
sort a deterministic final tie-break (count, then recency, then path; it had
left ties to set-iteration order): 56 of 430 co-change ranks changed, pooled
co-change moved from 0.547 / 0.644 to 0.551 / 0.649, adjacency and review
ranks did not change, and nothing below changed its verdict.

**Decision rule:** hit@10 ≥ 0.50 (met: 270 of 430, 0.628) *and* at least 5
points over co-change (not met: 270 against 279 of 430, −2.1 points). **Not
worth quoting as a reviewer feature.** Said plainly: on a repository you have
just indexed, the co-break list is right about six times in ten at ten
entries, and the git log is right about as often, with a better top five
(0.551 against 0.449).

What else the records say:

- **The two methods miss different pairs.** At ten entries review alone hit
  62 pairs the git log missed, the git log alone hit 71 that review missed,
  and either hit 79% of pairs (69% at five). A reviewer who runs both does
  better than either; nothing ships that today.
- **Review does relatively better with more context.** With one seed file
  (a 2-file commit) review hit 0.70 against co-change's 0.73; with two,
  0.66 against 0.76; with three, 0.60 against 0.57; with four or more, 0.60
  against 0.60.
- **Spreading beats the raw edges it spreads over.** Review (0.628) is 10
  points above direct structural adjacency (0.533) on the same graph, so the
  spread is doing something; it is the information, not the method, that
  runs out.
- Test files were 22% of the list entries and 21% of the held-out files;
  the list was 10 long on 91% of calls and never empty; a `review` call took
  a median 0.26 s.
- requests, with 4 pairs, is noise either way and is kept because the spec
  said it would be.

**What this means for the command.** Its output ends: "These files have
historically been edited together with the ones above." On a fresh index that
is not what it reports: the synapse store holds only the structural seeds
the build wrote, and the "edited together" history is exactly what the
co-change baseline computed from git and the command did not. The spec's
rule says the text must change when review doesn't beat co-change, and this
change ships with the result. Whether learned associations, after weeks on
one codebase, lift it past the git log is not measured here; `eval
--synapse-ab` is the tool for that question.

## Drift: would it have flagged the symbol the fix changed?

With the tree at the parent and the fix's hunks as the diff, `neuralmind
drift . --json --diff <fix>` examined the pre-fix symbols. A hit is one or
more findings. Commits whose fix only *added* lines leave drift nothing to
examine on the parent's side; they count as misses and are reported.

| Set | Commits | With a finding | Rate | No examinable pre-fix lines | Rate over examinable | Findings per commit |
|---|---|---|---|---|---|---|
| **fixes, public (pooled)** | 121 | 6 | **0.050** | 10 | 0.054 | 0.107 |
| **controls, public (pooled)** | 121 | 6 | **0.050** | 7 | 0.053 | 0.083 |
| click fixes / controls | 37 / 37 | 1 / 1 | 0.027 / 0.027 | 2 / 1 | 0.029 / 0.028 | 0.162 / 0.027 |
| flask fixes / controls | 40 / 40 | 4 / 3 | 0.100 / 0.075 | 3 / 2 | 0.108 / 0.079 | 0.150 / 0.075 |
| rich fixes / controls | 40 / 40 | 1 / 2 | 0.025 / 0.050 | 3 / 4 | 0.027 / 0.056 | 0.025 / 0.150 |
| requests fixes / controls | 4 / 4 | 0 / 0 | 0 / 0 | 2 / 0 | 0 / 0 | 0 / 0 |
| hermes-agent fixes (17 tasks, cached indexes, no control set) | 17 | 2 | 0.118 | 2 | 0.133 | 0.294 |

**Decision rule:** recall on fixes ≥ 0.15 (not met: 0.050) *and* at least
twice the control rate (not met: 0.050 against 0.050). **Not worth quoting.**
The check is quiet, which was the design ("fails quiet, never loud"), and on
these repositories it is as quiet on bugs as on everything else. The median
fix touched one symbol the graph knew.

What the 12 public findings were: 10 of them name a **test function** that
skips a fixture or helper its sibling tests call (`test_echo_custom_file()`
skipping `isolated_filesystem()`, `test_clean_pop()` skipping
`app_context()`), in fixes and controls alike. The one non-test finding in a
fix, `make_config()` skipping `update()` in flask, is the kind of thing drift
was built for; one in 121 is the rate. hermes-agent's 2 of 17 is on a larger
repository with no control set, so it says little on its own.

## What this does not say

- Nothing about learned synapses. Every index here was minutes old. The
  case for review is that weeks of co-editing teach it what git history
  already knows and more; that case is open, not closed, and measured by
  `neuralmind eval . --synapse-ab`.
- Nothing about whether a reviewer acts on the list, or how long review
  takes them.
- The four public repositories are the retrieval benchmark's. `review` and
  `drift` were not tuned on them, but they are not held out either.
- Co-change here is the plain count over 300 commits, ties broken by recency
  then path. A reviewer's `git log` has the whole history; a weighted or
  time-decayed version could do better still.
- `records.jsonl` holds the review ranks as the run recorded them and the
  baseline ranks as re-scored (the `rescore` record at the end names the
  tool and the count of changed pairs); `summary.json` is recomputed from it
  by `analyze`.

## Reproduce

```bash
python -m evals.review_drift.select --repos <dir with requests/ click/ flask/ rich/ clones> --out <out>/sets.json
python -m evals.review_drift.run --sets <out>/sets.json --out <out> --neuralmind <venv>/bin/neuralmind
python -m evals.review_drift.analyze <out>
```

Blob-less clones (`git clone --filter=blob:none`) are enough; the run checks
out each parent. About an hour on an M3 for the public repositories; the
hermes-agent arm needs the task-outcome indexes from
[`bench/task_outcome/`](../../task_outcome/) and runs with `--hermes`.
