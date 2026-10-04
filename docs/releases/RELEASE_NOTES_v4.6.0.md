# NeuralMind v4.6.0 — wired in, or gone

**Type:** Minor release | **Theme:** what the docs describe, the product does

The v4.3.4 public-copy pass checked every claim against the code and found five
features that existed as modules but weren't connected to the running product.
The site, README and wiki relabelled them "not yet wired in" or "roadmap".
v4.6.0 settles each one: three are wired in, one is deleted, and one is rebuilt
and stays on demand.

| Feature | Before (v4.5) | Now (v4.6) |
|---|---|---|
| **Read dedup** (`read_dedup.py`) | Not imported anywhere | A repeat read of an unchanged file comes back as a short stub (Claude Code) |
| **Co-access edges** (`graph_traversal.py`) | Not imported; called a store method that doesn't exist | **Deleted** — queries already reinforce what they retrieve together |
| **Decision invalidation** (`InvalidationEngine`) | Exercised only by tests; decisions went stale only by hand | Runs after every commit through the `init-hook` post-commit hook |
| **Team governance** | Scope and weight threshold stored and audited, never enforced; `remove-edge` only logged; `list-shared` printed `[]` | Enforced by `memory publish`; `remove-edge` removes and retracts; `list-shared` lists; imports and reviews audited |
| **Cognition loop** | On demand; its own SQL deleted most learned memory | Rebuilt on the store's own decay; still on demand, now safe for cron |

It also fixes decision search, which needed every word of a query to match
(section 6).

## 1. Read dedup — a repeat read becomes a stub

When your agent reads a file it already read in this session, and the content
hasn't changed, the Read hook replaces the repeat with this:

```
[neuralmind read-dedup] auth/session.py is unchanged since you read it at 14:03:22 in this session, so that earlier result is still current and this repeat read was shortened. If the earlier result is no longer in your context, read the file again: the next read returns it in full.
```

It uses Claude Code's PostToolUse `updatedToolOutput`, which replaces a tool
result before the model sees it. The replacement keeps the Read tool's own
output shape (`{"type": "text", "file": {...}}`, only the text swapped), and
Claude Code ignores a replacement that doesn't match that shape and delivers
the original read. Read dedup is the only hook action that replaces a tool
result; everything else in the hook block only adds context or writes state.

What counts as a repeat, and what keeps it safe:

- **Same session, same agent.** Reads are keyed on the hook payload's
  `session_id` and `agent_id`. A subagent's reads never count for the main
  conversation, or the other way round, and two sessions in one repo never
  share reads. A payload without a session id is never deduped.
- **Same text, same range.** The SHA-256 of exactly what the Read returned,
  plus its `offset` / `limit` / `pages`. Any edit, or another range of the
  file, is a new read.
- **Never two stubs in a row.** After a stub, the next read of that file goes
  through in full. An agent whose earlier copy has left its context gets the
  file back by reading it again.
- **Context resets reset it.** The `session-start` hook (new, resumed,
  cleared or compacted session) and the `pre-compact` hook forget the
  session's reads.
- **Recent reads only.** A full read more than an hour old doesn't count.
- **Big reads only.** Reads under 2,000 characters are never stubbed; the stub
  is about 350.

Where it applies: projects that already have a `.neuralmind/` directory (a
globally installed hook doesn't create one in every repository it sees), with
the hooks from `neuralmind install-hooks`. Off with `NEURALMIND_READ_DEDUP=0`;
also off under `NEURALMIND_BYPASS=1` and `NEURALMIND_NO_LEARN=1` (which
promises the hooks write nothing). State lives in `.neuralmind/read_cache.db`.

**Not benchmarked yet**, so these notes quote no token figure. The savings
depend on how often your sessions re-read large unchanged files.

The v3.13 description also mentioned "preloading related files". That part was
never built, and putting extra file contents into context is the opposite of
what read dedup is for, so it's dropped rather than deferred.

## 2. Co-access edges — removed

`graph_traversal.py` described edges reinforced "when files appear together in
query results". Every query already does that: `reinforce_from_query`
strengthens the edges between the nodes a query returns together, in the
namespaces recall reads. The module would have written a second, file-level
copy into a `traversal` namespace that no recall path ever read. Its
`get_related_files` called a `SynapseStore` method that doesn't exist, and its
decay multiplied weights by a negative factor. Wiring it in would have
double-counted learning into a namespace nothing reads, so it's deleted.

## 3. Decisions go stale when a commit changes their files

`neuralmind init-hook .` now installs a post-commit hook that runs
`neuralmind decisions scan` before rebuilding the index. When a decision went
stale, the commit says so:

```
$ git commit -m "Switch sessions to Redis"
[neuralmind] 1 decision(s) marked STALE by commit 3f9c2ab:
  - Sessions live in Postgres (5b1e0c7a-…) — commit 3f9c2ab changed auth/session.py since this decision was recorded
  Review: neuralmind decisions audit --stale   Still valid? neuralmind decisions restore <id>
[neuralmind] Rebuilding neural index...
```

The rule is the engine's, deliberately conservative: **any** change to a file a
decision names marks it STALE. There's no diff analysis. Two exemptions keep a
fresh decision from going stale on the commit that carries it:

- a decision anchored to the new commit itself is left alone;
- a decision whose files the commit stores exactly as the decision saw them
  stays ACTIVE. Recording (or amending, or restoring) a decision fingerprints
  each affected file with its git blob id, the way `git add` would store it;
  when every changed file the decision names matches its fingerprint, the
  commit carries the code the decision describes. Edit `auth.py`, record why,
  commit, as quickly as you like: the decision survives. Edit `auth.py` again,
  before or after that commit: it goes STALE. Decisions recorded before
  v4.6.0 have no fingerprints, so any change to their files marks them STALE.

The scan diffs the new commit against its first parent, so a merge commit
counts everything it brought in. A rename counts both the old and the new
path. A project in a subdirectory of its repository, or in a linked
worktree, works too: `init-hook` installs into the repository's hooks and
names the project by its path from the repository root (one NeuralMind
project per repository's hooks). Dependent decisions cascade, and the reason is kept on each decision
(`Marked STALE: commit 3f9c2ab changed auth/session.py after this decision was
recorded` in its evidence).

The PreToolUse stale-decision guard now shows that reason, the decision's full
id, and how to re-anchor one that still holds:

```
[neuralmind stale-guard] 1 decision(s) governing auth/session.py are no longer ACTIVE. Their rationale may not hold — verify before relying on them:
- [STALE] Sessions live in Postgres (id 5b1e0c7a-…, confidence 0.90, updated 2026-10-03): … — commit 3f9c2ab changed auth/session.py since this decision was recorded
If a STALE decision still holds after you check the code, `neuralmind decisions restore <id>` re-anchors it to HEAD.
```

- **Existing checkouts:** re-run `neuralmind init-hook .` to get the new
  post-commit block (it replaces the old one in place).
- **Run it by hand:** `neuralmind decisions scan .` (`--json`, `--quiet`). It
  never creates a decision store in a project that has none, and always exits 0.
- **Limits:** pulls, rebases and `git merge` without a manual commit don't run
  post-commit hooks, so a decision whose files changed only in pulled commits
  stays ACTIVE until one of your own commits touches them. Files are matched by
  exact path (relative or absolute); a decision that names a directory isn't
  matched by changes inside it.
- **Off:** `NEURALMIND_DECISION_SCAN=0`.

## 4. Team governance is enforced, not just recorded

Governance applies once an operator has set it up: `neuralmind onboarding`, or
any `neuralmind team governance` command that saves settings, writes the
tier2 config. Without that config, nothing below changes anything.

**`neuralmind memory publish` honours the policy:**

| `publishing_scope` | What `memory publish` writes |
|---|---|
| `personal` | Nothing. It refuses, exits 1 and names the admin command that changes the scope |
| `shared` | Only the team baseline (the `shared` namespace). Your personal memory stays on your machine |
| `both` (default) | Personal + shared, as before |

Synapse edges below `weight_threshold` (default 0.1) are left out of the bundle
and counted in the output. Transitions use a different scale and aren't
weight-filtered. The bundle's provenance records the policy it was published
under. If the governance config exists but can't be read (unreadable, malformed
YAML, or an invalid scope, for example), publish refuses rather than publishing
ungoverned memory.
`team governance set-governance-enabled false` turns these gates off; events
are still audited.

**`team governance remove-edge SOURCE TARGET`** stops sharing an association:

- it deletes the edge (and transitions between the two nodes) from the
  project's `shared` memory and from the review queue;
- it drops the pair from `.neuralmind-team-memory.json` and lists it under a
  new `retracted` key. That changes the bundle's content hash, so each
  teammate's next session imports the update and deletes the pair from their
  `shared` memory too;
- no later `memory publish` re-adds a retracted pair, even from someone's
  personal memory;
- commit the bundle to share the removal.

The bundle is written first, atomically. If that write fails, nothing has
changed. If the local store update fails after it, the bundle already carries
the retraction and the next session's import finishes it. A failed removal is
audited too.

Admin-only; a non-admin gets `Permission denied` and exit 1. **Breaking:** the
command now takes the two nodes (`remove-edge SOURCE TARGET [--project PATH]`)
instead of one `edge_id`. The old form never removed anything.

**`team governance list-shared [--project PATH] [--json]`** lists the
project's shared-memory associations, strongest first. It used to print `[]`.

**Audited:** publishes (including refused ones), imports of a teammate's
bundle, `memory review-approve` / `review-reject`, and removals now write to
the hash-chained audit log, alongside the configuration changes they already
covered. Appends are serialized across processes (a lock file beside the log),
so hooks and commands writing at the same moment can't fork the hash chain.
`neuralmind team audit verify` checks the chain;
`neuralmind team audit export --format csv --output audit.csv` hands it to an
auditor. The actor is `NEURALMIND_ACTOR_EMAIL`, else the repository's
`git config user.email`, else the OS user.

## 5. The cognition loop, rebuilt — and still on demand

Before v4.6.0, `neuralmind cognition-loop` ran its own SQL, and it destroyed
learned memory:

- a linear decay over every namespace, including shared team memory, ran up to
  nine times per pass, so most edges idle for more than about two days were
  deleted;
- the same 25 recent queries were replayed into the unread `traversal`
  namespace nine times per pass, and their clusters were promoted to long-term
  status without the repeated use that status requires;
- session summaries older than 30 days were deleted.

It now runs one idempotent pass on the machinery the hooks already use:

1. **Decay** — the synapse store's half-life decay: 30 days for personal and
   branch memory, 60 for shared, 1 for ephemeral, with long-term edges kept at
   their floor. It charges only the time since the previous decay, so running
   it often never decays anything twice.
2. **Read-dedup cleanup** — rows untouched for a day are dropped.

```bash
neuralmind cognition-loop .          # one pass
neuralmind cognition-loop . --json   # edges_pruned, edges_remaining, transitions_*, read_cache_pruned
```

**No timer ships, on purpose.** Claude Code's `session-start` hook already
decays at every session start, and `neuralmind watch` decays every 10 minutes.
The pass is for setups that run neither, such as an MCP-only client. It's safe
for cron:

```cron
0 * * * * cd /path/to/repo && neuralmind cognition-loop . >/dev/null
```

Hub normalization stays with the `pre-compact` hook: it scales a hub's edges
down on every call, so a frequent schedule would compound it. If you ran the old
pass, its leftover rows are inert; `neuralmind memory reset --namespace
traversal` removes them.

## 6. Decision search answers questions

Decision search required every word of the query, so `neuralmind decisions query`
found a decision for "sqlite wal" but not for "how do we handle sqlite wal?",
and agents send questions.

- **Any word of the query can match.** Common words such as "how" and "the"
  are ignored, and decisions matching more of the words, and rarer ones, rank
  first. This covers `decisions query`, the `neuralmind_query_decisions` and
  `neuralmind_memory_search` MCP tools, and the LIKE fallback used when SQLite
  lacks FTS5. A question nothing answers can still return partial matches, so
  check the titles.
- **Status filters are case-insensitive**, and `ALL` returns every status
  (over MCP, the advertised `"all"` used to match nothing). The CLI's
  `--status` also accepts `INVALIDATED`. An unknown status is an error,
  `invalid_request` over MCP, instead of an empty result.
- **`neuralmind decisions eval` leaves your decisions alone.** It used to delete
  the project's `.neuralmind/memory.db` and leave synthetic decisions with the
  author `eval-harness` behind; it now runs on a scratch store. The
  [Memory Layer wiki](../wiki/Memory-Layer.md#eval-harness) shows how to retire
  any it left. `--format md` no longer crashes.
- **`neuralmind decisions eval --queries FILE`** scores search against
  questions with known answers: recall@k and MRR as mean and range per query
  kind, with every miss and false positive listed. The committed query set and
  its measured results are in the
  [Memory Layer wiki](../wiki/Memory-Layer.md#eval-harness).
- **MCP errors say what to do.** A missing index is `code: "index_not_built"`
  with a hint to call `neuralmind_build`, not `security_denied`;
  `security_denied` carries `reason: "rbac"` or `"rate_limit"`. See
  [Troubleshooting](../wiki/Troubleshooting.md).

## What the agent actually sees post-install

| Agent | Before (v4.5) | After (v4.6) |
|---|---|---|
| **Claude Code** (hooks + MCP) | Every re-read of a file arrives in full. The stale-guard fires only on decisions someone invalidated by hand | A repeat read of an unchanged file arrives as a stub, with the next read always full. The stale-guard also fires after commits change a decision's files, and shows why, the id, and `decisions restore <id>` |
| **Cursor / Cline / Continue** (MCP) | Decision tools report what was invalidated by hand | Decisions also go STALE on commit (git hook), so `neuralmind_audit_decisions` and `neuralmind_query_decisions` reflect it. No read dedup (no PostToolUse hooks) |
| **Generic MCP client** | Same as above | Same as above |
| **git** (after `neuralmind init-hook .`) | post-commit rebuilt the index | post-commit first marks stale decisions and prints them, then rebuilds |
| **Team admins** | Scope, threshold and `remove-edge` recorded only | Enforced on publish; removals retract through the bundle; every team-memory event audited |
| **Any agent searching decisions** (MCP or CLI) | A question found nothing unless every word appeared in one decision; `status: "all"` matched nothing; a missing index came back as `security_denied` | Any word can match and fuller matches rank first; `ALL` works in any case; a missing index is `index_not_built`, with a hint to build |

## Upgrade notes

- **Re-run `neuralmind init-hook .`** in each checkout to get the decision scan.
- **`neuralmind team governance remove-edge`** takes `SOURCE TARGET`.
- **`memory publish` may publish less** under a governance config: weak edges
  below the threshold, or nothing under scope `personal`.
- **`cognition-loop --json` fields changed:** `steps_taken`,
  `edges_reinforced`, `edges_decayed`, `clusters_consolidated`,
  `summaries_pruned` and `read_cache_cleared` are gone; `edges_remaining`,
  `transitions_pruned`, `transitions_remaining`, `read_cache_pruned` and
  `skipped` are new. Its `NEURALMIND_COGNITION_*`, `NEURALMIND_DECAY_RATE`,
  `NEURALMIND_PRUNE_DAYS` and `NEURALMIND_SYNTHESIS_MIN_CLUSTER` variables are
  no longer read.
- **MCP error codes:** a missing index returns `index_not_built` instead of
  `security_denied`, and `security_denied` now carries `reason` (`rbac` or
  `rate_limit`). A client that matched `security_denied` to mean "not built"
  needs updating.
- **New switches:** `NEURALMIND_READ_DEDUP=0`, `NEURALMIND_DECISION_SCAN=0`.
- **New file:** `.neuralmind/read_cache.db` (per machine, never committed).

## Related

- Use cases: [Keep decision memory honest across commits](../use-cases/decision-memory-across-commits.md) · [Govern what your team's agents share](../use-cases/govern-team-memory.md)
- CLI reference: [`decisions scan`](../wiki/CLI-Reference.md#decisions-scan-v460), [`decisions eval`](../wiki/CLI-Reference.md#decisions-eval), [`cognition-loop`](../wiki/CLI-Reference.md#cognition-loop), [`team governance`](../wiki/CLI-Reference.md#team-governance), [hooks](../wiki/CLI-Reference.md#install-hooks)
