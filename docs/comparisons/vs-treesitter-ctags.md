# NeuralMind vs. Tree-sitter / ctags / grep

## What these tools are

Purely syntactic: tree-sitter parses source into AST, ctags builds a symbol index, grep matches regex across files. They are fast, deterministic, and answer "where is this symbol?" — not "what answers this question?".

## How NeuralMind differs

| Dimension | Tree-sitter / ctags / grep | NeuralMind |
|---|---|---|
| Query type | Exact / regex / symbol name | Natural language + BM25 exact-symbol hybrid (v0.38.0+) |
| Underlying signal | Syntax | Syntax (via graphify) **+** semantic embeddings |
| Output | List of matches | Structured, token-budgeted context for an LLM |
| Agent integration | You parse results yourself | MCP server + PostToolUse hooks |
| Handles synonyms / paraphrase | No | Yes (embedding similarity) |
| Dependencies | Minimal | ChromaDB |
| Offline | Yes | Yes |

## When to pick which

- **Pick grep/ctags/tree-sitter** when you need a deterministic, exhaustive answer — every occurrence of a symbol, 5ms, zero deps.
- **Pick NeuralMind** when the question is natural language, spans multiple files, or is the kind of thing an LLM agent needs to orient itself. Since v0.38.0, NeuralMind also handles exact-symbol queries better via BM25 hybrid ranking (RRF merge of BM25 + embedding results), so the gap on identifier-heavy queries is narrower — but grep is still the right tool for "find *all* occurrences."

They are complementary. NeuralMind's `search` command gives you ranked semantic results; `grep` gives you every literal hit. Most real agent loops benefit from both — which is why NeuralMind's PostToolUse hooks leave `Grep` output intact (just capped at 25 matches) rather than replacing it.

## The heuristic-only alternative

If you want NeuralMind's output *shape* (skeletons, clusters) without embeddings, the [graphify](https://github.com/dfrostar/graphify) knowledge graph alone already provides ~33x token reduction with zero ML dependencies. NeuralMind adds semantic retrieval on top, trading a ChromaDB dependency for stronger recall on paraphrased queries.

---

[← Back to comparison index](./README.md)
