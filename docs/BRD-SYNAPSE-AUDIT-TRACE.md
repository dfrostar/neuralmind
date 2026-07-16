# Business Requirements Document: Synapse Audit Trace over MCP
**Product**: dfrostar/neuralmind v0.46.0 (target)  
**Date**: 2026-07-16  
**Owner**: Engineering / DevEx Team

## 1. Executive Summary
A Reddit comparison against GitNexus (an MCP-native code-intelligence competitor,
~42k GitHub stars) flagged "auditability" — showing *why* a result was returned — as
a capability NeuralMind lacked. That's mostly not true: `neuralmind/trace.py`'s
`RetrievalTrace` system already records candidate generation, cluster scoring,
synapse-boost attribution, final hits, and token budget, and the CLI has shipped
`--trace`/`--trace-verbose`/`--explain` since PRD 3 Phase 1. The real gap was
narrower: this trace was never wired into the MCP server, so any agent talking to
NeuralMind over MCP (the primary integration surface) had no way to ask "why did
you give me this?" This release closes that gap — it's an exposure fix, not a new
subsystem.

## 2. Relationship to PRD 3
This is `docs/plans/2026-06-10-future-proofing-prd-pack.md`'s **PRD 3:
Explainability and Debug Traces**, whose own rollout plan already scoped this exact
step:

> - Phase 1: CLI trace mode. *(shipped)*
> - Phase 2: MCP trace metadata. *(this release)*
> - Phase 3: Graph UI replay. *(not in scope)*
> - Phase 4: Issue template with trace attachment support. *(not in scope)*

This release ships PRD 3 Phase 2 exactly as scoped, and closes PRD 3's Functional
Requirement #1 ("`query` and equivalent MCP methods must support trace mode") for
the MCP surface — the CLI already satisfied it.

## 3. What Changes
| Surface | Before | After |
| --- | --- | --- |
| `neuralmind_query` (MCP) | No `trace` param; trace data unreachable over MCP | Optional `trace`/`trace_verbose` params attach the same structured trace CLI users already get |
| L3 hit-level synapse boosts | Recorded a boost value on each hit, but not *why* (which co-activation produced it) | Traced via the same energy-attribution path L2 cluster boosts already used |
| CLI `--trace`/`--explain` | Unchanged | Unchanged |
| Persistent/historical audit log | Does not exist | Still does not exist (see Non-Goals) |

## 4. Acceptance Criteria
- [ ] `neuralmind_query(project_path, question, trace=true)` MCP call returns a
      `trace` key shaped like `RetrievalTrace.to_dict()` (query, verbose, events)
- [ ] Default (`trace` omitted) omits the `trace` key — zero overhead, unchanged
      response shape for existing callers
- [ ] A boosted L3 hit's trace includes which seed(s) and how much energy produced
      the boost, not just the resulting score delta
- [ ] `pytest tests/test_trace.py tests/test_mcp_server.py tests/test_context_selector.py -k "trace or Trace or SynapseBoost or Query"` passes

## 5. Non-Goals / Future Work
Deliberately deferred to later PRD 3 phases or a separate future feature:
1. **Persistent, cross-session audit history.** This trace lives only for the
   duration of one query; there is no queryable "show me every past retrieval that
   surfaced file X" store. Would require a new JSONL/SQLite sink, comparable in
   scope to the existing `event_log.py`/`EventLogWriter` bridge.
2. **PRD 3 Phase 3 — Graph UI replay.**
3. **PRD 3 Phase 4 — Issue-template trace attachment.**
4. **A standalone `neuralmind_explain` MCP tool.** Extending `neuralmind_query`'s
   own output covers the ask; a separate tool would just wrap the same call.
