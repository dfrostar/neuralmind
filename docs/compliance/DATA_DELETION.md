# Data Deletion Procedure

**Date:** 2026-10-18
**Version:** 1.2
**SOC 2 Controls:** C1.2, P4.3

---

## 1. Purpose

Define how to delete all NeuralMind data for a project, including the copies
NeuralMind writes outside the project directory.

Two things are kept unless erasure is required, and §3.1 says how to delete
each when it is:

- The Team governance audit log (§2.2) is hash-chained, so one project's
  records can't be removed from it without breaking its verification. It is
  kept, or deleted whole with every project's records in it.
- The project's file in `security.audit_anchor_dir`, if set, holds checkpoint
  record counts and hashes, no code. It is kept by default because it is how
  truncation of the audit log is detected (§5).

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
| `neuralmind-backend.yaml` (or `.yml`, or `.json`: NeuralMind reads the first that exists) | Configuration, including the security policy |
| The directory its `db_path` names, if set (relative to the project, or absolute) | The vector index stored outside `.neuralmind/`, including the text of indexed code (turbovec's `store.sqlite`) |

### 2.2 Outside the project

| Path | What it holds | Written by |
|---|---|---|
| `~/.claude/projects/<slug>/memory/synapse-activations.md` | Code symbol and file names from the project's synapse store. `<slug>` is the project's absolute path, symlinks resolved, with each `/` replaced by `-` | Memory export and the Claude Code `SessionStart` hook, when that directory exists |
| `projects.json` in `$NEURALMIND_CONFIG_DIR`, or `~/.config/neuralmind/` when that's unset | Paths of registered projects | `neuralmind build-all` and the project registry |
| `audit.db` in the same directory (or the Team config's `audit_db`) | The Team governance audit log: the project's path and the names of code nodes whose shared edges were retracted, hash-chained | `neuralmind team` governance commands |
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

*(v4.18.0+)* Start with `neuralmind data-locations .`, which lists every
location below that holds this project's data, resolved by the code that writes
it, with how to remove each. Run it again at the end (§3.3). If it reports a
`problem` with the config file, fix the file first: until it parses, the
`db_path` index and anchored checkpoints it names aren't listed.

First stop everything that writes NeuralMind data under this OS account, in
every project and not only this one: end the agent sessions that use NeuralMind
(Claude Code, Hermes-Agent, any MCP client), stop `neuralmind watch` and
`neuralmind serve`, and stop the daemon (`neuralmind daemon stop`). The query
log below is shared by every project, and a query any of them logs while it's
rewritten would be lost.

Before anything is deleted, note the two locations the project's config file
(`neuralmind-backend.yaml`, `.yml` or `.json`) may point outside
`.neuralmind/`, since the commands below delete that file:

- **`db_path`**, where the index is kept if it isn't in `.neuralmind/`. The
  index is `store*.sqlite*`, `index*.tvim*` and `bm25_index*.json` (turbovec), or `chroma.sqlite3*`
  (the database and its journals) and its UUID-named collection folders (ChromaDB). The names are fixed, so a
  location two projects share holds one index for both: it can't be split, and
  deleting it means the other project must run `neuralmind build` again.
  Delete those files, and the directory itself only if it holds nothing else.
- **`security.audit_anchor_dir`**, where this project's checkpoint copies are
  kept. When erasure is required, delete this project's file there; the other
  projects' files in the same directory are theirs. This prints its path, and
  reads the setting even when another checkpoint setting is invalid:

  ```bash
  python3 - <<'PY'
  import os
  from pathlib import Path
  from neuralmind.audit_checkpoint import anchor_checkpoints_path
  from neuralmind.backend_manager import backend_config_path, read_backend_config_file
  root = Path(".").resolve()
  config = backend_config_path(root)
  security = (read_backend_config_file(config) if config else {}).get("security") or {}
  anchor = security.get("audit_anchor_dir")
  if anchor:
      anchor_dir = Path(os.path.expanduser(str(anchor).strip()))
      print(anchor_checkpoints_path(root, anchor_dir if anchor_dir.is_absolute() else root / anchor_dir))
  else:
      print("no security.audit_anchor_dir is set")
  PY
  ```

Then run from the project root:

```bash
# Configuration first, so a later agent session can't recreate the data below
neuralmind install-hooks --uninstall             # this project's Claude Code hooks
# neuralmind install-hooks --uninstall --global  # if installed with --global and no other project uses them
# neuralmind install-hermes-plugin --unpin       # if the Hermes plugin is pinned to this project

# In the project
rm -rf .neuralmind/ graphify-out/
rm -f .neuralmind-team-memory.json neuralmind-backend.yaml neuralmind-backend.yml neuralmind-backend.json

# Outside the project: Claude Code's copy of the synapse export
slug="$(pwd -P | sed 's#/#-#g')"
rm -f ~/.claude/projects/"$slug"/memory/synapse-activations.md

# Outside the project: this project's queries in the global query log. A line
# that can't be parsed is kept; data-locations reports it, so inspect it.
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
```

If `.neuralmind` is a symlink, `rm -rf .neuralmind/` empties the directory it
points to but leaves that directory and the link: remove both
(`data-locations` lists the target and the command).

Then remove the rest of 2.3 that applies (the git hook blocks, the `CLAUDE.md`
import line), the project's entry from `projects.json` (in
`$NEURALMIND_CONFIG_DIR`, or `~/.config/neuralmind/`), the index files at
`db_path` and, when erasure is required, the anchored checkpoint file (both
noted above), and, if no other project uses NeuralMind, `~/.neuralmind/`.
The Team governance audit log is not deleted here: it's hash-chained, so
removing one project's records breaks its verification. Keep it for your
retention period, or, when erasure is required, delete the whole file
(`audit.db` in `$NEURALMIND_CONFIG_DIR` or `~/.config/neuralmind/`, or the Team
config's `audit_db`). That erases
every project's governance records, not only this one's.
The team memory bundle and the config file stay in git history until that
history is rewritten. The config file holds the project's
security policy, so committing its deletion removes the policy for everyone
who pulls the change.

### 3.2 Selective Deletion

```bash
# Remove only synapse store (keep index)
rm -f .neuralmind/synapses.db

# Remove only audit logs (the active log, its rotated archives, checkpoints,
# and the notes of records that couldn't be written)
rm -f .neuralmind/audit_events*.jsonl .neuralmind/audit_checkpoints.jsonl .neuralmind/audit_write_failures*

# Remove only the session recap records (stored prompts and edited paths)
neuralmind recap --clear

# Remove only team memory bundle
rm -f .neuralmind-team-memory.json
```

### 3.3 Verification

*(v4.18.0+)* `neuralmind data-locations .` should list as present only what you
chose to keep (§1). It finds the `db_path` index and the anchored checkpoint
file through the config file, which §3.1 deleted, so it can't see those two any
more. Check them yourself on every version: set these lines to the locations
noted before deleting (leave a line empty if that location wasn't set), and
each check should print nothing:

```bash
db_path=""      # the db_path, if one was set
anchor_file=""  # the anchored checkpoint file, if erasure was required
[ -z "$db_path" ] || ls "$db_path"/store*.sqlite* "$db_path"/index*.tvim* "$db_path"/bm25_index*.json "$db_path"/chroma.sqlite3* 2>/dev/null
[ -z "$anchor_file" ] || ls "$anchor_file" 2>/dev/null
```

Before v4.18.0, which has no `data-locations`, each of these should print
nothing too:

```bash
grep -sl "neuralmind _hook" .claude/settings.json ~/.claude/settings.json
grep -sF "$(pwd -P)" ~/.hermes/plugins/neuralmind/config.json
ls -a .neuralmind/ graphify-out/ .neuralmind-team-memory.json neuralmind-backend.y*ml neuralmind-backend.json 2>/dev/null
ls ~/.claude/projects/"$(pwd -P | sed 's#/#-#g')"/memory/synapse-activations.md 2>/dev/null
grep -F "\"$(pwd -P)\"" ~/.neuralmind/memory/query_events.jsonl 2>/dev/null
grep -F "\"$(pwd -P)\"" "${NEURALMIND_CONFIG_DIR:-$HOME/.config/neuralmind}/projects.json" 2>/dev/null
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
detected. When erasure is required, delete this project's file there as in
§3.1.

---

*This procedure is reviewed annually. Last reviewed: 2026-10-18.*
