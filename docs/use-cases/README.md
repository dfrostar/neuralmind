# NeuralMind Use Cases

Walkthroughs for the most common "what do I actually do?" questions, organized by who you are and what you're trying to solve. Each page is command-driven — copy, run, done.

| Use case | Best for | Primary goal |
|---|---|---|
| **[Index any repo with just `pip` (no graphify)](./zero-install-indexing.md)** | **First-timers, CI, locked-down machines** | **Nothing → queryable index in one install + one build** |
| **[Does it work on your code? (5-minute benchmark)](./benchmark-your-repo.md)** | **Evaluating whether to install at all** | **Measured before/after on YOUR codebase** |
| [Claude Code user](./claude-code.md) | You use Claude Code daily and want full two-phase optimization | Cheapest + smartest agent sessions |
| [Cost optimization](./cost-optimization.md) | Teams or solos watching LLM spend climb | Measure, reduce, and report savings — `neuralmind savings --cost` prices them in dollars (v0.45.0+) |
| [Any LLM (ChatGPT / Gemini / local)](./any-llm.md) | You use non-MCP chats or a model-agnostic workflow | Get NeuralMind context into any chat window |
| [Offline / regulated work](./offline-regulated.md) | Regulated industries, air-gapped machines | 100% local retrieval with zero telemetry |
| [Growing monorepo](./growing-monorepo.md) | Codebase where old context goes stale fast | Keep the index fresh with minimal effort |
| [Multi-agent codebase](./multi-agent.md) | You use multiple AI tools (Claude Code + Cursor + Hermes + OpenClaw) on the same project | One shared associative memory across every agent; v0.6.0 live graph shows the union |
| **[Slim & sovereign: ChromaDB-free local stack](./chromadb-free-local.md)** | **Security-sensitive teams, tiny-footprint installs (v0.21.0+)** | **Embed + search with zero ChromaDB — smaller deps, smaller index, fewer advisories** |
| **[Branch-isolated memory & team baselines](./branch-isolated-memory.md)** | **Heavy branchers, teams onboarding new devs (v0.24.0+)** | **Keep feature-branch learning out of `main`'s memory; ship a `shared` baseline as a versioned bundle** |
| **[Unified context engineering stack (NeuralMind + Ponytail + Headroom)](./unified-stack.md)** | **Teams who've hit the ceiling on single-tool optimization** | **Eliminate token waste at retrieval, transport, and generation simultaneously** |
| **[Blast radius before a rename](./blast-radius-before-a-rename.md)** | **Anyone (or any agent) about to rename, re-sign, or delete a symbol (v0.42.0+)** | **See every caller / importer / subclass a change would touch, before you edit — from the static code graph** |
| **[Decision provenance: answer "why is it like this?"](./decision-provenance.md)** | **Anyone inheriting code whose rationale lives in someone's head (v0.43.0+)** | **Capture a decision in a `Decision:` git trailer; recall it with `neuralmind why` — the *why* stored where it can't drift** |
| **[Find the coverage that lies: mock-only endpoints](./find-untested-endpoints.md)** | **Anyone with a green suite that still ships DB failures (v0.44.0+)** | **`neuralmind gaps` classifies endpoints live-covered / mock-only / untested — catch the `P2003` before the live smoke** |
| **[Measure memory across a major refactor (field report)](./measure-memory-across-a-refactor.md)** | **Anyone rebuilding a subsystem who wants proof the memory adapts** | **Before/after snapshot recipe + real case study: 48.8× reduction, personal synapse edges 36→135 on a ~9.3k-node TypeScript SaaS platform** |

Not sure which applies? Start with the [symptom / goal table in the main README](../../README.md#-when-do-i-reach-for-neuralmind).
