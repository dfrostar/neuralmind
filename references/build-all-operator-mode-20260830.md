# Build-All Operator Mode & Scope Filtering — 2026-08-30

Operator-scale workflow for managing multiple project indexes from a single command.

## Background

User (Darren Frost) manages 5+ repos: neuralmind, cmmc20, lingogame, autopilot, ai-agent-playbook-v2.
Running `neuralmind build` per-project by hand was the bottleneck. The fix has two parts:

1. **`build-all` command** — iterate registered projects, build each scope, summarize
2. **`--scope` flag** — filter nodes at embed time (code/content/docs) with per-scope index files

## Project Registry

`~/.config/neuralmind/projects.json` stores known projects:

```json
[
  {"path": "/home/dtfrost/cmmc20", "scopes": ["code", "content"]},
  {"path": "/home/dtfrost/neuralmind", "scopes": ["code"]}
]
```

Managed via `neuralmind project add/remove/list`.

## Scope Filtering

| Scope | File types included | Index file |
|-------|---------------------|------------|
| `all` | Everything (default) | `index.tvim` |
| `code` | `.py`, `.js`, `.ts`, `.tsx`, `.go`, `.rs`, etc. | `index.code.tvim` |
| `content` | `.md`, `.mdx`, `.txt`, `.rst`, `.pdf` | `index.content.tvim` |
| `docs` | `.md`, `.mdx`, `.txt`, `.rst` | `index.docs.tvim` |

Scope detection uses `file_type` from graph.json with extension fallback.

## Command Reference

```bash
# Add a project to the registry
neuralmind project add /path/to/project --scope=code,content

# List registered projects
neuralmind project list

# Build all registered projects (one command)
neuralmind build-all

# Build with scope filter
neuralmind build /path/to/project --scope=code

# Override scope for all projects in build-all
neuralmind build-all --scope=content
```

## Implementation Plan

Full plan at `.hermes/plans/2026-08-30-build-all-operator-mode.md`. Tasks:
1. `project_registry.py` — load/save `~/.config/neuralmind/projects.json`
2. Scope filtering in `TurboVecEmbedder.embed_nodes(scope=...)`
3. Per-scope index file naming (`index.code.tvim`, `index.content.tvim`)
4. Wire `--scope` into `cmd_build` CLI
5. `build-all` command — iterates registry, calls `cmd_build` per project
6. `project` subcommand — `add/remove/list` registry management
7. End-to-end validation on cmmc20

## Validation

Tested on cmmc20 (6767 nodes, code+content scopes):
- `neuralmind build --scope=code` — incremental, 4.1s, progress bar visible
- `neuralmind doctor` — new turbovec compatibility check, orphaned/stale node detection
- Large project warning fires when >2000 nodes detected
