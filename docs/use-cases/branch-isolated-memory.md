# Use Case: Branch-Isolated Memory & Shareable Team Baselines *(v0.24.0+)*

## What you're solving for

The synapse layer learns from how you actually work — which files co-fire,
what you edit next. That's the moat, but pre-v0.24 it had one store with one
view of the world, which created two real problems:

1. **Branch pollution.** A weekend refactor spike teaches the agent
   associations that are wrong on `main` ("`handlers.py` goes with
   `legacy_shim.py`"). The spike dies; the memory lingers.
2. **Unshareable experience.** A senior engineer's NeuralMind knows the
   codebase cold, and there was no sane way to hand that to the new hire
   without also handing over every personal quirk.

v0.24.0's **memory namespaces** solve both: `branch:<name>`, `personal`,
`shared`, and `ephemeral` memory live separately in the same store, and
recall reads a transparent, weighted merge.

## How the merged view works (the part worth understanding)

Reads default to **active namespace × 1.0 + personal × 0.8 + shared × 0.5**
— three published constants (`W_BRANCH` / `W_PERSONAL` / `W_SHARED` in
`neuralmind/synapses.py`), summed per edge. On the default branch the active
namespace *is* `personal`, so the merged view is identical to pre-namespace
behavior — nothing about your current setup changes until you branch.

Don't take the weighting on faith — trace it:

```bash
neuralmind query . "how does checkout work?" --trace --json | \
  python -c "import json,sys; [print(e) for e in json.load(sys.stdin)['trace']['events'] if e['kind']=='synapse_boost']"
# ... "namespace_contribution": {"branch:feature-x": 0.09, "shared": 0.045} ...
```

## Walkthrough 1 — keep a feature branch's memory out of main

```bash
git checkout -b feature-x
# ...work normally; hooks + watcher activations land in branch:feature-x...

neuralmind memory inspect .
# Active namespace: branch:feature-x  (schema v1)
# Namespace                  Edges    Weight  Transitions   Nodes
# branch:feature-x              34      6.20           12      28
# personal                     412     88.71          120     310

# Branch merged (or abandoned)? Drop exactly its memory:
neuralmind memory reset . --namespace branch:feature-x
```

The index, `personal`, `shared` — all untouched. `git checkout main` and the
agent is back on pure long-term memory.

## Walkthrough 2 — ship a team baseline (the PRD 8 on-ramp)

On the machine that knows the codebase:

```bash
neuralmind memory export . --namespace personal -o team-baseline.json
# Versioned JSON bundle reusing the IR's IRSynapse shape
```

On a teammate's (or a fresh dev container's) checkout:

```bash
neuralmind memory import team-baseline.json --namespace shared
```

Their recall now blends the team's priors at 0.5× under everything they
learn themselves — informative, never louder than their own experience.
Import validates the bundle's format + version first and merges weights by
MAX, so re-importing (say, in a recurring CI step) is **idempotent**.

## Walkthrough 3 — throwaway exploration that leaves no trace

```bash
NEURALMIND_NAMESPACE=ephemeral neuralmind query . "what if we inline the cache layer?"
```

`ephemeral` decays fast (0.25/tick, no long-term-potentiation floor) and is
cleared outright at the next session start and on daemon shutdown. Spelunk
freely; the brain forgets it by design.

## Pinning and overriding

| Mechanism | Scope | Example |
|---|---|---|
| `NEURALMIND_NAMESPACE` env var | One process | `NEURALMIND_NAMESPACE=ephemeral neuralmind query .` |
| `memory_namespace:` in `neuralmind-backend.yaml` | The project | A CI box pinned to `shared` so it only builds team baseline |
| git branch (automatic) | The checkout | `branch:feature-x` while you're on `feature-x` |
| *(nothing)* | Fallback | `personal` — non-repo, detached HEAD, or the default branch |

## What about my existing memory?

It migrates **in place, losslessly**, the first time v0.24.0 opens the
store: the three tables are rebuilt with `namespace` in their primary keys
inside one transaction (rollback on any failure), and every existing row
lands in `personal` with identical weights and counts. The single-namespace
behavior you had *is* the `personal` namespace — that's the compatibility
contract, and a dedicated no-data-loss test enforces it.

## Related

- [Release Notes v0.24.0](../../RELEASE_NOTES_v0.24.0.md) — full PRD 4 details
- [Multi-agent codebase](./multi-agent.md) — every agent shares the same
  namespaced store, so isolation applies across Claude Code + Cursor + Cline
- [Growing monorepo](./growing-monorepo.md) — keeping the *index* fresh;
  namespaces keep the *memory* clean
