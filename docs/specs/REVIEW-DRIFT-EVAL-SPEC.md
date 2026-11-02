# `neuralmind review` and `neuralmind drift` on real commits — pre-registration

**Status:** run 2026-11-02; **both commands fail their gate** (review hit@10
0.628 against git co-change 0.644; drift 5% on fixes and 5% on controls);
[results](../../bench/review_drift/2026-11-02/README.md) · **Harness:**
`evals/review_drift/` · **Results:** `bench/review_drift/2026-11-02/`

## Why

`review` (files not in your diff but strongly associated with the ones that
are) and `drift` (a changed symbol that skips a pattern its peers share) are
the two commands aimed at code review. Every other measured surface in this
repository is retrieval; neither of these has a number. The person they are
for is a reviewer on a codebase they didn't write, with a diff in front of
them. The question is not whether the commands beat nothing. It is whether
they beat what that reviewer already has: `git log` and the import graph.

## Questions

**Q1, review.** When a real commit changed several files and the reviewer's
diff is missing one of them, how often does `neuralmind review` name the
missing file in its top 5 and top 10, on an index built cold at the parent
commit (no usage history, structural seeds only)? How does that compare with
ranking files by git co-change history, and by direct structural adjacency?

**Q2, drift.** Of real bug fixes, how often would `neuralmind drift` have
flagged a symbol the fix changed, when run on the pre-fix code with the fix's
hunks as the diff? And how often does it flag a symbol on commits of the same
repositories that are not fixes, which is the noise it would add to every
review?

## Repositories

The four public-benchmark repositories at the commits pinned in
`evals/public/manifest.json` (requests, click, flask, rich), each **indexed
from the repository root**, as `neuralmind build .` indexes a checkout. That
is the reviewer's situation; the subdir layout the retrieval benchmark uses is
not. Retrieval was tuned on these repositories' 40 queries; `review` and
`drift` were not, but they are not held out in the strict sense, and the
report says so.

For drift only, NousResearch/hermes-agent as well: the 17 task-outcome tasks
(12 held-out, 5 screen) whose indexes at their base commits are already built
and cached. Neither command was developed with that repository in view.

Not NeuralMind's own repository: the graph, the structural seeding and the
drift defaults were developed on it.

## Commits

Selection is mechanical. No commit is read before it is selected.

**Review set.** Walking back from each pinned commit over at most 600
non-merge commits: every commit that changed between 2 and 6 `.py` files
under the manifest's source subdir, tests not counted toward that number.
Most recent first, at most 40 per repository (requests has 1 in its window:
its pinned commit is from 2024 and its history is mostly single-file).
A commit's **ground truth** is its full set of changed files that the index
built at its parent holds, code and tests alike, under the repository; files
the commit added, deleted or renamed are dropped from the ground truth, since
a file that doesn't exist at the parent can't be named by its index. A commit
whose ground truth shrinks below 2 files is dropped and counted.

**Drift fix set.** From the same windows, commits whose subject matches
`fix|bug|regress` (case-insensitive) and changed 1 to 6 source files, most
recent first, at most 40 per repository. **Drift control set:** from the same
windows, the same number per repository of commits whose subject does *not*
match, 1 to 6 source files, most recent first. For hermes-agent the fix set is
the 17 tasks' fix commits, already published with their gold files; it has no
control set, which the report says.

## Procedure

**Review.** For each commit `C` with parent `P` and ground truth `F`
(`|F| ≥ 2`):

1. Check out `P`. Remove `.neuralmind/` and run `neuralmind build .`: a fresh
   index with no learned synapses, which is the cold state a reviewer has on
   day one. The synapse store holds only the structural seeds the build writes.
2. For each `f ∈ F`: write `C`'s versions of `F \ {f}` into the tree
   (`git checkout C -- <files>`), run `neuralmind review . --json --top-k 10`,
   record `f`'s rank in `at_risk` (or a miss), the list's length, and how many
   of its entries are test files. Restore the tree.
3. On the same `(C, f)` pairs, rank the repository's files by each baseline,
   excluding the seed files, and record `f`'s rank:
   - **git co-change:** the number of commits among the 300 non-merge commits
     before `P` that changed both the file and at least one seed file; ties
     broken by the most recent such commit. What a reviewer gets from
     `git log` alone.
   - **structural adjacency:** the number of structural edges (calls,
     imports, inheritance, from the graph built in step 1) between the file's
     symbols and the seeds' symbols. The information `review` spreads over,
     without the spreading.
   - **random:** expected hit@k, `k / (N − |seeds|)` with `N` the files the
     index holds. Computed, not sampled.

**Drift.** For each commit `C` with parent `P` in a fix or control set:

1. Tree at `P`, index built at `P` (the review step's build where the commit
   is in both sets, else a fresh one; for hermes-agent, the cached index).
2. Run `neuralmind drift . --json --diff C`. With the tree at `P`, the diff
   against `C` carries the fix's hunks with the pre-fix code on the
   working-tree side, so the symbols drift examines are the ones as they were
   before the fix. A **hit** is one or more findings (drift reports only
   symbols the diff touched, so any finding names a symbol the fix changed).
   Record the finding count and `symbols_checked`.

Defaults throughout: `--top-k 10` for review; drift's `cohesion 0.6`,
`min_peers 3`, `max_findings 10`, refresh on. Nothing is tuned on these
commits. The tool is the checkout under test, named in the results with its
commit.

## Endpoints

**Review, primary:** hit@10 and hit@5, micro-averaged over all `(C, f)` pairs,
pooled across the four repositories, with the same for each baseline on the
same pairs. **Secondary:** MRR; the share of commits where review named at
least one missing file; the share of `at_risk` entries that are test files;
how often the list was empty or shorter than 10 (cold-index coverage); the
median time of a `review` call; per-repository tables.

**Drift, primary:** `recall_fix`, the share of fix commits with a hit, and
`rate_control`, the share of control commits with a hit. **Secondary:** mean
findings per commit in each set, `symbols_checked`, the hermes-agent fix set
on its own, and the share of commits in each set with **no examinable
pre-fix lines**: a commit that only added lines has zero-length hunks on the
parent's side, so drift examines no symbol. Those commits count as misses in
`recall_fix` (the check could not have caught them) and are also reported on
their own, since they measure the method's reach rather than its judgement.

## Decision rule

Written before any run, from what a reviewer tolerates: a co-break list that
is wrong more than half the time gets ignored, and a check that fires as often
on clean commits as on bugs gets disabled.

- **Review is worth quoting as a reviewer feature** when, pooled,
  **hit@10 ≥ 0.50** and **hit@10 exceeds git co-change's hit@10 by at least 5
  points**. Beating co-change but under 0.50: report it as "more often right
  than the git log, and wrong about half the time", nothing stronger. Not
  beating co-change: on a cold index the list adds nothing `git log` doesn't,
  and the command's output text ("these files have historically been edited
  together with the ones above") must change, because on a cold index that
  isn't what it reports.
- **Drift is worth quoting** when **recall_fix ≥ 0.15** and
  **recall_fix ≥ 2 × rate_control**. Below the first, the check is too quiet
  to catch fixes; below the second, it flags clean commits about as often as
  bugs.

A result that fails a rule is published the same way as one that passes.

## What this does not measure

- Whether a reviewer acts on the list, or how long review takes them.
- Learned synapses. This is the cold case on purpose; weeks of use on one
  codebase may change it, and a separate study would have to show that.
- Whether the missing file *needed* to change. Co-change is a proxy for
  coupling, and a commit that touched two unrelated files for convenience is
  a miss for every method alike.
- Languages other than Python.

## Threats to validity

- Squash merges bundle unrelated changes; the 6-file cap excludes refactors
  but not a 3-file bundle. It raises misses for all methods alike.
- Test files are frequent `at_risk` entries and frequent ground-truth files.
  That is the "forgotten test file" case the command describes, so they stay
  in; the test-file share is reported so a reader can discount it.
- The co-change window (300 commits) was chosen before running. A reviewer's
  `git log` has the whole history; the window approximates recent coupling.
- Lines a fix only *adds* have no pre-fix range, so drift can't examine a
  symbol the fix created or only extended at a new location. Those fixes
  count against `recall_fix`.
- The public repositories are the retrieval benchmark's; hermes-agent is the
  only repository neither command was developed near, and it enters the drift
  arm only.
- One requests commit (`555b870e`, 4 files) was used to check the mechanics
  before this was written: review listed 8 candidates, none the held-out
  `src/requests/__init__.py`; drift reported 0 findings on 3 symbols. It is in
  the review set and is counted like any other commit.

## Publication

Per-pair and per-commit records to `bench/review_drift/<date>/records.jsonl`,
the summary to `summary.json`, and a README with the tables and the misses.
Numbers reach the site only through `site/claims.json`, with their evidence
level, as every other figure does.

## Change log

- 2026-11-02 — questions, sets, procedure, endpoints and decision rule
  pre-registered before `evals/review_drift/` was written.
- 2026-11-02 — before the run, after a smoke run of the harness on requests
  only (one review commit, four fix and four control commits; its records
  were discarded because the co-change baseline had a bug): the requests
  review set is 1 commit, not 10 (the earlier count had walked from the
  clone's head, not the pinned commit); the "no examinable pre-fix lines"
  secondary endpoint was added after two of the four requests fixes turned
  out to be pure additions. The decision rule is unchanged.
- 2026-11-02 — the first full run was stopped after 47 parent commits and its
  records deleted: the venv's `neuralmind` console script resolved to the
  4.21.0 wheel from PyPI, not the checkout, while the harness's identity
  check, run from inside the repository, reported the checkout (the current
  directory shadows an installed package). The check now runs from `/` and
  records whether the module is an installed copy. The rerun uses a venv with
  an editable install of the checkout. Nothing from the stopped run was read
  beyond its progress lines and the build records' synapse namespaces, which
  is how the mismatch was found (4.21.0 seeded `shared`, not `structural`).
- 2026-11-02 — run complete (`neuralmind 4.24.0` at `d35bfbc5`; 319 builds,
  430 review pairs on 119 commits, 121 fix and 121 control commits, 17
  hermes-agent fixes). Review: hit@10 0.628, co-change 0.644, adjacency
  0.533; floor met, margin not. Drift: 0.050 on fixes, 0.050 on controls;
  neither condition met. Both published as failing. As the rule requires,
  `review`'s closing text no longer says the files were "historically edited
  together"; on a cold index it reports structural coupling, and the text and
  the docs now say so.
- 2026-11-02 — after review on #777, four harness corrections, none of which
  changes a review rank: the co-change baseline breaks ties on count, then
  recency, then **path** (it had left ties to set-iteration order, which
  varies with the hash seed), and both baselines were re-scored for every
  recorded pair under that sort, with any changed figure noted in the
  results README; MRR is reported as **MRR@10** for every method (review
  lists at most ten entries, so a baseline's rank 30 scores as a miss, as
  review's does); the decision rule is evaluated on exact counts, not rounded
  rates; and a `review` or `drift` call that fails now stops the run instead
  of being recorded as a miss (the published run had no such failure).
