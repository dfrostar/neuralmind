# Enterprise Competition & Monetization Plan

**Status:** Proposed · **Date:** 2026-07-15 · **Owner:** maintainer
**Reads alongside:** `docs/market-research/` (competitor deep-dive §9 is the
strategy source), `docs/NEXT-RELEASE-PLAN.md` §5 (enterprise lane — this doc
supersedes it now that team memory has shipped), `docs/BUSINESS-CASE.md`,
`docs/ENTERPRISE.md`, `docs/PILOT-BRD.md`, `LICENSE-COMMERCIAL.md`.

> **Public-repo note:** this repo is public, so this plan is written at the
> same altitude as material already published here (the comparison pages,
> the business case, the market-research pack). Anything more sensitive than
> what those already expose — negotiated pricing, named prospects, deal
> terms — belongs in the private business repo, not here.

---

## 0. Where we stand (v0.43)

The enterprise lane in `NEXT-RELEASE-PLAN.md` §5 was gated on a multi-user
surface existing. That gate has cleared — the assets below are shipped:

| Asset | Shipped | Strategic role |
|---|---|---|
| Team memory (committed synapse baseline) | v0.30/v0.31 | The multi-user surface; onboarding-lift wedge |
| Audit log: per-user actor, tamper-evident hash chain, search, verify | #336 | Governance story for regulated buyers |
| Vulnerability disclosure SLA + support commitment | #334 | Sellable assurance (see §2) |
| SBOM (CycloneDX) on every release, GHCR multi-arch images | v0.9 | Supply-chain assurance |
| Air-gapped install walkthrough | v0.9 | AirgapAI/Tabnine competitive alternative |
| Absolute-privacy-claims CI guard | #333 | Protects the honesty asset |
| Public reproducible benchmark + live competitor head-to-head | v0.31–v0.34 | Pressure on unsubstantiated competitor claims |
| Ten languages behind the tree-sitter seam | v0.27–v0.37 | Polyglot-monorepo credibility |
| Comparison pages (14) + honest assessment | ongoing | GTM top-of-funnel |

What does **not** exist yet: anything a customer can actually *pay for*.
That is the gap this plan closes.

---

## 1. The four strategic thrusts (from the competitor deep-dive §9)

### W1 — Defend the moat: zero-code-egress, made provable and productized

- **Keep the guarantee testable.** The privacy-claims CI guard (#333) protects
  the words; add a network-isolation CI job (`unshare -n` over the demo +
  benchmark) so the *behavior* is regression-tested, not just the copy.
- **Productize the air-gap bundle.** Today it's a walkthrough; make it an
  artifact: a signed, versioned offline bundle (wheels + ONNX model + docs)
  attached to releases. This is the Tabnine/AirgapAI counter-offer and the
  first thing worth charging for (§2).
- **Any license mechanism must be offline.** See §3 — a phone-home license
  check would refute the moat in one line of code.

### W2 — Exploit the white space: the 10–200 engineer segment

- **Positioning:** "multi-repo intelligence without the enterprise tax" —
  above Copilot's context ceiling, below Cody's ~$75K enterprise floor.
- **The wedge is team memory + onboarding lift.** "A new hire's agent boots
  with the team's accumulated map" is the story no per-user native memory
  (Claude's, Cursor's) will tell. The onboarding-lift eval (E1.5) is the
  proof; keep it in every pitch.
- **Pilot motion:** `docs/PILOT-BRD.md` acceptance criteria + the consulting
  agreement template are the machinery. Two-week paid pilots, priced low
  enough to be a credit-card decision (see §4).

### W3 — Counter the threats

- **Augment Code** (best-funded architectural neighbor): stay ahead on the
  part they can't do — local-first + the synapse learning layer. Per
  `NEXT-RELEASE-PLAN.md` §7: *the synapse layer is the product; the
  vector-RAG half is commodity.*
- **GitHub Copilot** network effects: never chase feature parity. Headline
  axes are privacy, intelligence depth, no lock-in — already the comparison
  pages' framing; keep it that way.
- **AirgapAI's "78×" claim:** the public benchmark harness
  (`evals/public/`, fairness contract in `COMPETITORS.md`) is the honest
  pressure instrument. If an adapter is tractable, score it; if not, publish
  why the claim isn't reproducible.

### W4 — Go-to-market

- Lead with the Cody gap in outreach copy (`docs/launch/` kit; standing rule:
  disclosed-maker only).
- Comparison pages are the SEO surface for this — they exist; keep them
  honest and current per the CLAUDE.md docs checklist.
- Integrate with Continue.dev / CodeGraph-compatible formats as complements,
  not competitors (broader `install-mcp` targets already on ROADMAP "Next").

---

## 2. Monetization: what people actually pay for, in order of effort

The revenue ladder, cheapest-to-build first. Rungs 1–2 need **zero new
product code** and can start immediately; rung 3 is where the commercial
license becomes real.

### Rung 1 — Assurance & support (now)

Regulated 10–200-eng teams pay for *accountability*, not features:

- **Priority support contract** backed by the published vuln SLA (#334) and
  a response-time commitment. Annual, flat-rate.
- **Paid pilots** using `PILOT-BRD.md` + the consulting agreement template:
  fixed-fee, two weeks, ends with the customer's own benchmark numbers.
- **Compliance documentation pack**: COMPLIANCE-SUMMARY, SECURITY-GUIDE,
  SBOM/provenance walkthrough, assembled per-customer with their deployment
  pattern. Sold with the support contract.

### Rung 2 — Signed artifacts (near-term, CI work only)

- **Signed offline air-gap bundle** per release (W1). Free tier gets the
  walkthrough and builds their own; paid tier gets the signed, tested,
  versioned artifact + upgrade support.
- Cosign image signing on GHCR (already a ROADMAP candidate) folds in here.

### Rung 3 — `neuralmind-enterprise` add-on package (when demand proves it)

A **separate, private, commercially-licensed** package distributed from a
private index — *not* a relicense of this repo. The dividing line:

> **Individual-developer value stays MIT. Multi-user organizational
> control is paid.**

Candidate contents (build in demand order, not speculatively):
- SSO / RBAC around the team-memory write path and `serve`
- Audit retention/rotation policies + compliance-export module
- Centralized policy config for multi-team deployments
- Offline license-file validation (signed file, zero network — §3)

This is what `LICENSE-COMMERCIAL.md` should attach to. Today it attaches to
nothing (§3).

### Rung 4 — Name & IP protection (parallel, ~£220 total, durable)

MIT gives away the code; it does not give away the name. The UK-costed
DIY path (no lawyers):

- **Copyright: already owned, £0.** Copyright is automatic under the Berne
  Convention — the public GitHub history (timestamped, hash-chained commits
  since 2024) plus PyPI release dates is strong authorship evidence. Fix the
  `LICENSE` notice to name the actual author instead of "NeuralMind
  Contributors", and sign commits/tags going forward. Defer US Copyright
  Office registration ($65) until there's an actual US infringement to act
  on — it can be filed then.
- **Trademark: UK IPO filing, £170** for one class, DIY online. **Run a
  free clearance search first** (IPO + EUIPO + USPTO databases) — at least
  one adjacent company uses a confusingly similar name (neuralmind.ai,
  Brazilian AI firm), and a contested software class is better discovered
  for £0 than after brand investment. Use ™ (no registration needed) until
  the mark grants; unregistered "passing off" protection accrues from
  trading use meanwhile. Defer US ($350/class) and EU (€850) filings until
  revenue in those markets justifies them.
- A fork can't ship as "NeuralMind" — the one IP lever that survives a
  permissive core, and the cheapest item in this plan.

---

## 3. Licensing decision brief

### Current state is incoherent — four defects

1. **The commercial gate is void.** `LICENSE-COMMERCIAL.md` claims enterprise
   features (SSO, RBAC, audit rotation, air-gap binaries) require payment
   above 5 users — but the audit module, team memory, and air-gap docs are in
   this MIT repo. MIT §1 grants unconditional rights to use, modify, and
   sell. The >5-user restriction restricts nothing.
2. **License telemetry contradicts the moat.** §3 of the commercial license
   references "authentication/telemetry that verifies license validity."
   Zero-code-egress is the deepest moat (deep-dive §9.1) and #333 just added
   a CI guard for privacy claims. Any license check must be an **offline
   signed license file** (e.g. ed25519-signed, verified locally).
3. **Entity/contact drift.** The doc names "NeuralMind, Inc." (Delaware) and
   `contact@neuralmind.io`; the operated domain is `neuralmind.uk`. Align
   with the real legal entity and contact before anything is signed.
4. **Pricing contradicts the GTM.** The $85K/yr site license sits *above*
   the ~$75K Cody floor the whole strategy attacks. And at $15/seat × 50
   devs = $750/mo against BUSINESS-CASE's measured ~$310/mo token savings,
   a pitch led by token savings fails its own math — the value case must
   lead with productivity recovery + compliance enablement
   (BUSINESS-CASE Scenarios A and C), with token savings as the bonus line.

### Options considered

| Option | Verdict | Why |
|---|---|---|
| **Open-core: MIT core + private commercial add-on + paid assurance** | ✅ **Recommended** | Keeps the trust asset and the adoption funnel; enterprise legal clears MIT instantly (matters for the exact regulated segment we target); commercial license finally attaches to something real. |
| Relicense future versions to BSL / FSL | ✗ | Protects against SaaS strip-mining — a threat that barely applies to a local-first dev tool. Costs community trust and contradicts "no lock-in" headline for protection we don't need. |
| AGPL + commercial dual-license | ✗ | AGPL is blanket-banned by most finance/healthcare legal departments — it would get the free tier banned by the buyers we're courting. Network-copyleft trigger rarely fires for a local tool anyway, so the leverage is weak. |
| Support/services only, no product tier | ◐ partial | It's rung 1 and starts now, but it scales with hours, not seats. Keep it as the bridge, not the destination. |

Single-author copyright (both commit identities are the maintainer, no
external code contributors of substance) means any of these was *feasible* —
the recommendation is open-core on the merits, not on constraint.

### Decision gate (maintainer)

- [ ] Confirm open-core direction (§2 rungs 1–3) — yes/no/shape
- [ ] Confirm MIT core is permanent (worth stating publicly once decided —
      it's a selling point against BSL-rug-pull anxiety)
- [ ] Legal entity: **recommended path is a UK private limited company**
      (Companies House online, £50, ~24h; ~£34/yr thereafter) — not the
      "NeuralMind, Inc." Delaware placeholder, which would add a registered
      agent, franchise tax, and US filings for no benefit absent US VC
      plans. Governing law for the commercial paper becomes England &
      Wales; the Delaware/AAA arbitration clauses go. A company (vs. sole
      trader) matters because the commercial license carries indemnity and
      liability clauses that should sit on an entity, not a person.
- [ ] Name clearance search (£0, DIY) → then UK trademark filing (£170) —
      see §2 rung 4
- [ ] Pricing recalibration (§4)

---

## 4. Pricing recalibration (proposal, needs maintainer sign-off)

Aligned to the white-space strategy — every number deliberately under the
incumbent it's positioned against:

| Tier | Proposal | Positioned against |
|---|---|---|
| Free (MIT) | Unlimited, forever, all core features | The funnel; Copilot's context ceiling |
| Support & assurance | ~$3–6K/yr flat | "Someone accountable to call" — no incumbent sells this standalone |
| Paid pilot | ~$2–5K fixed-fee, two weeks | Cody's high-touch sales motion |
| Enterprise per-seat | $15/user/mo (25-seat min — unchanged) | Copilot Business $19 |
| Site license | **$25–40K/yr** (down from $85K) | Cody's ~$75K floor — makes "without the enterprise tax" arithmetically true |

Keep BUSINESS-CASE.md's honesty rule: the ROI table a prospect sees leads
with Scenario A (productivity: ~$1,650/mo recovered per 15 devs) and
Scenario C (enablement where AI tooling was banned), with token savings as
the third line, not the headline.

---

## 5. Sequenced actions

### Now (no product code)
1. Maintainer runs the §3 decision gate.
2. Company formation (£50, Companies House) + name clearance search (£0)
   + UK trademark filing (£170) — the whole legal substrate is ~£220.
3. Rewrite `LICENSE-COMMERCIAL.md` to match the decision: real entity,
   England & Wales law, offline license validation, repriced tiers, scope =
   the private enterprise package + assurance services (not features this
   repo ships).
4. Publish the offerings page (`docs/OFFERINGS.md`) built from the existing
   SLA + SBOM + compliance docs, linked from the free-assessment funnel.
   First sellable SKUs.
5. Fix the `LICENSE` copyright notice (automatic copyright attaches to the
   author, not a fictional contributor collective) and enable signed
   commits/tags.

### Next (CI/docs work)
5. Network-isolation CI job proving zero-egress behaviorally (W1).
6. Signed air-gap bundle artifact on releases (rung 2).
7. Refresh `docs/ENTERPRISE.md` + comparison pages with the Cody-gap
   positioning and the assurance offering.

### Later (gated on a real prospect, not speculation)
8. Scaffold the private `neuralmind-enterprise` package with the offline
   license-file check as its first feature.
9. Build RBAC/SSO/compliance-export **in demand order** — first paying
   design partner picks the first feature.

**Anti-goal, restated from ROADMAP:** no hosted SaaS. The moment shared
state needs a server we've conceded the moat. The transport for team memory
is git; the review surface is the PR.

---

## 6. How this plan can fail (honest assessment, same rule as everywhere)

- **Nobody pays for assurance on a pre-1.0 tool.** Mitigation: the paid
  pilot is the cheapest possible test of willingness-to-pay — run two before
  building anything from rung 3.
- **Open-core line creep.** Every future feature triggers a "free or paid?"
  fight. The dividing line in §2 (individual vs organizational control) is
  the tiebreaker; write it into CONTRIBUTING when the enterprise package
  exists.
- **The segment consolidates upward.** If Copilot Enterprise gets genuinely
  good codebase intelligence at $39/seat, the white space shrinks. The
  synapse layer + cross-agent portability (ROADMAP "Next") is the hedge —
  bets on ecosystem fragmentation, not on incumbents standing still.
- **Solo-maintainer bandwidth.** Rungs 1–2 are deliberately zero-product-code
  so the core roadmap (impact tool, install-mcp targets, portable memory)
  doesn't stall while the business motion starts.
