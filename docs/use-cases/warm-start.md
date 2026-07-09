# Use Case: Warm Start — a useful synapse layer from commit zero *(v0.42.0+)*

## What you're solving for

NeuralMind's differentiator is the synapse layer: a learned map of which files
go together and what you edit next. The catch is how it learns — from *live
editing*. On a fresh install that map is empty, and it stays close to empty until
you've worked in the repo for roughly a week. So the capability the product leads
with is exactly the capability that isn't there when a new user (or a new agent,
or a CI job) first shows up.

That's the cold-start problem. `neuralmind mine-history` removes it.

Every repository already contains the signal the synapse layer wants. Files that
changed together in a commit are the *same* co-activation a live edit produces —
just already recorded, often thousands of observations deep. Mining reads that
history and seeds the store, so recall is useful on the **first** query.

## The one command

```bash
neuralmind build .            # index the code (if you haven't)
neuralmind mine-history .     # warm the synapse layer from git history
```

```console
Mined 1847 co-change edge(s) (206 durable) from 1983 of 2000 commit(s) into the 'history' namespace.
  + 412 directional transition(s) from 388 same-author commit sequence(s) (feeds `neuralmind next`).
  Skipped 17 commit(s) touching more than 50 files (noise).
  1847 edge(s) + 412 transition(s) written.
  These now bias recall from the first query. Re-run any time; clear with `neuralmind memory reset --namespace history`.
```

Prefer to look before you leap:

```bash
neuralmind mine-history . --dry-run
# → Would mine 1847 co-change edge(s) (206 durable) from 1983 of 2000 commit(s) ...
```

## What just happened, and why it's trustworthy

The worry with any "seed it from history" feature is that it floods the store
with noise. Three design choices keep the signal clean:

1. **File granularity.** Each changed path maps to its single *file-level* graph
   node, so a commit touching `k` files produces `k(k-1)/2` co-change pairs — not
   a clique over every symbol in every file. A 5-file commit is 10 pairs, not
   thousands.
2. **Focused commits weigh more.** Per-commit pair weight scales as `1/(k-1)`. A
   surgical two-file commit ("change the API, change its test") is strong
   evidence those two files relate; a 200-file dependency bump barely registers,
   and anything past `--max-files` (default 50) is dropped outright.
3. **Durable pairs are protected.** A pair that co-changed across ≥ 5 commits is
   written *already LTP-protected* — the decay layer's long-term-potentiation
   floor keeps a genuine structural fact from fading before you've generated the
   real usage that would replace it.

## It learns direction, too

Co-change says *these files go together*. Commit sequences say *this one comes
next*. Two consecutive commits by the **same author within six hours** are one
work session — after committing the API change, they went on to commit the
migration — and mining records that as a directional transition, the same signal
`neuralmind next` normally learns from watching you edit live. On a repo with
zero usage history:

```console
$ neuralmind next . api.py
After api.py:
   69.2%  models.py
   15.4%  utils.py
   15.4%  views.py
```

Rebased or reordered history (a negative timestamp gap between commits) breaks
the inferred session instead of fabricating a sequence.

## It's a prior, not an opinion

Mined edges live in their own `history` namespace, merged into every read at
`W_HISTORY` (0.35) — quieter than both your personal usage (0.8) and imported
team memory (0.5). That ordering is the whole point: history gives recall a
running start, and the moment you actually start editing, *what you do* outweighs
*what the repo did before you*.

You can see both layers directly. `neuralmind memory inspect` breaks recall down
by namespace, and reading one namespace explicitly shows its raw (unscaled)
weights:

```bash
neuralmind memory inspect . --namespace history   # what the mining produced
```

The raw weight of a saturated history edge is `1.0`; in the default merged view
that same edge contributes `0.35` (`1.0 × W_HISTORY`), sitting underneath any
personal usage on the same pair. Early on, with no usage yet, the history layer
is what surfaces a file's co-changed siblings; once you've edited for a while, the
personal layer leads and history recedes to a backstop.

It is also **sticky** (a co-change fact is long-lived, so it decays slowly),
**idempotent** to re-run (weights merge by MAX — running it twice never doubles
anything), and **independently clearable**:

```bash
neuralmind memory reset --namespace history    # forget the mined prior entirely
neuralmind mine-history .                       # re-mine, e.g. after a big merge
```

Nothing else in your memory is touched, and a project that never runs the command
behaves exactly as before — an empty `history` namespace contributes nothing.

## Where it pays off

- **Onboarding a new engineer.** Their agent knows the repo's structural
  relationships on day one instead of week two.
- **CI and ephemeral agents.** A fresh checkout in a pipeline has no usage history
  to learn from — mining gives it the co-change map anyway.
- **`neuralmind review` from the start.** The [review-before-push
  walkthrough](review-before-push.md) predicts co-break candidates from synapse
  weights; mining means those predictions are useful before you've trained them
  by hand.
- **Refresh after a big merge.** Re-run to fold newly-landed history into the
  prior.

## Honest limits

- **Renames and deletions.** Paths from old commits that no longer map to an
  indexed file are silently dropped — a missing prior, never a wrong one. The
  mined map reflects the code as it exists now.
- **Repo root = project root.** Like `neuralmind review` and the `init-hook`
  post-commit hook, mining assumes the project directory is the git repository
  root.
- **Session inference is heuristic.** Directional transitions come from
  consecutive same-author commits within a 6-hour window; rebased or reordered
  history (a negative timestamp gap) breaks the inferred session rather than
  fabricating a sequence, so heavily-rebased repos mine fewer transitions.

## Related

- [Branch-isolated memory & team baselines](branch-isolated-memory.md) — the
  namespace machinery `history` is built on.
- [Review before push](review-before-push.md) — the co-break feature warm start
  makes useful immediately.
