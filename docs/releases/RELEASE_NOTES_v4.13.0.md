# NeuralMind v4.13.0 — the index stays fresh after pulls, merges, branch switches and rebases, and the git hooks work whatever PATH the git client has; usage and learning you can see, a grace period for staleness gates, MCP calls attributed to their client, no silent leftover graphify graph, and a way to measure whether the learned layer helps on your own repo

**Type:** Minor release | **Theme:** `neuralmind init-hook` keeps the index in step with the checked-out tree — not only with local commits — without making git wait, and without touching throwaway worktrees

Until now `init-hook` installed one rebuild hook, `post-commit`. A `git pull`
that brought in merged work, a branch switch, a merge or a rebase changed the
files on disk without a local commit, and the index went on describing the old
tree until the next one, with nothing to say so. The hook also found
`neuralmind` with `command -v`, so a git client whose PATH lacks the install
directory — GUI clients, IDEs, agents started by launchd or systemd, with
pipx and venv installs living in `~/.local/bin` — skipped it without a word.
And every commit waited for the rebuild. The field report is #630.

---

## What changed

### Git hooks

- **Pulls, merges, branch switches and rebases rebuild the index.**
  `init-hook` now also installs `post-merge` (merges and pulls),
  `post-checkout` (only a branch checkout that lands on a different commit:
  file checkouts and `git checkout -b` from the current commit don't rebuild)
  and `post-rewrite` (rebases and amends). `post-commit` keeps its decision
  scan, which runs synchronously because it reads HEAD.
- **The hooks work from any git client.** `init-hook` resolves the
  `neuralmind` path when you run it and writes it into the hooks, with
  `command -v neuralmind` as the fallback, so a commit from a client whose
  PATH lacks it still rebuilds. It prints the path it baked in, and says so
  when it found none. The pre-commit drift guard uses the same path, so it no
  longer skips silently either; `--strict` still blocks the commit on a drift.
- **git doesn't wait.** The rebuild runs in the background and logs to
  `.neuralmind/hook-build.log`. A lock in `.neuralmind/` serializes builds:
  an event that arrives while one runs leaves a pending flag and the running
  build goes round once more, so a burst of events (a rebase, a pull right
  after a commit) costs at most one extra build, and an event that lands
  while the lock is being released still gets its build. The lock records
  the build's PID, so a lock left by a build that died is cleared on the next
  event, while a build that runs for over an hour keeps its lock. The hooks
  don't stop an existing hook that runs under `set -e`. `--sync` keeps the
  foreground rebuild.
- **Throwaway worktrees are left alone.** Linked worktrees share a
  repository's hooks (#316). The hooks now rebuild only a project that has
  been built — `.neuralmind/build_status.json`, the same test the session
  hooks use, because those create `.neuralmind/` in any repository they run
  in. A worktree gets rebuilds once someone runs `neuralmind build` there,
  and not before. The decision scan keeps its own precondition: a decision
  store to scan.
- Each block still sits between the `neuralmind-hook-start` / `-end`
  sentinels, contains no `exit`, and runs after whatever the hook already
  held (git-lfs installs `post-checkout` and `post-merge`), so other tools'
  hooks keep working.

### Observability for agents that depend on NeuralMind daily

A field report from a team running NeuralMind across two repositories, with
Claude Code on a Mac and a local Hermes-Agent both pointed at the same
projects, found the core path fast and the edges silent: no way to tell whether
the index was being used, which agent made a call, or that a graph file in the
repository was no longer read. This release closes three of those gaps.

- **Every query and build is counted, without its text.**
  `.neuralmind/metrics/` had loggers for queries and builds that nothing
  called, so `neuralmind metrics` only ever showed prompt-time recall, and a
  monitor watching it for "is the index used?" saw nothing. Every query that
  learns and every build now writes a record: when, latency, tokens, search
  hits and reduction ratio for a query; duration, node count and the synapse
  store's edge and transition totals for a build. No question text is
  written, so it needs no memory-logging consent; `recent_queries.jsonl`,
  which does hold question text, still waits for it. `neuralmind metrics`
  shows the last query and build (`3h ago`), how many synapse edges and
  transitions the window's builds added, and a per-day table; `--json` has
  `per_day` and `last_ts`. `--no-learn` / `NEURALMIND_NO_LEARN=1` queries
  stay unrecorded.
- **MCP calls name their client.** The audit log recorded MCP calls as actor
  `anonymous` under the default `identity: declared`, with the role only in
  `details`. Each `mcp_call` and `mcp_call_denied` event now carries
  `details.client`, the `clientInfo` name and version the client sent when it
  connected (`claude-code`, `hermes`, …), and the resolved role as
  `actor_role`. `neuralmind audit recent` shows a Client column. The client
  names itself, so this attributes calls; it never grants or denies access.
  Works on MCP SDK 1.x and 2.x.
- **A leftover graphify graph is named on every build, and can be archived.**
  Under `graph_source: auto`, a project that upgraded from a graphify-era
  build moves to the built-in `.neuralmind/graph.json` and never reads
  `graphify-out/graph.json` again, but nothing said so after the first
  build. Now every build prints `Ignoring graphify-out/graph.json: …`, the
  new `doctor` check **Graph source** warns, and
  `neuralmind build . --archive-graphify` renames the file to
  `graph.json.archived-<timestamp>` (rename it back to restore it). Setting
  `graph_source` explicitly silences both.
- **`query --explain --json` keeps the explanation.** `--json` used to drop
  it; the output now has an `explain` object with the per-layer budget,
  layers, intent, communities, top hits with their scores, and the synapse
  events that fired.
- **Every build shows what the synapse layer learned.** `neuralmind build`
  prints `Synapses: 3,612 edges (+47 since last build), 12 transitions (+12)`,
  and `neuralmind stats` adds **Learning (last 7 days)**: synapse growth across
  the window's builds, the number of queries and when the last one ran. The
  same field report had 3,612 edges and 0 transitions with no way to tell
  whether that was expected. It was: transitions come only from the files an
  agent reads and edits in turn, through the Claude Code hooks or the Hermes
  plugin, or from `neuralmind watch`; queries strengthen edges and never add
  transitions. With 0 transitions, `build`, `stats` and `synapse stats` now say
  so, and the Learning Guide has a table of which surface trains what and how to
  turn each off.
- **Staleness gates get a grace period, and drift gets a date.** Set
  `stale_after: 30m` in `.neuralmind.yaml` (or pass `--stale-after 30m`):
  `neuralmind health` exits 0 with status `catching_up` while the index has been
  behind the files for under 30 minutes and 1 after, and `neuralmind doctor`
  fails its Code graph check (exit 1) once it has been behind for longer.
  "Behind" is dated from the oldest unindexed change: when each such file was
  first seen (kept in `.neuralmind/drift_seen.json`, so a file rewritten while
  the watcher is down doesn't restart the clock), or its modification time if
  earlier. Deleted files and graphs built on another OS have no date and always
  count. Doctor's lines for missing and changed files now end with
  `; newest modified 2h ago`, so a file written during an incident stands out
  from old drift.
- **The build hint for files that change without commits now says
  `neuralmind watch . --reindex`.** It used to suggest plain `neuralmind watch .`,
  which learns from edits but doesn't re-index them, so anyone following it kept
  a drifting index.

### Measuring the learned layer instead of assuming it

A field user put NeuralMind to an adversarial review: the retrieval demos
showed the right symbols coming back, but nothing showed the synapse layer
making retrieval better over time, and the store had sat at 0 transitions for
two months. That was a fair hit. The CI synapse gate is directional and runs on
a ~500-line fixture; nothing published shows the layer paying off on a real
codebase. This release adds the measurement, and the public pages now say what
is and isn't shown.

- **`neuralmind eval . --synapse-ab`** runs your `.neuralmind.eval.yaml`
  questions twice, read-only, with the learned recall on and then off
  (`NEURALMIND_SYNAPSE_INJECT=0` for the second run only). Under the usual
  summary it prints the "off" hit@1, hit@5 and MRR, how many questions the
  learned layer moved up or down, hit@5 won and lost with an exact McNemar
  p-value, and the size of the layer it read:

  ```
  NeuralMind eval — shop (12 questions, read-only)
    hit@1 50% · hit@5 83% · MRR 0.64
    ...
    learned recall off: hit@1 42% · hit@5 83% · MRR 0.60
    learned recall moved 2 question(s) up, 0 down, 10 unchanged · hit@5 0 won / 0 lost (exact McNemar p = 1.00)
    learned layer read: 3,612 edges (41 LTP), 12 transitions
  ```

  (illustrative). A cold layer gives identical runs and says so. The
  comparison is stored in `.neuralmind/eval_history.jsonl` with the run, and
  `neuralmind eval . --report` adds a **Learned recall on vs off** table, one
  row per A/B run, so you can see whether the gap grows as the layer does.
  `--json` includes it as `synapse_ab`.
- **The Hermes plugin learns transitions from reads.** It recorded only
  `write_file` and `patch`, so a Hermes session that read its way through a
  codebase taught the store nothing about the order. A successful `read_file`
  of a file inside the served project now records a transition step, as
  Claude Code's Read hook does (`neuralmind _hook read-activity`). Reads
  outside the project, such as Hermes's own config or another repository, are
  never recorded. `NEURALMIND_NO_LEARN=1` turns it off with the rest of the
  learning.

### FIPS-mode hosts

- **Document ingestion works with the OS FIPS mode on.** It hashed a
  file's parent directory with a bare `hashlib.md5()` to build node ids, and a
  FIPS-mode OpenSSL refuses MD5, so `neuralmind ingest`, `ingest-content`,
  book builds and the `neuralmind_ingest_document` MCP tool failed with
  `UnsupportedDigestmodError` on the hosts the CMMC walkthrough tells you to
  configure. The call now passes `usedforsecurity=False` (it's an id, not a
  security control), and so does a SHA-1 sort key in the L3 slot ranking.
  Node ids are unchanged, so no rebuild is needed.
- **CI runs the test suite with the OpenSSL FIPS provider enforced**
  (`scripts/setup_fips_openssl.sh`), and `tests/test_fips_hash_usage.py` fails
  any MD5, SHA-1 or BLAKE2 call in the repo that doesn't say it's not for
  security.

## What the agent actually sees

The index an agent queries matches the checked-out tree after a pull, branch
switch, merge or rebase, not only after a local commit. A commit an agent
makes returns before the rebuild finishes, and the hook prints one line —
`[neuralmind] Rebuilding the index in the background (log: ./.neuralmind/hook-build.log)` —
instead of the two it printed around a foreground rebuild. A commit in a
worktree nobody built prints nothing from NeuralMind.

`neuralmind metrics .` (and the dashboard's `/api/metrics`) now report the
agent's queries, so whoever runs the agent can see that it uses the index and
when it last did. An MCP call's audit event names the agent that made it:

```json
{"action": "mcp_call", "actor": "anonymous", "actor_role": "builder",
 "details": {"client": {"name": "claude-code", "version": "2.1.0"}, "role": "builder"}, ...}
```

An agent that asks `query --explain --json` gets the reasons with the context,
so it can check which files and scores the answer rests on before trusting it.

A build an agent runs now ends with the synapse line, for example
`Synapses: 3,612 edges (+47 since last build), 0 transitions (+0)` followed by
what produces transitions. A cron job or CI step that runs
`neuralmind health . --stale-after 30m` stops paging while a watcher catches up
and pages once it falls behind for longer.

An agent, or the person running it, can check the learned layer instead of
trusting it: `neuralmind eval . --synapse-ab --json` returns the on and off
metrics side by side. Under Hermes, a session that only reads files now builds
transitions, so `neuralmind next` has something to say about what usually
follows.

## Per-agent expectations

| Agent | What changes |
|---|---|
| Claude Code (hooks + MCP) | The index follows git operations, not only commits; commits it runs return before the rebuild; its MCP calls are attributed to `claude-code` in the audit log; no hook, MCP tool or response field changed |
| Cursor / Cline / Continue (MCP) | Same; each call's audit event names the client by its own `clientInfo` name |
| Hermes-Agent plugin | Same; its prompt-time recall was already counted in `neuralmind metrics`, and queries Hermes makes through the MCP server are now counted too. A `read_file` of a file inside the project records a transition step, one background `neuralmind _hook read-activity` call per read |
| Generic MCP client | Same; a client that sends no `clientInfo` (allowed from the 2026-07-28 protocol on) is recorded without a `client` field |

## Upgrading

- **Re-run `neuralmind init-hook .`** in each repository to get the new
  hooks; the managed blocks are replaced in place.
- **Build once first.** The hooks rebuild only a built project; in a
  repository that has never been built, run `neuralmind build .` (`init-hook`
  warns when there is no index yet).
- **The rebuild no longer blocks the commit.** A script that commits and then
  queries straight away may see the previous build until the background one
  finishes. `neuralmind init-hook . --sync` keeps the foreground rebuild.
- Re-run `init-hook` after moving or reinstalling NeuralMind so the hooks
  name the new path; until then they fall back to PATH.
- No index format change.
- A project with an unused `graphify-out/graph.json` prints a notice on every
  build until you run `neuralmind build . --archive-graphify` or set
  `graph_source`.
- `neuralmind health` and `doctor` behave as before unless you set
  `stale_after` or pass `--stale-after`. `health --json` gains
  `stale_after_seconds` and `behind_seconds`, and a `catching_up` status that
  exits 0.
- The first build after upgrading prints synapse totals without a change;
  later builds show the change since the previous one.
- `eval --synapse-ab` is opt-in; a plain `neuralmind eval .` and its history
  rows are unchanged.
- Under Hermes, each `read_file` inside the project starts one short
  background NeuralMind process, as each edit already did.
- `.neuralmind/metrics/` grows by one small line per query (30 days kept,
  10 MB a day at most, as before). Fields a query doesn't record (tool calls,
  retrieval reuse) are no longer shown as zeros in `neuralmind metrics`.

## Reproduce

```bash
pytest tests/test_init_hook_lifecycle.py -v
pytest tests/test_usage_metrics.py tests/test_metrics.py tests/test_mcp_security.py -v
pytest tests/test_index_freshness.py -k "graphify or StaleAfter or Health" -v
pytest tests/test_cli_exit_codes.py -v
python scripts/mcp_stdio_smoke.py
pytest tests/test_measurement_v450.py -k "synapse_ab or SynapseAB" -v
pytest tests/test_hermes_plugin.py -k read -v
pytest tests/test_hooks.py -k read_activity -v
pytest tests/test_site_claims.py -v

# FIPS-mode hosts: the static check, then the whole suite under the provider
pytest tests/test_fips_hash_usage.py -v
bash scripts/setup_fips_openssl.sh ~/.cache/openssl-fips
OPENSSL_CONF=~/.cache/openssl-fips/openssl-fips.cnf \
  OPENSSL_MODULES=~/.cache/openssl-fips pytest tests/
```

The end-to-end tests drive real git with a fake `neuralmind` that records its
calls, a PATH that cannot find it, and a deliberately slow build: git returns
before the build ends, each new trigger rebuilds, a file checkout doesn't, a
burst of three commits costs two builds, a dead build's lock is cleared, and a
worktree whose `.neuralmind/` a session hook created is left alone while the
main checkout rebuilds.

## Related

- #630 — the field report this release fixes
- #316 — worktrees and NeuralMind state
- [CLI reference: `init-hook`](../wiki/CLI-Reference.md#init-hook)
- [Branch-isolated memory](../use-cases/branch-isolated-memory.md)
- [Does NeuralMind earn its place on your repo?](../use-cases/does-it-earn-its-place.md) — replay past incidents as gold questions, and A/B the learned layer
