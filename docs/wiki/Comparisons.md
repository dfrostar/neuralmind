# Comparisons

Honest side-by-side comparisons between NeuralMind and the tools developers most often evaluate alongside it. Each linked page follows the same structure: what the alternative is → how NeuralMind differs → when to pick which → feature matrix.

Full source of these pages lives at [docs/comparisons/](../blob/main/docs/comparisons/README.md). The wiki version below is a convenience mirror with anchor links.

## When to read each page

| Compared against | Best when you are asking |
|---|---|
| [Cursor `@codebase`](../blob/main/docs/comparisons/vs-cursor-codebase.md) | "I use Cursor — do I still need this?" |
| [Aider repo-map](../blob/main/docs/comparisons/vs-aider-repomap.md) | "Aider already builds a repo-map, isn't this the same?" |
| [Sourcegraph Cody](../blob/main/docs/comparisons/vs-cody.md) | "How is this different from Cody's code context?" |
| [Continue / Cline](../blob/main/docs/comparisons/vs-continue-cline.md) | "I already have an MCP-capable IDE agent" |
| [GitHub Copilot](../blob/main/docs/comparisons/vs-github-copilot.md) | "I pay for Copilot — does this overlap?" |
| [Windsurf / Codeium](../blob/main/docs/comparisons/vs-windsurf-codeium.md) | "How does this compare to the Windsurf IDE?" |
| [Claude Projects](../blob/main/docs/comparisons/vs-claude-projects.md) | "Can't I just attach files to a Claude Project?" |
| [Prompt caching](../blob/main/docs/comparisons/vs-prompt-caching.md) | "Doesn't prompt caching solve the cost problem?" |
| [LangChain / LlamaIndex for code](../blob/main/docs/comparisons/vs-langchain-llamaindex.md) | "Can I just wire up RAG myself?" |
| [Long context windows](../blob/main/docs/comparisons/vs-long-context.md) | "Claude has 1M context / Gemini has 2M — why compress?" |
| [Generic RAG over a codebase](../blob/main/docs/comparisons/vs-rag.md) | "Isn't this just RAG with extra steps?" |
| [Tree-sitter / ctags / grep](../blob/main/docs/comparisons/vs-treesitter-ctags.md) | "Why do I need embeddings at all?" |

## One-line verdicts

| Compared against | Short verdict |
|---|---|
| Cursor `@codebase` | Works *only* in Cursor; NeuralMind works in any agent and adds tool-output compression |
| Aider repo-map | Aider is syntactic only; NeuralMind adds semantic retrieval and compression |
| Sourcegraph Cody | Cody is server-hosted and org-wide; NeuralMind is local and per-project |
| Continue / Cline | Those are agent runtimes; NeuralMind is the context/compression layer underneath |
| GitHub Copilot | Copilot is hosted completions; NeuralMind is local context for any agent |
| Windsurf / Codeium | Vertically integrated IDE; NeuralMind is editor- and model-agnostic |
| Claude Projects | Projects reload all files every turn; NeuralMind retrieves only what the query needs |
| Prompt caching | Caching amortizes a big prompt; NeuralMind makes the prompt small — combine both |
| LangChain / LlamaIndex | Frameworks you assemble; NeuralMind is the assembled default for code agents |
| Long context (1M/2M) | Possible ≠ cheap — NeuralMind gives ~60× cost reduction on the same model |
| Generic RAG | Text chunking loses structure; NeuralMind keeps the call graph |
| Tree-sitter / ctags / grep | Deterministic but syntactic; use alongside NeuralMind, not instead of |

## TL;DR

Most alternatives cover **retrieval** (Cursor `@codebase`, Aider, LangChain) or **indexing** (Copilot, Cody) or **hosting** (Claude Projects, Windsurf) — not the **two-phase** story. NeuralMind optimizes both:

1. What context the agent *retrieves* (progressive disclosure, ~800 tokens/query)
2. What the agent *consumes* from its own tool calls (PostToolUse compression on Read/Bash/Grep)

The savings compound.

---

See the [full comparison index](../blob/main/docs/comparisons/README.md) for the structured decision-guidance table.
