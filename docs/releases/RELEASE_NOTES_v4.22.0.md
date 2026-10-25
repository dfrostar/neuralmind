# NeuralMind v4.22.0 — a feature branch's calls and memory stay on the branch

**Type:** Minor release | **Theme:** the call graph each build seeds, and the memory file Claude Code loads, follow the checkout, so a feature branch no longer reaches the default branch's recall or the agent's memory file

Every build seeds the call and import edges it finds into the synapse layer,
so recall can follow the code's structure from the first query. Those seeds
went into the `shared` baseline, which every branch reads and nothing cleared.
A call you added on a feature branch was seeded there by the branch's build,
and after you switched back to `main` it was still recalled, at half weight,
until it decayed on the shared 60-day half-life. The same went for a call
deleted from the code.

Recall of associations learned from use was never affected: they go into the
branch's own `branch:<name>` namespace, as they have since v0.24.0. But
`SYNAPSE_MEMORY.md`, the memory file Claude Code loads at session start,
listed the strongest associations from every namespace, so on `main` the agent
saw what it had learned on every other branch.

---

## What changed

### Call-graph seeds live in a `structural` namespace each build replaces

Seeds now go into a `structural` namespace that every build replaces with the
graph of the code checked out. After the `post-checkout` hook's rebuild (or any
build) on `main`, a feature branch's calls are gone from recall, and so is a
call deleted from the code.

- **Recall on a clean `main` doesn't change.** The merged read takes
  `structural` at 0.5, the weight the seeds had in `shared`. In a store an
  earlier release seeded, the old copies in `shared` add to it until they
  fade (below).
- **It doesn't decay**: the next build replaces it.
- **It isn't published.** `neuralmind memory publish` exports `personal` and
  `shared`, so the team bundle no longer carries call-graph seeds; each
  teammate's own build writes theirs.
- **It's never the active namespace.** `NEURALMIND_NAMESPACE` or
  `memory_namespace` naming `structural` is ignored, since a build would wipe
  anything learned there.
- `neuralmind memory inspect .` lists it as its own row.

### Old copies in `shared`

The seeds earlier releases wrote to `shared` are left there. Their rows look
like team memory (an edge approved with `neuralmind memory review-approve` or
imported from a bundle is a single-activation `shared` row too), so deleting
them would delete approved memory. Builds no longer refresh them, so they fade
on the 60-day shared half-life. Until then, a call still in the code is
counted in both `shared` and `structural`, and a branch-only call already in
`shared` is still recalled.

### The memory file follows the checkout too

`SYNAPSE_MEMORY.md` (and its copy in Claude Code's auto-memory directory) now
holds only what recall reads on the checkout: the active namespace (the
branch's own on a feature branch), `personal`, `shared` and `structural`.

- **Another branch's memory isn't in it**: not its pairs, its hub nodes or its
  "what typically comes next" transitions, and not a stale `ephemeral`
  session's either.
- **The header counts the same namespaces and names them**, in a new
  `- Namespaces:` line, so the edge, node and transition counts describe the
  file instead of the whole store.
- **Hub nodes count a pair once.** A pair held in two namespaces (learned
  from use and also a call) was two connections; it is one, as recall's own
  degree count has it. The list now shows up to eight hubs, the export's
  `top_hubs` default; `stats()` had capped it at five.
- The hooks write the file at session start, so it shows the branch checked
  out then; the MCP `neuralmind_export_synapse_memory` tool writes the view of
  the branch the server sees.

---

## What the agent sees

| Agent | Before (to v4.21.0) | After |
|---|---|---|
| Claude Code (hooks + MCP) | Prompt-time recall on `main` could name a file linked only by a call that exists on a feature branch, until it decayed; `SYNAPSE_MEMORY.md` listed associations learned on every branch | Recall follows the call graph of the code checked out, and `SYNAPSE_MEMORY.md` holds only what recall reads on it |
| Cursor / Cline / generic MCP | The same, in `neuralmind_query` and search results, and in the file `neuralmind_export_synapse_memory` writes | The same fix |
| Hermes-Agent plugin | The same, in the per-turn block | The same fix |

---

## Upgrading

`pip install -U neuralmind`, then build once (`neuralmind build .`) to fill
the `structural` namespace. The memory file is rewritten at the next session
start. Nothing else to change.

## Tests

- `tests/test_synapses.py`: a branch-only call is gone from the default
  branch's recall, and from every namespace, after switching back (on v4.21.0
  it was still recalled); a deleted call is dropped on rebuild; `structural`
  reads at the weight `shared` seeds had and doesn't decay; an empty graph
  empties it; seeding never deletes a `shared` row, approved edges included.
- `tests/test_synapse_namespaces.py`: a `structural` override falls through
  to branch detection.
- `tests/test_team_memory.py`: a published bundle carries no call-graph seeds.
- `tests/test_synapse_memory.py`: on `main` the memory file leaves out what
  was learned on `feature-x` (pairs, hubs and transitions), and its header
  counts only what it covers; on `feature-x` it includes that branch and
  `personal` but not another branch; the export writes the view of the
  namespace it is given; a pair in two namespaces is one hub connection.
