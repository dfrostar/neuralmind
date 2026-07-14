# Perplexity Analysis — DeepSeek Validation Brief

**Source:** Perplexity AI analysis of `dfrostar/neuralmind` vs. Cody (Sourcegraph), Cursor, Copilot, Claude Code
**Date:** 2026-07-14
**Purpose:** Validate claims before updating the NeuralMind roadmap / commercial packaging

---

## 1. What Perplexity Got Right (Accept)

| Claim | Assessment | Action |
|-------|-----------|--------|
| NeuralMind is not a standalone coding assistant — it's a memory/context layer underneath existing agents | Accurate. The ROADMAP confirms: "out of scope: inline completion, hosted SaaS, cross-repo/org-wide search." | No action needed — this is the chosen positioning. |
| Cody's core value is org-wide, cross-repo search + multi-LLM enterprise product; NeuralMind's is local/per-project semantic index | Accurate. | Use this as the competitive framing in marketing. |
| To compete with Cody feature-for-feature would require: org-wide multi-repo indexing, first-party UI, multi-LLM orchestration, real enterprise admin layer (SSO/SAML, audit dashboard, seat management), real certifications (SOC 2 Type II, ISO 27011), commercial packaging (pricing, SLAs) | Accurate gap list. | But: chasing Cody feature-for-feature is explicitly not our strategy. The question is *which* of these gaps matter for the "regulated-industry local alternative" positioning. |
| Strongest asset is 100% local processing, zero exfiltration, air-gap installable | This is the headline differentiator — but **needs validation** (see §2). |.Validate before claiming in enterprise positioning. |
| Recommends positioning as "on-prem/regulated-industry alternative to Cody's context layer" — with SOC 2/ISO + admin console, leaving chat/autocomplete to the agents NeuralMind already plugs into | Aligned with the open-core strategy already decided (OSS individual free / paid org features). | Validate; if confirmed, this becomes the GTM pivot point. |

---

## 2. Claims Requiring Validation (Send These to DeepSeek)

Perplexity flags several claims as unverified. The project makes these claims in docs but they haven't been independently tested. **Before the roadmap or commercial packaging relies on them, DeepSeek should validate:**

### 2.1 Air-Gapped Claim

**Claim:** "100% local, zero data exfiltration, air-gap installable" (README, air-gapped.md)

**Air-gapped walkthrough exists** (`docs/use-cases/air-gapped.md`) — detailed steps for:
- `pip download` wheel bundle + sneakernet transfer
- ChromaDB ONNX model pre-cache + transfer
- `turbovec` backend (ChromaDB-free, bundled ONNX model)
- Docker offline via `docker save`/`docker load`
- Verification via `ss -tnp` / `lsof -i`

**Validation needed:**
- [ ] Has this walkthrough ever been executed on a *clean, genuinely air-gapped* machine (not just a VM with network temporarily disabled)?
- [ ] Does `turbovec` backend actually produce equivalent retrieval quality to ChromaDB on the same codebase?
- [ ] Does `neuralmind build` + `neuralmind query` complete with zero outbound packets (`tcpdump -i any` on a clean box)?
- [ ] Does the ChromaDB-free path eliminate the *only* runtime network dependency, or are there others (e.g., tree-sitter grammar downloads, language-specific model lazy-loads)?
- [ ] Are there any telemetry/updater pings in the Python stdlib HTTP client or any dependency?

**If air-gap is validated:** This becomes the single strongest differentiator — literally zero enterprise competitors offer a fully air-gapped context layer. Defense/healthcare/finance is the beachhead.

**If air-gap has gaps:** The claim needs to be qualified ("air-gapped after initial install with offline bundle") or fixed before enterprise GTM.

### 2.2 Zero Exfiltration Claim

**Claim:** "Zero data exfiltration — your code never leaves your infrastructure" (SECURITY-GUIDE.md)

**Validation needed:**
- [ ] Static analysis: grep the codebase for any `requests.get/post`, `urllib`, `httpx`, `aiohttp`, `websocket` calls. Are there any outbound URLs hardcoded?
- [ ] Dependency audit: does any transitive dep (chromadb, mcp, tree-sitter, onnxruntime) phone home on import or at runtime? Check their source or SBOM.
- [ ] Runtime verification: run NeuralMind in a network-namespaced sandbox (Linux `unshare -n` or Docker `--network=none`) and confirm all functions work.
- [ ] Build verification: `neuralmind build` with `NEURALMIND_BYPASS=1` — does anything attempt network?

### 2.3 SOC 2 / GDPR "Ready Posture" Claim

**Claim:** "SOC 2 & GDPR-ready posture" (COMPLIANCE-SUMMARY.md referenced in air-gapped.md) / "NeuralMind satisfies SOC 2 Type II criteria" (SECURITY-GUIDE.md lines 424-444)

**Reality check:**
- SECURITY-GUIDE.md describes RBAC, OAuth, LDAP, audit logs, encryption at rest — but this is **documentation-aspirations and pseudo-code**, not production code.
- The actual project: single-user, local, per-project. No SSO. No admin console. No centralized audit dashboard. Local JSONL logs only.
- COMPLIANCE-SUMMARY.md is referenced but the file doesn't exist at the path.

**Validation needed:**
- [ ] Does a local-first, single-user, per-project tool *need* SOC 2 Type II to sell to regulated industries, or is SOC 2 Type I + a signed DPA + the zero-exfiltration architecture sufficient for initial contracts?
- [ ] For customers who *require* SOC 2 Type II attestation: what's the minimum viable audit scope? (Likely: the consulting/support entity, not the OSS tool itself, since the tool processes no customer data centrally.)
- [ ] Is "ready posture" a risky claim that invites auditor scrutiny, or is it standard pre-sales language?
- [ ] Can the project get a SOC 2 Type I attestation (6-9 months, ~$30-50k) vs. Type II (12+ months, ~$75-150k)? Which is the beachhead goal?

### 2.4 Commercial License Viability

**Existing terms** (LICENSE-COMMERCIAL.md already drafted):
- MIT free for individuals, non-commercial, teams <5 users
- Commercial: $15/user/month (min 25 seats) or $85,000/year site license
- Enterprise modules: SSO, RBAC, compliance-export, air-gap binaries, audit-log rotation

**Validation needed:**
- [ ] Is $15/user/month competitive with Cody ($18/user/month) and Copilot ($20-39/user/month)? Or is it too cheap — does it signal "not enterprise"?
- [ ] Site license at $85k/year — does that align with enterprise procurement expectations for a context-layer tool?
- [ ] Are the "enterprise modules" (SSO, RBAC, compliance-export, audit-log rotation) things that *must* be in a private/commercial repo, or can some be MIT-licensed community features? (Open-core decision)
- [ ] Is the "tamper-evident audit log" provision (Section 3) enforceable for a local-first tool? What's the technical mechanism?
- [ ] Does the "NeuralMind, Inc." licensor entity exist? If not, what's the path (Delaware LLC already exists: Cheval-Volant)?

### 2.5 "Air-gap binaries" as Commercial Feature

The commercial license lists "air-gap binaries" as an enterprise feature. But the OSS repo already includes `docs/use-cases/air-gapped.md` with full steps for air-gapped OSS install.

**Decision needed:** Is the air-gap *documentation* MIT (and that's fine), while the air-gap *packaging* (pre-built offline bundle, signed, checksummed, with support SLA) is commercial? Or should air-gap步行through be moved behind the paywall?

---

## 3. What DeepSeek Should Deliver

Per DeepSeek's structured analysis capability, ask it to produce:

1. **Air-gap technical validation report** — confirm or refute the walkthrough steps, identify hidden network deps
2. **Zero-exfiltration evidence** — static analysis + runtime sandbox report
3. **SOC 2 path analysis** — Type I vs Type II scope, cost, timeline, vendor (Vanta, Drata, etc.), whether the OSS tool itself needs to be in scope
4. **Competitive pricing analysis** — Cody ($18/mo), Copilot ($20-39/mo), Cline (free OSS + Pro plan), Continue (free OSS). Where should NeuralMind commercial pricing land?
5. **Open-core module classification** — which features stay MIT, which go commercial. Reference: GitLab's EE/CE split, Sentry's BSL→MIT, Render's pricing page.
6. **Delaware LLC → licensor entity structure** — Cheval-Volant LLC + "NeuralMind" DBA vs. new "NeuralMind, Inc." C-corp. What's the cleanest path for commercial licensing?

---

## 4. The Deeper Strategic Question

Perplexity's "more interesting alternative" is right *in principle* — but the road to it runs through a minefield:

- The SOC 2 claim is currently *documentation theater* — pseudo-code RBAC and OAuth integration that doesn't exist. An auditor would dismiss it.
- The air-gap claim *looks* solid on paper (the walkthrough is genuinely detailed) but may have hidden network dependencies in transitives.
- The "zero exfiltration" claim is *probably true* for the core Python code, but "probably" isn't "verified" and enterprise buyers need verified.
- The commercial license structure exists as a draft but the licensor entity may not be set up, and the "enterprise modules" in the license (SSO, RBAC, admin console, compliance-export) don't exist as shipped code.

**The actual play** isn't "chase Cody" — it's honestly narrower:

> "If you're a defense contractor, healthcare system, or financial firm with an air-gap mandate, NeuralMind is the only context layer that installs and runs with zero network, zero exfiltration, and zero vendor cloud dependency. Everything else sends your code to someone else's index."

That play only works if air-gap is *proven*, not just documented.

---

## 5. Immediate Action Items

| # | Item | Owner | Depends on |
|---|------|-------|-----------|
| 1 | Send §2 validation questions to DeepSeek profile | DTFrost | This brief |
| 2 | Decide open-core split (MIT vs commercial modules) | DTFrost + legal | DeepSeek pricing + open-core analysis (§3.4, §3.5) |
| 3 | Validate air-gap on genuinely air-gapped hardware (or at minimum, `unshare -n` sandbox + tcpdump) | Dev + DeepSeek §3.1 | DeepGap §3.1 |
| 4 | Static analysis for outbound network calls | Dev | DeepGap §3.2 |
| 5 | Update ROADMAP.md with: open-core plan, commercial module list, SOC 2 audit path, air-gap validation status | Dev | Items 1-4 |
| 6 | Update/rename COMPLIANCE-SUMMARY.md to distinguish "self-assessment / readiness" from "audited attestation" | Dev | DeepSeek §3.3 |
| 7 | Fix broken roadmap links (HONEST-ASSESSMENT.md, ENTERPRISE.md, COMPLIANCE-SUMMARY.md missing) | Dev | — |
| 8 | Licensor entity setup (Cheval-Volant LLC DBA "NeuralMind" vs new corp) | DTFrost + legal | DeepSeek §3.6 |
