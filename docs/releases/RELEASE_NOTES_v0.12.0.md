# NeuralMind v0.12.0 — install doctor + friendlier first run

**Release Date:** June 2026

## TL;DR

NeuralMind has grown a lot of moving parts — a code graph, a semantic
index, a synapse memory db, Claude Code hooks, an MCP server, and a
query-memory consent flag. When one of them isn't wired up, the symptom
used to be a cryptic stack trace or silent no-ops. v0.12.0 makes the
setup legible:

- **`neuralmind doctor`.** One command that inspects an install and
  reports each piece with a status and an exact fix:

  ```
  NeuralMind doctor — /path/to/project
  ============================================================
    [ ok ] Code graph: 1240 nodes at /path/to/project/graphify-out/graph.json
    [ ok ] Semantic index: 1240 nodes embedded (chromadb backend)
    [warn] Synapse memory: no synapses.db yet (nothing learned)
           -> It populates automatically as you query and edit the codebase.
    [ ok ] MCP server: MCP SDK importable (neuralmind-mcp ready)
    [warn] Claude Code hooks: not installed
           -> Install them: neuralmind install-hooks
    [ ok ] Query memory: enabled (logging queries for learning)
  ============================================================
  ```

  It exits non-zero when a check **fails** (graph/index missing), so you
  can gate CI or an agent's setup step on it. `--json` emits a stable
  machine-readable form for scripting and agent consumption.

- **Friendlier "graph not built" error.** Querying a project before its
  code graph exists used to surface an opaque `AttributeError`. It now
  raises a clear, actionable message naming the two commands to run
  (`graphify update`, then `neuralmind build`) and points you at
  `neuralmind doctor`.

No migration, no new dependencies, no behavior change for already-working
installs. `doctor` is read-only — it never builds, writes, or mutates
state.

---

## What the agent actually sees, post-install

A coding agent (or a human) dropped into a fresh clone can now run a
single command to learn exactly what's missing and how to fix it, instead
of discovering it one failed query at a time. For agents that provision
their own environment, `neuralmind doctor --json` is a pre-flight check:

```json
{
  "status": "fail",
  "checks": [
    {"name": "Code graph", "status": "fail",
     "detail": "not found at /repo/graphify-out/graph.json",
     "fix": "Generate it: graphify update /repo"},
    {"name": "Semantic index", "status": "fail",
     "detail": "no nodes embedded (chromadb backend)",
     "fix": "Build it: neuralmind build"}
  ]
}
```

### Per-agent expectations

| Agent | What changes |
|-------|--------------|
| **Claude Code** | `neuralmind doctor` confirms hooks are registered in `.claude/settings.json` and that `SYNAPSE_MEMORY.md` will load; a failed query now reads as a setup hint, not a trace. |
| **Cursor / Cline** | Same diagnostics via the CLI; the MCP-server check confirms `neuralmind-mcp` is importable for the MCP integration. |
| **Generic MCP client** | `doctor --json` gives a stable, parseable health snapshot to gate on before issuing tool calls. |

---

## Checks performed

| Check | OK when | Fix on failure |
|-------|---------|----------------|
| Code graph | `graphify-out/graph.json` present and parseable | `graphify update .` |
| Semantic index | nodes embedded in the active backend | `neuralmind build` |
| Synapse memory | `synapses.db` present (WARN if not — it's learned over time) | populates automatically |
| MCP server | MCP SDK importable | reinstall with the `mcp` extra |
| Claude Code hooks | a neuralmind hook block in project or global `settings.json` | `neuralmind install-hooks` |
| Query memory | `NEURALMIND_MEMORY` logging enabled | `NEURALMIND_MEMORY=1` |

---

## Upgrade

```bash
pip install --upgrade neuralmind
neuralmind doctor .
```

Nothing else to do.
