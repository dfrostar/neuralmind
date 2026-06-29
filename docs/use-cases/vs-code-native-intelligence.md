# Use case: VS Code native code intelligence

**Who this is for**: VS Code users who want NeuralMind's semantic search, graph view, and auto-build
available without leaving their editor or wiring up a tasks file.

**What it unlocks**: The NeuralMind VS Code extension turns the CLI into native editor affordances —
status bar freshness indicator, command palette queries, an embedded graph panel, and an opt-in hover
provider — all talking to the same local Python process, no cloud required.

---

## Installation

```bash
# 1. Install NeuralMind (if not already)
pip install neuralmind

# 2. Build your project's index
cd /path/to/your/project
neuralmind build .

# 3. Install the extension
cd /path/to/neuralmind-repo/editors/vscode
npm install && npm run compile

# 4. In VS Code: Extensions → "Install from VSIX" → select editors/vscode/
# Or open editors/vscode/ as a workspace and press F5 to launch a debug session.
```

---

## What you see

### Status bar

The status bar item on the left shows index freshness at a glance:

| State | Display | Meaning |
|-------|---------|---------|
| Building | `⟳ NeuralMind` (spin) | Polling on activation |
| Built, fresh | `✓ NeuralMind · 2.1k nodes` (green) | Index within threshold |
| Built, stale | `⚠ NeuralMind · 2.1k nodes` (yellow) | Older than `autoBuildThresholdHours` |
| Not built | `⊘ NeuralMind` (red) | No `.neuralmind/` directory found |

Click the status bar item to open the graph view.

### Command palette (`Ctrl+Shift+P`)

| Command | What it does |
|---------|-------------|
| `NeuralMind: Query` | Prompts for a question, shows optimised context in the Output panel |
| `NeuralMind: Wakeup` | Shows the ~600-token project overview in the Output panel |
| `NeuralMind: Skeleton` | Shows a compact skeleton of the active file |
| `NeuralMind: Build Index` | Runs `neuralmind build` with a progress notification |
| `NeuralMind: Probe` | Runs `neuralmind probe` and shows recall@k/MRR/answerability |
| `NeuralMind: Open Graph View` | Opens the force-directed graph panel |
| `NeuralMind: Setup Cline Integration` | Registers MCP with Cline (restart Cline after) |
| `NeuralMind: Setup VS Code MCP Integration` | Registers MCP in `settings.json` (VS Code 1.99+) |

### Graph panel

`NeuralMind: Open Graph View` opens the same force-directed graph as `neuralmind serve` in a
VS Code WebviewPanel — force layout, community colouring, semantic search bar, live synapse
events via SSE. The panel retains its layout state when hidden.

---

## Workflow

### Day-to-day query loop

1. Open your workspace. The status bar shows current index state.
2. Press `Ctrl+Shift+P` → `NeuralMind: Query` → type your question.
3. Context appears in the **NeuralMind** Output panel (optimised, 40–70× smaller than pasting files).
4. Copy the relevant context into your AI assistant prompt, or let the MCP server inject it automatically.

### Auto-build on stale index

On workspace open, if the index is older than `neuralmind.autoBuildThresholdHours` (default: 24h),
the extension shows a notification:

> **NeuralMind: Index is stale or not built. Build now?** [Build]

Click **Build** to run `neuralmind build .` in the background.

### Hover cards (opt-in)

Enable in Settings:

```json
{
  "neuralmind.enableHover": true
}
```

Hover over any function or class definition in Python, TypeScript, Go, Rust, Java, or C/C++ to see
a compact skeleton of that file's structure — same output as `neuralmind skeleton`. Results are
cached per-file for 60 seconds. Hover cards only appear when the index is built (checked via the
status bar).

### MCP integration for VS Code 1.99+

VS Code 1.99 added native MCP client support. Register NeuralMind in one command:

```
NeuralMind: Setup VS Code MCP Integration
```

This writes the `neuralmind-mcp` entry to your VS Code `settings.json` under `mcp.servers`.
Reload the window to activate. You can also run this from the CLI:

```bash
neuralmind install-mcp . --client vscode
```

---

## Troubleshooting

**Status bar stays red / `⊘ NeuralMind`**

Run `neuralmind build .` in the terminal. The extension polls `neuralmind stats --json` every 60
seconds, so it will update automatically after the build completes.

**"NeuralMind: CLI not found" notification**

Set `neuralmind.pythonPath` to your virtualenv's Python:

```json
{
  "neuralmind.pythonPath": "/path/to/venv/bin/python"
}
```

**Graph panel shows "server not running"**

The extension starts `neuralmind serve` on a random port at activation. If the server didn't start
(e.g. no index built yet), build the index first, then run `NeuralMind: Open Graph View` again.

**Hover cards are slow**

Hover cards spawn a subprocess per file. For large projects, the first call per file takes
~0.5–2 seconds (cached for 60s after). If that's too slow, disable hover:

```json
{
  "neuralmind.enableHover": false
}
```

---

## Related use cases

- [Benchmark your repo](./benchmark-your-repo.md) — measure token reduction and recall quality
- [Cost optimisation](./cost-optimization.md) — how NeuralMind reduces AI coding costs
- [Claude Code integration](./claude-code.md) — hooks, MCP, and PostToolUse compression
