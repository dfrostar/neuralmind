# Data-Flow Query Feature Spec

**Date:** 2026-07-15  
**Type:** New capability — discovery/investigation layer  
**Priority:** High (prevents runtime bugs shipping to production)

---

## 1. Problem

NeuralMind indexes code nodes and their co-occurrence. But when the user asks *cross-cutting questions*, it returns flat lists instead of propagation graphs.

**Real case — CyberSentinel session 2026-07-15:**

> "Find every place that reads `req.auth.orgId` and feeds it to a Prisma write, so I can apply the `resolveOrgId` fix in all of them."

NeuralMind returned: files containing both "auth" and "orgId" (flat list).  
The actual answer needed: a **data-flow graph** showing the propagation through resolveOrgId → sessionAPI → store → Prisma → FK constraint.

Result: 10 of 11 sites were fixed, #11 (`validateSession`) was missed until live smoke caught it.

---

## 2. Feature: Data-Flow Queries

### 2.1 Command

```
neuralmind flow <source> [--depth N] [--sink <pattern>] [--format graph|text|json]
```

### 2.2 Source specification

```
# Named source from index
neuralmind flow req.auth.orgId

# From file:line
neuralmind flow src/lib/server.ts:215

# From function return
neuralmind flow resolveOrgId.return

# From class method parameter
neuralmind flow sessionAPI.createSession:orgId
```

### 2.3 Options

| Flag | Description | Default |
|------|-------------|---------|
| `--depth N` | Max call/data-transfer hops | 6 |
| `--sink <pattern>` | Stop traversal when reaching nodes matching pattern | none (full graph) |
| `--format` | Output format: `text` (paths), `graph` (dot/mermaid), `json` (raw edges) | `text` |
| `--backwards` | Reverse: trace *into* source, reading callers instead of callees | off |
| `--highlight-risk` | Color/type-code nodes by whether they're "type-unsafe" string→FK | on |
| `--test-aware` | Mark nodes tested with real DB vs. in-memory | on |

### 2.4 Example output

```
$ neuralmind flow req.auth.orgId --depth 6 --highlight-risk

source: req.auth.orgId (src/lib/server.ts:216)
│
├── sink: resolveOrgId() [SAFE — resolves to UUID]
│   └── call: prisma.organization.findFirst/findOrCreate
│
├── sink: sessionAPI.createSession(orgId) [RISK: string→uuid]
│   └── call: pgStore.create(orgId)
│       └── prisma.session.create({ org_id: ??? })
│           └── FK: organizations.id ← P2003 risk
│
├── sink: sessionAPI.listSessions(orgId) [SAFE — after fix]
│
├── ... (10 paths)
│
└── sink: sessionAPI.validateSession(parsed.data.sessionId, orgId) [UNFIXED]
    └── [test coverage: 3 cases — all SKIP_PG=1, no live Postgres]
```

---

## 3. Schema-Aware Static Analysis (Type Bridge)

### 3.1 Goal

Detect "string literal flows into FK-constrained column" without running code.

### 3.2 How it works

1. **Indexer enhancement** reads `schema.prisma` (or `.sql` migrations, or ORM models) and produces a **type map**:
   ```
   sessions.org_id → Organization.id (FK, uuid)
   jwk_sets.org_id → Organization.id (FK, uuid)
   sessions.created_by_id → User.id (FK, nullable uuid)
   ```

2. **Static check**: when a literal string flows into a query builder param whose DB column is UUID FK, flag as **P2003 RISK**.

3. **Integration**: `neuralmind flow` auto-flags risk nodes. A standalone `neuralmind audit` command scans the whole graph for unattributed risks.

### 3.3 Example

```
$ neuralmind audit --type type-risks

RISK: P2003 on sessions.org_id
  src/lib/server.ts:235 passes 'default' literal
    → sessionAPI.createSession(orgId)
      → prisma.session.create({ org_id: ??? })
  Fix: resolveOrgId() not called in this handler

RISK: P2003 on sessions.created_by_id
  src/lib/server.ts:236 passes req.auth?.sub (= 'smoke')
    → sessionAPI.createSession(…, createdBy)
      → prisma.session.({ created_by_id: ??? })
  Fix: add isUuid(createdBy) guard
```

---

## 4. Test Mode Awareness

### 4.1 Problem

An endpoint "tested" only with `MemorySessionStore` will pass tests but fail against Postgres. No current tooling surfaces this gap.

### 4.2 Command

```
neuralmind gaps [--layer tests|coverage|runtime]
```

### 4.3 Output

```
$ neuralmind gaps --layer runtime

Routes tested (in-memory only, 0/3 live PG):
  POST /api/sessions    — 3 tests (all SKIP_PG=1)
  GET  /api/sessions     — 2 tests (all SKIP_PG=1)
  GET  /.well-known/jwks.json — 1 test (SKIP_PG=1)

Endpoints with no tests:
  POST /api/auth/jwk/rotate
  GET  /api/costs/avoidance
```

---

## 5. Implementation Sketch

### Phase 1: Data-flow graph

- **Parse function signatures** (parameter names, return types).
- **Build call graph** — which function calls which, with argument mappings.
- **Parameter propagation** — when `arg_n` of caller maps to `param_m` of callee, mark the binding.
- **Render**: BFS/DFS from source; stop at sink; output as paths.
- **Index store**: lightweight SQLite table `param_flows(caller, callee, caller_arg, callee_param, file, line)`.

### Phase 2: Schema awareness

- Add a `TypeParser` for Prisma/TypeORM/Drizzle/Go GORM/Python SQLAlchemy.
- Extend the indexer to produce a `column_types` table.
- During flow traversal, check the terminal sink's column type; annotate if source is incompatible string.

### Phase 3: Test awareness

- Harvest `Jest.describe()` / `test()` names, route paths, and store SKIPs.
- Cross-reference: route → test exists? test → real DB check?
- Cache results; invalidate on test file changes.

---

## 6. User-Visible Behavior

| Command | Capability |
|---------|-----------|
| `neuralmind flow X` | Trace variable X through call chain |
| `neuralmind flow X --sink Y` | Reaches-Y paths only |
| `neuralmind audit` | Scan for type-unsafe string→FK flows |
| `neuralmind gaps` | Find endpoints with no live-DB test |

**Natural language bridge**: `neuralmind ask "where does orgId flow"` routes to `flow`. Same UX, different backend.

---

## 7. Non-Goals

- Symbolic execution — we don’t solve, just propagate names and types.
- Runtime tracing — this is pure static analysis. Existing tools (OpenTelemetry, pg_stat_statements) cover runtime.
- Inter-language — first version TS-only. Python/Go/Java after stabilization.

---

## 8. Acceptance Criteria

1. `neuralmind flow req.auth.orgId` on CyberSentinel returns 11+ paths, including the missed `validateSession` one.
2. `neuralmind audit` surfaces the two P2003 issues without any smoke test.
3. `neuralmind gaps` reports exact route:test:PG-coverage matrix.
4. Output is <1s for repos ≤5k nodes (matches current build speed).

---

## 9. Priority Rationale

Without this, cross-cutting concerns (auth, logging, type-safety, i18n) are invisible to NeuralMind's index. The graph is connected — but users can only read one node at a time. 

The target UX shifts NeuralMind from *"here are files that mention X"* to *"here is everywhere X goes and every way it can break."*
