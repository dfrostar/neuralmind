# Upgrading NeuralMind

**Step-by-step guides for upgrading between NeuralMind versions.**

---

## Quick Reference

| From | To | Effort | Breaking Changes |
|------|---|--------|------------------|
| v0.3.x | v0.4.x | 5 min | Minor (CLI args) |
| v0.4.x | v0.4.y | 1 min | None |
| v0.4.x | v0.5.0 | 30 min | Yes (MCP server) |
| v0.5.x | v1.0.0 | 1 hour | Possibly (API) |

---

## v0.4.x → v0.4.y (Patch Release)

**Effort:** 5 minutes | **Risk:** Very Low

These are bug fixes and security patches—no breaking changes.

```bash
# Upgrade pip package
pip install --upgrade neuralmind

# Verify version
neuralmind --version

# Rebuild index (recommended after patch)
neuralmind build . --force
```

**After upgrade:**
- ✅ No configuration changes needed
- ✅ Existing indexes are compatible
- ✅ No commands changed

---

## v0.3.x → v0.4.x (Minor Version)

**Effort:** 10 minutes | **Risk:** Low | **Breaking:** Minor

### What Changed

**CLI:**
- `graphify build` → `graphify update` (graphify 1.2+ only)
- `--old-format` flag deprecated (use `--json` instead)
- New `--backend` option for embedding selection

**Indexes:**
- Graph format updated (auto-converted)
- Embeddings regenerated (one-time)

### Upgrade Steps

**1. Backup current index**
```bash
cd /path/to/project
cp -r neuralmind.db neuralmind.db.backup
cp -r .neuralmind .neuralmind.backup
```

**2. Upgrade NeuralMind**
```bash
pip install --upgrade neuralmind

# Verify version
neuralmind --version
# Output: neuralmind v0.4.x
```

**3. Upgrade graphify** (if needed)
```bash
cd graphify
git pull origin main
pip install -e .

# Verify version
graphify --version
# Should be v1.2.0+
```

**4. Update code graph**
```bash
cd /path/to/project
graphify update .

# Verify graph updated
ls -la graphify-out/graph.json
```

**5. Rebuild NeuralMind index**
```bash
neuralmind build . --force

# This regenerates embeddings with v0.4 format
# Takes ~same time as original build
```

**6. Verify everything works**
```bash
# Test basic commands
neuralmind stats .
neuralmind wakeup .
neuralmind query . "What is the main purpose of this project?"

# Compare results with backup if needed
```

**7. Clean up backup (if confident)**
```bash
rm -rf neuralmind.db.backup .neuralmind.backup
```

### Rollback (if needed)

```bash
# Uninstall v0.4
pip uninstall neuralmind

# Reinstall v0.3
pip install neuralmind==0.3.x

# Restore backup
rm -rf neuralmind.db .neuralmind
cp -r neuralmind.db.backup neuralmind.db
cp -r .neuralmind.backup .neuralmind

# You're back to v0.3
```

---

## v0.4.x → v0.5.0 (Major Version)

**Effort:** 30 minutes | **Risk:** Medium | **Breaking:** Yes

### What's Changing

**MCP Server:**
- Tool API redesigned (new parameter format)
- Authentication moved to middleware layer
- Response format updated

**Deprecations:**
- Python 3.9 support dropped (use 3.10+)
- Old embedding backend API removed
- Legacy query format deprecated

**New Features:**
- PostgreSQL pgvector support
- Advanced monitoring dashboard
- Kubernetes ready

### Upgrade Steps

**1. Read Breaking Changes**
```
See: docs/v0.4-to-v0.5-MIGRATION.md
```

**2. Backup Everything**
```bash
cd /path/to/project

# Backup index
cp -r neuralmind.db neuralmind.db.v0.4.backup
cp -r .neuralmind .neuralmind.v0.4.backup

# Backup configuration
cp neuralmind.toml neuralmind.toml.v0.4.backup
```

**3. Check Python Version**
```bash
python --version
# Must be 3.10 or higher

# If not, upgrade:
# See: https://python.org/downloads/
```

**4. Upgrade NeuralMind**
```bash
pip install neuralmind==0.5.0

neuralmind --version
# Output: neuralmind v0.5.0
```

**5. Update Configuration** (if using custom config)
```toml
# neuralmind.toml - v0.5.0 changes

[build]
# New option: backend specification
backend = "chromadb"  # or "postgres", "lancedb"

[backends.postgres]
# New! PostgreSQL support
connection_string = "postgresql://user:pass@host/db"
pool_size = 10

# Deprecated (remove if present):
# embedding_model = "sentence-transformers"  # Now specified elsewhere
```

**6. Rebuild Index**
```bash
neuralmind build . --force

# This rebuilds with v0.5 format
# May take longer due to new optimizations
```

**7. Update MCP Configuration** (if using MCP)

**Old (v0.4):**
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

**New (v0.5):**
```json
{
  "mcpServers": {
    "neuralmind": {
      "command": "neuralmind-mcp",
      "args": ["."],
      "env": {
        "NEURALMIND_VERSION": "0.5.0",
        "NEURALMIND_BACKEND": "chromadb"
      }
    }
  }
}
```

**8. Test All Commands**
```bash
# Test basic commands
neuralmind stats .
neuralmind wakeup .
neuralmind query . "What does this project do?"

# Test MCP (if applicable)
# Start Claude Code and verify tools load

# Test new features
neuralmind backend-list
neuralmind backend-check
```

**9. Verify Performance**
```bash
neuralmind benchmark .

# Compare against v0.4 baseline
# Should see similar or better token reduction
```

**10. Update Documentation** (for your team)
```bash
# Create migration guide for your usage
echo "# Upgrading to NeuralMind v0.5" > docs/NEURALMIND_UPGRADE.md
```

### Known Issues in v0.5.0

| Issue | Workaround | Status |
|-------|-----------|--------|
| Slow first query | First query optimizes cache; subsequent queries fast | Fixed in v0.5.1 |
| pgvector connection timeout | Set `NEURALMIND_DB_TIMEOUT=30` | Use v0.5.2+ |
| Old .neuralmind format causes error | Delete `.neuralmind/cache` and rebuild | Normal behavior |

### Rollback (if needed)

```bash
# Uninstall v0.5
pip uninstall neuralmind

# Reinstall v0.4
pip install neuralmind==0.4.x

# Restore backup
rm -rf neuralmind.db .neuralmind neuralmind.toml
cp -r neuralmind.db.v0.4.backup neuralmind.db
cp -r .neuralmind.v0.4.backup .neuralmind
cp neuralmind.toml.v0.4.backup neuralmind.toml

# Rebuild with v0.4
neuralmind build . --force
```

---

## v0.5.x → v1.0.0 (Stable Release)

**Effort:** 1 hour | **Risk:** Low-Medium | **Breaking:** Minimal

v1.0.0 is the first stable release with API guarantees.

### What to Expect

- ✅ Stable API (changes rare and documented)
- ✅ Long-term support (2 years)
- ✅ Production-ready
- ✅ Better documentation
- ✅ Commercial support available

### Upgrade Steps

```bash
# Simple upgrade path from v0.5.x
pip install neuralmind==1.0.0

# Rebuild recommended (one-time)
neuralmind build . --force

# No configuration changes needed
```

---

## Mass Upgrade (Multiple Projects)

**Upgrading 10+ projects at once:**

```bash
#!/bin/bash
# upgrade-all-projects.sh

PROJECTS_ROOT="$HOME/projects"
NEURALMIND_VERSION="0.4.2"

for project_dir in "$PROJECTS_ROOT"/*; do
    if [ ! -d "$project_dir" ]; then
        continue
    fi
    
    echo "Upgrading: $project_dir"
    
    cd "$project_dir"
    
    # Check if neuralmind initialized
    if [ ! -d "neuralmind.db" ]; then
        echo "  → Skipping (not initialized)"
        continue
    fi
    
    # Backup
    cp -r neuralmind.db "neuralmind.db.backup-$(date +%Y%m%d)"
    
    # Rebuild
    neuralmind build . --force
    
    # Verify
    if neuralmind stats . > /dev/null 2>&1; then
        echo "  → ✅ Success"
    else
        echo "  → ❌ Failed (rolled back)"
        rm -rf neuralmind.db
        cp -r "neuralmind.db.backup-$(date +%Y%m%d)" neuralmind.db
    fi
done

echo "Upgrade complete!"
```

Run it:
```bash
chmod +x upgrade-all-projects.sh
./upgrade-all-projects.sh
```

---

## Version Support Matrix

| Version | Status | Python | End of Support |
|---------|--------|--------|---|
| **v1.0.x** | LTS | 3.10-3.13+ | 2029-01 |
| **v0.5.x** | Current | 3.10-3.13 | 2026-10 |
| **v0.4.x** | LTS | 3.10-3.13 | 2026-10 |
| **v0.3.x** | Maintained | 3.10-3.12 | 2026-04 |
| **v0.2.x** | EOL | 3.10-3.11 | ❌ 2025-10 |

---

## Getting Help

- **Issues:** [GitHub Issues](https://github.com/dfrostar/neuralmind/issues)
- **Discussions:** [GitHub Discussions](https://github.com/dfrostar/neuralmind/discussions)
- **Docs:** [Setup Guide](https://github.com/dfrostar/neuralmind/wiki/Setup-Guide)
- **Troubleshooting:** [Troubleshooting Guide](https://github.com/dfrostar/neuralmind/wiki/Troubleshooting)

