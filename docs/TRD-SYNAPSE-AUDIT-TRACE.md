# Technical Requirements Document: Synapse Audit Trace over MCP
**Product**: dfrostar/neuralmind v0.46.0 (target)  
**Date**: 2026-07-16  
**Owner**: Engineering / DevEx Team

## 1. Technical Summary
Two precise, additive changes — no new storage, no schema migration:

1. `neuralmind/mcp_server.py::tool_query` gains `trace: bool = False` and
   `trace_verbose: bool = False` params, passed through to
   `NeuralMind.query(trace=..., trace_verbose=...)` (already fully supported in
   `core.py` since PRD 3 Phase 1). When `trace` is set and `result.trace is not
   None`, it's attached to the response dict as structured JSON.
2. `neuralmind/context_selector.py::_apply_synapse_boost` (L3 hit-level boosting)
   is wired to the traced recall path (`_recall_energy_traced`), mirroring the
   pattern its L2 sibling `_boost_communities_from_synapses` already used. A new
   `RetrievalTrace.record_hit_synapse_boost()` method records each boosted or
   pulled-in hit.

## 2. Existing Machinery (not being rebuilt)
This release is deliberately thin because most of the system already existed:
- `neuralmind/trace.py` — `RetrievalTrace`/`TraceEvent`: bounded (`MAX_ITEMS=25`),
  redactable (`to_dict(redact=True)` strips paths to basenames), JSON-safe,
  human-renderable (`render_text()`). Fully tested in `tests/test_trace.py`.
- `neuralmind/core.py::NeuralMind.query(question, trace=False, trace_verbose=False)`
  — already end-to-end wired; sets `result.trace = self._trace.to_dict()`.
- `neuralmind/context_selector.py::ContextSelector.get_query_context` — already
  instantiates `RetrievalTrace` and threads it through L0-L3 layer selection.
- `synapses.py::spread_with_contributions()` — per-namespace energy attribution
  already feeding `record_synapse_boost`'s `namespace_contribution` field (PRD 4).
- Per-hit `_synapse_boost` / `_synapse_recalled` fields — already computed in
  `_apply_synapse_boost`, already rendered in CLI L3 text output.
- CLI `--trace`/`--trace-verbose`/`--explain` — already shipped (PRD 3 Phase 1).

## 3. Design Decisions
- **Structured JSON, not `render_text()`, for the MCP payload.** `render_text()`
  remains the CLI-facing renderer. A downstream agent consuming the trace over MCP
  needs structured data to reason about (which node, how much boost, from which
  seed), not a formatted string — this also matches PRD 3 Functional Requirement
  #4 ("Trace payloads must be exportable as JSON").
- **A new `record_hit_synapse_boost()` method, not overloading
  `record_synapse_boost()`.** The existing method is typed against an int
  community id (`comm: int`) for L2 cluster-level attribution. L3 operates on
  individual hit node ids (`str`), which doesn't fit that shape — a sibling method
  keeps both call sites unambiguous rather than making `comm` do double duty.
  Adds a `recalled: bool` field distinguishing a hit that was already present and
  got re-ranked upward from one pulled in purely by co-activation (absent from
  vector search) — a distinction the L2 path doesn't need but L3 does, since
  `_apply_synapse_boost` has both cases (see `context_selector.py`'s "(a) boost
  in place" vs "(b) displace weakest for absent neighbor" comments).
- **Opt-in, zero default overhead.** Both new MCP params default to `False`; when
  unset, `tool_query`'s response shape is byte-identical to before this change.

## 4. Files Touched
- `neuralmind/mcp_server.py` — `tool_query` signature + body, `TOOLS["neuralmind_query"].inputSchema`, `handle_tool_call` dispatch lambda
- `neuralmind/context_selector.py` — `_apply_synapse_boost` (traced recall path, two record-call sites)
- `neuralmind/trace.py` — new `RetrievalTrace.record_hit_synapse_boost()`
- `tests/test_context_selector.py` — `TestSynapseBoost.test_boost_records_trace_event`, `test_kill_switch_disables_boost_trace`
- `tests/test_trace.py` — `test_record_hit_synapse_boost`
- `tests/test_mcp_server.py` — new `TestQueryTrace` class (4 tests: attach payload, default omits, `trace=True` with no underlying trace omits key, dispatch threading)

## 5. Test Plan
- Unit: `RetrievalTrace.record_hit_synapse_boost()` produces a well-formed event
  for both the boosted-in-place and pulled-in-by-recall cases (`tests/test_trace.py`).
- Unit: `_apply_synapse_boost` records a trace event per boosted hit when
  `self._trace` is set, and records nothing when the kill switch
  (`NEURALMIND_SYNAPSE_INJECT=0`) disables boosting entirely — the kill switch
  must no-op the trace call, not just the boost (`tests/test_context_selector.py`).
- Integration: `tool_query(..., trace=True)` returns a `trace` key shaped like
  `RetrievalTrace.to_dict()`; default omits it; `handle_tool_call` threads
  `trace`/`trace_verbose` from MCP call arguments (`tests/test_mcp_server.py`).
- Full suite: `pytest tests/ -x -q` before opening the PR.

## 6. Non-Goals / Future Work
Mirrors the BRD's Non-Goals, technical framing:
- No new persistence layer or schema — `RetrievalTrace` remains scoped to one
  `query()` call's lifetime.
- No change to bounded payload size (`MAX_ITEMS=25`) or redaction behavior.
- PRD 3 Phases 3-4 (graph UI replay, issue-template attachment) untouched.
