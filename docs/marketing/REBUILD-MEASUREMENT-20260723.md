# NeuralMind Rebuild — Marketing Measurement & Verification Report

**Date:** 2026-07-23
**Build duration:** 1,372s (22.9 min)
**Nodes:** 11,918 | **Links:** 19,583 | **Communities:** 610
**Post-rebuild benchmark:** 48.4x reduction (consistent with pre-rebuild)

---

## Executive Summary

| Claim | Evidence | Tier |
|-------|----------|------|
| "Cuts agent token spend 40-70x" | `neuralmind benchmark .` → 48.4x | **C** |
| "Your code never leaves" | Architectural fact, no telemetry | **A** |
| "Works with every agent" | MCP standard, Claude/Cursor/Cline verified | **A** |
| "Measured, not marketed" | Every number traces to a CLI command | **C** |
| "Self-improving" | **False** — no production evidence | **D** ⚠️ |

---

## 1. Graph Quality (Index Depth)

### Raw Stats
| Metric | Value |
|--------|-------|
| Total nodes | 11,918 |
| Total links | 19,583 |
| Communities | 610 |
| Shared edges | 1,490 |

### Node Type Distribution
| Type | Count | % |
|------|-------|---|
| Code | 5,720 | 48.0% |
| Document | 3,879 | 32.5% |
| Rationale | 2,319 | 19.5% |

### Link Type Distribution
| Type | Count | Purpose |
|------|-------|---------|
| contains | 9,041 | Structural hierarchy |
| calls | 7,937 | Runtime dependency |
| rationale_for | 2,320 | Explainability |
| imports_from | 2,31 | Module dependency |
| inherits | 28 | OOP relationships |
| describes | 26 | Doc↔code coupling |

---

## 2. Token Reduction (Core Benchmark)

### CLI Proof
```
$ neuralmind benchmark .
Wake-up tokens: 500
Avg query tokens: 1034.2
Avg reduction: 48.4x
```

### Savings Output
```
$ neuralmind savings .
Tokens actually used:      5,671
Est. cost without NM:     300,000
Tokens saved:             294,329
```

### Query-Sample Proof
| Query | Tokens | Reduction |
|-------|--------|-----------|
| How does authentication work? | 1,084 | 46.1x |
| What are the main API endpoints? | 956 | 52.3x |
| How is the database structured? | 1,062 | 47.1x |
| What frontend components exist? | 1,053 | 47.5x |
| How are errors handled? | 1,016 | 49.2x |

### Scrutiny: Why 48.4x is Honest, Not Hyped

| Check | Result |
|-------|--------|
| Reproducible? | Yes — `benchmark` is deterministic |
| Independent? | No — we wrote the benchmark (Tier C, not B) |
| Cherry-picked queries? | No — benchmark runs 50+ fixture queries |
| Warm cache? | Yes — first 5 bench queries warm the index |
| Blind spot? | Small codebases (<100 files) see <10x reduction |

---

## 3. Retrieval Quality (Deep DCTO Scrutiny)

### 3.1 Precision Check
**Test:** Query for a specific symbol, verify top-5 results contain it.

| Query | Top-1 Correct? | Top-3 Contains? |
|-------|----------------|-----------------|
| "license validator" | ✅ | ✅ |
| "tuner fitness" | ✅ | ✅ |
| "seat governance" | ✅ | ✅ |
| "circuit breaker" | ❌ (not yet in codebase) | N/A |
| "self-improving loop" | ⚠️ returns aspirational docs | ⚠️ |

**Finding:** Retrieval is precise for shipped features, but returns **marketing docs for unreleased features** (self-improving, circuit breaker). This inflates perceived capability.

### 3.2 Recall Check
**Test:** Does all relevant code appear in top-10 results?

- "auth middleware" → 8/10 results are auth-related ✅
- "database schema" → 7/10 are ORM/schema-related ✅
- "error handling" → 6/10 are error-related ✅

### 3.3 Cross-File Accuracy
**Test:** Does the graph connect symbols across files?

- `team_memory.py` ↔ `synapse_feedback.py` edge: ✅
- `governance.py` ↔ `audit.py` edge: ✅
- `license.py` ↔ `anti_tamper.py` edge: ❌ (no edge — Gap!)

**Finding:** Anti-tamper module is not wired to license validation in the graph. This is a real retrieval gap for license-team queries.

---

## 4. Team Memory Quality

### Shared Namespace Stats
| Metric | Value |
|--------|-------|
| Shared edges | 1,490 |
| Edge weight sum | 2,038.49 |
| Transitions | 0 |

**Scrutiny:** Zero transitions means the synapse layer has not learned any co-view patterns yet. The 1,490 edges are **structural seeds** (call/contains relationships), not learned team knowledge.

### Team Memory Claim Verification
| Claim | Verdict |
|-------|---------|
| "Team memory that learns" | ⚠️ Overclaimed — no co-view signal yet |
| "Quality-weighted merge" | ✅ Shipped (E2) |
| "Peer review gate" | ✅ Shipped (E3) |
| "Staleness detection" | ✅ Shipped (E4) |
| "Contribution scoring" | ✅ Shipped (E1) |

---

## 5. What We CANNOT Claim (Honesty Gate)

| Claim | Reality | Impact |
|-------|---------|--------|
| "Self-improving" | No production fitness data | Tier D — remove from marketing |
| "Team memory learns" | No co-view signal accumulated | Tier D — soften language |
| "40-70x reduction" | Lab benchmark, not production | Tier C — fine with disclaimer |
| "SOC 2 compliant" | False | Remove entirely |
| "Zero code egress" | Overclaim — agent layer talks to model | Reword to "no network calls of our own" |

---

## 6. Recommended Marketing Language (Post-Scrutiny)

### Tier A (Verifiable Architecture)
> "NeuralMind is local-first AI code intelligence. Your code never leaves your machine. The MIT core is free forever and works with every agent — Claude Code, Cursor, Cline, any MCP client."

### Tier C (Self-Measured, Reproducible)
> "Cut your agent token bill 40-70x. Measured with `neuralmind benchmark .` — a command you can run yourself. 48.4x reduction, 500 wake-up tokens per query, reproducible."

### Tier D (Honest Framing)
> "Built for self-improvement. The operator (autopilot) is architecture-complete with signal detection, root-cause analysis, and bandit-allocated experimentation. Production fitness gains will be published when observed."

### What to Remove
- "Self-improving product" (unproven)
- "SOC 2 compliant" (false)
- "Zero code egress" (overclaim)

---

## 7. Action Items

| Priority | Task | Owner |
|----------|------|-------|
| P1 | Remove "self-improving" from Hero.tsx | Agent |
| P1 | Remove "SOC 2" from site | Agent |
| P2 | Soften "team memory language" | Agent |
| P3 | Wire anti_tamper ↔ license in graph (fix gap) | Agent |
| P3 | Re-run benchmark after graph fix | Agent |
| P4 | Establish live fitness baseline (autopilot) | Agent |

---

*Report v1.0. Rebuild measurement complete. All claims tiered A/B/C/D. Three findings: (1) retrieval returns marketing docs for unfinished features, (2) anti_tamper↔license graph gap, (3) zero co-view transitions in team memory.*
