# Show HN

**Disclosed-maker post.** Submit yourself; post the first comment right after.

---

## Title

```
Show HN: NeuralMind – semantic code memory for AI agents, with an honest benchmark
```

(Alt, if you want the number in the title:
`Show HN: NeuralMind – 38–85× less context for code questions, benchmark included`)

## URL

```
https://github.com/dfrostar/neuralmind
```

## First comment (post immediately after submitting)

```
Maker here. NeuralMind is a local semantic-memory layer for AI coding agents
(Claude Code, Cursor, Cline, anything that speaks MCP). It does two things:

1. Progressive context disclosure — instead of pasting files or dumping a
   whole vector-RAG result into the window, it assembles a compact structured
   context (project map → relevant symbols → call edges) on demand.

2. A "synapse" layer — a Hebbian graph that learns which code goes with what
   from how you actually work, decays unused links, and runs spreading
   activation for recall. It's the part a static code index can't copy.

I got tired of token-reduction claims with no correctness number attached, so
the headline ships with a reproducible benchmark you can run yourself:

  git clone https://github.com/dfrostar/neuralmind && cd neuralmind
  pip install -e . tiktoken
  python -m evals.public.run

It clones real, pinned OSS repos (requests, click), and scores cost AND
correctness together — "gold-file recall" where the gold file is the objective
definition site of a named symbol (verifiable with one rg command, no LLM
judge). On those repos: 100% gold-file recall at 38–85× fewer tokens than
pasting files, beating ripgrep on both axes.

Where it does NOT win, stated plainly: a well-tuned vector RAG using the same
encoder ties it on pure findability and is cheaper on raw tokens — NeuralMind
spends those extra tokens assembling readable structured context to *answer*,
not just locate. That's in the table.

I also ran a live head-to-head vs the obvious incumbent, codebase-memory-mcp
0.8.1, on the same repos/questions/scorer at matched retrieval depth: 100%
recall and MRR 0.96 vs 0.23 on requests. Pure retrieval ranking on both sides,
their most-favorable keyword mapping, raw traces committed:
python -m evals.public.competitor

Methodology + raw data: https://github.com/dfrostar/neuralmind/blob/main/docs/benchmarks/public.md

100% local, no API key needed for the index. Happy to answer anything —
especially the skeptical questions about the benchmark design.
```

## Anticipated questions — short honest answers to have ready

- **"Isn't this just RAG?"** The retrieval core *is* a vector index. The
  difference is (a) progressive disclosure assembling structured context vs
  dumping chunks, and (b) the synapse layer that learns associations from usage.
  The benchmark isolates this — `embedding-rag` is literally NeuralMind's own
  encoder in isolation, so the gap shows what the assembly layer adds and costs.
- **"You picked easy repos."** They're pinned at SHAs you can check out; queries
  are pre-registered in `evals/public/manifest.json` before tuning; every query
  is reported including losses. Add your own repo and re-run — it's one manifest
  entry.
- **"Vector RAG beats you on tokens."** Yes, on bare findability. Said so in the
  table and the comment. The extra tokens buy assembled context to answer with.
- **"158 languages elsewhere."** The incumbent advertises 158 (vendored
  grammars); its own paper scores 31, and C at 0.58. We ship 7 languages at
  measured parity and disclose what's out (macros, templates, `#ifdef`).
