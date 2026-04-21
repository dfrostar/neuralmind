# NeuralMind vs. Aider repo-map

## What Aider's repo-map is

Aider builds a concise, tree-sitter-derived map of your repository — a ranked list of the most relevant symbols and their signatures — and injects it into the prompt every turn. It's a clever, zero-embedding, purely static approach.

## How NeuralMind differs

| Dimension | Aider repo-map | NeuralMind |
|---|---|---|
| Technique | Static tree-sitter + PageRank over symbol graph | Knowledge graph + vector embeddings (ChromaDB) |
| Semantic retrieval | No — syntactic signal only | Yes — embedding similarity over all nodes |
| Output | Ranked signatures injected every turn | On-demand progressive layers (wakeup / query / skeleton) |
| Host | Aider CLI only | Any MCP agent + CLI + copy-paste to any LLM |
| Tool-output compression | None | Read/Bash/Grep PostToolUse hooks |
| Learns from usage | No | Yes — cooccurrence-based reranking |
| Languages | Whatever tree-sitter supports | Same (via graphify) |

## When to pick which

- **Pick Aider repo-map** if you use Aider and want a zero-dependency, deterministic map.
- **Pick NeuralMind** if you want semantic (not just syntactic) retrieval, want it outside Aider, or want the consumption-side compression. Aider's map answers "what symbols exist"; NeuralMind's query answers "which 800 tokens best explain X".

They compose: you can feed NeuralMind's `wakeup` output into an Aider session as additional context.

---

[← Back to comparison index](./README.md)
