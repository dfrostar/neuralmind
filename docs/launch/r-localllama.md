# r/LocalLLaMA — self-post

**Disclosed-maker post.** First person, as the author. r/LocalLLaMA tolerates
maker self-posts when they're technical, honest, and local-first — which this is
(100% local, no API key for the index). Disclose in the first line. Don't ask
for upvotes.

---

## Title

```
I built a local semantic-memory layer for coding agents — and an honest benchmark to back it (100% local, no API key)
```

## Body (copy-paste)

```
I'm the author of NeuralMind, an open-source local memory layer for AI coding
agents (Claude Code, Cursor, Cline, any MCP client). Posting it here because it's
exactly the kind of thing this sub cares about: it runs 100% on-device, the index
needs no API key, and your code never leaves the machine. The more capable your
local model, the more each saved token is worth — context compression pays off
more, not less, as models get better.

The pitch in one line: instead of pasting files or dumping a vector-RAG result
into the window, NeuralMind assembles a compact, structured context on demand
(project map → relevant symbols → call edges), and a brain-like "synapse" layer
learns which code goes with what from how you actually work.

I'm allergic to token-reduction claims with no correctness number attached, so
every benefit below ships with an eval you can run yourself. Four data-backed
benefits, not just "fewer tokens":

  💸 Cheaper context — 100% gold-file recall at 38–85× fewer tokens than pasting
     files; beats ripgrep on BOTH recall and cost. (Public benchmark, real OSS
     repos: requests, click.)

  🎯 Finds the RIGHT code, not just less of it — 100% gold-file recall, MRR 0.96
     (ranks the correct file at the top). Beats the incumbent codebase-memory-mcp
     on retrieval ranking, 0.96 vs 0.23. (Same benchmark.)

  🧠 Learns how you work — a Hebbian synapse layer that learns co-edited files
     lifts top-k retrieval hit-rate +11.7 points (71.7% → 83.3%), budget-neutral
     (no extra tokens). This is the part a static code index structurally can't
     copy. (Synapse A/B eval.)

  🔬 Better-grounded answers — at a matched token budget, the assembled context
     carries more of the gold facts than naive truncation: faithfulness +0.143,
     grounding 1.00. (Faithfulness/parity gate.)

Honest scope (because this sub will and should ask): the cost + accuracy rows run
on real, pinned OSS repos and are fully reproducible. The learning + grounding
rows are committed A/Bs on a bundled reference fixture — real, but smaller-scope,
and I label them that way. And where it loses: a well-tuned vector RAG using the
same encoder ties it on pure findability and is cheaper on raw tokens. That's in
the table, not buried — NeuralMind spends the extra tokens assembling readable
structured context to *answer*, not just to locate the file.

Reproduce the headline yourself (no trust required):

  git clone https://github.com/dfrostar/neuralmind && cd neuralmind
  pip install -e . tiktoken
  python -m evals.public.run     # clones pinned repos, prints the table

The gold file for each query is the objective definition site of a named symbol —
verifiable with one rg command, no LLM judge. Queries are pre-registered before
tuning and every one is reported, including losses.

Repo: https://github.com/dfrostar/neuralmind
Benchmark methodology + raw data: https://github.com/dfrostar/neuralmind/blob/main/docs/benchmarks/public.md

Happy to go deep on the benchmark design, the synapse learning math, or how it
plugs into a local agent loop. Tear it apart — that's why the harness is in the
repo.
```

## If asked "how is this different from <X> / from plain RAG"

Short answer to drop in a reply: "The retrieval core *is* a local vector index —
I'm not hiding that, the `embedding-rag` baseline in the benchmark is literally
my own encoder in isolation. The two things on top are (1) progressive disclosure
that assembles structured context instead of dumping chunks, and (2) the synapse
layer that learns associations from your usage and decays unused ones. The
benchmark gap between `neuralmind` and `embedding-rag` is exactly the cost/benefit
of that assembly layer, measured."
