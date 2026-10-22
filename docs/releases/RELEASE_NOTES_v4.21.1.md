# NeuralMind v4.21.1 — a feature branch's calls stay on the branch

**Type:** Patch release | **Theme:** the call graph each build seeds follows the checkout, so a branch's calls no longer reach the default branch's recall

Every build seeds the call and import edges it finds into the synapse layer,
so recall can follow the code's structure from the first query. Those seeds
went into the `shared` baseline, which every branch reads and nothing cleared.
A call you added on a feature branch was seeded there by the branch's build,
and after you switched back to `main` it was still recalled, at half weight,
until it decayed on the shared 60-day half-life. The same went for a call
deleted from the code.

Associations learned from use were never affected: they go into the branch's
own `branch:<name>` namespace, as they have since v0.24.0.

---

## What changed

### Call-graph seeds live in a `structural` namespace each build replaces

Seeds now go into a `structural` namespace that every build replaces with the
graph of the code checked out. After the `post-checkout` hook's rebuild (or any
build) on `main`, a feature branch's calls are gone from recall, and so is a
call deleted from the code.

- **Recall on a clean `main` doesn't change.** The merged read takes
  `structural` at 0.5, the weight the seeds had in `shared`.
- **It doesn't decay**: the next build replaces it.
- **It isn't published.** `neuralmind memory publish` exports `personal` and
  `shared`, so the team bundle no longer carries call-graph seeds; each
  teammate's own build writes theirs.
- **It's never the active namespace.** `NEURALMIND_NAMESPACE` or
  `memory_namespace` naming `structural` is ignored, since a build would wipe
  anything learned there.
- `neuralmind memory inspect .` lists it as its own row.

### Old copies in `shared`

Each seeding pass deletes the single-activation `shared` copies of the pairs it
seeds, so a current call isn't counted twice. A branch-only call already in
`shared` can't be told apart from team memory, so it stays and fades on its
60-day half-life.

### Still open

The `SYNAPSE_MEMORY.md` file written for Claude Code at session start lists
the strongest associations from every namespace, other branches' included.
Recall doesn't read them; the agent does see the file.

---

## What the agent sees

| Agent | Before (to v4.21.0) | After |
|---|---|---|
| Claude Code (hooks + MCP) | Prompt-time recall on `main` could name a file linked only by a call that exists on a feature branch, until it decayed | Recall follows the call graph of the code checked out |
| Cursor / Cline / generic MCP | The same, in `neuralmind_query` and search results | The same fix |
| Hermes-Agent plugin | The same, in the per-turn block | The same fix |

---

## Upgrading

`pip install -U neuralmind`, then build once (`neuralmind build .`) to fill
the `structural` namespace. Nothing else to change.

## Tests

- `tests/test_synapses.py`: a branch-only call is gone from the default
  branch's recall, and from every namespace, after switching back (on v4.21.0
  it was still recalled); a deleted call is dropped on rebuild; `structural`
  reads at the weight `shared` seeds had and doesn't decay; an empty graph
  empties it; seeding removes legacy `shared` seeds but keeps team memory.
- `tests/test_synapse_namespaces.py`: a `structural` override falls through
  to branch detection.
- `tests/test_team_memory.py`: a published bundle carries no call-graph seeds.
