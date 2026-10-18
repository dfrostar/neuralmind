# Data Deletion Procedure

**Date:** 2026-10-18
**Version:** 1.2
**SOC 2 Controls:** C1.2, P4.3

---

## 1. Purpose

Define how to delete all NeuralMind data for a project, including the copies
NeuralMind writes outside the project directory.

Version 1.1 listed only the project directory, and named a `.neuralmind/hooks/`
directory that NeuralMind never creates. It missed the files below under
"Outside the project": one holds code symbol names, and one, when query memory
logging is on, the text of every query from every project.

## 2. Scope

### 2.1 In the project

| Path | What it holds |
|---|---|
| `.neuralmind/` | Vector index, code graph, synapse store, decision memory (`memory.db`), audit log and its rotated archives, audit checkpoints, session recaps, command-output cache, build status |
| `graphify-out/` | A legacy index or a graphify graph, when present |
| `.neuralmind-team-memory.json` | The team memory bundle. It is committed, so deleting the file leaves earlier versions in git history |
| `neuralmind-backend.yaml` | Configuration, including the security policy |

### 2.2 Outside the project

| Path | What it holds | Written by |
|---|---|---|
| `~/.claude/projects/<slug>/memory/synapse-activations.md` | Code symbol and file names from the project's synapse store. `<slug>` is the project's absolute path, symlinks resolved, with each `/` replaced by `-` | Memory export and the Claude Code `SessionStart` hook, when that directory exists |
| `~/.config/neuralmind/projects.json` | Paths of registered projects | `neuralmind build-all` and the project registry |
| `~/.config/neuralmind/`, `~/.local/share/neuralmind/` (the rest) | User configuration, Team configuration and license; the self-hosted data directory. No project data | You, `neuralmind self-hosted init` |
| `~/.neuralmind/memory/query_events.jsonl` | The text of every query, with its project's path, from every project on the machine | Query memory logging, when it was accepted at the first-run prompt and `NEURALMIND_MEMORY` isn't `0` |
| `~/.neuralmind/` (the rest) | Daemon discovery file and log, the graph server's access token, the memory-consent record, the Team license store | The daemon, `neuralmind serve`, the first-run memory-consent prompt, `neuralmind team` / `license` |
| The `security.audit_anchor_dir` directory, if set | Copies of audit checkpoints (record counts and hashes, no code) | `neuralmind audit checkpoint` |
| `~/.cache/neuralmind/` | The embedding model. No project data | First build |

### 2.3 Configuration NeuralMind added

| Where | How to remove it |
|---|---|
| Claude Code hooks in `.claude/settings.json` (or `~/.claude/settings.json` with `--global`) | `neuralmind install-hooks --uninstall` (add `--global` for the global install) |
| Git hooks from `neuralmind init-hook` | Delete the block between `# neuralmind-hook-start` and `# neuralmind-hook-end` in each hook under `git rev-parse --git-path hooks` (`post-commit`, `post-merge`, `post-checkout`, `post-rewrite`) |
| The Hermes-Agent plugin | `neuralmind install-hermes-plugin --uninstall` |
| An `@.neuralmind/SYNAPSE_MEMORY.md` import line in `CLAUDE.md` | Delete the line |

## 3. Deletion Procedure

### 3.1 Complete Deletion

First stop everything that writes NeuralMind data, so nothing is written while
it's being deleted: end the agent sessions that use NeuralMind (Claude Code,
Hermes-Agent, any MCP client), stop `neuralmind watch` and `neuralmind serve`,
and stop the daemon (`neuralmind daemon stop`). The query log below is shared by
every project, and a query logged while it's rewritten would be lost.

Then run from the project root:

```bash
# In the project
rm -rf .neuralmind/ graphify-out/
rm -f .neuralmind-team-memory.json neuralmind-backend.yaml

# Outside the project: Claude Code's copy of the synapse export
slug="$(pwd -P | sed 's#/#-#g')"
rm -f ~/.claude/projects/"$slug"/memory/synapse-activations.md

# Outside the project: this project's queries in the global query log
python3 - "$(pwd -P)" <<'PY'
import json, sys
from pathlib import Path
log = Path.home() / ".neuralmind" / "memory" / "query_events.jsonl"
if log.exists():
    def other_project(line):
        try:
            return json.loads(line).get("project_path") != sys.argv[1]
        except ValueError:
            return True
    kept = [l for l in log.read_text(encoding="utf-8").splitlines() if other_project(l)]
    log.write_text("".join(l + "\n" for l in kept), encoding="utf-8")
PY

# Configuration
neuralmind install-hooks --uninstall
```

Then remove the project's entry from `~/.config/neuralmind/projects.json`, the
git hook blocks (2.3), and, if no other project uses NeuralMind, `~/.neuralmind/`.
The team memory bundle and `neuralmind-backend.yaml` stay in git history until
that history is rewritten. `neuralmind-backend.yaml` holds the project's
security policy, so committing its deletion removes the policy for everyone
who pulls the change.

### 3.2 Selective Deletion

```bash
# Remove only synapse store (keep index)
rm -f .neuralmind/synapses.db

# Remove only audit logs (the active log, its rotated archives and checkpoints)
rm -f .neuralmind/audit_events*.jsonl .neuralmind/audit_checkpoints.jsonl

# Remove only the session recap records (stored prompts and edited paths)
neuralmind recap --clear

# Remove only team memory bundle
rm -f .neuralmind-team-memory.json
```

### 3.3 Verification

After a complete deletion each of these should print nothing:

```bash
ls -a .neuralmind/ graphify-out/ .neuralmind-team-memory.json neuralmind-backend.yaml 2>/dev/null
ls ~/.claude/projects/"$(pwd -P | sed 's#/#-#g')"/memory/synapse-activations.md 2>/dev/null
grep -F "\"$(pwd -P)\"" ~/.neuralmind/memory/query_events.jsonl 2>/dev/null
grep -F "\"$(pwd -P)\"" ~/.config/neuralmind/projects.json 2>/dev/null
grep -l "neuralmind-hook-start" "$(git rev-parse --git-path hooks)"/* 2>/dev/null
```

## 4. Recovery

NeuralMind data can be rebuilt:
- Index: `neuralmind build .`
- Synapses: re-learn from usage (no backup needed)
- Team memory: re-import from teammate's clone

## 5. Audit Trail

Deletion events are NOT logged (the act of deletion removes the log). This is acceptable because:
- Deletion is user-initiated
- No external party is affected
- Git history preserves code (not data)

A copy of the audit checkpoints in `security.audit_anchor_dir` survives a
deletion of `.neuralmind/`, by design: it is how truncation of the log is
detected.

---

*This procedure is reviewed annually. Last reviewed: 2026-10-18.*
