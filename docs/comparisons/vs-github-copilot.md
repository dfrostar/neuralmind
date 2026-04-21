# NeuralMind vs. GitHub Copilot

## What GitHub Copilot is

GitHub Copilot is Microsoft/GitHub's AI pair programmer: inline completions in your editor and a chat panel that can reference open files, workspace context, and (with Copilot Chat/Enterprise) indexed repositories. The index and retrieval are managed on GitHub's infrastructure.

## How NeuralMind differs

| Dimension | GitHub Copilot | NeuralMind |
|---|---|---|
| Core product | Code completion + chat | Context provider / token optimizer |
| Hosted | GitHub cloud | Fully local |
| Indexing | Server-side, GitHub-managed | Local knowledge graph + ChromaDB |
| Works outside GitHub's editors | Limited | Yes — any MCP agent, any CLI, any LLM |
| Model choice | GitHub-provided models | Model-agnostic (Claude, GPT, Gemini, local) |
| Tool-output compression | No | Yes (PostToolUse hooks) |
| License | Proprietary, per-seat | MIT, free |
| Data flow | Code snippets sent to GitHub/OpenAI | Nothing leaves your machine |
| Cost scaling | Flat subscription | Flat local cost; API costs drop 40–70× |

## When to pick which

- **Pick Copilot** if you want a fully hosted, zero-config pair programmer tied to VS Code / JetBrains and your GitHub account.
- **Pick NeuralMind** if you run your own agent (Claude Code, Cursor, Cline, Continue), want local-only indexing, or want to *reduce* the token bill of the agent you already use.

They are complementary: Copilot handles inline suggestions, NeuralMind handles the "explain / plan / refactor" conversations in whatever agent you prefer. If you are paying per-token for a non-Copilot agent, NeuralMind's savings compound with every query.

---

[← Back to comparison index](./README.md)
