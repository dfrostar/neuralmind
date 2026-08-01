# Multi-Project Scoping

**Last updated:** 2026-08-02  
**Version:** v1.12.0  
**Audience:** Operators and agents working across multiple codebases (e.g., a monorepo with separate NeuralMind indexes, or a team managing multiple products)

---

## The rule

**NeuralMind isolates automatically. External memory layers do not.**

| Layer | Scope | How it isolates |
|-------|-------|-----------------|
| **NeuralMind** | Per-project | `.neuralmind/` lives in each project root. `build .` in repo A never touches repo B's index. |
| **memU** (single store) | Flat across projects | `memu-hermes retrieve` searches everything. **You must scope manually.** |
| **Hermes memory** | Flat across projects | All entries visible to every session. **You must prefix with `[project]`.** |
| **session_search** | Flat across projects | Searches all past conversations. **You must include project name in query.** |

---

## For end users (single project)

Nothing to do. NeuralMind's design already isolates:

```bash
cd /path/to/project
neuralmind build .      # creates .neuralmind/ here, local only
neuralmind query . "X"  # searches this project's index only
```

No cross-contamination possible. Your index is your index.

---

## For operators (multiple projects)

When you have separate NeuralMind indexes for multiple codebases (e.g., `cmmc20`, `neuralmind`, `lingogame`), the **NeuralMind layer is safe**. But any shared memory system needs scoping discipline:

### memU queries

Always prefix with the project tag:

```bash
# ✅ Scoped — only neuralmind results
memu-hermes retrieve "[neuralmind] seed_from_documentation"

# ✅ Scoped — only cmmc20 results  
memu-hermes retrieve "[cmmc20] zero trust gateway"

# ❌ Unscoped — mixes all projects
memu-hermes retrieve "synapse seeding"
```

### Hermes memory entries

Every memory entry should carry a project tag:

```
[neuralmind] v1.12.0 — seed_from_documentation wired into ingest_document()
[cmmc20] Zero Trust Gateway live, 426 tests
[cybersentinel] 9 tables, AdaptiveDetector, 462 tests
[meta] Cross-project preferences (models, brand, workflow)
```

If you see an untagged entry, that's a bug — flag it.

### session_search queries

Always include the project name:

```python
# ✅ Scoped
session_search(query="neuralmind seed_from_documentation")

# ✅ Scoped  
session_search(query="cmmc20 zero trust gateway")

# ❌ Unscoped — surfaces everything
session_search(query="synapse edges")
```

---

## Why this matters

NeuralMind's Hebbian synapse layer learns **per-project**. Edge weights, community structure, and learned transitions are specific to each codebase. Mixing them would:

1. **Corrupt recall** — spreading activation from cmmc20 could surface neuralmind nodes
2. **Pollute audit trails** — ingestion events from one project appearing in another's history  
3. **Confuse agents** — an agent working on cmmc20 getting neuralmind's architecture in its context window

The isolation is physical (separate `.neuralmind/` dirs) but only works if the *query layer* respects it.

---

## Checklist for multi-project operators

- [ ] Each project has its own `.neuralmind/` (automatic with `build .`)
- [ ] memU retrieve queries always start with `[project]`
- [ ] Hermes memory entries always carry `[project]` prefix
- [ ] session_search queries always include project name
- [ ] When in doubt, scope it

---

*This page is part of the operator documentation. End users running NeuralMind on a single project don't need to read this.*
