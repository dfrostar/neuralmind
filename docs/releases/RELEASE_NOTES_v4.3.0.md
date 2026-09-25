# Release Notes — v4.3.0

**Date:** 2026-09-25
**Tag:** [v4.3.0](https://github.com/dfrostar/neuralmind/compare/v4.2.0...v4.3.0)
**Upgrade:** `pip install --upgrade neuralmind`

---

## Memory Layer v4.3 — Progressive Retrieval + Session-Boundary Hooks

This release ships Components B and C of the Memory Layer build spec:
the 3-layer progressive decision retrieval and the session-boundary
summary hooks, plus a train of critical fixes found by CI matrix and
independent adversarial QA (Qwen 3.8 Flash, 8-area risk checklist).

## What the agent sees

### 1. 3-layer progressive decision retrieval

Agents now filter before they fetch. Three new MCP tools replace the
single fat query for decision memory:

- **`neuralmind_memory_search`** (Layer 1) — compact index rows
  (~50–100 tokens each: id, title, status, type, commit, date). Cheap
  first call to scan candidates.
- **`neuralmind_memory_timeline`** (Layer 2) — chronological context
  around an anchor decision. Answers "what else was being decided
  around then?"
- **`neuralmind_memory_get`** (Layer 3) — full records (rationale,
  rejected alternatives, evidence, invalidation status), batch-capped
  at 20 ids per call so filtering happens before fetching.

A "why did we choose JWT over sessions?" workflow now completes in
≤3 tool calls and ≤2,000 tokens on the fixture repo. The existing
tools (`query/audit/record/invalidate_decisions`) are unchanged and
backwards compatible. Tool count: 25 → 28.

### 2. Stop + SessionEnd hooks (HOOK_VERSION 4)

Claude Code lifecycle coverage extends to the session boundary. Hooks
run one process per invocation, so both derive their view from the
durable event log (`.neuralmind/events.jsonl`):

- **Stop** (turn end) — ticks the summary cadence: counts events newer
  than the latest summary and writes one when the every-N threshold is
  met. Final-turn activity is never lost to a mid-cadence exit.
- **SessionEnd** (session close) — aggregates the recent event window
  (12h lookback, 500-event cap applied AFTER the time filter) into a
  final digest via SessionTracker (dedup + pruning included).

Both fail-open and opt-out via `NEURALMIND_SESSION_END=0`.
`install_hooks` now also wires PreToolUse (the stale-decision guard
was previously advertised but never installed — latent bug fixed).

## Critical fixes

- **`neuralmind demo` was broken on main** (since v4.2.0's output-dir
  consolidation): the demo check moved to `.neuralmind/graph.json` but
  the bundled fixture stayed in `graphify-out/`, and the gitignore made
  the new location untrackable. Fixed; the wheel now ships exactly the
  demo graph (no runtime artifacts).
- **Wheel packaging**: hatchling honors `.gitignore` during build
  inclusion — the `.neuralmind/` rule silently dropped graph.json from
  wheels even with an explicit pyproject include. Fixed with ordered
  exclude-then-include gitignore rules.
- **ONNX deadlock workaround completed**: large embed batches fan out to
  subprocesses; the child re-chunks to 32 texts with a fresh ONNX
  session per chunk (onnxruntime 1.29 on Python 3.14 deadlocks after
  2–3 `session.run()` calls on a reused session). The child code is
  inlined via `python -c` so it works identically from source checkouts
  and pip installs.
- **Legacy vector-db path fallback removed** — the fallback caused
  phantom "no nodes embedded" failures (writes to `graphify-out/` while
  doctor checked `.neuralmind/`). `neuralmind doctor` now detects
  orphaned legacy indexes and prints the migrate command.
- **`InMemoryEmbeddingBackend.graph_path` is now a live property** —
  the cached attribute pinned the canonical path at init and never saw
  legacy graphs written afterwards (fixed 4 pre-existing test failures).
- **Turbovec migration notice** detects legacy chroma indexes at both
  canonical and legacy paths.
- **Path-traversal guard in `graph_json_path`** is now analyzer-visible
  (CodeQL clean) via `_validated_artifact`.
- **Undefined `logger` NameError** in synapse_dynamics error paths (the
  module logger is named `log`).

## Numbers

- 22 new tests for the retrieval layers and hooks; full memory suite at
  123+, hooks suites at 59+, all CI matrices green (ubuntu/macos/windows
  × Python 3.10–3.12), CodeQL clean, parity benchmark gate green.
- MCP tools: 28. Hook events: 7 (PreToolUse, PostToolUse, SessionStart,
  UserPromptSubmit, PreCompact, Stop, SessionEnd).

## Known limitations (unchanged)

- Decision invalidation *signaling* at session end is future work — the
  summary records files touched; the staleness-scan command covers the
  audit side today.
- Sessions exceeding 1,500 events in 12h lose their oldest events from
  the digest window (documented limit).
- MiniLM-L6-v2 (384-dim) remains the embedding ceiling.

## What's next

Component A of the build spec — the contamination-blocked eval harness
with residual-context measurement — is queued as the next phase, followed
by Component D (framework-aware invalidation edges for FastAPI/Flask/
Django routes).
