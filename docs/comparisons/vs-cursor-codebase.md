# NeuralMind vs. Cursor `@codebase`

## What Cursor `@codebase` is

Cursor's `@codebase` feature indexes your repository and injects relevant chunks into the model prompt when you reference it in a chat. Indexing is automatic and tied to the Cursor IDE.

## How NeuralMind differs

| Dimension | Cursor `@codebase` | NeuralMind |
|---|---|---|
| Host | Cursor IDE only | Any agent (Claude Code, Cursor, Cline, Continue, Claude Desktop, CLI) via MCP |
| Index unit | File chunks | Graph nodes (functions, classes) + communities + rationales |
| Retrieval | Chunk similarity | 4-layer progressive disclosure (identity → summary → clusters → search) |
| Output | Raw chunks into prompt | Structured, token-budgeted context with reduction metrics |
| Tool-output compression | None | PostToolUse hooks compress Read/Bash/Grep results |
| Offline | No (Cursor cloud) | Yes — nothing leaves your machine |
| Cost | Bundled in Cursor subscription | Free, local |
| Adapts to you | No | Yes — `neuralmind learn` discovers cooccurrence patterns |

## When to pick which

- **Pick Cursor `@codebase`** if you only use Cursor and are happy with the built-in behavior.
- **Pick NeuralMind** if you want the same quality of retrieval outside Cursor, measurable token savings, offline operation, or tool-output compression that cuts cost across *every* `Read`/`Bash`/`Grep` call — not just explicit `@codebase` invocations.

They are not mutually exclusive: run NeuralMind's MCP server inside Cursor and you get compression on top of Cursor's own indexing.
