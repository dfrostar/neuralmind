# NeuralMind — Three Key Benefits

**For the pitch. Not features — outcomes.**

---

## 1. Cost Savings — "Stop paying to paste your whole repo"

**The number:** 40-70× token reduction per code question. $2,800/mo → $400/mo for a 15-engineer team.

**The mechanism:** NeuralMind loads ~800 tokens of precisely-retrieved context instead of pasting 50K tokens of raw codebase. Same answer, 98% cheaper.

**The proof:** `neuralmind benchmark .` on your codebase. 30 seconds. Reproducible in CI on every commit.

**Who cares:** CFO, VP Eng, anyone paying per-token for AI agents.

---

## 2. Co-Breakage Awareness — "Catch what breaks together before CI"

**The number:** On a 9,600-node telehealth repo, NeuralMind caught that `notifications.ts` changes should prompt a check of `telegram.ts` and the PRD taxonomy. Without it, that drift would have hit CI or a reviewer.

**The mechanism:** The synapse layer learns which files you edit together. Before commit, `neuralmind review` surfaces co-break candidates — files historically associated with your changes that you haven't touched yet.

**The proof:** Measured in production sessions. Caught the PRD drift that manual grep + read would have missed.

**Who cares:** Senior devs, platform leads, anyone who's been burned by "I didn't know that file was related."

---

## 3. Onboarding Acceleration — "New engineers productive in days, not months"

**The number:** Session wakeup in 455 tokens vs. re-reading CLAUDE.md + TODO.md + last 20 messages. New engineer asks "how does billing work?" and gets a precise answer on day one — without reading 50K tokens or bothering a teammate.

**The mechanism:** NeuralMind learns your codebase architecture and remembers it across sessions. The synapse layer pre-fetches related modules. Session recovery is one tool call, not five.

**The proof:** Measured wake-up tokens (455) and query tokens (~800-1,033) on real production repos. Onboarding time estimate: 3 months → 3 weeks.

**Who cares:** CTO, VP Eng, team leads hiring into AI-assisted workflows.

---

## The Pitch (one sentence each)

| Benefit | Pitch |
|---------|-------|
| **Cost** | "Cut your AI agent token bill by 95%. Measured, not marketed." |
| **Quality** | "Catch what breaks together — before CI, not after." |
| **Speed** | "New engineers productive on day one. Your codebase remembers." |

---

## What we DON'T lead with (Tier D — unmeasured)

- "Self-improving" — architecture complete, fitness gain unmeasured
- "Team memory" — structural seeds exist, co-view signal pending
- "SOC 2 compliant" — architecture supports, certification Q3 2027

Lead with the three measured benefits. Let the Tier D capabilities be discovered, not claimed.

---

*Pitch v1.0. Three benefits, all Tier C (CI-measurable, reproducible).*
