# NeuralMind Compatibility Matrix

**Last Updated:** 2026-07-31  
**Next Review:** 2026-10-31

---

## Version Compatibility

| NeuralMind | Status | Python | Release Date | Support Until |
|------------|--------|--------|--------------|---------------|
| v1.10.1 | ✅ Current | 3.10-3.13 | 2026-07-30 | 2027-01-30 |
| v1.10.0 | ✅ Maintained | 3.10-3.13 | 2026-07-28 | 2026-12-28 |
| v1.9.x | ✅ Maintained | 3.10-3.13 | 2026-07-15 | 2026-10-15 |
| v0.42.x | ⚠️ LTS | 3.10-3.13 | 2026-06-01 | 2026-12-01 |
| v0.41.x | ⚠️ LTS | 3.10-3.13 | 2026-05-01 | 2026-11-01 |
| v0.4.x | ❌ EOL | 3.10-3.13 | 2026-04-20 | 2026-07-20 |
| v0.3.x | ❌ EOL | 3.10-3.12 | 2025-10-01 | 2026-04-01 |
| v0.2.x | ❌ EOL | 3.10-3.11 | 2025-06-01 | 2025-10-01 |

---

## Platform Support

| OS | Status | Notes |
|----|--------|-------|
| Linux | ✅ Full | CI-verified on every PR (Python 3.10–3.12) |
| macOS | ✅ Full | CI-verified on every PR; x86 and Apple Silicon |
| Windows | ✅ Full | CI-verified on every PR (`windows-latest`, Python 3.12) |
| Docker | ✅ Full | Included in releases; multi-platform (linux/amd64 + linux/arm64) |

---

## Python Version Support

| Python | Status | Notes |
|--------|--------|-------|
| 3.13 | ✅ Supported | Latest, actively tested |
| 3.12 | ✅ Supported | Stable, recommended |
| 3.11 | ✅ Supported | Still widely used |
| 3.10 | ✅ Supported | Minimum version |
| 3.9 | ❌ Unsupported | End of support Oct 2025 |

---

## Embedding Backend Compatibility

| Backend | Min Version | Status | Use Case | Notes |
|---------|------------|--------|----------|-------|
| turbovec (default) | v0.29.0 | ✅ Default | Local/Single-machine | ChromaDB-free, quantized vectors, parity-gated |
| ChromaDB | 0.4.20+ | ✅ Opt-in | Local/Single-machine | Legacy backend, still supported |
| PostgreSQL pgvector | 0.1.0 | ⚠️ Experimental | Enterprise/Large-scale | 100K-10M nodes |
| LanceDB | 0.1.0 | 🔬 Research | Edge/Offline | Still in beta |

**Note:** Since v0.29.0, turbovec is the default backend. ChromaDB is opt-in via `pip install neuralmind[chromadb]`. The `neuralmind doctor` command shows the resolved backend.

---

## MCP Server Compatibility

| MCP Version | NeuralMind Compat | Status | Features |
|------------|------------------|--------|----------|
| 0.1.0+ | v0.4.x+ | ✅ Current | All tools |

---

## Known Issues & Workarounds

### Issue: Test suite hangs on `test_e2e_seat_governance.py`
- **Affected:** All versions
- **Status:** Under investigation (pre-existing, not a regression)
- **Workaround:** Run tests with `--ignore=tests/test_e2e_seat_governance.py` or use `pytest --timeout=30` to catch hangs

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
| ChromaDB as default | v0.29.0 | v0.29.0 | turbovec (ChromaDB still opt-in) |

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
v0.4.x → v1.9.x: Recommended, minor adjustments
v1.9.x → v1.10.x: Non-breaking, direct upgrade
v1.10.x → v1.10.1: Patch release, direct upgrade
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

### Planned for v1.11.0 (Q3 2026)
- None currently planned

### Planned for v2.0.0 (TBD)
- Stable API guarantee
- Long-term support for 2 years
- Commercial support options
