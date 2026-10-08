# NeuralMind v4.12.0 — retrieval that keeps what vector search finds: 92% hit@5 on the retrieval eval, 97.5% public-benchmark recall, 14 ms queries

**Type:** Minor release | **Themes:** [ranking](#1-l3-ranks-a-pool-of-20-and-keeps-eight) · [what gets embedded](#4-what-a-node-is-embedded-as) · [speed](#5-speed) · [JavaScript](#6-javascript-repositories-get-code-nodes) · [fixes](#7-fixes) · [measurement](#8-measurement)

An assessment of NeuralMind's retrieval found one result that framed everything
else: on the public benchmark, the `embedding-rag` baseline — NeuralMind's
*own* vector index, top 8, nothing added — matched or beat the full
`NeuralMind.query` pipeline on gold-file recall on all four repositories, at
fewer tokens. The layers on top of vector search were taking accuracy away.

Four things did it:

- L3 kept only **four** hits, and every re-ranking pass ran *after* that cut, so
  nothing could rescue a gold file at fused rank 5–8.
- **Multipliers sized to outvote the ranking.** A query whose words looked like
  code multiplied code hits by 3 and docstrings by 0.5, and a word of the
  question appearing anywhere in a file's path multiplied it by up to 10, over
  fused scores between 0 and 1.
- **Question words in the keyword search.** "the", "how" and "message" could put
  an unrelated docstring above the one that named the answer.
- **A node embedded as metadata.** A method was embedded without its class, and
  without the docstring that says what it does, beside a line number and a
  cluster number that carry no meaning.

v4.12.0 fixes each one. Every change was measured on the 150-question retrieval
eval and the 40-query public benchmark. Each ranking default was then checked
by putting it back one at a time.

## The numbers

| | v4.11.1 | **v4.12.0** |
|---|---:|---:|
| Retrieval eval: hit@5, 150 questions over 5 repos | 80.0% | **92.0%** |
| Retrieval eval: MRR | 0.671 | **0.729** |
| Retrieval eval: context tokens per question | 930 | **773** (−17%) |
| Public benchmark: gold-file recall, 40 queries | 95% (85.71–100% per repo) | **97.5%** (90–100% per repo) |
| Public benchmark: fewer tokens than pasting every file | 45–246× | **54–260×** |
| Faithfulness fixture: gold facts in the context | 0.559 | **0.825** |
| Self-benchmark fixture: top-k hit rate / reduction | 75% / 5.1× | **88% / 5.6×** |
| Query latency, p50 (one machine, see below) | 266–348 ms | **14–19 ms** |
| Indexing this repository (19,629 nodes, one machine) | 22 min | **6.7 min** |

- **Retrieval eval:** 20 questions won and 2 lost on hit@5 (exact McNemar
  p = 0.0001). Every repository improved: requests +3, click +4, flask +2,
  rich +3, this repository +6. The mean MRR change is +0.057, with a paired
  bootstrap 95% interval of [+0.003, +0.109].
  [`bench/retrieval/vs-v4.11`](https://github.com/dfrostar/neuralmind/blob/main/bench/retrieval/vs-v4.11/report.md)
- **Public benchmark:** NeuralMind now finds every gold file on requests, click
  and rich, and 9 of 10 on flask.
  [`docs/benchmarks/public.md`](../benchmarks/public.md)
- **Evidence levels.**
  - *Reproducible on demand:* the retrieval eval, the public benchmark, and the
    two fixture gates (the self-benchmark and faithfulness runs, also CI gates).
  - *One machine, not committed as data:* query latency and indexing time,
    measured by a local harness on a 4-core container. The retrieval eval now
    records p50/p95 query latency, so the next release's comparison is
    committed.

## 1. L3 ranks a pool of 20 and keeps eight

- **What the agent gets:** L3, the search results, now holds **8 hits instead of
  4**.
- **How they are chosen:** from a pool of the **20 best fused candidates**.
  - Every pass that re-ranks runs over the whole pool first: the type mark-down,
    the duplicate collapse, and the boosts below.
  - Only then is the pool cut to eight.
  - The structural and synapse passes then re-rank those eight, as before.
- **Putting four back costs 14 of the 150 questions** (`on-v4.12`, `l3_k4`).
- **Settings:** `NEURALMIND_L3_K` (default 8) and `NEURALMIND_L3_POOL`
  (default 20).
- **Duplicates collapse.** Hits that repeat the same text in the same file
  collapse into the best-ranked one. In requests, `ok`, `__bool__` and
  `__nonzero__` share one docstring, and they used to take three of the four
  slots.

## 2. Boosts that no longer outvote the ranking

- **Requested types only.** Code-or-docs re-weighting now applies only when the
  type is asked for: `--type code|docs`, or the MCP `query_type`.
  - An intent *detected* from the wording of the question no longer re-weights
    hits. The detector is a keyword heuristic, and it read "how does X…"
    questions as documentation questions.
  - Turning detected-intent re-weighting back on costs 3 questions overall, and
    the markdown-heavy repository drops from 77% to 67%.
  - `NEURALMIND_AUTO_INTENT_BOOST=1` restores it.
- **Code-signal boost off.** It multiplied a hit by up to 10 when a word of the
  question appeared in its path, label or text.
  - It is now off by default; on, it costs 2 questions.
  - When on, it matches whole words of the **file name**. It used to match
    substrings of the whole path, so the package directory (`requests`, `click`)
    matched every file, and one-letter names like click's `F` matched almost
    anything.
  - `NEURALMIND_CODE_SIGNAL_CAP=N` turns it back on, capped at N×.
- **Docstrings count as code.** Under a code intent, a docstring now counts as
  the code it documents. Markdown is still marked down. The docstring is the
  node a "what does X do" question matches best.
- **Keyword search drops question words.** It ignores "the", "how", "what" and
  similar words in the *query*; the index itself is unchanged. On click's
  `echo-util` miss, the docstring "Aborts the execution of the program with a
  specific error message" ranked first on "the / message / program", ahead of
  `echo()`'s.

## 3. L2 shows this query's candidates

- **Before:** L2, "Relevant Code Areas", listed the first seven nodes of each
  relevant cluster in graph order. That was the same for every query and
  unrelated to it: for a question about click's `echo`, it showed
  `_compat.py: CYGWIN, WIN, _ansi_re`.
- **Now:** it lists this query's candidates that L3 doesn't show, pool ranks
  9–20, grouped by cluster.
- **Faithfulness fixture:**
  - With everything else in v4.12.0 held fixed, this change alone took fact
    recall from 0.723 to 0.825.
  - Against v4.11.1, the context now beats a naive context of the same size by
    +0.25. In v4.11.1 the margin was +0.03.
- **L1 is unchanged.**
- **Setting:** `NEURALMIND_QUERY_LAYERS` picks which layers a query returns.
  `L0,L3` cuts tokens by 57% on the retrieval eval at the same hit@5, but loses
  the facts L2 carries.

## 4. What a node is embedded as

A method used to be embedded as:

```
Entity: send()
Type: code
File: sessions.py
Location: L673
Community: 3
```

It is now embedded as its qualified name, its module and its docstring:

```
Session.send()
In module sessions
Send a given PreparedRequest.
```

- **Docstring nodes** embed as the docstring alone.
- **One shared definition.** Both backends use `neuralmind/node_text.py`, so a
  node embeds the same on turbovec and on ChromaDB.
- **Moving code no longer re-embeds it.** The line number and cluster number
  are gone from the embedded text and from its content hash. Inserting a line
  re-embedded every symbol below it, and a cluster renumbering re-embedded the
  whole repository.
- **Measured:** during development, on the four library repositories with the
  new ranking, the new text gained 4 questions and lost none against the old
  text.
- **Not done: code bodies.** Adding the first 200 or 600 characters of each
  function's body *lowered* recall with this encoder (MiniLM, trained on
  128-token prose). That waits for a code-trained embedder.

## 5. Speed

- **Embedder padding.** The bundled MiniLM embedder padded every text to 256
  tokens. A 15-token query and a 40-token node paid for 256.
  - It now pads to the longest text in the batch. Because pooling is
    attention-masked, the vectors are bit-for-bit identical (maximum
    difference 0.0 on mixed-length inputs).
  - An indexing batch of 32 runs about 6.7× faster.
- **Session reuse.** It now reuses one ONNX session per process instead of
  building one (~150 ms) for every call.
  - A query embeds in about 3 ms instead of about 275 ms.
  - On Python 3.14, where onnxruntime 1.29 deadlocks after a few runs on one
    session, every batch still gets a fresh one.
  - `NEURALMIND_ORT_SESSION_CACHE=0` or `=1` forces either way.
- **Inverted keyword index.** BM25 searches an inverted index instead of
  scanning every document for every query term. The scores are the same.
- **Indexing outside Python 3.14** runs in-process instead of starting a
  subprocess for every 256 texts.

## 6. JavaScript repositories get code nodes

- **Before:** `.js`, `.mjs`, `.cjs` and `.jsx` files had no grammar. A
  JavaScript-only repository was classified as prose and got no code nodes at
  all.
- **Now:** they are parsed with the TypeScript grammars. You get functions,
  classes, methods, JSDoc docstrings, imports and calls.
- **JSX:** `.tsx` and `.jsx` use the TSX grammar. The TypeScript grammar read
  `<div>` as a type assertion and lost the component around it.
- **Imports:** extensionless imports (`./lib/util`) and ESM-style `.js` imports
  from TypeScript (`./db.js` → `db.ts`) now resolve.

## 7. Fixes

- **Redaction gap on turbovec.** With `--redact-secrets` on, turbovec's
  `embed_nodes` stored a markdown section's body without redacting it. The other
  two embed paths did redact. The body reached the vector store's SQLite file
  and the keyword index. It is now redacted, and a regression test reads the
  stored rows.
- **Wrong model for large batches.** An injected embedder's batches over 256
  texts were sent to subprocesses that always built MiniLM, so its vectors
  could mix two models. Any embedder other than MiniLM now runs in-process.
- **Re-ranking mutated the search cache.** Re-ranking scaled the scores of the
  per-query search cache in place, so every later reader saw them compounded.
  It now works on copies.
- **Small indexes re-searched every layer.** The search cache missed whenever
  the index had fewer results than asked for, so a small index searched again
  for every layer.
- **Self-reinforcing synapse loop.** Query reinforcement wired the hits the
  synapse layer *itself* pulled in to the question's own hits. Repeated, that
  let the graph confirm its own guesses until the edge reached long-term weight.
  Only hits the question's own search found co-activate now.
- **ChromaDB markdown.** The ChromaDB backend embedded a markdown section's
  heading, not its body (turbovec embedded the body).
- **Class matching.** A class was matched to its file by an id prefix without
  the separator, so `foo_py` matched classes in `foo_py.py`.
- **Dead code.** `QueryHandler` is removed. It was unused, and every method in
  it called something that doesn't exist.

## 8. Measurement

- **Public benchmark, `neuralmind` backend:**
  - It runs read-only (`learn=False`); it used to train the index it measured.
  - Its tokens are counted with the benchmark's tokenizer, like every other
    backend's. They were counted with a chars/4 estimate, which ran 13% under
    on one query.
- **`embedding-rag` baseline:** it is now described as what it is: the top 8
  entries of NeuralMind's own vector index, sending a symbol's name, module and
  docstring, not its code. Its token count is a floor, below what a chunk RAG
  that sends code bodies would pay.
- **Retrieval eval: a paired keep rule.**
  - A configuration is kept when, pooled over every question, it wins more
    hit@5 questions than it loses with an exact McNemar p < 0.05, no repository
    drops by more than two questions, and tokens rise by at most 10%.
  - The old rule asked for a rise on three repositories, with one question
    worth 3.3 points. It rejected a change that raised two repositories and
    lowered none.
  - The report adds the MRR change with a bootstrap interval and p50/p95 query
    latency.
- **Comparing releases:** `--compare OLD NEW` pairs two runs, which is how
  `vs-v4.11` was made.

## What the agent actually sees

The click question "how does echo print a message with a newline to stdout"
(556 tokens):

```
## Relevant Code Areas

### Cluster 2 (relevance: 2.22)
- readline() (code) — testing.py
- STDOUT_HANDLE (code) — _winconsole.py
- EchoingStdin (code) — testing.py
…
### Cluster 1 (relevance: 1.96)
- get_binary_stdout() (code) — _compat.py
- echo_via_pager() (code) — termui.py

## Search Results

1. **Print a message and newline to stdout or a file. …** (score: 1.00)
   Type: rationale
   File: utils.py

2. **echo()** (score: 0.96)
   Type: code
   File: utils.py

3. **_echo()** (score: 0.92)
   Type: code
   File: testing.py
…
8. **_get_text_stdout()** (score: 0.51)
   Type: code
   File: _winconsole.py
```

- **v4.11.1** returned four hits for this question, in 632 tokens. The top two
  were the same. Its L2 listed each cluster's first seven nodes:
  `_compat.py`, `CYGWIN`, `WIN`, `_ansi_re` and so on.
- A code hit no longer repeats `Entity: … Type: … File: …` as a snippet under
  its own title. Only document hits carry a snippet.
- On the public benchmark's version of this question (`echo-util`), v4.11.1
  missed `utils.py`; v4.12.0 finds it.

## Per-agent expectations

| Agent | What changes |
|---|---|
| Claude Code (hooks + MCP) | `neuralmind_query` returns 8 search results and the query's other candidates in L2; prompt-time recall and session hooks are unchanged |
| Cursor / Cline / Continue (MCP) | The same `neuralmind_query` output; `query_type` still re-weights results when you pass it |
| Hermes-Agent plugin | The same context through `pre_llm_call` |
| Generic MCP client | The same; no tool, argument or response field changed |

## Settings

| Variable | Default | What it does |
|---|---|---|
| `NEURALMIND_L3_K` | `8` | L3 search results per query (v4.11: 4) |
| `NEURALMIND_L3_POOL` | `20` | Fused candidates L3 is chosen from |
| `NEURALMIND_QUERY_LAYERS` | `L0,L1,L2,L3` | Layers a query returns |
| `NEURALMIND_AUTO_INTENT_BOOST` | unset | `1` re-weights hits by the intent detected from the question (v4.11 behaviour) |
| `NEURALMIND_CODE_SIGNAL_CAP` | `1` (off) | `N` turns the code-signal boost back on, up to N× (v4.11: 10) |
| `NEURALMIND_ORT_SESSION_CACHE` | auto | `1` reuses one ONNX session per process, `0` builds one per batch; auto reuses except on Python 3.14 |

## Not measured, and where it still loses

- **Answer quality with a model in the loop is not measured.** Every number
  above is about whether the right file, or the right fact, reaches the
  context.
- **Rank of the gold file.** On flask and rich, NeuralMind's MRR (0.70, 0.83) is
  still below the plain vector baseline's (0.74, 0.94). Recall is at or above
  it.
- **One public query lost.** `request-wrapper` on flask (gold `wrappers.py`)
  was found in v4.11.1 and is missed now.
- **The parameter tuner is not wired in.** It still writes its choice where the
  selector doesn't read it, and its live evaluation doesn't pass candidate
  settings through the selector. Wiring it as it stands would steer budgets
  toward their minimum. It stays opt-in and inert until that is fixed.
- **The synapse layer's lift is measured only on the fixture** (+5 points this
  release, +6 in v4.11.1), whose seeded sessions overlap its gold answers.
  There is no real-repository measurement yet.

## Upgrading

- **Run `neuralmind build` once.** Every node's embedded text changed, so the
  first build after upgrading re-embeds every node once.
  - A full build took 6.7 minutes for this repository's 19,629 nodes on a
    4-core container. Re-embedding the four library repositories (548–2,069
    nodes) took 13–41 seconds each.
  - Later builds re-embed only what changed.
- **Restore v4.11 ranking:** `NEURALMIND_L3_K=4 NEURALMIND_CODE_SIGNAL_CAP=10
  NEURALMIND_AUTO_INTENT_BOOST=1`.
- **No index format change.** No hook re-install.

## Reproduce

```bash
git clone https://github.com/dfrostar/neuralmind && cd neuralmind
pip install -e . tiktoken
NEURALMIND_ORT_THREADS=1 python -m evals.public.run --out bench/public
NEURALMIND_ORT_THREADS=1 python -m evals.retrieval.run \
  --configs baseline,l3_k4,code_signal,auto_intent,l3_only,bm25_off --out bench/retrieval/on-v4.12
python -m evals.retrieval.run --compare \
  bench/retrieval/vs-v4.11/results-v4.11.1.json bench/retrieval/vs-v4.11/results-v4.12.0.json
```

## Related

- [Public benchmark](../benchmarks/public.md)
- [Retrieval eval reports](https://github.com/dfrostar/neuralmind/blob/main/bench/retrieval/README.md)
- [CLI reference: environment variables](../wiki/CLI-Reference.md#environment-variables)
- [v4.11.1 release notes](RELEASE_NOTES_v4.11.1.md)
