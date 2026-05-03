# NeuralMind

Adaptive semantic code intelligence for AI coding agents. Reduces tokens
on code questions by 40-70x via progressive context disclosure, plus a
brain-like synapse layer that learns associations between code nodes
from how you actually use the codebase.

## Architecture

Two cooperating brains:

- **Claude (or any agent) = cortex.** Stateless reasoning over a
  working-memory window. NeuralMind never tries to reason here.
- **NeuralMind = hippocampus + associative cortex.** Persistent
  weighted graph of code nodes. Learns by Hebbian co-activation,
  decays unused edges, runs spreading activation for recall.

Communication channels: MCP tools, Claude Code lifecycle hooks
(`SessionStart`, `UserPromptSubmit`, `PreCompact`, `PostToolUse`),
and the file activity watcher.

## Layout

- `neuralmind/core.py` — orchestrator, public API
- `neuralmind/embedder.py` — graphify graph → ChromaDB embeddings
- `neuralmind/context_selector.py` — L0/L1/L2/L3 progressive disclosure
- `neuralmind/synapses.py` — SQLite-backed Hebbian synapse store
- `neuralmind/synapse_memory.py` — markdown export to Claude Code memory
- `neuralmind/watcher.py` — file activity → synapse co-activation
- `neuralmind/hooks.py` — Claude Code hook registration + runtime
- `neuralmind/mcp_server.py` — MCP tools for any agent
- `neuralmind/cli.py` — `neuralmind {build,query,watch,install-hooks,…}`

## Local conventions

- Tests live in `tests/`. The synapse layer's tests are stdlib-only
  so they run without the full dep set.
- Generated state lives in `<project>/.neuralmind/` — never committed.
- Behavior toggles via env vars: `NEURALMIND_BYPASS=1` skips
  compression, `NEURALMIND_SYNAPSE_INJECT=0` skips prompt-time
  recall, `NEURALMIND_SYNAPSE_EXPORT=0` skips memory export.

## Learned associations

@.neuralmind/SYNAPSE_MEMORY.md
