# NeuralMind vs. Claude Projects

## What Claude Projects is

Claude Projects is Anthropic's feature for attaching a persistent set of files (docs, code, PDFs) to a Claude.ai conversation. The attached knowledge is loaded into the model context each turn, up to Claude's context window.

## How NeuralMind differs

| Dimension | Claude Projects | NeuralMind |
|---|---|---|
| Surface | Claude.ai web | CLI + MCP + Claude Code hooks |
| Indexing | None — files are loaded verbatim | Knowledge graph + vector index |
| Context shape | Raw file text | 4-layer progressive disclosure (L0–L3) |
| Cost per turn | Pays for all attached content every turn | Pays only for the ~800 tokens actually retrieved |
| File limit | Bounded by the attached-files quota | Bounded only by disk |
| Works in IDE agents | No | Yes |
| Tool-output compression | No | Yes |
| Offline | No | Yes |
| Model choice | Claude only | Any model |

## When to pick which

- **Pick Claude Projects** for doc-centric chats, onboarding material, or mixed knowledge bases you interact with through Claude.ai.
- **Pick NeuralMind** when the content is source code, when you want retrieval that scales to larger codebases, or when you are working inside an IDE agent rather than Claude.ai.

A common pattern: use Claude Projects for product specs and NeuralMind for the repo. Feed NeuralMind's `wakeup` or `query` output into a Projects conversation for the best of both.

---

[← Back to comparison index](./README.md)
