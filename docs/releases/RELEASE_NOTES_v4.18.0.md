# NeuralMind v4.18.0 — `neuralmind data-locations`, audit writes that can't fail unseen, and home-directory copies that follow the encryption policy

**Type:** Minor release | **Theme:** closing the gaps the v4.17.2 compliance documents named

v4.17.2 rewrote the compliance documents to say what NeuralMind does, including
three things it didn't do well. This release fixes them, and adds the command
the data deletion procedure needed all along.

- **There was no way to list a project's data.** The deletion procedure tried
  to name every place by hand, and seven rounds of review each found one it
  missed: an index at a custom `db_path`, the global query log, the Team audit
  log, `NEURALMIND_CONFIG_DIR`, a config named `.yml`, a BM25 file.
- **An audit record that couldn't be written disappeared.** Every caller
  swallows a failed append so that auditing never blocks a query or a build,
  so a full disk or a permissions error left a gap in the log that nothing
  reported.
- **Copies under the home directory skipped the encryption check.** Claude
  Code's synapse export (code symbol names) and the global query log (query
  text) are written under `~`, which `security.require_encrypted_storage`
  never checked. On a host whose project volume was encrypted and whose home
  wasn't, they landed unencrypted.
- **`NEURALMIND_SYNAPSE_EXPORT=0` didn't cover the MCP tool.** It switched off
  the hooks' export, but `neuralmind_export_synapse_memory` still wrote
  Claude Code's copy.

---

## What changed

### `neuralmind data-locations`

Lists every place NeuralMind keeps data for a project, in the project, outside
it, and in the integrations that write it, and whether each holds anything.
Each location comes from the code that writes it, so the list can't drift from
the code. A `.neuralmind/` that's a symlink is listed by the directory it points
to, with both to remove: `rm -rf .neuralmind/` would empty it and leave the
directory and the link. It's read-only.

```
$ neuralmind data-locations .
NeuralMind data for /work/app

Project:
  [present] .neuralmind/: /work/app/.neuralmind
            holds: index, code graph, synapses, decisions, audit log, recaps, caches
            remove: rm -rf .neuralmind/
  [present] index at db_path: /mnt/fast/app-index
            holds: the vector index, including indexed text (bm25_index.json, index.tvim, store.sqlite)
            remove: delete the files listed; the directory only if nothing else is in it
  ...

Outside the project:
  [present] global query log: /home/dev/.neuralmind/memory/query_events.jsonl
            holds: the text of this project's queries, among every project's (12 line(s) from this project)
            remove: remove this project's lines (DATA_DELETION.md 3.1)
  ...

Integrations:
  [present] git hook blocks: /work/app/.git/hooks
            holds: rebuilds that write this project's index (post-commit, post-merge)
            remove: delete each block between # neuralmind-hook-start and # neuralmind-hook-end
  ...

5 of 15 present. See docs/compliance/DATA_DELETION.md.
```

`--json` gives the same list for a script. The
[data deletion procedure](../compliance/DATA_DELETION.md) runs it before
deleting and again after: once the deletion is done, only what you chose to keep
should be listed as present. The `db_path` index and anchored checkpoints are
found through the config file, which the procedure deletes, so it notes those
two first and checks them by hand at the end.

### Failed audit writes are noted and reported

A record that can't be written is noted in
`.neuralmind/audit_write_failures.jsonl` (a separate file, since the log or its
lock may be what failed) and logged as a warning. `neuralmind doctor` has a new
*Audit log writes* check:

```
  [warn] Audit log writes: 3 audit record(s) couldn't be written, so the log is missing them; the last, query/query at 2026-10-18T13:02:11+00:00: OSError: [Errno 28] No space left on device
```

It warns, and fails under `security.profile: cui`, where a complete audit log
is a control. The call itself still runs, as before.

Fix the cause, then record the gap in the log itself:

```
$ neuralmind audit record-gap .
✓ Recorded a gap of 3 missing record(s), 2026-10-18T12:58:40+00:00 to 2026-10-18T13:02:11+00:00, in the audit log.
```

That appends one hash-chained `audit/gap_recorded` record, with status `failure`,
naming how many records are missing, of which events, when, and the last error.
The check then passes, counting only failures after that record. The failures
file is kept and only appended to, so clearing the warning doesn't erase the
evidence, and deleting the file doesn't make later failures look recorded.

### Home-directory copies follow `security.require_encrypted_storage`

Claude Code's synapse export and the global query log are written only where the
storage check passes. Under `security.require_encrypted_storage` (which
`security.profile: cui` turns on), an unverified home directory gets neither;
the project's own copies, already checked, are written as before. The storage
check records each location it checks in the audit log, as it does for the
project.

### `NEURALMIND_SYNAPSE_EXPORT=0` covers the MCP tool

`neuralmind_export_synapse_memory` returns
`{"enabled": false, "written": [], "reason": "NEURALMIND_SYNAPSE_EXPORT=0"}`
instead of exporting.

## What the agent actually sees

- **Nothing new, normally.** The MCP tools, hooks and queries behave as before.
- **With `NEURALMIND_SYNAPSE_EXPORT=0`**, a call to
  `neuralmind_export_synapse_memory` returns the reason instead of a file list.
- **Under `security.require_encrypted_storage` with an unencrypted home**,
  Claude Code's auto-memory no longer gets `synapse-activations.md`. The
  project's `.neuralmind/SYNAPSE_MEMORY.md`, which the `CLAUDE.md` import line
  reads, is unchanged.

## Per-agent expectations

| Agent | What changes |
|---|---|
| Claude Code (hooks + MCP) | Under required encryption and an unencrypted home, no copy in `~/.claude/projects/<slug>/memory/`; the project file still loads |
| Cursor / Cline / Continue (MCP) | `neuralmind_export_synapse_memory` honours `NEURALMIND_SYNAPSE_EXPORT=0` |
| Hermes-Agent plugin | As Claude Code |
| Generic MCP client | As Cursor |

## Upgrading

- Run `neuralmind doctor .`. An *Audit log writes* warning means records went
  missing; the detail names the last and why. Fix the cause, then run
  `neuralmind audit record-gap .`.
- Under `security.require_encrypted_storage`, if `doctor` passes but Claude
  Code stops seeing `synapse-activations.md`, the home directory isn't on a
  verified encrypted volume. Encrypt it, or rely on the project's
  `SYNAPSE_MEMORY.md` import.
- Nothing to change otherwise.

## Reproduce

```bash
pytest tests/test_data_locations.py -v           # every location found from the code, and nothing written
pytest tests/test_outside_project_copies.py -v   # failed audit writes noted and recorded as gaps; home copies follow the policy; MCP off switch
```

## Related

- [Data deletion procedure](../compliance/DATA_DELETION.md): now built on `data-locations`
- [v4.17.2 release notes](RELEASE_NOTES_v4.17.2.md): the documents that named these gaps
- [Security guide: security checklist](../SECURITY-GUIDE.md#security-checklist)
