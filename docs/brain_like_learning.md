# Brain-like Continual Learning (Opt-in MVP)

NeuralMind includes opt-in, local-first scaffolding for implicit continual learning.

## What this MVP does

- Uses **local JSONL memory files** only (no telemetry upload).
- Keeps two scopes:
  - **Per-project:** `<project>/.neuralmind/memory/query_events.jsonl`
  - **Global:** `~/.neuralmind/memory/query_events.jsonl`
- Logs only:
  - query text
  - retrieval summary (`layers_used`, `communities_loaded`, `search_hits`, token count, reduction ratio)
- Uses one-time consent sentinel:
  - `~/.neuralmind/memory_consent.json`
- Supports disable switches:
  - `NEURALMIND_MEMORY=0`
  - `NEURALMIND_LEARNING=0`

## CLI behavior

- `neuralmind query ...`:
  - prompts once for consent in TTY sessions only
  - does not prompt in non-interactive sessions
  - if non-interactive and not already enabled, no memory is logged
- `neuralmind learn <project_path>`:
  - minimal scaffold command
  - safe no-op when learning is disabled

## Hook points

- Primary logging hook: `neuralmind/core.py` → `NeuralMind.query()`
  - this covers both CLI and MCP query flows

## Decision log (2026-04-20)

- Chosen direction: opt-in, implicit “brain-like” continual learning scaffolding.
- Defaults approved:
  - local-first storage
  - project + global memory scopes
  - JSONL format
  - MVP signals limited to query + retrieval summary
  - one-time consent sentinel
  - env var disable switches (`NEURALMIND_MEMORY=0`, `NEURALMIND_LEARNING=0`)
- Prompting behavior: avoid spam; non-interactive flows default to no logging unless already enabled.
- Initial implementation scope: scaffolding only (no heavy model training, no ChromaDB indexing changes, no telemetry upload).
