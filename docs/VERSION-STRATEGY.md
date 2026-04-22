# NeuralMind Version Strategy

**Status:** Active  
**Version:** 0.4.x (current)  
**Support Policy:** Semantic Versioning (SemVer)

---

## Versioning Scheme

NeuralMind uses **Semantic Versioning (SemVer)**: `MAJOR.MINOR.PATCH`

```
v0.4.2
│ │ └─ PATCH: bug fixes, security patches (auto-deployed)
│ └──── MINOR: new features, non-breaking changes (quarterly)
└────── MAJOR: breaking changes, major architecture shifts (annually)
```

### Version Lifecycle

- **Current (v0.4.x):** Active development
- **Previous (v0.3.x):** 6 months LTS (bug fixes only)
- **Older:** Unsupported

---

## Breaking Changes Policy

**A breaking change is:**
- Removing a command or flag
- Changing output format in non-backward-compatible way
- Changing required dependencies
- Changing minimum Python version
- Changing default behavior (that apps rely on)

**When releasing a breaking change:**
1. Announce 1 version in advance (v0.4.x with deprecation warning)
2. Provide migration guide
3. Release as MAJOR version bump
4. Maintain compatibility guide in docs

**Example:**
```
v0.4.5: neuralmind query --old-flag (deprecated, use --new-flag)
v0.5.0: --old-flag removed (BREAKING)
docs/MIGRATIONS.md: "v0.4 → v0.5 migration guide"
```

---

## Dependency Management

### Core Dependencies

| Package | Min Version | Max Version | Why |
|---------|------------|-------------|-----|
| Python | 3.10 | 3.13 | Type hints, walrus operator |
| chromadb | 0.4.0 | latest | Vector storage |
| pyyaml | 6.0 | latest | Config parsing |
| toml | 0.10 | latest | TOML support |

### Optional Dependencies

| Extra | Package | Min Version | Use Case |
|-------|---------|------------|----------|
| `[mcp]` | mcp | 0.1.0 | MCP server |
| `[dev]` | pytest | 7.0 | Testing |
| `[dev]` | black | 23.0 | Formatting |
| `[dev]` | ruff | 0.1.0 | Linting |

### Compatibility Matrix

Generated monthly (in `docs/COMPATIBILITY.md`):

```
| NeuralMind | graphify | Python | Status |
|------------|----------|--------|--------|
| v0.4.x | v1.2+ | 3.10-3.13 | ✅ Tested |
| v0.3.x | v1.1-v1.2 | 3.10-3.12 | ⚠️ Maintained |
| v0.2.x | v1.0-v1.1 | 3.10-3.11 | ❌ EOL |
```

---

## Release Process

### 1. Preparation (1 week before)

- [ ] Run full test suite
- [ ] Run benchmarks (confirm no regression)
- [ ] Update CHANGELOG.md
- [ ] Update version in `__init__.py`
- [ ] Create release notes (highlights, migration guide if breaking)

### 2. Tag & Release (Release Day)

```bash
# Tag the commit
git tag -a v0.4.3 -m "Release v0.4.3: bug fixes and performance"

# GitHub Actions auto-publishes to PyPI
# Creates release page with notes and artifacts
```

### 3. Post-Release (Day 1-2)

- [ ] Verify PyPI package
- [ ] Run install test on fresh venv
- [ ] Update docs/wiki to reference new version
- [ ] Announce in Discussions
- [ ] Update compatibility matrix

---

## Security Updates

**Critical security fixes:** Released same-day as patches  
**Public disclosure:** After patch is released

```bash
# Example: CVE in dependency
v0.4.2: chromadb 0.4.5 (has CVE-2024-1234)
v0.4.3: chromadb 0.4.7 (patch)  ← Released same day
```

---

## Feature Flags (for gradual rollout)

For risky features, use feature flags:

```python
# In config
[features]
enable_pgvector_backend = false  # Experimental
enable_new_ranking_algo = false  # Opt-in

# Code
if config.get("features.enable_pgvector_backend"):
    use_pgvector()
```

---

## Deprecation Timeline

When deprecating a feature:

```
v0.4.5: Feature X deprecated
  - Docs marked [DEPRECATED]
  - Code shows warning: "Feature X will be removed in v0.5.0"
  - Alternative documented

v0.5.0: Feature X removed
  - Release notes highlight breaking change
  - Migration guide provided
```

---

## Support Timeline

| Version | Released | Type | Support Until | Status |
|---------|----------|------|-------------|--------|
| v0.4.x | 2026-04 | Current | 2026-10 | ✅ Active |
| v0.3.x | 2025-10 | LTS | 2026-04 | ⚠️ Maintained |
| v0.2.x | 2025-06 | Old | 2025-10 | ❌ EOL |
| v0.1.x | 2025-01 | Beta | 2025-06 | ❌ EOL |

---

## Migration Guides

When a breaking change occurs, create `docs/MIGRATIONS.md`:

```markdown
# Migration Guides

## v0.4 → v0.5

### Changed: neuralmind query output format

**Before (v0.4):**
```json
{
  "query": "...",
  "results": [...]
}
```

**After (v0.5):**
```json
{
  "query": "...",
  "results": [...]
}
```

**Action Required:**
Update parsing code to handle new schema. Backward compatibility flag available with `--legacy-output`.
```

---

## Changelog Format

File: `CHANGELOG.md` (follows [Keep a Changelog](https://keepachangelog.com/))

```markdown
## [0.4.3] - 2026-04-22

### Added
- Query memory learning (experimental)
- PostgreSQL pgvector backend support

### Fixed
- Issue #123: Auto-discovery task failure on Windows
- Issue #124: Memory leak in large codebases

### Changed
- Updated graphify to v1.2.0

### Deprecated
- `neuralmind query --old-format` (use `--json` instead)

### Security
- Fixed CVE-2024-1234 in chromadb dependency
```

---

## Rollback Policy

If a release has critical bugs:

```bash
# Example: v0.4.3 breaks core functionality
# Immediately patch and release v0.4.4
# Users can roll back: pip install neuralmind==0.4.2

# If v0.5.0 has major issue:
# - Yank v0.5.0 from PyPI
# - Release v0.5.1 with fix
# - Mark v0.5.0 as "do not use"
```

---

## Version Bump Decision Tree

```
Is it a bug fix?
  ├─ Yes → PATCH (v0.4.2 → v0.4.3)
  └─ No → Continue

Does it add backward-compatible features?
  ├─ Yes → MINOR (v0.4.x → v0.5.0)
  └─ No → Continue

Does it break existing code/APIs?
  ├─ Yes → MAJOR (v0.x → v1.0)
  └─ No → (shouldn't happen, re-check)
```

---

## Current Status

- **Latest:** v0.4.2 (2026-04-20)
- **Next:** v0.4.3 (scheduled 2026-05-15, includes security patches)
- **Future:** v0.5.0 (planned 2026-07, includes MCP enhancements)
- **Long-term:** v1.0.0 (2027 Q1, production-ready)

