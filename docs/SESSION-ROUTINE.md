# Session Routine — Standardized Workflow

**Version:** 1.0.0
**Date:** 2026-07-21
**Purpose:** A repeatable routine for every session transition — pickup, execute, document, handoff. Improves over time.

---

## The Session Lifecycle

Every session follows this lifecycle, regardless of what work is being done:

```
┌─────────────────────────────────────────────────────────────┐
│ 1. PICKUP (5-10 min)                                         │
│    - Read session prompt / handoff doc                       │
│    - Verify state against git log (CRITICAL: don't trust     │
│      prompts blindly — cross-reference commits)              │
│    - Run tests in both repos                                 │
│    - Report current state to user                            │
├─────────────────────────────────────────────────────────────┤
│ 2. EXECUTE (rest of session)                                 │
│    - Load required skills                                    │
│    - Build → test → document in same pass                    │
│    - Dispatch DeepSeek QA for per-module review              │
│    - Patch CRITICAL + WARNING findings immediately            │
│    - Run tests after every patch                             │
├─────────────────────────────────────────────────────────────┤
│ 3. DOCUMENT (end of session)                                 │
│    - BRD/TRD for the wave (if planning)                      │
│    - QA Report (DeepSeek findings + patches + test results)  │
│    - Test Plan (test files, what they cover, how to run)     │
│    - Decisions (ADR format)                                  │
│    - ROADMAP sync (if ship)                                  │
├─────────────────────────────────────────────────────────────┤
│ 4. HANDOFF (last 10 min)                                     │
│    - Next-session prompt (self-contained, paste-ready)       │
│    - Dated report (archival, preserved in repo)              │
│    - Commit + push all doc artifacts                         │
│    - Update memory/skill if lessons learned                  │
└─────────────────────────────────────────────────────────────┘
```

---

## 1. PICKUP — Session Start Checklist

### 1.1 Read the Prompt
- Open the session prompt / handoff doc
- Note the claimed current state (version, tests, last commit)

### 1.2 Verify Against Git Log (CRITICAL)
- Run `git log --oneline -20` in EACH repo
- Compare claimed state against actual commits
- If discrepancy: report to user BEFORE proceeding
- This prevents building on stale assumptions

### 1.3 Run Tests
```bash
# autopilot
cd /home/dtfrost/neuralmind-autopilot && PYTHONPATH=. python3 -m pytest tests/ -q

# neuralmind (tier2 first, fast)
cd /home/dtfrost/neuralmind && PYTHONPATH=. python3 -m pytest tests/test_tier2_seats.py tests/test_tier2_governance.py tests/test_tier2_license.py tests/test_v049_patches.py -q

# neuralmind (full, may take 5+ min — run in background)
cd /home/dtfrost/neuralmind && PYTHONPATH=. python3 -m pytest tests/ -q --tb=no
```

### 1.4 Upgrade Check
```bash
# Check if pip package is behind repo
pip show neuralmind | grep Version
cd /home/dtfrost/neuralmind && grep -m1 "__version__" neuralmind/__init__.py

# If pip is behind:
pip install --upgrade neuralmind
```

### 1.5 Report State
- "Autopilot: v0.X, N/N tests green, last commit: <sha> <msg>"
- "NeuralMind: v0.X, N/N tests green, last commit: <sha> <msg>"
- Flag any discrepancies

---

## 2. EXECUTE — Build Loop

### 2.1 Load Skills
Load the skills named in the session prompt. Don't skip even if you "know" the pattern — skills encode pitfalls learned from prior sessions.

### 2.2 Build → Test → Document
For each workstream:
1. Write code following existing patterns
2. Write tests alongside code (not after)
3. Run tests immediately after writing
4. Document the module (docstring + BRD/TRD update)
5. Commit when green

### 2.3 DeepSeek QA Dispatch
For every new/changed module, dispatch DeepSeek review:
- One subagent per module (never batch)
- Inline the actual code (don't ask DeepSeek to read files)
- Pin model: `{"provider": "deepseek", "model": "deepseek-v4-pro"}`
- Request patch diffs (not just findings)
- Apply CRITICAL + WARNING after verification against actual code

### 2.4 Parallel Execution
When workstreams are independent:
- Use `delegate_task` with `tasks=[...]` for parallel dispatch
- Max 3 concurrent subagents
- Main thread continues on dependent workstreams
- Consolidate results when all return

---

## 3. DOCUMENT — End-of-Session Artifacts

### 3.1 BRD (Business Requirements Document)
- File: `docs/WAVE<N>-BRD.md`
- Sections: Problem, Objectives, Stakeholders, Workstreams, Risks, Release Criteria
- Claim tier every objective (A/B/C/D)

### 3.2 TRD (Technical Requirements Document)
- File: `docs/WAVE<N>-TRD.md`
- Sections: Scope, Architecture, Component Requirements, Database, Security, Test Plan, Acceptance
- Cross-reference prior TRDs/BRDs

### 3.3 Test Plan
- File: `docs/WAVE<N>-TEST-PLAN.md`
- Sections: Scope, Test Files, Critical Tests, Edge Cases, Running, Definition of Done
- List every test file and what it covers

### 3.4 QA Report
- File: `docs/WAVE<N>-QA-REPORT.md`
- Sections: Summary (CRITICAL/WARNING counts), Findings (per-module), Test Coverage, Recommendations
- Include patch diffs for every finding

### 3.5 Decisions (ADR)
- File: `docs/WAVE<N>-DECISIONS.md`
- One ADR per significant decision: Context, Decision, Consequences, Alternatives

### 3.6 ROADMAP Sync
- Update `ROADMAP.md` if new forward candidates emerged
- Move completed items to "Shipped" section

---

## 4. HANDOFF — Session End Checklist

### 4.1 Next-Session Prompt
- File: `docs/WAVE<N>-SESSION-PROMPT.md` or `NEXT-SESSION.md`
- Self-contained: paste into fresh session, picks up without prior context
- Sections: Recap, Goal, Versioning, Conventions, Skills to Load, Start Here, Pre-Flight

### 4.2 Dated Report
- File: `docs/handoffs/YYYY-MM-DD-<slug>.md`
- Archival: preserved in repo as immutable milestone marker
- Sections: State of Project, Phases, Decisions, Verification Commands, What to Do Next, Blockers, Git Log

### 4.3 Commit + Push All Artifacts
```bash
cd /home/dtfrost/neuralmind
git add docs/ tests/ src/
git commit -m "docs: Wave N BRD/TRD/QA report + test plan"
git push
```

### 4.4 Update Memory/Skill
- If a new pitfall was discovered: update the relevant skill
- If a new pattern was established: create a new skill
- If a user preference was stated: update memory

---

## 5. IMPROVEMENT LOG

Track improvements to this routine over time:

| Date | Improvement | Why |
|------|-------------|-----|
| 2026-07-21 | Created routine document | Standardize session-to-session workflow |
| | | |

---

## 6. Common Pitfalls (from prior sessions)

1. **Don't trust handoff prompts blindly.** Always verify against git log.
2. **Don't skip DeepSeek QA.** Every module gets reviewed.
3. **Don't batch DeepSeek dispatches.** One subagent per module.
4. **Don't apply CRITICAL findings without verification.** ~20% false positive rate.
5. **Don't forget to run tests after patching.** Stale test expectations are real.
6. **Don't skip the dated report.** It's the archival record.
7. **Don't stop at "code works."** Documentation IS the product.
8. **Don't rebuild on stale index.** Run `neuralmind build` before tagging.

---

*Routine v1.0.0. Improves every session.*
