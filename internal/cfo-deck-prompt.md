# CFO Pitch Deck — Prompt for Generation

_Use this prompt with any deck builder (Gamma.app, Beautiful.ai, Canva, Powerpoint generator, or an LLM markdown converter). Copy the section below into your deck generator and follow the structure and constraints exactly._

---

## ROLE

Expert B2B SaaS pitch writer specializing in developer tools and AI cost optimization for mid-market CFOs (employees: 50–500, AI spend: $50K–$500K/yr). You write pitch decks that are defensible, not viral — every claim must survive a skeptical CFO's scrutiny.

## CORE MESSAGE

NeuralMind won't sell more AI tools. It sells governance and savings on the AI tools that teams already use — MIT-core free forever, paid tier only for governance features that address CFO-level risk (audit, compliance, seat management, self-hosted deployment).

---

## DECK STRUCTURE

Generate exactly **8 slides**, in this order. Each slide must have:
- Title (≤8 words)
- 3–5 bullets (≤15 words each)
- Optional: one-sentence footer for data sources

### SLIDE 1: TITLE
**Title:** NeuralMind — AI Code Intelligence, Local-First
**Subtitle:** The MIT-core tool that measures, reduces, and governs AI inference spend
**Footer:** neuralmind.uk | docs.neuralmind.uk | github.com/dfrostar/neuralmind

### SLIDE 2: THE PROBLEM (TITLE: "The AI inference bill is invisible")
**Bullets:**
- Your engineering team runs Claude Code, Cursor, Cline — nobody tracks per-developer spend
- AI compute is the fastest-growing line item in engineering budgets
- No visibility means no leverage: procurement can't negotiate what it can't measure
- Token spend grows with codebase context — agents paste entire repos to answer simple questions
**Footer:** Constraint: do not name specific competitors

### SLIDE 3: THE MARKET (TITLE: "Where the spend lives")
**Bullets:**
- Mid-market engineering teams (50–500 devs) spending $20K–$500K/yr on AI coding agents
- Average: 30 queries/dev/day × $0.015/input-token × expanding context = compounding waste
- Context window costs dominate: the agent sends your whole repo, not just the relevant 2%
- Existing monitoring tools measure utilization, not inference price
**Source note:** All figures in docs/BUSINESS-CASE.md as "modeled"

### SLIDE 4: THE MEASUREMENT (TITLE: "Free in 15 minutes, no credit card")
**Bullets:**
- `pip install neuralmind` → `neuralmind savings .` → per-query, per-developer, per-project token report
- CI-measured 40–70× retrieval-stage reduction, benchmarked on every commit
- MIT core does the measurement and compression; free forever before any commitment
- Reproducible on your own codebase — no synthetic benchmarks, no sales demo
**Primary CTA text:** "Verify on your own repo in ~15 minutes — no license required"

### SLIDE 5: THE SAVINGS MODEL (TITLE: "What the math shows")
**Bullets:**
- Modeled 50-dev team, 30 queries/day, Sonnet pricing: **~$310/mo back on tokens**
- Context-limit thrashing recovery (re-prompting, re-reading): **~$1,650/mo engineering-hours saved**
- Figures are MODELED with assumptions documented — link to docs/BUSINESS-CASE.md
- CI-measured retrieval reduction is Measured (Tier C); end-to-end multiplier is Derived, not directly observed
**Footer:** Constraint: every dollar figure must be labeled "Measured" or "Modeled"; never conflate the two

### SLIDE 6: THE RISK CASE (TITLE: "Why governance is the bigger purchase")
**Bullets:**
- No audit trail = no SOX / SOC 2 evidence for AI-agent decision-making (contract selection, code review)
- No seat governance = no revocation when engineers leave or rotate — orphaned team memory persists
- No self-hosted option = code egress to agent model providers, even when the index stays local
- Compliance teams need tamper-evident logs; NeuralMind's hash-chained audit provides them
**Honest framing:** MIT core covers the compression; Team tier covers the governance audit trail

### SLIDE 7: THE PAID TIER (TITLE: "$29/user/mo — What it actually buys")
**Bullets:**
- Team tier (5–50 seats, annual): admin memory governance, hash-chained audit log, seat management, self-hosted deployment
- NOT included: the 40–70× compression (already free in MIT core)
- Optional: Cheval-Volant consulting for multi-team rollout and compliance review
**Honest framing:** "If prompt caching already covers your workload, we say so" — the assessment proves fit before purchase

### SLIDE 8: THE ASK (TITLE: "Try before you buy — three paths")
**Bullets:**
- Path A: `pip install neuralmind` → run `neuralmind savings .` on your repo (15 min, no signup)
- Path B: Free 1-seat Team license auto-issues on first `neuralmind team` command — governance features free for one admin
- Path C: hello@neuralmind.uk → schedule a 30-min assessment on your metrics (productivity + compliance)
**Closing line:** No rip-and-replace. NeuralMind works with Claude Code, Cursor, Cline, and any MCP agent.
**Footer:** Constraint: no Tier D claims (no "self-improving", no "SOC 2 certified")

---

## DESIGN CONSTRAINTS

1. **No code blocks** in the deck body — code references stay in footers or appendix
2. **No internal codenames**: "CI-Gated Tuner", "E1.5", "Wave 4", "F3" → forbidden. Say "evolutionary tuner" if you must reference it; omit if not yet released
3. **Measured vs. Modeled**: use exact labels in footers. The reader must be able to distinguish CI-measured retrieval reduction from modeled end-to-end savings. Never blend them into the same statistic.
4. **No superlatives**: "revolutionary", "transformative", "AI-powered" → forbidden. CFOs dismiss these instantly. Use numbers instead.
5. **One-slide-one-claim rule**: each slide makes one point; no slide mixes savings, governance, and integrations
6. **Tone**: direct, skeptical-of-marketing, structured like an internal memo — not an external pitch
7. **Sources**: every number slides from docs/BUSINESS-CASE.md or HONEST-ASSESSMENT.md; link the doc, not a blog post

---

## CLAIM TIER ENFORCEMENT

Every claim in the deck must pass this audit before finalizing:

| Claim | Tier | Allowed? |
|-------|------|----------|
| 40–70× retrieval reduction (CI-benchmarked) | C | ✅ "measured on every commit" |
| Per-query transparency | C | ✅ "run neuralmind savings" |
| Local-first / no phone-home | A | ✅ architectural fact |
| $310/mo token savings | C | Must be labeled "Modeled" |
| $1,650/mo engineering-hours recovery | C | Must be labeled "Modeled" |
| Works with Claude Code, Cursor, Cline | C | ✅ implementable feature |
| Hash-chained audit | C | ✅ Wave 9 shipped |
| Self-improving / evolving | D | ❌ Do not include (Tier D, no evidence) |
| SOC 2 compliant | False | ❌ Architecture supports; not certified |

Do not include any Tier D claim. If a slide requires one for a narrative, delete the slide instead.

---

## DELIVERABLE FORMAT

1. Markdown document with each slide as a ## section
2. Speaker notes under each slide (≤100 words) for live presentation
3. One-page appendix listing the source URLs for every claim
4. Commit the deck to `docs/deck-cfo-neuralmind.md` in the repo
