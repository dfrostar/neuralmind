# Data-Flow Query Feature Spec

**Date:** 2026-07-15 (revised 2026-07-16, incorporating DeepSeek preliminary review)  
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
| `--async-aware` | Model Promise chain boundaries, `.then()` edges, and event emitter callbacks | on |

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
├── ... (9 paths)
│
└── sink: sessionAPI.validateSession(parsed.data.sessionId, orgId) [UNFIXED]
    └── [test coverage: 3 cases — all SKIP_PG=1, no live Postgres]
    └── [dispatch: polymorphic — 1 override determined, 0 unknown]
```

---

## 3. Schema-Aware Static Analysis (Type Bridge)

### 3.1 Goal

Detect "string flows into FK-constrained column" without running code.

### 3.2 How it works

1. **Indexer enhancement** reads `schema.prisma` (or other schema sources) and produces a **type map**:
   ```
   sessions.org_id → Organization.id (FK, uuid)
   jwk_sets.org_id → Organization.id (FK, uuid)
   sessions.created_by_id → User.id (FK, nullable uuid)
   ```

2. **Static check**: during flow traversal, check the terminal sink's column type; annotate if source is incompatible string. Covers type compatibility matrix including:
   - Nullable vs non-nullable (e.g. `String?` accepts `null` literal)
   - Branded/opaque types (custom UUID deep path)
   - Enum types string-compatible at runtime

3. **Integration**: `neuralmind flow` auto-flags risk nodes. A standalone `neuralmind audit` command scans the whole graph for unattributed risks.

### 3.3 Schema drift detection

Schemas drift from actual DB due to manual migrations or failed rollbacks. Detection via checksum comparison between `schema.prisma` and the actual database schema (via `\d table_name` in Postgres, or parsing `migration_lock.toml` + migration history). Reported as drift warnings.

### 3.4 Example

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

### 4.3 Test detection heuristics

Route-path matching handles:
- Template literals (`` /api/users/${userId} ``)
- String concatenation (`'/api/' + resource`)
- Separately-defined constants and config files
- Different parameter syntax (`:id` vs `{id}` vs `(*)`) via normalization

"Real DB check" definition: test imports from `@/db` / `@/repositories`, or uses `testDb` fixture, or asserts against `prisma` mock directly. Mocks of `prisma.user.findUnique` are flagged as indirect.

### 4.4 Output

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

### Phase 1: Async-aware TS call graph

- **Scope**: TypeScript only. Module-level functions first; class methods documented as best-effort with polymorphic dispatch flagged as "unknown sink".
- **Parse function signatures** (parameter names, return types, inferred types via `tsc` API or tree-sitter with type inference).
- **Build call graph** — which function calls which, with argument mappings.
- **Async modeling** — follow `.then()` chains, `await` boundaries, and event emitter callbacks as first-class edges.
- **Higher-order functions / closures** — limited support; flagged as "indirect flow" when unresolved.
- **Parameter propagation** — when `arg_n` of caller maps to `param_m` of callee, mark the binding.
- **Polymorphic dispatch** — explicitly flagged as "[dispatch: polymorphic — N overrides determined, M unknown]" in output.
- **Render**: BFS/DFS from source; stop at sink; bounded by `--depth`.
- **Index store**: SQLite table `param_flows(caller, callee, caller_arg, callee_param, file, line)` with materialized adjacency paths.
- **Incremental analysis**: graph is rebuilt only for changed subtrees on code edits (watch-based rebuild).

### Phase 2: Schema awareness

- Add a `TypeParser` for Prisma only initially.
- New parsers (TypeORM/Drizzle/GORM/SQLAlchemy) plugged in behind a `SchemaSource` abstraction.
- Extend the indexer to produce a `column_types` table.
- During flow traversal, check the terminal sink's column type; annotate if source is incompatible string.

### Phase 3: Cross-repo / monorepo support

- Shared types/interfaces in a `common` package.
- RPC/API calls between services (OpenAPI/gRPC proto consumption).
- Message queue events (Kafka, SQS, RabbitMQ) — documented but deferred.

### Phase 4: Test awareness

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

- Symbolic execution — we don't solve, just propagate names and types.
- Runtime tracing / dynamic analysis — Phase 1 is pure static. Existing tools (OpenTelemetry, pg_stat_statements) cover runtime. Hybrid approach deferred to Phase 3.
- Cross-language — **Phase 1: TypeScript only.** Go/Java have DI/reflection defeating naive AST analysis. Python best-effort via `ast` + type hints in Phase 2. Java/Go explicitly deferred.
- Cross-repo / monorepo — Phase 1 operates within a single repo. Monorepo support in Phase 3.
- LSP integration — deferred; initial build uses existing AST infrastructure. LSP may replace per-language parsers in Phase 2+.
- Whole-program pointer analysis — polymorphic dispatch is flagged "unknown", not resolved.

---

## 8. Acceptance Criteria

1. On CyberSentinel, `neuralmind flow req.auth.orgId` returns **≥11 true-positive paths** with **false-positive rate <20%** against a hand-labeled benchmark (N=25 golden paths across 3 routes).
2. `neuralmind audit --type type-risks` surfaces both P2003 issues without any smoke test.
3. `neuralmind gaps --layer runtime` reports route:test:PG-coverage matrix acurrately against the actual SKIP_PG distribution.
4. Output is **<1s for repos ≤5k nodes**, **<3s for repos ≤100k nodes**.
5. Incremental rebuild on file change is **<500ms** for projects ≤5k nodes.

---

## 9. Priority Rationale

Without this, cross-cutting concerns (auth, logging, type-safety, i18n) are invisible to NeuralMind's index. The graph is connected — but users can only read one node at a time.

The target UX shifts NeuralMind from *"here are files that mention X"* to *"here is everywhere X goes and every way it can break."*

> **Preliminary — requires human review before sign-off.**
