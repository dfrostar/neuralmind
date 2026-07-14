# NeuralMind — Competitive Pricing & Licensing Analysis

**Source:** Deep-competitive research (GitHub Copilot, Cody, Cursor, Tabnine, Augment, Cline, Continue, CodeRabbit)
**Date:** 2026-07-14
**Status:** Final — sent to DeepSeek profile for validation

---

## 1. AI Coding Assistant Pricing — Full Market Map (Q2 2026)

### 1.1 Per-Seat Pricing (Annual, per user/month)

| Tool | Free | Pro/Individual | Team | Enterprise | Air-Gap |
|------|------|---------------|------|------------|---------|
| **GitHub Copilot** | ✅ Free | $10/mo (Pro), $39/mo (Pro+), $100/mo (Max) | $19/mo (Business) | $39/mo (Enterprise) | ❌ |
| **Sourcegraph Cody** | ❌ (killed Jul 2025) | — | — | $59/mo | ❌ |
| **Cursor** | ✅ Free | $20/mo (Pro) | $20/mo | — | ❌ |
| **Cline** | ✅ Apache-2.0 BYOK | — | $0→$20/mo (post-Q1 2026) | $20/mo | ❌ |
| **Continue.dev** | ✅ MIT, free | — | — | — | ❌ |
| **Tabnine** | ❌ (killed 2025) | $39/mo (Code Asst) | — | Custom | ✅ (Enterprise) |
| **Augment Code** | — | $20-50/mo | $60-200/mo (≤20 users) | Custom | ❌ |
| **Amazon Q Developer** | ✅ Free | $19/mo | — | — | ❌ |
| **Supermaven** | ✅ Free | $10/mo | — | — | ❌ |
| **CodeRabbit** | ✅ (public repos) | $24-30/mo | $24-30/mo | — | ❌ |
| **Claude Code** | — | $20/mo (Pro) | API pay-per-token | — | ❌ |

### 1.2 Billing Model Trends

- **Usage-based is winning:** Copilot → AI Credits (Jun 2026), Cursor → credits, CodeRabbit → per-agent-minute
- **Flat-rate is retreating:** Tabnine and Cody still charge flat per-seat, but even Tabnine is moving toward credits
- **Free + BYOK is the OSS default:** Cline, Continue → $0 platform fee, pay only for API tokens
- **Air-gapped is premium:** Tabnine charges custom Enterprise pricing for air-gapped deployment — no competitor offers it as standard

### 1.3 The "Context Layer" Sub-Market

NeuralMind competes in a narrower category: **AI agent context/memory**, not the full IDE/assistant.

| Competitor | Model | Notes |
|------------|-------|-------|
| **Aider** (repo记忆) | Free OSS | Rudimentary, no persistent graph |
| **Continue.dev** (codebase index) | Free OSS | Indexes your code but no persistent memory/synapses |
| **Cline** (OpenCtx / Memory) | Free OSS | Memory is limited, not persistent across agents |
| **Cursor Rules** | $20/mo included | Lightweight "rules" — not a learning graph |
| **Claude Code Memory** | $20/mo included | Memory files in Claude Memory tool — no graph, no synapses |
| **Sourcegraph Cody** | $59/mo | Full org-wide index — NeuralMind's closest *enterprise* competitor |

**No competitor offers:**
- Hebbian synapse learning from edit patterns
- Air-gapped deployment with zero exfiltration
- Per-project local semantic index + directional recall
- Multi-agent portable memory (Claude Code ↔ Cursor ↔ Cline)

→ NeuralMind's niche is **unique**: persistent, learning, air-gapped, cross-agent memory.

---

## 2. Pricing Diagnosis — Current NeuralMind Pricing vs. Market

### 2.1 Current Pricing (LICENSE-COMMERCIAL.md)

| Tier | Price | Minimum | Annual Equivalent |
|------|-------|---------|-------------------|
| MIT Free | $0 | — | $0 |
| Per-Seat | $15/user/month | 25 seats | $180/user/year, $4,500 min |
| Site License | $85,000/year | — | $85,000 flat |
| Assessment | $35,000 one-time | — | — |
| Pilot | $55,000 one-time | — | — |

### 2.2 Problems with Current Pricing

| Problem | Evidence |
|---------|----------|
| **$15/mo is below credible pricing** | Tabnine charges $39/mo (no air-gap), Copilot Business is $19/mo, Cody is $59/mo. $15/mo signals "not enterprise-grade." |
| **Minimum 25 seats = $375/mo = $4,500/year minimum** | This is actually reasonable for team pricing, but the per-seat rate is too low to scale revenue. |
| **$85k site license is reasonable** | For 100 users: $850/user/year. Cody would be $708/user/year. Tabnine air-gapped likely $960-1,200/user/year. So site license is **competitive** — actually slightly premium to Cody. BUT for 500 users: $170/user/year — this is too cheap, undercuts per-seat revenue. |
| **Gap between 25 seats and site license** | A team of 30 pays $5,400/year at $15/seat. A team of 100 pays $18,000/year at $15/seat. But a team of 100 needs SSO/admin — which should be enterprise-priced. The current $85k site license jumps from $18k (at $15/seat × 100) to $85k — a 4.7x jump that will stall sales. |
| **Assessment too cheap** | $35K for a codebase audit + TCO comparison is below market. Comparable assessments (consulting firms) run $50-100K. Given the air-gapped/zero-exfiltration angle, pricing can support a premium. |

### 2.3 Market-Aligned Pricing Recommendations

| Tier | Old Price | New Price | Rationale |
|------|-----------|-----------|-----------|
| **Community (MIT)** | $0 | $0 | Unchanged — free forever for individuals, OSS, <5 users |
| **Pro** (individual) | — | $25/mo (or $250/yr) | No min seats. Competes with Cursor Pro ($20/mo), Copilot Pro+ ($39/mo). Individual professionals who want personal memory layer. |
| **Team** | $15/mo (25+ min) | $35/user/mo (10+ min) | 10-seat minimum = $350/mo = $4,200/yr minimum. Still below Tabnine ($39/mo) and Cody ($59/mo). Positioned as "budget enterprise-grade." |
| **Enterprise** | $85k/yr site license | $75/user/mo (or $150k/yr site license for 200+) | Per-seat for teams 50-200. Site license for 200+. Aligns with Cody ($59/mo), Tabnine air-gapped ($80-100/mo). |
| **Assessment** | $35K one-time | $45K one-time | Below big-consulting ($100K+) but credible for a solo practice. |
| **Pilot** | $55K one-time | $75K one-time | Deployment + SSO + benchmark + executive readout. |
| **Air-Gap Packaging** | Bundled in Enterprise | $15K/yr add-on (Enterprise only) | Tabnine charges custom (est. $20-50K) for air-gapped. This is a pure differentiator upsell. |

**Effective pricing after change:**

| User Count | Old Annual Cost | New Annual Cost | Delta |
|------------|-----------------|-----------------|-------|
| 1 (individual) | $0 (MIT) | $0 (MIT) or $250 (Pro) | +$250 if Pro |
| 10 (team) | N/A (min 25) | $4,200 ($35/mo × 10) | New tier |
| 25 (team) | $4,500 | $10,500 ($35/mo × 25) | +$6,000 (133%) |
| 50 (team) | $9,000 | $45,000 ($75/mo × 50) | +$40,000 (444%) |
| 100 (ent) | $18,000 | $90,000 ($75/mo × 100) | +$72,000 (400%) |
| 200 (ent) | $36,000 | $150,000 (site license) | +$114,000 (317%) |
| 500 (ent) | $85,000 (site) | $150,000 (site) | +$65,000 (76%) |

The new pricing:
- **More competitive for small teams** — opens the 10-25 seat range that was previously blocked
- **Revenue-neutral to slightly up at 25 seats** ($4.5K → $10.5K / year) but justified by market alignment
- **Revenue-positive at 50-200 seats** — this is where SSO/admin features are needed
- **Maintains site-license option for 200+** — at $150k for 500 users = $300/user/year (still below Cody at $708/user/year and Tabnine air-gapped)

### 2.4 Usage-Based Billing Option

Market trend is toward usage-based. Consider offering **both**:

- **Flat-rate (default):** Predictable, easy procurement
- **Usage-based (optional):** $0.02/query after included quota, or $0.10/1K context tokens
  - This matches Copilot's credit model and CodeRabbit's per-agent-minute
  - Appeals to teams with variable usage patterns
  - Can be the "Pro" tier model — $25/mo includes 1,000 queries, then $0.02/query

**Hybrid model recommendation:**
- **Pro:** $25/mo flat — individual, unlimited
- **Team:** $35/user/mo flat — 10+ seats, unlimited
- **Enterprise:** Choose flat ($75/user/mo) OR usage-based ($50/user/mo base + $0.01/query over 5K queries/month)
  - Gives enterprise customers flexibility
  - Usage-based option captures value from heavy users

---

## 3. Licensing Structure

### 3.1 Dual-License Model (Recommended)

```
MIT License (free)
├── Individuals
├── Non-commercial use
├── Teams <5 users
└── Full OSS core included:
    ├── Semantic index + synapse layer
    ├── All 10 languages
    ├── MCP server
    ├── Team memory (git-committed)
    ├── Air-gapped walkthrough
    └── Graph view

Commercial License (paid)
├── Organizations >5 users
├── Enterprise features (private repo):
│   ├── SSO/SAML/OAuth
│   ├── Admin Console
│   ├── Compliance Export (SOC 2 / ISO / GDPR)
│   ├── Air-Gap Packaging (signed bundles)
│   ├── Audit-Log Shipping (centralized)
│   └── Priority Support SLA
└── Gated via license key
```

**Why not BSL?**
- BSL (Business Source License) converts to OSS after a change date — protects from AWS but delays OSS conversion
- NeuralMind doesn't have an AWSCompeting risk (it's local-first, no hosted service)
- BSL creates legal friction for OSS contributors — not needed here
- Dual-license is simpler, cleaner, and the MIT free tier is genuinely useful on its own

**Why not pure open-core?**
- The "commercial modules" need to live in a **private repo** (dfrostar/neuralmind-enterprise), not just be MIT-with-feature-flags
- Enterprise modules (SSO, admin, compliance) require ongoing maintenance, security patches, and support — they can't be community-maintained
- Protects the investment: if someone forks and builds a competing SSO module, the MIT core is fine, but the premium support/deployment packaging is the moat

### 3.2 Private Repository Structure

```
dfrostar/neuralmind (PUBLIC — MIT)
├── All core OSS features
├── docs/
├── tests/
└── pyproject.toml (core only)

dfrostar/neuralmind-enterprise (PRIVATE — Commercial License)
├── enterprise/
│   ├── sso/ (Okta, Azure AD, JumpCloud adapters)
│   ├── admin/ (dashboards, seat management, audit viewer)
│   ├── compliance/ (SOC 2 report gen, DPA templates)
│   ├── airgap/ (signed bundle builder, checksum verification)
│   └── audit_shipping/ (centralized log aggregator)
├── LICENSE-COMMERCIAL.md
└── pyproject.toml (neuralmind[commercial] extra)
```

**Build/install path:**
```bash
# OSS (free)
pip install neuralmind

# Commercial (requires license key file at ~/.neuralmind/license.key)
pip install "neuralmind[commercial]"
neuralmind license activate <key>
# Verifies license locally, unlocks enterprise features
# No phoning home — offline verification via signed JWT
```

### 3.3 License Key Delivery (Manual-First)

For the first 10-50 customers, no license server needed:

1. Customer signs Commercial License / Consulting Agreement
2. Invoice issued (50% upfront, 50% on completion)
3. Payment clears
4. License key delivered (signed JWT in PDF + `~/.neuralmind/license.key`)
5. Customer runs: `neuralmind license activate <key>`
6. Key verifies locally (signed with NeuralMind private key, expires annually)
7. No network call required — air-gap compatible

At 100+ customers, add:
- License server for automatic renewal (optional — manual still works)
- Usage reporting for usage-based tiers (opt-in, documented)
- Key revocation capability (rarely needed)

---

## 4. Cost Competitiveness Analysis

### 4.1 Comparison: NeuralMind vs. Closest Competitors (Annual, per user)

| Tool | Base Price | SSO/Admin | Air-Gapped | Annual/User | NeuralMind Advantage |
|------|-----------|-----------|------------|-------------|---------------------|
| **GitHub Copilot Enterprise** | $39/mo | ✅ (GitHub-native) | ❌ | $468 | Air-gap, no Microsoft dependency |
| **Sourcegraph Cody** | $59/mo | ✅ (full IdP) | ❌ | $708 | Air-gap, per-project privacy |
| **Tabnine Enterprise** | Custom (~$80-100/mo est.) | ✅ | ✅ (custom) | $960-1,200 | Price, per-project vs. org-wide |
| **Augment Code** | $60/mo (Standard) | ✅ | ❌ | $720 | Air-gap, price |
| **NeuralMind (new)** | $75/mo (Enterprise) | ✅ | ✅ (standard) | $900 | Competitive |

**NeuralMind's competitive position:**
- Priced between Tabnine Enterprise and Augment Code — credible
- Only tool with **air-gap as standard** in enterprise tier (not custom add-on)
- Only tool with **zero exfiltration** as architecture (Tabnine has zero-retention policy but still SaaS-hosted)
- Lower total cost than full IDE replacement (Cody, Copilot) for orgs that already use Claude Code/Cursor/Cline

### 4.2 Cost Savings Pitch (for CFO/CTO buyers)

> "Your engineers ask AI agents ~20 questions/day. Each question reads 10-50 files it doesn't need. At current API rates, that's $800-1,200/engineer/month in wasted context tokens. NeuralMind cuts that 40-70x — to $12-30/month for the memory layer itself."

**At 100 engineers:**
- Current waste: $800,000-1,200,000/year
- NeuralMind cost: $90,000/year (Enterprise at $75/mo)
- **Net savings: $710,000-1,110,000/year (89-93% reduction)**

This is the CFO pitch — and at $75/mo, the tool pays for itself 11x over.

---

## 5. Path to Making Modules Private

### 5.1 What Goes Private

Move these from `dfrostar/neuralmind` (public) to `dfrostar/neuralmind-enterprise` (private):

| Module | Reason for privatization |
|--------|--------------------------|
| SSO/SAML/OAuth adapters | Enterprise-only, requires ongoing security patches, customer-specific configs |
| Admin Console | UI for seat management — competitive moat |
| Compliance Export | Report templates — customers expect polished, non-OSS deliverables |
| Air-Gap Packaging Builder | The *process* can be MIT (air-gapped.md already is), but the signed bundle, checksum verification tooling, and support SLA are commercial |
| Audit-Log Shipping | Enterprise-only, requires log destination configs (Splunk, Datadog, Elastic) |

**What stays PUBLIC (MIT):**
- Everything already shipped in the OSS repo
- The air-gapped walkthrough (documentation)
- The team memory format spec (interoperability)
- All retrieval/synapse/core code (trust through transparency)

### 5.2 Privatization Execution

1. **Create `dfrostar/neuralmind-enterprise` repo** (private, GitHub free for private repos)
2. **Extract enterprise modules** — nothing to extract yet (they don't exist), so this is greenfield
3. **`pyproject.toml` split:**
   - Public: `pip install neuralmind` — core only
   - Commercial: `pip install "neuralmind[commercial]"` — requires `neuralmind-enterprise` repo access + license key
4. **License key verification:**
   - Public repo contains a `LicenseVerifier` class (MIT)
   - Commercial repo provides signed keys (encrypted with NeuralMind private key)
   - No network call — all verification is local
5. **Continuous integration:**
   - Public CI: standard GitHub Actions
   - Private CI: access public repo via `workflow_dispatch`, build against license check
6. **Community contributions:**
   - Core improvements → MIT, public
   - Enterprise features → Commercial, with contributor agreement if needed

### 5.3 License Key Format (Technical)

```json
{
  "iss": "neuralmind",
  "sub": "customer-name",
  "tier": "enterprise",
  "seats": 100,
  "features": ["sso", "admin", "compliance", "airgap", "audit_shipping"],
  "exp": 1784073600,
  "airgap_compatible": true,
  "sig": "RS256-signature"
}
```

- Signed with NeuralMind RSA private key
- Public key embedded in OSS code (`neuralmind/license.py`)
- Verification: `neuralmind license verify <key>` — fully offline
- Rotation: annual re-license upon renewal
- Revocation: append-only revocation list (distributed annually, or on-support-contact)

---

## 6. DeepSeek Validation Questions

Send these to the DeepSeek profile:

### 6.1 Pricing Validation

1. Is $75/user/month enterprise pricing credible vs. Cody ($59/mo) and Tabnine air-gapped (est. $80-100/mo)?
2. Should the Team tier be $35/mo or $45/mo? (lower = more adoption, higher = better revenue per seat)
3. Is the $150k site license at 200+ users sustainable, or should it be $200k?
4. Does usage-based billing make sense for the Enterprise tier, or does it create procurement friction?
5. Is the Assessment ($45K) / Pilot ($75K) split right, or should Assessment be folded into Pilot?

### 6.2 Licensing Validation

1. Is dual-license (MIT + Commercial) preferable to BSL for a local-first tool?
2. Does a private repo for enterprise modules create contributor friction?
3. Is a manual license-key system (for first 50 customers) viable without a license server?
4. Is air-gap-compatible license verification (signed JWT, local verification) legally defensible?
5. Can the OSS repo include the commercial modules as "dummy" packages that check for a license key, or does that create a "policy-less open-core" problem?

### 6.3 Market Validation

1. Given that Tabnine charges ~$39/mo for its baseline (non-air-gapped) offering, is NeuralMind's "air-gap at enterprise tier" actually a $20-30/mo premium, or is it table stakes for defense/healthcare buyers?
2. For the 50-200 person enterprise segment, does $75/user/mo with air-gap feel competitive against "you can get Copilot Enterprise for $39/mo but no air-gap"?
3. Is the "40-70x token reduction" claim strong enough to justify $75/mo when Copilot/Cursor are $20-39/mo and already provide context? (Value prop question — can only be answered with实测 data)

---

## 7. Immediate Actions

| # | Action | Owner | Deadline |
|---|--------|-------|----------|
| 1 | Send §6 questions to DeepSeek profile | DTFrost | This week |
| 2 | Update LICENSE-COMMERCIAL.md with new pricing tiers | DTFrost | After DeepSeek validation |
| 3 | Create `dfrostar/neuralmind-enterprise` repo (private) | DTFrost | After pricing locked |
| 4 | Splash `pyproject.toml` for `[commercial]` extra | Dev | With first enterprise feature |
| 5 | Build `LicenseVerifier` class (offline JWT verification) | Dev | Before first commercial sale |
| 6 | Build air-gap signed bundle builder | Dev | Before first enterprise sale |
| 7 | Update ROADMAP.md with final pricing + licensing plan | Dev | After DeepSeek + pricing locked |
| 8 | LinkedIn content rollout for new pricing | DTFrost | After public launch |

---

## Appendix: Source URLs

- https://github.com/features/copilot/plans — GitHub Copilot pricing
- https://weavai.app/blog/en/2026/04/30/sourcegraph-cody-review-2026-enterprise-ai-at-59-mo — Cody at $59/mo
- https://checkthat.ai/brands/tabnine/pricing — Tabnine pricing
- https://checkthat.ai/brands/augment-code/pricing — Augment Code pricing
- https://www.usagepricing.com/blueprint/augment-code — Augment with credits
- https://www.coderabbit.ai/pricing — CodeRabbit usage-based
- https://getdx.com/blog/ai-coding-assistant-pricing — DX pricing guide
- https://pricepertoken.com/coding-assistants — 17 tool comparison
- https://www.augmentcode.com/pricing — Augment's official pricing
