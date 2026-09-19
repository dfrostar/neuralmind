# Context Mode + NeuralMind Integration — Executive Summary

**Date:** 2026-09-16
**Decision:** Use together as complementary layers, don't merge

---

## The Stack

| Layer | Tool | Job |
|-------|------|-----|
| **Context Manager** | Context Mode (mcp) | Buffers tool outputs, prevents context flooding, survives compaction |
| **Content Retriever** | NeuralMind (mcp) | Indexes personal docs, semantic search, confidence flags |

They're not competitors. They're sequential stages:

```
Context Mode → manages the window (what the LLM doesn't see)
     ↓
NeuralMind → fills the window (what the LLM needs to see)
```

## Why Both

- **Context Mode** buffers `grep`, `test`, `build` outputs so the LLM doesn't see 315KB of raw stdout
- **NeuralMind** retrieves the right paragraph from your medical textbook when you ask about semaglutide
- **Without Context Mode:** NeuralMind's retrieval results flood the context window
- **Without NeuralMind:** Context Mode has nothing to buffer for research queries

## For Your Setup

| Machine | Context Mode | NeuralMind |
|---------|-------------|------------|
| **XPS (Linux)** | ✅ Install via npm | ✅ Already running |
| **Mac** | ✅ Install via npm | ✅ Already running |
| **Matrix fleet** | ⚠️ Needs Hermes wrapper | ✅ Already running |
| **Codex CLI** | ✅ MCP config | ❌ Not yet |
| **Cursor** | ✅ MCP config | ❌ Not yet |

## npm Install (Pending Network)

```bash
# When network is available:
npm install -g context-mode

# Claude Code (XPS):
cat >> ~/.claude/settings.json << 'EOF'
{
  "mcpServers": {
    "context-mode": { "command": "context-mode" }
  }
}
EOF

# Codex CLI:
cat >> ~/.codex/config.toml << 'EOF'
[mcp_servers.context-mode]
command = "context-mode"
EOF

# Cursor (per-project):
cat > .vscode/mcp.json << 'EOF'
{
  "servers": {
    "context-mode": { "command": "context-mode" }
  }
}
EOF
```

## For Your Local Repos

Index each with NeuralMind:
```bash
cd ~/cmmc20 && neuralmind build
cd ~/lingogame && neuralmind build
cd ~/autopilot && neuralmind build
cd ~/ai-agent-playbook-v2 && neuralmind build
```

Context Mode automatically works per-project (creates `.context-mode/` SQLite DB).

## Verdict

Use both. Context Mode for session management, NeuralMind for content retrieval. They're the two halves of the same problem.

---

*Full spec: `/home/dtfrost5/neuralmind/INTEGRATION_CONTEXT_MODE.md`*
