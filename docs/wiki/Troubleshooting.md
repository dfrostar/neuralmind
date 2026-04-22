# Troubleshooting

Common issues and solutions for NeuralMind.

## Table of Contents

- [Installation Issues](#installation-issues)
- [Build Issues](#build-issues)
- [Query Issues](#query-issues)
- [MCP Issues](#mcp-issues)
- [Scheduling & Automation Issues](#scheduling--automation-issues)
- [Performance Issues](#performance-issues)
- [Error Reference](#error-reference)
- [Getting Help](#getting-help)

---

## Installation Issues

### "Command not found: neuralmind"

**Symptoms**: Running `neuralmind` returns "command not found" or similar.

**Causes**:
1. Python scripts directory not in PATH
2. Package not installed correctly
3. Virtual environment not activated

**Solutions**:

```bash
# Check if neuralmind is installed
pip show neuralmind

# If installed, find the scripts location
python -c "import site; print(site.USER_BASE + '/bin')"

# Add to PATH (Linux/macOS)
export PATH="$HOME/.local/bin:$PATH"

# If using virtual environment, ensure it's activated
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate     # Windows
```

### "No module named 'chromadb'"

**Symptoms**: Import errors when running NeuralMind.

**Causes**:
1. Dependencies not installed
2. Corrupted installation
3. Wrong Python environment

**Solutions**:

```bash
# Reinstall with dependencies
pip uninstall neuralmind
pip install neuralmind

# Or install dependencies manually
pip install chromadb>=0.4.0 pyyaml>=6.0

# Verify installation
python -c "import chromadb; print('ChromaDB OK')"
python -c "import neuralmind; print('NeuralMind OK')"
```

### "Could not build wheels for chromadb"

**Symptoms**: Installation fails when building ChromaDB.

**Causes**:
1. Missing build dependencies
2. Outdated pip/setuptools
3. Platform-specific compilation issues

**Solutions**:

```bash
# Update pip and build tools
pip install --upgrade pip setuptools wheel

# On Linux, install build dependencies
sudo apt-get install python3-dev build-essential

# On macOS, ensure Xcode tools are installed
xcode-select --install

# Try installing again
pip install neuralmind
```

### Python Version Incompatibility

**Symptoms**: Package fails to install or import with Python version errors.

**Causes**: Python version < 3.10

**Solutions**:

```bash
# Check Python version
python --version

# If < 3.10, install newer Python
# Ubuntu/Debian
sudo apt install python3.11

# macOS with Homebrew
brew install python@3.11

# Use pyenv for version management
pyenv install 3.11.0
pyenv local 3.11.0
```

---

## Build Issues

### "graph.json not found"

**Symptoms**: `neuralmind build` fails with "graph.json not found".

**Causes**:
1. Graphify not run on the project
2. Wrong project path
3. graph.json in different location

**Solutions**:

```bash
# Generate knowledge graph first
pip install graphifyy
graphify update /path/to/project

# Verify graph exists
ls /path/to/project/graphify-out/graph.json

# Run build with correct path
neuralmind build /path/to/project
```

### "Empty graph - no nodes to embed"

**Symptoms**: Build completes but reports 0 nodes processed.

**Causes**:
1. Graphify didn't find any code files
2. Project uses unsupported languages
3. All files excluded by .gitignore

**Solutions**:

```bash
# Check graphify output
cat /path/to/project/graphify-out/GRAPH_REPORT.md

# Verify graph.json has content
python -c "import json; g=json.load(open('graphify-out/graph.json')); print(f'Nodes: {len(g.get(\"nodes\", []))}')"

# Re-run graphify with verbose output
graphify update /path/to/project --verbose
```

### "ChromaDB database locked"

**Symptoms**: Build fails with database lock errors.

**Causes**:
1. Another process using the database
2. Previous run didn't close properly
3. File permissions issue

**Solutions**:

```bash
# Kill any hanging processes
pkill -f neuralmind

# Remove lock files
rm -rf /path/to/project/graphify-out/neuralmind_db/*.lock

# Or delete and rebuild database
rm -rf /path/to/project/graphify-out/neuralmind_db
neuralmind build /path/to/project
```

### Memory Error During Build

**Symptoms**: Build crashes with MemoryError or system becomes unresponsive.

**Causes**:
1. Very large codebase
2. Insufficient RAM
3. Too many nodes to embed at once

**Solutions**:

```bash
# Check codebase size
python -c "import json; g=json.load(open('graphify-out/graph.json')); print(f'Nodes: {len(g[\"nodes\"])}')"

# For large codebases (>10,000 nodes), consider:
# 1. Close other applications to free memory
# 2. Use a machine with more RAM
# 3. Exclude test/vendor directories from graphify

# Build incrementally after initial build
neuralmind build /path/to/project  # Uses incremental updates
```

---

## Query Issues

### "Index not built"

**Symptoms**: Query fails with "index not built" or "run build first".

**Causes**:
1. `build` command never run
2. Database was deleted
3. Wrong project path

**Solutions**:

```bash
# Check if index exists
ls /path/to/project/graphify-out/neuralmind_db/

# Build the index
neuralmind build /path/to/project

# Then query
neuralmind query /path/to/project "your question"
```

### Poor/Irrelevant Search Results

**Symptoms**: Queries return context that doesn't seem relevant.

**Causes**:
1. Graph doesn't capture relevant code structure
2. Query too vague or ambiguous
3. Embeddings don't match query vocabulary

**Solutions**:

```bash
# Try more specific queries
neuralmind query /path "How does JWT authentication work?"  # Instead of "auth"

# Use search to understand what's indexed
neuralmind search /path "authentication" --n 20

# Check graph quality
cat /path/graphify-out/GRAPH_REPORT.md

# Rebuild with fresh graph
graphify update /path --force
neuralmind build /path --force
```

### Token Count Higher Than Expected

**Symptoms**: Query returns more tokens than expected (~2000+ instead of ~1000).

**Causes**:
1. Complex query triggers more communities
2. Large L1 summary from complex project
3. Many search results

**Solutions**:

```bash
# For minimal context, use wakeup
neuralmind wakeup /path  # L0 + L1 only

# Review project structure
neuralmind stats /path
```

### Context Doesn't Include Expected Code

**Symptoms**: You know specific code exists but it's not in the context.

**Causes**:
1. Code not in knowledge graph
2. Embeddings don't match query semantically
3. Token budget limits excluded it

**Solutions**:

```bash
# Search directly for the code
neuralmind search /path "function_name" --n 20

# Check if it's in the graph
python -c "
import json
g = json.load(open('graphify-out/graph.json'))
for n in g['nodes']:
    if 'function_name' in n.get('name', ''):
        print(n)
"

# If not in graph, re-run graphify
graphify update /path
```

---

## MCP Issues

### "MCP server failed to start"

**Symptoms**: Claude Desktop or Cursor can't connect to NeuralMind MCP server.

**Causes**:
1. neuralmind-mcp not in PATH
2. Python environment issues
3. Port already in use

**Solutions**:

```bash
# Test the same operation via CLI first
neuralmind query /path/to/project "test question"

# Check for port conflicts
lsof -i :8080  # If using custom port
```

### Claude Desktop Not Detecting Server

**Symptoms**: Server runs but Claude Desktop doesn't show NeuralMind tools.

**Causes**:
1. Config file syntax error
2. Wrong config file location
3. Claude Desktop needs restart

**Solutions**:

1. Verify config location:
   - macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - Windows: `%APPDATA%\Claude\claude_desktop_config.json`
   - Linux: `~/.config/Claude/claude_desktop_config.json`

2. Validate JSON syntax:
```bash
cat ~/Library/Application\ Support/Claude/claude_desktop_config.json | python -m json.tool
```

3. Ensure config is correct:
```json
{
  "mcpServers": {
    "neuralmind": {
      "command": "neuralmind-mcp"
    }
  }
}
```

4. Restart Claude Desktop completely

### "Tool call failed" in Claude

**Symptoms**: Claude shows errors when calling NeuralMind tools.

**Causes**:
1. Invalid project path
2. Index not built
3. MCP communication error

**Solutions**:

```bash
# Test the same operation via CLI first
neuralmind query /path/to/project "test question"

# Ensure index is built
neuralmind build /path/to/project

# Check MCP server logs (run manually to see output)
neuralmind-mcp 2>&1 | tee mcp.log
```

---

## Scheduling & Automation Issues

### Windows Task Scheduler: "Access is denied"

**Symptoms**: Running `Register-ScheduledTask` fails with permission error.

**Causes**:
1. PowerShell not running as Administrator
2. User doesn't have Task Scheduler permissions

**Solutions**:

```powershell
# MUST run PowerShell as Administrator
# Right-click PowerShell → "Run as administrator"

# Then set execution policy
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# Now register the task
$trigger = New-ScheduledTaskTrigger -Daily -At 2:00am
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-NoProfile -ExecutionPolicy Bypass -File C:\scripts\run-neuralmind-all.ps1"
Register-ScheduledTask -TaskName "NeuralMind Suite" -Trigger $trigger -Action $action -RunLevel Highest
```

### Scheduled Task Not Running

**Symptoms**: Task appears in Task Scheduler but never executes.

**Causes**:
1. Script path is incorrect
2. Python/neuralmind not in PATH when task runs
3. Task disabled or trigger misconfigured
4. Network not available (if using network-dependent features)

**Solutions**:

```powershell
# Verify task exists and is enabled
Get-ScheduledTask -TaskName "NeuralMind*" | Select-Object TaskName, State

# Check task history
Get-ScheduledTaskInfo -TaskName "NeuralMind Suite"

# Test running manually
Start-ScheduledTask -TaskName "NeuralMind Suite"

# Check results and logs
Get-ScheduledTaskInfo -TaskName "NeuralMind Suite" | Select-Object LastRunTime, LastTaskResult
```

**If task runs but fails silently:**

1. Use full path to Python in script:
```powershell
# Bad: powershell.exe -File script.ps1
# Good: C:\Users\username\AppData\Local\Programs\Python\Python311\python.exe script.py
```

2. Add error handling to script:
```powershell
$ErrorActionPreference = "Stop"
try {
    cd C:\path\to\project
    neuralmind wakeup . 2>&1 | Tee-Object -FilePath "C:\logs\neuralmind.log"
} catch {
    Add-Content -Path "C:\logs\error.log" -Value "Error: $_"
    exit 1
}
```

3. Test the script directly:
```powershell
# Run in PowerShell (not scheduled) to see errors
C:\scripts\run-neuralmind-all.ps1
```

### Auto-Discovery Not Finding Projects

**Symptoms**: Scheduled task runs but finds "0 initialized projects".

**Causes**:
1. Projects don't have `neuralmind.db/` directory
2. Wrong root path in script
3. Path permissions issue

**Solutions**:

```powershell
# Verify projects are initialized
Get-ChildItem -Path "C:\Users\dtfro\claudecode" -Directory | ForEach-Object {
    $hasIndex = Test-Path (Join-Path $_.FullName "neuralmind.db")
    Write-Host "$($_.Name): $($hasIndex ? 'Ready' : 'NOT INITIALIZED')"
}

# Initialize missing projects
cd "C:\path\to\project"
graphify update .
neuralmind build .
```

### Cloud Repo Sync Failing

**Symptoms**: Cloud sync task runs but doesn't update repos.

**Causes**:
1. Git not in PATH
2. SSH keys not configured
3. Repository URL incorrect
4. No internet connectivity

**Solutions**:

```powershell
# Verify git is accessible
git --version

# Test cloning manually
cd C:\temp
git clone https://github.com/yourname/your-repo.git

# If SSH required, ensure keys are set up
ssh -T git@github.com

# Check repo URLs in sync script
# Should be: https://github.com/owner/repo.git
# NOT: git@github.com:owner/repo.git (unless SSH configured)
```

### Logs Not Being Created

**Symptoms**: Scheduled tasks run but no log files appear in expected directory.

**Causes**:
1. Log directory path wrong or doesn't exist
2. Permissions issue with log directory
3. Task failed before logging started

**Solutions**:

```powershell
# Create log directory if missing
$logDir = "$env:USERPROFILE\Documents\neuralmind-logs"
if (!(Test-Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir | Out-Null
}

# Check directory permissions
Get-Acl $logDir

# Manually test logging
$logFile = "$logDir\test.log"
"Test message" | Tee-Object -FilePath $logFile
Get-Content $logFile
```

---

## Performance Issues

### Slow Build Times

**Symptoms**: Initial build takes a very long time (>5 minutes for medium projects).

**Causes**:
1. Large codebase with many nodes
2. Slow embedding model
3. Disk I/O bottleneck

**Solutions**:

```bash
# Check node count
neuralmind stats /path 2>/dev/null || \
  python -c "import json; print(len(json.load(open('graphify-out/graph.json'))['nodes']))"

# For subsequent builds, incremental is automatic
neuralmind build /path  # Only embeds changed nodes

# Force rebuild only when necessary
neuralmind build /path --force  # Re-embeds everything
```

### Slow Query Times

**Symptoms**: Queries take >1 second to return.

**Causes**:
1. Large vector database
2. Cold start (first query)
3. Slow disk access

**Solutions**:

```bash
# First query is slower (loading model), subsequent are faster
time neuralmind query /path "test"
time neuralmind query /path "another test"  # Should be faster

# Move database to SSD if on HDD — rebuild after moving
mv graphify-out/neuralmind_db /ssd/path/
neuralmind build /path --force
```

### High Memory Usage

**Symptoms**: NeuralMind consumes excessive RAM.

**Causes**:
1. Large embedding model loaded
2. Many nodes in graph
3. ChromaDB caching

**Solutions**:

```python
# Memory is primarily from:
# - Embedding model: ~100-200MB (unavoidable)
# - ChromaDB: Scales with node count
# - Graph data: Loaded entirely

# For very large projects, consider:
# 1. Excluding test/vendor directories from graphify
# 2. Running on a machine with more RAM
# 3. Using a remote ChromaDB instance
```

---

## Error Reference

### Exit Codes

| Code | Meaning | Common Causes |
|------|---------|---------------|
| 0 | Success | Normal completion |
| 1 | General error | Various runtime errors |
| 2 | Invalid arguments | Wrong CLI arguments |
| 3 | Graph not found | graphify not run |
| 4 | Index not built | build command not run |
| 5 | Database error | ChromaDB issues |

### Common Exception Messages

| Exception | Meaning | Solution |
|-----------|---------|----------|
| `FileNotFoundError: graph.json` | Knowledge graph missing | Run `graphify update` |
| `RuntimeError: Index not built` | Embeddings not generated | Run `neuralmind build` |
| `chromadb.errors.InvalidCollectionException` | Database corruption | Delete and rebuild database |
| `MemoryError` | Insufficient RAM | Reduce project size or increase RAM |
| `ValueError: Empty query` | Query string is blank | Provide a valid question |

---

## Diagnostic Commands

### Health Check Script

```bash
#!/bin/bash
# neuralmind_health.sh - Check NeuralMind installation

echo "=== NeuralMind Health Check ==="

# Check installation
echo -n "NeuralMind installed: "
python -c "import neuralmind; print('✓')" 2>/dev/null || echo "✗"

# Check dependencies
echo -n "ChromaDB: "
python -c "import chromadb; print(f'✓ v{chromadb.__version__}')" 2>/dev/null || echo "✗"

echo -n "PyYAML: "
python -c "import yaml; print('✓')" 2>/dev/null || echo "✗"

# Check CLI
echo -n "CLI available: "
which neuralmind >/dev/null && echo "✓" || echo "✗"

# Check graphify
echo -n "Graphify installed: "
which graphify >/dev/null && echo "✓" || echo "✗"

# Check MCP server
echo -n "MCP server: "
which neuralmind-mcp >/dev/null && echo "✓" || echo "✗"

echo ""
echo "=== Version Info ==="
python -c "import neuralmind; print(f'NeuralMind: installed')" 2>/dev/null
python -c "import chromadb; print(f'ChromaDB: {chromadb.__version__}')" 2>/dev/null
python --version
```

### Project Diagnostic

```bash
#!/bin/bash
# project_diagnostic.sh - Check project setup

PROJECT="${1:-.}"

echo "=== Project: $PROJECT ==="

# Check graph
if [ -f "$PROJECT/graphify-out/graph.json" ]; then
    echo "✓ Knowledge graph exists"
    NODE_COUNT=$(python -c "import json; print(len(json.load(open('$PROJECT/graphify-out/graph.json'))['nodes']))")
    echo "  Nodes: $NODE_COUNT"
else
    echo "✗ Knowledge graph missing (run: graphify update $PROJECT)"
fi

# Check index
if [ -d "$PROJECT/graphify-out/neuralmind_db" ]; then
    echo "✓ NeuralMind index exists"
    DB_SIZE=$(du -sh "$PROJECT/graphify-out/neuralmind_db" | cut -f1)
    echo "  Size: $DB_SIZE"
else
    echo "✗ NeuralMind index missing (run: neuralmind build $PROJECT)"
fi

# Test query
if [ -d "$PROJECT/graphify-out/neuralmind_db" ]; then
    echo ""
    echo "=== Test Query ==="
    time neuralmind wakeup "$PROJECT" | head -20
fi
```

---

## Getting Help

### Before Asking for Help

1. **Check this troubleshooting guide** for your specific issue
2. **Run diagnostic commands** to gather system info
3. **Check the logs** for specific error messages
4. **Try the minimal reproduction** - does it fail with a simple test?

### Reporting Issues

When opening a GitHub issue, include:

```markdown
**Environment**
- OS: [e.g., Ubuntu 22.04, macOS 14, Windows 11]
- Python version: [output of `python --version`]
- NeuralMind version: [output of `pip show neuralmind`]
- ChromaDB version: [output of `pip show chromadb`]

**Steps to Reproduce**
1. ...
2. ...

**Expected Behavior**
What should happen.

**Actual Behavior**
What actually happens.

**Error Output**
```
Paste full error message here
```

**Additional Context**
- Project size (number of nodes)
- First time or worked before?
- Any recent changes?
```

### Resources

- **GitHub Issues**: [Report bugs](https://github.com/dfrostar/neuralmind/issues)
- **Discussions**: [Ask questions](https://github.com/dfrostar/neuralmind/discussions)
- **Documentation**: [Wiki](https://github.com/dfrostar/neuralmind/wiki)

---

## See Also

- [Installation](Installation.md) - Setup instructions
- [CLI Reference](CLI-Reference.md) - Command documentation
- [API Reference](API-Reference.md) - Python API
