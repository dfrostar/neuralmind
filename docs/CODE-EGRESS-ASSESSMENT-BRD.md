# Business Requirements Document

**Initiative:** NeuralMind Code Egress Risk Assessment & Compliance-Evidence Backbone
**Document owner:** Darren Frost
**Status:** Draft v0.1 — for review
**Date:** July 13, 2026

## 1. Executive summary

NeuralMind will launch a free **Code Egress Risk Assessment** as the primary top-of-funnel offer for regulated buyers (defense, healthcare, finance). The assessment maps where a prospect's source code currently leaves their network via third-party AI tools, quantifies the associated risk and cost, and produces a defensible findings summary the prospect's own compliance team can use.

The assessment is only credible if NeuralMind can substantiate its compliance positioning. This initiative therefore has a second, dependent workstream: a **compliance-evidence backbone** — a control-to-capability mapping across SOC 2, NIST, HIPAA, and ITAR, with supporting evidence artifacts and pre-approved marketing language. The assessment is the go-to-market motion; the backbone is what makes it survive diligence.

## 2. Business context & problem statement

AI coding assistants have become a largely unmanaged data-egress channel: developers transmit proprietary source to third-party APIs whose retention, training-use, and sub-processor handling are governed by vendor policy, not the customer's controls. Regulated organizations are increasingly required to account for this, but most have neither classified the exposure nor quantified it.

NeuralMind's air-gapped, zero-egress architecture removes the channel entirely. The commercial problem is that this advantage is currently asserted in marketing without a structured way to (a) prove it to a compliance audience and (b) convert interest into qualified pipeline. The assessment plus the evidence backbone solve both.

## 3. Business objectives & success metrics

| # | Objective | Success metric (target TBD by GTM lead) |
|---|-----------|------------------------------------------|
| O1 | Generate qualified pipeline from regulated buyers | # assessments booked; # converting to opportunity |
| O2 | Establish compliance credibility that survives diligence | # assessments passing prospect security review without escalation |
| O3 | Shorten sales cycle for security-led deals | Avg. days from assessment to proposal vs. current baseline |
| O4 | Eliminate overclaiming risk in marketing & sales | Zero legal/procurement rejections of compliance claims |
| O5 | Build reusable compliance evidence | Completed control mapping for all four frameworks |

## 4. Scope

**In scope:** the free assessment offer (intake, delivery, findings deliverable, sales handoff); the compliance-evidence backbone (control mappings, evidence artifacts, approved claim language); the corrected marketing/social language that references them.

**Out of scope (this initiative):** achieving NeuralMind's own SOC 2 Type II report (tracked as a dependency, not delivered here); pricing/packaging of the paid product; net-new product features beyond what evidence collection requires; the paid engagement that follows a successful assessment.

## 5. Stakeholders

Sales/GTM (owns the assessment motion and conversion), Compliance/Security (owns the control mappings and evidence), Product/Engineering (supplies technical evidence of egress behavior and logging), Legal (approves claim language and the assessment's no-obligation terms), Marketing (owns the post and the offer's public framing), and Executive sponsor (Darren).

## 6. Business requirements

### Workstream A — Code Egress Risk Assessment offering

| ID | Requirement | Priority |
|----|-------------|----------|
| BR-A1 | The offer shall be positioned as free, no-obligation, with findings owned by the prospect regardless of purchase decision. | Must |
| BR-A2 | An intake instrument shall capture the quantification inputs (current AI tools in use and sanctioned vs. shadow; contractual/regulatory egress restrictions; # developers blocked or under review; audit-prep effort; current tooling spend). | Must |
| BR-A3 | The assessment shall be deliverable in under one hour of the prospect's time. | Must |
| BR-A4 | The assessment shall produce a 1–2 page findings summary covering: egress paths identified, each vendor's retention/training-use posture, compliance gaps against the prospect's target framework, and a quantified risk-and-savings estimate built from the prospect's own inputs. | Must |
| BR-A5 | The risk-and-savings estimate shall be derived from prospect-supplied figures, not vendor-asserted benchmarks. | Must |
| BR-A6 | A defined sales handoff shall convert a completed assessment into a scoped follow-up conversation; commercial terms shall be introduced only post-assessment. | Must |
| BR-A7 | The offer shall carry a consistent name and a low-friction booking path (e.g., DM/comment/landing form). | Should |
| BR-A8 | All prospect data collected during assessment shall itself be handled per NeuralMind's own compliance posture (no retention beyond stated purpose). | Must |

### Workstream B — Compliance-evidence backbone

| ID | Requirement | Priority |
|----|-------------|----------|
| BR-B1 | A control-mapping matrix shall link each NeuralMind capability (zero egress, local-only inference, local immutable query logging, US-hosted air-gap) to the specific controls it supports in SOC 2, NIST (800-53/800-171/AI RMF), HIPAA Security Rule, and ITAR. | Must |
| BR-B2 | Each mapped control shall reference a concrete evidence artifact (architecture attestation, log sample, network-flow diagram, BAA template, etc.). | Must |
| BR-B3 | The framework prioritized first shall be determined by the initial target segment (open decision — see §10). | Must |
| BR-B4 | All external claim language shall use supportable phrasing ("helps you meet," "supports compliance with," "designed to satisfy the relevant controls") and shall not state or imply guaranteed audit outcomes or non-existent certifications (e.g., "HIPAA certified," "pass any audit"). | Must |
| BR-B5 | The distinction between NeuralMind's own vendor compliance and the customer's audit outcome shall be explicit in all collateral. | Must |
| BR-B6 | Legal shall review and approve the claim language and control mappings before external use. | Must |
| BR-B7 | The backbone shall be maintained as a living artifact, updated as certifications (e.g., NeuralMind's own SOC 2) are achieved. | Should |

## 7. Assumptions

That NeuralMind's architecture genuinely delivers zero code egress and local-only inference as marketed (this is the load-bearing assumption and must be engineering-verified before any claim ships); that regulated buyers have budget and mandate to address AI-tool egress; and that a free assessment is an acceptable motion under the target segments' procurement norms.

## 8. Constraints & dependencies

The assessment cannot make compliance claims the backbone hasn't yet substantiated, so **Workstream B gates the public launch of Workstream A**. NeuralMind's own SOC 2 Type II report (if not yet held) is a dependency for the strongest version of the SOC 2 claim. ITAR positioning depends on verified US-person/US-soil handling of any prospect data. Legal sign-off is a hard gate on external release.

## 9. Risks

The dominant risk is **overclaiming**: any gap between marketed compliance language and provable capability, discovered in diligence by exactly this audience, damages credibility disproportionately — mitigated by BR-B4/B5/B6. Secondary risks: the free assessment attracting unqualified volume without a conversion path (mitigated by BR-A2 qualification inputs and BR-A6 handoff); and assessment-collected prospect data becoming its own compliance liability (mitigated by BR-A8).

## 10. Open decisions

Which framework leads (defense/ITAR-CMMC vs. healthcare/HIPAA vs. finance/SOC 2) — this sets the sequencing of Workstream B and the hero message of the offer. Target metrics for §3. Whether NeuralMind currently holds a SOC 2 report or needs to initiate one. The official name for the assessment.
