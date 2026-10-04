# NeuralMind vs. Windsurf / Codeium

## What Windsurf and Codeium are

Codeium (now evolving into the Windsurf IDE) is a full AI coding environment with its own editor, proprietary indexing, and agent runtime. It indexes your repository on Codeium's infrastructure and injects context into completions and chat.

## How NeuralMind differs

| Dimension | Windsurf / Codeium | NeuralMind |
|---|---|---|
| Product type | IDE + agent + indexer, vertically integrated | Context provider / optimizer |
| Editor | Windsurf (VS Code fork) | Editor-agnostic |
| Indexing | Server-side, proprietary | Local knowledge graph + ChromaDB |
| Agent runtime | Built-in | Use your own (Claude Code, Cursor, Cline, Continue) |
| Model choice | Codeium-curated set | Any — NeuralMind is just context |
| Data flow | Code sent to Codeium infrastructure | No telemetry and no repository content sent by default (your agent still sends the slice it selects to its model) |
| Tool-output compression | No | No (its Claude Code PostToolUse hooks used to; measured, that added tokens — [benchmark](https://github.com/dfrostar/neuralmind/blob/main/docs/benchmarks/compression.md)) |
| License | Proprietary | MIT |

## When to pick which

- **Pick Windsurf/Codeium** if you want a turn-key AI IDE and you are comfortable with server-side indexing.
- **Pick NeuralMind** if you already have an editor and agent you like, want local-only indexing, or want model-agnostic context that works across Claude, GPT, and Gemini.

You can also use NeuralMind *inside* Windsurf as a CLI: generate `wakeup` / `query` context and paste it into the chat panel. You don't get NeuralMind's Claude Code hooks there (prompt-time recall, the stale-decision guard — they're Claude-Code-specific), but you still get the retrieval-side savings.

---

[← Back to comparison index](./README.md)
