# Setup Guide

First-time setup for NeuralMind on any platform in under 5 minutes.

NeuralMind is a two-phase token optimizer for AI coding agents: a 4-layer semantic index that answers code questions in ~800 tokens, plus PostToolUse hooks that compress `Read`/`Bash`/`Grep` output before your agent sees it. Typical combined reduction is **5–10× vs baseline** Claude Code / Cursor / any-LLM usage.

See [Use Cases](Use-Cases) if you're unsure whether NeuralMind fits your workflow, or [Comparisons](Comparisons) for how it differs from Cursor `@codebase`, Copilot, Claude Projects, long context, and others.

## Table of Contents

- [30-Second Setup](#30-second-setup)
- [Choose Your Workflow](#choose-your-workflow)
- [Platform Setup](#platform-setup)
  - [Claude Code](#claude-code)
  - [Claude Desktop](#claude-desktop)
  - [Cursor / Cline / Continue](#cursor--cline--continue)
  - [Any LLM (copy-paste)](#any-llm-copy-paste)
- [Keeping the Index Fresh](#keeping-the-index-fresh)
- [Verify Everything Works](#verify-everything-works)
- [Requirements](#requirements)

---

## 30-Second Setup

```bash
# 1. Install NeuralMind and graphify
pip install neuralmind graphifyy

# 2. Go to your project
cd /path/to/your-project

# 3. Generate the knowledge graph
graphify update .

# 4. Build the neural index
neuralmind build .

# 5. Test it
neuralmind wakeup .
```

You should see a compact project overview. If you do, NeuralMind is ready.

---

## Choose Your Workflow

| Your tool | What to set up | Guide |
|-----------|---------------|-------|
| **Claude Code** | CLI + PostToolUse hooks + MCP | [Claude Code](#claude-code) |
| **Claude Desktop** | MCP server | [Claude Desktop](#claude-desktop) |
| **Cursor / Cline / Continue** | MCP server | [Cursor / Cline / Continue](#cursor--cline--continue) |
| **ChatGPT / Gemini / any LLM** | CLI (copy-paste output) | [Any LLM](#any-llm-copy-paste) |

---

## Platform Setup

### Claude Code

Claude Code gets the full two-phase optimization: smart retrieval **and** compressed tool outputs.

```bash
pip install neuralmind graphifyy

cd your-project
graphify update .
neuralmind build .

# Install PostToolUse compression hooks (compresses Read/Bash/Grep output)
neuralmind install-hooks .

# Optional: auto-rebuild index on every git commit
neuralmind init-hook .
```

**Use it:**

Inside a Claude Code session, call NeuralMind tools directly:

```
neuralmind_wakeup(".")          # project overview at session start
neuralmind_query(".", "How does auth work?")   # focused context
neuralmind_skeleton("src/auth.py")             # compact file view
```

Or add a `.mcp.json` at your project root so Claude Code loads NeuralMind automatically:

```json
{
  "mcpServers": {
    "neuralmind": {
      "command": "neuralmind-mcp",
      "args": ["."]
    }
  }
}
```

---

### Claude Desktop

```bash
pip install "neuralmind[mcp]" graphifyy

cd your-project
graphify update .
neuralmind build .
```

Add NeuralMind to your Claude Desktop config:

- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **Linux**: `~/.config/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "neuralmind": {
      "command": "neuralmind-mcp",
      "args": ["/absolute/path/to/your-project"]
    }
  }
}
```

Restart Claude Desktop. NeuralMind tools (`neuralmind_wakeup`, `neuralmind_query`, etc.) will appear automatically.

> **Tip:** If NeuralMind is installed in a virtual environment, use the full path:
> `"/path/to/venv/bin/neuralmind-mcp"`

---

### Cursor / Cline / Continue

```bash
pip install "neuralmind[mcp]" graphifyy

cd your-project
graphify update .
neuralmind build .
```

Add to your MCP config (location varies by tool — check your tool's docs):

```json
{
  "mcpServers": {
    "neuralmind": {
      "command": "neuralmind-mcp"
    }
  }
}
```

When using MCP tools, always pass the `project_path` parameter pointing to your project root.

---

### Any LLM (copy-paste)

No special integration needed. Just pipe CLI output into your chat interface.

```bash
# Copy project overview (macOS)
neuralmind wakeup . | pbcopy

# Copy project overview (Linux)
neuralmind wakeup . | xclip -selection clipboard

# Copy project overview (Windows PowerShell)
neuralmind wakeup . | Set-Clipboard

# Ask a specific question and copy the answer
neuralmind query . "How does the payment system work?" | pbcopy
```

Paste the output at the start of any Claude/ChatGPT/Gemini conversation.

---

## Keeping the Index Fresh

### Option A — Git hook (recommended for active projects)

```bash
# Install managed hook (idempotent, coexists with other hooks)
neuralmind init-hook .
```

The index rebuilds automatically after every commit.

### Option B — Manual

```bash
# After code changes
graphify update .
neuralmind build .
```

### Option C — Scheduled (CI/CD or cron)

```yaml
# .github/workflows/update-neuralmind.yml
- run: pip install neuralmind graphifyy
- run: graphify update .
- run: neuralmind build .
```

---

## Verify Everything Works

```bash
# Check version
neuralmind --help

# Check index stats
neuralmind stats .

# Run token-reduction benchmark
neuralmind benchmark .
```

Expected output from `stats`:
```
Project: your-project
Built: True
Nodes: <number>
```

If `Built: False`, run `graphify update . && neuralmind build .` again.

---

## Requirements

| Requirement | Version |
|-------------|---------|
| Python | 3.10 or higher |
| NeuralMind | `pip install neuralmind` |
| graphify | `pip install graphifyy` |
| MCP support (optional) | `pip install "neuralmind[mcp]"` |

> **Supported OS:** Linux, macOS, Windows 10+

---

## Next Steps

- **[CLI Reference](CLI-Reference)** — All commands and options
- **[Scheduling Guide](Scheduling-Guide)** — Automate audits & queries on Windows, Linux, macOS, or GitHub Actions
- **[Learning Guide](Learning-Guide)** — Teach NeuralMind your query patterns
- **[Integration Guide](Integration-Guide)** — CI/CD, VS Code, JetBrains
- **[Troubleshooting](Troubleshooting)** — Common issues and fixes
