# NeuralMind — Messaging Architecture

**Date:** 2026-07-23
**Purpose:** Unified messaging framework from positioning → content across all public touchpoints
**Based on:** April Dunford positioning methodology + 2026 signal-anchored outreach best practices
**Owner:** Darren Frost (cheval-volant_llc)

---

## 1. Positioning Foundation (April Dunford Model)

### 1.1 Competitive Frame
**You are the best choice for:** development teams (10+ devs) on 10K+ line codebases who are paying per-token for AI agent inference and hitting context limits weekly.

**You replace:** blind "paste the whole repo" context-loading and the developer-hours burned finding the right file.

**Why you are the obvious choice:** you shrink the "what context to load" decision from O(repo) to O(query), measured 40-70× retrieval-stage reduction in CI on every commit — while keeping 100% of the code local.

### 1.2 Why Now (The "Why Now" Trigger)
The AI agent token bill has become a line item, not a rounding error. Claude Code / Cursor / Cline usage scales linearly with codebase size — every new file is another context load. Long-context models (1M, 2M tokens) plus prompt caching give ~90% compression WITHOUT retrieval infrastructure — that's the honest competitor. NeuralMind's marginal win is additive to caching, not a replacement for it. The gap: until now, nobody could see where their AI spend actually went. NeuralMind gives per-query, per-developer attribution — and that transparency story is the wedge.

### 1.3 The Honest Boundary
**NOT for:** codebases under 5K lines, free-tier users, inline-completion-only workflows, teams already deep into prompt caching + long context. We say this explicitly — our brand is honesty > hype.

---

## 2. Touchpoint Inventory (All Public-Facing Surfaces)

### 2.1 GitHub Repository (`github.com/dfrostar/neuralmind`)

| Element | What It Says | Audience | Gap |
|---------|-------------|----------|-----|
| README headline | "Persistent memory and context compression for AI coding agents. Queries your codebase in ~800 tokens instead of ~50,000" | Dev + CTO | Missing: transparency hook as primary messaging. No "what it's NOT for" section. |
| Community benchmarks | n=2 (project-alpha 65.6×, project-beta 46.0×), honestly labeled "directional" | CFO + Dev | Need: n=10+ outside repos, telehealth 60× data missing here |
| Topics/tags | 21 tags including agent-memory, local-first, mcp, token-reduction, synapse-layer | Dev + SEO | Could add: code-intragrity, context-compression, blast-radius |
| Description tagline | "Persistent memory for AI coding agents. Your agent learns the codebase like a senior engineer... 100% local. (Side effect: 40-70× cheaper code questions.)" | Dev + CTO | Good. |
| Releases (latest: v1.5.0) | Detailed release notes per version | Dev + CTO | Need: a releases-summary.md that aggregates the story |
| SECURITY.md | Comprehensive, honest, SBOM, hash-chained audit, "architecture supports but not certified" | Security Engineer | Excellent. Updated 2026-06-30. |
| CHANGELOG.md | Exhaustive | Dev | Need: narrative summary at top |

### 2.2 PyPI

| Element | Current | Gap |
|---------|---------|-----|
| Summary | Persistent memory and context compression for AI coding agents | Missing: transparency hook |
| Version | 1.5.0 | Stale vs. current release (v1.4.0 shipped, v1.5.0 on PyPI) |

### 2.3 Website (neuralmind.uk)

| Page | Headline | Audience | Gap |
|------|----------|----------|-----|
| Homepage | "Your agent learns your codebase. And remembers it. 40–70× token reduction." | Dev + CTO | Good. Missing: transparency pillar as primary hook |
| Security | "Transparent security info" | Security Engineer | Good. SOC 2 Q3 2027 target visible |
| Effectiveness | "48.8× token reduction on a real CRM" | CFO + Dev | Excellent. Honest caveats are strong |
| Publications | Claude teams deep dive, QWM | Dev + CTO | Good. Needs: case study framing update |
| Privacy | Privacy policy | All | Good |

### 4.4 GitHub Pages / Docs (`docs.neuralmind.uk/wiki`)

| Element | Current | Gap |
|---------|---------|-----|
| Wiki home | "Reduce Claude, GPT, and Gemini token costs 40–70×" | Good. Missing: honest "when NOT to use" callout |
| Benchmarks page | Detailed benchmark methodology | Good |

### 4.5 LinkedIn (Personal Profile: Darren Frost)

| Artifact | Current | Gap |
|----------|---------|-----|
| Headline | "M&A Integration & Carve-Out / Separation..." | Doesn't mention NeuralMind in primary position |
| Activity | Posts about AI, OpenSource, tools | Good foundation. Need: fresh effectiveness data |

### 4.6 Outreach (Outbound / AgentMail)

| Artifact | Current | Gap |
|----------|---------|-----|
| v0.53.0 post draft | "Governance-as-a-seat" thesis | Stale — for monetization launch, not current effectiveness story |
| v0.53.0 outreach targets (7) | Built for monetization thesis | Stale — need rebuild for transparency + compression story |
| Previous validated posts | Transparency + cost-reduction | Good foundation, update with telehealth data |

### 4.7 Other Surfaces

| Surface | Status |
|---------|--------|
| Twitter/X | No active presence (@neuralframes, @Neural_pro are unrelated). Opportunity. |
| Reddit | No creator-posts yet. r/selfhosted is the highest-value target. |
| Hacker News | No Show HN yet. Timing: after next measurement publication. |

---

## 3. Messaging Hierarchy (Validated — Measurement-Framework v1.0)

| Priority | Pillar | Claim | Evidence Tier | Source |
|----------|--------|-------|---------------|--------|
| 1 | **Transparency** | "Your AI agent bill is a black box — we open it" | C | `neuralmind savings` output, per-query attribution |
| 2 | **Context Compression** | "60× token reduction on real production repos" | C | CI benchmarks, telehealth 9,600-node repo data |
| 3 | **Co-Breakage Awareness** | "Catches what bumps break together — before CI" | C | Session data: caught PRD drift on notifications.ts |
| 4 | **Session Recovery** | "Wake back up in 455 tokens, not 20 messages" | C | Effectiveness page: 455 wake-up tokens measured |
| 5 | **Local-First** | "Code never leaves your machine" | A | Architectural fact — no phone-home, no telemetry |
| 6 | **Agent-Agnostic** | "Works with every MCP agent" | B | Claude Code, Cursor, Cline, Continue, any MCP client |

**What we DO NOT market yet (Tier D):**
- "Self-improving" — architecture complete, fitness gain unmeasured
- "Team memory" — structural seeds exist, co-view signal pending
- "SOC 2 compliant" — architecture supports, certification Q3 2027

---

## 4. Audience-to-Message Mapping

| Audience | Primary Pain | Hook | Message | CTA |
|----------|-------------|------|---------|-----|
| **CFO / VP Eng** | "We spend $500K/yr on AI tokens with no visibility" | "Find $144K/yr waste in your AI agent spend" | Per-query attribution + 40-70× compression | Free full spend model email |
| **CTO / Platform Lead** | "New engineers take 3 months to learn the codebase" | "Your AI agents learn your codebase — and remember it" | Hebbian synapses + session recovery | GitHub stars → team tier |
| **Senior Dev** | "My Claude Code bill hit $240/mo" | "One pip install cut it to $40" | Same questions, stop pasting the whole repo | `pip install neuralmind` |
| **Security Engineer** | "I can't send our codebase to a SaaS" | "Your code never leaves your machine" | 100% local engine, SBOM, hash-chained audit | Security audit → team tier |

---

## 4. Touchpoint Inventory & Current Messaging

### 4.1 Public Website (neuralmind.uk)

| Page | Current Headline | Audience | Gap |
|------|-----------------|----------|-----|
| Homepage | "Your agent learns your codebase. And remembers it. 40–70× token reduction." | Dev + CTO | Good. Missing: transparency pillar as primary hook |
| Security | "Transparent security info" | Security Engineer | Good. SOC 2 Q3 2027 target is visible |
| Effectiveness | "48.8× token reduction on a real CRM" | CFO + Dev | Excellent. Honest caveats are strong |
| Publications | Claude teams deep dive, QWM | Dev + CTO | Good. Needs: case study framing update |

**Homepage refresh recommendation:** Lead with the transparency crisis ("Your AI bill is a black box") as the opening hook, with 40-70× as the proof anchor. This follows the validated hierarchy from Section 2.

### 4.2 GitHub Repository

| Element | Current | Gap |
|---------|---------|-----|
| README title | "NeuralMind — Persistent Memory for AI Coding Agents" | Missing: transparency hook, honest caveat |
| Community benchmarks | n=2, honestly labeled | Need: n=10+ outside repos claim |
| Features list | 10 items | Need: "what it's NOT for" section |

### 4.3 LinkedIn (personal profile + outreach)

| Artifact | Current | Gap |
|----------|---------|-----|
| v0.53.0 post draft | "Governance-as-a-seat" thesis | Stale — was for monetization launch, not current effectiveness story |
| Outreach targets (7) | Built for monetization thesis | Stale — need rebuild for transparency + compression story |
| Previous validated posts | Transparency + cost-reduction | Good foundation, update with telehealth data |

### 4.4 Docs

| Document | Current State | Gap |
|----------|--------------|-----|
| HONEST-ASSESSMENT.md | Comprehensive, honest, well-structured | Update with telehealth 60× and project-alpha 65× data points |
| BUSINESS-CASE.md | Solid ROI math | Update sensitivity analysis with 60× headline number |
| MEASUREMENT-FRAMEWORK.md | Claim tiers defined | Add telehealth effectiveness data as new Tier C evidence |

---

## 5. LinkedIn Cold Outreach Sequence (2026 Refresh)

### 5.1 The Three-Part Sequence

**Part 1: Value-First Insight Post (Week 0)**
- Hook: "We measured 60× token reduction on a 9,600-node healthcare codebase. Here's what we actually found."
- Body: Honest-fit framing — who it's for, who it's NOT for, what we can't claim yet
- CTA: "Has your team measured this?" (engagement question, no pitch)

**Part 2: Signal-Anchored DMs (Week 1-2)**
- Target selection: CTO/VP Eng at healthcare, fintech, defense (regulated = local-first resonance)
- DM framework: "Reference specific post they made → share our measurement → trade notes (not pitch)"
- No demo, no signup, no meeting link

**Part 3: Methodology Share (Week 3)**
- Target: Hard peers — MCP builders, code-graph authors, eval-harness maintainers
- Message: "We benchmarked transparency on a real codebase — here's the script. Want to compare notes?"

### 5.2 Target Profile Selection (Three-Axis)

Every target must satisfy ≥2:
1. **Domain expertise** — built/shipped codebase intelligence, MCP server, code-graph, or eval harness
2. **Honest-eval posture** — public proof they evaluate critically, not just shill
3. **Audience overlap** — followers include OSS AI tooling developers

**Bonus:** profiles that explicitly use "local-first", "no cloud", "MIT", "100% local"

### 5.3 DM Script Rules (from b2b-social-content reference)
- Under 80 words
- One specific artifact target built or published
- Disclose maker identity + project
- Knowledge-exchange tone, not pitch
- No sale, no signup — "stars/issues/PRs welcome"

---

## 6. Contact List Refresh Plan

### 6.1 Deep Research Targets (TBD signal-anchored)

| Segment | Role | Where | Why |
|---------|------|-------|-----|
| Healthcare | CTO / VP Eng | Mid-market EHR / telehealth | Local-first + compliance resonance |
| Fintech | CFO / VP Eng | Mid-market fintech | Token cost visibility + security |
| DevTools | Founder / CTO | MCP / code-graph / code-intel | Technical credibility, peer channel |
| Defense | Engineering Lead | Cleared dev teams | Air-gapped, offline, self-hosted |

### 6.2 Existing Contacts to Retain (from v0.53.0 list)

| Name | Domain | Fits New Thesis? | Action |
|------|--------|-----------------|--------|
| Czar Khoe (Cal.com) | OSS team seats | Partial — monetization ref | Retain for future pricing story |
| Boris Tane (PostHog) | OSS self-hosted | Yes — transparency value prop | Re-engage with new angle |
| Tirth Kanani (code-review-graph) | Code-graph MCP | Yes — direct peer | Re-engage with evaluation ask |
| Bharadwaz Kari (Smriti MCP) | Local-first memory | Yes — shared problem | Re-engage with team-tier learnings |
| Peer Richel (Cal.com) | Seat model | Partial | Retain |
| Eli Schleifer (Mintlify) | OSS free-for-OSS | Partial | Retain |
| Bram Borggreve (Bundlephobia) | OSS cost-of-tooling | Yes — CFO cost framing | Re-engage with measurement focus |

### 6.3 Deep Research Required

Run deep research on:
- CTO/VP Eng at healthcare companies (5-500 employees) who posted about AI agent costs
- CFOs who authored "AI spend visibility" content on LinkedIn
- MCP server builders shipping code-graph or memory products
- Authors of code intelligence / RAG evaluation benchmarks

---

## 7. Content Calendar (First 30 Days)

| Week | Channel | Content | Owner |
|------|---------|---------|-------|
| 0 | LinkedIn | Insight post: "We measured 60× token reduction. Here's what we actually found." | Darren + AI |
| 0 | Site | Homepage hook refresh: "Your AI bill is a black box" → transparency lead | Darren + AI |
| 1 | LinkedIn | Signal-anchored DMs to 5 targets (healthcare + fintech CTOs) | Darren + AI |
| 1 | Docs | Update HONEST-ASSESSMENT.md with telehealth data | AI |
| 2 | Reddit | r/selfhosted creator-post: "Built local-first AI agent memory. Here's what broke." | Darren + AI |
| 2 | Outbound | AgentMail to 5 warm contacts with new assessment data | Darren + AI |
| 3 | LinkedIn | Peer DM to 5 MCP / code-graph builders | Darren + AI |
| 3 | Docs | Update README with honest caveats + new benchmarks | AI |
| 4 | LinkedIn | Case study post: "1 semantic search vs 20 grep calls — measured" | Darren + AI |

---

## 8. Claim Audit (Per-Post Gate)

Before publishing ANY content:
1. Extract every claim
2. Tier each (A/B/C/D)
3. Soften all D claims ("built for", "architecture supports", "may")
4. Verify C claims against CLI commands
5. Remove internal codenames (C4, E1, CI-Gated Tuner → "auto-tuner")
6. Label modeled vs measured
7. Run: "would I post this if it weren't my project?"

---

## 9. Skill Requirements

This architecture requires a new skill: `marketing-messaging-audit`

**Trigger:** "audit our messaging", "update our positioning", "refresh our LinkedIn approach", "check our public touchpoints"

**Deliverables:**
1. Touchpoint inventory (what exists, what it says, who's the audience)
2. Gap analysis (what's stale, what's missing, what's inconsistent)
3. Positioning refresh (April Dunford model applied quarterly)
4. Content calendar (30/60/90 day)
5. Claim audit per artifact

**References:**
- `references/messaging-architecture.md` (this document)
- `references/linkedin-outreach-targets.md` (current target list)
- `references/brand-voice-checklist.md` (voice enforcement)

## 10. Honest-Assessment Integration

The new LongCat 2.0 assessment (telehealth 9,600-node repo, project-alpha 1,080-node repo) provides fresh Tier C evidence. Update these artifacts:

| Artifact | Current | Update Needed |
|----------|---------|---------------|
| HONEST-ASSESSMENT.md | n=2 community benchmarks | Add telehealth 60× and project-alpha 65× data points |
| BUSINESS-CASE.md | 40-70× headline, n=2 | Update sensitivity analysis with 60× data |
| MEASUREMENT-FRAMEWORK.md | Baseline 48.1× | Add telehealth baseline measurement |
| Effectiveness page | CRM 48.8× | Add telehealth as second case study |
| README | n=2 benchmarks | Add telehealth data point |

---

*Architecture v1.0. Reviewed by: Darren Frost. Next review: 2026-10-23.*
