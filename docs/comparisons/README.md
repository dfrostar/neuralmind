# NeuralMind Comparisons

Honest side-by-side comparisons between NeuralMind and the tools developers most often evaluate alongside it.

Each page follows the same structure:

1. **What it is** — one-paragraph description of the alternative
2. **How it differs** — concrete mechanism and output differences
3. **When to pick which** — decision guidance, not a sales pitch
4. **Feature matrix** — side-by-side table

| Compared against | Best when you are asking |
|---|---|
| [Cursor `@codebase`](./vs-cursor-codebase.md) | "I use Cursor — do I still need this?" |
| [Aider repo-map](./vs-aider-repomap.md) | "Aider already builds a repo-map, isn't this the same?" |
| [Sourcegraph Cody](./vs-cody.md) | "How is this different from Cody's code context?" |
| [Continue / Cline](./vs-continue-cline.md) | "I already have an MCP-capable IDE agent" |
| [LangChain / LlamaIndex for code](./vs-langchain-llamaindex.md) | "Can I just wire up RAG myself?" |
| [Long context windows](./vs-long-context.md) | "Claude has 1M context / Gemini has 2M — why compress?" |
| [Generic RAG over a codebase](./vs-rag.md) | "Isn't this just RAG with extra steps?" |
| [Tree-sitter / ctags / grep](./vs-treesitter-ctags.md) | "Why do I need embeddings at all?" |

## TL;DR

NeuralMind is specifically a **two-phase token optimizer for AI coding agents**:

- **Phase 1 (retrieval):** a 4-layer progressive disclosure index that surfaces ~800 tokens of structured context for a code question.
- **Phase 2 (consumption):** PostToolUse hooks that compress `Read`, `Bash`, and `Grep` output *before the agent sees it*.

Most alternatives cover one or the other, not both. The comparison pages walk through where each tool fits in that split.
