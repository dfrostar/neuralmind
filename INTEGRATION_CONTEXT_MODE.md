# Context Mode + NeuralMind Integration Plan

**Date:** 2026-09-16
**Status:** Implementation guide — npm install pending network access

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    AI Coding Agent                       │
│              (Claude Code / Codex / Cursor)              │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌─────────────────┐     ┌─────────────────────────┐   │
│  │  Context Mode   │     │     NeuralMind           │   │
│  │  (MCP Server)   │     │     (MCP Server)         │   │
│  ├─────────────────┤     ├─────────────────────────┤   │
│  │ • Buffers tool  │     │ • Indexes personal docs  │   │
│  │   outputs       │     │ • Semantic search (ONNX) │   │
│  │ • SQLite FTS5   │     │ • BM25 hybrid           │   │
│  │ • Session       │     │ • Confidence flags       │   │
│  │   continuity    │     │ • Chapter-level retrieval │   │
│  │ • 98% context   │     │                          │   │
│  │   reduction     │     │                          │   │
│  └─────────────────┘     └─────────────────────────┘   │
│           │                        │                    │
│           ▼                        ▼                    │
│  ┌─────────────────┐     ┌─────────────────────────┐   │
│  │  Per-project    │     │  Personal knowledge      │   │
│  │  SQLite DB      │     │  base (books, notes,     │   │
│  │  (tool outputs) │     │  proprietary docs)       │   │
│  └─────────────────┘     └─────────────────────────┘   │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

## What Each Does

| Dimension | Context Mode | NeuralMind |
|-----------|-------------|------------|
| **Scope** | Session-scoped (this conversation) | Persistent (your entire library) |
| **Input** | Tool output during the session | Pre-existing documents, books, notes |
| **Value** | Prevents context flooding | Surfaces relevant content from your knowledge base |
| **Search** | FTS5 keyword matching | Semantic (ONNX embeddings) + BM25 |
| **Continuity** | ✅ Survives compaction | ❌ Stateless per query |
| **Prose/books** | ❌ Code-only | ✅ Chapter-level + medical terminology |
| **Install** | `npm i -g context-mode` | `pip install neuralmind` |

## Integration Points

### 1. Claude Code (XPS Machine)

Both servers run as MCP servers. Context Mode buffers tool outputs; NeuralMind retrieves from your docs.

**Config:** `~/.claude/settings.json` or `.claude/settings.json` in project

```json
{
  "mcpServers": {
    "context-mode": {
      "command": "context-mode"
    },
    "neuralmind": {
      "command": "neuralmind-mcp"
    }
  }
}
```

**Hooks:** Context Mode auto-generates `AGENTS.md` routing instructions.

### 2. Codex CLI

**Config:** `~/.codex/config.toml`

```toml
[mcp_servers.context-mode]
command = "context-mode"

[mcp_servers.neuralmind]
command = "neuralmind-mcp"
```

### 3. Cursor

**Config:** `.vscode/mcp.json` in project root

```json
{
  "servers": {
    "context-mode": {
      "command": "context-mode"
    },
    "neuralmind": {
      "command": "neuralmind-mcp"
    }
  }
}
```

### 4. Hermes Agent Fleet (Matrix)

Context Mode can be exposed as a tool for all agents in the fleet. This requires wrapping the MCP server as a Hermes tool.

**Config:** Add to `~/.hermes/config.yaml` or per-agent config

```yaml
mcp_servers:
  context-mode:
    command: context-mode
  neuralmind:
    command: neuralmind-mcp
```

### 5. Other Local Repos

For repos like `cmmc20`, `lingogame`, `autopilot`, `ai-agent-playbook-v2`:

**NeuralMind** can index each repo:
```bash
cd ~/cmmc20 && neuralmind build
cd ~/lingogame && neuralmind build
cd ~/autopilot && neuralmind build
cd ~/ai-agent-playbook-v2 && neuralmind build
```

**Context Mode** works per-project — each repo gets its own SQLite DB.

---

## Installation Steps

### Step 1: Install Context Mode

```bash
# When network is available:
npm install -g context-mode

# Verify:
context-mode --version
```

### Step 2: Configure Per-Project

For each project where you want both tools:

```bash
# Create MCP config
cat > .claude/settings.json << 'EOF'
{
  "mcpServers": {
    "context-mode": { "command": "context-mode" },
    "neuralmind": { "command": "neuralmind-mcp" }
  }
}
EOF

# Build NeuralMind index
neuralmind build
```

### Step 3: Verify

```bash
# Check Context Mode is running
ctx stats

# Check NeuralMind is responding
neuralmind query "What is this project about?"
```

---

## Usage Patterns

### Pattern 1: Long Coding Session

1. Context Mode buffers all tool outputs (grep, test, build) into SQLite
2. When context fills up, it summarizes instead of dumping raw output
3. NeuralMind retrieves relevant code/docs from your knowledge base
4. Both work together: Context Mode manages the window, NeuralMind fills it

### Pattern 2: Research Across Docs

1. NeuralMind retrieves relevant chapters from your books/notes
2. Context Mode buffers the retrieval results for session continuity
3. After compaction, Context Mode restores what NeuralMind found

### Pattern 3: Multi-Repo Work

1. NeuralMind indexes each repo separately
2. Context Mode buffers tool output per-project
3. Query across repos: `neuralmind query "How does auth work?" --project cmmc20`

---

## Known Limitations

| Limitation | Workaround |
|------------|------------|
| Context Mode is code-only | Use NeuralMind for prose/books |
| NeuralMind has no session continuity | Use Context Mode for session state |
| npm install needs network | Install when network is available |
| Context Mode MCP not yet in Hermes | Manual config for each agent |

---

## Next Steps

1. Install Context Mode when network allows
2. Configure Claude Code on XPS with both MCP servers
3. Index all local repos with NeuralMind
4. Test session continuity across compaction
5. Evaluate Hermes fleet integration

---

*Drafted by Hermes Agent. Pending npm install for full implementation.*
