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
| Tool-output compression | None | None (its PostToolUse hooks used to compress Read/Bash/Grep results; measured, that added tokens — [benchmark](https://github.com/dfrostar/neuralmind/blob/main/docs/benchmarks/compression.md)) |
| Offline | No (Cursor cloud) | Yes — no repository content transmitted; one first-build model download, pre-seedable |
| Cost | Bundled in Cursor subscription | Free, local |
| Install methods | Paid Mac/Windows/Linux IDE installer | `pip` / `pipx` / `uv` / Docker / source — runs anywhere Python does |
| Adapts to you | No | Yes — a Hebbian synapse layer learns associations from your usage automatically (co-activation with decay), no manual step |

## When to pick which

- **Pick Cursor `@codebase`** if you only use Cursor and are happy with the built-in behavior.
- **Pick NeuralMind** if you want the same quality of retrieval outside Cursor, measurable token savings, or offline operation.

They are not mutually exclusive: run NeuralMind's MCP server inside Cursor and you get its token-budgeted retrieval and learned memory on top of Cursor's own indexing.

---

[← Back to comparison index](./README.md)
