# Memory Layer

The Memory Layer gives agents persistent, queryable decision memory: every architectural decision is recorded with its rationale, evidence, and the git commit where it was made — and goes stale when a commit changes the code it describes (v4.6.0+, through the post-commit hook from `neuralmind init-hook`).

## Overview

- **Storage:** SQLite (`.neuralmind/memory.db` in your project root), created on first use
- **Search:** FTS5 keyword search over titles and rationales, prefix-matched. Common words (how, do, the…) are dropped, any remaining word can match, and bm25 ranks decisions that match more of the words first, so a question works as well as keywords. Evidence, tags and rejected alternatives are stored and returned with each record, but search doesn't look at them yet.
- **Invalidation:** file-touch and cascade rules, run after every commit by `neuralmind decisions scan` (the `init-hook` post-commit hook, v4.6.0+) — decisions whose files a commit changed after they were recorded go STALE
- **Access:** CLI (`neuralmind decisions`), MCP tools (7), and Python API

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
neuralmind decisions query "keywords or a question" [project_path] [--limit 10] [--status ACTIVE|STALE|INVALIDATED|ALL] [--json]
```

The query text comes **first**; the project path is optional and comes second.
Search matches the query's words against titles and rationales, prefix-matched
("pool" finds "pooling"). Common words such as "how", "do" and "the" are
dropped, a decision needs to contain only one of the remaining words, and bm25
ranks the decisions that contain more of them, and rarer ones, first. So "how
do we handle sqlite wal?" finds what "sqlite wal" finds. The flip side: a
question nothing answers still returns the closest partial matches, so check
the titles before relying on a hit. Without FTS5 (some minimal SQLite builds)
the same words are matched as substrings, and decisions containing more of
them rank first. `--status` is case-insensitive and defaults to `ACTIVE`;
`ALL` includes every status.

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
neuralmind decisions eval --queries tests/memory/fixtures/decision_queries.json [--limit 5] [--format json|md]
```

Both seed a scratch store in a temporary directory and never read or change
your project's decisions. Earlier versions deleted `.neuralmind/memory.db` in
`project_path` (the current directory by default) and left 15 synthetic
decisions in its place. If you ran `decisions eval` inside a project, those
decisions have the author `eval-harness`: find them with
`neuralmind decisions audit --format json` and retire each with
`neuralmind decisions invalidate <id> --reason "eval seed"`.

The default run replays five maintenance tasks with keyword queries and
reports recall, precision and stale influence with the status filter on and
off. `--queries` scores search against questions with known answers and lists
every miss, false positive and answer not ranked first. The committed set,
`tests/memory/fixtures/decision_queries.json`, is synthetic: 35 decisions (30
ACTIVE), 20 agent-style questions that each share at least one word with their
answer, and 4 questions nothing answers. The eval also asks every ACTIVE
decision's exact title. Measured with FTS5 at the default limit of 5
(`tests/memory/test_query_eval.py` keeps this table in step with the eval):

| Measure | Result |
|---------|--------|
| Recall@5 on 20 questions, mean (range) | 1.00 (1.00–1.00) |
| MRR on 20 questions, mean (range) | 0.94 (0.33–1.00) |
| Exact titles ranked first | 30 of 30 |
| Questions nothing answers that still return decisions | 2 of 4 |
| Recall@5 without FTS5 (LIKE fallback), mean (range) | 0.95 (0.00–1.00) |
| Maintenance tasks, recall / precision at limit 10 | 90% / 53% |

When every word had to appear, none of the 20 questions returned anything, and
the maintenance tasks scored 50% recall and 83% precision. The misses now: two
answers rank second and third rather than first; two of the four unanswerable
questions return partial matches; without FTS5 one question misses its answer;
and the maintenance tasks' precision fell because partial matches fill the
list below the answers, which still rank first to third. A question that
shares no word with its answer is still not found: that takes semantic search.

## MCP Tools

Registered in the MCP server (28 tools total as of v4.3.0):

| Tool | Arguments | Description |
|------|-----------|-------------|
| `neuralmind_query_decisions` | `project_path`, `query`, `limit` | Search decision titles and rationales by keywords or a question (ACTIVE only) |
| `neuralmind_audit_decisions` | `project_path`, `stale_only` | List decisions, filter by status |
| `neuralmind_record_decision` | `project_path`, `title`, `rationale`, `commit_sha`, `files_affected`, `decision_type`, `confidence`, `evidence`, `rejected_alternatives`, `tags` | Store a new decision |
| `neuralmind_invalidate_decision` | `project_path`, `decision_id`, `reason` | Mark a decision INVALIDATED; the reason is appended to its evidence |
| `neuralmind_memory_search` | `project_path`, `query`, `limit`, `status` | **Layer 1** — compact index rows (~50–100 tokens each). Cheap first call; filter here before fetching. `status` is `ACTIVE` (default), `STALE`, `INVALIDATED` or `ALL`, case-insensitive; an unknown value returns an error |
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
- Roles are declared by the MCP caller and not authenticated; see the [Security Guide](../SECURITY-GUIDE.md#access-control)

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

The tests in `tests/memory/` cover store CRUD/FTS/audit/export, search terms and ranking on both the FTS5 path and the LIKE fallback, the invalidation engine (file-touch, the carrying-commit exemption, renames, merges, subdirectory projects, cascade, idempotency), `decisions scan`, MCP tool dispatch, both eval harnesses and the decision-search eval set, and integration (lifecycle, export/import roundtrip, 10-thread concurrency, broken-git graceful degradation).
