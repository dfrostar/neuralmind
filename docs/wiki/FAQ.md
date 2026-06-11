# Frequently Asked Questions

Quick answers to common NeuralMind questions.

---

## Installation & Setup

### "I installed NeuralMind but `neuralmind` command not found"

**Solution:**
```bash
# Check if installed
pip show neuralmind

# If installed, find where
python -c "import site; print(site.USER_BASE + '/bin')"

# Add to PATH (Linux/macOS)
export PATH="$HOME/.local/bin:$PATH"

# Add to PATH (Windows PowerShell)
$env:Path += ";$env:APPDATA\Python\Python311\Scripts"
```

---

### "graphify build fails with 'unknown command'"

*(Only relevant if you installed the optional graphify backend — since
v0.15.0 NeuralMind builds the code graph itself.)*

**Solution:**
The command changed in newer versions. Use:
```bash
graphify update .    # New (v1.2+)
# NOT: graphify build .
```

---

### "neuralmind build takes forever on large codebase"

**Solutions:**
```bash
# 1. First build is slow (one-time)
#    Subsequent builds are incremental and fast

# 2. Exclude unnecessary files
#    Add to neuralmind.toml:
# [build]
# exclude_patterns = ["*.test.js", "node_modules/", "dist/"]

# 3. Use faster backend
neuralmind build . --backend lancedb  # Faster than ChromaDB
```

---

## Usage & Queries

### "How do I search across multiple files?"

**Answer:** NeuralMind searches semantically across your entire codebase automatically.

```bash
# Just ask a question about the whole project
neuralmind query . "How is data validation handled throughout the codebase?"

# It will find relevant validation code in multiple files
```

---

### "Can I search for exact strings?"

**Answer:** Use `neuralmind search` for semantic search:
```bash
neuralmind search . "authentication"   # Semantic: finds related code
```

For exact string matching, use your editor or `grep`:
```bash
grep -r "authenticate" src/
```

---

### "Output is too long/verbose"

**Solutions:**
```bash
# 1. Ask more specific questions
neuralmind query . "How does password validation work?"  # Better than "How does auth work?"

# 2. Use JSON output and parse it
neuralmind query . "What endpoints are available?" --json | jq '.results | length'

# 3. Narrow scope
neuralmind query src/auth/ "How does login work?"  # Limits to one directory
```

---

### "Why is the same question giving different results?"

**Reasons:**
1. **Index changed** — Code was updated, rebuild with `neuralmind build .`
2. **Learning kicked in** — NeuralMind learns from your queries (improvement!)
3. **Randomness** — Small variations in embedding similarity

**Solution:** Results should be consistent. If they vary significantly, rebuild:
```bash
neuralmind build . --force
```

---

## Performance & Scaling

### "Is NeuralMind slow for large codebases?"

**No!** 
- Initial build is 1-2 min per 10K nodes
- Queries are <100ms
- Works for 1M+ LOC codebases

**For large projects:**
```bash
# Use PostgreSQL backend (scales to 10M+ nodes)
neuralmind build . --backend postgres --db-url postgresql://...
```

---

### "How much disk space does the index need?"

**Rough estimates:**
- 100K LOC → 50-100 MB
- 500K LOC → 200-500 MB
- 1M LOC → 500MB-2GB
- 10M LOC → 5-20GB

**Compress if needed:**
```bash
# Delete old indexes
rm -rf neuralmind.db

# Rebuild with optimization
neuralmind build . --optimize
```

---

## Features & Capabilities

### "Does NeuralMind support my language?"

**Supported:**
- Python, JavaScript/TypeScript, Java, C++, Go, Rust, C#, PHP, Ruby, SQL

**Partial support:**
- Other languages (graphify has limited AST extraction)

**If not supported:**
```bash
# Use `--format any` to treat as plaintext
neuralmind build . --format any

# Still works, just less precise
```

---

### "Can NeuralMind read test files?"

**Yes, but consider excluding them:**
```toml
# neuralmind.toml
[build]
exclude_patterns = [
    "*.test.js",
    "*.spec.py",
    "test/",
    "tests/"
]
```

**Why?** Test code clutters the index without adding understanding.

---

### "Does NeuralMind work with private packages?"

**Yes!**
```bash
# If your project uses private packages, NeuralMind indexes:
# 1. Your code (always)
# 2. Local node_modules / site-packages (yes)
# 3. External PyPI/npm packages (no, stays private)

# Nothing leaves your machine
```

---

## Collaboration & Teams

### "How do team members share a NeuralMind index?"

**Option 1: Local per-developer (simplest)**
```bash
# Each developer on their machine
neuralmind build .
neuralmind install-hooks .
```
Pros: Simple, fully private  
Cons: Index duplication

**Option 2: Shared PostgreSQL backend (enterprise)**
```bash
# Setup: Central PostgreSQL database
# Each developer points to it:
neuralmind build . --backend postgres --db-url postgresql://...
```
Pros: Single source of truth, auditable  
Cons: Requires infrastructure

---

### "Can I restrict who can use NeuralMind?"

**Yes, with MCP server + RBAC:**
```bash
# Launch MCP with access control
neuralmind-mcp . --rbac-enabled \
  --admin-users alice@company.com \
  --developer-users bob@company.com,charlie@company.com \
  --viewer-users intern@company.com
```

---

## Security & Compliance

### "Does NeuralMind send data to external servers?"

**No.** 
- ✅ 100% local processing
- ✅ No cloud APIs
- ✅ No telemetry
- ✅ Zero data exfiltration

---

### "How do I ensure no secrets leak into the index?"

```bash
# 1. Scan for secrets before building
neuralmind scan-for-secrets .

# 2. Fix exposed secrets
# (Remove from code, regenerate tokens)

# 3. Build with redaction enabled
neuralmind build . --redact-secrets

# 4. Verify
neuralmind search . "password"  # Should return no results
```

---

### "Can I use NeuralMind in a regulated industry?"

**Yes!** NeuralMind is built for compliance:
- ✅ NIST AI RMF audit trail
- ✅ SOC 2 compliance mapping
- ✅ GDPR-compliant (local processing)
- ✅ HIPAA-friendly (no data exfiltration)

---

## Troubleshooting

### "NeuralMind build fails with 'No module named chromadb'"

```bash
pip install --upgrade neuralmind

# Or install with dev extras (testing/linting tools)
pip install "neuralmind[dev]"
```

---

### "Queries return irrelevant results"

**Solutions:**
1. **Rebuild index** — Code changed, index is stale
   ```bash
   neuralmind build . --force
   ```

2. **Ask better questions** — Be more specific
   ```bash
   # Bad: "How does it work?"
   # Good: "How does user authentication work?"
   ```

3. **Enable learning** — NeuralMind improves with use
   ```bash
   neuralmind learn .
   ```

---

### "Why does my `serve` canvas stay quiet when I edit files?" *(v0.6.0+)*

You ran `neuralmind serve`, opened the graph view, edited a file in
your editor — and no node pulsed. The live feed (v0.6.0) depends on
two paths working: the in-process event bus, and the cross-process
JSONL bridge. When the canvas is silent, one of these is the
culprit. Check in this order:

1. **`.neuralmind/` directory exists in the project root.** The
   JSONL bridge writes to `<project>/.neuralmind/events.jsonl`,
   which the watcher and `serve` both need to find. If the directory
   doesn't exist (fresh clone, or you blew it away):

   ```bash
   neuralmind build .   # creates .neuralmind/ alongside graphify-out/
   ```

2. **`NEURALMIND_EVENT_LOG` is not set to `0`.** This env var
   disables the JSONL writer. If it's set in your shell config or
   the parent process of either `serve` or `watch`, the in-process
   feed still works for the *same* process but cross-process events
   never reach the canvas.

   ```bash
   env | grep NEURALMIND_EVENT_LOG   # should be empty or =1
   unset NEURALMIND_EVENT_LOG        # clear it if set
   ```

3. **Both processes target the same project root.** A common gotcha:
   `neuralmind serve` was started from `~/projects/foo` and
   `neuralmind watch` from `~/projects/foo/src/`. They write to
   *different* `.neuralmind/events.jsonl` files and never see each
   other. Run both from the project root, or pass an explicit
   `project_path`:

   ```bash
   neuralmind serve /abs/path/to/project &
   neuralmind watch /abs/path/to/project &
   ```

4. **The file watcher is actually running.** If you're relying on
   Claude Code's `PostToolUse` hooks for file events, those only
   fire on tool calls — they won't see your manual editor saves.
   For editor-driven pulses, start `neuralmind watch` separately:

   ```bash
   neuralmind watch . --quiet &
   ```

5. **The browser tab actually has the SSE stream open.** Open the
   browser devtools network tab and look for a long-lived request
   to `/api/events`. If it's missing or 404, refresh the page; if it
   401s, your token expired (re-open the URL `serve` printed).

6. **The synapse store is being reinforced.** If no agent is
   calling `neuralmind_query` or any other NeuralMind MCP tool, the
   synapse store has nothing to publish — the canvas pulses only
   when something actually happens. Trigger one manually:

   ```bash
   neuralmind query . "test query"
   ```

   You should see a pulse within ~1s.

If the canvas still stays quiet after all six, that's a bug — open
an issue with the output of `neuralmind stats .` and a
description of what you tried.

---

### "MCP server won't start"

```bash
# Check port is free
lsof -i :8000

# Run with debug output
NEURALMIND_DEBUG=1 neuralmind-mcp . --port 8000

# Check configuration
neuralmind backend-check
```

---

### "Can't connect to PostgreSQL backend"

```bash
# Test connection
psql -h db.company.com -U neuralmind -d neuralmind -c "SELECT 1;"

# Check URL format
# postgresql://username:password@hostname:port/database

# Set connection timeout
neuralmind build . --backend postgres --db-timeout 30
```

---

## Pricing & Licensing

### "Is NeuralMind free?"

**Yes!**
- ✅ MIT License (fully open source)
- ✅ No subscription
- ✅ No usage limits
- ✅ Self-hosted (no cloud costs)

---

### "Can I use NeuralMind commercially?"

**Yes!** MIT License allows commercial use:
- ✅ Use in products
- ✅ Use in services
- ✅ Use in enterprises
- ✅ Modify for your needs

Just include the license text.

---

### "Is commercial support available?"

Coming in v1.0 (Q1 2027):
- Priority bug fixes
- Deployment consulting
- Custom integrations
- SLA guarantees

---

## Comparisons

### "How is NeuralMind different from Cursor @codebase?"

| Feature | NeuralMind | Cursor |
|---------|-----------|--------|
| Works everywhere | ✅ Yes | ❌ Cursor only |
| 100% offline | ✅ Yes | ❌ Cloud |
| Token reduction | 5-10× | 2-3× |
| Cost | Free | Paid (Cursor) |
| Open source | ✅ Yes | ❌ No |

---

### "Why not just use long context windows?"

```
Claude 3.5 Sonnet:
- Input: $3/1M tokens
- Output: $15/1M tokens

Traditional (50K tokens):
- Cost: $0.15 per query

With NeuralMind (800 tokens):
- Cost: $0.0024 per query
- Savings: 60× cheaper

Even with 200K token context limit available,
NeuralMind is 10× cheaper because the prompt is small.
```

---

### "Does NeuralMind replace Copilot?"

**No, they're complementary:**
- **Copilot** — Code completions, inline suggestions
- **NeuralMind** — Code understanding, context retrieval

Use both together for maximum productivity.

---

## Contact & Support

### "Where can I ask questions?"

- 📖 [GitHub Discussions](https://github.com/dfrostar/neuralmind/discussions)
- 🐛 [Report Issues](https://github.com/dfrostar/neuralmind/issues)
- 📧 Email: contact@company.com

### "How do I report a bug?"

```bash
# 1. Reproduce the issue
# 2. Collect debug info
neuralmind --version
python --version
uname -a

# 3. Open GitHub issue with:
#    - Clear title
#    - Reproduction steps
#    - Expected vs actual behavior
#    - Debug output
```

### "Can I contribute?"

**Yes!** See [CONTRIBUTING.md](https://github.com/dfrostar/neuralmind/blob/main/CONTRIBUTING.md)

