# Multi-Project Scoping

**Last updated:** 2026-10-05  
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
| **NeuralMind Hermes plugin, pinned** *(v4.8.0+)* | Every session on that Hermes home | A pinned project serves every Hermes session, in any directory, and records their prompts and edited paths. **For several projects, install without a path** ([below](#hermes-plugin-dont-pin-across-projects-v480)). |

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

When you have separate NeuralMind indexes for multiple codebases (e.g., `cmmc20`, `neuralmind`, `lingogame`), the **NeuralMind layer is safe**, unless the Hermes plugin is pinned to one of them. But any shared memory system needs scoping discipline:

### Hermes plugin: don't pin across projects *(v4.8.0+)*

A project pinned with `neuralmind install-hermes-plugin <path>` does **not** isolate per repository. The pin applies to every Hermes session that uses that Hermes home, whatever directory it runs in: each one gets the pinned project's context, and its prompts (and the paths of files it edits) are recorded in the pinned project's `.neuralmind/recaps/`. That includes a session in a repository that must never be indexed, such as `autopilot`. Prompts are redacted before they're written, but the patterns catch common credential formats, not every secret, and the next session in the pinned project, Hermes or Claude Code, can start with them in its recap. The paths of files edited in other repositories also go into the pinned project's synapse store, from where `neuralmind memory publish` can carry them into the project's committed team-memory bundle (`.neuralmind-team-memory.json`). `NEURALMIND_PROJECT` set in Hermes's environment does the same.

For several projects, install without a path, so the plugin follows the directory Hermes works in and does nothing in a repository NeuralMind hasn't built, such as `autopilot`:

```bash
# ✅ Several projects — follows the directory Hermes works in
neuralmind install-hermes-plugin           # first install
neuralmind install-hermes-plugin --unpin   # already pinned: a re-run without a path keeps the pin, so clear it

# ❌ Several projects — every Hermes session, autopilot included, is recorded in neuralmind's recaps and synapse store
neuralmind install-hermes-plugin /path/to/neuralmind
```

The plugin follows the directory by reading `TERMINAL_CWD` from the Hermes process's environment. That matches where Hermes works in the terminal CLI and a standalone gateway (Telegram, Discord …), but the gateway's terminal working directory (`terminal.cwd`, else `MESSAGING_CWD`, else your home directory) is rarely the project you mean. Hermes Desktop, ACP editor sessions and per-session workspaces keep each session's directory elsewhere, so the plugin can't follow it there. Unpinned there, every session uses the Hermes process's own `TERMINAL_CWD` (or its working directory), so if that is a built project, all those sessions are served and recorded as that project.

Pin only for a single-project setup or for the gateway. In Hermes Desktop, ACP editor sessions and per-session workspaces, pin a project or set `NEURALMIND_PROJECT`, and everything above about a pin applies.

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
- [ ] The Hermes plugin isn't pinned (installed without a path, or with `--unpin`), unless Hermes serves a single project or the gateway; in Hermes Desktop, ACP editor sessions and per-session workspaces it can't follow the directory, so pin or set `NEURALMIND_PROJECT` there
- [ ] memU retrieve queries always start with `[project]`
- [ ] Hermes memory entries always carry `[project]` prefix
- [ ] session_search queries always include project name
- [ ] When in doubt, scope it

---

*This page is part of the operator documentation. End users running NeuralMind on a single project don't need to read this.*
