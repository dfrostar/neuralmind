# NeuralMind v0.24.0 — memory namespaces & branch isolation

**The headline:** the learned synapse layer is now **namespace-aware**
(**PRD 4**). Branch experiments, your personal long-term memory, an imported
team baseline, and throwaway session scratch live in **separate namespaces**
inside the same store — `branch:<name>`, `personal`, `shared`, `ephemeral` —
so a weekend spike on a feature branch can't pollute what the agent learned
about `main`. Reads stay smart by default: a **transparent merged view**
prioritizes recent branch-local context while retaining useful long-term
priors, with the weighting published as three constants you can read in one
line. Existing learned memory migrates **in place, losslessly** — everything
you've taught NeuralMind so far simply becomes the `personal` namespace.

## What the agent actually sees post-install

Nothing breaks, and on the default branch nothing even changes: the active
namespace *is* `personal` and merged reads return the same weights as
v0.23.0. The new behavior appears the moment you branch:

- On `git checkout -b feature-x`, hook and watcher activations start landing
  in `branch:feature-x`. The agent's recall now *prefers* what you've been
  touching on this branch, backed by your long-term `personal` memory at 0.8×
  and any imported `shared` team baseline at 0.5×.
- `neuralmind stats` and the new `neuralmind memory inspect` show exactly
  which namespace every learned edge lives in.
- When the branch merges and you delete it, `neuralmind memory reset
  --namespace branch:feature-x` clears just that memory — the index and every
  other namespace are untouched.
- A traced query (`neuralmind query . "..." --trace`, PRD 3) now attributes
  each synapse boost to the namespace that drove it via a
  `namespace_contribution` field — the merged weighting is inspectable, not
  folklore.

## What's new

- **Namespaced memory writes.** Every synapse, transition, and node
  activation records a namespace. The active namespace resolves
  automatically: `NEURALMIND_NAMESPACE` env var → `memory_namespace:` pinned
  in `neuralmind-backend.yaml` → `branch:<name>` on a non-default git branch
  → `personal`. Detection is best-effort stdlib `git rev-parse` with a
  3-second timeout — a detached HEAD, a missing git, or a non-repo all
  degrade safely to `personal` and never fail a write. Long-lived processes
  (the daemon's warm registry, the MCP server's mind cache) notice a
  `git checkout` between writes via a cheap `.git/HEAD` fingerprint and
  re-target the store automatically — branch isolation never requires a
  restart.

- **Lossless in-place schema migration (v0 → v1).** `namespace` joins the
  primary keys of all three tables — SQLite can't alter a PK, so the store
  rebuilds each table (rename → create v1 → copy into `personal` → drop)
  inside a **single IMMEDIATE transaction** that rolls back wholesale on any
  failure. Your existing memory is preserved verbatim under `personal`; a
  `schema_version` row in `meta` records the upgrade; re-opening is a no-op.
  A mandatory stdlib-only test opens a real pre-namespace database and proves
  every edge, transition, and activation survives with identical weights.

- **Transparent merged reads.** By default, recall (`spread`), `neighbors`,
  `next_likely`, `edges`, and `transitions` merge the **active namespace at
  1.0×** (`W_BRANCH`), **personal at 0.8×** (`W_PERSONAL`), and **shared at
  0.5×** (`W_SHARED`) — explicit module-level constants with the formula
  documented beside them, because "weighting logic becomes hard to reason
  about" is this feature's #1 risk. Passing `namespaces=[...]` (or
  `--namespace` on the CLI) reads exactly one namespace at raw weights, so
  inspection and export always see true values.

- **`neuralmind memory {inspect,reset,export,import}`.**
  - `inspect` — contribution by namespace (edges, weight, transitions,
    nodes), the active namespace, and the schema version; `--json` for
    tooling. Also folded into `neuralmind stats`.
  - `reset --namespace N` — clear **one** namespace without deleting the
    project index or any other namespace.
  - `export --namespace N [-o file]` — a portable, versioned JSON bundle
    reusing the IR's `IRSynapse` shape (this is the PRD 8 team-memory
    on-ramp).
  - `import <file> [--namespace N]` — validates format + version, then
    merges into the target namespace **idempotently** (weights merge by MAX,
    so importing the same bundle twice never double-counts).

- **Per-namespace decay / TTL.** `decay()` now applies a retention policy
  per namespace: `shared` is sticky (0.005/tick — a team baseline shouldn't
  evaporate because one developer changed focus), `personal` and `branch:*`
  decay at the existing rates with LTP intact, and `ephemeral` fades fast
  (0.25/tick, **no LTP floor**) and is **cleared outright at session
  boundaries** — the SessionStart hook drops the previous session's scratch,
  and the daemon clears it for warm projects on shutdown.

- **Namespace-attributed traces (PRD 3 × PRD 4).** Synapse-boost trace
  events gain a `namespace_contribution` map showing how much boost energy
  arrived through each namespace's edges — and the attribution is computed
  only on traced queries, so the untraced hot path pays nothing.

- **Public API.** `SynapseStore(db, namespace=...)`, `namespaces=[...]` on
  all read methods, `clear_namespace()`, `spread_with_contributions()`,
  `import_edges()` / `import_transitions()`, `resolve_namespace()`, and
  `export_synapse_bundle` / `import_synapse_bundle` / `validate_synapse_bundle`
  — all stdlib-only, like the rest of the synapse layer.

## Why it matters

- **Branch experiments stop poisoning trunk memory.** A refactor spike
  teaches the agent associations that are wrong on `main`. Now those edges
  live (and die) with the branch.
- **Team memory becomes shippable.** `shared` plus versioned export/import
  bundles is the concrete on-ramp to PRD 8's portable team memory — a
  senior engineer can export what NeuralMind learned and a new teammate can
  import it as priors that inform recall without shouting over their own
  experience.
- **The migration is the feature.** A learned memory store is only worth
  having if upgrades can't corrupt it. The single-transaction rebuild plus
  the no-data-loss test is the pattern future schema bumps follow.

## Per-agent expectations

| Agent | What changes in v0.24.0 |
|-------|--------------------------|
| **Claude Code** | Hook activations (SessionStart / UserPromptSubmit / PostToolUse / watcher) now land in the branch's namespace automatically; `SYNAPSE_MEMORY.md` still exports the full picture. SessionStart additionally clears the previous session's `ephemeral` scratch. No setup change. |
| **Cursor / Cline** | Same MCP tools. Recall served through them now uses the merged namespace view (branch-local context first). No tool-surface change in this release. |
| **Generic MCP client** | No new tools yet; namespace-scoped MCP tool parameters ride with a later phase. Behavior change is the merged read prioritization, which is transparent and documented. |
| **Contributors / CI** | `SynapseStore` gains `namespace=` / `namespaces=` seams; `tests/test_synapse_namespaces.py` (stdlib-only) covers migration, isolation, weighting, decay policy, bundles, and mocked-git resolution. The v0→v1 migration test is the template for future schema bumps. |

## How to use it

```bash
# See what's learned, per namespace
neuralmind memory inspect .
neuralmind stats .            # includes the same breakdown

# Pin a namespace for a process (e.g. throwaway exploration)
NEURALMIND_NAMESPACE=ephemeral neuralmind query . "how does auth work?"

# Clear a merged branch's memory — index and other namespaces untouched
neuralmind memory reset . --namespace branch:feature-x

# Ship learned memory to a teammate (PRD 8 on-ramp)
neuralmind memory export . --namespace personal -o team-baseline.json
# ...on their machine:
neuralmind memory import team-baseline.json --namespace shared

# Read one namespace at raw weights
neuralmind next . src/auth.py --namespace branch:feature-x
```

```python
from neuralmind import SynapseStore, default_db_path, resolve_namespace

ns = resolve_namespace(".")                      # e.g. "branch:feature-x"
store = SynapseStore(default_db_path("."), namespace=ns)
store.reinforce(["auth.py", "session.py"])       # lands in the active namespace
store.neighbors("auth.py")                       # merged: branch 1.0 + personal 0.8 + shared 0.5
store.neighbors("auth.py", namespaces=["shared"])  # one namespace, raw weights
```

Pin a project to a namespace in `neuralmind-backend.yaml`:

```yaml
memory_namespace: shared   # e.g. a CI box that should only build team baseline
```

## Honest scope & what's next

- **Phases 1–2 ship now** (namespace tagging + migration; CLI controls +
  stats-by-namespace + branch resolution). The merged read view also ships
  because it's what keeps the default experience unchanged on `main`.
- **Phase 3–4 refinements next:** namespace-scoped MCP tool parameters,
  smarter cross-branch promotion (graduating a branch's proven edges into
  `personal` on merge), and the full PRD 8 team-memory story (signed
  bundles, CI/devcontainer hydration) on top of today's export/import.
- **Out of scope by design:** identity/RBAC, cloud sync, multi-tenant hosted
  storage. Namespaces are local separation, not access control.
