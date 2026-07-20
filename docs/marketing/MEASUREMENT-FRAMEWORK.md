# NeuralMind Rebuild — Effectiveness Measurement Framework

**Date:** 2026-07-23
**Purpose:** Quantify index quality before/after rebuild for marketing claims
**Methodology:** Run benchmark + stats, compare against known baselines, tier all claims

---

## 1. What to Measure

| Metric | Command | Marketing Use |
|--------|---------|---------------|
| Graph nodes | `neuralmind stats .` | "Indexes N symbols across codebase" |
| Graph edges (calls/imports/contains) | `neuralmind stats .` | Depth of code understanding |
| Query reduction ratio | `neuralmind benchmark .` | "Cuts agent token spend 40-70x" |
| Wake-up tokens | `neuralmind benchmark .` | Efficiency per query |
| Communities | `neuralmind stats .` | Architectural awareness |
| Multi-language coverage | `neuralmind stats .` | "Understands N languages" |
| Benchmark latency | `time neuralmind benchmark .` | Proof of speed |

## 2. Baseline (pre-rebuild, from memory)

| Metric | Last Claimed | Claim Tier |
|--------|--------------|------------|
| Nodes | 11,530 | C |
| Communities | 593 | C |
| Query reduction | 48.1x | C |
| Wake-up tokens | 500 | C |

## 3. Measurement Protocol

```bash
# Step 1: Full graph stats
neuralmind stats .

# Step 2: Full benchmark (with timing)
time neuralmind benchmark . 2>&1

# Step 3: Edge type distribution
python3 -c "
import json
with open('graphify-out/graph.json') as f:
    g = json.load(f)
    edge_types = {}
    for l in g['links']:
        rel = l.get('relation','')
        edge_types[rel] = edge_types.get(rel, 0) + 1
    for k, v in sorted(edge_types.items(), key=lambda x: -x[1]):
        print(f'  {k}: {v}')
"

# Step 4: Query-specific reduction (real agent queries)
echo "How does auth middleware work?" | neuralmind query .
echo "Where is the license validator?" | neuralmind query .
echo "How does the tuner optimize parameters?" | neuralmind query .

# Step 5: Savings calculation
neuralmind savings .
```

## 4. Claim Tiering (Honest)

| Tier | Definition | What Qualifies |
|------|------------|----------------|
| **A** | Verifiable by architecture | Local-first, no phone-home, agent-agnostic |
| **B** | Third-party benchmark | Independent audit, academic paper |
| **C** | Self-measured, reproducible | `neuralmind benchmark .` output, CI-tracked |
| **D** | Hypothesized, unmeasured | Self-improving lift, team memory onboarding ROI |

## 5. Marketing Message Stack (Validated)

**Tier A claims (architectural facts):**
- "Your code never leaves your machine" — 100% local, no telemetry
- "Works with every agent" — Claude Code, Cursor, Cline, any MCP client
- "Open source MIT core" — free forever, no vendor lock-in

**Tier C claims (CI-measured, reproducible):**
- "Cut your AI agent token bill 40-70x" — `neuralmind benchmark .`
- "Measured, not marketed" — every number traces to a command you can run
- "Rebuilds your code graph automatically" — file watcher + commit hooks

**Do NOT market (no evidence yet):**
- "Self-improving" — Tier D, no production evidence of fitness gain
- "Team memory that learns" — Tier C, shipped but unmeasured for lift
- "SOC 2 compliant" — false, architecture supports but not certified

## 6. Output Deliverables

| Deliverable | File |
|-------------|------|
| Raw benchmark data | `docs/marketing/rebuild-measurement-20260723.md` |
| Before/after comparison table | Same file |
| Claim tier verification | Same file |
| Marketing one-liner refresh | `internal/cfo-deck-pick-prompt.md` update |

---

*Framework v1.0. Execute after `neuralmind build` completes. All claims tiered.*
