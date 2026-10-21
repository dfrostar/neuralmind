# Use Cases

Command-driven walkthroughs matched to how people actually use NeuralMind. Copy, run, done.

Canonical pages live at [docs/use-cases/](https://github.com/dfrostar/neuralmind/blob/main/docs/use-cases/README.md) — this wiki page is a jump table.

## Pick your situation

| Use case | Best for you if… | Primary outcome |
|---|---|---|
| [Claude Code user](https://github.com/dfrostar/neuralmind/blob/main/docs/use-cases/claude-code.md) | You use Claude Code daily | Retrieval + session memory + lifecycle hooks |
| [Cost optimization](https://github.com/dfrostar/neuralmind/blob/main/docs/use-cases/cost-optimization.md) | You need to reduce and *report* LLM spend | Baseline → measure → stakeholder-ready report |
| [Any LLM (ChatGPT / Gemini / local)](https://github.com/dfrostar/neuralmind/blob/main/docs/use-cases/any-llm.md) | You use a non-MCP chat or mixed models | Copy-paste + CLI-piped context into any model |
| [Offline / regulated work](https://github.com/dfrostar/neuralmind/blob/main/docs/use-cases/offline-regulated.md) | You're on air-gapped or regulated systems | Local-first, no telemetry, compliance properties table |
| [Growing monorepo](https://github.com/dfrostar/neuralmind/blob/main/docs/use-cases/growing-monorepo.md) | Your codebase grows fast and drifts often | Three freshness strategies + large-repo tuning |
| [Slim & sovereign: ChromaDB-free local stack](https://github.com/dfrostar/neuralmind/blob/main/docs/use-cases/chromadb-free-local.md) | Security-sensitive teams, tiny-footprint installs (v0.21.0+) | Embed + search with zero ChromaDB — smaller deps, 8–16× smaller index, fewer advisories |
| [Team memory via CI auto-index *(v0.38.0+)*](https://github.com/dfrostar/neuralmind/blob/main/docs/use-cases/ci-auto-index.md) | You want every developer's NeuralMind index to stay fresh automatically | On-push GitHub Action rebuilds incrementally + commits shared team memory bundle |

## Decision helpers

### "What am I trying to solve for?"

| If your goal is… | Do this | Expected outcome |
|---|---|---|
| **Fewer tokens per code question** | `install-hooks` + use `query` for questions | Fewer tokens per code question — measure yours with `neuralmind benchmark .`. Not a smaller bill: a 20-task pilot found no difference in cost per task ([report](https://github.com/dfrostar/neuralmind/blob/main/bench/task_outcome/pilot/report.txt)) |
| **Ground the agent** in your code | `wakeup` at session start → `query` / `skeleton` during | A project map at session start and a ranked slice per question, so less re-exploration. What's measured is whether the right file is in that slice (40 of 40 public-benchmark queries; a gold file in the top five on 93.3% of the 150-question eval). On task outcomes, a 20-task pilot found no difference: the agent never called NeuralMind's tools ([report](https://github.com/dfrostar/neuralmind/blob/main/bench/task_outcome/pilot/report.txt)) |
| **Keep all code local** | Default install — no extra config | No telemetry; no repository content transmitted by default; works offline after the first build. Your agent still sends the slice it selects to its own model — use a local model to keep that on the machine too |
| **Work across Claude + GPT + Gemini** | Build once, pipe output into any model | Model-agnostic |
| **Make retrieval adapt** to your team's patterns | Enable memory + `install-hooks` (+ optional `neuralmind watch .`) + `neuralmind_feedback` MCP tool | The synapse layer learns which files you use together and re-ranks recall with those links; positive/negative feedback strengthens or weakens them. Whether it helps on your repo: `neuralmind eval . --synapse-ab` |
| **Measure savings** for a stakeholder | `neuralmind benchmark . --json` | Per-query tokens, reduction ratios |
| **Auto-refresh** the index | `neuralmind init-hook .` | Commits rebuild incrementally — and since v4.13.0 merges and pulls, branch switches and rebases too |

### "This is happening to me" (symptoms → fix)

Full symptom/fix table lives in the [main README](https://github.com/dfrostar/neuralmind/blob/main/README.md#-when-do-i-reach-for-neuralmind).

## Still not sure?

**You probably don't need NeuralMind if:**

- Your codebase is under ~5K tokens total (just paste the whole thing in).
- You don't use an AI coding agent.
- You only want inline completions — use [Copilot](Comparisons) or [Cursor](Comparisons) directly.

**You almost certainly want NeuralMind if:**

- You pay per-token for code questions and your bill keeps growing.
- Your agent keeps running out of context or re-exploring structure it has already seen.
- You need AI help on code that cannot leave your machine — NeuralMind transmits no repository content by default; pair it with a local model.

---

See the [Setup Guide](Setup-Guide) once you've picked a use case.
