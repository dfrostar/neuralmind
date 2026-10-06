# Data Retention Policy

**Date:** 2026-10-03
**Version:** 1.1
**SOC 2 Controls:** C1.1, P4.2

---

## 1. Purpose

Define how long NeuralMind data is retained and when it is deleted.

## 2. Scope

Covers:
- `.neuralmind/` directory (synapse store, audit logs, caches)
- `graphify-out/` directory (vector index, graph)
- `.neuralmind-team-memory.json` (committed team memory)
- GitHub Actions artifacts (CI logs, evidence)

## 3. Retention Periods

| Data | Location | Retention | Rationale |
|------|----------|-----------|-----------|
| Synapse store | `.neuralmind/synapses.db` | Indefinite (until deleted) | User-controlled, local |
| Audit events | `.neuralmind/audit_events.jsonl` | Indefinite (until deleted) | User-controlled, local |
| Query cache | `.neuralmind/last_output.json` | Single slot (overwritten) | 2 MB cap, atomic |
| Session recaps (v4.8+) | `.neuralmind/recaps/*.jsonl` | Ten most recently active sessions, plus any active in the last 24 hours (older ones deleted when a fresh session starts) | Prompts credential-redacted and cut to 200 characters; `neuralmind recap --clear` deletes them |
| Vector index | `graphify-out/neuralmind_db/` | Indefinite (until deleted) | User-controlled, local |
| Team memory | `.neuralmind-team-memory.json` | Indefinite (committed) | Git history preserves |
| CI artifacts | GitHub Actions | 90 days | GitHub default |
| Evidence exports | `evidence/` directory | 1 year | Local compliance copies |

## 4. Deletion Triggers

Data is deleted when:
- User runs `rm -rf .neuralmind/` (complete local deletion)
- User runs `neuralmind clean` (if implemented)
- A fresh or cleared Claude Code session starts (session recap records beyond the ten most recent, and inactive for 24 hours, are deleted)
- User runs `neuralmind recap --clear` (all session recap records)
- GitHub Actions artifacts auto-expire (90 days)

## 5. User Rights

Users can:
- Delete all their data at any time (`rm -rf .neuralmind/`)
- Disable team memory inheritance (`NEURALMIND_TEAM_MEMORY=0`)
- Disable audit logging (`NEURALMIND_MEMORY=0`)
- Disable synapse learning (`NEURALMIND_LEARNING=0`)
- Disable prompt and edit recording for the session recap (`NEURALMIND_SESSION_RECAP=0`)

---

*This policy is reviewed annually. Last reviewed: 2026-07-27.*
