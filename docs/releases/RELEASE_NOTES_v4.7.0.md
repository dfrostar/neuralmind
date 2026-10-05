# NeuralMind v4.7.0 — decision search finds a decision worded differently from the question

**Type:** Minor release | **Theme:** decision memory

Decision search used to find a decision only when the question shared a word
with it. An agent asking "where do we verify who is calling an endpoint?"
never reached "Use per-handler authentication middleware", because the two
share no word. v4.7.0 ranks decisions by meaning as well, with the same local
embedding model the code index already uses, and makes the fused ranking the
default:

1. **Three search modes.** `hybrid` (default) fuses a keyword ranking and a
   meaning ranking; `semantic` ranks by meaning only; `keyword` is the v4.6
   search.
2. **Local, and never a download.** Vectors are computed on your machine and
   cached in `.neuralmind/memory.db`. Search uses the model `neuralmind build`
   already fetched; without it, hybrid search returns keyword results and says
   so.
3. **Measured before it became the default.** 20 paraphrased questions that
   share no word with their answers were written and committed, with a keep
   rule, before semantic search was run on them. Hybrid passed the rule. It
   finds 9 of the 20 in its top 5, where keyword search finds none, and the
   misses are listed below.

This is item G1 of the mem0 gap analysis in
[`docs/specs/LOCAL-API-SPEC.md`](../specs/LOCAL-API-SPEC.md) §4.1. The other
items (change history, duplicate warnings, filters, expiry dates and the rest)
are not in this release.

## 1. Three search modes

| Mode | Ranks by | Use it for |
|------|----------|------------|
| `hybrid` (default) | Shared words and meaning, fused by reciprocal rank fusion (k = 60) | Everyday questions |
| `semantic` | Cosine similarity between the question and each decision's title + rationale, embedded with `all-MiniLM-L6-v2`; a decision needs at least 0.30 | Questions you expect to share no word with the decision |
| `keyword` | Shared words: FTS5, bm25-ranked, any word can match (v4.5.1+) | Exact identifiers, and the v4.6 ranking |

- **CLI:** `neuralmind decisions query "QUESTION" --mode hybrid|semantic|keyword`.
  The header names the mode that ran:
  `# NeuralMind Decisions Query: "…" (hybrid)`.
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

## 2. Local, cached, and never a download

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

## 3. Measured before it became the default

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

## 4. The eval scores every mode

- `neuralmind decisions eval --queries FILE` runs keyword, semantic and hybrid
  side by side on one scratch store (`--mode all`, the default), or one of
  them with `--mode`.
- A mode that can't run, because the model isn't on disk, is listed under
  **Not run** with the reason. A hybrid search that fell back to keyword
  results is never scored as hybrid.
- The maintenance replay (`decisions eval` without `--queries`) stays on
  keyword search, so its numbers don't depend on whether the model is cached.

## What the agent actually sees post-install

| Agent | Before (v4.6) | After (v4.7) |
|---|---|---|
| **Claude Code** (MCP + hooks) | `neuralmind_memory_search` and `neuralmind_query_decisions` found a decision only through a shared word; a question in other words got nothing, or partial matches on unrelated words | The same calls also rank by meaning. The response says `"mode": "hybrid"`, or `"mode": "keyword"` with a `notice` when the model isn't on disk. Hooks are unchanged: the stale-decision guard matches by file, not by search |
| **Cursor / Cline / Continue** (MCP) | Same as Claude Code | Same as Claude Code |
| **Generic MCP client** | No way to choose the ranking | Optional `mode`: `hybrid`, `semantic` or `keyword`. `semantic` without the model returns `code: "semantic_unavailable"`; an unknown mode is `invalid_request` |

## Upgrade notes

- `pip install -U neuralmind`. No rebuild and no configuration change.
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

- [Memory Layer wiki: search modes and the eval](../wiki/Memory-Layer.md#query-decisions)
- [CLI reference: `decisions`](../wiki/CLI-Reference.md#decisions-v410) and
  the `NEURALMIND_DECISION_SEARCH` variable
- Use case: [Find the decision behind the code when you don't know its words](../use-cases/find-decisions-by-meaning.md)
- Comparison: [NeuralMind vs. Mem0 and Zep](../comparisons/vs-mem0-zep.md)
