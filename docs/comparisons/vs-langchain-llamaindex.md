# NeuralMind vs. LangChain / LlamaIndex for code

## What LangChain and LlamaIndex are

General-purpose frameworks for building RAG pipelines. You choose a loader, splitter, embedder, vector store, and retriever, then wire them into a prompt template. For code, a common recipe is: `DirectoryLoader` → `RecursiveCharacterTextSplitter` → OpenAI/local embeddings → Chroma/FAISS → retriever.

## How NeuralMind differs

| Dimension | LangChain / LlamaIndex for code | NeuralMind |
|---|---|---|
| Primitives | Document/Node, Splitter, Embedder, Retriever | Code graph (functions, classes, communities) |
| Chunking | Text-level (line/token windows) | Symbol-level from the knowledge graph |
| Context shape | Flat top-k chunks | 4 layers (identity, summary, clusters, search) with token budget |
| Setup | You assemble the pipeline | `pip install neuralmind && neuralmind build .` |
| Agent integration | You write the glue | MCP server + CLI + PostToolUse hooks ready to use |
| Tool-output compression | Not its concern | First-class feature |
| Flexibility | Very high | Opinionated for code |

## When to pick which

- **Pick LangChain / LlamaIndex** if you are building a custom RAG product (e.g., a domain-specific code assistant, a web app, a multi-source retriever mixing code + docs + tickets).
- **Pick NeuralMind** if you want the "best default" code context for an AI coding agent with zero glue code and measurable per-query token savings.

Roughly: LangChain/LlamaIndex give you the Lego bricks; NeuralMind is the assembled model optimized specifically for "AI agent answers questions about a repo".

---

[← Back to comparison index](./README.md)
