# NeuralMind v0.47.0 — Impact: blast radius under a name you'd actually reach for

A Reddit comparison against GitNexus flagged "no `impact` tool" as a gap. It
wasn't quite right — `neuralmind structural --blast-radius` has answered "what
depends on this?" since v0.42.0 — but the critique had a real point buried in
it: nobody finds a boolean flag on a differently-named command when they're
looking for "impact analysis." v0.47.0 gives the same capability a name an
agent (or a human) would actually reach for, plus richer output.

```bash
neuralmind impact hash_password --depth 2
```

## What you get

```
Impact of auth_handlers_hash_password (semantic match) — depth 2:
  h1  calls          authenticate_user() — handlers.py

1 dependent(s).
```

Each dependent row now carries its **hop** (how many steps away) and its
**relation** (`calls`/`inherits`/`imports_from`/`implements`) — not just a bare
id, which is all `structural --blast-radius` returned before this release.
`--json` gives `{symbol, depth, relations, resolution, resolved_node,
dependents, count}`, where `resolution` tells you whether `symbol` matched
exactly or was resolved via the closest semantic hit.

The MCP tool is `neuralmind_impact(project_path, symbol, depth)` — same shape,
agent-callable.

## What's actually new vs. what's just renamed

Nothing about the underlying traversal changed. `impact` calls the exact same
`StructuralIndex` reverse-dependency BFS `structural --blast-radius` always
has — same hub-normalization, same cycle-safety, same relation set. What's new:

- **A name that matches the question.** "What's the blast radius of this
  change?" maps to `impact`, not to `structural --blast-radius`.
- **Per-dependent hop and relation attribution**, instead of a flat id list.
- **Resolution transparency** — `exact` vs `semantic` vs `none` — so a caller
  knows whether `symbol` was a literal node id or a best-effort match.

`structural --blast-radius` isn't deprecated or changed — it's still there,
byte-identical, for anyone already using it. Internally it's now a one-line
wrapper over the same `blast_radius_detail()` this release added, so there is
exactly one traversal implementation, not two drifting in parallel.

## Honest scope

- No confidence scoring — hop distance and relation type are the signal, not
  a probability.
- No pre-computation — the traversal runs on request from the in-memory
  structural index, not cached at build time.
- One known imprecision: `imports_from` and `imports` edges both surface as
  `imports_from` on a dependent row (they share one traversal view; per-edge
  relation tracking would roughly double the index's memory footprint for a
  distinction this release doesn't need).

See [docs/BRD-IMPACT-TOOL.md](docs/BRD-IMPACT-TOOL.md) and
[docs/TRD-IMPACT-TOOL.md](docs/TRD-IMPACT-TOOL.md) for the full requirements
and design rationale, and
[docs/use-cases/blast-radius-before-a-rename.md](docs/use-cases/blast-radius-before-a-rename.md)
for the walkthrough.
