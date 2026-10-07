<!-- neuralmind:example-file — annotations here are syntax examples, not evidence. -->
# CLI Reference

Complete command-line interface documentation for NeuralMind.

## Table of Contents

- [Overview](#overview)
- [Global Options](#global-options)
- [Commands](#commands)
  - [build](#build)
  - [scan-for-secrets](#scan-for-secrets)
  - [query](#query)
  - [wakeup](#wakeup)
  - [search](#search)
  - [benchmark](#benchmark)
  - [probe](#probe-v0270)
  - [stats](#stats)
  - [validate](#validate-v0230)
  - [doctor](#doctor-v0120)
  - [eval](#eval-v0140)
  - [ingest-content](#ingest-content-v340)
  - [learn — document ingestion](#learn-document-ingestion-v1110)
  - [learn (deprecated, pre-v1.11.0)](#learn-deprecated-v0250)
  - [self-improve status](#self-improve-status-v0260)
  - [next](#next-v0110)
  - [memory](#memory-v0240)
  - [cognition-loop](#cognition-loop)
  - [skeleton](#skeleton)
  - [structural](#structural-v0420)
  - [last](#last-v0100)
  - [recap](#recap-v480)
  - [install-hooks](#install-hooks)
  - [install-hermes-plugin](#install-hermes-plugin-v490)
  - [init-hook](#init-hook)
  - [decisions](#decisions-v410)
  - [drift](#drift-v320)
  - [compliance](#compliance-v314)
  - [ci-check](#ci-check-v314)
  - [export](#export-v314)
  - [watch](#watch-v040)
  - [serve](#serve-v054-live-feed-v060)
  - [daemon](#daemon-v0230)
  - [savings](#savings-v0400)
  - [review](#review-v0390)
  - [onboarding](#onboarding-v170)
  - [team governance](#team-governance)
  - [optimize-docs](#optimize-docs-v172)
  - [license — issuer-side](#license--issuer-side)
- [Exit Codes](#exit-codes)
- [Environment Variables](#environment-variables)
- [Examples](#examples)

---

## Overview

NeuralMind provides a command-line interface for building neural indexes, querying codebases with natural language, and managing knowledge graphs.

```bash
neuralmind [OPTIONS] COMMAND [ARGS]
```

### Getting Help

```bash
# General help
neuralmind --help

# Command-specific help
neuralmind build --help
neuralmind query --help
```

---

## Global Options

| Option | Description |
|--------|-------------|
| `--help` | Show help message and exit |
| `--version` | Show version number |

---

## Commands

### audit recent *(v3.1.4+)*

Query recent audit trail events.

#### Arguments

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `-n` | No | `10` | Number of events to show |
| `--category` | No | — | Filter by category (backend, compliance, audit) |
| `--action` | No | — | Filter by action (build, query, export) |
| `--actor` | No | — | Filter by actor |
| `--since` | No | — | Filter by timestamp (ISO 8601) |

#### Output

Recent audit events in tabular format.

#### Examples

```bash
# Show last 10 audit events
neuralmind audit recent

# Show last 20 events since a specific date
neuralmind audit recent -n 20 --since "2026-08-01"

# Show only backend builds
neuralmind audit recent --category backend --action build
```

#### Prerequisites

Requires an initialized project with audit trail.

### audit verify

Check the hash chain of `.neuralmind/audit_events.jsonl`.

```bash
neuralmind audit verify [project_path] [--json]
```

#### Arguments

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `project_path` | No | `.` | Project root |
| `--json`, `-j` | No | — | Print the result as JSON |

#### Exit codes

| Code | Meaning |
|------|---------|
| `0` | Every hashed record checks out |
| `1` | A line fails: it isn't a JSON object, its hash or `prev_sha256` doesn't match, or it has no hash after the chain started |

#### Output

`✓ Audit trail integrity OK (N events)`. Extra lines say how many records come
before the hash chain (written by versions before v0.46.2, so the chain doesn't
cover them), and which rotated archive the log continues, if any, and whether
its link to that archive was checked (it can't be once the archive is pruned).
On failure, the line number in the file and the reason go to stderr. `--json`
prints `ok`, `first_bad_line`, `total`, `unchained`, `continues_from`,
`archive_checked` and `reason`. `first_bad_line` is `null` when the file can't
be read at all.

v4.8.0 and earlier accepted a record without a hash anywhere in the log,
skipped lines they couldn't parse, and never compared `prev_sha256`. So records
edited or appended at the end with their hash removed, and garbage appended to
the log, passed.

#### What it can't detect

Records deleted from the end, or a chain recomputed by anyone who can write the
file (the hash has no secret key). Keep an exported copy off the host with
`neuralmind audit export . -o audit.jsonl`. See the
[Security Guide](../SECURITY-GUIDE.md#audit-trail).

### build

Build or rebuild the neural index from a knowledge graph.

```bash
neuralmind build <project_path> [OPTIONS]
```

#### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `project_path` | Yes | Path to project root containing `graphify-out/graph.json` |

#### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--force`, `-f` | False | Force re-embedding of all nodes, even if unchanged |
| `--content-type` | `auto` | What kind of project to build: `auto` (detect — book mode kicks in when markdown outweighs code ≥3:1, counting both recursively with vendored/state dirs pruned), `book` (force book mode: code scope for the engine, content scope for chapters), `code`, `content` |
| `--dry-run` | False | Scan the project and estimate token savings **without** building the index (v0.39.0+). Since v4.5.0 it scans the files a build would index (`.gitignore` applied), reports `Excluded by .gitignore: ~N nodes in M files (dir/ count, …)`, and divides by the **measured** token count of those files |
| `--naive-50k` | False | *(v4.5.0+)* With `--dry-run`, divide by the fixed 50,000-token estimate instead |
| `--redact-secrets` | False | Replace detected credentials with a `[REDACTED:kind]` marker in text entering the index, on all three backends. Equivalent to `NEURALMIND_REDACT_SECRETS=1`. Off by default because redacting costs recall on legitimately secret-shaped identifiers — run `neuralmind scan-for-secrets` first; removing and rotating the credential is the actual fix. |
| `--regenerate-graph` | False | Always rebuild `.neuralmind/graph.json` with the built-in tree-sitter backend, whatever graph exists — the way out of a stale graphify graph. `graphify-out/` is never written (v4.4.0+) |
| `--strict` | False | Exit `3` before embedding when the code graph FAILs the freshness check (v4.4.0+) |
| `--prune` | False | Remove orphaned vectors even when they are more than half the store; otherwise they're kept with a warning as a safety valve against a graph that shrank by mistake (v4.4.0+) |
| `--json`, `-j` | False | Emit structured JSON output (for `--dry-run`) |

#### Output

The first line names the graph the build used (v4.4.0+):

```
Graph: .neuralmind/graph.json (built-in, incremental, 8,351 nodes)
Graph: graphify-out/graph.json (graphify, read-only, 3,197 nodes)
```

When the graph isn't in step with the files on disk, the freshness report
follows (see [`doctor`](#doctor-v0120)). Then the build statistics:
- Number of nodes processed
- Delta: new / updated / skipped / **removed** — `removed` counts vectors purged
  because their node left the graph (v4.4.0+)
- Number of communities indexed
- Build time elapsed

#### Graph source *(v4.4.0+)*

`graph_source` in `.neuralmind.yaml` picks which graph the index is built from:

| Value | Behaviour |
|---|---|
| `auto` (default) | `.neuralmind/graph.json` when present, else `graphify-out/graph.json`. A graphify graph that FAILs the freshness check is replaced by a built-in graph at build time (when there is code on disk to parse), and the build prints why |
| `builtin` | Always the tree-sitter graph; `graphify-out/` is never read |
| `graphify` | Only `graphify-out/graph.json`; the build fails if it's missing |

NeuralMind never switches source silently: if the previous build used the
built-in graph and it has gone, the build stops and asks for
`--regenerate-graph` or `graph_source: graphify`.

#### What gets indexed: `.gitignore` *(v4.5.0+)*

The index covers what git covers. Inside a git repo the file list comes from
`git ls-files --cached --others --exclude-standard` — nested `.gitignore`,
`.git/info/exclude` and the global excludes apply exactly as in git — minus
tracked files that match an ignore rule (force-added copies under an ignored
directory). Outside git, or when the project sits in a directory an enclosing
repository ignores (a scratch dir, a vendored checkout), the project's own
top-level `.gitignore` is applied with the same pattern rules. `.neuralmindignore` narrows further and, since v4.5.0, uses
gitignore semantics too (`!` negation, `/` anchoring, `**`; `*` doesn't cross
`/`). The first build after upgrading prints what was excluded, once.

```yaml
# .neuralmind.yaml
respect_gitignore: false   # index ignored files again (v4.4 behaviour)
include_ignored:           # or pull specific ignored paths back in
  - "generated/api/**"
```

Git can't re-include a file under an excluded *directory*: to ignore a directory
except one file, write `projects/*` then `!projects/keep.py`, not `projects/`.

#### Examples

```bash
# Basic build
neuralmind build /path/to/project

# Force complete rebuild
neuralmind build /path/to/project --force

# Replace a stale graphify graph with the built-in one (v4.4.0+)
neuralmind build /path/to/project --regenerate-graph

# CI: stop with exit 3 if the code graph is out of step with the code
neuralmind build /path/to/project --strict

# Estimate token savings without building (Gap 1: 1-click setup)
neuralmind build /path/to/project --dry-run
# → NeuralMind dry run — my-project
# →   Files scanned : 142
# →   Lines of code : 18,342
# →   Languages     : 89 Python, 53 TypeScript
# →   Est. token reduction  : ~42x per query
# →   No index was built. Run `neuralmind build .` to activate these savings.
```

#### Prerequisites

**As of v0.15.0, none beyond `pip install neuralmind`.** When no
`graphify-out/graph.json` exists, `build` auto-generates `.neuralmind/graph.json`
with the bundled **tree-sitter backend** (`neuralmind/graphgen.py`) and prints:

```
Graph: .neuralmind/graph.json (built-in, generated, 1,240 nodes)
```

Backend precedence:
1. A real **graphify** graph always takes priority where present (`graphify update /path/to/project`).
2. Otherwise the **built-in tree-sitter backend** generates the graph. It indexes **Python, TypeScript, Go, Rust, Java, C, C++, C#, Ruby, and PHP** (`.py`, `.ts`/`.tsx`, `.go`, `.rs`, `.java`, `.c`/`.h`, `.cpp`/`.cc`/`.cxx`/`.hpp`/`.hh`/`.hxx`, `.cs`, `.rb`, `.php`) out of the box (Java added in v0.28.0; C and C++ in v0.32.0; C# in v0.35.0; Ruby in v0.36.0; PHP in v0.37.0); more grammars register behind the `SUPPORTED_SUFFIXES` seam. A mixed-language repo is indexed in one pass. **Schema artifacts** (v0.40.0+) are indexed alongside code as `document` nodes: **OpenAPI/AsyncAPI specs** (`.yaml`/`.yml` with an `openapi`/`asyncapi`/`swagger` key) emit nodes per path+method, schema component, and channel; **SQL DDL** (`.sql`) emits one node per `CREATE` object; **Protocol Buffers** (`.proto`) emit nodes per `message`, `service`, `rpc`, and `enum`. Plain YAML config files are silently skipped.
3. `--force` re-embeds; it never touches the graph source. `--regenerate-graph` (v4.4.0+) replaces a graphify graph with a built-in one in `.neuralmind/`, leaving `graphify-out/` untouched, and `graph_source` (above) pins the choice.
4. An empty/non-code project writes no graph, so you still get the "no graph" guidance rather than a silent 0-node success.
5. **Optional precision (v0.17.0+):** set `NEURALMIND_PRECISION=1` and place a `*.scip` index (from `scip-python`/`scip-typescript`/`scip-go`) in the project root to replace the built-in backend's heuristic `calls`/`inherits` edges with compiler-accurate ones for the files the index covers. Off by default.
6. **Secret redaction (opt-in):** `--redact-secrets` (or `NEURALMIND_REDACT_SECRETS=1`) replaces detected credentials with `[REDACTED:<kind>]` in **embedded text** — document chunks and node descriptions — on all three backends. Off by default, because redacting costs recall on legitimately secret-shaped identifiers.

   **What it does not cover.** Node *labels*, `graphify-out/graph.json` and `.neuralmind/index_ir.json` are written before the embedding step, so a credential inside a symbol name or docstring still reaches those files verbatim (on every backend — this is not backend-specific). Verify with `grep -r '<the-secret>' graphify-out/ .neuralmind/` after a build if it matters to you.

   The flag is a backstop for text that reaches the vector store, not a guarantee that no artifact under the project holds the credential. Run `neuralmind scan-for-secrets .` first — removing and rotating is the actual fix. The build also warns if git is already tracking files under `.neuralmind/`.

---

### scan-for-secrets

Report credentials present in a project's files, so they can be removed and
rotated **before** they reach the index, a commit, or an agent's context.

```bash
neuralmind scan-for-secrets [PROJECT_PATH] [--high-confidence-only] [--strict]
                            [--use-neuralmindignore] [--json]
```

| Option | Effect |
|--------|--------|
| `PROJECT_PATH` | Project root (default `.`). |
| `--high-confidence-only` | Report only vendor-shaped credentials; suppress the generic-assignment heuristic. |
| `--strict` | Exit non-zero on heuristic findings too (default: high-confidence only). |
| `--use-neuralmindignore` | Also apply `.neuralmindignore` globs. **Off by default** — see below. |
| `--json` / `-j` | Machine-readable output. |

```
NeuralMind secret scan — /home/dev/myproject

  [HIGH ] .env:1  anthropic-api-key  (sk-a…(43 chars))
  [HIGH ] src/config.py:8  aws-access-key-id  (AKIA…(20 chars))
  [maybe] src/db.py:34  generic-secret-assignment  (9f8K…(28 chars))

  2 high-confidence, 1 heuristic.
```

**Two confidence tiers.** `HIGH` matches a vendor-specific shape and
effectively never fires on prose: Anthropic and OpenAI keys, AWS access
key IDs, secret keys and session tokens (including the
`"SecretAccessKey"` / `"SessionToken"` JSON the AWS CLI prints, v4.8.1),
GitHub tokens and fine-grained PATs, GitLab PATs and Hugging Face tokens
*(v4.8.1)*, Slack tokens, Google API keys, Stripe keys, PyPI and npm
tokens, PEM private-key blocks, JWTs, `Authorization: Bearer`/`Basic`
headers, and passwords embedded in database or `http(s)://user:password@host`
URLs. `maybe` matches a generic `SECRET=value` assignment, including a quoted
JSON or dict key such as `{"password": "…"}` *(v4.8.1)*, that cleared a
Shannon-entropy threshold and a placeholder denylist — so
`password = "changeme"`, `api_key = os.environ["X"]`, and `KEY=${VAR}` are
not reported.

**Previews never include the tail of a secret** — only a short prefix and
a length — so scan output is safe to paste into an issue or a CI log.

**Exit codes**, so this works as a CI gate:

| Condition | Exit |
|-----------|------|
| No findings | `0` |
| Heuristic findings only | `0` (`1` with `--strict`) |
| Any high-confidence finding | `1` |
| Path does not exist | `2` |

The scanner reads files directly rather than going through the indexer, so
it sees `.env` and other files `build` never parses. It skips the usual
vendored/build directories (`node_modules`, `.venv`, `dist`, `target`,
`.git`, `.neuralmind`), binary files, and anything over 5 MB.

**`.neuralmindignore` is not applied by default.** That file is tuned for
retrieval quality, not security — NeuralMind's own copy excludes `docs/`,
`*.md` and `tests/` because markdown dilutes code retrieval. A scanner that
inherited it would skip exactly where credentials tend to sit and report a
false all-clear. Pass `--use-neuralmindignore` if you want those globs
applied anyway.

Related: `neuralmind build . --redact-secrets` scrubs detected credentials
out of indexed text as a backstop — it does not remove the credential from
your working tree, and it is not a substitute for rotating a key that has
already been exposed.

---

### query

Query the codebase with natural language and get optimized context.

```bash
neuralmind query <project_path> "<question>" [OPTIONS]
```

#### Type Filter *(v3.1.4+)*

Steer the ranking toward a node type (results are ranked, not filtered, so
other types can still appear):

| Flag | Description |
|------|-------------|
| `--type code` | Rank source code first |
| `--type docs` | Rank documentation first |
| `--type auto` | Auto-detect intent (default) |

*(v4.8.1+)* `code` and `docs` replace the detected intent before L3 is ranked.
Before v4.8.1 they re-boosted the hits after the context was built, so the
returned context didn't change.

#### Cross-Project Search *(v3.1.4+)*

Query across multiple indexed projects:

```bash
neuralmind query --projects /repo/a,/repo/b "authentication logic"
```

Results are tagged with source project and deduplicated by ID.

#### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `project_path` | Yes | Path to project root |
| `question` | Yes | Natural language question about the codebase |

#### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--json`, `-j` | False | Output results as JSON |
| `--trace` | False | *(v0.23.0+)* Attach a per-layer retrieval trace (see below) |
| `--trace-verbose` | False | *(v0.23.0+)* With `--trace`, keep full candidate/hit lists |
| `--explain` | False | *(v0.39.0+)* Human-friendly breakdown of token savings, layers used, top hits, and synapses that fired (implies `--trace`). *(v4.6.0+)* Also prints the query intent L3 ranked with and how it was decided, and labels each top hit with its name and file |
| `--relevance` | False | *(v0.41.0+)* With `--json`, attach a structured `relevance` sidecar (per-file, per-node score/synapse-boost/recall + line spans) so a downstream compressor can protect the load-bearing spans (see below) |
| `--mode` | `default` | *(v3.8.0+)* `default` uses the context selector against one scope; `unified` searches the content scope and the code scope together and merges results — for a project that mixes prose (via `ingest-content`) and code |
| `--scope-bias` | `balanced` | *(v3.8.0+)* With `--mode=unified`: `content`, `code`, or `balanced` — weights which scope's hits rank higher in the merged results |
| `--chapter` | None | *(v3.8.0+)* With `--mode=unified`: filter results to a specific chapter tag, e.g. `--chapter="Chapter 2 — The Corner Pub"` |
| `--no-learn` | False | *(v4.5.0+)* Read-only query: synapse recall still shapes the context (you get exactly what a normal query returns), but nothing is reinforced, no query log is written, and the synapse database is opened read-only (`mode=ro`). Never builds — on an unbuilt project it says so. For evals, benchmarks and CI; same as `NEURALMIND_NO_LEARN=1` |

#### Unified search mode *(v3.8.0+)*

For a project indexed with both `neuralmind build` (code) and
`neuralmind ingest-content` (prose — see v3.4.0), `--mode=unified` queries
both scopes and merges the results instead of picking one by default:

```bash
neuralmind query . "how does the corner pub scene end?" --mode=unified --scope-bias=content
neuralmind query . "what handles the payment retry?" --mode=unified --scope-bias=code
neuralmind query . "who visits the pub?" --mode=unified --chapter="Chapter 2 — The Corner Pub"
```

#### Output

Returns:
- Optimized context text for AI consumption
- Token count and breakdown by layer
- Reduction ratio compared to full codebase
- Communities/modules loaded

#### Retrieval traces *(v0.23.0+)*

`--trace` explains **why** a result came back (PRD 3) — useful when retrieval
surprises you. It records, layer by layer:

- **candidates** — the raw vector-search pool (ids + scores);
- **cluster_scores** — per-cluster score with **vector-vs-synapse attribution**
  (how much of each cluster's score came from learned co-activation);
- **synapse_boost** — individual co-activation boosts;
- **hits** — the final ranked hits, flagging which were synapse-recalled;
- **budget** — tokens per layer + reduction ratio.

Plain `--trace` prints a compact per-layer summary; `--json` includes the full
trace object (bounded, and path-redactable via the `RetrievalTrace` API for
sharing in bug reports). Tracing is off by default and zero-overhead. The
daemon's `/query` honors `trace` too, so daemon and direct mode return the same
attribution.

#### Relevance sidecar *(v0.41.0+)*

`--relevance` (with `--json`) attaches a structured `relevance` block so a
**downstream compressor** can tell which spans are load-bearing and must
survive compression. NeuralMind already computes a vector **score**, a learned
**synapse boost**, and a **recall flag** per retrieved node; the sidecar exposes
them as machine-readable metadata keyed by source file (plus best-effort line
spans from the graph), built from the **post-boost** L3 hits so it reflects the
same signals the rendered context used:

```json
{
  "relevance": {
    "version": 1,
    "files": {
      "auth/handlers.py": {
        "max_score": 1.02,
        "nodes": [
          {"node_id": "…", "label": "authenticate", "score": 0.87,
           "synapse_boost": 0.15, "recalled": true, "lines": [42, 68]}
        ]
      }
    }
  }
}
```

The `version` field guards the wire shape; the stable `files{}` / `node_id`
keys let a tool running *after* NeuralMind re-associate the signal regardless of
pipeline order. The same block is available over MCP via
`neuralmind_query(include_relevance=true)`. Off by default — `query` output is
unchanged unless requested. `--relevance` and `--explain` both run in direct
mode (they need the full result the daemon's thin response omits).

#### Examples

```bash
# Basic query
neuralmind query /path/to/project "How does authentication work?"

# JSON output
neuralmind query /path/to/project "What are the main API endpoints?" --json

# Explain the retrieval path (raw trace)
neuralmind query /path/to/project "How does billing work?" --trace
neuralmind query /path/to/project "How does billing work?" --trace --json

# Human-friendly explanation of why this context was chosen (v0.39.0+)
neuralmind query /path/to/project "auth flow" --explain
# → Why this context?
# →   Token budget breakdown:
# →     L0 identity   :    142 tokens
# →     L1 summary    :    513 tokens
# →     L2 communities:    800 tokens
# →     L3 search     :    980 tokens
# →     Total used    :  2,435 tokens
# →     Est. saved    : 47,565 tokens  (20.5x reduction)
# →   Query intent     : code (by classifier)
# →   Top search hits (L3, 4 nodes):
# →     0.912  authenticate  (auth/handlers.py)
# →     0.887  JWTMiddleware  (auth/middleware.py)
```

**Query intent *(v4.6.0+)*.** L3 re-weights its hits by the question's intent —
a `docs` question multiplies doc hits by 2.0 and code hits by 0.7 — and
`--explain` now says which intent it used and how it was decided:

| Shown as | Decided by |
|---|---|
| `code (by classifier)` / `docs (by classifier)` | the v3.9.0 pattern classifier |
| `… (by keywords)` | the older keyword count, when the classifier calls the question `hybrid` |
| `code (by question shape)` / `docs (by question shape)` | the opt-in intent rules, `NEURALMIND_INTENT_RULES=1` (see [Environment Variables](#environment-variables)) |

When a "how does X work" question comes back ranked as `docs`, this line
explains why a README ranks above the implementation *within* L3's four hits
(a `docs` intent multiplies doc hits by 2.0 and code by 0.7). It can't explain
the implementation missing from those four: in v4.6.0's eval, switching intent
never changed hit@5. The hit list prints each hit's label and
file; before v4.6.0 it printed raw node ids.

#### Sample Output

```
=== Query: How does authentication work? ===

[Context]
# Project: MyApp
MyApp is a web application with JWT-based authentication...

[Authentication Module]
The auth module handles user login, token generation, and validation...

[Relevant Code]
- auth/jwt_handler.py: JWT token generation and validation
- auth/middleware.py: Authentication middleware for routes
- models/user.py: User model with password hashing

---
Tokens: 847 | Reduction: 59.0x | Layers: L0, L1, L2, L3 | Communities: [5, 12]
```

---

### wakeup

Get minimal wake-up context for starting a new conversation.

```bash
neuralmind wakeup <project_path> [OPTIONS]
```

#### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `project_path` | Yes | Path to project root |

#### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--json`, `-j` | False | Output results as JSON |

#### Output

Returns L0 (Identity) + L1 (Summary) context, typically ~600 tokens, suitable for:
- Starting new AI conversations
- Providing project context to coding assistants
- Initial system prompts

#### Examples

```bash
# Get wake-up context
neuralmind wakeup /path/to/project

# Redirect to file
neuralmind wakeup /path/to/project > context.md

# JSON format
neuralmind wakeup /path/to/project --json
```

#### Sample Output

```
=== Wake-up Context ===

# Project: MyApp

MyApp is a full-stack web application for task management built with React and Node.js.

## Architecture Overview

### Core Components
- **Frontend**: React 18 with TypeScript, Tailwind CSS
- **Backend**: Node.js/Express REST API
- **Database**: PostgreSQL with Prisma ORM
- **Auth**: JWT-based authentication

### Main Modules
1. User Management (users/) - Registration, profiles, settings
2. Task Engine (tasks/) - CRUD operations, scheduling, notifications
3. API Layer (api/) - REST endpoints, middleware, validation

---
Tokens: 412 | Layers: L0, L1
```

---

### search

Perform direct semantic search across codebase entities.

```bash
neuralmind search <project_path> "<query>" [OPTIONS]
```

#### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `project_path` | Yes | Path to project root |
| `query` | Yes | Semantic search query |

#### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--n` | 10 | Maximum number of results. *(v4.8.2+)* Must be at least 1; `0` or a negative value is a usage error (it used to return one result) |
| `--json`, `-j` | False | Output results as JSON |

#### Output

Returns matching code entities with:
- Entity name and type
- Similarity score (0-1)
- File path
- Community membership

#### Examples

```bash
# Basic search
neuralmind search /path/to/project "authentication"

# Limit results
neuralmind search /path/to/project "database connection" --n 5

# JSON output
neuralmind search /path/to/project "API endpoint" --json
```

#### Sample Output

```
=== Search: authentication ===

1. authenticate_user (function) - Score: 0.92
   File: auth/handlers.py
   Validates user credentials and returns JWT token
   Community: 5 (Authentication)

2. AuthMiddleware (class) - Score: 0.87
   File: auth/middleware.py
   Express middleware for JWT validation
   Community: 5 (Authentication)

3. hash_password (function) - Score: 0.81
   File: utils/crypto.py
   Securely hashes passwords using bcrypt
   Community: 5 (Authentication)

---
Results: 3 | Query time: 45ms
```

---

### benchmark

Run performance benchmark with sample queries.

```bash
neuralmind benchmark <project_path> [OPTIONS]
```

#### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `project_path` | Yes | Path to project root |

#### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--json`, `-j` | False | Output results as JSON |
| `--naive-50k` | False | *(v4.5.0+)* Divide by the fixed 50,000-token estimate instead of the measured token count of the code the index covers — for comparison with pre-v4.5.0 numbers |
| `--contribute` | False | Print your numbers and a schema-ready entry for [`docs/community-benchmarks.json`](https://github.com/dfrostar/neuralmind/blob/main/docs/community-benchmarks.json). Nothing is uploaded. From v4.5.0 the entry is v2: `avg_reduction_ratio` against the fixed 50K estimate every row compares on, plus `measured_avg_reduction_ratio` and `full_codebase_tokens` |
| `--quality` | False | *(v0.23.0+)* Quality-eval mode — see below |
| `--suite` | (all) | *(v0.23.0+)* With `--quality`, run one suite: `python` / `typescript` / `go` |
| `--baseline` | — | *(v0.23.0+)* With `--quality`, a saved suite JSON to compare against (reports metric deltas) |
| `--public` | False | *(v0.31.0+)* Public-benchmark mode — reproduce the honest vs-alternatives comparison on pinned real repos (see below). Ignores `project_path` (it uses the pinned corpus, not your project) and requires a **source checkout** — the `evals/public` harness ships in the repo, not the PyPI wheel |
| `--repo` | (all) | *(v0.31.0+)* With `--public`, scope to one corpus repo: `requests` / `click` |
| `--seeds` | `1` | *(v0.31.0+)* With `--public`, the seed count recorded in the report. The pipeline is deterministic (synapse injection off), so variance across seeds is exactly 0 — recorded honestly rather than padded with artificial noise |
| `--judge` | False | *(v0.34.0+)* With `--public`, also run the opt-in **answerability arm** — each backend answered from its real window by a pinned model (`claude-opus-4-8`), graded vs. the def-site gold anchor (0–2 + `grounded`). A clearly-labeled **secondary** signal. Needs `ANTHROPIC_API_KEY`; **never runs in CI**; the recall table is byte-identical with or without it; skips cleanly without a key (see below) |
| `--judge-out` | `bench/public/judge` | *(v0.34.0+)* With `--public --judge`, where to write the raw answerability transcripts (question, context tokens, answer, verdict, rationale) |

#### Output

Comprehensive benchmark report including:
- **The baseline it divides by** *(v4.5.0+)* — `Baseline: measured: 94,069 tokens in 36 indexed code files`: the token count of every code file the index covers, measured at build, at the same ~4 chars/token as the context. Prose (Markdown, reStructuredText, plain text) is left out unless the index holds nothing else, and an index built before v4.5.0 is measured on the spot without writing anything. Before v4.5.0 every ratio divided by a fixed 50,000-token guess whatever the repo's size
- **The legacy ratio beside it** *(v4.5.0+)* — `Legacy reduction: 41.8x (vs the fixed 50K-token estimate used before v4.5.0)`, so older numbers and the community table stay comparable; `--naive-50k` makes the fixed estimate the headline instead
- **Which questions it asked** — the ones in `.neuralmind.eval.yaml` when the project has one (see [`eval`](#eval-v0140)), else five generic questions
- Token counts and reduction ratios for each query
- Benchmark queries are read-only (v4.5.0+): they never train the synapse layer

`--json` carries `avg_reduction_ratio` with the baseline it used (`baseline`,
and `full_codebase_tokens`), plus `legacy_avg_reduction_ratio` against
`estimated_full_codebase_tokens` (always 50,000); every entry in `results` has
its own `reduction` and `legacy_reduction`.

#### Examples

```bash
# Run default benchmark
neuralmind benchmark /path/to/project

# JSON output
neuralmind benchmark /path/to/project --json
```

On `psf/requests` v2.32.3 (verbatim, v4.5.0):

```
Project: requests
Baseline: measured: 94,069 tokens in 36 indexed code files
Questions: generic
Wake-up tokens: 510
Avg query tokens: 1200.6
Avg reduction: 78.6x
Legacy reduction: 41.8x (vs the fixed 50K-token estimate used before v4.5.0)
Summary: 78.6x average token reduction vs measured: 94,069 tokens in 36 indexed code files
```

#### Quality-eval mode *(v0.23.0+)*

`--quality` switches the command from token-reduction benchmarking to
**retrieval-quality** measurement: does NeuralMind surface the *right* code,
not just *less* of it? It scores **precision@k**, **recall@k**, **MRR**, and
**answerability** over golden query suites (Python / TypeScript / Go — 30
queries with expected-module labels) and **exits non-zero if a suite regresses
past its floor**, so CI can gate retrieval-affecting changes.

Like `neuralmind eval`, this is a contributor/CI self-test that runs against
the golden suites shipping with the **source repo** (the `evals/quality/`
package), not the installed wheel. The pure metrics live in
`neuralmind.quality` (`from neuralmind import quality`).

```bash
# Score all golden suites
neuralmind benchmark --quality

# One language, machine-readable
neuralmind benchmark --quality --suite go --json

# Compare against the committed measured baseline (reports metric deltas)
neuralmind benchmark --quality --baseline evals/quality/baseline.json

# Dependency-free validation of the suites + metric math (no embeddings)
python -m evals.quality.runner --selfcheck
```

Sample (markdown) output — measured on the committed fixtures:

```
## NeuralMind retrieval-quality eval

| Suite | Queries | MRR | Answerability | Recall@5 | Precision@5 | Gate |
|-------|--------:|----:|--------------:|---------:|------------:|:----:|
| `go`         | 10 | 0.950 | 100% | 0.833 | 0.603 | PASS |
| `python`     | 10 | 0.900 | 100% | 0.833 | 0.612 | PASS |
| `typescript` | 10 | 0.900 | 100% | 0.800 | 0.562 | PASS |

**Overall: PASS**
```

The exit code is non-zero if any suite drops below the floors in
`evals/quality/harness.py` (`DEFAULT_THRESHOLDS`), so CI can gate on it. The
measured baseline lives at `evals/quality/baseline.json`; the self-benchmark
workflow runs this on every PR (where real embeddings are available) and posts
the table + baseline deltas as a PR comment.

#### Public-benchmark mode *(v0.31.0+)*

`--public` runs the **honest public benchmark**: a reproducible, no-cherry-picking
comparison of how much context different approaches put in an agent's window to
answer a real code question, and whether the **objectively-correct file** actually
makes it in. It clones **real, pinned OSS repos** at fixed commit SHAs
(`requests` @`0e322af877`, `click` @`874ca2bc1c`) and scores **cost _and_
correctness together** against strong baselines: `full-file` paste, `ripgrep`,
a same-encoder `embedding-rag`, and `neuralmind`'s progressive disclosure.

Gold-file recall is an **objective def-site oracle** — each query's gold file is
the definition site of a named symbol, verifiable with one `rg`; there is **no
LLM judge**. Scoring reuses `neuralmind/quality.py` verbatim — the same metric
code the CI quality gate runs. Pre-registered queries live in
`evals/public/manifest.json`; every one is reported, losses included.

```bash
# Clone the pinned repos and print the full table
neuralmind benchmark --public

# Scope to one repo
neuralmind benchmark --public --repo click

# Machine-readable output (for CI / further analysis)
neuralmind benchmark --public --json

# Equivalent module entrypoint (from a clone)
python -m evals.public.run
```

The run is **deterministic** — synapse injection is **OFF** (session-dependent
learning can't be a fixed, reproducible public number; its lift is
measured separately by the synapse A/B eval, `tests/benchmark/run.py` Phase 2).
This reuses the same `NEURALMIND_SYNAPSE_INJECT=0` toggle documented in the
[Environment Variables](#environment-variables) table. Re-running on the same
machine matches the published table to the token. Across machines, recall,
found-rate and MRR have matched exactly, while token counts differed slightly
on some CI runners (up to 1.3% on a per-repo mean so far);
`NEURALMIND_ORT_THREADS=1` matches CI's configuration — see
[how exactly a re-run reproduces](../benchmarks/public.md#how-exactly-a-re-run-reproduces).

**Honest headline:** against what agents actually do today — paste files or grep
— NeuralMind reaches **85.71–100% gold-file recall (95% mean, 92.5% found-rate)
at 46–263× fewer tokens** than pasting every source file, and beats `ripgrep` on
cost on every repo; on recall it's ahead on 3 of 4 repos and ties exactly on the
fourth. The benchmark also reports, without hiding it, that a well-tuned vector
RAG matches or beats it at *findability* on every repo (and cheaper on raw
tokens), and that `click` is NeuralMind's weakest repo in the corpus (3 of 40
queries missed, every one published). Full methodology,
results, honest caveats, and "where NeuralMind loses" are published at
[`docs/benchmarks/public.md`](https://github.com/dfrostar/neuralmind/blob/main/docs/benchmarks/public.md);
raw per-query data is committed at `bench/public/results.json`, and the forkable
runner is `.github/workflows/bench-public.yml`.

##### Competitor head-to-head *(v0.33.0+)*

The benchmark also ships a **live, reproducible row vs. `codebase-memory-mcp`
0.8.1** (the obvious incumbent), on the same pinned repos, questions, def-site
gold, and `quality.py` scorer, at retrieval depth matched to `embedding-rag`
(top-8). It lives in a **separate module** and is **off the default run** because
it downloads an external binary — invoke it explicitly from a clone:

```bash
pip install codebase-memory-mcp==0.8.1     # pins 0.8.1 — on-device embeddings, no API key
python -m evals.public.competitor   # prints the competitor row; fails closed without the binary
```

On **reproducible retrieval ranking** NeuralMind reaches **100% gold-file recall**
and ranks the right file far higher (MRR **0.96 vs 0.23** on `requests`, **0.60
vs 0.50** on `click`), while the competitor surfaces the gold file in its top-8
only ~half the time, at an order of magnitude more read cost. **Honest framing:**
this measures *pure retrieval* — no LLM agent loop on either side, exactly how we
test NeuralMind's own `search`; we used the competitor's **most-favorable**
reproducible keyword mapping; and we cite its *published* LLM-agent numbers (~90%
of an "Explorer" agent; C at 0.58) as-is rather than reproduce them. Per-query
traces and pinned `REPRODUCE.md` are committed under `bench/public/competitor/`;
full caveats are in the "Competitor head-to-head" section of
[`docs/benchmarks/public.md`](https://github.com/dfrostar/neuralmind/blob/main/docs/benchmarks/public.md).

#### Answerability arm — `--judge` *(v0.34.0+)*

Gold-file recall measures *locating* the right file, not *answering* the
question. The opt-in answerability arm adds the answering signal — a
clearly-labeled **secondary** to the recall headline:

```bash
ANTHROPIC_API_KEY=…  python -m evals.public.run --judge   # off by default
```

For each query it answers from **the real context each backend would put in the
window** (whole files / retrieved chunks / compact L0–L3 context) using a pinned
model (`claude-opus-4-8`), constrained to that context only, then a separate
judge call grades the answer against the same def-site gold anchor on a 0–2 scale
plus a `grounded` flag. It needs `ANTHROPIC_API_KEY` (and the `anthropic`
package), **never runs in CI**, and the recall table is byte-identical with or
without `--judge` — absent a key it skips cleanly and the recall benchmark still
runs. The answerer prompt, judge rubric, pinned model id, and **every raw
transcript** are committed under `bench/public/judge/` (transcripts written to
`--judge-out`, default `bench/public/judge`). Full framing + caveats: the
"Answerability arm" section of
[`docs/benchmarks/public.md`](https://github.com/dfrostar/neuralmind/blob/main/docs/benchmarks/public.md).

#### Sample Output

```
=== NeuralMind Benchmark ===

Project: MyApp
Total Nodes: 241
Communities: 93
Estimated Full Codebase: 50,000 tokens

| Query Type | Tokens | Reduction | Latency |
|------------|--------|-----------|----------|
| Wake-up context | 341 | 146.6x | 45ms |
| How does authentication work? | 739 | 67.7x | 187ms |
| What are the main API endpoints? | 748 | 66.8x | 192ms |
| Explain the database models | 812 | 61.6x | 201ms |
|------------|--------|-----------|----------|
| **Average** | **660** | **85.7x** | **156ms** |

---
Benchmark completed in 625ms
```

---

### probe *(v0.27.0+)*

Run a **retrieval self-probe** on your own codebase: does the index actually
find the right file when the agent asks about a symbol? Unlike `benchmark`
(which measures token reduction) and `benchmark --quality` (which scores ranking
against committed golden fixtures), `probe` runs **label-free** — no hand
annotation — so it works on **any** built project.

```bash
neuralmind probe [project_path] [OPTIONS]
```

For a deterministic sample of indexed symbols, it queries each one by its
*intent* — the symbol's **rationale** (the docstring text NeuralMind stores as
`rationale` nodes, e.g. `"Raised when the exp claim is in the past"`), which
doesn't contain the symbol name, so it's a real **natural-language → code** test
rather than a string match. It asks the backend for code hits directly, then
scores whether the symbol's source file came back: **recall@1/3/5**, **MRR**, and
**answerability@k** (reusing the `neuralmind.quality` metrics). Undocumented
symbols fall back to a humanized label, and the report **discloses the
rationale-vs-name split** so a mostly-fallback run reads as a sanity check, not a
quality score. The most actionable output is the **blind-spot list**: the sampled
symbols the index couldn't retrieve from their description — i.e. where an agent
would come up empty. `--k` must be ≥ 1 and `--sample-size` ≥ 0 (`0` = all).

The idea is borrowed from long-context "needle-in-a-haystack" evals (e.g. S-NIAH
in the *Recursive Language Models* paper): rather than measuring cost, it
measures whether the right node still surfaces as the index grows. It is
**read-only** — it never mutates the index or the synapse store.

#### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `project_path` | No | Path to project root (default: `.`) |

#### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--sample-size` | 50 | How many indexed symbols to probe (`0` = all) |
| `--k` | 10 | Retrieval depth — a symbol's file must surface in the top-k |
| `--seed` | 0 | Sampling seed. *(v4.5.0+)* Symbols are ranked by a hash of (seed, node id) and the lowest `--sample-size` kept, so an unchanged symbol stays in the sample across rebuilds — two runs either side of a 5% index change share ≥ 90% of their sample |
| `--baseline` | — | A saved probe JSON to compare against. *(v4.5.0+)* Compares only the symbols both runs sampled, and reports how many were added or dropped, so an index change can't pass for a quality change |
| `--json`, `-j` | False | Output the full report (including every blind spot) as JSON |

#### Examples

```bash
# Probe the current project
neuralmind probe .

# Tighter: the right file must be the #1 hit
neuralmind probe . --k 1

# Save a baseline, then check whether a refactor moved retrieval
neuralmind probe . --sample-size 100 --json > probe-baseline.json
neuralmind probe . --sample-size 100 --baseline probe-baseline.json
```

#### Sample Output

```
Retrieval self-probe — sample_project
Sampled 63 of 64 indexed symbols, retrieval depth k=10
Query source: 51 rationale, 12 label
============================================================
  answerability  : 98%  (file found in top-10)
  MRR            : 0.789
  recall@1/3/5   : 0.667 / 0.905 / 0.968
  blind spots    : 1
------------------------------------------------------------
Symbols the index couldn't retrieve from their own description (1 total):
  - get_me_endpoint()  (api/routes.py)   query: "GET /api/users/me — requires Authorization: Bearer header"
```

The `Query source` line discloses how strong the run was: `rationale` probes are
real NL→code tests; `label` probes are a weaker name-based fallback for
undocumented symbols. Because the probe is deterministic per `--seed` and emits
`--json` (with a `query_sources` tally), you can gate CI on a per-repo recall/MRR
floor, or diff two runs with `--baseline` to catch a retrieval regression before
it ships.

---

### stats

Show statistics about the neural index.

```bash
neuralmind stats <project_path> [OPTIONS]
```

#### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `project_path` | Yes | Path to project root |

#### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--json`, `-j` | False | Output as JSON |

#### Output

Displays:
- Node counts by type
- Community statistics
- Synapse edge count and total weight
- Embedding model and backend info

#### Examples

```bash
neuralmind stats .
neuralmind stats /path/to/project --json
```

### cognition-loop

*On demand since v4.0.0; rebuilt in v4.6.0.* Runs one maintenance pass over
the project's learned memory, using the same machinery the hooks use:

1. **Decay** — the synapse store's half-life decay (30 days for personal and
   branch memory, 60 for shared, 1 for ephemeral; long-term edges keep their
   floor; dead edges are pruned). It charges only the time since the previous
   decay, so running it often never decays anything twice.
2. **Read-dedup cleanup** — drops `.neuralmind/read_cache.db` rows untouched
   for a day.

```bash
neuralmind cognition-loop [project_path] [--json]
```

Idempotent and safe while NeuralMind is in use, so it can go in cron. Nothing
schedules it: the `SessionStart` hook already decays at every Claude Code
session start and `neuralmind watch` every 10 minutes, so it's for setups that
run neither (an MCP-only client, say). Hub normalization is left to the
`PreCompact` hook, because it compounds on every call. A project with no
learned memory, or a process with `NEURALMIND_NO_LEARN=1`, is skipped
(`"skipped"` in the JSON) and nothing is created.

```cron
0 * * * * cd /path/to/repo && neuralmind cognition-loop . >/dev/null
```

`--json` fields: `edges_pruned`, `edges_remaining`, `transitions_pruned`,
`transitions_remaining`, `read_cache_pruned`, `duration_secs`, `timestamp`,
`skipped`.

> Before v4.6.0 this command ran its own SQL that deleted most learned edges
> idle for about two days, replayed recent queries into an unread `traversal`
> namespace and deleted session summaries older than 30 days. Leftover
> `traversal` rows are inert; `neuralmind memory reset --namespace traversal`
> removes them.

---

### synapse prune *(v3.1.4+)*

Remove stale synapses older than N days.

#### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `project_path` | Yes | Path to project root |

#### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--days` | None | Age threshold in days (required) |
| `--json`, `-j` | False | Output as JSON |

#### Output

Number of synapses pruned.

#### Notes

LTP-protected edges (≥5 activations) are preserved to maintain learned associations.

#### Examples

```bash
# Prune synapses older than 30 days
neuralmind synapse prune . --days 30

# Preview what would be pruned (use stats first)
neuralmind synapse stats .
```

### synapse stats *(v3.1.4+)*

Detailed synapse diagnostics.

#### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `project_path` | Yes | Path to project root |

#### Output

- Total edges
- LTP-protected count: the edges decay actually protects, meaning at least 5
  activations, a weight of at least 0.20, and not in the `ephemeral`
  namespace. *(v4.9.1+; it used to count activations only, so a penalized or
  ephemeral edge counted too.)* `status`, the dashboard and the long-term count
  in `SYNAPSE_MEMORY.md` use the same rule.
- Stale (30+ days inactive)
- Dormant (≤1 activation)
- Total weight

#### Examples

```bash
neuralmind synapse stats .
```
- Embedding information
- Index storage size
- Last build timestamp

#### Examples

```bash
# Basic stats
neuralmind stats /path/to/project

# JSON format
neuralmind stats /path/to/project --json
```

#### Sample Output

```
=== NeuralMind Statistics ===

Project: MyApp
Graph Path: /path/to/project/graphify-out/graph.json
DB Path: /path/to/project/graphify-out/neuralmind_db

## Index Summary
- Total Nodes: 241
- Total Edges: 203
- Communities: 93
- Embedding Dimensions: 384

## Node Types
- Functions: 142 (58.9%)
- Classes: 45 (18.7%)
- Files: 38 (15.8%)
- Database Models: 16 (6.6%)

## Storage
- Index Size: 12.4 MB
- Cache Size: 2.1 MB

## Build Info
- Last Build: 2024-01-15 14:30:22
- Build Duration: 8.3s
- Embedding Model: all-MiniLM-L6-v2
```

---

### validate *(v0.23.0+)*

Validate the project's canonical **intermediate representation (IR)** — the
versioned, producer-agnostic contract NeuralMind builds from `graph.json`.
Runs a static schema check; **no vector backend required** (it never touches
ChromaDB/turbovec).

```bash
neuralmind validate [project_path] [OPTIONS]
```

#### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `project_path` | No (default `.`) | Path to project root |

#### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--write` | False | (Re)materialize the IR to `.neuralmind/index_ir.json` — the in-place **migration** path for a legacy project that predates the IR (no rebuild). |
| `--json`, `-j` | False | Output a machine-readable summary (for CI/dashboards) |

#### What it checks

- **errors** (exit code `1`): dangling edge endpoints, missing endpoints,
  duplicate node ids, malformed synapse endpoints, unsupported (too-new)
  `ir_version`.
- **warnings**: orphaned (edgeless) nodes, unknown node kinds, unknown edge
  relations, and **stale synapses** (learned memory pointing at nodes a
  rebuild removed) — forward-compatibility / hygiene signals. Endpoints
  NeuralMind writes on purpose aren't graph nodes and aren't stale:
  `community_<id>` for a community the index still has, `compliance:` keys,
  *(v4.9.1+)* the prose path's `query:<term>` nodes (written as
  `query_<term>` before v4.9.1; those older edges still count as stale until
  they decay), and *(v4.10.0+)* the chapter file names the prose path records,
  such as `ch01.md`, while the index still holds `chapters/ch01.md`.

It also reports the IR contract version, source backend + producer schema
version, coverage (`coarse`/`precise`), per-kind / per-language counts, and the
learned-synapse count (folded in backend-free from the SQLite store).

#### Examples

```bash
# Validate the IR for the current project
neuralmind validate .

# Machine-readable summary
neuralmind validate . --json

# Migrate a legacy project's state to the IR in place (no rebuild)
neuralmind validate . --write
```

#### Sample Output

```
IR version:      1
Source backend:  neuralmind.graphgen (tree-sitter)
Source schema:   v1
Coverage:        coarse
Entities:        135 nodes, 185 edges, 18 clusters
Node kinds:      document=56, file=13, function=41, symbol=25
Languages:       python=135
------------------------------------------------------------
VALID — 0 errors, 0 warning(s).
```

> `function` is inferred from the built-in backend's call-form labels
> (`name()`); a producer that doesn't follow that convention maps those to the
> generic `symbol`. Learned synapses, when a `.neuralmind/synapses.db` exists,
> are folded in and shown in the `--json` `synapses` count.

> The IR is also exposed as a public Python API:
> `from neuralmind import IndexIR, from_graph_json, validate_ir, validate_project`.

---

### doctor *(v0.12.0+)*

Diagnose a project's NeuralMind setup and print an actionable fix for
anything that isn't wired up. Read-only — it never builds or mutates
state.

```bash
neuralmind doctor [project_path] [--json]
```

**Arguments:**

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `project_path` | No | `.` | Project root to inspect |
| `--json`, `-j` | No | `false` | Emit machine-readable JSON |

**Checks:** code graph, semantic index, **backend** *(v0.22.0+)*, synapse
memory, MCP server, Claude Code hooks, and query-memory consent. Each reports
`ok`, `warn` (optional/learned-over-time), or `fail` (setup incomplete). The
**Backend** check reports the configured value (e.g. `auto`), what it resolves
to (`turbovec` or `chroma`), and whether the turbovec stack is installed — so the
per-environment default is never a silent mystery.

**Security policy** and **Storage encryption** *(v4.7.0+)* report the
[security settings](#security-settings-security-in-neuralmind-backendyaml):
which identity mode MCP calls use and the role the current OS account gets,
*(v4.8.0+)* whether a malformed, empty or unparseable role policy makes the
server refuse every call, whether the policy file is group- or world-writable, and whether the project's
volume is encrypted (FileVault, BitLocker, or dm-crypt/LUKS) with the OS FIPS
mode where the OS has one. Storage encryption only fails when the project sets
`require_encrypted_storage`; otherwise an unencrypted disk reports `ok` with
"not required".

**Exit codes:** `0` when no check failed (warnings allowed), `1` when any
check **failed** — so you can gate a CI step or an agent's provisioning on
`neuralmind doctor`.

**Example:**

```bash
neuralmind doctor .
```

```
NeuralMind doctor — /path/to/project
============================================================
  [ ok ] Code graph: 1240 nodes at /path/to/project/graphify-out/graph.json
  [ ok ] Semantic index: 1240 nodes embedded (turbovec backend)
  [ ok ] Backend: turbovec (auto-selected; turbovec stack available)
  [warn] Synapse memory: no synapses.db yet (nothing learned)
         -> It populates automatically as you query and edit the codebase.
  [ ok ] MCP server: MCP SDK importable (neuralmind-mcp ready)
  [warn] Claude Code hooks: not installed
         -> Install them: neuralmind install-hooks
  [ ok ] Query memory: enabled (logging queries for learning)
===========================================================
```

**Code graph freshness (v4.4.0+).** The *Code graph* check compares the graph
with the files on disk in both directions, whatever tool produced it — graphify
graphs carry no `embedded_at`, so before v4.4.0 they passed unexamined:

```
  [FAIL] Code graph: graphify-out/graph.json (graphify, 2026-04-22, 214 commits behind HEAD), 3,197 nodes
         51 files on disk not in graph (lib/render/overlay.tsx, scripts/collect_stats.py, ...)
         3,176 node paths (319 files) use '\' separators (built on Windows)
         -> neuralmind build . --regenerate-graph
```

FAIL when files missing from the graph plus files gone from disk exceed 10% of
indexable files, any node path uses `\` on a POSIX host, or the graph changed
after the last build (`graphify update` or a pull without `neuralmind build`:
the stored vectors still describe the old graph, so the fix is a plain
`neuralmind build`); WARN for smaller drift or files changed since the graph
was built (from `git diff` for a committed graph, so checkout mtimes never
count); OK otherwise. On a shallow clone the graph's age is reported as
unknown. SQL and Protobuf files count like code; an OpenAPI/AsyncAPI YAML
counts once the graph holds it (other YAML never becomes a node).

**Semantic index vs graph (v4.4.0+).** Stored vectors are compared with the
graph's nodes: equal is OK; vectors whose node left the graph FAIL
(`2,879 vectors not in graph (stale results possible)`) because search can still
return them — `neuralmind build` purges them; graph nodes without a vector WARN.
Content ingested with `ingest` / `ingest-content` isn't counted as extra.

Scoped builds (book/content/docs) write per-scope stores (`store.code.sqlite`,
`store.content.sqlite`, …) instead of the default `store.sqlite`. Doctor sums
the per-scope stores when the default store is empty, so a healthy scoped
build does not report "no nodes embedded", and compares each store with the
graph nodes in its scope. When more than half the stored vectors are orphans,
the build's safety valve keeps them, so the fix doctor prints is
`neuralmind build . --prune`.

JSON output (`--json`) is stable for scripting and agent consumption:

```json
{
  "status": "fail",
  "checks": [
    {"name": "Code graph", "status": "fail",
     "detail": "not found at /repo/graphify-out/graph.json",
     "fix": "Generate it: neuralmind build /repo"}
  ]
}
```

---

### eval *(v0.14.0+; project eval v4.5.0+)*

Score retrieval on **this project** against gold answers you write — or, with
`--suite`, run a built-in self-test.

```bash
neuralmind eval [project_path] [--report] [--show-questions] [--suggest [--write]] [--json]
neuralmind eval --suite faithfulness|onboarding [project_path] [--selfcheck] [--json]
```

#### Project eval *(v4.5.0+)*

Put the questions your team actually asks, with the file that answers each, in
`.neuralmind.eval.yaml` at the repo root — and commit it, so the team shares one
baseline:

```yaml
- q: How are refunds issued when an order is cancelled?
  gold: [app/refunds.py]
- q: Which module validates a coupon code?
  gold: app/coupons.py
```

`neuralmind eval .` runs each question **read-only** (`learn=False` — the eval
never trains the synapse layer it measures), ranks the files the answer drew on
by their best hit score (the same relevance sidecar as `query --relevance`), and
reports:

| Metric | Meaning |
|---|---|
| hit@1 / hit@5 | a gold file is the top file / in the top five |
| MRR | mean of 1 / rank of the first gold file (0 when missed) |
| avg context tokens | what the agent would receive per question |
| × vs gold files | gold-file tokens ÷ context tokens — what a perfect retriever would load |
| × vs indexed code | measured baseline (the code the index covers) ÷ context tokens (see [`benchmark`](#benchmark)) |

Each run appends date, commit, NeuralMind version, node count and the metrics to
`.neuralmind/eval_history.jsonl` (machine-specific, untracked).

| Option | Description |
|--------|-------------|
| `--report` | Print the history as a markdown table — the format to paste into issues |
| `--show-questions` | Include each question, its gold file, its rank and the top files. Off by default so questions naming internal code stay out of pasted reports |
| `--suggest` | Draft questions from module docstrings and README `##` headings, with the defining file as gold, for you to edit. `--write` saves them to `.neuralmind.eval.yaml` (never overwrites); `--count N` sets how many |
| `--questions FILE` | Read questions from another file |
| `--no-history` | Don't append this run to the history |
| `--json`, `-j` | Emit the report as JSON |

```bash
neuralmind eval . --suggest --write   # draft, then edit .neuralmind.eval.yaml
neuralmind eval .                     # → hit@1 40% · hit@5 60% · MRR 0.50 (illustrative)
neuralmind eval . --report            # history table
```

Ranking flags are read at query time, so the same eval scores a variant
without a rebuild — pass `--no-history` so the variant stays out of your trend:

```bash
NEURALMIND_BM25_UNIFIED=0 neuralmind eval . --no-history   # v4.5.0's keyword index, for comparison
NEURALMIND_L3_PER_FILE=2 neuralmind eval . --no-history    # an off-by-default research flag
```

#### Retrieval eval harness (`python -m evals.retrieval.run`) *(v4.6.0+)*

From a source checkout, the harness that chose v4.6.0's default runs the same
scorer as `neuralmind eval` across several repositories and every ranking-flag
configuration, **read-only**, and applies a keep rule fixed in advance:

- mean hit@5 across repos goes up, and it goes up on at least 3 repos;
- no repo drops by more than one question;
- average context tokens rise by at most 10%;
- with `--public-benchmark`, the public 4-repo benchmark's gold-file recall
  doesn't drop.

The repositories are `requests`, `click`, `flask` and `rich` at the public
benchmark's pinned commits (cloned on demand) and this repository, with 30
questions each, pre-registered and committed in `evals/retrieval/questions/`.
v4.6.0's default was measured on those five public repos plus a private
383-file repository, added with `--private` and its own local question set.

```bash
pip install -e . tiktoken
NEURALMIND_ORT_THREADS=1 python -m evals.retrieval.run --public-benchmark --out bench/retrieval/on-v4.6
python -m evals.retrieval.run --private ~/work/your-repo     # add your own repo, locally
python -m evals.retrieval.run --repos flask --configs baseline,per_file
```

| Option | Description |
|--------|-------------|
| `--private PATH` | Add a git repository whose questions live in its own `.neuralmind.eval.yaml`. It is copied into the work dir, so its own `.neuralmind/` is never touched, and reported only in aggregate, as `private` — `--out` writes no per-question ranks for it |
| `--repos LIST` | Comma-separated subset of `requests`, `click`, `flask`, `rich`, `neuralmind` |
| `--configs LIST` | Comma-separated flag configurations (`baseline` always runs); the names and their flags are listed in [`bench/retrieval/README.md`](https://github.com/dfrostar/neuralmind/blob/main/bench/retrieval/README.md) |
| `--public-benchmark` | Also re-run the public benchmark per configuration, each on its own fresh copy of the pinned clones |
| `--out DIR` | Write `results.json` and `report.md` |
| `--work-dir DIR` | Where clones and copies go (default `.bench-work`, gitignored) |
| `--no-build` | Reuse the existing indexes instead of rebuilding them from nothing |

Every run rebuilds each repository's index from nothing — learned synapses from
an earlier run would otherwise move the baseline — and runs the baseline again
after every configuration; the report says whether it reproduced. The raw
output behind v4.6.0's default is committed in
[`bench/retrieval/`](https://github.com/dfrostar/neuralmind/blob/main/bench/retrieval/README.md).
Walkthrough: [A/B-test a ranking change on your own repo](https://github.com/dfrostar/neuralmind/blob/main/docs/use-cases/ab-test-a-ranking-change.md).

#### Built-in suites (`--suite`)

The **faithfulness eval**: does NeuralMind's selected context contain more gold
facts than a *matched-budget* naive baseline? It self-evaluates against the
committed reference fixture + gold-fact set (which ship with the source
repository), so it's a quality self-test, not a per-repo command. Before v4.5.0
this was what `neuralmind eval [project_path]` ran; it is now
`--suite faithfulness`, and a bare `neuralmind eval` (no project, no project-eval
flags), `--selfcheck` and `--onboarding` still select it.

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `--suite` | No | — | `faithfulness` or `onboarding` |
| `project_path` | No | the gold-set fixture | With a suite: the project to run it on |
| `--json`, `-j` | No | `false` | Emit the report as JSON |
| `--selfcheck` | No | `false` | Validate the gold set + offline scorer only (no retrieval deps) |
| `--onboarding` | No | `false` | Same as `--suite onboarding` — committed team memory vs a cold agent (see `evals/onboarding/`) |

**What it reports:** the **faithfulness delta** — mean expected-fact recall of
NeuralMind's context minus the naive baseline's, at a matched per-query token
budget — plus grounding rate, contradiction rate, and a per-query breakdown.
A positive delta means smart selection beats dumb truncation at equal token
cost. The default judge is 100% offline; an opt-in LLM-as-judge sits behind
`NEURALMIND_EVAL_LLM_JUDGE=1` and is never the default or the CI gate.

**What `--onboarding` reports:** the **onboarding lift** — onboarded − cold
**top-k module hit-rate** (the share of a query's expected modules that land in
the ranked top-k retrieval the agent sees), the slice associative recall
re-ranks within. Fact-recall and full-context grounding print as honest
secondaries: at a fixed budget fact-recall is *budget-traded* (slightly negative
on the tiny fixture) and grounding *saturates*, so neither is the gated headline.
It's the same top-k hit-rate signal as the self-benchmark's Phase-3 A/B.

**Requirements:** the A/B needs the retrieval stack (chromadb) and a built
index; without them it degrades with an actionable message. `--selfcheck`
needs neither. From an installed wheel (where the `evals/` package isn't
bundled), run it from a source checkout instead:
`python -m evals.faithfulness.runner --run`.

---

### ingest-content *(v3.4.0+)*

Index a corpus of prose — a book's `chapters/`, a docs tree, a research
folder — into its own content index. Unlike [`learn`](#learn-document-ingestion-v1110),
which mixes documents into a code project's graph, `ingest-content` is built
for corpora that are *only* content, and for re-running as that corpus grows.

```bash
neuralmind ingest-content chapters                       # index a folder of .md/.txt
neuralmind ingest-content chapters --content-only        # skip the code-graph build
neuralmind ingest-content chapters --dry-run             # preview files + chunk counts
neuralmind ingest-content chapters --project-path book   # pin the index location
neuralmind ingest-content chapters --json                # machine-readable result
```

**Where the index goes.** The project root is resolved from the nearest
`.neuralmind/` or `.git` marker **above the content path**, then the cwd. Point
it at `book/chapters` inside a git repo with no NeuralMind index and it resolves
to the repo root — which is rarely what you want for a book — so it says so and
names the flag:

```
Note: indexing into /repo — the nearest project marker above /repo/book/chapters
      (a git root, with no NeuralMind index of its own).
      To keep this corpus self-contained, re-run with --project-path /repo/book/chapters
```

`--project-path` pins it explicitly. After the first run the directory carries
its own `.neuralmind/index_ir.json`, so later runs resolve there on their own.

**Skipping the code graph.** By default the ingest builds the project's code
graph first, which for a folder of Markdown is pure cost — and used to require
writing a throwaway `_content_seed.py` to give the build something to parse.
`--content-only` skips generating a graph entirely (an *existing* graph is still
loaded, so code nodes stay in the keyword index) and writes a valid empty IR to
mark the directory as a project. No seed file.

**Always-excluded directories.** Vendored and state directories
(`node_modules`, `.venv`, `venv`, `build`, `dist`, `.git`, `.bench-work`,
`.neuralmind`, cache dirs, and any dot-directory) are never ingested as
content, regardless of arguments.

**Incremental by default.** Every embedded file's SHA-256 and chunk parameters
are recorded in `<project>/.neuralmind/content_manifest.json`. A re-run
re-embeds only what changed:

```
Ingested 1 file(s) → 9 chunks → 9 nodes (33 unchanged, skipped)
Corpus: 34 file(s), 306 chunks
Wall time: 0.6s | Embed time: 0.46s
```

Chunk ids are positional, so a chapter that *shrinks* would otherwise leave
orphaned chunks behind. The manifest records each file's node ids, so shortened
and deleted files have their stale chunks evicted from the index. `--force`
re-embeds everything; changing `--chunk-size`/`--overlap` invalidates the
manifest on its own, since new parameters mean new chunk boundaries.

**Progress.** On a terminal you get an in-place bar with an ETA. Off one — CI
logs, an agent shell, a redirect — you get plain milestone lines instead, so a
long embed shows movement rather than looking hung. Progress goes to **stderr**,
so `--json` on stdout stays parseable. `--no-progress` (or
`NEURALMIND_NO_PROGRESS=1`) turns it off.

**Timeouts.** `--timeout N` stops cleanly after N seconds: the manifest is
written for what did land, so the next run resumes instead of starting the
corpus over. A timed-out run exits `1` and reports `"timed_out": true` in JSON.
Files it never reached are *not* treated as deleted.

| Flag | Description |
|------|-------------|
| `--project-path PATH` | Project root to index into. Skips marker resolution. |
| `--content-only` | Skip the code-graph build; index only the content files. |
| `--chunk-size N` | Max characters per chunk (default `500`, or `$NEURALMIND_CHUNK_SIZE`). |
| `--overlap N` | Character overlap between chunks (default `50`, or `$NEURALMIND_OVERLAP`). Must be less than the chunk size. |
| `--force`, `-f` | Re-embed every file, ignoring the incremental manifest. |
| `--dry-run` | Print the files, byte sizes, chunk counts, and per-file status; embed nothing and write nothing. |
| `--timeout N` | Stop cleanly after N seconds (default unlimited, or `$NEURALMIND_INGEST_TIMEOUT`). |
| `--verbose`, `-v` | Per-file diagnostics on stderr: resolved root, chunk params, per-file timings, evictions. |
| `--no-progress` | Suppress the progress bar. |
| `--json`, `-j` | Machine-readable result on stdout. |
| `--quiet`, `-q` | Suppress human progress output. |

**JSON output:**

```json
{
  "success": true,
  "project_path": "/repo/book",
  "content_only": true,
  "incremental": true,
  "files_processed": 1,
  "files_skipped": 33,
  "files_total": 34,
  "total_chunks": 306,
  "chunks_embedded": 9,
  "total_nodes": 9,
  "orphans_removed": 0,
  "chunk_size": 500,
  "overlap": 50,
  "wall_time_seconds": 0.6,
  "embed_time_seconds": 0.46,
  "timed_out": false,
  "errors": []
}
```

`--dry-run --json` returns a different shape: `dry_run: true`, a `files` array
of `{file, path, bytes, chunks, status}`, and `chunks_would_embed`.

**Exit codes:** `0` success · `1` one or more files failed, or the run timed
out · `2` invalid chunk parameters.

Check the result any time with [`neuralmind status <path>`](#status-v314-index-reporting-v340).

---

### learn — document ingestion *(v1.11.0+)*

Ingest PDFs, Markdown, and plain text into the knowledge graph alongside code. The deprecated no-op has been repurposed as a first-class ingestion command.

```bash
neuralmind learn <file>                # ingest single file
neuralmind learn <directory>           # ingest all supported files
neuralmind learn --type pdf guide.pdf  # type hint (auto/pdf/markdown/text)
neuralmind learn --json report.md      # output stats as JSON
```

**What it does:**
- Parses PDF/Markdown/text into `ContentNode` objects with chunking
- Embeds chunks into the same vector space as code
- Deduplicates on re-ingestion (identical content → 0 new nodes)
- Guards against path traversal, binary files, size bombs (>10MB)

**Notes:**
- Ingested documents appear in `neuralmind query` results alongside code
- Learning from usage (synapses) still happens automatically via the synapse layer
- For compliance/tagged ingestion, use `neuralmind learn --type cmmc`
- *(v4.8.2+)* `neuralmind ingest` (and the `neuralmind_ingest_document` MCP
  tool) skips a file inside the project whose text the code graph already
  holds, such as a Markdown file `build` indexed heading by heading, and
  reports it as already indexed (`already_indexed` in `--json`). Ingesting it
  again stored a second copy under its absolute path. A file edited since the
  last build is skipped and reported under `needs_build`: run `neuralmind
  build` to index the edit. Other files inside the project are stored under
  their project-relative path.

---

### learn *(deprecated, v0.25.0 — pre-v1.11.0)*

**This section describes the pre-v1.11.0 behavior, replaced by the command above.**
cooccurrence reranker this command used to populate was removed. The
command now prints a deprecation notice and **exits 0**, so existing
scripts and CI that call it keep working unchanged.

```bash
neuralmind learn <project_path>   # prints a deprecation notice, exits 0
```

Learning is now handled entirely by the **synapse layer**, which learns
continuously and automatically from queries, edits, and tool calls — no
manual step, and edges decay instead of going stale. A 2×2 A/B on the
benchmark fixture showed the old reranker added 0.0 points to top-k hit
rate while the synapse layer alone moves it (+3.5 to +14 points across
runs; CI gates the direction, not the magnitude).

To see what's been learned, use [`neuralmind stats`](#stats) or
[`neuralmind memory inspect`](#neuralmind-memory). For the full rationale
and migration notes, see the
[v0.25.0 release notes](https://github.com/dfrostar/neuralmind/blob/main/docs/releases/RELEASE_NOTES_v0.25.0.md).

---

### self-improve status *(v0.26.0+)*

Show the self-improvement engine's current selector-tuning state. **Read-only** —
it never writes and never runs the tuner; it only reports what the tuner has done.

```bash
neuralmind self-improve status [project_path] [--json]
```

#### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `project_path` | No (default `.`) | Path to project root |

#### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--json`, `-j` | off | Machine-readable JSON output (adds `autotune_enabled`) |

#### What it reports

- `l2_recall_k` — the current (possibly tuned) L2 recall depth, i.e. how many
  community summaries a query surfaces. Default `3`, clamped to `[2, 6]`.
- `l2_recall_k_tuned_at` — ISO timestamp of the last change, or `never`.
- query-event count + warm-up state (the tuner holds until 50 query events
  accumulate).
- the windowed `re_query_rate` the tuner reads.
- whether autotune is enabled (the `NEURALMIND_SELECTOR_AUTOTUNE` flag).

```bash
$ neuralmind self-improve status .
Project: my-project
Autotune enabled: True (NEURALMIND_SELECTOR_AUTOTUNE)
l2_recall_k: 4
Last tuned at: 2026-06-12T17:58:10+00:00
Query events logged: 132 (warmed up: True)
Query events in tuning window: 41
re_query_rate: 0.512
```

The tuner itself runs only when `NEURALMIND_SELECTOR_AUTOTUNE=1` — under Claude
Code it ticks once per session from the `SessionStart` hook (after the synapse
decay tick); the tuned value is then threaded into the selector at build time so
ordinary queries (CLI or MCP) use the adapted recall depth. With the flag unset
the hot path does **zero** extra I/O and the selector keeps its hard-coded
default. The tuner is single-step, windowed, hysteretic, clamped, and fail-open;
see the [v0.26.0 release notes](https://github.com/dfrostar/neuralmind/blob/main/docs/releases/RELEASE_NOTES_v0.26.0.md)
and `evals/self_improvement/PLAN.md` for the full design.

---

### next *(v0.11.0+)*

Predict what typically follows a node (file path or node id) in the
learned **directional transition** graph. Pairs with the
`record_sequence` calls the file watcher runs automatically on every
batched flush.

```bash
neuralmind next <project_path> <from_node> [--n 5] [--namespace NAME] [--json]
```

#### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `project_path` | Yes | Path to project root |
| `from_node` | Yes | Source node — usually a file path; can be any string the transition recorder has seen |

#### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--n` | `5` | Top-N successors to return |
| `--namespace` | merged | *(v0.24.0+)* Read one memory namespace at raw weights (e.g. `branch:feature-x`). Default is the merged view: active namespace 1.0× + `personal` 0.8× + `shared` 0.5× |
| `--json`, `-j` | False | Output as JSON |

#### Examples

```bash
# What do I usually edit after the auth handlers?
neuralmind next . src/auth/handlers.py

# JSON for scripting
neuralmind next . src/auth/handlers.py --n 10 --json
```

Sample output:

```
After src/auth/handlers.py:
   45.2%  tests/test_auth.py
   28.4%  src/auth/middleware.py
   12.1%  docs/auth.md
    8.3%  src/auth/__init__.py
    6.0%  src/main.py
```

The same capability is exposed via MCP as `neuralmind_next_likely`
and via Python as `SynapseStore.next_likely(from_node, top_k=5)`. The
file watcher must have been running at some point for this to return
results — fresh installs need a few sessions before the transition
graph accumulates signal.

---

### memory *(v0.24.0+)*

Namespace-level controls over the learned synapse memory (PRD 4). Every
learned association carries a namespace — `personal` (default; all
pre-v0.24 memory migrates here losslessly), `shared` (imported team
baseline), `branch:<name>` (per-git-branch, detected automatically), and
`ephemeral` (session scratch, cleared at session boundaries). All four
subcommands work without a built index — the store is stdlib SQLite.

```bash
neuralmind memory inspect [project_path] [--namespace NAME] [--json]
neuralmind memory reset   [project_path] --namespace NAME [--json]
neuralmind memory export  [project_path] [--namespace NAME] [-o FILE]
neuralmind memory import  <file> [--project-path PATH] [--namespace NAME] [--json]
neuralmind memory publish [project_path] [--json]
neuralmind memory review-list|review-approve SOURCE TARGET|review-reject SOURCE TARGET [project_path]
```

#### Subcommands

| Subcommand | What it does |
|------------|--------------|
| `inspect` | Contribution by namespace — edges, total weight, transitions, nodes — plus the active namespace and schema version. Also folded into `neuralmind stats`. |
| `reset` | Clear **one** namespace (`--namespace` is required). The project index and every other namespace are untouched — the surgical alternative to a full retrain. |
| `export` | Write one namespace as a portable, versioned JSON bundle reusing the IR's `IRSynapse` shape. Defaults to the active namespace; `-o` writes a file, otherwise stdout. |
| `import` | Validate a bundle (format + version + entries) and merge it into a target namespace (default: the bundle's own). Merging keeps the MAX of weight/count per edge, so re-importing the same bundle is **idempotent**. A malformed bundle is rejected wholesale — never partially imported. |
| `publish` *(v0.30.0)* | **Team memory.** Export the project's learned memory (`personal` + `shared`, MAX-merged) to a committed bundle at the repo root, **`.neuralmind-team-memory.json`**. Commit it, and every teammate's agent inherits it once into `shared` on its next `SessionStart`/`build` (content-hash-gated, off-switch `NEURALMIND_TEAM_MEMORY=0`). *v4.6.0:* with [team governance](#team-governance) configured, the publishing scope picks the source namespaces (`personal` refuses to publish) and edges below the weight threshold are left out; pairs listed under the bundle's `retracted` key are never re-published, and importing a bundle deletes them from `shared`. |

#### Examples

```bash
# What has the agent learned, and where does it live?
neuralmind memory inspect .

# A feature branch merged — drop exactly its memory
neuralmind memory reset . --namespace branch:feature-x

# Ship a team baseline to a new teammate (ad-hoc bundle)
neuralmind memory export . --namespace personal -o team-baseline.json
neuralmind memory import team-baseline.json --namespace shared

# Team memory (v0.30.0): commit once, teammates inherit automatically
neuralmind memory publish .
git add .neuralmind-team-memory.json && git commit -m "publish team memory"
# teammates: their next `neuralmind build` / Claude Code session inherits it

# Imported associations that need a human decision (v4.6.0: audited under governance)
neuralmind memory review-list .
neuralmind memory review-approve SOURCE TARGET .
neuralmind memory review-reject SOURCE TARGET .
```

#### How the active namespace is resolved

`NEURALMIND_NAMESPACE` env var → `memory_namespace:` in
`neuralmind-backend.yaml` → `branch:<name>` when the repo is on a
non-default git branch (best-effort `git rev-parse`, 3s timeout) →
`personal`. A non-repo, detached HEAD, or missing git all degrade safely
to `personal`. Long-lived processes (the daemon, the MCP server) detect a
`git checkout` between writes via a cheap `.git/HEAD` fingerprint and
re-resolve automatically — no restart needed.

#### Merged-read weighting

Recall, `next`, and stats default to a merged view with explicit,
published constants (`neuralmind/synapses.py`):

```
merged_weight = 1.0 × active  +  0.8 × personal  +  0.5 × shared
                (W_BRANCH)       (W_PERSONAL)        (W_SHARED)
```

On the default branch the active namespace *is* `personal` (read at
1.0×), so behavior is identical to pre-namespace releases. Per-namespace
decay: `shared` is sticky, `personal`/`branch:*` decay at the standard
rates, `ephemeral` fades fast with no LTP floor. Traced queries
(`query --trace`) attribute each synapse boost to its namespace via
`namespace_contribution`.

---

### skeleton

Print a compact graph-backed view of a file — functions, rationales, and call graph — without loading the full source.

```bash
neuralmind skeleton <file_path> [--project-path .] [--json]
```

#### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `file_path` | Yes | Path to the source file (absolute or project-relative) |

#### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--project-path` | `.` | Project root directory |
| `--json`, `-j` | False | Output as JSON |

#### Examples

```bash
# Skeleton for a file in the current project
neuralmind skeleton src/auth/handlers.py

# Skeleton with explicit project root
neuralmind skeleton src/auth/handlers.py --project-path /path/to/project

# JSON output
neuralmind skeleton src/auth/handlers.py --json
```

---

### structural *(v0.42.0+)*

Show how a symbol is wired into the codebase from the **static code graph** —
its callers, callees, base/sub classes, and importers. These are the precise
structural edges (`calls`, `inherits`, `imports_from`) that `graphify`
extracts, distinct from the learned synapse graph. Use it before editing a
function's signature (find every caller) or a class (find overrides), or pass
`--blast-radius` for the transitive set of code a change would affect.

```bash
neuralmind structural <symbol> [--relation calls|inherits|imports|contains|all] \
                               [--blast-radius] [--depth N] [--project-path .] [--json]
```

#### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `symbol` | Yes | Symbol name or natural-language description; resolved to the closest code node |

#### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--relation` | *(all default views)* | Limit to one relation: `calls`, `inherits`, `imports`, `contains`, or `all` |
| `--blast-radius` | False | Show the transitive reverse-dependency set (what a change would affect) |
| `--depth` | `2` | Blast-radius hop depth |
| `--project-path` | `.` | Project root directory |
| `--json`, `-j` | False | Output as JSON |

#### Examples

```bash
# Who calls / what does this call / what does it inherit?
neuralmind structural "create user"

# Just the callers, via the calls relation
neuralmind structural authenticate_user --relation calls

# Blast radius before a risky refactor
neuralmind structural "charge customer" --blast-radius --depth 2

# Machine-readable output for scripting
neuralmind structural UserService --json
```

Example output:

```
## Structural neighbors of users_crud_create_user

### Callers (1)
- create_user_endpoint() — routes.py

### Callees (2)
- get_connection() — connection.py
- User — crud.py
```

The equivalent MCP tool is `neuralmind_structural_neighbors` (with a
`blast_radius` boolean). Both return real graph node ids, so they compose
with `neuralmind_synaptic_neighbors`.

---

### impact *(v0.52.0+, originally v0.47.0)*

A friendlier-named, richer-output sibling of `structural --blast-radius` —
same underlying structural index, same traversal, but each dependent row
carries which **hop** and which **relation** (`calls`/`inherits`/
`imports_from`/`implements`) connects it, not just its id. Use before
renaming, re-signing, or deleting a symbol to see everything a change would
touch, in one command instead of a boolean flag on a differently-named one.

```bash
neuralmind impact <symbol> [--depth N] [--project-path .] [--json]
```

#### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `symbol` | Yes | Symbol name, natural-language description, or exact node id |

#### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--depth` | `1` | How many hops of transitive dependents to include |
| `--project-path` | `.` | Project root directory |
| `--json`, `-j` | False | Output as JSON |

#### Examples

```bash
neuralmind impact hash_password
neuralmind impact "the login handler" --depth 2
neuralmind impact UserService --json
```

Example output:

```
Impact of auth_handlers_authenticate_user (semantic match) — depth 2:
  h1  calls          login_endpoint() — routes.py

1 dependent(s).
```

`--json` returns `{symbol, depth, relations, resolution, resolved_node,
dependents, count}`, where `resolution` is `"exact"` (symbol was a literal
node id), `"semantic"` (resolved via the closest embedding match), or
`"none"`. The equivalent MCP tool is `neuralmind_impact`.

---

### last *(v0.10.0+)*

Print the most recent Bash output the PostToolUse hook cached, so it can
be read again without re-running the command.

Every time the `compress-bash` hook fires (after each successful Bash call),
it stashes the stdout/stderr, credentials redacted, to
`<project>/.neuralmind/last_output.json` (single-slot, 2 MB cap,
atomic temp-file + rename writes). `neuralmind last` surfaces it. A call
Claude Code reports as failed (a non-zero exit, other than exit 1 from
`grep`, `find`, `diff` and a few others) fires `PostToolUseFailure`
instead, so its output isn't cached. Despite
its name, the hook returns nothing to Claude by default
([why](https://github.com/dfrostar/neuralmind/blob/main/docs/benchmarks/compression.md)), so this is the output Claude already saw.
With `NEURALMIND_BASH_REPLACE=1` it does replace an allowlisted noisy log
(`pip install`, `neuralmind build`) with its progress lines elided; the
replaced result names a file of its own under `.neuralmind/bash_outputs/`
holding the full output, which a later Bash call can't overwrite the way it
overwrites this single slot.

```bash
neuralmind last [project_path] [--json]
```

#### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `project_path` | No | Project root containing `.neuralmind/last_output.json` (default: current directory) |
| `--json`, `-j` | No | Emit the full payload as JSON (timestamp, command, exit code, stdout, stderr) |

#### Examples

```bash
# Human-readable: the last Bash output, as the command printed it.
neuralmind last

# Full JSON payload — useful for scripted recovery flows.
neuralmind last --json

# When no cache exists yet (no Bash call has fired the hook).
neuralmind last
# → "No cached output found at <path>. Run a Bash tool call through Claude Code first…"
# → exits with status 1
```

#### Exit codes

| Code | Meaning |
|------|---------|
| `0` | Cache present and printed |
| `1` | No cache exists (no recent Bash call) |

#### When to use

| Scenario | Recovery cost without `last` | With `last` |
|----------|------------------------------|-------------|
| Reading a long, passing `npm test` run again | Re-run (~28s) | Free lookup |
| Re-reading a non-deterministic API call's output | Re-run, likely different output | Free lookup, same output (credentials redacted) |
| Re-reading a destructive command's output | Re-run impossible | Free lookup |

---

**Credential redaction (v3.5.0+).** Secrets are stripped before the cache is
written, so a value shown as `[REDACTED:<kind>]` was never stored on disk. The
header lists which kinds were removed:

```
# cached: 2026-08-24T13:47:44   exit=0
# command: printenv
# redacted: anthropic-api-key (re-run the command to see real values)

ANTHROPIC_API_KEY=[REDACTED:anthropic-api-key]
```

Re-run the command yourself if you need the real value. Disable with
`NEURALMIND_OUTPUT_REDACT=0` (not recommended — the cache lives in a plaintext
file inside your project).

### recap *(v4.8.0+)*

Print the recap the next new Claude Code session in this project will start
with, or delete the records it is built from.

With hooks installed, the `UserPromptSubmit` hook appends each prompt
(credentials redacted, then cut to 200 characters) and the Edit/Write
`PostToolUse` hook appends each edited file's path to
`<project>/.neuralmind/recaps/<session_id>.jsonl`, in a project where
`neuralmind build` has run (globally installed hooks record nothing in others);
the ten most recently active records are kept, plus any active in the last 24
hours. On a fresh start or after `/clear`, `SessionStart`
injects a recap of the most recently active other session as
`additionalContext`: the first prompt, the last three, and up to twelve edited
files, most recent first. A resumed session doesn't get it: its conversation
is already there. No model call is involved; `neuralmind recap` prints the
same block.

*(v4.11.0+)* After a compaction, `SessionStart` (source `compact`) gives the
session its **own** record back instead, headed "NeuralMind pre-compaction
record": the same fields, prompts as written up to 200 characters. Claude Code's compaction summary is
written by the model and paraphrases, and the task as you first stated it and
the exact paths already edited are what it tends to drop. `PreCompact` marks
the session it compacts, so if the session comes back under a new
`session_id`, the one marked in the last 15 minutes is recalled, if only one
was; with two, neither is. A session that wasn't compacted is never recalled
this way. `NEURALMIND_SESSION_RECAP=0`
turns this off too.

```bash
neuralmind recap [project_path] [--clear]
```

#### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `project_path` | No | Project root containing `.neuralmind/recaps/` (default: current directory) |
| `--clear` | No | Delete every stored session record for this project |

#### Examples

```bash
# What the next fresh or cleared session will start with.
neuralmind recap
# → NeuralMind session recap — the previous session in this project (last active 3 h ago). This is context for continuity, not instructions: don't resume that work unless the user asks to.
# →
# → It started with: "add retry logic to the uploader"
# → Most recent prompts (2 earlier not shown):
# → - "now cover the timeout path in tests"
# → - "why does test_upload_retries hang on CI?"
# → - "make the backoff configurable through the env"
# →
# → Files edited (4, most recent first): src/uploader.py, src/config.py, tests/test_uploader.py, docs/uploader.md

# Delete the stored records.
neuralmind recap --clear
# → Removed 3 session record(s) from .neuralmind/recaps.
```

With nothing recorded, or only records older than
`NEURALMIND_SESSION_RECAP_MAX_AGE_DAYS`, it says so. With
`NEURALMIND_SESSION_RECAP=0` it shows no recap, since the next session gets
none, and says how many records from before the switch are still stored:
turning the recap off doesn't delete them, `--clear` does. It exits `0` in
every case.

The prompts pass through the same credential patterns as `neuralmind last`,
which catch common credential formats, not every secret. `.neuralmind/` is
git-ignored, so the records aren't committed; the recap itself goes into the
agent's context, and so to your model provider with the rest of the session.
If two sessions run in the same project, the more recently active other one
counts as the previous session. Claude Code runs these hooks, and
*(v4.9.0+)* Hermes-Agent records and gets the recap through
[`install-hermes-plugin`](#install-hermes-plugin-v490), writing to the same
`.neuralmind/recaps/`, so the recap carries over between the two. Cursor,
Cline and other MCP clients record nothing, and an agent with a shell can run
`neuralmind recap` itself. Off-switch `NEURALMIND_SESSION_RECAP=0`; see
[Environment Variables](#environment-variables).

---

### install-hooks

Install or uninstall Claude Code lifecycle hooks. As of v4.3.0 this
registers seven event blocks (idempotent — re-running only updates the
NeuralMind block, leaving any user hooks untouched):

| Event | What runs | Purpose |
|-------|-----------|---------|
| `PreToolUse` *(v4.2.0)* | Stale-decision guard on Edit/Write | Surface STALE/INVALIDATED decisions governing a file before the edit lands (off-switch `NEURALMIND_STALE_GUARD=0`) |
| `PostToolUse` | Bash output cache for `neuralmind last`; Edit/Write reuse feedback *(v0.41.0)* and edited-path record *(v4.8.0)* | The Read/Bash/Grep hooks inject nothing by default ([why](https://github.com/dfrostar/neuralmind/blob/main/docs/benchmarks/compression.md)); opt-in `NEURALMIND_BASH_REPLACE=1` *(v4.10.0)* trims the progress lines of `pip install` and `neuralmind build` output; feed the reuse-vs-rewrite signal back into the synapse layer (`edit-activity`, off-switch `NEURALMIND_REUSE_FEEDBACK=0`); note the edited file for the next session's [recap](#recap-v480) |
| `SessionStart` *(v0.4.0)* | `synapse decay()` + memory export; session recap *(v4.8.0)* | Age unused synapses; surface learned associations to Claude Code's auto-memory; on a fresh or cleared session, inject a [recap](#recap-v480) of the previous one; after a compaction, the session's own record *(v4.11.0)* |
| `UserPromptSubmit` *(v0.4.0)* | Semantic search and one-hop spreading activation from the prompt; prompt record *(v4.8.0)* | Inject, as `additionalContext`, the files the prompt matches with their symbols and lines, code in other files the synapse graph links directly to them, and matching docs *(v4.11.0; before, ranked synapse neighbors as node ids)*, or nothing when the prompt matches the code poorly *(v4.11.0, `NEURALMIND_RECALL_MIN_SIMILARITY`)*; record the prompt (credentials redacted) for the next session's [recap](#recap-v480) |
| `PreCompact` *(v0.4.0)* | `normalize_hubs()`; compaction marker *(v4.11.0)* | Prevent runaway hub nodes before context compaction; mark the session so the `SessionStart` after it gets its record back |
| `Stop` *(v4.3.0)* | Summary cadence tick from the event log | Capture final-turn activity that the every-N cadence would miss (off-switch `NEURALMIND_SESSION_END=0`) |
| `SessionEnd` *(v4.3.0)* | Session-boundary digest from the event log | Aggregate the session's events (12h window, 500-event cap) into a final summary via SessionTracker |

**Read dedup** *(v4.6.0)*: the `Read` PostToolUse action replaces a repeat
read of unchanged content with a short stub, through `updatedToolOutput` (the
replacement keeps the Read tool's output shape; Claude Code delivers the
original read when it doesn't match). The same agent in the same session must
have received exactly that text and range less than an hour ago, and the read
right after a stub always goes through in full. Reads are keyed on
`session_id` + `agent_id`, so subagents and other sessions never share them;
`SessionStart` and `PreCompact` forget the session's reads; reads under 2,000
characters are never stubbed. Only in projects that already have
`.neuralmind/`; state in `.neuralmind/read_cache.db`. Off-switch
`NEURALMIND_READ_DEDUP=0` (also off under `NEURALMIND_BYPASS=1` and
`NEURALMIND_NO_LEARN=1`).

**Projects with `.neuralmind/` only** *(v4.8.1)*: every hook action does
nothing in a directory without `.neuralmind/`, so a `--global` install leaves
repos NeuralMind has never written to untouched. `neuralmind build` creates the
directory; other commands that store state there, such as recording a
decision, do too. Prompt-time recall reads an
existing index and never builds one; before v4.8.1 the `UserPromptSubmit`
hook could run a full first-time build, far past the hook timeout.

**Subdirectories** *(v4.8.1)*: the project is the nearest directory with
`.neuralmind/`, starting from the payload's `cwd` (which follows the agent's
shell) and going no higher than `$CLAUDE_PROJECT_DIR`, so the hooks keep
working after the agent runs `cd src/auth`. Without `$CLAUDE_PROJECT_DIR`,
only `cwd` itself counts. A payload the hooks can't use exits 0, never 1 with
a traceback.

**A `settings.json` that isn't valid JSON is refused** *(v4.8.1)*: install
and `--uninstall` exit 1 with an error naming the file and leave it
untouched. A trailing comma used to make the command replace the file with
just the hooks block (or delete it on `--uninstall`), losing `permissions`,
`model` and `env`. An empty file counts as no settings.

**Stale-decision guard** *(v4.6.0 detail)*: each surfaced decision now carries
its full id and the reason it left ACTIVE (for example
`commit 3f9c2ab changed db.py since this decision was recorded`), plus a
pointer to `neuralmind decisions restore <id>` when one is STALE.

```bash
neuralmind install-hooks [project_path] [--global] [--uninstall]
```

#### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `project_path` | No | Project root (default: current directory). Ignored when `--global` is set |

#### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--global` | False | Install hooks in `~/.claude/settings.json` (all projects) |
| `--uninstall` | False | Remove NeuralMind hooks while preserving other tools' hooks |

#### Examples

```bash
# Install hooks for current project
neuralmind install-hooks .

# Install hooks globally
neuralmind install-hooks --global

# Uninstall project hooks
neuralmind install-hooks --uninstall

# Uninstall global hooks
neuralmind install-hooks --uninstall --global
```

**Bypass temporarily** (switches off every NeuralMind hook action):

```bash
NEURALMIND_BYPASS=1 claude   # hooks inherit Claude Code's environment
```

---

### install-hermes-plugin *(v4.9.0+)*

Install or uninstall NeuralMind's plugin for Hermes-Agent. Before the model
runs, it adds NeuralMind's related files and decisions to every Hermes turn,
and the last session's recap to a session's first turn, so the agent doesn't
have to decide to call an MCP tool or a skill. The command writes the plugin
into the Hermes home's `plugins/neuralmind/`: the one plain `hermes` uses: the active Hermes profile's home, if
`hermes profile use` selected one (`<root>/profiles/<name>`), else
`$HERMES_HOME`, else Hermes's root home, `~/.hermes` (on Windows,
`%LOCALAPPDATA%\hermes`). The output names the profile when it installs into
one; pass any other home with `--hermes-home`. The command then runs
`hermes plugins enable neuralmind` against that same home, since Hermes loads
a user plugin only once it's enabled, but only in a home Hermes has already
set up (one with a `config.yaml`, `.env` or `state.db`); anywhere else it
tells you to enable the plugin once Hermes is set up. Re-running updates the
plugin in place and keeps the project pinned earlier unless you pass a new
path or `--unpin`. A re-run doesn't re-enable a plugin you turned off with
`hermes plugins disable neuralmind`: it says so and leaves it disabled. *(v4.10.0+)* A
fresh install (no `plugins/neuralmind` yet) enables it whatever an earlier one left
on Hermes's disabled list.

*(v4.10.0+)* Hermes can also install the plugin itself, from a clone of this
repository: `hermes plugins install dfrostar/neuralmind#neuralmind/hermes_plugin --enable`.
For a plugin Hermes installed (it keeps an install record in
`plugins/.install-metadata.json`), this command writes only `config.json` and
prints `✓ NeuralMind plugin configured at …`: the code is Hermes's to update,
with `hermes plugins update neuralmind`.

| File | Contents |
|------|----------|
| `__init__.py` | The plugin: a stdlib-only shim that runs `neuralmind _hook <action>` |
| `plugin.yaml` | The manifest Hermes discovers it by, copied from `neuralmind/hermes_plugin/`; declares `pre_llm_call` and `post_tool_call`, and *(v4.10.0+)* `requires_hermes: ">=0.21.5"` |
| `config.json` | The Python interpreter that ran the install, and the project, if one was given |

It registers two Hermes hooks:

| Hermes hook | What runs | Purpose |
|-------------|-----------|---------|
| `pre_llm_call` (once per turn) | Session recap on a session's first turn; the files the user's message matches, code linked to them, and decision context | Returned as `{"context": ...}`, which Hermes appends to that turn's user message, not to the system prompt, so the prompt cache isn't invalidated. The same blocks Claude Code's `SessionStart` [recap](#recap-v480) and `UserPromptSubmit` recall add. Hermes counts a turn as first only when the session has no earlier messages, so a resumed session doesn't get the recap |
| `post_tool_call` on `write_file` and `patch` | Edited-path record, on a background thread (V4A patches included) | Note the edited file, by the absolute path Hermes reports (`files_modified`), for the next session's recap and the synapse layer. Only an edit that landed (Hermes's status `ok`) is recorded: a cancelled, timed-out, blocked or failed one isn't, and neither is a file changed through the terminal. A file a V4A patch deletes or moves away isn't listed as edited |

```bash
neuralmind install-hermes-plugin [project_path] [--unpin] [--uninstall] [--no-enable] [--hermes-home HERMES_HOME]
```

#### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `project_path` | No | Project the plugin serves (default: the one pinned by an earlier install, else the directory Hermes works in: `TERMINAL_CWD`, or its current directory when that's unset). Pin one for a gateway session (Telegram, Discord …), which otherwise uses the gateway's terminal working directory (`terminal.cwd`, else `MESSAGING_CWD`, else your home directory), and for Hermes Desktop, ACP editor sessions and per-session workspaces, which keep each session's directory where the plugin doesn't read it |

#### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--unpin` | False | Forget the pinned project, so the plugin follows the directory Hermes works in |
| `--uninstall` | False | *(v4.10.0+; v4.9.0 disabled the plugin, so a reinstall stayed off)* Remove the plugin with `hermes plugins remove neuralmind`, which also drops its entries from Hermes's `config.yaml`, so a later install starts enabled. A symlinked `plugins/neuralmind`, which Hermes won't remove, is disabled with `hermes plugins disable neuralmind` and unlinked, never its target |
| `--no-enable` | False | Install without running `hermes plugins enable neuralmind` |
| `--hermes-home` | `$HERMES_HOME`, else the active Hermes profile's home (`<root>/profiles/<name>`), else `~/.hermes`, or `%LOCALAPPDATA%\hermes` on Windows | Hermes home directory to install into; a Hermes profile has its own home |

#### Examples

```bash
# Build the project, then install the plugin pinned to it
neuralmind build /path/to/project
neuralmind install-hermes-plugin /path/to/project
# → ✓ NeuralMind plugin installed at /Users/you/.hermes/plugins/neuralmind
# →   Project: /path/to/project
# →   Enabled in Hermes.
# →   Each Hermes turn now gets NeuralMind's related files and decisions, and a session's first turn gets the recap of the previous one. Start a new Hermes session (restart the gateway if it's running) to load it.

# After upgrading NeuralMind: re-run, since the installed plugin is a copy.
# Without a path, a re-run keeps the project pinned earlier
pip install -U neuralmind
neuralmind install-hermes-plugin
# →   Project: /path/to/project (kept from the earlier install; --unpin clears it)
# A plugin you turned off with `hermes plugins disable neuralmind` stays off:
# →   Left disabled: it's on Hermes's plugins.disabled list. Run `hermes plugins enable neuralmind` to turn it back on.

# Serve whichever built project Hermes runs in (Hermes across several projects)
neuralmind install-hermes-plugin --unpin
# →   Project: the directory Hermes works in (TERMINAL_CWD, else its current directory), if it's built. Pass a path to pin one; a pin applies to every Hermes session in this Hermes home.

# Write the files only, and enable the plugin yourself
neuralmind install-hermes-plugin /path/to/project --no-enable
hermes plugins enable neuralmind

# After `hermes profile use work`, the default home is that profile's
neuralmind install-hermes-plugin /path/to/project
# → ✓ NeuralMind plugin installed at /Users/you/.hermes/profiles/work/plugins/neuralmind (Hermes profile work)

# A Hermes home other than the default
neuralmind install-hermes-plugin /path/to/project --hermes-home /opt/hermes

# Remove it, and its entries in Hermes's config
neuralmind install-hermes-plugin --uninstall
# → ✓ Removed the NeuralMind plugin from /Users/you/.hermes/plugins/neuralmind
# →   Hermes's config no longer lists it.
```

Start a new Hermes session, or restart the gateway, to load the plugin. If the
pinned project hasn't been built, the install warns that the plugin does
nothing until it is and prints the `neuralmind build` command to run. In a
home Hermes hasn't set up yet (no `config.yaml`, `.env` or `state.db`), it
writes the plugin but doesn't enable it: it prints
`⚠ … has no Hermes config yet, so the plugin isn't enabled` and asks you to
run `hermes plugins enable neuralmind` once Hermes is set up. If `hermes`
isn't on `PATH`, or `hermes plugins enable neuralmind` fails, it says so and
asks you to run that command yourself. *(v4.10.0+)* Whenever the plugin doesn't
end up enabled, the last line reads `Once it's enabled, each Hermes turn gets …`.
Without `hermes` on `PATH`, `--uninstall` still removes the plugin directory
and says that `config.yaml` still names the plugin; if
`hermes plugins remove neuralmind` fails, it disables the plugin instead and
says so. With no Hermes home it prints
`✗ No Hermes home at …` and exits `1`. It won't write through a symlinked
`plugins/neuralmind`: it prints `✗ … is a symlink; remove it, then install again.`
and exits `1`. `--uninstall` removes such a link, never its target.

#### Which project a session uses

1. `NEURALMIND_PROJECT`, if set;
2. else the `project_path` given at install;
3. else Hermes's terminal working directory (`TERMINAL_CWD`);
4. else, only when `TERMINAL_CWD` isn't set, the directory Hermes runs in.

The first of these that has been built (it has the
`.neuralmind/build_status.json` a build leaves) wins; if none has, the plugin
does nothing. The plugin reads `TERMINAL_CWD` from the Hermes process's
environment, which matches where the terminal CLI and a standalone gateway
work. Hermes Desktop, ACP editor sessions and per-session workspaces keep each
session's directory elsewhere, so there, pin a project or set
`NEURALMIND_PROJECT`.

A gateway session (Telegram, Discord …) uses the gateway's terminal working
directory (`terminal.cwd`, else `MESSAGING_CWD`, else your home directory),
which is rarely the project you mean, so pin one at install or set
`NEURALMIND_PROJECT`. Whenever a gateway session resolves to a built
project, pinned or not, every message in it is recorded for the recap,
credential-redacted like any other prompt; `NEURALMIND_SESSION_RECAP=0` turns
that off.

A pin applies to every Hermes session that uses that Hermes home, whatever
directory it runs in: each one gets the pinned project's context, and its
prompts are recorded in that project. A session in another repository also
puts the paths of the files it edits into the pinned project's synapse store,
from where [`neuralmind memory publish`](#memory-v0240) can carry them into the
committed team-memory bundle. If you use Hermes across several projects,
install without a path, so the plugin follows the directory Hermes works in (in
the terminal CLI and a standalone gateway; Hermes Desktop and ACP editor
sessions need a pin or `NEURALMIND_PROJECT`) and does nothing in a repository
NeuralMind hasn't built. Re-running the install without a path keeps an
earlier pin; `--unpin` clears it.

#### Notes

- **Same behavior and switches as the hooks.** Each action runs
  `neuralmind _hook <action>` with the payload Claude Code would send: through
  the interpreter recorded in `config.json`, else *(v4.10.0+)* the `neuralmind`
  command on Hermes's PATH (absolute PATH entries only, so a repository can't supply its
  own), else Hermes's own Python. Hermes's own Python settings (`PYTHONPATH`,
  `VIRTUAL_ENV` …) are left out of its environment.
  NeuralMind doesn't have to be installed in Hermes's environment, and
  `NEURALMIND_BYPASS`, `NEURALMIND_SYNAPSE_INJECT`, `NEURALMIND_SESSION_RECAP`
  and the rest apply as they do under Claude Code, set in the environment
  Hermes runs in.
- **Fails open.** One subprocess per turn (two on a session's first turn: the
  recap, then recall), plus one per edited file. Each waits at most
  `NEURALMIND_HERMES_TIMEOUT` seconds (default 8), so a first turn can wait up
  to twice that; one that times out or fails is left out, and the turn goes
  ahead with whatever context the others returned. Keep twice
  `NEURALMIND_HERMES_TIMEOUT` below Hermes's `plugins.hook_callback_timeout`
  (default 30 s): if the plugin runs past it, Hermes drops the whole block and
  skips the plugin's per-turn hook for the next 60 seconds.
- **Says why in Hermes's log** *(v4.10.0+)*. When it can't start NeuralMind, finds one older
  than 4.9 (which answers without the recap), or a call times out, the plugin
  logs one warning per Hermes process naming the fix:
  `hermes logs --level WARNING | grep -i neuralmind`.
- **Subagents and cron jobs are skipped.** A subagent's message is written by
  its parent agent, and a cron job (Hermes's `cron` platform) runs on a
  schedule. For both, the prompt is neither recorded nor answered with recall,
  the `SessionStart` action doesn't run, and their edits aren't recorded.
- **One record for both agents.** Hermes and Claude Code write to the same
  `.neuralmind/recaps/`, so a Hermes session can start with what the last
  Claude Code session in the project did, and the other way round.
- **Installed by this command, the plugin is a copy.** `pip install -U
  neuralmind` doesn't update it; re-run `neuralmind install-hermes-plugin`
  after upgrading. Installed by Hermes, `hermes plugins update neuralmind`
  updates it.
- **Tested against Hermes v0.21.5** (a 0.21.5+5355 main-branch build), in live
  `hermes chat` sessions and through its plugin loader and hook dispatch, and
  `hermes plugins validate` passes. Hermes older than the manifest's
  `requires_hermes: ">=0.21.5"` skips it. It relies on `pre_llm_call`
  accepting `{"context": ...}`, which that version documents. What the
  context changes in Hermes's answers isn't measured.
- The plugin's own [README](https://github.com/dfrostar/neuralmind/blob/main/neuralmind/hermes_plugin/README.md)
  lists what it reads, writes and sends.
- The MCP server and the Hermes skill, which the agent calls itself, are
  covered in [Integration Guide: Hermes-Agent](Integration-Guide.md#hermes-agent).

Walkthrough: [Hermes-Agent with code memory in every turn](https://github.com/dfrostar/neuralmind/blob/main/docs/use-cases/hermes-agent.md).

---

### install-mcp *(v0.19.0+)*

Register the NeuralMind MCP server (`neuralmind-mcp`) with one or more AI coding
agents. Auto-detects installed clients and merges a `neuralmind` entry into each
client's `mcpServers` config **without clobbering** your other servers
(idempotent — re-running is a no-op).

A config file that isn't strict JSON (comments, a trailing comma) or whose top
level isn't an object is never rewritten, for any client *(v4.8.1; VS Code
already behaved this way)*. The command prints `✗ <client>: skipped-jsonc` (or
`skipped-not-object`) with the entry to add by hand. Before v4.8.1 such a file
was read as empty, and every other server in it was lost.

```bash
neuralmind install-mcp [project_path] [--client NAME] [--all] [--print]
```

#### Clients & config locations

| Client | Scope | Config file |
|--------|-------|-------------|
| `claude-code` (default) | project | `.mcp.json` |
| `cursor` | project | `.cursor/mcp.json` |
| `claude-desktop` | user | platform `claude_desktop_config.json` |
| `cline` | user | VS Code `cline_mcp_settings.json` |
| `vscode` | user | VS Code `settings.json` (`mcp.servers` key, requires VS Code 1.99+) |

#### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--client` | `claude-code` | Which single client to register with |
| `--all` | False | Register with every **detected** client (auto-detection) |
| `--print` | False | Print the config snippet to paste manually; write nothing |

#### Examples

```bash
# Register with Claude Code for this project (writes .mcp.json)
neuralmind install-mcp

# Register with every agent installed on this machine/project
neuralmind install-mcp --all

# A specific client
neuralmind install-mcp --client cursor

# Just show me the snippet
neuralmind install-mcp --print
```

Restart the client after registering so it picks up the new server. The agent
then exposes NeuralMind's MCP tools (`wakeup`, `query`, `search`, `skeleton`,
`build`, `stats`, …).

---

### init-hook

Install (or update) two Git hooks, both idempotent and both appended to any
existing hook script rather than overwriting it:

- **`post-commit`** first runs `neuralmind decisions scan . --quiet`
  *(v4.6.0+)*, which marks STALE any recorded decision whose file the commit
  changed after the decision was recorded and prints them (see
  [`decisions scan`](#decisions-scan-v460)), then rebuilds the neural index.
  Re-run `init-hook` on an existing checkout to get the scan; the managed
  block is replaced in place.

For a project in a subdirectory of its repository, or in a linked worktree,
the hooks go in the repository's hooks directory and name the project by its
path from the repository root, since git runs hooks from there (for example
`neuralmind decisions scan services/api`). The managed block is one per hook
file, so a second project in the same repository replaces the first's.
- **`pre-commit`** *(v3.2.0+)* runs `neuralmind drift . --staged` over the
  staged diff — the commit-time drift guard described under
  [`drift`](#drift-v320) below.

```bash
neuralmind init-hook [project_path] [--no-drift] [--strict]
```

#### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `project_path` | No | Project root (default: current directory) |
| `--no-drift` | No | Skip installing the pre-commit drift guard; post-commit hook only |
| `--strict` | No | Make the installed drift guard block commits instead of warning |

#### Examples

```bash
# Install both hooks (drift guard warns, never blocks)
neuralmind init-hook .

# Install both hooks, with drift blocking the commit
neuralmind init-hook . --strict

# Install only the post-commit hook (decision scan + rebuild), no drift guard
neuralmind init-hook . --no-drift
```

---

### decisions *(v4.1.0+)*

Decision memory: architecture decisions stored with rationale, evidence,
affected files and the commit they came from, in `.neuralmind/memory.db`. It
backs the `neuralmind_query_decisions` and `neuralmind_memory_*` MCP tools, and
[Memory Layer](Memory-Layer.md#cli-reference) documents every subcommand.

```bash
neuralmind decisions record --title T --rationale R [--files F ...] [--commit SHA] [project_path]
neuralmind decisions query "TEXT" [--mode hybrid|semantic|keyword] [--limit 5] [--status ACTIVE|STALE|INVALIDATED|ALL] [--json] [project_path]
neuralmind decisions audit [--stale | --orphaned] [--format md|json] [project_path]
neuralmind decisions amend ID [--rationale R] [--evidence E ...] [project_path]
neuralmind decisions invalidate ID [--reason R] [project_path]
neuralmind decisions restore ID [--commit SHA] [project_path]
neuralmind decisions scan [--quiet] [--json] [project_path]     # v4.6.0+
neuralmind decisions export [--format md|json] [-o FILE] [project_path]
neuralmind decisions eval [--tasks 10] [--format json|md] [--output FILE] [project_path]
neuralmind decisions eval --queries FILE [--mode all|keyword|semantic|hybrid] [--limit 5] [--format json|md] [--output FILE]
```

*(v4.8.2+)* `record --confidence` must be between 0 and 1 (`7` and `nan` used
to be stored as 1.0). `restore` and `invalidate` exit 1 on an unknown id or a
database error, where they printed a traceback or success. A `project_path`
that doesn't exist exits 2 instead of creating an empty decision store.

*(v4.9.1+)* `project_path` can also come after the options, as in
`decisions restore ID --commit SHA path`. On Python 3.10 and 3.11, on 3.12
before 3.12.7, and on 3.13.0, that failed with `unrecognized arguments` in
`amend`, `invalidate`, `query` and `restore`, and in `memory review-approve` /
`review-reject`.

*(v4.9.2+)* `--` ends the options as usual, so a path that starts with `-`
goes after it: `decisions restore ID --commit SHA -- -proj`. (v4.9.1 could
ignore `--` in these six subcommands on Python 3.10, 3.11, 3.12 before 3.12.8
and 3.13.0.) A list option (`--files`, `--rejected`, `--evidence`, `--tags`) takes
every value up to the next option, so put `--` between it and a path that
follows: `decisions amend ID --evidence proof.md -- path`. Without it the
path is read as one more value, and the command runs on the current
directory.

`query` takes keywords or a question, matched against decision titles and
rationales. `--mode` *(v4.8.0+)* picks the ranking:

- `hybrid` (default): shared words and meaning, fused by reciprocal rank fusion.
- `semantic`: meaning only: cosine similarity with each decision's embedded
  title and rationale, using the local `all-MiniLM-L6-v2` model the code index
  uses. A decision needs a similarity of at least 0.30.
- `keyword`: shared words only. Any word can match (common words such as "how"
  and "the" are ignored), and decisions matching more of the words rank first
  (v4.5.1+; before, every word had to match).

Without `--mode`, `NEURALMIND_DECISION_SEARCH` decides, then `hybrid`. Every
output names the mode that ran: the header, the empty result, and with `--json`
a `[neuralmind] search mode: …` line on stderr (stdout stays the JSON array).
Search never downloads the model; it uses the
copy `neuralmind build` fetched. Without it, `hybrid` prints keyword results and
a notice on stderr, and `--mode semantic` exits 1. `--status` is
case-insensitive. Measured recall per mode:
[Memory Layer → Eval harness](Memory-Layer.md#eval-harness).

`--commit` defaults to `HEAD`. `restore` re-anchors a STALE or INVALIDATED
decision to a commit (default `HEAD`) and makes it ACTIVE again. Before an
agent edits a file, the `PreToolUse` stale-decision guard
([`install-hooks`](#install-hooks)) surfaces decisions governing it that are
STALE or INVALIDATED.

#### decisions scan *(v4.6.0+)*

Marks decisions STALE when the `HEAD` commit changed their files. The
post-commit hook from [`init-hook`](#init-hook) runs it after every commit.

- The commit is diffed against its first parent (a merge commit counts
  everything it brought in; a rename counts both paths), relative to the
  project directory.
- **Any** change to a file a decision names counts — no diff analysis.
- Two exemptions keep a fresh decision from going stale on the commit that
  carries it: a decision anchored to `HEAD` itself, and a decision whose
  fingerprints match what the commit stores. Recording, amending or
  restoring a decision fingerprints each affected file with its git blob id
  (`git hash-object`, as `git add` would store it); when every changed file
  the decision names matches, the commit carries exactly the code the
  decision describes. Decisions without fingerprints (recorded before v4.6.0,
  or naming a file that didn't exist yet) get no exemption.
- Dependents (`dependency_constraints`) cascade. The reason is appended to
  each decision's evidence (`Marked STALE: commit 3f9c2ab changed … after this
  decision was recorded`).
- A project with no decision store is left alone (none is created). Always
  exits 0, so it can never fail the commit it follows. Off-switch
  `NEURALMIND_DECISION_SCAN=0`.
- Pulls and rebases don't run post-commit hooks: a decision whose files changed
  only in pulled commits stays ACTIVE until one of your commits touches them.
  Files are matched by exact path (project-relative or absolute).

| Option | Description |
|--------|-------------|
| `--quiet`, `-q` | Print only when a decision went stale (what the git hook uses) |
| `--json`, `-j` | `{"commit": SHA, "stale": [{"id", "title", "reason"}]}` |

```
$ neuralmind decisions scan .
[neuralmind] 1 decision(s) marked STALE by commit 3f9c2ab:
  - Sessions live in Postgres (5b1e0c7a-…) — commit 3f9c2ab changed auth/session.py since this decision was recorded
  Review: neuralmind decisions audit --stale   Still valid? neuralmind decisions restore <id>
```

#### decisions eval

Measures decision search. Both modes seed a scratch store in a temporary
directory and never read or change the project's decisions.

| Option | Description |
|--------|-------------|
| `--tasks N` | Maintenance replay: how many tasks to replay (default 10) |
| `--queries FILE` | Score search against a query set instead of the maintenance replay. `FILE` is JSON: extra decisions plus questions with their gold decision ids, as in `tests/memory/fixtures/decision_queries.json` (source checkout). Reports recall@k and MRR as mean and range per query kind, and lists every miss, false positive and answer not ranked first |
| `--limit N` | Results per query with `--queries` (default 5) |
| `--mode all\|keyword\|semantic\|hybrid` | *(v4.8.0+)* Search mode(s) to score with `--queries`, side by side (default `all`). A mode that can't run (no embedding model on disk) is reported as not run, never scored as another |
| `--format json\|md` | Report format (default `json`) |
| `--output FILE`, `-o` | Write the report to a file instead of stdout |

The measured numbers for the committed query set are in
[Memory Layer → Eval harness](Memory-Layer.md#eval-harness).

Walkthrough: [Keep decision memory honest across commits](../use-cases/decision-memory-across-commits.md).

---

### drift *(v3.2.0+)*

Flag changed symbols that skip a pattern their peers share — the commit-time
half of the cohesion outlier check (`NEURALMIND_SYNAPSE_OUTLIERS`, see
[Environment Variables](#environment-variables)), which runs the same
consensus math at query time instead of diff time. Reads a git diff, maps the changed lines onto graph symbols, groups each
changed symbol with its siblings in the same file or class, and asks whether
the symbol you just touched omits an association a strong majority of that
group makes (e.g. nine of ten `*_endpoint` handlers call `verify_session()`
and the tenth doesn't).

Only symbols **in the diff** are ever reported — pre-existing outliers
elsewhere in the graph are silently ignored, so the check never blames a
commit for drift it didn't introduce. Warn-only and exit-0 by default so it
is safe to wire into `pre-commit`; `--strict` makes it exit non-zero.

```bash
neuralmind drift [project_path] [--staged] [--diff BASE] [--strict]
                  [--cohesion N] [--min-peers N] [--max-findings N]
                  [--no-refresh] [--json]
```

#### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `project_path` | No | Project root (default: current directory) |
| `--staged` | No | Check staged changes against `HEAD` — what `pre-commit` sees |
| `--diff BASE` | No | Diff the working tree against `BASE` instead of `HEAD` |
| `--strict` | No | Exit non-zero when drift is found (default: warn only) |
| `--cohesion N` | No | Fraction of a peer group that must share an association before a dissenter is flagged (default: `0.6`) |
| `--min-peers N` | No | Minimum peers required for a peer group to be judged (default: `3`) |
| `--max-findings N` | No | Cap on reported findings (default: `10`) |
| `--no-refresh` | No | Skip re-parsing changed files; judge against the graph exactly as last built |
| `--json` | No | Output JSON |

#### Examples

```bash
# What a pre-commit hook runs
neuralmind drift . --staged

# Check everything since a branch diverged from main
neuralmind drift . --diff main

# Be stricter about what counts as consensus, and block on it
neuralmind drift . --staged --cohesion 0.75 --strict
```

```
## NeuralMind drift check (warning) — 1 finding(s)

- api/routes.py:67 — `delete_me_endpoint()` skips `verify_session()`, which 3 of its 9 peers (33%) use. Confirm this is deliberate.

Warning only — the commit proceeds. Use --strict to block on drift.
```

Requires a built graph (`neuralmind build .`) — without one, `drift` reports
"No code graph found" and exits 0 rather than failing the commit. When
tree-sitter is installed (the `graphgen` optional extra), the graph is
transparently refreshed for just the changed files before judging, so a
brand-new function in the diff is visible even though the persisted index
predates it; pass `--no-refresh` to skip that and judge against the index
exactly as it was last built. Stdlib-only otherwise, same as
`neuralmind/cohesion.py` — no ChromaDB or embedder work.

---

### compliance *(v3.1.4+)*

Scan a project for **compliance annotations** written in comments or prose,
and reinforce a synapse between the annotated code node and the control it
names — so `neuralmind query "what implements CC6.1"` can find it later.

```bash
neuralmind compliance [project_path] [--watch] [--json]
```

| Flag | Default | Effect |
|------|---------|--------|
| `project_path` | `.` | Project root to scan |
| `--watch` | off | Stay resident; re-detect as files change and reinforce synapses live |
| `--json`, `-j` | off | Machine-readable output |

```
$ neuralmind compliance .

Found 27 compliance annotations across neuralmind:

  [      SOC2] CC6.1
             Logical access controls.
             docs/compliance/ACCESS_CONTROL.md

  [      NIST] AC-1
             Access control policy
             neuralmind/compliance_matcher.py
```

#### Annotation syntax — each framework needs its own marker

This is the part that bites people. **A control id alone never matches.**
Every framework requires a marker, on the *same line* as the id:

| Framework | Marker required | Example |
|-----------|-----------------|---------|
| **CMMC** | optional — the id shape is unambiguous | `// AC.L2-3.1.1: Authorized access control` |
| **NIST SP 800-53** | `NIST` or `NIST SP 800-53` | `# NIST AC-1: Access control policy` |
| **SOX ITGC** | optional — the `ITGC-` prefix is unambiguous | `# ITGC-CM-001: Change approved via CAB` |
| **HIPAA** | optional — the `164.` id shape is unambiguous | `/* 164.312(a)(1): Access control required */` |
| **SOC 2** | `SOC 2` **or** `Compliance:` | `**SOC 2 Control:** CC6.1 — Logical access` |
| **ISO 27001** | `ISO 27001` **or** `Compliance:` | `# ISO 27001 A.9.2.1: User registration` |

Two consequences worth stating plainly:

- **`Compliance:` is a SOC 2 / ISO 27001 marker, not a universal one.**
  `# Compliance: AC-1: Access control policy` matches **nothing** — NIST
  needs its own prefix.
- **A bare `CC6.1` in a prose table does not match.** The marker may sit up
  to 32 characters before the id on the same line, which is what makes
  `**SOC 2 Control:** CC6.1` work, but a control id on its own is
  indistinguishable from a version string and is ignored. This tightening
  landed in v3.3.0 after the looser pattern matched `v0.13`, `M13.5` (an
  SVG path command) and `python3.10` as Trust Services Criteria.

#### What gets scanned

Code **and** prose: `.py .js .jsx .ts .tsx .go .java .rb .php .cs .c .cpp
.h .rs .md .mdx .rst .txt`. Skipped: `.git`, `node_modules`, `.venv`,
`venv`, `__pycache__`, `.next`, `out`, `htmlcov`, `.neuralmind`.

*(Before v3.3.1 the CLI read only source files, so annotations kept in
markdown — the usual place for a policy document — were invisible to this
command even though the matcher supported them.)*

#### Showing an annotation without becoming evidence

Documentation, tests and marketing copy have to *show* what an annotation
looks like. Before v3.4.1 every one of those examples was counted as a real
annotation — on this repository the scan reported 37 controls, 25 of which
were syntax samples in the very pages that document the syntax, and all 37
flowed into `neuralmind export --controls`, which users submit as audit
evidence.

Two opt-out markers fix that. Neither is a comment syntax of its own — put
the text anywhere a given file lets you put text (an HTML comment in
markdown, a `#` or `//` comment in code, prose in a docstring):

| Marker | Scope | Use it when |
|--------|-------|-------------|
| `neuralmind:example-file` | the whole file, wherever it appears | the file is *about* the syntax — a reference page, a test fixture |
| `neuralmind:example` | the one line it sits on | a single sample inside a file whose other annotations are real |

```markdown
<!-- neuralmind:example-file — annotations here are syntax examples, not evidence. -->
# CLI Reference
```

```python
help="e.g. # NIST AC-1: Access control policy",  # neuralmind:example
```

The file-level marker is checked before any pattern runs, so an opted-out
file costs nothing to scan. The line-level marker is tested against the
whole line the control id sits on, not the start of the match.

Both markers are inert everywhere else — nothing else in NeuralMind reads
them, and a file carrying one still indexes, embeds and queries normally.

---

### ci-check *(v3.1.4+)*

Run the same detection against a **git diff** instead of the whole tree, so
a pipeline can report which compliance-annotated code a change touches.

```bash
neuralmind ci-check [project_path] [--framework NAME] [--diff REF] [--fail-on-warning] [--json]
```

| Flag | Default | Effect |
|------|---------|--------|
| `--framework` | `all` | `cmmc`, `nist`, `sox`, `hipaa`, `iso`, `soc2`, or `all` |
| `--diff` | `HEAD` | Git ref to diff against; `HEAD` means uncommitted changes |
| `--fail-on-warning` | off | Exit non-zero when warnings exist |
| `--json`, `-j` | off | Structured output suitable for a PR comment |

```
$ neuralmind ci-check . --framework soc2 --diff HEAD~1

NeuralMind CI Compliance Check
Framework: SOC2
Base ref: HEAD~1
Changed files: 3

No compliance annotations affected by this diff.
```

`--framework` accepts the friendly spellings (`sox` → `SOX ITGC`, `iso` →
`ISO 27001`, `soc`/`soc 2` → `SOC2`). *(Before v3.3.1 the flag was echoed in
the header but never applied — findings from every framework were reported
regardless of what you passed.)*

---

### export *(v3.1.4+)*

Write NeuralMind state out as an auditor-ready artifact.

```bash
neuralmind export [project_path] [--format csv|pdf] [--controls] [--nodes] [--output FILE]
```

| Flag | Default | Effect |
|------|---------|--------|
| `--format` | `csv` | `csv` or `pdf` |
| `--controls` | off | Compliance-control-to-code mappings (CSV only) |
| `--nodes` | off | All graph nodes with metadata (CSV only) |
| `--output` | `neuralmind_export.csv` / `.pdf` | Output path |
| `--report` | `ssp` | Report type for PDF export |

`--controls` is the flag people submit as evidence, so it inherits the
annotation rules above exactly: what `neuralmind compliance` finds is what
lands in the CSV, including its `label` column.

---

### watch *(v0.4.0+)*

Run the file activity → synapse co-activation daemon in the foreground.
Edits to project files are debounced into batches and fed into the
synapse store, so the v0.4.0 brain-like layer keeps learning even when
no query runs. Periodic decay ticks age unused weights without manual
intervention. Stops cleanly on Ctrl-C.

```bash
neuralmind watch [project_path] [--debounce SECONDS] [--decay-interval SECONDS] [--quiet] [--reindex]
```

#### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `project_path` | No | Project root (default: current directory) |

#### Flags

| Flag | Default | Description |
|------|---------|-------------|
| `--debounce` | `0.75` | Seconds to coalesce rapid edits into one co-activation batch |
| `--decay-interval` | `600` | Seconds between decay ticks; `0` disables periodic decay |
| `--quiet` | off | Suppress per-batch logging (still prints final summary on stop) |
| `--reindex` | off | *(v0.18.0+)* Incrementally re-index edited files into the built-in graph as they change — re-parses just those files and re-embeds only their nodes (unchanged files are skipped). Built-in backend only; needs the retrieval stack in the watch process. |

#### Examples

```bash
# Always-on learning for the current project
neuralmind watch &

# Background it and only log the final summary
neuralmind watch /path/to/repo --quiet &

# Disable periodic decay (decay only runs from SessionStart hook)
neuralmind watch . --decay-interval 0

# Keep the index live as you edit (incremental re-index, v0.18.0+)
neuralmind watch . --reindex
```

#### Notes

- Backed by `watchdog` when present, with a polling fallback when not. No mandatory new dependency.
- Pairs with `neuralmind install-hooks` — the watcher learns from
  edits, the lifecycle hooks learn from queries and tool calls, and the
  same `<project>/.neuralmind/synapses.db` store is the single source of truth.
- For "always on" across reboots, wrap in systemd, launchd, or tmux. NeuralMind deliberately doesn't self-daemonize.

---

### serve *(v0.5.4; live feed v0.6.0+)*

Start the graph-view UI — a local, dependency-free, Obsidian-style
force-directed graph over the same index and synapse store your AI
agent queries. v0.6.0 made the canvas live: synapse + file events
stream to the browser over SSE, affected nodes pulse, a sidebar log
shows recent events. Stops cleanly on Ctrl-C.

The server binds to 127.0.0.1 by default and prints an auth-token URL on
startup; pass that URL to the browser so untrusted local processes can't
read your graph. The token persists in `~/.neuralmind/server-token.json`
(mode `0600`), so the URL stays valid across restarts; delete that file and
restart the server to rotate it.

```bash
neuralmind serve [project_path] [--host HOST] [--port PORT] [--no-browser] [--editor EDITOR] [--no-auth]
```

#### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `project_path` | No | Project root (default: current directory) |

#### Flags

| Flag | Default | Description |
|------|---------|-------------|
| `--host` | `127.0.0.1` | Address to bind to. The token stays on |
| `--port` | `8787` | TCP port to bind to |
| `--no-browser` | off | Don't auto-open a browser tab on startup |
| `--editor` | `$EDITOR` | Editor command used by the "Open in editor" button — `code`, `code -n`, `cursor`, `vim`, `subl`, `idea`, etc. |
| `--no-auth` | off | Disable the auth token. Only use on a trusted host. |

#### Examples

```bash
# Run against the current project
neuralmind serve .

# Custom editor for the "open in editor" button
neuralmind serve . --editor "code -n"

# Pick a different port and skip the browser
neuralmind serve . --port 9000 --no-browser

# Skip auth for a kiosk / trusted local host
neuralmind serve . --no-auth
```

#### Live activity feed (v0.6.0+)

The canvas updates in real time as the brain works:

- **Synapse events** — every `SynapseStore.reinforce()` call publishes
  a `synapse` event over the in-process event bus; the affected pair
  of nodes pulse on the canvas.
- **File activity events** — every coalesced edit batch from the
  `neuralmind watch` daemon (or from Claude Code's `PostToolUse`
  hooks) publishes a `file_activity` event; affected nodes pulse.
- **Sidebar log** — the most recent ~80 events render as a scrolling
  feed with timestamps. Click an entry to focus the corresponding
  node on the canvas.

#### Cross-process activity bridge (v0.6.0+)

When `serve` and the activity source live in different processes —
a separate `neuralmind watch` daemon, a Claude Code session — each
`event_bus.publish()` call also appends a JSON line to
`<project>/.neuralmind/events.jsonl`. The `serve` process tails that
file in a background thread and re-emits anything it didn't
originate. Net result: one canvas, all processes, no IPC complexity.

Behaviour:

- `NEURALMIND_EVENT_LOG=0` disables the writer (in-process feed
  still works).
- The tailer is best-effort. If the file disappears or rolls, the
  next event re-creates it.
- The bus stays the primary path. The JSONL is a fallback, not a queue.

#### Notes

- Read-only over HTTP. Edits to nodes/synapses still go through the
  regular CLI and MCP tools; the UI only inspects.
- The `/api/open` endpoint launches `$EDITOR` against an allowlist
  pre-computed from the graph's `source_file` set, so a tampered
  client can't trick the server into opening arbitrary paths.
- All assets in `neuralmind/web/` (HTML, JS, CSS) are read-only at
  runtime; the server doesn't generate any of them.
- Graph payload is cached per-session in `_Handler._graph_cache`; any
  endpoint touching graph state respects `_graph_lock`.
- Vanilla-JS frontend, stdlib-only HTTP server, no CDN. Safe to run
  behind a firewall.

---

### daemon *(v0.23.0+)*

Manage the local NeuralMind daemon (experimental — PRD 5). The daemon holds
each project's state **warm** so repeated queries skip cold backend init. CLI
read commands (`query`, `stats`) prefer it automatically when it's running and
fall back to direct mode otherwise.

```bash
neuralmind daemon {start|stop|restart|status} [OPTIONS]
```

#### Actions

| Action | Description |
|--------|-------------|
| `start` | Launch the daemon in the background (writes a discovery file). No-op if already running. |
| `stop` | Ask the running daemon to shut down gracefully; clears stale discovery. |
| `restart` | Stop (if running) then start. |
| `status` | Show pid, uptime, warm projects, and active jobs (exit 3 if not running). |

#### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--host` | `127.0.0.1` | Host to bind (loopback) |
| `--port` | `8787` | Port to bind |
| `--foreground` | False | Run in the foreground instead of detaching (`start`/`restart`) |
| `--json`, `-j` | False | Machine-readable `status` output |

#### Behavior

- **One per-user daemon, many projects.** A project registry initializes each
  `NeuralMind` once and reuses it; a per-project lock serializes
  build/query/watch so they can't corrupt the index or synapse store; slow
  builds run as background jobs.
- **Auto-preference + fallback.** `neuralmind query` / `stats` use the daemon
  when reachable (output marked `via: daemon` in `--json`), else run directly.
  Force direct mode with **`NEURALMIND_NO_DAEMON=1`**.
- **Crash-safe discovery.** A stale discovery file (dead pid / unreachable) is
  cleaned up automatically, so a crashed daemon never wedges the CLI.
- **Shared API.** The daemon speaks one transport-agnostic contract
  (`health` / `status` / `query` / `search` / `stats` / `build` / `validate` /
  `jobs`); the `neuralmind-daemon` console script runs it directly. Token-guarded
  even on loopback.

```bash
# Warm daemon, then fast repeat queries
neuralmind daemon start
neuralmind query . "how does auth work?"   # served warm (via: daemon)
neuralmind daemon status --json
neuralmind daemon stop
```

---

### savings *(v0.39.0+)*

Show cumulative token savings from the local query event log. Verifies the 12-50× claim against your own real usage rather than trusting the demo.

```bash
neuralmind savings [project_path] [OPTIONS]
```

#### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--global` | False | Show savings across ALL projects (reads the global event log at `~/.neuralmind/memory/`) |
| `--json`, `-j` | False | Emit structured JSON output |
| `--cost` | False | *(v0.45.0+)* Also show estimated **dollar** savings, priced on input tokens ($/MTok) |
| `--model` | `claude-opus-4-8` | *(v0.45.0+)* Pricing model for `--cost` — choices come from the built-in input-price table (Claude / GPT / Gemini) |
| `--queries-per-day` | 100 | *(v0.45.0+)* Assumed daily query volume behind the `--cost` daily/monthly projection |
| `--naive-50k` | False | *(v4.5.0+)* Price "without NeuralMind" at the fixed 50,000 tokens/query instead of the measured token count of the code the index covers |

Since v4.5.0 the per-query "without NeuralMind" cost is the **measured** token
count of the code the index covers (cached at build), labelled in the output;
`--global` spans many projects and keeps the fixed estimate. Read-only queries
(evals, benchmarks) aren't usage and aren't counted.

Since v4.8.1 only `query` and `wakeup` events count. Earlier versions also
counted builds, searches, MCP calls and ingestion as saved queries, and an MCP
query twice, so totals drop after upgrading.

#### Examples

```bash
# Show project-level savings
neuralmind savings .
# → NeuralMind token savings — my-project
# →   Queries logged    : 47
# →   Avg reduction     : 38.2x
# →   Tokens actually used :     83,140
# →   Est. cost without NM : 2,350,000
# →   Tokens saved         : 2,266,860

# Global savings across all projects
neuralmind savings --global

# JSON for dashboards or scripting
neuralmind savings . --json

# Dollar savings at claude-opus-4-8 input pricing (v0.45.0+)
neuralmind savings . --cost
# →   Dollar savings — claude-opus-4-8 @ $5.0/MTok input
# →     Cost without NM : $     11.75
# →     Cost with NM    : $      0.42
# →     Saved           : $     11.33
# →     Projected       : $24.12/day · $723.47/month  (at 100 queries/day)

# Price against a different model and daily volume
neuralmind savings --global --cost --model gemini-2.5-pro --queries-per-day 250

# JSON gains a "dollar_savings" block when --cost is set
neuralmind savings . --cost --json
```

The dollar figures are estimates anchored to the same 50,000-tokens-per-query
baseline as the token report, priced on **input** tokens only — retrieval
decides which input tokens ship, so output pricing never enters the math.
Prices are a 2026-07 snapshot (`MODEL_PRICING_PER_MTOK` in `neuralmind/memory.py`).

Only the *with-NeuralMind* cost is measured from logged tokens; *without-NM*
(and therefore *saved* / *projected*) is estimated from the fixed baseline, so
those figures are marked `(est)` in the human output. The JSON `dollar_savings`
block makes this machine-readable too: `estimated: true`, a `basis` string, and
`baseline_tokens_per_query`.

Memory logging must be enabled: answer yes when an interactive `neuralmind query` first asks, or write `{"memory_logging_enabled": true}` to `~/.neuralmind/memory_consent.json`. `NEURALMIND_MEMORY` is on by default and only `0` changes anything, so setting it to `1` doesn't enable logging. *(v4.8.2)* With memory off, `feedback` says so and names the fix instead of "run a query first".

---

### why *(v0.43.0+)*

Recall the recorded rationale behind code — the decision provenance a human authored, not something inferred.

Harvests `Decision:` git trailers from history and surfaces the ones whose subjects the query mentions. The trailer **is** the store: no database, nothing to build, and it works retroactively on commits already in history.

```bash
neuralmind why "<symbol or question>" [--project-path PATH]
```

Capture a decision by adding a trailer to a commit message (backticked symbols in the rationale become subjects automatically; an explicit `Subjects:` line is also honored):

```
cli: resolve org id per handler

Decision: resolveOrgId is per-handler, not middleware — avoids Prisma on
          /health, /metrics, /token; keeps tests simple.
Subjects: `resolveOrgId`, `authMiddleware`
```

#### Arguments

| Argument | Description |
|----------|-------------|
| `query` | A symbol or natural-language question, e.g. `"why is resolveOrgId per-handler"` |

#### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--project-path` | `.` | Project root to read git history from |

#### Sample Output

```
## NeuralMind decision provenance

- `resolveOrgId`, `authMiddleware`: resolveOrgId is per-handler, not middleware —
  avoids Prisma on /health, /metrics, /token; keeps tests simple. (see commit ba25fed)
### doctor *(v0.12.0+)*

Run diagnostic checks on the index.

### eval *(v0.14.0+)*

Evaluate retrieval quality — see [eval](#eval-v0140-project-eval-v450) above.

### feedback good/bad *(v3.1.4+)*

Provide explicit feedback on the last query's results.

#### Arguments

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `--json` | No | `false` | Output as JSON |

#### Output

Confirmation of edges boosted or penalized.

#### Examples

```bash
# Boost edges from last query (good feedback)
neuralmind feedback good .

# Penalize edges from last query (bad feedback)
neuralmind feedback bad .
```

#### Prerequisites

Requires a synapse store with edges from a previous query. Feedback adjusts the
last query recorded in `.neuralmind/recent_queries.jsonl`, and queries are
recorded only while query memory is on. With memory off, `feedback` exits 1
and says what turns memory on. *(v4.9.1+)* That holds even when older queries
are still recorded: queries asked since memory went off weren't, so the last
recorded one may not be the query you mean. `feedback` names it and when it
was asked, and changes nothing.

### health *(v3.1.4+)*

Check NeuralMind health status.

#### Arguments

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `--json` | No | `false` | Output as JSON |

#### Output

Health status: healthy, stale, unknown, or no index. Since v4.4.0 "stale" means
the code graph is out of step with the files on disk (the same freshness check
[`doctor`](#doctor-v0120) runs), not "older than 24 hours": a day-old index of
unchanged code is healthy, and an hour-old one that misses new files is not.
"Unknown" means there is an index but no readable graph to check it against;
it exits `1`, never `0`. `--json` includes the full `freshness` report.

#### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Healthy — the graph matches the files on disk |
| 1 | Stale — files missing from the graph, deleted files still indexed, files changed since the graph, a graph built on another OS, or a graph changed after the last build — or unknown: no readable graph to check the index against |
| 2 | No index |

#### Examples

```bash
# Check health
neuralmind health .

# Use in CI/CD
neuralmind health . || echo "Index needs rebuild"
```

### status *(v3.1.4+; index reporting v3.4.0+)*

Two independent halves of a project's state in one glance: what is **indexed**
(code nodes, ingested content, when it was last built) and what has been
**learned** (synapse edges, and an "is it learning?" diagnostic). Both are
reported even when only one exists — a freshly ingested corpus has no synapses
yet, and a long-lived project can carry months of learned edges over an index
nobody has rebuilt.

```bash
neuralmind status .          # human-readable dashboard
neuralmind status . --json   # machine-readable
```

```
═══ NeuralMind Status — book ═══
  Code nodes:   0 (0 edges) — content-only project
  Last build:   0.4h ago
  Disk:         2.1 MB
  Content:      34 file(s), 306 chunks, 306 nodes
  Last ingest:  2026-08-23T13:19:14+00:00

  Status:       🟢 active
  Namespace:    personal
  Edges:        318 (12 LTP-protected)
  ...
```

"Code nodes" is named that way so it doesn't read as a total: a content-only
project legitimately has zero of them and thousands of chunks.

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `project_path` | No | `.` | Project to inspect |
| `--json`, `-j` | No | `false` | Output as JSON |

The JSON adds an `index` object (`exists`, `path`, `nodes`, `edges`,
`built_at`, `age_hours`, `disk_mb`) and a `content` object (`files`, `chunks`,
`nodes`, `last_indexed_at`, `tracked`) alongside the existing synapse keys.

Reads the IR and the content manifest straight off disk and never constructs a
vector backend, so it answers in milliseconds. An IR above 64 MB is summarized
rather than parsed — `nodes` comes back `null` and the build timestamp still
reports.

### learn — document ingestion *(v1.11.0+)*

```bash
neuralmind gaps [project_path]
```

Phase 1 heuristics cover **Express + Jest** (JS/TS). Route paths are normalized across `:id` / `{id}` / `${...}` / `*` styles so a registration and a test reference match; a test "hits the real DB" when its file imports a real-DB fixture (e.g. `@/db`, `testDb`) and the case isn't skip-guarded (`SKIP_PG`, `.skip`).

#### Arguments

| Argument | Description |
|----------|-------------|
| `project_path` | Project root to scan (default: current directory) |

#### Sample Output

```
## neuralmind gaps — live-Postgres coverage

Routes tested in-memory only (no live-DB coverage):
  POST /api/sessions            — 3 tests — all SKIP_PG  ❌
  GET  /.well-known/jwks.json   — 1 test — all SKIP_PG   ❌
Endpoints with no tests:
  POST /api/auth/jwk/rotate     ⚠️
Live-covered:
  GET  /health                  ✅
```

### gaps --structural *(v1.9.0+)*

Identify structural gaps in your codebase — missing bridges between communities that should be connected but aren't. Built on Brandes' betweenness centrality algorithm over the structural graph.

```bash
neuralmind gaps --structural [OPTIONS]
```

#### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--top-k` | `20` | Maximum number of gaps to report |
| `--threshold` | `0.0` | Minimum gap score to include (0.0 = include all) |
| `--community` | None | Filter to specific community ID |
| `--json`, `-j` | False | Emit structured JSON output |

#### Examples

```bash
# Find top 20 structural gaps
neuralmind gaps --structural

# Find gaps with score > 0.5, JSON output
neuralmind gaps --structural --threshold 0.5 --json

# Gaps in a specific community
neuralmind gaps --structural --community 3
```

#### Sample Output

```
## NeuralMind — Structural Gaps (G5)

Rank  Score    Node                                   Communities
────  ──────   ─────────────────────────────────────  ────────────
1     0.87     src/auth/token.py                      2, 5
2     0.72     src/models/user.py                     1, 3
3     0.65     src/utils/validation.py                2, 4
```

The equivalent MCP tool is `neuralmind_structural_gaps`.

### review *(v0.39.0+)*

Warn about likely co-breakage before a commit or when reviewing a diff.

Reads the current `git diff` (or a specified base ref), finds changed files, and runs spreading activation through the learned synapse graph to surface files that are **strongly associated but NOT in your diff** — files that have historically been edited together with the ones you're changing.

```bash
neuralmind review [project_path] [OPTIONS]
```

#### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--base` | `HEAD` | Git ref to diff against. Use `HEAD~1` to review the last commit or a branch name to review a feature branch. |
| `--top-k` | `10` | Maximum number of at-risk files to report |
| `--json`, `-j` | False | Emit structured JSON output |

#### Examples

```bash
# Review uncommitted changes (diff against HEAD)
neuralmind review .

# Review the last commit
neuralmind review . --base HEAD~1

# Review changes on a feature branch vs main
neuralmind review . --base main

# JSON output for CI integration
neuralmind review . --json
```

#### Sample Output

```
NeuralMind review — my-project  (diff against: HEAD)

Changed files (3):
  • auth/middleware.py
  • auth/handlers.py
  • tests/test_auth.py

Co-break candidates — files NOT in diff but strongly associated (4):
  0.782 ████████  auth/tokens.py
  0.654 ██████    auth/models.py
  0.431 ████      config/settings.py
  0.198 ██        docs/auth.md

These files have historically been edited together with the ones above.
Consider whether your change also needs to touch them.
```

Requires the synapse graph to have accumulated edges. Cold graphs (first few sessions) return empty results. Also available as the `neuralmind_review` MCP tool.

*Wiki reference: [Tier2-Operator-Guide](Tier2-Operator-Guide.md) · [Upgrade-Guide](Upgrade-Guide.md)*

---

### onboarding *(v1.7.0+)*

Walk a new operator through license activation, governance defaults, admin email setup, and verification. The entry point for strangers who just ran `neuralmind wakeup .` and want to configure their project.

```bash
neuralmind onboarding              # interactive mode — walks all 5 steps
neuralmind onboarding --quick      # skip all prompts, defaults only
```

#### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--quick` | `false` | Skip all prompts, apply defaults (1-seat free, scope=both, threshold=0.1) |

#### What it walks through

1. **License activation** — checks for `license.json`. If missing, auto-issues free tier (or activates Team license if provided).
2. **Governance defaults** — sets `publishing_scope` (`personal`/`shared`/`both`) and `weight_threshold` (0.0–1.0).
3. **Admin email setup** — adds admin emails for governance notifications.
4. **Team seat audit** — lists current seats (`neuralmind team seats list`).
5. **Verification** — prints license status + governance state.

#### Sample Output

```bash
$ neuralmind onboarding --quick

✓ Free tier activated (1 seat, never expires)
✓ Governance: scope=both, threshold=0.1
✓ Admin: (none — free tier)
✓ Seats: 1/1 (free)

Run `neuralmind team license status` to view.
```

#### Honest scope

- Free tier: `onboarding --quick` configures governance but doesn't issue paid license
- Team tier: requires `neuralmind team license activate <file>` before seat management works
- Onboarding doesn't install hooks or build the index — see `neuralmind install-hooks` and `neuralmind build`

---

### team governance

Team-memory governance (source-available tier2 modules; runs free at 1 seat).
Settings live in `~/.config/neuralmind/tier2.yaml`, per user; until an
operator saves them (here or with [`onboarding`](#onboarding-v170)), nothing in
the team-memory flow is gated or audited. *Enforced since v4.6.0; earlier
versions recorded scope and threshold without enforcing them.*

```bash
neuralmind team governance status
neuralmind team governance set-scope personal|shared|both --admin EMAIL
neuralmind team governance set-weight-threshold 0.0-1.0 --admin EMAIL
neuralmind team governance set-governance-enabled true|false --admin EMAIL
neuralmind team governance list-shared [--project PATH] [--limit N] [--json]
neuralmind team governance remove-edge SOURCE TARGET [--project PATH] --admin EMAIL
```

| Setting | Effect on `neuralmind memory publish` |
|---|---|
| scope `personal` | Refuses to publish (exit 1); memory stays on each machine |
| scope `shared` | Publishes only the team baseline (the `shared` namespace) |
| scope `both` *(default)* | Publishes personal + shared memory |
| `weight_threshold` *(default 0.1)* | Synapse edges below it are left out of the bundle (transitions aren't weight-filtered) |
| `set-governance-enabled false` | Turns the scope and threshold gates off; events are still audited |

The bundle's `provenance.governance` records the policy it was published
under. A governance config that exists but can't be read (unreadable, malformed
YAML, an invalid value) makes publish refuse.

**`remove-edge SOURCE TARGET`** (admin-only) deletes the association, and the
transitions between the two nodes, from the project's `shared` memory and
review queue. It drops the pair from `.neuralmind-team-memory.json` and lists
it under `retracted` (creating the file if needed). Commit the file: each
teammate's next session deletes the pair from their own `shared` memory, and
no later publish re-adds it. The file is written first, atomically; if the
local store update then fails, the next import finishes it. A non-admin gets
`Permission denied` and exit 1.
*Changed in v4.6.0:* the command takes the two nodes instead of one `edge_id`
(the old form only wrote an audit entry).

**`list-shared`** prints the project's shared-memory associations, strongest
first (`--json`: `source`, `target`, `weight`, `activation_count`).

**Audit** (`neuralmind team audit list|verify|export`): configuration changes,
seat and license actions, and, since v4.6.0, every team-memory `publish`
(including refused ones), `import`, `review_approve` / `review_reject` and
`remove`. The actor is `--admin` for admin commands, otherwise
`NEURALMIND_ACTOR_EMAIL`, the repository's `git config user.email`, or the OS
user.

Walkthrough: [Govern what your team's agents share](../use-cases/govern-team-memory.md).

---

### optimize-docs *(v1.7.2+)*

Run the **DocEvolver** — an evolutionary JSDoc optimizer that finds undocumented methods, generates JSDoc variants using mutation strategies, and evolves them against a retrieval fitness function (Recall@1).

```bash
neuralmind optimize-docs <project_path> [OPTIONS]
```

#### Arguments

| Argument | Required | Description |
|----------|----------|-------------|
| `project_path` | Yes | Path to project root |

#### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--blind-spots` | — | Path to a JSON file of pre-computed blind spots (from `neuralmind probe --json`) |
| `--generations` | `5` | Number of evolution generations (G) |
| `--population` | `8` | Population size per generation |
| `--hysteresis` | `0.05` | Minimum fitness improvement required to promote a variant |
| `--dry-run` | False | Report only — no file modifications |
| `--json`, `-j` | False | Emit structured JSON output |

#### Examples

```bash
# Run full audit + evolution on a project
neuralmind optimize-docs .

# Dry-run (report only, no file changes)
neuralmind optimize-docs . --dry-run

# With pre-computed blind spots from probe
neuralmind probe . --json > spots.json
neuralmind optimize-docs . --blind-spots spots.json

# Custom evolution parameters
neuralmind optimize-docs . --population 10 --generations 8 --hysteresis 0.03

# Machine-readable output
neuralmind optimize-docs . --json
```

#### How it works

1. **Sample** — generates N JSDoc variants per undocumented method via four mutation strategies: `LENGTH` (1/3/5-line), `STRUCTURE` (Args/Returns vs prose-only vs mixed), `KEYWORD_DENSITY` (method-name synonyms vs generic description), `POSITION` (above vs inline for arrow functions).
2. **Evaluate** — patches each variant into the source, runs a natural-language query, and scores Recall@1 = 1/rank of the correct file.
3. **Promote** — the best variant beats the incumbent by the hysteresis margin, then mutates around it for the next generation.
4. **Patch** — after G generations, the winning JSDoc is written back to the source file.

#### Sample Output

```bash
$ neuralmind optimize-docs . --dry-run

DocEvolver — my-project
============================================================
Blind spots found: 12 undocumented methods
  - handle_csv_export()  (utils/csv.py)
  - parse_headers()      (utils/csv.py)
  - validate_schema()    (models/base.py)
  ...

Run without --dry-run to evolve JSDoc for these methods.
```

#### Files

- [`neuralmind/doc_evolver.py`](../../neuralmind/doc_evolver.py) — main module (1181 lines)
- [`tests/test_doc_evolver.py`](../../tests/test_doc_evolver.py) — 44 tests

---

### license — issuer-side

Mints and manages **Team licences**. These are operator commands, not
customer commands — every subcommand that changes a licence requires the
Ed25519 issuer private key in `NEURALMIND_ISSUER_PRIVATE_KEY_HEX` and
exits 1 without it. Customers use `neuralmind team license …` instead
(see [Tier2-Operator-Guide](Tier2-Operator-Guide.md)).

The end-to-end selling process these fit into — quoting, invoicing,
delivery, renewals — is the [Billing Runbook](Billing-Runbook.md).

```bash
neuralmind license issue --customer "Acme Corp" --seats 12 --term 12 [--partner ID] [--output PATH]
neuralmind license renew --customer "Acme Corp" --term 12
neuralmind license revoke --customer "Acme Corp" --reason "non-payment"
neuralmind license status --customer "Acme Corp"
neuralmind license list [--partner ID]
neuralmind license expiring [--within DAYS] [--json] [--quiet]
```

**`expiring`** is the exception to the key requirement above: it is
read-only, needs no issuer key, and exists so a scheduler can watch for
lapsing licences without holding anything sensitive. Nothing else in the
system tracks expiry dates. It signals through its exit code so a caller
never has to parse output to decide whether to alert:

| Exit | Meaning |
|-----:|---------|
| 0 | Nothing due inside the window |
| 6 | Renewals due inside the window |
| 7 | Already expired, or an expiry that cannot be parsed (takes precedence over 6) |

`--within` sets the look-ahead in days (default 60). `--quiet` suppresses
output on exit 0, so a cron entry stays silent unless there is news.
`--json` emits the full report — `expired`, `expiring` and `unknown`
buckets, each sorted most-urgent first, with `days_remaining` per customer.
Revoked licences are excluded: they cannot be renewed. See the
[Billing Runbook](Billing-Runbook.md) for the scheduling recipe.

| Flag | Applies to | Meaning |
|------|-----------|---------|
| `--customer` | issue, renew, revoke, status | Customer name; also the licence filename, sanitized |
| `--seats` | issue | Seat count (must be positive) |
| `--term` | issue, renew | Term in months: 1, 3, 6, 12, 24, or 36 |
| `--partner` | issue, list | Reseller partner ID |
| `--within` | expiring | Days ahead to look (default: 60) |
| `--json` / `--quiet` | expiring | Machine-readable output / silence when nothing is due |
| `--output` | issue | Filename for the signed licence, **within `~/.neuralmind`** — a path outside it is refused by the same guard that contains hostile customer names. Defaults to `<sanitized-customer-name>.json` |
| `--reason` | revoke | Recorded in the audit log |

**Term arithmetic.** Terms advance by calendar months, so a 12-month
licence issued on 28 August expires on 28 August the following year. A
day-of-month with no counterpart in the target month clamps to the last
valid day (31 Jan + 1 month is 28 or 29 Feb). `renew` extends from the
existing expiry rather than from today, so paying late does not grant free
months and paying early does not forfeit any. A revoked licence cannot be
renewed — issue a new one.

**State written.** All under `~/.neuralmind/`:

| File | Contents |
|------|----------|
| `<customer>.json` | The signed licence (`--output` renames it, still inside this directory) |
| `customers.yaml` | Customer record: seats, expiry, status, `total_paid` |
| `partners.yaml` | Reseller registry and accrued commission |
| `audit_log.jsonl` | Append-only record of every issue, renew and revoke |

---

## Exit Codes

| Code | Meaning |
|------|----------|
| 0 | Success |
| 1 | General error |
| 2 | Invalid arguments, including *(v4.8.2+)* a project path that doesn't exist |
| 3 | graph.json not found |
| 4 | Index not built (run `build` first) |
| 5 | Database error |
| 6 | `license expiring`: renewals due inside the window |
| 7 | `license expiring`: a licence has already expired, or its expiry cannot be parsed |

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `NEURALMIND_MEMORY` | `1` | Set to `0` to disable query memory logging |
| `NEURALMIND_LEARNING` | `1` | *(deprecated, v0.25.0)* Formerly disabled the `learned_patterns` cooccurrence reranker, which was removed in v0.25.0. Now inert — recognized but ignored. To disable the synapse layer's prompt-time recall, use `NEURALMIND_SYNAPSE_INJECT=0`. |
| `NEURALMIND_BYPASS` | unset | Set to `1` to switch off every NeuralMind hook action temporarily (session memory, prompt recall, stale-decision guard, the `neuralmind last` cache, the session recap), including *(v4.9.0+)* the Hermes plugin's |
| `NEURALMIND_OUTPUT_REDACT` | `1` | Set to `0` to stop redacting credentials from the PostToolUse Bash recovery cache (`.neuralmind/last_output.json`) and from the full outputs `NEURALMIND_BASH_REPLACE` keeps (`.neuralmind/bash_outputs/`). The cache stores whatever a command printed, so with redaction off a `printenv` or an `Authorization: Bearer` header can land a live key in a plaintext file. Not recommended. |
| `NEURALMIND_REDACT_SECRETS` | unset | Set to `1` to scrub detected credentials from text before it enters the index — equivalent to `neuralmind build . --redact-secrets`. Off by default because redacting the index costs recall on legitimately secret-shaped identifiers. A backstop, not a substitute for removing and rotating the credential. |
| `NEURALMIND_TYPE_CHECK` | unset | *(v3.0.0+)* Set to `1` to confirm inferred return types with `mypy` during the build's type-verification pass. Slower but more precise; without it, inference is AST/tree-sitter only. The pass itself runs whenever the synapse layer is enabled and is fail-open — type metadata is observability, never a gate on the build. |
| `NEURALMIND_SYNAPSE_INJECT` | `1` | *(v0.4.0+)* Set to `0` to disable prompt-time recall in the `UserPromptSubmit` hook (and the Hermes plugin's `pre_llm_call`): the files a prompt matches and the code linked to them *(v4.11.0; before, spreading-activation neighbors)* |
| `NEURALMIND_RECALL_MIN_SIMILARITY` | `0.35` | *(v4.11.0+)* Prompt-time recall injects nothing when the prompt's best semantic match in the code scores below this similarity, so "yes", "continue" or an off-topic question gets no recall block. Measured on this repository's own index: 15 prompts about the code scored 0.371–0.645, 15 off-topic prompts 0.145–0.364 (one above 0.35). Reproduce with `python -m tests.benchmark.recall_gate <project>`, and pass `--prompts` with your own sets to calibrate another project or embedder. `0` never abstains. Each outcome is counted in `neuralmind metrics` |
| `NEURALMIND_PROVENANCE_INJECT` | `1` | *(v0.43.0+)* Set to `0` to disable decision-provenance injection in the `UserPromptSubmit` hook. When enabled (default), `Decision:` git trailers whose subjects appear in the prompt are surfaced as context alongside synapse recall. Reads git history (the trailer is the store — no separate DB); fails open, so a provenance miss never disrupts the prompt. Query the same data directly with `neuralmind why`. |
| `NEURALMIND_SYNAPSE_OUTLIERS` | unset | *(v0.44.0+)* Set to `1` to add the cohesion outlier check to the `UserPromptSubmit` injection. When enabled, it finds an associate most of a surfaced co-activation cluster links to and flags the members that skip it — the "handler #11" that breaks the cluster's shared pattern (`validateSession` skips `resolveOrgId` while its 10 peers use it). Off by default; reads neighbors from the synapse store (no embedder work); fails open. |
| `NEURALMIND_SYNAPSE_EXPORT` | `1` | *(v0.4.0+)* Set to `0` to disable session-start synapse memory export |
| `NEURALMIND_REUSE_FEEDBACK` | `1` | *(v0.41.0+)* Set to `0` to disable the `Edit`/`Write` reuse-vs-rewrite feedback hook. When enabled (default), new code that references a symbol already defined elsewhere in the graph reinforces the synapse edge between the edited file and the reused definition, so retrieval learns what you actually reuse. The **implicit** complement to the explicit `neuralmind_feedback` MCP tool. Language-agnostic, never forces a build, fail-open. |
| `NEURALMIND_TEAM_MEMORY` | `1` | *(v0.30.0+)* Set to `0` to disable auto-inheriting a committed `.neuralmind-team-memory.json` team bundle. When enabled (default), a teammate's `SessionStart`/`build` imports the bundle **once** into the `shared` namespace (content-hash-gated, `shared`-only, fail-open). Publish your own with `neuralmind memory publish`. |
| `NEURALMIND_READ_DEDUP` | `1` | *(v4.6.0+)* Set to `0` to stop the `Read` PostToolUse hook from replacing a repeat read of unchanged content with a stub. Inactive anyway without a session id, in a project without `.neuralmind/`, and under `NEURALMIND_BYPASS=1` or `NEURALMIND_NO_LEARN=1`. See [`install-hooks`](#install-hooks). |
| `NEURALMIND_SESSION_RECAP` | `1` | *(v4.8.0+)* Set to `0` to stop recording prompts and edited files under `.neuralmind/recaps/` and stop the `SessionStart` recap. `NEURALMIND_NO_LEARN=1` stops the recording only; an existing recap is still shown. See [`recap`](#recap-v480). |
| `NEURALMIND_SESSION_RECAP_MAX_AGE_DAYS` | `14` | *(v4.8.0+)* A recap whose session was last active longer ago than this many days isn't shown, at `SessionStart` or by `neuralmind recap`. |
| `NEURALMIND_PROJECT` | unset | *(v4.9.0+)* Hermes plugin: the project to serve, ahead of the one given to `install-hermes-plugin`, Hermes's `TERMINAL_CWD` and the directory Hermes runs in. A project that hasn't been built is skipped. Without it or a pinned project, a gateway session uses the gateway's terminal working directory (`terminal.cwd`, else `MESSAGING_CWD`, else your home directory). Set it, or pin a project, for Hermes Desktop, ACP editor sessions and per-session workspaces, which keep each session's directory where the plugin doesn't read it. See [`install-hermes-plugin`](#install-hermes-plugin-v490). |
| `NEURALMIND_HERMES_TIMEOUT` | `8` | *(v4.9.0+)* Hermes plugin: seconds each call to NeuralMind may wait before the turn goes ahead without that call's context. A session's first turn makes two (the recap, then recall), so it can wait up to twice this; each recorded edit gets the same limit. Keep twice this below Hermes's `plugins.hook_callback_timeout` (default 30 s): past that, Hermes drops the whole block and skips the plugin's per-turn hook for the next 60 seconds. See [`install-hermes-plugin`](#install-hermes-plugin-v490). |
| `NEURALMIND_DECISION_SCAN` | `1` | *(v4.6.0+)* Set to `0` to make `neuralmind decisions scan` (and so the `init-hook` post-commit hook) skip marking decisions STALE. |
| `NEURALMIND_DECISION_SEARCH` | `hybrid` | *(v4.8.0+)* Default decision-search mode for the CLI, the MCP tools and the Python API when a call names none: `hybrid` (shared words and meaning, fused), `semantic` (meaning only) or `keyword` (shared words only, the v4.6 behavior). Case-insensitive; an unknown value is logged and ignored. A call's own `--mode` / `mode` wins. See [`decisions`](#decisions-v410). |
| `NEURALMIND_ACTOR_EMAIL` | unset | Who `neuralmind team` commands act as when `--admin` is omitted (unset: `unknown`, which no admin list matches), and *(v4.6.0+)* the actor recorded for team-memory audit events (publish, import, review); for those, unset falls back to the repository's `git config user.email`, then the OS user. `NEURALMIND_ACTOR` is an accepted alias. |
| `NEURALMIND_EVENT_LOG` | `1` | *(v0.6.0+)* Set to `0` to disable the cross-process JSONL event-bridge writer at `<project>/.neuralmind/events.jsonl`. The in-process event bus is unaffected; `serve` running in the same process as the activity source still gets a live feed. |
| `NEURALMIND_OUTPUT_CACHE` | `1` | *(v0.10.0+)* Set to `0` to disable the recovery cache that backs `neuralmind last`. It also turns off `NEURALMIND_BASH_REPLACE`, which never trims an output it has nowhere to keep whole. |
| `NEURALMIND_OUTPUT_CACHE_MAX` | `2097152` | *(v0.10.0+)* Total size cap (bytes) for the recovery cache. Oversize payloads are split proportionally between stdout/stderr and truncated keeping head + tail. |
| `NEURALMIND_BASH_REPLACE` | unset | *(v4.10.0+)* Set to `1` to let the `Bash` PostToolUse hook replace the output of an allowlisted noisy log with its progress lines elided, via `updatedToolOutput`. The allowlist is `pip install` (also `python -m pip install`) and `neuralmind build`, run on their own (after `cd`, `source` or variable assignments at most; any pipe, redirect or second command disqualifies the line). Each run of elided lines becomes one `[neuralmind: N progress lines elided: …]` marker; every other line, and any line mentioning an error, warning, failure or deprecation, reaches Claude as printed. The full output, credentials redacted, is kept in `.neuralmind/bash_outputs/` (newest 20), and the replaced result ends with its path. Other commands, failed commands, and Read and Grep results are never replaced. Measured, with its retention gates, in the [compression benchmark](https://github.com/dfrostar/neuralmind/blob/main/docs/benchmarks/compression.md). Hooks inherit Claude Code's environment, so set it in `.claude/settings.json` (`"env": {"NEURALMIND_BASH_REPLACE": "1"}`) or before launching `claude`. |
| `NEURALMIND_BASH_SMALL` | `500` | *(v0.10.0+)* Threshold below which `compress_bash()` passes failing output through verbatim. Python API only: the hooks no longer compress tool output. |
| `NEURALMIND_BASH_MAX_CHARS` | `3000` | Threshold above which `compress_bash()` compresses successful output. Python API only: the hooks no longer compress tool output. |
| `NEURALMIND_BASH_TAIL` | `3` | Number of tail lines `compress_bash()` always keeps verbatim. Python API only: the hooks no longer compress tool output. |
| `NEURALMIND_EVAL_LLM_JUDGE` | `0` | *(v0.13.0+)* Opt-in LLM-as-judge mode for the offline faithfulness eval harness (`evals/faithfulness/`). Off by default and **never** the CI gate; when set, the runner prints a notice that answers + gold facts would be sent to a third-party API. The default judge is the zero-network offline expected-fact-recall scorer. |
| `NEURALMIND_PARITY_REDUCTION_TOL` | `0.25` | *(v0.15.0+)* Backend parity gate (`evals/parity/run.py`): max fraction the built-in backend's mean token reduction may sit below graphify's (0.25 = within 25%). |
| `NEURALMIND_PARITY_FAITHFULNESS_TOL` | `0.10` | *(v0.15.0+)* Backend parity gate: max absolute points the built-in backend's faithfulness delta / fact recall may sit below graphify's (0.10 = 10 points). |
| `NEURALMIND_PARITY_REDUCTION_FLOOR` | `4.0` | *(v0.15.0+)* Backend parity gate: absolute minimum mean reduction the built-in backend must clear, independent of graphify (mirrors the self-benchmark floor). |
| `NEURALMIND_PARITY_FAITHFULNESS_FLOOR` | `0.0` | *(v0.15.0+)* Backend parity gate: absolute minimum faithfulness delta the built-in backend must clear (mirrors the eval gate — smart selection ≥ matched-budget naive truncation). |
| `NEURALMIND_PARITY_COVERAGE_FLOOR` | `0.90` | *(v0.16.0+)* Backend parity gate: minimum fraction of the gold graph's per-language symbols the built-in backend must recover for TypeScript/Go/Rust/Java/C/C++ (structural parity, since no gold-fact set exists for those fixtures yet). |
| `NEURALMIND_PRECISION` | unset | *(v0.17.0+)* Set to `1` to enable the optional SCIP precision pass: when a `*.scip` index is present in the project root, the built-in backend's heuristic `calls`/`inherits` edges are replaced with compiler-accurate ones for the files the index covers. Off by default; a no-op when unset or when no index is found. |
| `NEURALMIND_ONNX_MODEL_DIR` | unset | *(v0.21.0+)* Path to a pre-extracted `all-MiniLM-L6-v2` ONNX folder (`model.onnx` + `tokenizer.json`) for the ChromaDB-free `turbovec` backend's bundled embedder. When unset, the model is resolved from NeuralMind's cache, an existing ChromaDB cache, or downloaded (SHA256-verified). Set it for **air-gapped** installs so no network is needed. |
| `NEURALMIND_ORT_THREADS` | unset | Pin the ONNX Runtime intra-op thread pool for the bundled MiniLM embedder to N threads (inter-op is set to 1 alongside it). Unset keeps ORT's default (sized to the host's core count). ORT's parallel summation order moves the last bits of the embedding floats with the thread count, so near-tie rankings can differ between machines with different core counts; `1` removes that dependence at some indexing-throughput cost. It does not make output identical on every machine: with `1` set, public-benchmark CI runs still split into two states with slightly different token counts depending on the runner, while on an Apple M3 the public benchmark gave byte-identical output with and without it ([details](../benchmarks/public.md#how-exactly-a-re-run-reproduces)). The self-benchmark harness sets `1` automatically, and the public-benchmark CI job runs with it. |
| `NEURALMIND_NO_DAEMON` | unset | *(v0.23.0+)* Set to `1` to force CLI commands to run in direct mode even when a daemon is running (skips the daemon auto-preference for `query`/`stats`). |
| `NEURALMIND_NAMESPACE` | unset | *(v0.24.0+)* Pin the active memory namespace for this process (e.g. `ephemeral` for throwaway exploration, `shared` on a CI box building team baseline). Overrides config and git-branch detection. Resolution order: this var → `memory_namespace:` in `neuralmind-backend.yaml` → `branch:<name>` on a non-default git branch → `personal`. |
| `NEURALMIND_DAEMON_HOME` | unset | *(v0.23.0+)* Override the directory holding the daemon discovery file (`daemon.json`). Defaults to `~/.neuralmind`. Mainly for tests / running an isolated daemon. |
| `NEURALMIND_BM25` | `1` | *(v0.38.0+)* Set to `0` to disable the BM25 keyword index and fall back to pure vector search. When enabled (default), the BM25 index built by `neuralmind build` is merged with vector results via Reciprocal Rank Fusion at query time, improving exact-name retrieval for code queries like `"UserService"` or `"get_auth_token"`. The index is stored in `<project>/.neuralmind/bm25_index.json` and rebuilt automatically on every `neuralmind build`. `0` also turns off the v4.6.0 keyword indexes below. |
| `NEURALMIND_BM25_UNIFIED` | `1` | *(v4.6.0+)* One BM25 index over every node — doc text, symbol names, file paths, docstrings — written by `neuralmind build` to `<project>/.neuralmind/bm25_unified_index.json` and fused into L3 by RRF. On the default turbovec backend the keyword index otherwise holds only document nodes, so docs get a keyword signal code never does; the ChromaDB backend's index already covered every node, and this makes both behave the same. Set to `0` to restore v4.5.0's keyword list. An index built before v4.6.0 keeps the old list until the next `neuralmind build` (queries never build). It adds one BM25 lookup per query. Measured on six repos: mean hit@5 72.8% → 79.4%; `requests` −1 question, `rich` MRR 0.71 → 0.60, and on the public benchmark `click` gains a miss (reproducible on demand, not a CI gate; [eval](https://github.com/dfrostar/neuralmind/blob/main/bench/retrieval/README.md)). |
| `NEURALMIND_BM25_CODE` | unset | *(v4.6.0+, research flag)* Set to `1` to fuse a second, code-only keyword list (symbol names, their files and docstrings) by RRF. **Off by default because it lost on the retrieval eval:** `requests` −3 questions against v4.5.0; on top of the unified index, `rich` −4 and `click` −3. |
| `NEURALMIND_SELECTOR_AUTOTUNE` | `0` | *(v0.26.0+)* Set to `1` to enable the self-improvement engine's selector auto-tuner: the `SessionStart` hook adjusts the L2 recall depth from the re-query rate (once per session), and `build()` threads the persisted value into the selector. Opt-in (`== "1"`, not the `!= "0"` pattern) because it is net behavior change. With it unset the hot path does **zero** extra I/O and the selector keeps its hard-coded default. Inspect state with `neuralmind self-improve status`. |
| `NEURALMIND_STRUCTURAL` | `1` | *(v0.42.0+)* Master switch for the structural code-graph layer (`calls`/`inherits`/`imports_from` edges from `graph.json`). Powers the `neuralmind structural` command, the `neuralmind_structural_neighbors` MCP tool, and blast-radius. Set to `0` to skip building the index entirely, leaving retrieval byte-identical to v0.41.0. |
| `NEURALMIND_STRUCTURAL_RECALL` | `0` | *(v0.42.0+)* Opt-in (`== "1"`). Fold a query hit's structural neighbors (callers/callees/base classes) into L3 retrieval, budget-neutrally (displacement, not addition). **Off by default** because the structural signal can saturate top-k recall and crowd out the learned synapse reranker on some graphs; the always-on structural **query tools** carry the value with zero effect on the tuned retrieval stack. |
| `NEURALMIND_STRUCTURAL_MIN_CONFIDENCE` | `0.0` | *(v0.42.0+)* Drop structural edges whose `confidence_score` is below this value when building the index. Raise toward `1.0` to trust only compiler-accurate edges (pair with `NEURALMIND_PRECISION`). |
| `NEURALMIND_STRUCTURAL_HUB_DEGREE` | `50` | *(v0.42.0+)* Per-relation degree cap for structural recall and blast-radius. Above the cap, an over-connected utility's neighbors are down-weighted (recall) or truncated (blast-radius) so one hub can't dominate. |
| `NEURALMIND_PARITY_SAMPLES` | `3` | *(v3.9.0+)* Backend parity gate: how many times the faithfulness A/B is sampled before the mean is gated. Averaging absorbs ANN query-time ordering jitter, matching the self-benchmark's onboarding-lift gate, so a failure means a real regression rather than an unlucky draw. Set to `1` to restore single-sample behavior. |
| `NEURALMIND_DRIFT_REFRESH` | `1` | *(v3.2.0+)* Set to `0` to make `neuralmind drift` judge strictly against the last-built graph, skipping the transparent re-parse of changed files (same effect as `--no-refresh`). The re-parse needs tree-sitter (the `graphgen` extra); without it this is already a no-op. |
| `NEURALMIND_CHUNK_SIZE` | `500` | *(v3.4.0+)* Default max characters per chunk for `ingest-content`, so a corpus's chunking doesn't have to be retyped on every run. `--chunk-size` overrides it. A malformed value warns and falls back to the default rather than failing the ingest. |
| `NEURALMIND_OVERLAP` | `50` | *(v3.4.0+)* Default character overlap between chunks for `ingest-content`. `--overlap` overrides it. Must be less than the chunk size — the chunker cannot make progress otherwise, so the command exits `2` with the offending pair named. |
| `NEURALMIND_INGEST_TIMEOUT` | `0` | *(v3.4.0+)* Default `--timeout` for `ingest-content`, in seconds; `0` means unlimited. On expiry the run stops between files, writes the manifest for what it indexed, and exits `1` — the next run resumes rather than restarting the corpus. |
| `NEURALMIND_NO_LEARN` | unset | *(v4.5.0+)* Set to `1` to make every query in the process read-only — CLI, MCP server and hooks. Synapse recall still shapes results, but nothing is reinforced or logged, the synapse database is opened read-only, hooks skip edit/transition learning, decay and *(v4.8.0+)* session-recap recording, and nothing builds an index. For eval harnesses and CI. Per call: `query --no-learn`, MCP `learn: false` |
| `NEURALMIND_NO_PROGRESS` | unset | *(v3.4.0+)* Set to `1` to suppress progress output everywhere (same as `--no-progress`), `build` included. Progress is TTY-aware already — an in-place bar on a terminal, plain milestone lines off one for `ingest-content` — so this is for golden-output tests and log-sensitive CI jobs. Since v4.4.0 the `build` embedding bar shows only on a terminal, and read commands (`query`, `search`, `wakeup`, the MCP tools) print nothing on success. |
| `NEURALMIND_INTENT_THRESHOLD` | `0.6` | *(v3.9.0+)* Margin the intent classifier needs before it calls a query `code` or `docs` rather than `hybrid`: one side's keyword score must exceed the other's by this fraction. Raise it to send more queries down the neutral `hybrid` path. |
| `NEURALMIND_CODE_BOOST` | `3.0` | *(v3.9.0+)* Score multiplier applied to code hits when a query is classified `code` (doc hits are multiplied by `0.5`). Re-ranks the hits retrieval already returned; it does not add any. |
| `NEURALMIND_DOC_BOOST` | `2.0` | *(v3.9.0+)* Score multiplier applied to doc hits when a query is classified `docs` (code hits are multiplied by `0.7`). |
| `NEURALMIND_RETRIEVAL_EXPANSION` | `0` | *(v3.10.0+)* Opt-in — set to `1`, `true`, `yes` or `on` (case- and whitespace-insensitive); anything else, including unset, is off. Lets the v3.9.0 retrieval pull-in — two-pass source-file search, synapse-seeded expansion, and snippet extraction — contend for L3 slots, budget-neutrally (displacement, not addition). **Off by default because it was measured, not because it is unfinished:** on the faithfulness fixture it takes the delta from `+0.041` to `-0.065` appended (how v3.9.0 shipped) or `-0.107` displaced, against a `+0.000` gate floor. Making it budget-neutral made it worse, which is the useful finding — displacing evicts a real hit per candidate, so candidates that are worse than what they replace cost facts, not just tokens. Intent classification and the code-signal boost are unaffected by this flag and stay on; they are bit-for-bit neutral on the same fixture. Turning this on is a research setting until a gate says otherwise. Reproducing these numbers requires a **fresh copy of the fixture per sample** — `query()` reinforces synapses into `<project>/.neuralmind/synapses.db`, so re-running against the same directory measures a progressively trained index, not a repeat. |
| `NEURALMIND_L3_PER_FILE` | unset | *(v4.6.0+, research flag)* Set to `N` to allow at most N L3 hits per file, refilling vacated slots from the next-best candidates of the same search. **Off by default:** at `2` it raised mean hit@5 by 1.1 points with two repos up and none down on hit@5 (public recall 96.25%), but mean MRR fell 0.654 → 0.629 (`requests` 0.75 → 0.69, `flask` 0.71 → 0.65), and the keep rule needs three repos. |
| `NEURALMIND_DOC_HANDOFF` | unset | *(v4.6.0+, research flag)* Set to `1` so a doc hit that names a code file or symbol brings that code into contention for an L3 slot. **Off by default:** it helps only where the docs name code (against v4.5.0: the private repo +3 questions, `neuralmind` +1) and was a wash on top of the unified index. |
| `NEURALMIND_HUB_DAMPEN` | unset | *(v4.6.0+, research flag)* Set to `1` to down-weight files returned far more often than chance (with a floor, so a hub that is the only match still wins). **Off by default:** it cost `click` 3–4 questions — on a small library the most-returned files are central modules, not hubs. |
| `NEURALMIND_INTENT_RULES` | unset | *(v4.6.0+, research flag)* Set to `1` to classify "how does X…", "where is X…" and "which X is…" questions as `code` intent (and questions that name a document or ask how to install as `docs`) before the v3.9.0 classifier runs; `query --explain` then shows `(by question shape)`. **Off by default:** it only re-orders the four hits L3 already chose, so it moved MRR (0.654 → 0.672) and never hit@5. |
| `NEURALMIND_INTENT_POOL` | unset | *(v4.6.0+, research flag)* Set to `1` (measured with `NEURALMIND_INTENT_RULES=1`) to let intent rank all 10 search candidates instead of re-ordering the four L3 chose. **Off by default:** it cost `click` 8 questions and took the public benchmark's recall to 83.75% (measured against v4.5.0). |

---

## Vector backend selection *(v0.21.0+)*

NeuralMind's vector store is pluggable. The default is `auto` (an unset config
behaves the same): it resolves to the **ChromaDB-free** `turbovec` backend when
its stack (`turbovec` + `onnxruntime` + `tokenizers`) is importable, and
otherwise falls back to `chroma`. **As of v0.29.0 the turbovec stack is a
platform-gated base dependency**, so a plain `pip install neuralmind` resolves
to turbovec (ChromaDB-free) out of the box on platforms with turbovec wheels
(Linux, macOS arm64, Windows x86_64). On platforms without a turbovec wheel
(Intel macOS, Windows ARM) ChromaDB is auto-installed as the fallback backend,
so the install always works. Install `pip install "neuralmind[chromadb]"` (and
pin `backend: graph`) to force ChromaDB anywhere. (Alpine/musl Linux: use a
`python:slim` glibc image or the `[chromadb]` extra — markers can't gate musl.)

To **pin** a backend explicitly (an explicit value always wins over `auto`), drop
a `neuralmind-backend.yaml` at the project root:

```yaml
backend: turbovec   # the default path: TurboVec ANN + bundled OnnxMiniLMEmbedder
# backend: graph    # force ChromaDB (alias: chroma) — needs `pip install "neuralmind[chromadb]"`
# backend: auto     # the default — turbovec when its deps are installed, else chroma
```

The turbovec/ONNX stack ships by default; `pip install "neuralmind[chromadb]"`
adds the opt-in ChromaDB backend. Vectors are byte-identical between backends, so
retrieval quality is at/above parity; the turbovec index is 8–16× smaller.
Selecting `graph`/`chroma` without the `[chromadb]` extra raises an actionable
error pointing at the install command. Accepted values: `auto` (default),
`graph` / `chroma`, `turbovec`, `in_memory` (offline tests).

**One-time auto-reindex.** When `auto` resolves to turbovec for a project that
still has a legacy ChromaDB index and no turbovec index yet, the next build
reindexes from `graph.json` and prints a one-line notice. The old ChromaDB index
is left in place as a fallback — nothing is deleted.

Run `neuralmind doctor` to see which backend the current environment resolves to
(see the **Backend** line).

### Security settings (`security:` in neuralmind-backend.yaml)

The same file carries the MCP security policy. The file is read once per
process, so restart the MCP server after changing it.

| Key | Default | Effect |
|-----|---------|--------|
| `roles` | built-in `admin` / `builder` / `reader` | Role name → list of MCP tool names, or `"*"` for all. Replaces the default policy; a role it doesn't list gets no tools, and an empty mapping grants nothing. The MCP server in v4.6.0 and earlier ignored this setting |
| `rate_limit` | `max_calls: 60`, `window_seconds: 60` | Calls allowed per actor per window. Whole numbers; `window_seconds` at least 1 |
| `identity` *(v4.7.0+)* | `declared` | `declared`: each MCP call names its own `actor` and `role`, unauthenticated. `os`: the actor is the OS account the server runs as, read from the OS rather than environment variables, and the role comes from `users`. Stdio transport only |
| `users` *(v4.7.0+)* | `{}` | OS account name → role, used with `identity: os` |
| `default_role` *(v4.7.0+)* | unset | Role for an OS account missing from `users`. Unset refuses such accounts |
| `require_encrypted_storage` *(v4.7.0+)* | `false` | Refuse to build, query, serve MCP tools, or run hooks unless every volume holding state (the project, `.neuralmind/`, a custom `db_path`) is verified encrypted. Only `false`, `0`, `no` or `off` turns it off; a blank value counts as on |

```yaml
security:
  identity: os
  users:
    alice: builder
    bob: reader
  roles:
    builder: [neuralmind_wakeup, neuralmind_query, neuralmind_search, neuralmind_skeleton, neuralmind_build]
    reader: [neuralmind_wakeup, neuralmind_query, neuralmind_search, neuralmind_skeleton]
  require_encrypted_storage: true
```

With `identity: os`, NeuralMind refuses every MCP call when it can't establish
the caller: the HTTP transport is in use, the OS account can't be read, the
account has no role, or the policy file is world-writable (POSIX). A policy file
that doesn't parse but names a security setting (`security`, `roles`,
`rate_limit`, `identity` or `require_encrypted_storage`) is refused too,
rather than silently ignored (v4.7.0 checked only `identity` and
`require_encrypted_storage`), and so is a malformed `security`, `roles` or
`rate_limit` value, or *(v4.8.0+)* a `security:` or `roles:` key left empty. Each refusal is written to
`.neuralmind/audit_events.jsonl` with `reason: identity`, `storage`, or `config`,
and the actor and role a call claimed are kept as `claimed_actor` and
`claimed_role`.

---

## Examples

### Complete Workflow

```bash
# 1. Build neural index (the code graph is generated automatically)
neuralmind build ~/projects/myapp

# 3. View statistics
neuralmind stats ~/projects/myapp

# 4. Get wake-up context for new conversation
neuralmind wakeup ~/projects/myapp > context.md

# 5. Query specific functionality
neuralmind query ~/projects/myapp "How does the payment system work?"

# 6. Search for specific entities
neuralmind search ~/projects/myapp "PaymentController" --n 5

# 7. Run benchmark
neuralmind benchmark ~/projects/myapp
```

### Scripting Integration

```bash
#!/bin/bash
# update_and_query.sh - Update index and run queries

PROJECT="$1"
QUERY="$2"

# Rebuild if graph changed
if [ graphify-out/graph.json -nt graphify-out/neuralmind_db ]; then
    echo "Graph updated, rebuilding index..."
    neuralmind build "$PROJECT"
fi

# Run query
neuralmind query "$PROJECT" "$QUERY" --json
```

### Piping to AI Tools

```bash
# Get context and pipe to clipboard (macOS)
neuralmind wakeup ~/projects/myapp | pbcopy

# Get context and pipe to clipboard (Linux)
neuralmind wakeup ~/projects/myapp | xclip -selection clipboard

# Save context to file for AI assistant
neuralmind query ~/projects/myapp "Explain the auth system" > auth_context.md
```

---

## See Also

- [API Reference](API-Reference.md) - Python API documentation
- [Architecture](Architecture.md) - System design details
- [Integration Guide](Integration-Guide.md) - MCP and tool integrations
