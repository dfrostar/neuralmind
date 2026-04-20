# NeuralMind Project Setup Guide

This guide covers first-time setup of NeuralMind for any project, regardless of your IDE, editor, or AI coding platform. Works with **Claude Code, GitHub Copilot (Codex), Cursor, VSCode, Cline, Continue, and any other AI assistant**.

## ⚡ 30-Second Setup (Minimal)

Just want to get started? Run this:

```bash
pip install neuralmind graphifyy
cd your-project
graphify update . && neuralmind build .
neuralmind query . "your question"
```

Done. That's the minimum to start querying your codebase.

---

## 📊 Which Setup Path Should I Take?

```
Are you using Claude Code?
├─ YES → Full setup (hooks for 90% token savings)
│         graphify update . && neuralmind build . && neuralmind install-hooks .
│
└─ NO → Which platform?
    ├─ GitHub Copilot → CLI only (copy-paste output)
    ├─ Cursor / Cline / Continue → MCP (auto-discovery)
    ├─ VSCode / JetBrains → CLI (terminal commands)
    └─ ChatGPT / Gemini → CLI (manual paste)
```

**Details below**, or jump to:
- [Claude Code Setup](#claude-code-full-integration)
- [GitHub Copilot Setup](#github-copilot-codex)
- [Other Platforms](#how-to-use-neuralmind-across-platforms)

---

## Prerequisites

**Version Requirements:**

| Tool | Minimum | Recommended | Check |
|------|---------|-------------|-------|
| Python | 3.10 | 3.11+ | `python --version` |
| neuralmind | 0.2.0+ | Latest | `neuralmind --version` |
| graphifyy | 0.1.0+ | Latest | `graphify --version` |

Install/upgrade:
```bash
pip install --upgrade neuralmind graphifyy
```

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

Claude Code has first-class support for NeuralMind with **native hooks** for 90% token compression on Read/Bash/Grep output.

**Full Setup (Recommended):**
```bash
cd your-project
graphify update .
neuralmind build .
neuralmind install-hooks .
```

**Result:** Queries cost ~$0.002 each (vs $0.15 without NeuralMind)

**Minimal Setup (if short on time):**
```bash
graphify update .
neuralmind build .
```

Still get retrieval optimization, but miss the 90% hook compression. Upgrade anytime:
```bash
neuralmind install-hooks .
```

**Usage:**
```bash
# Query directly
neuralmind query . "How does authentication work?"

# Or let Claude call it automatically via MCP (if configured)
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

## Platform Comparison & Cost Savings

| Platform | Method | Token Reduction | Setup Time | Best For |
|----------|--------|----------|---------|---------|
| **Claude Code** | CLI + Hooks | **~90%** ⭐ | 5 min | Full optimization, passive compression |
| **Cursor** | MCP | ~65% | 3 min | Native MCP support like Claude Code |
| **Cline/Continue** | MCP | ~65% | 3 min | Extensible editors, seamless tools |
| **Copilot** | CLI (copy-paste) | ~40% | 1 min | Lightweight, no installation overhead |
| **ChatGPT/Gemini** | CLI (copy-paste) | ~40% | 1 min | No IDE integration needed |
| **VSCode + AI** | CLI (terminal) | ~40% | 2 min | Manual but flexible workflows |

**Token Reduction Examples** (100 queries/month, Claude Sonnet):
- **Claude Code with hooks**: $450/month → $45/month (**$405 saved**)
- **Cursor with MCP**: $450/month → $157/month (**$293 saved**)
- **Copilot CLI mode**: $450/month → $270/month (**$180 saved**)

---

## Setup by Platform

### Claude Code (Full Integration)

---

## Setup Timing & Performance

**Expected Duration:**

| Step | Duration | Notes |
|------|----------|-------|
| `pip install` | 30 sec - 2 min | One-time, depends on internet/disk |
| `graphify update .` | 5 sec - 5 min | Depends on codebase size (AST is fast) |
| `neuralmind build .` | 10 sec - 10 min | Embedding generation; larger codebases take longer |
| `neuralmind install-hooks .` | 2 sec | Just writes config files |
| **Total** | **~1-20 minutes** | Most projects < 5 minutes |

**If setup is taking > 20 minutes:**

1. **Check progress:**
   ```bash
   # See what neuralmind is doing
   neuralmind build . --verbose
   ```

2. **For large codebases (>50K LOC):**
   ```bash
   # Build incrementally
   neuralmind build . --batch-size 100
   ```

3. **Exclude unneeded files:**
   ```bash
   # Create .neuralmindignore (like .gitignore)
   echo "node_modules/" >> .neuralmindignore
   echo "dist/" >> .neuralmindignore
   neuralmind build . --force
   ```

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

### "Build is slow / running out of memory"

Cause: Large codebase or insufficient RAM.

Solutions:
```bash
# Option 1: Exclude non-essential directories
echo "node_modules/" >> .neuralmindignore
echo ".venv/" >> .neuralmindignore
neuralmind build . --force

# Option 2: Reduce batch size
neuralmind build . --batch-size 50

# Option 3: Check available memory
free -h  # Linux
vm_stat  # macOS
Get-WmiObject Win32_OperatingSystem | Select TotalVisibleMemorySize  # Windows
```

### "Results don't seem relevant"

Cause: Index is out of sync with code.

Solution:
```bash
# Full rebuild
graphify update . --full
neuralmind build . --force

# Then test
neuralmind query . "your question"
```

---

## Brain-Like Learning (New in v0.2.0)

After setup, NeuralMind can learn your project patterns. This is **optional but recommended**.

### How It Works
```bash
# After setup, just use it normally
neuralmind query . "How does authentication work?"

# First time, you'll see:
# "NeuralMind would like to learn from your queries. Enable? (y/n)"

# Say yes. Then NeuralMind collects patterns from your queries.
# After 10 similar queries: neuralmind stats --memory
# "Top patterns: auth/ → validation/ → middleware/"
```

### Quick Reference
| Command | Purpose |
|---------|---------|
| `neuralmind stats --memory` | See collected patterns |
| `neuralmind learn . --dry-run` | Preview what would be learned (v0.2.1+) |
| `neuralmind memory reset .` | Clear learning for this project |
| `NEURALMIND_LEARNING=0` | Disable learning globally |

### See More
👉 **[Full Brain-Like Learning Guide](../brain_like_learning.md)** — Privacy, examples, troubleshooting

---

## Next Steps

1. **Enable learning** (optional) — Say "yes" to the first-time prompt
2. **[Brain-Like Learning](../brain_like_learning.md)** — How learning improves your context
3. **[CLI Reference](CLI-Reference)** — All commands and options
4. **[Integration Guide](Integration-Guide)** — Deep dive on MCP and hooks
5. **[Usage Guide](Usage-Guide)** — Real-world examples
6. **[Troubleshooting](Troubleshooting)** — Common issues

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
