# NeuralMind v0.40.0 — Schema artifacts: OpenAPI, SQL, and Protobuf

**The headline:** NeuralMind now indexes non-code schema artifacts alongside your source
— OpenAPI/AsyncAPI specs, SQL DDL, and Protocol Buffer definitions — so agents can answer
questions like "What does `POST /payments/charge` accept?" or "Which tables reference
`user_id`?" from the same compressed context window that covers your code.

## What changed

### Schema artifact indexing: OpenAPI, SQL, Protobuf

Three new extractors join the `graphify`-compatible document layer. Each emits
`document` nodes that the context selector folds into L1/L2 exactly like Markdown
headings — agents retrieve them via the same `neuralmind_query` and `neuralmind_search`
MCP tools, no new API surface.

**OpenAPI / AsyncAPI (`.yaml`, `.yml`)**

Parses the spec with `PyYAML` (falls back to JSON), then emits:

- One file-level node labelled by `info.title` (e.g. `Payments API`)
- One node per path+method, labelled by `summary` or `operationId` (e.g. `Charge a card`)
- One node per schema component (e.g. `schema:Payment`, `schema:ChargeRequest`)
- One node per AsyncAPI channel (e.g. `channel:payment.charged`)

Plain YAML config files (no `openapi`/`asyncapi`/`swagger` key) are silently skipped —
NeuralMind never indexes infrastructure config as API docs.

**SQL DDL (`.sql`)**

Regex-matches `CREATE TABLE`, `CREATE VIEW`, `CREATE PROCEDURE`, `CREATE FUNCTION`,
`CREATE TRIGGER`, `CREATE INDEX`, and `CREATE TYPE` statements, emitting one node per
object (e.g. `TABLE:accounts`, `VIEW:active_users`, `PROCEDURE:cleanup`).

**Protocol Buffers (`.proto`)**

Emits one node per `message`, `service`, `rpc`, and `enum` definition
(e.g. `service:UserService`, `rpc:GetUser`, `message:GetUserRequest`, `enum:Status`).

### What agents actually see

After `neuralmind build .` on a project with schema files:

```
$ neuralmind query . "What fields does the Payment schema have?"

L0 — entry point
  POST /payments/charge (api/openapi.yaml:L18)  ← operation node
  schema:Payment        (api/openapi.yaml:L54)  ← schema component node

L1 — same community
  schema:ChargeRequest  (api/openapi.yaml:L61)

L2 — related areas
  TABLE:payments        (db/schema.sql:L3)      ← SQL DDL node
  process_payment()     (payments/service.py:L42)

Total: 612 tokens  (down from ~18,400 for full-file paste)
```

The synapse layer learns cross-artifact associations the same way it learns
code co-activation: if an agent retrieves `POST /payments/charge` and then
`process_payment()`, that edge strengthens automatically.

### What it covers and what it doesn't

**Covered:**
- OpenAPI 2.x (`swagger`), 3.x (`openapi`), AsyncAPI 2.x/3.x (`asyncapi`)
- SQL `CREATE` statements (case-insensitive, `OR REPLACE`, `IF NOT EXISTS` variants)
- `.proto` messages, services, RPCs, enums (proto2 + proto3)

**Explicitly out of scope (disclosed):**
- OpenAPI `$ref` resolution — components are indexed as named nodes; cross-file
  `$ref` chains are not followed
- SQL `ALTER TABLE` / `INSERT` / `SELECT` — only DDL `CREATE` is indexed
- Protobuf `import` edges — files are indexed independently; cross-file
  message references are not resolved as graph edges
- `application/json` schemas embedded inline in response bodies — only
  top-level `components/schemas` (OAS 3.x) and `definitions` (OAS 2.x) are indexed
- GraphQL schemas (`.graphql`) — planned for v0.41.0

### Incremental rebuild support

Schema files participate in `neuralmind watch --reindex`. A changed `.yaml`,
`.sql`, or `.proto` re-extracts only that file's nodes on the next
`neuralmind build . --incremental` pass — same as `.py`/`.ts` files.

## Per-agent expectations

| Agent | What changes |
|---|---|
| **Claude Code** | `neuralmind_query` + `neuralmind_search` MCP tools now return API/DB/schema nodes alongside code nodes. No config change. |
| **Cursor** | Same — schema nodes surface in `@neuralmind` context blocks. |
| **Cline** | Same. |
| **Generic MCP** | No new tools. Schema nodes have `file_type: "document"` — same as Markdown nodes. |

## Upgrade

```bash
pip install --upgrade neuralmind
neuralmind build .   # re-index to pick up schema files
```

No breaking changes. Existing indexes continue to work; schema nodes are additive.
If `PyYAML` is not installed, `.yaml`/`.yml` OpenAPI files are silently skipped
(the rest of the index is unaffected). Install with `pip install neuralmind[yaml]`
or `pip install pyyaml` to enable them.
