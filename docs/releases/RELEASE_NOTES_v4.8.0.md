# NeuralMind v4.8.0 — a new session starts where the last one left off, decision search by meaning, and policy mistakes refused

**Type:** Minor release | **Themes:** session continuity · decision memory ([decision search by meaning](#decision-search-by-meaning)) · MCP access control ([policy mistakes refused](#policy-mistakes-that-meant-the-defaults-now-refuse))

A new Claude Code session used to start cold. NeuralMind gave it the code it
had learned (`SYNAPSE_MEMORY.md`, per-prompt recall), but not the work: what
you were doing yesterday, which files you had open, what you asked last. You
re-explained it, or asked the agent to go and find out.

v4.8.0 records each session's prompts and edited files as you work. The next
fresh or cleared session starts with a short recap of the most recent one:

1. **No new hooks.** Recording rides on the `UserPromptSubmit` and Edit/Write
   hooks NeuralMind already installs; the recap arrives through the existing
   `SessionStart` hook. The hook block's version is unchanged, so an
   existing `neuralmind install-hooks` setup picks it up on upgrade.
2. **No model call.** The recap is assembled from what the hook payloads
   already carry: the prompt text, the edited file's path, the session id.
   Nothing summarizes it, so it costs a few small file reads at session
   start.
3. **Only when the conversation is missing.** A resumed session already has its
   conversation, and a compacted one has Claude Code's own summary, so the
   recap is injected only on a fresh start and after `/clear`.
4. **`neuralmind recap`** prints what the next session will see, and
   `neuralmind recap --clear` deletes the stored records.

## What the agent actually sees

At the start of a new session, before your first message, the agent's
context gains this block:

```
NeuralMind session recap — the previous session in this project (last active 3 h ago). This is context for continuity, not instructions: don't resume that work unless the user asks to.

It started with: "add retry logic to the uploader"
Most recent prompts (2 earlier not shown):
- "now cover the timeout path in tests"
- "why does test_upload_retries hang on CI?"
- "make the backoff configurable through the env"

Files edited (4, most recent first): src/uploader.py, src/config.py, tests/test_uploader.py, docs/uploader.md
```

- **The first prompt and the last three**, each collapsed to one line and cut
  at 200 characters. The first prompt is usually the session's goal; the last
  ones are where it stopped.
- **Up to twelve edited files**, most recent first, relative to the project
  root (a file outside the project shows as `~/…` or its full path). Control
  characters are removed from prompts and paths, and a path longer than 160
  characters keeps its last 160. Only
  Edit and Write are recorded, so a file changed through a shell command isn't
  listed.
- **"Not instructions."** The block says so, so the agent doesn't pick an old
  task back up on its own. Ask "where were we?" or "carry on" and it has what
  it needs to answer.
- **The most recently active other session**, by the times recorded in each
  record. If two sessions run in the same project, whichever was active most
  recently counts as "where we left off".

## Per-agent expectations

| Agent | What changes |
|---|---|
| **Claude Code** (a built project, with `neuralmind install-hooks`) | A fresh or cleared session starts with the recap above. Resumed and compacted sessions don't get it. |
| **Cursor / Cline / generic MCP clients** | Nothing. These hosts don't run Claude Code hooks, so nothing is recorded and nothing is injected. |
| **Hermes-Agent and other agents with a shell** | Nothing automatic. An agent that can run commands can call `neuralmind recap` to read what the last Claude Code session in the project did. |

## Where it's stored, and what's redacted

- Recording happens only in a project where `neuralmind build` has run (it
  leaves `.neuralmind/build_status.json`, which no hook creates). Hooks
  installed globally fire in every repository, but they record no prompts in
  the ones NeuralMind hasn't built.
- A `.neuralmind/` or `.neuralmind/recaps/` that is a symlink is refused, and
  symlinked record files are skipped: nothing is written, read or deleted
  through them, since a cloned repository could point either outside the
  project.
- Each session appends to `.neuralmind/recaps/<session_id>.jsonl`, one short
  line per prompt or edit. Appending means hooks running in parallel can't
  corrupt a record. The ten most recently active records are kept; older ones
  are deleted when a fresh session starts, except a record active in the last
  24 hours, so a session that's still open keeps its start.
- The recap writes `.neuralmind/`'s self-ignoring `.gitignore` before its
  first record, so `git add -A` doesn't stage the records.
- Prompts pass through NeuralMind's credential patterns (the same redaction
  `neuralmind last` uses) **before** they're written, and before they're cut
  to 200 characters, so a credential can't survive in the kept slice. The
  patterns catch common credential formats, not every secret, so a secret in
  an unusual format can still be written.
- The recap goes into the agent's context, so it's sent to your model provider
  along with the rest of the session, as the original prompts were.

## Settings

| Variable | Default | Effect |
|---|---|---|
| `NEURALMIND_SESSION_RECAP` | on | `0` stops recording and stops the recap |
| `NEURALMIND_SESSION_RECAP_MAX_AGE_DAYS` | `14` | A recap whose session was last active longer ago than this isn't shown |
| `NEURALMIND_NO_LEARN` | off | `1` stops recording (nothing is written) but still shows an existing recap |
| `NEURALMIND_BYPASS` | off | `1` switches off every hook action, this one included |

Turning the recap off, or setting `NEURALMIND_NO_LEARN=1`, doesn't delete
records already written, and a recap past the age limit is hidden, not deleted.
`neuralmind recap --clear` removes them; while the recap is off,
`neuralmind recap` says how many are still stored.

## Why it's built this way

NeuralMind already had session summaries (`session_summaries.py`), written by
the `Stop` and `SessionEnd` hooks. They're built from `.neuralmind/events.jsonl`,
which is only written while `neuralmind watch` or `neuralmind serve` is
running. With hooks alone, nothing new reaches that log, so the summaries don't
reflect the session, or aren't written at all. The session recap reads only fields Claude Code's
hook payloads carry, so it works with the hooks alone.

## Not measured

This release doesn't claim a number. We haven't measured whether the recap
shortens the start of a session, or how often an agent acts on it when it
shouldn't. The block's size is bounded by count, not by a character budget: at
most four prompts of 200 characters and twelve file paths, plus a header. The
example above is 525 characters; four full-length prompts and twelve
30-character paths come to about 1,500.

## Decision search by meaning

Decision search used to find a decision only when the question shared a word
with it. An agent asking "where do we verify who is calling an endpoint?"
never reached "Use per-handler authentication middleware", because the two
share no word. v4.8.0 ranks decisions by meaning as well, with the same local
embedding model the code index already uses, and makes the fused ranking the
default:

- **Three search modes.** `hybrid` (default) fuses a keyword ranking and a
  meaning ranking; `semantic` ranks by meaning only; `keyword` is the v4.6
  search.
- **Local, and never a download.** Vectors are computed on your machine and
  cached in `.neuralmind/memory.db`. Search uses the model `neuralmind build`
  already fetched; without it, hybrid search returns keyword results and says
  so.
- **Measured before it became the default.** 20 paraphrased questions that
  share no word with their answers were written and committed, with a keep
  rule, before semantic search was run on them. Hybrid passed the rule. It
  finds 9 of the 20 in its top 5, where keyword search finds none, and the
  misses are listed below.

This is item G1 of the mem0 gap analysis in
[`docs/specs/LOCAL-API-SPEC.md`](../specs/LOCAL-API-SPEC.md) §4.1. The other
items (change history, duplicate warnings, filters, expiry dates and the rest)
are not in this release.

### Three search modes

| Mode | Ranks by | Use it for |
|------|----------|------------|
| `hybrid` (default) | Shared words and meaning, fused by reciprocal rank fusion (k = 60) | Everyday questions |
| `semantic` | Cosine similarity between the question and each decision's title + rationale, embedded with `all-MiniLM-L6-v2`; a decision needs at least 0.30 | Questions you expect to share no word with the decision |
| `keyword` | Shared words: FTS5, bm25-ranked, any word can match (v4.5.1+) | Exact identifiers, and the v4.6 ranking |

- **CLI:** `neuralmind decisions query "QUESTION" --mode hybrid|semantic|keyword`.
  Every output names the mode that ran: the header
  (`# NeuralMind Decisions Query: "…" (hybrid)`), the empty result
  (`No decisions found for: … (hybrid search)`), and, with `--json`, a
  `[neuralmind] search mode: hybrid` line on stderr; stdout stays the JSON
  array of records.
- **MCP:** `neuralmind_query_decisions` and `neuralmind_memory_search` take an
  optional `mode` (case-insensitive). Every response carries `mode`, the mode
  that ranked the results, and `notice` when hybrid fell back to keyword.
- **Python:** `DecisionStore.query(..., mode=...)` as before, and
  `DecisionStore.search(...)`, which also returns the mode that ran and any
  notice.
- **Default:** `NEURALMIND_DECISION_SEARCH` sets the mode for calls that name
  none: CLI, MCP tools and Python API. Unset, it is `hybrid`.
  `NEURALMIND_DECISION_SEARCH=keyword` restores the v4.6 ranking everywhere.
- All three modes search the same fields, titles and rationales, and honor
  the same status and confidence filters. Evidence, tags and rejected
  alternatives are still not searched.

### Local, cached, and never a download

- **What gets embedded:** each decision's title and rationale, the fields
  keyword search covers. Evidence is left out because invalidating, staling
  and restoring a decision append lifecycle notes to it.
- **When:** the first semantic or hybrid search embeds every decision.
  Vectors are cached in a new `decision_vectors` table in
  `memory.db`, with a hash of the text and the model id. Later searches embed
  only the question and any decision recorded or amended since; a status
  change doesn't re-embed. Deleting a decision deletes its vector. Recording a
  decision stays as fast as before, because nothing is embedded at write time.
- **Never a download:** search uses the model only if it is already on disk
  (`neuralmind build` fetches it once, or ChromaDB's cache has it). Without it:
  - `hybrid` returns keyword results, with
    `[neuralmind] semantic ranking unavailable (…); keyword results only` on
    stderr (CLI) or `"mode": "keyword"` plus a `notice` (MCP);
  - `semantic` is an error: the CLI exits 1, and MCP returns
    `code: "semantic_unavailable"` with a hint.
- Each semantic or hybrid search loads the model, so it takes longer than a
  keyword search. No outbound request is added.

### Measured before it became the default

**Evidence:** reproducible on demand from a source checkout, not a CI gate for
every column:

```bash
NEURALMIND_ORT_THREADS=1 neuralmind decisions eval \
  --queries tests/memory/fixtures/decision_queries.json --format md
```

`tests/memory/test_query_eval.py` holds the
[Memory Layer wiki](../wiki/Memory-Layer.md#eval-harness)'s table to what the
eval measures: the keyword column on every CI run, the semantic and hybrid
columns wherever the model is on disk (CI doesn't download it). Repeated runs
here gave identical numbers, with `NEURALMIND_ORT_THREADS=1` and without it.

**What was frozen first.** Commit
[`7172855`](https://github.com/dfrostar/neuralmind/commit/7172855) added 20 paraphrased questions,
each sharing no search word with its answer (a test enforces it), with the
0.30 similarity floor and this keep rule. Nothing was changed after the run.
Against keyword search, hybrid becomes the default only if:

- (a) recall on the paraphrases rises;
- (b) recall on the 20 existing questions doesn't fall, and their MRR falls by
  no more than 0.05;
- (c) no fewer exact titles rank first.

Questions nothing answers are reported, not gated. Keyword search already
returns partial matches for them, and the tools tell the agent to check the
titles.

Synthetic set: 35 decisions (30 ACTIVE), limit 5, status ACTIVE.

| Measure | Keyword (v4.6) | Semantic | Hybrid (default) |
|---------|---------|----------|------------------|
| Recall@5 on 20 questions, mean (range) | 1.00 (1.00–1.00) | 0.95 (0.00–1.00) | 1.00 (1.00–1.00) |
| MRR on 20 questions, mean (range) | 0.94 (0.33–1.00) | 0.95 (0.00–1.00) | 0.95 (0.50–1.00) |
| Recall@5 on 20 paraphrases, mean (range) | 0.00 (0.00–0.00) | 0.50 (0.00–1.00) | 0.45 (0.00–1.00) |
| MRR on 20 paraphrases, mean (range) | 0.00 (0.00–0.00) | 0.44 (0.00–1.00) | 0.28 (0.00–1.00) |
| Paraphrases that return nothing | 6 of 20 | 7 of 20 | 1 of 20 |
| Exact titles ranked first | 30 of 30 | 30 of 30 | 30 of 30 |
| Questions nothing answers that still return decisions | 2 of 4 | 1 of 4 | 2 of 4 |

Hybrid passed all three conditions.

#### The misses, published

- **Half the paraphrases are still missed.** Semantic search finds 10 of 20 in
  its top 5. For 7 it returns nothing, because no decision reaches the 0.30
  floor. For 3 it returns only other decisions: "where do we verify who is
  calling an endpoint?" ranks a logging decision, not the authentication
  middleware.
- **Hybrid finds one paraphrase fewer than semantic alone, and ranks them
  lower** (MRR 0.28 against 0.44): keyword partial matches on other words of
  the question take slots. In exchange it keeps every keyword hit, and it
  returns something for 19 of the 20.
- **Semantic alone misses a question keyword search answers.** "is the graph
  server reachable from other machines on the network?" ranks the
  graph-server decision instead of the loopback-binding one. Hybrid ranks the
  answer second.
- **Questions nothing answers:** hybrid returns decisions for the same 2 of 4
  as keyword search; for "what is our gdpr data retention policy?" it fills
  all 5 slots.
- **Synthetic, one author.** Every decision and question was written by the
  same author, in the same session as the keep rule. Real teams word things
  more differently. Score your own with a query set in the same format.

The smoke test run while building this used one of the 20 paraphrases ("where
do we verify who is calling an endpoint?"), so that question's semantic result
was seen before the eval ran. The floor and the keep rule were not changed.

### The eval scores every mode

- `neuralmind decisions eval --queries FILE` runs keyword, semantic and hybrid
  side by side on one scratch store (`--mode all`, the default), or one of
  them with `--mode`.
- A mode that can't run, because the model isn't on disk, is listed under
  **Not run** with the reason. A hybrid search that fell back to keyword
  results is never scored as hybrid.
- The maintenance replay (`decisions eval` without `--queries`) stays on
  keyword search, so its numbers don't depend on whether the model is cached.

### What the agent sees

| Agent | Before (v4.7) | After (v4.8) |
|---|---|---|
| **Claude Code** (MCP + hooks) | `neuralmind_memory_search` and `neuralmind_query_decisions` found a decision only through a shared word; a question in other words got nothing, or partial matches on unrelated words | The same calls also rank by meaning. The response says `"mode": "hybrid"`, or `"mode": "keyword"` with a `notice` when the model isn't on disk. Hooks are unchanged: the stale-decision guard matches by file, not by search |
| **Cursor / Cline / Continue** (MCP) | Same as Claude Code | Same as Claude Code |
| **Generic MCP client** | No way to choose the ranking | Optional `mode`: `hybrid`, `semantic` or `keyword`. `semantic` without the model returns `code: "semantic_unavailable"`; an unknown mode is `invalid_request` |

**New variable:** `NEURALMIND_DECISION_SEARCH` sets the decision-search mode
for calls that name none (`hybrid` by default; `semantic`; `keyword` for the
v4.6 ranking).

## Policy mistakes that meant the defaults now refuse

[v4.6.1](RELEASE_NOTES_v4.6.1.md) made the MCP server apply `security.roles`
and `security.rate_limit`, and refuse a `security:` value of the wrong type
with `reason: config`. Its release notes also listed two mistakes it still read
as "no policy", which applies the default policy. That policy gives `admin`
every tool, and any caller can declare `admin` unless
[`identity: os`](RELEASE_NOTES_v4.7.0.md) is set. v4.8.0 refuses both.

If `neuralmind-backend.yaml` has no `security:` section, nothing changes.

### What changed

- **A policy file that doesn't parse is refused** when its text, outside
  comments, names a security setting: `security`, `roles`, `rate_limit`,
  `identity` or `require_encrypted_storage`. Every MCP call returns
  `code: "security_denied"`, `reason: "config"`, and an error quoting the parse
  failure. v4.7.0 did this only for files naming `identity` or
  `require_encrypted_storage`, and counted a mention in a comment. Other
  unparseable files still read as empty, so a typo in backend tuning doesn't
  block the server.
- **A `security:` or `roles:` key left empty is refused.** YAML reads a key
  with nothing under it as `null`, which is what's left when every entry under
  it is commented out. The error says what to write instead: `roles: {}` to
  grant nothing, or no key at all to use the defaults. An empty `rate_limit:`
  still means the default limit, and a missing key still means the defaults.
- **`neuralmind doctor` reports it.** The *Security policy* check fails on any
  role-policy problem that makes the server refuse every call: these two, and
  the wrong-type values v4.6.1 already refused.

A misspelled key, such as `role:` for `roles:`, is still read as absent. After
writing a policy, call a tool you left out with `role: "admin"` and check that
it returns `security_denied`.

### What the agent sees

Only in a project whose `neuralmind-backend.yaml` has one of these mistakes.
Every other project sees what it saw in v4.7.0.

| Agent | Before | After |
|---|---|---|
| **Claude Code** (MCP + hooks) | The default policy: a call declaring `admin` reached every tool | Every MCP tool returns `security_denied` with `reason: "config"` and the setting to fix. Hooks don't go through the MCP role policy and are unaffected |
| **Cursor / Cline / Continue** (MCP) | Same as Claude Code | Same as Claude Code |
| **Generic MCP client** | Same as Claude Code | Same as Claude Code |

## Upgrading

`pip install -U neuralmind`. Nothing to reinstall, and nothing to rebuild in a
project built with v3.9.0 or later (the recap looks for the
`.neuralmind/build_status.json` a build leaves). The first recap appears in the
session after the first one you work in on v4.8.0.

**Decision search:**

- **The first semantic or hybrid search embeds your decisions** and caches
  the vectors in `memory.db`. On a machine where `neuralmind build` has never
  run, hybrid search keeps returning keyword results, with a notice, until it
  does.
- **Results can differ from v4.7 for the same question.** Hybrid adds
  decisions related in meaning and reorders the list, and a question nothing
  answers may return loosely related decisions. Check the titles, as before.
  `NEURALMIND_DECISION_SEARCH=keyword` restores the v4.6 ranking.
- **`neuralmind decisions eval --queries` JSON changed shape.** Results are
  now under `modes`, keyed by mode (`{"summary", "per_query"}` each), with
  `not_run` beside them. The Markdown table gained a Mode column. A script that
  read the top-level `summary` should read `modes.keyword.summary` instead.

**MCP security policy:**

- If `neuralmind-backend.yaml` has a `security:` section, run
  `neuralmind doctor` before upgrading the MCP server. A failed
  *Security policy* check names the setting to fix.
- The server reads the policy once per process, so after fixing it, restart
  the MCP server (a new agent session, or reconnecting the server).

## Related

- Use case: [Pick up where you left off](../use-cases/pick-up-where-you-left-off.md)
- CLI reference: [`recap`](../wiki/CLI-Reference.md#recap-v480),
  [Environment Variables](../wiki/CLI-Reference.md#environment-variables)
- [Memory Layer wiki: search modes and the eval](../wiki/Memory-Layer.md#query-decisions)
- [CLI reference: `decisions`](../wiki/CLI-Reference.md#decisions-v410) and
  the `NEURALMIND_DECISION_SEARCH` variable
- Use case: [Find the decision behind the code when you don't know its words](../use-cases/find-decisions-by-meaning.md)
- Comparison: [NeuralMind vs. Mem0 and Zep](../comparisons/vs-mem0-zep.md)
- [Security Guide: capping what a caller can claim](../SECURITY-GUIDE.md#capping-what-a-caller-can-claim)
- Previous release: [v4.7.0](RELEASE_NOTES_v4.7.0.md)
