# NeuralMind v0.43.0 — Surface what you can't see

Three features, one thesis: the graph surfacing the thing a *flat list* hides.
NeuralMind has always been able to tell you what's related to a query. This
release adds three things it couldn't say before — **the odd one out**, **the
coverage that lies**, and **the reason why** — each the kind of gap that ships a
bug or wastes an afternoon precisely because nothing made it visible.

## What's in this release

| Feature | Surfaces the… | Surface |
|---------|---------------|---------|
| **Decision provenance** | *reason why* — rationale a human authored, recalled from a `Decision:` git trailer | `neuralmind why` · `NEURALMIND_PROVENANCE_INJECT` |
| **Cohesion outlier detection** | *odd one out* — the cluster member that skips a pattern its peers share | `NEURALMIND_SYNAPSE_OUTLIERS` (prompt injection) |
| **`neuralmind gaps`** | *coverage that lies* — endpoints "green" only in mock mode, never live-DB | `neuralmind gaps` |

All three are additive and off-by-default where they touch the hot path; default
retrieval stays byte-identical.

---

## 1. Decision provenance — recall *why* code is the way it is

NeuralMind indexes what a codebase **is**; it never indexed **why**. So "why is
`resolveOrgId` per-handler instead of middleware?" had an answer — "avoids Prisma
on `/health`, `/metrics`, `/token`; keeps tests simple" — that lived in a human's
head, never in any artifact the graph could recall.

Add a `Decision:` trailer to the commit that makes the change (backticked symbols
become subjects; an explicit `Subjects:` line is honored too):

```
Decision: resolveOrgId is per-handler, not middleware — avoids Prisma on
          /health, /metrics, /token; keeps tests simple.
Subjects: `resolveOrgId`, `authMiddleware`
```

Then recall it:

```
$ neuralmind why "why is resolveOrgId per-handler?"

## NeuralMind decision provenance
- `resolveOrgId`, `authMiddleware`: resolveOrgId is per-handler … (see commit ba25fed)
```

**Git history is the store** — the trailer is the persistence, so there's no
database to build or drift, and it works retroactively on commits already in
history. At prompt time, matching decisions inject on `UserPromptSubmit` alongside
synapse recall (`NEURALMIND_PROVENANCE_INJECT`, default on, fails open).

## 2. Cohesion outlier detection — flag the *odd one out*

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

## 3. `neuralmind gaps` — the *coverage that lies*

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
| **Claude Code** | `neuralmind why` and `neuralmind gaps` are callable; with the hook installed, decisions inject on prompts (and outliers with `NEURALMIND_SYNAPSE_OUTLIERS=1`) | Ask "why is X like this?"; run `gaps` before trusting a green suite |
| **Cursor / Cline** | Same via the shared hook + CLI | Provider-agnostic |
| **Generic MCP / CLI** | `neuralmind why <query>`, `neuralmind gaps [path]` | Call directly or wire into a pre-commit / pre-edit check |

## Configuration

| Env var | Default | Effect |
|---------|---------|--------|
| `NEURALMIND_PROVENANCE_INJECT` | `1` (on) | `0` → skip decision injection in the `UserPromptSubmit` hook. Fails open. |
| `NEURALMIND_SYNAPSE_OUTLIERS` | unset | `1` → add the cohesion outlier check to the injection. Off by default; fails open. |

## Honest scope

- **Provenance** captures rationale, it doesn't infer it — no trailer, no memory;
  matching is lexical over subjects.
- **Cohesion** needs a warm synapse graph; it's silent on a cold or internally
  consistent cluster (by design).
- **`gaps`** Phase 1 is Express/Jest heuristics (regex over JS/TS), not a full
  parser; it does not cover other frameworks yet.

## Upgrade

```
pip install --upgrade neuralmind
```

Nothing to rebuild. `neuralmind why` and `neuralmind gaps` work immediately;
start adding `Decision:` trailers and set `NEURALMIND_SYNAPSE_OUTLIERS=1` if you
want the cohesion check.
