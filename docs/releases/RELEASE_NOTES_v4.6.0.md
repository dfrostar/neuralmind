# NeuralMind v4.6.0 — one keyword index for docs and code, and the documented features wired in

**Type:** Minor release | **Themes:** retrieval ranking, measured (sections 1–5) · what the docs describe, the product does (sections 6–10)

## Retrieval ranking, measured

v4.5.0 gave every project a way to measure retrieval on its own questions.
v4.6.0 pointed that measurement at NeuralMind's own ranking: six candidate
changes to how the four L3 search slots are spent, 30 questions on each of six
repositories — pre-registered and committed for the five public repositories,
plus a private 383-file repository — and a keep rule written down before the
first run. One change passed it.

1. **One BM25 index for docs and code, on by default.** Mean hit@5 across the
   six repositories went from **72.8% to 79.4%** (MRR 0.589 → 0.654).
2. **The public 4-repo benchmark's gold-file recall went from 93.75% to 95%**,
   at 46–263× fewer tokens than pasting every source file.
3. **Five more ranking changes (six flags — the intent pool is a variant of
   the intent rules) were measured and not kept.** They ship off by default,
   behind flags, with the numbers that sank them.

**Evidence:** reproducible on demand, not a CI gate. The raw output is
committed in [`bench/retrieval/`](https://github.com/dfrostar/neuralmind/blob/main/bench/retrieval/README.md);
`pip install -e . tiktoken`, then
`NEURALMIND_ORT_THREADS=1 python -m evals.retrieval.run --public-benchmark`
re-runs it. The question sets for the five public repositories are
pre-registered and committed; the private 383-file repository uses its own
local question set, which readers can't re-run. On the five public
repositories alone, mean hit@5 went from 75.3% to 80.7% (MRR 0.614 → 0.664).

Run `neuralmind build` once after upgrading: the build writes the new index,
and a query never builds anything.

## Wired in, or gone

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

## 1. One BM25 index for docs and code

L3 fuses vector search with a BM25 keyword list by Reciprocal Rank Fusion. On
the default turbovec backend, that keyword index held only **document** nodes.
A question whose words appeared in a README or a wiki page gave the docs a
second signal that code never got — so on "how does X work" questions a doc
kept taking a slot the implementation should have had.

- `neuralmind build` now writes `.neuralmind/bm25_unified_index.json`: every
  node — doc text, symbol names, file paths, docstrings — in one BM25 index.
  Queries fuse that instead of the docs-only list.
- The ChromaDB backend's BM25 index already covered every node; the unified
  index makes both backends behave the same.
- **Cost:** one BM25 lookup per query, and 1.1% more context tokens on
  average across the six repositories.
- **Opt out:** `NEURALMIND_BM25_UNIFIED=0` restores v4.5.0's docs-only keyword
  list.

Against v4.5.0 — hit@5 / MRR, 30 questions per repository
([`bench/retrieval/vs-v4.5`](https://github.com/dfrostar/neuralmind/blob/main/bench/retrieval/vs-v4.5/report.md)):

| Repository | v4.5.0 | v4.6.0 (unified BM25) |
|---|---:|---:|
| `requests` | 90% / 0.76 | 87% / 0.75 |
| `click` | 93% / 0.69 | 93% / 0.79 |
| `flask` | 73% / 0.63 | 83% / 0.71 |
| `rich` | 80% / 0.71 | 80% / 0.60 |
| `neuralmind` (this repository, docs indexed) | 40% / 0.27 | 60% / 0.47 |
| a private 383-file repository | 60% / 0.47 | 73% / 0.60 |
| **mean** | **72.8% / 0.589** | **79.4% / 0.654** |

### The losses, published

- **`requests` loses one question** (hit@5 90% → 87%). The keep rule says no
  repository drops by more than one question; it is still a drop.
- **`rich`'s MRR falls from 0.71 to 0.60.** Its hit@5 holds at 80%, but the
  gold file ranks lower.
- **`click` has a new public-benchmark miss.** `echo-util` (gold `utils.py`)
  now retrieves `termui.py` and `core.py`, and `click` fell from 100% to
  85.71% on the public benchmark. The benchmark's total still rose, from
  93.75% to 95%.
- **The private repository's target is not met.** The work started from its
  60% hit@5; the target was hit@5 ≥ 80% and MRR ≥ 0.65. v4.6.0 reaches
  73% / 0.60.

## 2. `query --explain` says which intent L3 ranked with

L3 re-weights its hits by query intent — a `docs` question multiplies doc hits
by 2.0 and code hits by 0.7 — and nothing showed which intent a query got.
`--explain` now prints it, and how it was decided:

```
  Query intent     : docs (by classifier)
```

- `classifier` — the v3.9.0 pattern classifier decided.
- `keywords` — the classifier called the question `hybrid`, so the older
  keyword count decided.
- `question shape` — the opt-in intent rules (`NEURALMIND_INTENT_RULES=1`)
  matched, e.g. `code (by question shape)`.

The `Top search hits` list now shows each hit's label and file; it printed raw
node ids before.

## 3. How the decision was made — `python -m evals.retrieval.run`

A multi-repo retrieval eval ships in the source tree, with its raw output
committed in [`bench/retrieval/`](https://github.com/dfrostar/neuralmind/blob/main/bench/retrieval/README.md).

- **Pre-registered questions.** 30 per repository for `requests`, `click`,
  `flask` and `rich` (at the public benchmark's pinned commits) and for this
  repository, committed in `evals/retrieval/questions/` before any ranking
  change was tried. A sixth repository — a private 383-file repository — came
  in through `--private PATH` and is reported only in aggregate: no
  per-question ranks, no question text.
- **The keep rule**, fixed before the runs:
  - mean hit@5 across repositories goes up, and it goes up on at least 3;
  - no repository drops by more than one question;
  - average context tokens rise by at most 10%;
  - the public 4-repo benchmark's gold-file recall doesn't drop.
- **Read-only, one scorer.** Every flag configuration runs through the same
  scorer as `neuralmind eval`, so the harness's hit@5 on a repository is the
  number `neuralmind eval .` prints there (for this repository, with its docs
  indexed — the harness overrides its `.neuralmindignore`).
- **Three rounds.** Round 1 measured the five work items against v4.5.0, with
  BM25 switched off as a reference. Round 2 tried three variants designed after
  seeing round 1 — the unified index among them; the public benchmark's 40
  queries, written long before, are the holdout that keeps that honest. Round 3
  re-ran every remaining item on top of the new default
  ([`bench/retrieval/on-v4.6`](https://github.com/dfrostar/neuralmind/blob/main/bench/retrieval/on-v4.6/report.md)).
- **Contamination, found and fixed.** The public benchmark queries with
  learning on, and it was running against the same pinned clones the eval
  used: its queries trained the eval's indexes, and the flags-off baseline
  moved between runs. Now every run builds fresh indexes, each public-benchmark
  run gets its own fresh copy of the clones, and the baseline runs again after
  every configuration — the report says whether it reproduced. In both
  committed runs it reproduced exactly on all six repositories.

## 4. Measured and not kept

Each stays available behind its flag, off by default:

| Flag | What it does | Why it wasn't kept |
|---|---|---|
| `NEURALMIND_L3_PER_FILE=2` | at most N L3 hits per file | +1.1 pts mean hit@5, 2 repos up, none down on hit@5, but mean MRR fell 0.654 → 0.629 (`requests` 0.75 → 0.69, `flask` 0.71 → 0.65); public recall 96.25% — the rule needs 3 repos |
| `NEURALMIND_DOC_HANDOFF=1` | a doc hit that names code pulls that code in | helps only where docs name code (private +3, `neuralmind` +1 question vs v4.5.0); a wash on top of v4.6.0 |
| `NEURALMIND_HUB_DAMPEN=1` | down-weights files returned far more often than chance | cost `click` 3–4 questions |
| `NEURALMIND_INTENT_RULES=1` | "how does X… / where is X… / which X is…" → code intent | moves MRR (0.654 → 0.672), never hit@5: it only re-orders the 4 hits L3 already chose |
| `NEURALMIND_INTENT_POOL=1` (with `NEURALMIND_INTENT_RULES=1`) | intent ranks all 10 candidates | `click` −8 questions, public recall 83.75% (vs v4.5.0) |
| `NEURALMIND_BM25_CODE=1` | a separate code-only keyword list | `requests` −3 (vs v4.5.0); `rich` −4, `click` −3 (on v4.6.0) |

One finding is worth keeping even though its fix wasn't. The intent
classifier — still the default, since the intent rules weren't kept — sends
many "how does X…" and "where is X…" behaviour questions to **docs** intent,
which multiplies doc hits ×2.0 and code ×0.7. Four such shapes are now
regression tests that the intent rules must send to code
([`tests/test_l3_slots_v460.py`](https://github.com/dfrostar/neuralmind/blob/main/tests/test_l3_slots_v460.py)): "How does
the session pick which adapter sends a request?", "Where is the redirect
followed after a POST?", "Which hook runs before a request is sent?" and "How
does the cache avoid storing the same response twice?". Sending questions like
these to code intent instead only re-orders the four hits L3 already chose,
which is why the intent rules moved MRR and never hit@5.

## 5. The public benchmark, regenerated

[`bench/public/results.json`](https://github.com/dfrostar/neuralmind/blob/main/bench/public/results.json) was regenerated
on v4.6.0 (tiktoken o200k_base; reproduce with
`NEURALMIND_ORT_THREADS=1 python -m evals.public.run`):

- **95% gold-file recall**, the query-weighted mean over all 40 queries (was
  93.75%), **85.71–100% per repo** (was 85–100%):
  `click` 85.71%, `flask` 95%, `requests` 96.43%, `rich` 100%.
- **92.5% found-rate** — 37 of 40 (was 90%).
- **3 misses of 40** (was 4): `requests` `xfile-status-codes` (partial),
  `click` `echo-util` (new), `flask` `xfile-dispatch-context` (partial).
- **46–263× fewer tokens** than pasting every source file (was 45–261×):
  `requests` 46.6×, `flask` 78×, `click` 121.7×, `rich` 262.1×.
- **`embedding-rag` still leads on recall**, at 98.75% mean. NeuralMind trails
  a bare vector-RAG baseline on findability, as it did before.

## 6. Read dedup — a repeat read becomes a stub

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

## 7. Co-access edges — removed

`graph_traversal.py` described edges reinforced "when files appear together in
query results". Every query already does that: `reinforce_from_query`
strengthens the edges between the nodes a query returns together, in the
namespaces recall reads. The module would have written a second, file-level
copy into a `traversal` namespace that no recall path ever read. Its
`get_related_files` called a `SynapseStore` method that doesn't exist, and its
decay multiplied weights by a negative factor. Wiring it in would have
double-counted learning into a namespace nothing reads, so it's deleted.

## 8. Decisions go stale when a commit changes their files

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

## 9. Team governance is enforced, not just recorded

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

## 10. The cognition loop, rebuilt — and still on demand

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

## What the agent actually sees post-install

### Retrieval ranking (sections 1–5)

- **Code can now win an L3 slot on keywords too**, not only on vector
  similarity — across the eval's six repos mean hit@5 rose 72.8% → 79.4%,
  though `requests` lost a question and `rich`'s gold files rank lower. The
  default intent classifier still treats many "how does X…" questions as docs
  questions; `query --explain` shows which it chose.
- **Learned recall only takes a slot for a file the hits don't already show.**
  Synapse recall swaps the weakest L3 hits for nodes your team co-edits. With
  the stronger keyword ranking, those swaps started trading the only hit from a
  second relevant file for more of the first, and the CI onboarding gate's lift
  went negative: −0.009 on the fixture, where v4.5.0 measured +0.046. Recall now
  skips neighbours from files already in the hits; the gate measures +0.046
  again, and faithfulness on the same fixture moves from −0.001 to +0.027.
- **`neuralmind query --explain` shows the intent** the query was ranked with,
  and why.
- **Nothing changes until `neuralmind build` runs once.** An index built before
  v4.6.0 keeps the docs-only keyword list.

| Agent | Before (v4.5.0) | After (v4.6.0) |
|---|---|---|
| **Claude Code** (MCP + hooks) | `neuralmind_query` ranked L3 with a keyword list only docs were in | Same tool and the same four slots, ranked with one keyword index over docs and code after the next build; hooks unchanged |
| **Cursor** (MCP) | Same as Claude Code | Same change through `neuralmind_query`; `neuralmind_search` (plain vector search) is unchanged |
| **Cline / Continue** (MCP) | Same as Claude Code | Same as Cursor |
| **Generic MCP client** | — | No schema change: same tools, same arguments, re-ranked L3 hits |
| **CI** | `neuralmind eval .` scored v4.5.0 ranking | Same command; run it with and without `NEURALMIND_BM25_UNIFIED=0` to see what v4.6.0 changed on your repo |

### Wired in, or gone (sections 6–10)

| Agent | Before (v4.5) | After (v4.6) |
|---|---|---|
| **Claude Code** (hooks + MCP) | Every re-read of a file arrives in full. The stale-guard fires only on decisions someone invalidated by hand | A repeat read of an unchanged file arrives as a stub, with the next read always full. The stale-guard also fires after commits change a decision's files, and shows why, the id, and `decisions restore <id>` |
| **Cursor / Cline / Continue** (MCP) | Decision tools report what was invalidated by hand | Decisions also go STALE on commit (git hook), so `neuralmind_audit_decisions` and `neuralmind_query_decisions` reflect it. No read dedup (no PostToolUse hooks) |
| **Generic MCP client** | Same as above | Same as above |
| **git** (after `neuralmind init-hook .`) | post-commit rebuilt the index | post-commit first marks stale decisions and prints them, then rebuilds |
| **Team admins** | Scope, threshold and `remove-edge` recorded only | Enforced on publish; removals retract through the bundle; every team-memory event audited |

## Environment variables

| Variable | Default | Effect |
|---|---|---|
| `NEURALMIND_BM25_UNIFIED` | on | One BM25 index over docs and code, written by `build`. `0` restores v4.5.0's docs-only keyword list |
| `NEURALMIND_L3_PER_FILE` | off | `N` caps L3 hits per file (measured at `2`), refilling from the next-best candidates |
| `NEURALMIND_DOC_HANDOFF` | off | `1`: a doc hit that names a code file or symbol brings that code into contention |
| `NEURALMIND_HUB_DAMPEN` | off | `1`: down-weights files returned far more often than chance |
| `NEURALMIND_INTENT_RULES` | off | `1`: "how does X… / where is X… / which X is…" questions get code intent; questions that name a document or ask how to install get docs |
| `NEURALMIND_INTENT_POOL` | off | `1`: intent ranks all 10 candidates instead of re-ordering the four L3 chose; measured with `NEURALMIND_INTENT_RULES=1` |
| `NEURALMIND_BM25_CODE` | off | `1`: a second, code-only keyword list fused by RRF |
| `NEURALMIND_READ_DEDUP` | on | `0`: every re-read of a file arrives in full (no stub) |
| `NEURALMIND_DECISION_SCAN` | on | `0`: the post-commit hook skips the decision scan |

Five more ranking changes (six flags — the intent pool is a variant of the
intent rules) were measured and not kept. Those flags are research settings:
each one lost on the eval above. Measure one on your own repository before turning it on — see
[A/B-test a ranking change on your own repo](https://github.com/dfrostar/neuralmind/blob/main/docs/use-cases/ab-test-a-ranking-change.md).

## Upgrade notes

- **Run `neuralmind build` once.** Read paths never build (v4.4.0), so until a
  build writes `bm25_unified_index.json`, queries keep v4.5.0's keyword list.
  Running `neuralmind eval .` before and after the build shows what the change
  did on your repository.
- **Rankings move.** Expect different top hits on code questions, and note
  `rich`: an MRR can fall while hit@5 holds. If your own eval drops,
  `NEURALMIND_BM25_UNIFIED=0` restores v4.5.0 ranking — and an issue with your
  `neuralmind eval . --report` table helps the next round.
- **The BM25 change needs no API, MCP schema or config-file change.** Its one
  new file is `.neuralmind/bm25_unified_index.json`, rewritten on every build.
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
- **New switches:** `NEURALMIND_READ_DEDUP=0`, `NEURALMIND_DECISION_SCAN=0`.
- **New file:** `.neuralmind/read_cache.db` (per machine, never committed).

## Related

- Use case: [A/B-test a ranking change on your own repo](https://github.com/dfrostar/neuralmind/blob/main/docs/use-cases/ab-test-a-ranking-change.md)
- Use case: [Measure retrieval on your own repo](https://github.com/dfrostar/neuralmind/blob/main/docs/use-cases/measure-retrieval-on-your-repo.md)
- Raw eval output and how to reproduce it: [`bench/retrieval/`](https://github.com/dfrostar/neuralmind/blob/main/bench/retrieval/README.md)
- Public benchmark: [methodology and results](https://github.com/dfrostar/neuralmind/blob/main/docs/benchmarks/public.md)
- CLI reference: [`query`](https://github.com/dfrostar/neuralmind/blob/main/docs/wiki/CLI-Reference.md#query), [`eval`](https://github.com/dfrostar/neuralmind/blob/main/docs/wiki/CLI-Reference.md#eval-v0140-project-eval-v450), [environment variables](https://github.com/dfrostar/neuralmind/blob/main/docs/wiki/CLI-Reference.md#environment-variables)
- Use cases: [Keep decision memory honest across commits](../use-cases/decision-memory-across-commits.md) · [Govern what your team's agents share](../use-cases/govern-team-memory.md)
- CLI reference: [`decisions scan`](../wiki/CLI-Reference.md#decisions-scan-v460), [`cognition-loop`](../wiki/CLI-Reference.md#cognition-loop), [`team governance`](../wiki/CLI-Reference.md#team-governance), [hooks](../wiki/CLI-Reference.md#install-hooks)
