# NeuralMind v0.44.0 — the odd one out, and the coverage that lies

v0.43.0 gave the graph the *reason why* (decision provenance). v0.44.0 finishes
the **"Surface what you can't see"** theme with the other two things a *flat
list* can't tell you: **which member is wrong**, and **which test lies**.

## What's in this release

| Feature | Surfaces the… | Surface |
|---------|---------------|---------|
| **Cohesion outlier detection** | *odd one out* — the cluster member that skips a pattern its peers share | `NEURALMIND_SYNAPSE_OUTLIERS` (prompt injection) |
| **`neuralmind gaps`** | *coverage that lies* — endpoints "green" only in mock mode, never live-DB | `neuralmind gaps` |

Both are additive and off-by-default where they touch the hot path; default
retrieval stays byte-identical.

## 1. Cohesion outlier detection — flag the *odd one out*

Spreading-activation recall returns a flat ranked list: it tells you what
co-activates, not which member *breaks* the cluster's shared pattern. When ten
handlers route `orgId` through `resolveOrgId` and one passes a bare string, the
odd one out is exactly the line that ships a bug — and it looks like every other
cluster member to a flat list.

With `NEURALMIND_SYNAPSE_OUTLIERS=1`, the `UserPromptSubmit` injection adds a
cohesion check: it finds an associate most of a surfaced cluster links to, then
flags the members that skip it.

```
## NeuralMind cohesion check
- `validateSession` skips `resolveOrgId` — 10 of its 10 cluster-peers (100%) use it.
  Likely the odd one out; verify before trusting it.
```

Opt-in, fails open, and reads neighbors straight from the synapse store (a few
SQLite lookups, no embedder work).

## 2. `neuralmind gaps` — the *coverage that lies*

An endpoint can pass its whole suite in **mock mode** — an in-memory store that
accepts any string where Postgres would reject a non-UUID foreign key — and read
as "green" right up until it hits a live database and throws. That's the P2003
shape: three passing tests, all `SKIP_PG`-guarded, zero live coverage.

`neuralmind gaps` scans a project's routes and tests and classifies each endpoint:

```
$ neuralmind gaps

Routes tested in-memory only (no live-DB coverage):
  POST /api/sessions            — 3 tests — all SKIP_PG  ❌
  GET  /.well-known/jwks.json   — 1 test — all SKIP_PG   ❌
Endpoints with no tests:
  POST /api/auth/jwk/rotate     ⚠️
Live-covered:
  GET  /health                  ✅
```

Phase 1 is Express + Jest (JS/TS): route paths are normalized across
`:id` / `{id}` / `${...}` / `*` styles, and a test "hits the real DB" when it
imports a real-DB fixture and isn't skip-guarded.

## What the agent actually sees post-install

| Agent | What changes | How to use it |
|-------|--------------|---------------|
| **Claude Code** | `neuralmind gaps` is callable; with `NEURALMIND_SYNAPSE_OUTLIERS=1`, cohesion outliers inject on prompts alongside synapse recall | Run `gaps` before trusting a green suite; ask about a symbol to see its cluster outlier |
| **Cursor / Cline** | Same via the shared hook + CLI | Provider-agnostic |
| **Generic MCP / CLI** | `neuralmind gaps [path]` | Call directly or wire into a pre-commit check |

## Configuration

| Env var | Default | Effect |
|---------|---------|--------|
| `NEURALMIND_SYNAPSE_OUTLIERS` | unset | `1` → add the cohesion outlier check to the `UserPromptSubmit` injection. Off by default; fails open. |

## Honest scope

- **Cohesion** needs a warm synapse graph; it's silent on a cold or internally
  consistent cluster (by design), and matching is over learned edges.
- **`gaps`** Phase 1 is Express/Jest heuristics (regex over JS/TS), not a full
  parser; it surfaces suspects to verify, not a proof of coverage, and does not
  cover other frameworks yet.

## Upgrade

```
pip install --upgrade neuralmind
```

Nothing to rebuild. `neuralmind gaps` works immediately; set
`NEURALMIND_SYNAPSE_OUTLIERS=1` if you want the cohesion check in prompt-time
recall. Together with v0.43.0's decision provenance, these complete the
"Surface what you can't see" trio.
