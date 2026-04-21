# NeuralMind vs. Generic RAG over a codebase

## What "generic RAG" means here

The standard recipe: chunk files by lines or tokens, embed them, store in a vector DB, retrieve top-k by cosine similarity, concatenate into the prompt. Works fine for documentation and long-form text.

## Why code needs more

Code is not prose. It has structure (call graphs, imports, class hierarchies) that text chunking destroys. NeuralMind keeps that structure and uses it.

| Dimension | Generic RAG | NeuralMind |
|---|---|---|
| Unit of retrieval | Text chunk (e.g. 500 chars) | Graph node (function, class) with metadata |
| Context | Flat list of chunks | Progressive: identity → summary → clusters → hits |
| Call graph | Lost at chunking | Preserved, used in skeletons |
| Community/cluster awareness | None | First-class (top clusters by relevance in L2) |
| Cross-file edges | Not encoded | Explicit (`imports_from`, `shares_data_with`) |
| Token budget | You enforce it | Built-in, reported per query |
| Consumption-side savings | None | Read/Bash/Grep PostToolUse compression |

## When to pick which

- **Pick generic RAG** if you are indexing docs, tickets, or mixed content where structure doesn't matter.
- **Pick NeuralMind** for code. The graph-aware layers and skeleton output capture the structural context that generic chunking throws away — and you don't pay for the throwaway tokens.

If you already have a generic RAG pipeline and only want the compression half, NeuralMind's PostToolUse hooks can run standalone without the retrieval layer.

---

[← Back to comparison index](./README.md)
