# Brain-like Continual Learning (Opt-in MVP)

> **Note (v0.25.0):** this document describes the original v0.3.x learning
> scaffolding, including the `learned_patterns` cooccurrence reranker and
> `neuralmind learn`. **That reranker was removed in v0.25.0** — `neuralmind
> learn` is now an exit-0 deprecation no-op, and learning is handled entirely
> by the Hebbian synapse layer (see the [Learning Guide](wiki/Learning-Guide.md)
> and the [v0.25.0 release notes](../RELEASE_NOTES_v0.25.0.md)). The
> consent/query-event-logging content below remains accurate; treat the
> reranker references as historical design rationale.

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
  - **deprecated and a no-op since v0.25.0** (prints a deprecation notice, exits 0)
  - the synapse layer now learns automatically; nothing to run manually

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
