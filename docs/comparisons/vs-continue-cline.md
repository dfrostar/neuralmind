# NeuralMind vs. Continue / Cline (MCP-capable IDE agents)

## What Continue and Cline are

Continue and Cline are open-source coding agents that run inside VS Code (and elsewhere) and support the Model Context Protocol (MCP). They provide the *agent runtime*: chat UI, tool execution, model routing.

## How NeuralMind differs

NeuralMind is not an agent — it's a **context provider** that agents call. It plugs into Continue, Cline, Claude Code, Claude Desktop, Cursor, or any MCP client.

| Dimension | Continue / Cline | NeuralMind |
|---|---|---|
| Role | Agent runtime (chat + tools + model) | Context provider (MCP server + CLI) |
| What it produces | LLM responses, file edits | Token-budgeted context strings, skeletons, search results |
| Codebase retrieval built-in | Basic (file reads, grep, optional embeddings) | Dedicated 4-layer progressive disclosure system |
| Tool-output compression | No | Yes (Claude Code hook format; portable to others) |
| Replaces the other? | No | No — they compose |

## When to pick which

Use both. NeuralMind makes Continue/Cline cheaper and more accurate by:

1. Providing the `neuralmind_query` MCP tool for any code question.
2. (In Claude Code) compressing every `Read`/`Bash`/`Grep` result via PostToolUse hooks.

If you only use Continue or Cline without NeuralMind, you rely on their built-in file-read/grep flow — which loads raw content and pays for every line the model sees. NeuralMind is the compression layer underneath.

---

[← Back to comparison index](./README.md)
