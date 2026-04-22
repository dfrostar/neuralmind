# NeuralMind Compatibility Matrix

**Last Updated:** 2026-04-22  
**Next Review:** 2026-05-22

---

## Version Compatibility

| NeuralMind | Status | Python | graphify | chromadb | Release Date | Support Until |
|------------|--------|--------|----------|----------|--------------|---------------|
| v0.4.2 | ✅ Current | 3.10-3.13 | 1.2+ | 0.4.20+ | 2026-04-20 | 2026-10-20 |
| v0.4.1 | ✅ Maintained | 3.10-3.13 | 1.2+ | 0.4.15+ | 2026-03-15 | 2026-09-15 |
| v0.3.x | ⚠️ LTS | 3.10-3.12 | 1.1-1.2 | 0.4.0+ | 2025-10-01 | 2026-04-01 |
| v0.2.x | ❌ EOL | 3.10-3.11 | 1.0-1.1 | 0.3.x | 2025-06-01 | 2025-10-01 |
| v0.1.x | ❌ EOL | 3.10 | 0.9 | 0.2.x | 2025-01-01 | 2025-06-01 |

---

## Platform Support

| OS | Status | Tested Versions | Notes |
|----|--------|-----------------|-------|
| Linux | ✅ Full | Ubuntu 20.04+ | All features supported |
| macOS | ✅ Full | 11.0+ | x86 and Apple Silicon |
| Windows | ✅ Full | 10, 11 | Task Scheduler integration tested |
| Docker | ✅ Full | Docker 20.10+ | Included in releases |

---

## Python Version Support

| Python | Status | Until | Notes |
|--------|--------|-------|-------|
| 3.13 | ✅ Supported | 2025-10 | Latest, actively tested |
| 3.12 | ✅ Supported | 2026-10 | Stable, recommended |
| 3.11 | ✅ Supported | 2027-10 | Still widely used |
| 3.10 | ✅ Supported | 2026-10 | Minimum version |
| 3.9 | ❌ Unsupported | - | End of support Oct 2025 |

---

## Embedding Backend Compatibility

| Backend | Min Version | Status | Use Case | Notes |
|---------|------------|--------|----------|-------|
| ChromaDB | 0.4.20 | ✅ Default | Local/Single-machine | Recommended for <100K nodes |
| PostgreSQL pgvector | 0.1.0 | ⚠️ Experimental | Enterprise/Large-scale | 100K-10M nodes |
| LanceDB | 0.1.0 | 🔬 Research | Edge/Offline | Still in beta |

---

## Graphify Compatibility

| graphify | NeuralMind Compat | Status | Breaking Changes |
|----------|------------------|--------|------------------|
| 1.2.0+ | v0.4.x | ✅ Current | None |
| 1.1.x | v0.3.x, v0.4.x | ✅ Supported | Minor (query syntax) |
| 1.0.x | v0.2.x, v0.3.x | ⚠️ Maintained | Graph format changed |
| 0.9.x | v0.1.x | ❌ EOL | Major format change |

**Installation:**
```bash
# Upgrade to latest
git clone https://github.com/safishamsi/graphify.git
cd graphify && git pull && pip install -e .
```

---

## MCP Server Compatibility

| MCP Version | NeuralMind Compat | Status | Features |
|------------|------------------|--------|----------|
| 0.1.0+ | v0.4.x | ✅ Current | All tools |
| - | v0.3.x | ❌ Not supported | Use CLI instead |

---

## Known Issues & Workarounds

### Issue: ChromaDB 0.4.15-0.4.19 Memory Leak
- **Affected:** NeuralMind v0.4.0-v0.4.1
- **Status:** Fixed in v0.4.2 (updated to chromadb 0.4.20+)
- **Workaround:** Upgrade to v0.4.2 or pin chromadb>=0.4.20

### Issue: graphify 1.1.x Changes Query Format
- **Affected:** NeuralMind v0.3.x with graphify 1.1.0+
- **Status:** Handled in v0.4.0 (auto-converts)
- **Workaround:** Use graphify 1.2.0+ or NeuralMind v0.4.0+

### Issue: Windows Task Scheduler + Python Venv
- **Affected:** Auto-discovery on Windows with venv
- **Status:** Documented in Scheduling Guide
- **Workaround:** Use full path to python.exe in venv

---

## Deprecated Features

| Feature | Deprecated In | Removed In | Replacement |
|---------|---------------|-----------|-------------|
| `--old-output` flag | v0.3.5 | v0.4.0 | `--json` or `--markdown` |
| `graphify build` | v0.3.0 | v0.4.0 | `graphify update` |
| Legacy MCP tools | v0.4.0 | v0.5.0 | New MCP server |

---

## Testing Matrix

| Test Type | Frequency | Coverage |
|-----------|-----------|----------|
| Unit Tests | Per commit | 85% |
| Integration Tests | Per PR | Core workflows |
| Compatibility Tests | Weekly | All Python versions |
| Performance Benchmarks | Every PR | Token reduction |
| Security Scans | Weekly | Dependencies + code |

---

## Upgrade Path

```
v0.1.x → v0.2.x: Migration guide required
v0.2.x → v0.3.x: Non-breaking, direct upgrade
v0.3.x → v0.4.x: Recommended, minor adjustments
v0.4.x → v0.5.0: Breaking changes (see MIGRATIONS.md)
```

---

## How to Report Compatibility Issues

1. Check this matrix first
2. Check `docs/TROUBLESHOOTING.md`
3. Open issue with:
   - NeuralMind version: `neuralmind --version`
   - Python version: `python --version`
   - OS and version
   - Exact error message
   - Reproduction steps

---

## Future Changes

### Planned for v0.5.0 (Q3 2026)
- Python 3.9 support dropped
- MCP server redesigned (breaking API)
- New embedding backend selector

### Planned for v1.0.0 (Q1 2027)
- Stable API guarantee
- Long-term support for 2 years
- Commercial support options

