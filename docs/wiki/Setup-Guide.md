# NeuralMind Project Setup Guide

This guide covers first-time setup of NeuralMind for any project, regardless of your IDE, editor, or AI coding platform. Works with **Claude Code, GitHub Copilot (Codex), Cursor, VSCode, Cline, Continue, and any other AI assistant**.

## Quick Answer: "How do I set up NeuralMind?"

Three commands, run once per project:

```bash
# 1. Generate knowledge graph from code and docs
graphify update .

# 2. Build the neural index
neuralmind build .

# 3. Install hooks (optional, adds passive token savings in Claude Code)
neuralmind install-hooks .
```

That's it. Your project is ready to use with NeuralMind.

---

## Prerequisites

Before starting, ensure you have:

1. **A project worth indexing** — NeuralMind shines on projects with >2,000 lines of code or significant documentation
2. **graphify installed** — `pip install graphifyy`
3. **neuralmind installed** — `pip install neuralmind`

Quick verification:
```bash
neuralmind --version
graphify --version
```

---

## First-Time Setup (Run Once Per Project)

### Step 1: Generate Knowledge Graph

The knowledge graph extracts code structure and relationships:

```bash
cd your-project
graphify update .
```

**Cost:**
- Code-only extraction: **Free** (uses AST)
- With documentation/papers: **LLM tokens** (extracts semantic meaning from docs)

**Output:** `graph.json` in your project root

### Step 2: Build the Neural Index

Create embeddings for semantic search:

```bash
neuralmind build .
```

**Cost:** Free (uses embeddings, no LLM calls)

**Output:** `.neuralmind/` directory with embeddings database

### Step 3: Install Hooks (Optional, Claude Code Only)

For **Claude Code users only**: Install PostToolUse hooks to compress Read/Bash/Grep output before Claude sees it:

```bash
neuralmind install-hooks .
```

This saves an additional **~90% tokens** on tool outputs.

**For other platforms** (Copilot, Cursor, VSCode, etc.): Skip this step — use the CLI or MCP server instead.

---

## When to Rebuild the Index

Your index can become stale if code/docs change. Rebuild strategically:

| Change Type | Command | Cost | When |
|-------------|---------|------|------|
| **Code files added/changed** | `neuralmind build . --force` | Free | After feature work |
| **Docs/papers added/changed** | `graphify update . && neuralmind build .` | LLM tokens | After documentation updates |
| **Major refactor** (new modules) | `graphify update . --full && neuralmind build .` | Full cost | After structural changes |
| **Nothing changed** | (skip) | $0 | Don't rebuild unnecessarily |

**Don't rebuild for:**
- Config changes (.env, settings)
- Data files (JSON, CSV, databases)
- Dependencies (.txt, lock files)

---

## How to Use NeuralMind Across Platforms

### Claude Code (Full Integration)

Claude Code has first-class support for NeuralMind:

```bash
# After setup, use the CLI
neuralmind query . "How does authentication work?"

# Or use MCP tool (if .mcp.json configured)
# Claude will automatically call neuralmind tools
```

**Recommended setup:**
```bash
neuralmind build .
neuralmind install-hooks .  # adds passive token compression
```

### GitHub Copilot (Codex)

Copilot can use NeuralMind via CLI output. Pipe context into your chat:

```bash
# Get project overview
neuralmind wakeup . | pbcopy  # macOS
neuralmind wakeup . | xclip   # Linux
neuralmind wakeup . | clip    # Windows

# Get query-specific context
neuralmind query . "your question" | pbcopy
```

Then paste into your Copilot chat.

**Advanced:** Use in GitHub Actions to generate context for CI:
```yaml
- run: pip install neuralmind graphifyy
- run: neuralmind wakeup . > CONTEXT.md
- run: # Use CONTEXT.md in your workflow
```

### Cursor

Cursor supports MCP servers. Add to `.cursor/settings.json`:

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

Then:
```bash
neuralmind build .
# Cursor will auto-discover neuralmind tools
```

### VSCode with Cline or Continue

Both integrate MCP servers. Add to your MCP config:

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

Setup:
```bash
neuralmind build .
# Restart your extension
```

### JetBrains IDEs with Copilot / AI Assistant

Use CLI commands in the integrated terminal:

```bash
neuralmind wakeup .          # project overview
neuralmind query . "..."     # query-specific context
neuralmind skeleton src/foo.py  # compact file view
```

Copy output into your AI chat.

### Command-Line Only (ChatGPT, Gemini, Claude.ai)

Perfect for manual workflows:

```bash
# Get project overview (~600 tokens, free)
neuralmind wakeup .

# Get query-specific context
neuralmind query . "How does X work?"

# Get compact file view
neuralmind skeleton src/auth/handlers.py
```

Pipe or copy-paste output into your AI chat.

---

## What to Put in CLAUDE.md

If using NeuralMind in Claude Code, document it for future sessions:

```markdown
## Context Management

This project uses NeuralMind for intelligent code retrieval.

### Quick Query
\`\`\`bash
neuralmind query . "your question"
\`\`\`

### Navigation
1. **For code questions:** Use `neuralmind query . "question"`
2. **For file understanding:** Use `neuralmind skeleton path/to/file.py`
3. **For project overview:** Use `neuralmind wakeup .`
4. **For raw files:** Only if neuralmind has no answer

### Index Health
- **Last built:** [auto-update via git hook]
- **Code files:** [number]
- **Docs:** [number]

### When to Rebuild
After major code changes:
\`\`\`bash
neuralmind build . --force
\`\`\`
```

---

## What Makes NeuralMind Successful

✅ **Graph stays current** — Rebuild after structural code changes. Stale graph = stale retrieval.

✅ **Hooks installed** (Claude Code only) — PostToolUse hooks do the real token savings. Without them, you only get retrieval benefits.

✅ **Smart rebuild strategy** — Don't rebuild on every file change. Only rebuild when code structure changes.

✅ **Sized right for your project** — NeuralMind shines on projects >2,000 lines. Tiny projects fit in context anyway.

---

## Automating Rebuilds

### Git Hook (Recommended)

Auto-rebuild on each commit:

```bash
neuralmind init-hook .
```

This creates `.git/hooks/post-commit` that runs:
```bash
graphify update . --quiet
neuralmind build . --quiet
```

### Cron Job

Daily rebuild at 6 AM:

```bash
# Linux/macOS
0 6 * * * cd /path/to/project && graphify update . --quiet && neuralmind build . --quiet
```

### CI/CD Pipeline

Rebuild on push (GitHub Actions example):

```yaml
- name: Update NeuralMind index
  run: |
    pip install neuralmind graphifyy
    graphify update .
    neuralmind build .
    
- name: Save context for docs
  run: neuralmind wakeup . > AI_CONTEXT.md
```

---

## Platform Comparison

| Platform | Method | MCP Support | Hooks Support | Best For |
|----------|--------|-----------|---|---------|
| **Claude Code** | CLI, MCP, Hooks | ✅ Yes | ✅ Yes (native) | Full optimization |
| **Copilot** | CLI (copy-paste) | ❌ No | ❌ No | Lightweight integration |
| **Cursor** | MCP | ✅ Yes | ❌ No | Similar to Claude Code |
| **Cline/Continue** | MCP | ✅ Yes | ❌ No | Extensible editors |
| **VSCode + Copilot** | CLI (copy-paste) | ❌ No | ❌ No | Manual workflows |
| **ChatGPT/Gemini** | CLI (copy-paste) | ❌ No | ❌ No | No integration needed |

---

## Troubleshooting Setup

### "graph.json not found"

Cause: Graphify hasn't been run.

Solution:
```bash
pip install graphifyy
graphify update .
neuralmind build .
```

### "No module named neuralmind"

Cause: neuralmind not installed.

Solution:
```bash
pip install neuralmind
neuralmind --version
```

### "Build failed: chromadb error"

Cause: ChromaDB not installed or outdated.

Solution:
```bash
pip install --upgrade neuralmind
```

### "Hooks won't install"

Cause: Claude Code-specific issue. Hooks only work in Claude Code.

Solution: If using other platforms, skip `install-hooks` and use CLI or MCP instead.

### "Index is stale / results are wrong"

Cause: Code changed but index wasn't rebuilt.

Solution:
```bash
neuralmind build . --force
# or if docs changed:
graphify update .
neuralmind build .
```

---

## Next Steps

1. **[CLI Reference](CLI-Reference)** — All commands and options
2. **[Integration Guide](Integration-Guide)** — Deep dive on MCP and hooks
3. **[Usage Guide](Usage-Guide)** — Real-world examples
4. **[Troubleshooting](Troubleshooting)** — Common issues

---

## One-Liner Setup

To set up NeuralMind on any new project in one go:

```bash
pip install neuralmind graphifyy && graphify update . && neuralmind build .
```

For Claude Code with full optimization:

```bash
pip install neuralmind graphifyy && graphify update . && neuralmind build . && neuralmind install-hooks .
```
