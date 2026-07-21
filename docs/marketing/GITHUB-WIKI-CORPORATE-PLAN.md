# GitHub Pages, Wiki & Corporate Strategy — Action Plan

**Date:** 2026-07-23
**Scope:** GitHub Pages/wiki improvements, Claude Teams for corporate users, compliance certification strategy

---

## 1. GitHub Pages & Wiki — Improvement Plan

### 1.1 Current State Audit

| Surface | Quality | Gap |
|---------|---------|-----|
| README.md | Comprehensive but dense, 2079 lines | Hard to scan. No "what it's NOT for" section. Transparency hook buried. |
| Wiki Home | "What's New" is 31 versions behind | Maintenance debt. Needs batch backfill. |
| Architecture.md | References `mempalace.yaml` config file | This is a project metadata format, NOT a repo name — keep as-is |
| Community benchmarks | n=3, anonymized | Honest but small sample |
| Effectiveness page | CRM case study only | Telehealth 60× data missing |
| SECURITY.md | Excellent, updated 2026-06-30 | None |
| COMPLIANCE-SUMMARY.md | Solid one-pager | Good for procurement teams |

### 1.2 README Restructuring (Priority Order)

**A. Add "When NeuralMind is NOT for you" section (near top, after the 4-benefit table)**

Current README buries this in the FAQ at the bottom. CFOs evaluating need the honest-fit frame early.

```markdown
## When NeuralMind is **not** worth installing

- **Codebase under ~5K lines** — just paste it into context.
- **Free-tier or flat-rate LLM access** — no per-query cost to reduce.
- **Inline-completion-only workflows** — wrong layer of the stack.
- **Already running prompt caching + long context** — marginal win shrinks.
- **Polyglot with weak tree-sitter coverage** — retrieval quality drops.

If you're unsure: `bash scripts/demo.sh` takes 30 seconds. `neuralmind benchmark .` takes 5 minutes. Decide from data.
```

**B. Move transparency hook to the opening paragraph**

Current opening: "Persistent memory and context compression for AI coding agents."

Better: "Your AI agent bill is a black box. NeuralMind opens it — and cuts token costs 40-70× as a side effect."

This is the validated messaging hierarchy: transparency > compression.

**C. Add "Quick start by agent" summary table**

Already exists in current README (lines 1910-1940). Good. Keep.

**D. Trim release notes history**

Current README has 30+ version entries. Move versions older than v0.30.0 to a separate `RELEASE_HISTORY.md` or link to GitHub releases. Keep only the last 5-8 versions visible.

### 1.3 Wiki "What's New" Backfill

The wiki Home.md "What's New" feed is stuck at v0.21.0 (31 versions behind).

**Fix:** Batch-fill with one-line summaries, newest first, pointing to release notes.

Pattern:
```markdown
### v1.5.0 — Latest release
[Release notes →](RELEASE_NOTES_v1.5.0.md)

### v1.4.0 — Louvain modularity clustering
[Release notes →](RELEASE_NOTES_v1.4.0.md)

### v1.3.0 — G3+G4 shipped, dangling edge prune
...

### v1.0.0 — Team tier ships (July 2026)
...

(older versions archived → see GitHub releases)
```

Don't write prose. One headline + link per version.

### 1.4 Cross-Page Consistency Fixes

| Page | Fix |
|------|-----|
| README.md | Add "NOT for you" section, transparency lead, trim history |
| Wiki Home.md | Backfill "What's New" to v1.5.0 |
| docs/about.html | Add "What's New" for v1.5.0 above prior sections |
| site/ Hero.tsx | Update heroStats with telehealth data: `{ label: 'Token Ratio', value: '60×', highlight: true }` |
| site/ Features.tsx | Add card: "Effectiveness: 60× on telehealth (9,600 nodes)" |
| Effectiveness page | Add telehealth as second case study |

---

## 2. Claude Teams for Corporate Users

### 2.1 The Open-Core Boundary (from tier2-dual-tier-license pattern)

| MIT (Free, always) | Paid tier ($29/user/mo) |
|---|---|
| Full retrieval (L0–L3, synapses) | — |
| MCP server, all tools | — |
| Memory namespaces (personal/branch/shared) | — |
| Team memory format (file-based) | — |
| Audit trail (hash-chained) | — |
| RBAC via static config | RBAC-as-a-service (web admin UI) |
| Manual team-memory sync | Real-time cross-machine sync |
| Actor resolution from env/OS user | SSO/SAML/OIDC org IdP integration |
| Self-hosted deploy | Managed/hosted offering |
| `hello@` for support | Defined SLA with severity tiers |
| — | Quantitative audit logs for compliance attestation |

**Core principle:** Sell deployment pain, not features. The MIT core is fully useful for solo devs and teams <10. The paid tier solves org-scale governance that only appears at 10+ engineers.

### 2.2 License Distribution (Corporate Procurement)

**Level 1 (now):** PGP-signed license.json via secure channel
```bash
scripts/issue_team_license.py --pgp-sign --customer "Acme Corp" --seats 15 --expires 2027-07-19
```

**Level 2 (Month 2-3):** Per-customer portal at `license.neuralmind.uk`
- Customer enters order email → downloads signed license.json
- Portal logs download (audit trail)
- Dashboard shows expiring seats, active customers

**Level 3 (when Stripe volume > 10/mo):** Stripe webhook auto-issue
- Payment → auto-generate license → email to customer
- Idempotent, fail-closed, signature-verified

### 2.3 Corporate Procurement Checklist

Corporate buyers will ask:

| Question | Answer |
|----------|--------|
| Where do we download? | `https://license.neuralmind.uk` (Level 2) or PGP-signed file (Level 1) |
| How do we verify it's legit? | PGP signature from dfrostar (fingerprint published) |
| When does it expire? | Visible in license.json `expires_at` |
| What if we stop paying? | License expires → fallback to free tier (1 seat, no data loss) |
| Do you store our data? | No. License file stays on your machine. No phone-home. |
| Is the verification signature the same as the license key? | No. PGP = transport validation. Ed25519 = license content validation. |

---

## 3. Compliance Certification Strategy

### 3.1 What the Architecture Already Supports

From `COMPLIANCE-SUMMARY.md` and `SECURITY.md`, NeuralMind's architecture aligns with:

| Framework | Architecture Support | Current Claim | Cert Cost (Solo) |
|-----------|---------------------|---------------|------------------|
| **SOC 2 Type I** | CC6.1, CC7.1, CC7.2, A1.1, C1.2, P3.1/P4.1 | "Architecture supports" (honest) | $5K-$10K + auditor |
| **SOC 2 Type II** | Requires Type I first + 6-12 mo operational evidence | Not yet | $15K-$30K/yr |
| **GDPR** | Data residency, no external processing, right to erasure | Already compliant (architecture is the control) | Free |
| **HIPAA** | Encryption at rest (OS), access controls, audit logging | "Architecture supports" | $5K-$10K (BAA + audit) |
| **ISO 27001** | Information security management | Not yet | $15K-$25K (too heavy for solo) |
| **PCI DSS** | Not applicable (Stripe handles payment data) | Don't pursue | Free (Stripe is PCI-compliant) |
| **FedRAMP** | US federal authorization | Don't pursue | $200K+ (no federal contracts yet) |
| **NIST AI RMF** | GOVERN, MAP, MEASURE, MANAGE mapped | Full coverage documented | Free (self-attestation) |

### 3.2 Recommended Certification Path

**Phase 1 (Now — Free):**
- **NIST AI RMF** — already documented in `COMPLIANCE-SUMMARY.md`. Self-attestation is credible for technical buyers. Claim: "NIST AI RMF aligned — full coverage documented."
- **GDPR** — architecture is already compliant. Claim: "GDPR-aligned architecture — no external processing, data residency under operator control."

**Phase 2 (Month 6-12, $10K-$15K):**
- **SOC 2 Type I** — point-in-time design audit. The credibility unlock for enterprise sales. Use Vanta for auto-evidence collection.
- Prerequisite: B-Audit (actor resolution + hash-chain) — already shipped in v0.27.0.

**Phase 3 (Month 18-24, if revenue justifies):**
- **HIPAA** — healthcare is a high-value vertical (regulated = local-first resonance). Requires Business Associate Agreement (BAA) with any cloud providers. Since NeuralMind is self-hosted, this is lighter than typical.
- **SOC 2 Type II** — operational audit over 6-12 months. Only pursue if enterprise contracts > $50K/yr.

**Don't pursue (for now):**
- **ISO 27001** — too heavy for solo operations. Defer until team > 5.
- **PCI DSS** — irrelevant. Stripe handles payment processing.
- **FedRAMP** — $200K+ and only matters for US federal contracts. Not in target market yet.

### 3.3 Honest Marketing Claims (Compliance)

**Current (no cert yet):**
- ✅ "Architecture supports SOC 2 Type I evidence — see COMPLIANCE-SUMMARY.md"
- ✅ "Audit hardening in progress — control mapping public"
- ✅ "GDPR-aligned: no external processing, data residency under operator control"
- ❌ NOT "SOC 2 certified"
- ❌ NOT "SOC 2 compliant"
- ❌ NOT "GDPR compliant" (certification vs. architecture alignment are different)

**After SOC 2 Type I:**
- ✅ "SOC 2 Type I certified"
- ✅ "Type II readiness underway"
- ❌ NOT "SOC 2 Type II certified"
- ❌ NOT "SOC 2 and GDPR compliant" (they're separate)

---

## 4. Execution Priority

| Priority | Action | Impact | Effort |
|----------|--------|--------|--------|
| **P0** | README: Add "NOT for you" section, transparency lead | Conversion | Low |
| **P0** | README: Trim release history to last 5-8 versions | Readability | Low |
| **P1** | Wiki: Backfill "What's New" to v1.5.0 | Credibility | Medium |
| **P1** | Site Hero: Add telehealth 60× data | Proof | Low |
| **P1** | Site Effectiveness: Add telehealth case study | Proof | Medium |
| **P2** | NIST AI RMF self-attestation page | Free compliance signal | Low |
| **P2** | License portal (Level 2) | Corporate procurement | Medium |
| **P3** | SOC 2 Type I via Vanta | Enterprise credibility | $10K, 6 mo |
| **P3** | HIPAA alignment documentation | Healthcare vertical | Medium |

---

*Plan v1.0. Next review: after README refresh ships.*
