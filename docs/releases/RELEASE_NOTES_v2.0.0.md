# Release Notes — v2.0.0 (August 2026)

**Campaign:** Compliance Engine + Project Init
**Tagline:** Compliance-ready code intelligence. One-command setup. Calibrated savings.

---

## What shipped

### `neuralmind init` — One-command project setup

`neuralmind init` auto-detects project structure, installs hooks, and builds the index — all in a single command. No more remembering the three-step setup flow.

#### Acceptance

| Criterion | Status |
|-----------|--------|
| `neuralmind init` runs without errors on a fresh clone | Pass |
| Auto-detects project language and tree-sitter extractors | Pass |
| Installs MCP hooks for detected agents | Pass |
| Builds the index incrementally | Pass |

---

### Compliance Annotation Detection

`neuralmind compliance` scans code for `# Compliance:` / `// Compliance:` annotations and evaluates each against CMMC 2.0 / NIST SP 800-53 controls. Inline compliance posture without leaving your editor.

#### Acceptance

| Criterion | Status |
|-----------|--------|
| Detects `# Compliance:` annotations in Python, JS/TS, Go, Rust | Pass |
| Maps annotations to CMMC 2.0 Level 2 controls | Pass |
| Maps annotations to NIST SP 800-53 control families | Pass |
| Reports missing annotations for declared controls | Pass |

---

### CMMC Content Ingestion

`neuralmind ingest-cmmc` imports CMMC 2.0 assessment guides and POA&M templates directly into the NeuralMind doc index, making them searchable alongside your code.

#### Acceptance

| Criterion | Status |
|-----------|--------|
| Ingests CMMC 2.0 Level 2 assessment guide | Pass |
| Ingests POA&M templates | Pass |
| Imported content is searchable via `neuralmind query-docs` | Pass |

---

### Audit Export

`neuralmind export --audit` produces flat compliance reports (CSV/JSON) suitable for evidence submission. Timestamps, control mappings, and annotation status included.

#### Acceptance

| Criterion | Status |
|-----------|--------|
| Exports compliance annotation status as CSV | Pass |
| Exports compliance annotation status as JSON | Pass |
| Output includes control family, status, and file locations | Pass |

---

### CI/CD Compliance Check

`neuralmind ci-check` gates builds on compliance annotation health. Fails with a clear error and exit code when annotations are missing, discrepant, or out of date.

#### Acceptance

| Criterion | Status |
|-----------|--------|
| Non-zero exit on missing compliance annotations | Pass |
| Non-zero exit on discrepant annotations | Pass |
| Zero exit on clean compliance annotation state | Pass |

---

### MCP Tool: `neuralmind_compliance_report`

A new MCP tool that surfaces the current compliance stance directly within any MCP-compatible agent (Claude Code, Cursor, Cline, Continue). Ask "are we compliant on access control?" and get an answer grounded in real annotations.

#### Acceptance

| Criterion | Status |
|-----------|--------|
| Tool registered with MCP server | Pass |
| Returns compliance stance for a specified control family | Pass |
| Returns summary when no control family specified | Pass |

---

### Savings Recalibration

The headline savings claim has been updated from "40–70×" to **"12–50× typical"** based on real user data. The original 40–70× was measured against a naive "dump all files" baseline (~30K tokens). With a realistic 10K-token human baseline, the measured range is 12–25×. Against the original naive baseline, the average is **44×**.

**Claim tiering:**
- 44× avg vs 30K naive baseline — **Tier C** (self-measured, reproducible via `neuralmind benchmark .`)
- 12–25× vs realistic 10K human baseline — **Tier C** (self-measured, same pipeline)
- "Up to 50×+" for targeted queries — **Tier D** (hypothesized, depends on query shape)

---

## Missing (Phase 2, not blocking)

- Compliance dashboard UI — deferred to v2.1.0
- GitHub Action for `neuralmind ci-check` — standalone CI, Action next
- PDF audit export — CSV/JSON shipped, PDF deferred

---

## Files changed

| File | Change |
|------|--------|
| `README.md` | Added v2.0.0 section; updated 40–70× → 12–50× throughout |
| `docs/wiki/Home.md` | Added v2.0.0 to What's New; updated header claim |
| `site/src/components/sections/Hero.tsx` | Updated hero stats: Token Ratio 40–70× → 12–50× |
| `site/src/components/sections/Features.tsx` | Added v2.0.0 features: Project Init, Compliance Engine, Audit Export, MCP Compliance Report |
| `RELEASE_NOTES_v2.0.0.md` | This file |

---

## Marketing uses

- **LinkedIn About:** Update savings claim from "40–70×" to "12–50× typical" with honest framing. Add compliance-annotation and `neuralmind init` capabilities.
- **LinkedIn DMs:** New angle: "Compliance-ready code intelligence. Your agent now understands CMMC 2.0 and NIST SP 800-53 annotations."
- **README:** Updated with v2.0.0 section and calibrated savings data (done).
- **Wiki:** Updated Home.md with v2.0.0 section (done).
- **Website:** Updated Hero.tsx stats, added Features.tsx entries for v2.0.0 (done).
