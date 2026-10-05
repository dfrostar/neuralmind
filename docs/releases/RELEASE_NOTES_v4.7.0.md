# NeuralMind v4.7.0 — MCP roles bound to OS accounts, a check for encrypted storage, and decision search by meaning

**Type:** Minor release | **Themes:** CMMC 2.0 readiness (sections 1–3) · decision memory (sections 4–7)

## CMMC 2.0 readiness

Until this release, every MCP tool call named its own `actor` and `role`, and
nothing checked either: any caller could declare `admin`. NeuralMind also left
encryption at rest entirely to the host, with no way to confirm it was there.
Both gaps came up when mapping NeuralMind to CMMC 2.0 Level 2 for teams that
index source code containing Controlled Unclassified Information (CUI).

- **`security.identity: os` ties MCP roles to OS accounts.** The server takes
  the caller's identity from the OS account it runs as — over the default
  stdio transport, the agent that launched it — and the role from
  `security.users`. What a call declares is ignored and kept in the audit log
  as a claim.
- **`security.require_encrypted_storage: true` refuses unverified volumes.**
  NeuralMind checks for FileVault, BitLocker, or dm-crypt/LUKS and refuses to
  build, query, serve MCP tools, or run hooks until the check passes.
- **`neuralmind doctor` reports both** as two new checks: *Security policy*
  and *Storage encryption*.

Nothing changes for a project that doesn't set these keys. Both build on
[v4.6.1](RELEASE_NOTES_v4.6.1.md), which made the MCP server apply
`security.roles` and `security.rate_limit` at all.

## Decision search by meaning

Decision search used to find a decision only when the question shared a word
with it. An agent asking "where do we verify who is calling an endpoint?"
never reached "Use per-handler authentication middleware", because the two
share no word. v4.7.0 ranks decisions by meaning as well, with the same local
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

---

## 1. Identity from the OS, not from the call

```yaml
# neuralmind-backend.yaml
security:
  identity: os
  users:
    alice: builder
    bob: reader
  default_role: reader      # optional; unset refuses accounts missing from users
```

The account name comes from the OS: the passwd entry for the effective uid on
Linux and macOS, `GetUserNameW` on Windows. `LOGNAME`, `USER` and `USERNAME` are
not consulted, because the process that launches the server sets them.

NeuralMind refuses every MCP call, with `reason: identity`, when:

- the HTTP transport is in use (`NEURALMIND_MCP_TRANSPORT=streamable_http`):
  the server's OS account is not the remote caller's;
- the OS account can't be determined;
- the account isn't in `users` and `default_role` is unset;
- the policy file is world-writable (POSIX), since any local user could edit
  the role mapping;
- `identity` has a value other than `declared` or `os`, or `users` isn't a
  mapping.

A policy file that names `identity` or `require_encrypted_storage` but doesn't
parse is refused too. The general config loader treats a broken file as empty,
which would quietly switch enforcement off.

The rate limit keys on the OS account under `identity: os`, so a caller can't
reset its budget by declaring a different actor. Audit events written outside
MCP (CLI queries, builds) also take the OS account as their actor;
`NEURALMIND_ACTOR` is recorded as `claimed_actor` instead of being believed.

**What it does not do.** Anyone who can run commands as that OS account can
also read `.neuralmind/` directly and edit a policy file they own. `identity:
os` makes per-user roles and audit attribution trustworthy on a host where an
administrator owns the policy file and users have separate accounts. On a
single-user laptop its value is attribution: the agent can no longer write a
different name into the audit log.

## 2. Encrypted storage, verified

NeuralMind does not encrypt `.neuralmind/` itself. CMMC SC.L2-3.13.11 asks for
FIPS-validated cryptography, and the OpenSSL inside a pip-installed
`cryptography` wheel is not FIPS-validated, so in-process encryption would not
satisfy the control. The accepted answer is the OS's full-disk encryption, and
NeuralMind now verifies it:

| OS | What counts as encrypted | FIPS mode reported from |
|----|--------------------------|-------------------------|
| macOS | `diskutil` reports FileVault on for the volume. Apple silicon encrypts internal disks in hardware even with FileVault off, but then the key isn't protected by a password, so that doesn't count | Not reported: macOS has no FIPS switch. FileVault uses Apple corecrypto; check Apple's CMVP certificates for your macOS version |
| Linux | `lsblk` shows a `crypt` layer under the filesystem holding the project | `/proc/sys/crypto/fips_enabled` |
| Windows | BitLocker protection on for the drive | The `FipsAlgorithmPolicy` registry value |

The check covers every place NeuralMind's state can land: the project root,
`.neuralmind/` (following a symlink to wherever it points), and a custom vector
index location from `db_path`, whether passed in, configured, or set by a
backend switch. Anything short of a positive answer — a check that times out,
an overlay filesystem in a container, BitLocker suspended — counts as not
verified. Only an explicit `false` (or `0`, `no`, `off`) turns the setting off;
a blank `require_encrypted_storage:` counts as on. The
verdict is written to the audit log once per process as a `storage_check`
event, which gives an assessor a dated record.

With `require_encrypted_storage: true` and an unverified volume:

- `neuralmind build` and `neuralmind query` exit with the reason;
- MCP tools return `security_denied` with `reason: storage`;
- hooks write nothing (no output cache, no synapse transitions) and stay out of
  the agent's way;
- the decision store won't open.

## 3. Malformed policies under the new settings

v4.6.1 refuses a `security:` value of the wrong type with `reason: config`. In
v4.7.0 the MCP dispatcher checks for that before the storage check, so a broken
policy is reported as the cause rather than as a storage refusal it also
triggers. A file that names `identity` or `require_encrypted_storage` but
doesn't parse is refused too; other unparseable files still read as empty, as
in v4.6.1.

## 4. Three search modes

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

## 5. Local, cached, and never a download

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

## 6. Measured before it became the default

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

### The misses, published

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

## 7. The eval scores every mode

- `neuralmind decisions eval --queries FILE` runs keyword, semantic and hybrid
  side by side on one scratch store (`--mode all`, the default), or one of
  them with `--mode`.
- A mode that can't run, because the model isn't on disk, is listed under
  **Not run** with the reason. A hybrid search that fell back to keyword
  results is never scored as hybrid.
- The maintenance replay (`decisions eval` without `--queries`) stays on
  keyword search, so its numbers don't depend on whether the model is cached.

## What the agent actually sees post-install

### Security settings (sections 1–3)

Nothing, unless the project sets the new keys.

With `identity: os`, a tool call that declares `role: admin` runs with the role
`security.users` gives the OS account. A tool outside that role returns:

```json
{"error": "Access denied for role 'reader' on tool 'neuralmind_build'", "code": "security_denied", "reason": "rbac"}
```

An account with no role, or the HTTP transport, returns `reason: identity`.
With `require_encrypted_storage` on an unverified volume, every tool returns
`reason: storage`, with the check's detail in `error`.

| Agent | Transport | `identity: os` | `require_encrypted_storage` |
|-------|-----------|----------------|-----------------------------|
| Claude Code | stdio | Works: the server runs as the developer's account | MCP tools and hooks both refuse on an unverified volume |
| Cursor | stdio | Works | MCP tools refuse; Cursor runs no NeuralMind hooks |
| Cline | stdio | Works | MCP tools refuse |
| Generic MCP client | stdio | Works | MCP tools refuse |
| Any client over Streamable HTTP | HTTP | Refused: the server can't identify a remote caller | MCP tools refuse |

### Decision search (sections 4–7)

| Agent | Before (v4.6) | After (v4.7) |
|---|---|---|
| **Claude Code** (MCP + hooks) | `neuralmind_memory_search` and `neuralmind_query_decisions` found a decision only through a shared word; a question in other words got nothing, or partial matches on unrelated words | The same calls also rank by meaning. The response says `"mode": "hybrid"`, or `"mode": "keyword"` with a `notice` when the model isn't on disk. Hooks are unchanged: the stale-decision guard matches by file, not by search |
| **Cursor / Cline / Continue** (MCP) | Same as Claude Code | Same as Claude Code |
| **Generic MCP client** | No way to choose the ranking | Optional `mode`: `hybrid`, `semantic` or `keyword`. `semantic` without the model returns `code: "semantic_unavailable"`; an unknown mode is `invalid_request` |

## Environment variables

- **Added:** `NEURALMIND_DECISION_SEARCH` sets the decision-search mode for calls
  that name none (`hybrid` by default; `semantic`; `keyword` for the v4.6
  ranking). See section 4.
- `NEURALMIND_MCP_TRANSPORT=streamable_http` is now refused under
  `identity: os`. Under `identity: os`, `NEURALMIND_ACTOR` no longer sets the
  audit actor; it is recorded as `claimed_actor`.

## Upgrade notes

`pip install -U neuralmind`. No rebuild is needed.

**Security settings:**

- No action is needed if `neuralmind-backend.yaml` has no `security:` section.
- To adopt `identity: os`, list each OS account in `users`, make the file
  writable only by its owner (`chmod 644`), and run `neuralmind doctor` to see
  the role your account gets.
- To adopt `require_encrypted_storage`, run `neuralmind doctor` first. The
  *Storage encryption* line shows what the check sees on each machine,
  including CI runners, which usually aren't encrypted.

**Decision search:**

- **The first semantic or hybrid search embeds your decisions** and caches
  the vectors in `memory.db`. On a machine where
  `neuralmind build` has never run, hybrid search keeps returning keyword
  results, with a notice, until it does.
- **Results can differ from v4.6 for the same question.** Hybrid adds
  decisions related in meaning and reorders the list, and a question nothing
  answers may return loosely related decisions. Check the titles, as before.
  `NEURALMIND_DECISION_SEARCH=keyword` restores the v4.6 ranking.
- **`neuralmind decisions eval --queries` JSON changed shape.** Results are
  now under `modes`, keyed by mode (`{"summary", "per_query"}` each), with
  `not_run` beside them. The Markdown table gained a Mode column. A script that
  read the top-level `summary` should read `modes.keyword.summary` instead.

## Related

- [CMMC 2.0 practice mapping](../COMPLIANCE-SUMMARY.md) — what NeuralMind
  provides for each Level 2 practice, and what stays yours
- [Security settings reference](../wiki/CLI-Reference.md)
- [Use case: NeuralMind in a CMMC CUI enclave](../use-cases/cmmc-cui-enclave.md)
- [Security Guide — Access Control](../SECURITY-GUIDE.md#access-control)
- [Memory Layer wiki: search modes and the eval](../wiki/Memory-Layer.md#query-decisions)
- [CLI reference: `decisions`](../wiki/CLI-Reference.md#decisions-v410) and
  the `NEURALMIND_DECISION_SEARCH` variable
- Use case: [Find the decision behind the code when you don't know its words](../use-cases/find-decisions-by-meaning.md)
- Comparison: [NeuralMind vs. Mem0 and Zep](../comparisons/vs-mem0-zep.md)
