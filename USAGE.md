# NeuralMind Usage Guide

> Complete guide to features, use cases, and scheduling routines for NeuralMind

## Table of Contents

- [What is NeuralMind?](#what-is-neuralmind)
- [Key Features](#key-features)
- [The 4-Layer Architecture](#the-4-layer-architecture)
- [Quick Start](#quick-start)
- [Use Cases](#use-cases)
- [CLI Command Reference](#cli-command-reference)
- [Scheduling Routines](#scheduling-routines)
- [ROI Calculator](#roi-calculator)
- [MCP Server Integration](#mcp-server-integration)
- [Troubleshooting](#troubleshooting)
- [Brain-like Continual Learning](#brain-like-continual-learning)

---

## What is NeuralMind?

**NeuralMind** is an intelligent context system that dramatically reduces the tokens needed when working with AI coding assistants like Claude, GPT-4, and Cursor.

### The Core Problem

```
You: "How does authentication work in my codebase?"

❌ Traditional approach: Load entire codebase → 50,000 tokens → $0.15-$3.75/query
✅ NeuralMind approach: Load smart context → 766 tokens → $0.002-$0.06/query
```

### The Solution

NeuralMind creates a semantic understanding of your codebase and provides query-aware context that includes only what's relevant to your question.

---

## Key Features

| Feature | Description | Benefit |
|---------|-------------|--------|
| **4-Layer Context** | Progressive disclosure architecture | Only loads what's relevant |
| **Semantic Search** | Vector embeddings for meaning-based lookup | Finds related code by concept |
| **Query-Aware** | Different queries get different context | Maximizes relevance |
| **CLI Tool** | Simple command-line interface | Easy integration |
| **MCP Server** | Direct IDE integration | Works with Claude Desktop/Cursor |
| **Auto-Updates** | Scheduled maintenance | Always current knowledge |

---

## The 4-Layer Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ Layer 0: Project Identity (~100 tokens) - ALWAYS LOADED     │
│ • Project name, type, tech stack                            │
│ • Entry points, main patterns                               │
├─────────────────────────────────────────────────────────────┤
│ Layer 1: Architecture Summary (~300 tokens) - ALWAYS LOADED │
│ • Module overview, key components                           │
│ • Dependencies, data flow                                   │
├─────────────────────────────────────────────────────────────┤
│ Layer 2: Relevant Modules (~300 tokens) - QUERY-SPECIFIC    │
│ • Code clusters related to your question                    │
│ • Community detection based on code relationships           │
├─────────────────────────────────────────────────────────────┤
│ Layer 3: Semantic Search (~300 tokens) - QUERY-SPECIFIC     │
│ • Direct keyword and concept matches                        │
│ • Vector similarity search results                          │
└─────────────────────────────────────────────────────────────┘

Total: ~800-1,100 tokens vs 50,000+ for full codebase
```

### How It Works

1. **Graphify** analyzes your codebase and creates a knowledge graph
2. **NeuralMind** creates vector embeddings of all code entities
3. **When you query**, it selects only relevant context using semantic similarity
4. **You get** focused, accurate context that fits in any LLM's context window

---

## Quick Start

### Step 1: Install

```bash
pip install neuralmind graphifyy
```

### Step 2: Generate Knowledge Graph

```bash
cd your-project
graphify update .
```

### Step 3: Build Neural Index

```bash
neuralmind build .
```

### Step 4: Query Your Codebase

```bash
# Get project overview
neuralmind wakeup .

# Ask specific questions
neuralmind query . "How does authentication work?"
neuralmind query . "What are the main components?"
neuralmind query . "How is data validated?"
```

### Step 5: Use with AI

```bash
# Copy output to clipboard (macOS)
neuralmind query . "How does X work?" | pbcopy

# Copy output to clipboard (Linux)
neuralmind query . "How does X work?" | xclip -selection clipboard

# Copy output to clipboard (Windows PowerShell)
neuralmind query . "How does X work?" | Set-Clipboard

# Then paste into Claude/ChatGPT/Cursor
```

---

## Use Cases

### Use Case 1: Daily Development Questions

**When**: You need to ask AI about your codebase multiple times per day

**How**:
```bash
# Get context for your question
neuralmind query . "How does the payment processing work?"

# Copy output → Paste into Claude/ChatGPT → Get accurate answer
```

**Benefit**: 100 queries/day goes from $450/month → $7/month with Claude 3.5 Sonnet

---

### Use Case 2: New Developer Onboarding

**When**: New team member needs to understand the codebase

**How**:
```bash
# Generate project overview
neuralmind wakeup . > project_overview.md

# Answer common onboarding questions
neuralmind query . "What are the main API endpoints?" > docs/api_overview.md
neuralmind query . "How is the database structured?" > docs/database.md
neuralmind query . "What authentication method is used?" > docs/auth.md
neuralmind query . "How do I set up my local development environment?" > docs/setup.md
```

**Benefit**: New devs get accurate answers without constantly asking senior devs

---

### Use Case 3: Code Review Context

**When**: Reviewing a PR and need to understand related code

**How**:
```bash
# Understand the feature being changed
neuralmind query . "How does the user registration flow work?"

# Find related code that might be affected
neuralmind search . "validation middleware"

# Understand the test coverage
neuralmind query . "What tests exist for user registration?"
```

**Benefit**: Better code reviews with full context awareness

---

### Use Case 4: Documentation Generation

**When**: Creating or updating documentation

**How**:
```bash
# Export structured understanding
neuralmind wakeup . > docs/ARCHITECTURE.md

# Generate API documentation
neuralmind query . "List all API endpoints with their purposes" >> docs/API.md

# Generate component documentation
neuralmind query . "Describe each React component and its purpose" >> docs/COMPONENTS.md
```

**Benefit**: AI-assisted documentation that's accurate to actual code

---

### Use Case 5: CI/CD Integration

**When**: Automated context generation in pipelines

**How**:
```yaml
# .github/workflows/update-context.yml
name: Update AI Context
on:
  push:
    branches: [main]

jobs:
  update-context:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install NeuralMind
        run: pip install neuralmind graphifyy
      
      - name: Update knowledge graph
        run: graphify update .
      
      - name: Build neural index
        run: neuralmind build .
      
      - name: Generate AI context file
        run: neuralmind wakeup . > AI_CONTEXT.md
      
      - name: Commit updated context
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add AI_CONTEXT.md
          git diff --staged --quiet || git commit -m "docs: update AI context"
          git push
```

**Benefit**: Always up-to-date context file in your repo

---

### Use Case 6: IDE Integration (MCP Server)

**When**: Direct AI integration in Claude Desktop or Cursor

**How**:
```json
// ~/.config/claude/claude_desktop_config.json (macOS/Linux)
// %APPDATA%\Claude\claude_desktop_config.json (Windows)
{
  "mcpServers": {
    "neuralmind": {
      "command": "neuralmind-mcp",
      "args": ["/path/to/your/project"]
    }
  }
}
```

**Benefit**: Claude Desktop automatically gets relevant context for every question

---

## CLI Command Reference

| Command | Purpose | Example |
|---------|---------|--------|
| `neuralmind build .` | Build/rebuild neural index | First-time setup, after major changes |
| `neuralmind query . "..."` | Query with natural language | Daily usage |
| `neuralmind wakeup .` | Get project overview | Start new AI conversations |
| `neuralmind search . "..."` | Direct semantic search | Find specific code entities |
| `neuralmind benchmark .` | Measure token reduction | Verify cost savings |
| `neuralmind stats .` | Show index statistics | Check index health |

### Detailed Command Usage

#### `neuralmind build`

Builds or rebuilds the neural index from your knowledge graph.

```bash
# Build index for current directory
neuralmind build .

# Build index for specific project
neuralmind build /path/to/project

# Rebuild after code changes
graphify update . && neuralmind build .
```

**When to use**: After initial setup, after significant code changes, weekly maintenance.

#### `neuralmind query`

Asks a natural language question and returns relevant context.

```bash
# Basic query
neuralmind query . "How does authentication work?"

# Query and save to file
neuralmind query . "What are all the API endpoints?" > api_context.md

# Query and copy to clipboard (macOS)
neuralmind query . "How is data validated?" | pbcopy
```

**When to use**: Every time you want to ask AI about your code.

#### `neuralmind wakeup`

Returns the project overview (L0 + L1 layers) for starting new conversations.

```bash
# Get wakeup context
neuralmind wakeup .

# Save as project overview
neuralmind wakeup . > PROJECT_OVERVIEW.md
```

**When to use**: Starting a new Claude/ChatGPT conversation about your project.

#### `neuralmind search`

Direct semantic search without the full context layers.

```bash
# Search for related code
neuralmind search . "payment processing"
neuralmind search . "error handling middleware"
neuralmind search . "database models"
```

**When to use**: When you want to find specific code entities quickly.

#### `neuralmind benchmark`

Measures token reduction for sample queries.

```bash
# Run benchmark
neuralmind benchmark .

# Example output:
# Query: "How does authentication work?" - 739 tokens (67.7x reduction)
# Query: "What are the API endpoints?" - 748 tokens (66.8x reduction)
# Average: 766 tokens (65.3x reduction)
```

**When to use**: Verifying your cost savings, demonstrating value to team.

#### `neuralmind stats`

Shows index statistics.

```bash
# View stats
neuralmind stats .

# Example output:
# Nodes: 241
# Edges: 203
# Communities: 93
# Index size: 12.4 MB
```

**When to use**: Checking index health, monitoring project growth.

#### `neuralmind learn`

Runs the opt-in continual learning scaffold using local memory traces.

```bash
neuralmind learn .
```

If `NEURALMIND_LEARNING=0`, the command exits as a safe no-op.

### Brain-like Continual Learning

See **[docs/brain_like_learning.md](docs/brain_like_learning.md)** for behavior, storage paths, consent, and env-var controls.

---

## Scheduling Routines

### When to Update Your Index

| Scenario | Recommended Action | Frequency |
|----------|-------------------|----------|
| Active development | Git hook on commit | Every commit |
| Team project | Automated CI/CD | On merge to main |
| Stable codebase | Scheduled maintenance | Weekly |
| Before code review | Manual update | As needed |
| After major refactor | Full rebuild | Immediately |

### Git Hook Setup (Recommended for Active Development)

Automatically update the index after every commit:

```bash
# Create post-commit hook
cat > .git/hooks/post-commit << 'EOF'
#!/bin/bash
echo "🧠 Updating NeuralMind index..."
graphify update . --quiet 2>/dev/null
neuralmind build . --quiet 2>/dev/null
echo "✓ NeuralMind index updated"
EOF

# Make it executable
chmod +x .git/hooks/post-commit
```

### Cron Job Setup (Recommended for Servers)

```bash
# Edit crontab
crontab -e

# Daily update at 6 AM
0 6 * * * cd /path/to/project && graphify update . && neuralmind build . >> /var/log/neuralmind.log 2>&1

# Weekly update on Monday at 3 AM
0 3 * * 1 cd /path/to/project && graphify update . && neuralmind build . >> /var/log/neuralmind.log 2>&1
```

### CI/CD Integration (Recommended for Teams)

```yaml
# .github/workflows/neuralmind-update.yml
name: Update NeuralMind Index

on:
  push:
    branches: [main]
  schedule:
    - cron: '0 6 * * *'  # Daily at 6 AM UTC

jobs:
  update:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install neuralmind graphifyy
      - run: graphify update .
      - run: neuralmind build .
      - run: neuralmind stats .
```

### Maintenance Checklist

Weekly maintenance routine:

```bash
#!/bin/bash
# weekly_maintenance.sh

echo "🔧 NeuralMind Weekly Maintenance"
echo "================================"

# Update knowledge graph
echo "1. Updating knowledge graph..."
graphify update .

# Rebuild neural index
echo "2. Rebuilding neural index..."
neuralmind build .

# Show stats
echo "3. Current statistics:"
neuralmind stats .

# Run benchmark
echo "4. Benchmark results:"
neuralmind benchmark .

echo ""
echo "✅ Maintenance complete!"
```

---

## ROI Calculator

### Cost Comparison by Model

| Model | Input Price | Without NeuralMind | With NeuralMind | Per-Query Savings |
|-------|-------------|-------------------|-----------------|------------------|
| Claude 3.5 Sonnet | $3/1M tokens | $0.15/query | $0.0023/query | $0.1477 (98.5%) |
| GPT-4o | $5/1M tokens | $0.25/query | $0.0038/query | $0.2462 (98.5%) |
| GPT-4.5 | $75/1M tokens | $3.75/query | $0.0574/query | $3.6926 (98.5%) |
| Claude Opus | $15/1M tokens | $0.75/query | $0.0115/query | $0.7385 (98.5%) |
| Gemini 2.5 Pro | $2.50/1M tokens | $0.125/query | $0.0019/query | $0.1231 (98.5%) |

### Monthly Savings Calculator

| Daily Queries | Claude 3.5 Sonnet | GPT-4o | GPT-4.5 | Claude Opus |
|---------------|-------------------|--------|---------|-------------|
| 10 queries/day | $44/month | $74/month | $1,107/month | $221/month |
| 50 queries/day | $221/month | $369/month | $5,539/month | $1,108/month |
| 100 queries/day | **$443/month** | **$738/month** | **$11,078/month** | **$2,216/month** |
| 500 queries/day | $2,216/month | $3,693/month | $55,389/month | $11,078/month |

### Annual Savings

| Usage Level | Annual Savings (Claude 3.5) | Annual Savings (GPT-4.5) |
|-------------|----------------------------|-------------------------|
| Light (10/day) | $531 | $13,284 |
| Medium (50/day) | $2,658 | $66,468 |
| Heavy (100/day) | **$5,316** | **$132,936** |
| Enterprise (500/day) | $26,580 | $664,668 |

---

## MCP Server Integration

### What is MCP?

Model Context Protocol (MCP) allows AI assistants to directly query external tools. NeuralMind's MCP server lets Claude Desktop and Cursor automatically get relevant code context.

### Setup for Claude Desktop

1. Install NeuralMind (the MCP server is included by default since v0.5.0):
```bash
pip install neuralmind
```

2. Add to Claude Desktop config:

**macOS/Linux**: `~/.config/claude/claude_desktop_config.json`
**Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "neuralmind": {
      "command": "neuralmind-mcp",
      "args": ["/path/to/your/project"]
    }
  }
}
```

3. Restart Claude Desktop

### Available MCP Tools

| Tool | Description |
|------|-------------|
| `neuralmind_wakeup` | Get project overview |
| `neuralmind_query` | Query with natural language |
| `neuralmind_search` | Direct semantic search |
| `neuralmind_skeleton` | Graph-backed file view |
| `neuralmind_recursive_query` | Decompose complex questions |
| `neuralmind_query_docs` | Search reference documents |
| `neuralmind_build` | Rebuild index |
| `neuralmind_stats` | Show index statistics |
| `neuralmind_benchmark` | Run token benchmark |

### Usage in Claude Desktop

Once configured, Claude will automatically have access to your codebase context. Just ask questions like:

- "How does authentication work in this project?"
- "What are all the API endpoints?"
- "Explain the database schema"

Claude will use NeuralMind to get relevant context before answering.

---

## 📄 Document RAG (Reference Documents)

NeuralMind can index reference documents (PDFs, DOCX, TXT, HTML) alongside your code. Documents are converted to markdown and stored in a separate ChromaDB collection.

### Setup

```bash
# Install dependencies
pip install pypdf mammoth

# Convert documents to markdown
# Place PDFs/DOCX in a folder, then:
python -c "
from pathlib import Path
import subprocess
for f in Path('~/docs/legal').expanduser().glob('*'):
    if f.suffix in ['.pdf', '.docx', '.txt', '.html']:
        subprocess.run(['python', 'convert_script.py', str(f)])
"
```

### Indexing

```bash
# Build the document index
python -m neuralmind.doc_indexer build /path/to/project

# Stats
python -m neuralmind.doc_indexer stats /path/to/project
```

### Searching

Via MCP:
```
neuralmind_query_docs(project_path="/path/to/project", question="HIPAA requirements")
```

Via CLI:
```bash
python -m neuralmind.doc_indexer query /path/to/project "patient consent form"
```

### How It Works

1. Documents are converted to markdown and stored in `docs/reference/`
2. Markdown is chunked into ~1000-char segments with 200-char overlap
3. Chunks are embedded and stored in a separate ChromaDB collection
4. Queries search both code AND document indexes for comprehensive answers

### Limitations

- Document index is separate from code index (different ChromaDB collections)
- Scanned PDFs need OCR first (`ocrmypdf` before converting)
- Markdown files are not processed by graphify AST extraction

---

## Troubleshooting

### Common Issues

#### "No graph.json found"

```bash
# Solution: Run graphify first
graphify update .
neuralmind build .
```

#### "Index out of date"

```bash
# Solution: Rebuild the index
graphify update .
neuralmind build .
```

#### "ChromaDB error"

```bash
# Solution: Clear and rebuild
rm -rf graphify-out/neuralmind_db
neuralmind build .
```

#### "Module not found"

```bash
# Solution: Reinstall
pip uninstall neuralmind
pip install neuralmind
```

### Getting Help

- **GitHub Issues**: https://github.com/dfrostar/neuralmind/issues
- **Wiki**: https://github.com/dfrostar/neuralmind/wiki
- **Discussions**: https://github.com/dfrostar/neuralmind/discussions

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT License - see [LICENSE](LICENSE) for details.
