# Find the decision behind the code when you don't know its words

**Best for:** teams and agents with recorded decisions
(`neuralmind decisions record`, or `neuralmind_record_decision` over MCP),
where whoever asks "why is it like this?" isn't whoever wrote the answer down.

**Primary goal:** a question finds the decision that answers it even when the
two share no word, and you can check how often that holds on your own
decisions (v4.8.0+).

Decisions are written by one person, on one day, in that person's words.
Months later an agent asks in its own: "what happens if someone steals a copy
of our db?". The answer is on record as "Hash API tokens before storing them".
Keyword search can't connect the two, because they share no word. From v4.8.0,
decision search also ranks by meaning, with the embedding model NeuralMind
already runs locally for the code index.

---

## 1. Set up once

```bash
neuralmind build .
```

Building the code index downloads the embedding model (`all-MiniLM-L6-v2`)
once. Decision search uses that copy and never downloads anything itself.
Nothing else to configure: `hybrid`, the default mode, fuses keyword ranking
with meaning ranking.

## 2. Ask in your own words

Four decisions are on record in this example: sessions in Postgres, hashed API
tokens, a per-client rate limit, and a loopback-only server.

```
$ neuralmind decisions query "what happens if someone steals a copy of our db?" --mode keyword
No decisions found for: what happens if someone steals a copy of our db? (keyword search)

$ neuralmind decisions query "what happens if someone steals a copy of our db?"
# NeuralMind Decisions Query: "what happens if someone steals a copy of our db?" (hybrid)

1. [ACTIVE] Hash API tokens before storing them
   Commit: 8c458f9f18e4ccdd5eb771503d06b69112446a78
   Files: auth/tokens.py
   A leaked database must not leak usable tokens. Tokens are stored as SHA-256 hashes and compared in c...
```

The first semantic or hybrid search embeds every decision on record and caches
the vectors in `.neuralmind/memory.db`. Later searches embed only the question,
plus any decision recorded or amended since.

## 3. What your agent sees

Agents get the same ranking through `neuralmind_memory_search` and
`neuralmind_query_decisions`, and every response names the mode that ranked
it:

```json
{
  "query": "what happens if someone steals a copy of our db?",
  "mode": "hybrid",
  "count": 1,
  "results": [
    {"id": "cafd8b7a-…", "title": "Hash API tokens before storing them", "status": "ACTIVE", "…": "…"}
  ]
}
```

If the model isn't on disk, `"mode"` is `"keyword"` and a `notice` says why, so
an agent never mistakes keyword results for a search by meaning.

## 4. Know where it stops

Meaning ranking misses too. In the same project:

```
$ neuralmind decisions query "what stops a buggy assistant from overwhelming us?" --mode semantic
No decisions found for: what stops a buggy assistant from overwhelming us? (semantic search)
```

The rate-limit decision ("A runaway agent loop can issue thousands of calls…")
answers it, but its similarity stays under the 0.30 floor. In hybrid mode, the
same question returns two decisions that only share word prefixes with it. On
the committed synthetic eval, semantic search finds 10 of 20 paraphrased
questions in its top 5 and hybrid finds 9; the misses are listed in the
[Memory Layer wiki](../wiki/Memory-Layer.md#eval-harness). So read the titles
before trusting a hit, as you would with keyword results.

Pick a mode for the question:

| You're asking with… | Use |
|---|---|
| Your own words, or an agent's | `hybrid` (default) |
| An exact identifier or a word you know is in the decision | `hybrid` or `keyword` |
| Words you're sure the decision doesn't contain | `semantic` (shorter lists; nothing under the floor) |

`NEURALMIND_DECISION_SEARCH=keyword` keeps the v4.6 ranking everywhere: CLI,
MCP tools and Python API.

## 5. Measure it on your own decisions

The eval that chose the default runs on any query set in the same format:
decisions, plus questions with the ids that answer them.

```json
{
  "extra_decisions": [
    {"id": "tok", "title": "Hash API tokens before storing them", "rationale": "A leaked database must not leak usable tokens."}
  ],
  "queries": [
    {"id": "q1", "kind": "paraphrase", "query": "what happens if someone steals a copy of our db?", "gold": ["tok"]}
  ]
}
```

```bash
neuralmind decisions eval --queries my_decision_queries.json --format md
```

It scores keyword, semantic and hybrid side by side on a scratch store, with the
eval's own 15 synthetic seed decisions mixed in as distractors: recall@5
and MRR per question kind, with every miss listed. Your project's own decisions
are never read or changed. Write the questions before you look at the results,
and keep the ones that miss.

## See also

- [Keep decision memory honest across commits](./decision-memory-across-commits.md):
  decisions go STALE when their code changes
- [Memory Layer wiki](../wiki/Memory-Layer.md#query-decisions): every mode, flag
  and MCP argument
- [v4.8.0 release notes](../releases/RELEASE_NOTES_v4.8.0.md#decision-search-by-meaning)
