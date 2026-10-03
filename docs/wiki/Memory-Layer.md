# Memory Layer

The Memory Layer gives agents persistent, queryable decision memory: every architectural decision is recorded with its rationale, evidence, and the git commit where it was made — and goes stale when a commit changes the code it describes (v4.6.0+, through the post-commit hook from `neuralmind init-hook`).

## Overview

- **Storage:** SQLite (`.neuralmind/memory.db` in your project root), created on first use
- **Search:** FTS5 full-text search over titles, rationales, and evidence
- **Invalidation:** file-touch and cascade rules, run after every commit by `neuralmind decisions scan` (the `init-hook` post-commit hook, v4.6.0+) — decisions whose files a commit changed after they were recorded go STALE
- **Access:** CLI (`neuralmind decisions`), MCP tools (4), and Python API

## CLI Reference

> **Command group:** decision verbs live under **`neuralmind decisions`**. The
> `neuralmind memory` group carries management subcommands only (`inspect`,
> `reset`, `export`, `import`, `publish`, `review-*`, `staleness-*`).
> (v4.1.0 documented `neuralmind memory <verb>` — that surface was renamed;
> see the erratum in the v4.1.0 release notes.)

### Record a decision

```bash
neuralmind decisions record [project_path] --title "TITLE" --rationale TEXT
    [--commit SHA] [--files "a.py" "b.py"] [--type architecture]
    [--rejected "rejected option A" "rejected option B"]
    [--evidence "ref or URL 1" "ref or URL 2"]
    [--confidence 0.95] [--tags "perf" "storage"]
```

### Query decisions

```bash
neuralmind decisions query "natural language query" [project_path] [--limit 10] [--status ACTIVE|STALE|ALL] [--json]
```

The query text comes **first**; the project path is optional and comes second.

### Audit

```bash
neuralmind decisions audit [project_path] [--stale] [--orphaned] [--format md|json]
```

Lists every recorded decision by default. `--stale` / `--orphaned` narrow the
list to entries that need attention: age-based staleness (STALE_DAYS=90) plus
orphaned-SHA detection (commit no longer in git history).

### Amend / Invalidate / Restore

```bash
neuralmind decisions amend <decision-id> [--rationale TEXT] [--evidence "ref"] [--rejected "alt"]
neuralmind decisions invalidate <decision-id> --reason "why"
neuralmind decisions restore <decision-id> [--commit SHA]
```

### Scan the last commit *(v4.6.0+)*

```bash
neuralmind decisions scan [project_path] [--quiet] [--json]
```

Marks STALE every decision whose files the `HEAD` commit changed after the
decision was recorded. The post-commit hook installed by `neuralmind init-hook`
runs it after every commit (re-run `init-hook` on an older checkout). See
[Invalidation semantics](#invalidation-semantics).

### Export

```bash
neuralmind decisions export [project_path] [--format md|json] [--output FILE]
```

### Eval harness

```bash
neuralmind decisions eval [project_path] [--tasks 10] [--format json|md] [--output FILE]
```

## MCP Tools

Registered in the MCP server (28 tools total as of v4.3.0):

| Tool | Arguments | Description |
|------|-----------|-------------|
| `neuralmind_query_decisions` | `project_path`, `query`, `limit` | Natural-language search over decisions |
| `neuralmind_audit_decisions` | `project_path`, `stale_only` | List decisions, filter by status |
| `neuralmind_record_decision` | `project_path`, `title`, `rationale`, `commit_sha`, `files_affected`, `decision_type`, `confidence`, `evidence`, `rejected_alternatives`, `tags` | Store a new decision |
| `neuralmind_invalidate_decision` | `project_path`, `decision_id`, `reason` | Mark a decision INVALIDATED (reason kept in its evidence) |
| `neuralmind_memory_search` | `project_path`, `query`, `limit`, `status` | **Layer 1** — compact index rows (~50–100 tokens each). Cheap first call; filter here before fetching |
| `neuralmind_memory_timeline` | `project_path`, `decision_id` or `query`, `before`, `after` | **Layer 2** — chronological context around an anchor decision |
| `neuralmind_memory_get` | `project_path`, `ids` (max 20) | **Layer 3** — full records (rationale, rejected alternatives, evidence); batch-capped to force filtering |

### Progressive retrieval workflow (v4.3.0)

```
memory_search   →  scan compact rows, pick candidates (~50-100 tokens/row)
memory_timeline →  (optional) what else was decided around a hit
memory_get      →  full records for the shortlist (batch-capped at 20)
```

A "why did we choose X over Y?" lookup completes in ≤3 tool calls and
≤2,000 tokens on the fixture repo. The single-shot tools above remain
for compatibility.

### RBAC

- **Builder role:** all 7 memory tools
- **Reader role:** `query` + `audit` + the 3 progressive-retrieval tools — write tools verified denied

## Invalidation Semantics

- `invalidate()` sets status to `INVALIDATED` (not `STALE`) and appends the reason to the decision's evidence
- **Automatic staleness (v4.6.0+):** `neuralmind decisions scan` (run by the `init-hook` post-commit hook) diffs `HEAD` against its first parent, relative to the project. A decision whose `files_affected` includes a changed file goes **STALE**, with `Marked STALE: commit <sha> changed <files> since this decision was recorded` appended to its evidence; dependents cascade. Any change counts — no diff analysis
- **The commit that carries a decision keeps it ACTIVE:** a decision anchored to `HEAD` is left alone, and so is one whose fingerprints match the commit. `record`, `amend` and `restore` store each affected file's git blob id (`decision_fingerprints` table); when every changed file the decision names is stored by the commit exactly as fingerprinted, the commit carries the code the decision describes. No fingerprint, no exemption
- Invalidation is **file-scoped**: untouched decisions stay ACTIVE. Renames count both paths; merge commits count everything they brought in; pulls and rebases don't run post-commit hooks
- `restore` re-anchors a STALE or INVALIDATED decision to a commit (default `HEAD`) and makes it ACTIVE again
- `audit` lists all decisions by default; `--stale`/`--orphaned` filter to entries needing attention (age-based 90-day staleness plus orphaned-SHA detection)
- `DecisionStore` has no `.close()` — connections are managed internally

## Stale-Decision Guard (v4.2.0)

The runtime counterpart of the eval harness's `stale_influence_rate` metric: instead of only measuring how often stale memory steers edits, the guard prevents it.

**How it works:** when your agent is about to edit a file (Claude Code `Edit`/`Write` tools), a `PreToolUse` hook checks the decision store for any STALE or INVALIDATED decisions whose `files_affected` covers that file. If found, they're injected into the agent's context before the edit lands:

```
[neuralmind stale-guard] 1 decision(s) governing neuralmind/db.py are no longer ACTIVE. Their rationale may not hold — verify before relying on them:
- [STALE] Use SQLite WAL (id 5b1e0c7a-…, confidence 0.90, updated 2026-09-10): WAL mode required for concurrent readers... — commit 3f9c2ab changed neuralmind/db.py since this decision was recorded
If a STALE decision still holds after you check the code, `neuralmind decisions restore <id>` re-anchors it to HEAD.
```

Since v4.6.0 each line carries the full id and the reason the decision left
ACTIVE (from its evidence).

The agent sees which remembered rationales may no longer hold — before it edits, not after.

**Properties:**

- **Fail-open by design** — no store, guard error, or empty result produces no output; the edit proceeds normally. A guard failure must never block an edit.
- **Never denies edits** — pure context injection. The agent (and user) decide what to do with the information.
- **Opt-out:** `NEURALMIND_STALE_GUARD=0`
- **Cap:** at most 5 decisions surfaced per edit, with a pointer to `neuralmind decisions audit` for the rest
- **Path normalization:** absolute hook paths are resolved to repo-relative before matching `files_affected`

**Installation:** ships with `neuralmind install-hooks` (hook block v3). Existing installs pick it up automatically on upgrade — re-run `neuralmind install-hooks` after upgrading to v4.2.0+.

## Python API

```python
from neuralmind.memory.store import DecisionStore

store = DecisionStore(project_path=".")
store.record(
    title="Use SQLite for decision store",
    rationale="Single-file, no server, ACID-compliant",
    files_affected=["neuralmind/memory/store.py"],
    decision_type="architecture",
    confidence=0.95,
)
results = store.query("database choice")
```

## Testing

`tests/memory/` covers store CRUD/FTS/audit/export, the invalidation engine (file-touch, the carrying-commit exemption, renames, merges, subdirectory projects, cascade, idempotency), `decisions scan`, MCP tool dispatch, eval harness, and integration (lifecycle, export/import roundtrip, 10-thread concurrency, broken-git graceful degradation). All stdlib-only.
