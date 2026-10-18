# Data Retention Policy

**Date:** 2026-10-18
**Version:** 1.2
**SOC 2 Controls:** C1.1, P4.2

---

## 1. Purpose

Define how long NeuralMind data is retained and when it is deleted.

## 2. Scope

Covers:
- `.neuralmind/` directory (vector index, code graph, synapse store, audit logs, caches)
- `graphify-out/` directory (a legacy index or a graphify graph, when present)
- `.neuralmind-team-memory.json` (committed team memory)
- The copies NeuralMind writes outside the project, listed in
  [Data Deletion §2.2](DATA_DELETION.md#22-outside-the-project)
- GitHub Actions artifacts (CI logs, evidence)

## 3. Retention Periods

| Data | Location | Retention | Rationale |
|------|----------|-----------|-----------|
| Synapse store | `.neuralmind/synapses.db` | Indefinite (until deleted) | User-controlled, local |
| Audit events | `.neuralmind/audit_events.jsonl` | Indefinite (until deleted) | User-controlled, local |
| Failed audit writes *(v4.18.0+)* | `.neuralmind/audit_write_failures.jsonl` | Until deleted after the cause is fixed | Event name, time and error of each record that couldn't be written, no query text |
| Query cache | `.neuralmind/last_output.json` | Single slot (overwritten) | 2 MB cap, atomic |
| Session recaps (v4.8+) | `.neuralmind/recaps/*.jsonl` | Ten most recently active sessions, plus any active in the last 24 hours (older ones deleted when a fresh or cleared Claude Code session, or (v4.9+) a Hermes-Agent session other than a subagent or cron job, starts) | Claude Code and Hermes-Agent prompts (not a Hermes subagent's or cron job's), credential-redacted and cut to 200 characters, and edited file paths; `neuralmind recap --clear` deletes them |
| Vector index | `.neuralmind/neuralmind_db/` (`graphify-out/neuralmind_db/` in a legacy layout) | Indefinite (until deleted) | User-controlled, local |
| Query memory | `.neuralmind/memory/query_events.jsonl` and `~/.neuralmind/memory/query_events.jsonl` | Indefinite (until deleted) | Written only after a yes at the first-run memory-consent prompt; the copy in the home directory holds every project's queries |
| Synapse export for Claude Code | `~/.claude/projects/<slug>/memory/synapse-activations.md` | Overwritten at each export | Written only when Claude Code's memory directory for the project exists |
| Team memory | `.neuralmind-team-memory.json` | Indefinite (committed) | Git history preserves |
| CI artifacts | GitHub Actions | 90 days | GitHub default |
| Evidence exports | `evidence/` directory | 1 year | Local compliance copies |

## 4. Deletion Triggers

Data is deleted when:
- User follows the [Data Deletion procedure](DATA_DELETION.md) (complete
  deletion, including the copies outside the project). `rm -rf .neuralmind/`
  alone leaves those copies
- A fresh or cleared Claude Code session starts, or a Hermes-Agent session's first turn with the NeuralMind plugin runs, unless it's a subagent's or a cron job's (session recap records beyond the ten most recent, and inactive for 24 hours, are deleted)
- User runs `neuralmind recap --clear` (all session recap records)
- GitHub Actions artifacts auto-expire (90 days)

## 5. User Rights

Users can:
- Delete all their data at any time ([Data Deletion procedure](DATA_DELETION.md))
- Disable team memory inheritance (`NEURALMIND_TEAM_MEMORY=0`)
- Disable query memory logging (`NEURALMIND_MEMORY=0`, or decline the
  first-run prompt). It doesn't affect the audit log, which has no off switch:
  delete it as in [Data Deletion §3.2](DATA_DELETION.md#32-selective-deletion)
- Disable synapse learning (`NEURALMIND_LEARNING=0`)
- Disable prompt and edit recording for the session recap (`NEURALMIND_SESSION_RECAP=0`)

---

*This policy is reviewed annually. Last reviewed: 2026-10-18.*
