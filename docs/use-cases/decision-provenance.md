# Use Case: Decision Provenance — Answer "Why Is It Like This?" From Git

## What you're solving for

Six months ago someone made `resolveOrgId` per-handler instead of putting it in
middleware. There was a good reason — it avoids a Prisma call on `/health`,
`/metrics`, and `/token`, and it keeps the tests simple. But that reason lives in
one person's head, or a scrolled-past chat, or nowhere. So the next engineer (or
the next AI agent) either re-derives it, interrupts someone to ask, or —
worst case — "cleans it up" into middleware and silently reintroduces the exact
problem the decision avoided.

NeuralMind indexes what the code *is*. This makes it also remember *why* it's
that way — captured at the one moment the reason is fresh (the commit) and stored
in the one place that never gets lost (git history).

## Setup (one time)

```bash
pip install neuralmind
```

Nothing to build or configure. Decision provenance reads straight from git
history — the commit trailer is the store.

## Step 1 — Capture the decision when you make it

Add a `Decision:` trailer to the commit that carries the change. Backticked
symbols in the rationale become the decision's subjects automatically; you can
also list them explicitly with a `Subjects:` line:

```
cli: resolve org id per handler

Decision: resolveOrgId is per-handler, not middleware — avoids Prisma on
          /health, /metrics, /token; keeps tests simple.
Subjects: `resolveOrgId`, `authMiddleware`
```

That's the whole capture cost: one trailer, on a commit you were already making.
No separate doc, no wiki page to keep in sync.

## Step 2 — Recall it later

```bash
neuralmind why "why is resolveOrgId per-handler?"
```

```
## NeuralMind decision provenance

- `resolveOrgId`, `authMiddleware`: resolveOrgId is per-handler, not middleware —
  avoids Prisma on /health, /metrics, /token; keeps tests simple. (see commit ba25fed)
```

The commit SHA is there so you can read the full change for context. Recall is
subject-keyed: a decision only surfaces when its symbols appear in the query, so
`neuralmind why "how does the embedder cache work?"` stays silent about
unrelated decisions.

## Step 3 — Let it surface automatically to your agent

With the `UserPromptSubmit` hook installed (`neuralmind install-hooks`), any time
your prompt mentions a symbol that has a recorded decision, the rationale is
injected as context — alongside the usual synapse recall. So when you ask your
agent to "move `resolveOrgId` into middleware to clean it up", it sees *why that
was avoided* before it starts, and can push back instead of silently regressing.

Toggle it with `NEURALMIND_PROVENANCE_INJECT=0` (on by default, fails open —
a provenance miss never disrupts the prompt).

## Step 4 — Retract a decision you reversed *(v4.16.0+)*

A commit message can't be edited, so a reversed decision used to keep arriving
with every prompt that named its symbols. Now the decision store holds each
trailer's status. `neuralmind decisions scan .` imports the trailers in
recent history into it. Run it once; after that the post-commit hook from
`neuralmind init-hook .` runs it for you (re-run `init-hook` if you installed
the hooks before v4.16.0). Then:

```bash
neuralmind decisions query "resolveOrgId" --status ALL   # find the trailer's id (STALE ones too)
neuralmind decisions invalidate <id> --reason "moved into middleware in #812"
```

The prompt hooks and `neuralmind why` stop showing it. A later commit, pull,
merge or rebase that changes the files the trailer's commit changed marks it
STALE, and the hooks
show it with `[STALE: its code changed after this was decided; check it still
holds]` until you run `neuralmind decisions restore <id>` or invalidate it.
Importing again never brings an invalidated trailer back, and a rebase keeps
its id, since the id comes from the rationale. A trailer is judged against the
code its own commit stored, so one whose files changed since comes in STALE.

The status lives in `.neuralmind/memory.db`, which isn't committed: it applies
to your clone. A teammate who wants the same retraction runs the same
`invalidate`.

## Why git history is the store

The commit trailer holds the decision; the decision store only holds its
status:

- **Nothing to drift.** The rationale can't fall out of sync with the code,
  because it's attached to the commit that changed the code.
- **Retroactive.** Adopt the trailer today and `neuralmind why` reads every
  decision already in your history — no migration, no re-index.
- **As durable as your code.** A decision is exactly as permanent, and exactly
  as auditable, as the commit that carries it.

## Honest scope

- This *captures* rationale — it does not *infer* it. No trailer, no memory.
- Matching is lexical over subjects, not semantic; name the symbols you mean.
- Harvest reads recent history (default last 300 commits).

## Related

- [Blast radius before a rename](./blast-radius-before-a-rename.md) — the
  structural "what does this touch?" complement to the "why is it like this?"
  answer here.
