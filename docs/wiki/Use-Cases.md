# Use Cases

Command-driven walkthroughs matched to how people actually use NeuralMind. Copy, run, done.

Canonical pages live at [docs/use-cases/](../blob/main/docs/use-cases/README.md) — this wiki page is a jump table.

## Pick your situation

| Use case | Best for you if… | Primary outcome |
|---|---|---|
| [Claude Code user](../blob/main/docs/use-cases/claude-code.md) | You use Claude Code daily | Two-phase optimization: retrieval + PostToolUse compression |
| [Cost optimization](../blob/main/docs/use-cases/cost-optimization.md) | You need to reduce and *report* LLM spend | Baseline → measure → stakeholder-ready report |
| [Any LLM (ChatGPT / Gemini / local)](../blob/main/docs/use-cases/any-llm.md) | You use a non-MCP chat or mixed models | Copy-paste + CLI-piped context into any model |
| [Offline / regulated work](../blob/main/docs/use-cases/offline-regulated.md) | You're on air-gapped or regulated systems | 100% local, zero telemetry, compliance properties table |
| [Growing monorepo](../blob/main/docs/use-cases/growing-monorepo.md) | Your codebase grows fast and drifts often | Three freshness strategies + large-repo tuning |

## Decision helpers

### "What am I trying to solve for?"

| If your goal is… | Do this | Expected outcome |
|---|---|---|
| **Cut LLM spend** on code Q&A | `install-hooks` + use `query` for questions | 5–10× total reduction vs baseline agent |
| **Faster, more grounded** agent responses | `wakeup` at session start → `query` / `skeleton` during | Fewer hallucinations; less re-exploration |
| **Keep all code local** | Default install — no extra config | 100% offline; nothing leaves the machine |
| **Work across Claude + GPT + Gemini** | Build once, pipe output into any model | Model-agnostic |
| **Make retrieval adapt** to your team's patterns | Enable memory + `neuralmind learn .` | Reranking improves over time |
| **Measure savings** for a stakeholder | `neuralmind benchmark . --json` | Per-query tokens, reduction ratios |
| **Auto-refresh** the index | `neuralmind init-hook .` | Every commit rebuilds incrementally |

### "This is happening to me" (symptoms → fix)

Full symptom/fix table lives in the [main README](../blob/main/README.md#-when-do-i-reach-for-neuralmind).

## Still not sure?

**You probably don't need NeuralMind if:**

- Your codebase is under ~5K tokens total (just paste the whole thing in).
- You don't use an AI coding agent.
- You only want inline completions — use [Copilot](Comparisons) or [Cursor](Comparisons) directly.

**You almost certainly want NeuralMind if:**

- You pay per-token for code questions and your bill keeps growing.
- Your agent keeps running out of context or confidently hallucinating structure.
- You need AI help on code that cannot leave your machine.

---

See the [Setup Guide](Setup-Guide) once you've picked a use case.
