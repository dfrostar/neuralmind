# NeuralMind — Commercial License Agreement

**Version 1.1 — Effective [Date]** *(remove DRAFT once executed)*

> Canonical commercial facts (entity, pricing, contact) live in
> [`commercial-terms.json`](commercial-terms.json) and are CI-gated by
> `scripts/check_commercial_terms.py`. This document must agree with that file.

This Commercial License Agreement ("Agreement") is entered into between **Cheval-Volant LLC**, a Texas limited liability company doing business as **NeuralMind** ("Licensor"), and the entity agreeing to these terms ("Licensee").

---

## 1. Eligibility & Grant of Use

This commercial license applies to the **NeuralMind Team and Enterprise tiers** (the "Software") deployed in environments of **five (5) or more users** or where paid-tier features are used.

Subject to payment of applicable fees and compliance with this Agreement, Licensor grants Licensee a non-exclusive, non-transferable (except as a whole-entity transfer) right to:

- Deploy the Software on Licensee's infrastructure
- Access paid-tier features: **shared-memory governance, seat management, hash-chained audit log, compliance export, self-hosted deployment**
- Receive **priority support** (SLA defined in Exhibit A)
- Use accompanying documentation and updates during the term

**The MIT core remains free for everyone** — including all token compression and savings — and a 1-seat free-tier license auto-issues on first run (no signup, never expires).

**Affiliates:** Licensee's Affiliates (as defined below) may use the Software under this Agreement, provided Licensee remains responsible for their compliance. "Affiliate" means any entity that directly or indirectly controls, is controlled by, or is under common control with Licensee, where "control" means more than 50% of voting securities or equivalent.

---

## 2. Pricing & Payment

| Model | Rate | Seats |
|-------|------|-------|
| **Team (per-seat)** | $29 / user / month, annual contract | 5–50 |
| **Enterprise** | Custom — [hello@neuralmind.uk](mailto:hello@neuralmind.uk) | Per agreement |

Annual payment includes all updates, patches, and support during the term.

**Order Form Precedence:** Licensee's fees, seat counts, scope, and terms are set exclusively by the executed Agreement and any Order Form(s) referencing it, which prevail over commercial-terms.json, the Commercial Modules License, LICENSING.md, and any repository content. Licensor may change its advertised pricing by editing commercial-terms.json, but such changes shall not affect (i) any then-current executed Agreement or Order Form, (ii) Licensee's rights under the free-tier or evaluation terms, or (iii) any rights that vested before the change.

---

## 3. Restrictions

Licensee shall **not**:

- **Redistribute, resell, sublicense**, or make the Commercial Modules available to third parties as a standalone product or managed service without a separate OEM agreement; *except* that Licensee may permit its third-party professional-services vendors, consultants, and contractors to install, configure, and operate the Commercial Modules solely for Licensee's (and its Affiliates') own benefit and within Licensee's environment or on infrastructure controlled by Licensee, provided such vendors do not themselves offer the Commercial Modules as a standalone or managed service to any third party and are bound by confidentiality obligations at least as protective as those in this Agreement. Licensee remains responsible for its vendors' compliance and for all fees for users engaged in such use.
- **Remove, disable, defeat, or circumvent** audit-log, license-validation, or compliance-export features, or any technological measure that controls access to or protects the Software (these are core to licensed operation); *except* that Licensee may (a) temporarily disable an audit or validation feature to diagnose a defect, provided Licensee promptly notifies Licensor and re-enables the feature; and (b) conduct security testing including testing the integrity of the audit and validation features, provided results are shared with Licensor under a reasonable coordinated-disclosure process. Any such circumvention constitutes material breach, terminates this license immediately, and constitutes unauthorized circumvention of a technological measure under the Digital Millennium Copyright Act (17 U.S.C. §1201). Licensor reserves all remedies under §1201, including statutory damages and injunctive relief, against any person who circumvents such measures.
- **Offer the Commercial Modules to third parties** as a managed, hosted, or multi-tenant on-demand service for the benefit of persons other than the Licensee and its Affiliates, or otherwise monetize the Commercial Modules' capabilities as a service to unaffiliated third parties. *For the avoidance of doubt, Licensee's own internal use across its business units, departments, and Affiliates — including operation of a shared internal platform serving Licensee and its Affiliates — is not a "hosted service" to "third parties" within this Paragraph.*
- **Embed or distribute the Commercial Modules**, or any substantial portion of their code, as a component of, or within, a software product or service that Licensee offers to third parties for a fee or as part of a commercial offering (OEM), including re-exporting the Commercial Modules' functionality as part of Licensee's own commercial product. *For the avoidance of doubt, this Paragraph does NOT prohibit: (a) Licensee's own internal use including invocation of the Commercial Modules from Licensee's own scripts, CI/CD pipelines, build systems, agents, or applications for Licensee's internal operations; (b) use through the open-source CLI/core where permitted by this Agreement; or (c) Licensee distributing its own products that merely call or interoperate with, but do not embed the source of, the Commercial Modules.*
- **Reverse-engineer, decompile**, or attempt to derive source code beyond what is necessary for debugging Licensee's own deployments
- Use the Software in any manner that violates applicable law or regulation

Enterprise modules may include authentication/telemetry and other technological measures that verify license validity and control access to the Software. Circumvention, removal, or disablement of such measures is prohibited under §1201 of the DMCA (17 U.S.C. §1201) and constitutes a material breach of this Agreement.

---

## 4. Ownership & Intellectual Property

Licensor retains all right, title, and interest in the Software, including modifications, enhancements, and derivative works created by Licensor. Licensee retains ownership of its own data and models. Licensor does not claim rights to Licensee's outputs or proprietary models trained using the Software.

The Software is deployed and operates on Licensee's own infrastructure. Licensee's source code, code graphs, embeddings, index files, synapse data, and models remain on Licensee's systems and are not transmitted to, accessed by, or stored by Licensor. Licensor does not collect, use, or train on Licensee's data, code, or models, and has no license to do so. The only data transmitted from Licensee's environment is optional, anonymous license-validation/telemetry needed to verify license validity, which Licensee may disable. Licensor's standard telemetry does not include source code or file contents.

**Open-Source Boundary:** The MIT-licensed core and the commercial/Enterprise modules are separate works. Nothing in this Agreement, and no contribution policy, shall cause the commercial modules to be licensed under, or combined with, any copyleft license (including GPL/AGPL/LGPL, or their successors). Licensor does not accept, and Licensee shall not submit or incorporate into the Software, any code licensed under copyleft terms for the MIT core in a manner that would render the core or the commercial modules subject to copyleft obligations. Licensee shall not embed or link the commercial modules with any copyleft-licensed work. Licensor retains sole authority to determine the license terms of all contributions under the core's contribution policy (MIT/permissive only).

---

## 4A. Audit and Compliance

Licensee shall maintain accurate records of its number of seats, its Authorized Users, and its use of the Software sufficient to demonstrate compliance with this Agreement. Licensor (or a third-party auditor bound to confidentiality) may, upon at least fifteen (15) days' written notice and no more than once per calendar year (or at any time if Licensee is reasonably suspected of material non-compliance), audit Licensee's deployment, the hash-chained audit log, and license-file usage to verify compliance with the seat counts and use limitations herein. Licensee shall provide reasonable access, cooperation, and copies of relevant records. If an audit reveals underpaid fees or unauthorized use of paid-tier or Enterprise features, Licensee shall pay the shortfall plus interest at the lower of the maximum lawful rate or 1.5% per month, and reimburse Licensor's reasonable audit costs. Unauthorized use of paid-tier features constitutes material breach.

---

## 5. Term & Termination

**Term:** This Agreement begins on the effective date and continues for the purchased period. Auto-renewal occurs unless either party provides 30 days' written notice.

**Termination for Cause:** Either party may terminate for material breach uncured within 30 days. Licensee may terminate at any time; fees paid are non-refundable except for Licensor's uncured material breach.

**Effects of Termination:** Upon termination, Licensee shall cease all use of the Commercial Modules and, at Licensor's written request, delete or destroy all copies of the Commercial Modules in Licensee's possession or control and certify such deletion in writing within thirty (30) days; PROVIDED that (i) Licensee may retain a single archival and/or disaster-recovery copy for compliance and legal-hold purposes, which shall not be used to operate the Commercial Modules for any user; (ii) Licensee's legal right to its own data, audit records, exports, and configurations created through the use of the Commercial Modules survives termination and is not impacted; and (iii) the following survive termination: license grants necessary to operate any MIT core separately, Confidentiality, Indemnification, Limitation of Liability, and audit-right obligations.

---

## 6. Confidentiality

Licensee's deployment configuration and model weights are Licensee's confidential information. Licensor's pricing and product roadmap are Licensor's confidential information. Neither party shall disclose the other's confidential information except to employees/contractors with a need-to-know under equivalent obligations.

---

## 7. Indemnification

Licensor shall defend Licensee against third-party claims that the Software infringes a U.S. copyright or trade secret, provided Licensee gives prompt notice, sole control, and reasonable assistance. Licensor liability is capped under Section 8.

---

## 8. Warranty & Limitation of Liability

**Warranty:** Licensor warrants, for the term of this Agreement, that (i) the Commercial Modules will, when operated in accordance with the documentation on a supported platform, function materially in accordance with their published specifications, including that the hash-chained audit log will accurately and tamper-evidently record the events it is documented to record; (ii) the Commercial Modules do not, as delivered, infringe any third-party copyright or patent; and (iii) the license validation feature will not falsely reject a validly-licensed, non-expired Licensee deployment. Licensor's sole obligation for breach of the warranty in (i) is to remediate the defect or provide a workaround within a reasonable period, subject to the Limitation of Liability below. EXCEPT AS EXPRESSLY WARRANTED IN THIS PARAGRAPH, THE COMMERCIAL MODULES ARE PROVIDED "AS IS" AND WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, AND NON-INFRINGEMENT.

**Limitation of Liability:** TO THE MAXIMUM EXTENT PERMITTED BY LAW, (A) LICENSOR'S AGGREGATE LIABILITY FOR DIRECT DAMAGES UNDER THIS AGREEMENT SHALL NOT EXCEED THE GREATER OF (I) THE FEES PAID BY LICENSEE IN THE TWELVE (12) MONTHS PRECEDING THE CLAIM OR (II) TWENTY-FIVE THOUSAND DOLLARS (US$25,000); (B) NEITHER PARTY SHALL BE LIABLE FOR INDIRECT, INCIDENTAL, SPECIAL OR CONSEQUENTIAL DAMAGES, INCLUDING LOST PROFITS OR LOST DATA, EXCEPT AS REQUIRED BY APPLICABLE LAW; AND (C) THE FOREGOING CAPS AND EXCLUSIONS DO NOT APPLY TO (I) EITHER PARTY'S WILLFUL MISCONDUCT OR GROSS NEGLIGENCE, (II) BREACH OF CONFIDENTIALITY, (III) INDEMNIFICATION OBLIGATIONS, OR (IV) A FALSE-DENY OR VALIDATION FAILURE DESCRIBED IN THE WARRANTY PARAGRAPH, FOR WHICH LICENSOR SHALL, AS LICENSEE'S SOLE REMEDY, PROVIDE A REFUND OF FEES PAID FOR THE AFFECTED PERIOD AND REASONABLE SERVICE CREDITS PER THE DEFINED SLA.

---

## 9. Governing Law & Dispute Resolution

This Agreement is governed by the laws of the **State of Texas**, without regard to conflict-of-law principles. All disputes, claims, or controversies arising out of or relating to this Agreement or the Commercial Modules, including any question of its existence, validity, or termination, shall be resolved by binding arbitration in accordance with the AAA Commercial Rules. The arbitration shall be conducted remotely (by videoconference) unless both parties agree otherwise in writing. Venue shall be mutually agreed; if not mutually agreed, the seat shall be Dallas County, Texas. Each party bears its own costs unless the arbitrator awards otherwise. NOTWITHSTANDING THE FOREGOING, either party may seek injunctive relief in any court of competent jurisdiction for breach of the confidentiality, IP, or license-validation provisions of this Agreement.

---

## 10. General

- **Entire Agreement:** Supersedes prior discussions; amendments must be in writing and signed
- **Severability:** If a provision is unenforceable, the remainder continues with the closest valid equivalent
- **Force Majeure:** Neither party is liable for failures beyond reasonable control
- **Trademarks & Publicity:** Neither party acquires any rights in the other's names, logos, or trademarks. Licensee may refer to the NeuralMind software by name in factual, non-endorsing contexts. Licensee shall not state or imply that it is endorsed by, affiliated with, or that its products/services are certified by Licensor absent a separate, written co-marketing agreement. Licensor shall not use Licensee's name or logo in case studies or press without Licensee's prior written consent.
- **Assignment:** Licensee may not assign, transfer, or sublicense this Agreement or any rights hereunder without Licensor's prior written consent, except that Licensee may assign to an affiliate or in connection with a merger, acquisition, or sale of substantially all its assets, provided the assignee agrees in writing to be bound. Licensor may freely assign or transfer this Agreement, in whole or in part, to any affiliate, acquirer, or successor in connection with a merger, acquisition, reorganization, change of control, or sale of all or substantially all of Licensor's assets or the Software (an "Acquisition"), without Licensee's consent, and this Agreement shall inure to the benefit of the successor. Licensor shall notify Licensee of any such assignment.
- **Export Compliance:** The Software, documentation, and related technical data may be subject to U.S. export controls, including the Export Administration Regulations (15 C.F.R. 730 et seq.), the International Traffic in Arms Regulations, and trade sanctions administered by OFAC. Licensee shall comply with all applicable export and re-export laws and shall not (i) export, re-export, transfer, or download the Software (or its commercial tier or license keys) to or for the benefit of any sanctioned/embargoed country, entity, or individual, or (ii) use the Software for a prohibited end-use. Licensee is responsible for determining its own export compliance. Because portions of the Software implement cryptographic authentication (e.g., Ed25519) and may be subject to encryption controls under CCL Category 5 Part 2 (5D002), Licensee acknowledges Licensor makes no representation regarding ECCN classification and Licensee should confirm classification with its own export counsel before transferring the Software cross-border.
- **Data Protection:** The Software is deployed and operates on Licensee's own infrastructure. Licensee's data remains on Licensee's systems. Licensor does not claim rights to Licensee's data, code, or models. The only data transmitted is optional, anonymous license-validation/telemetry, which Licensee may disable.
- **Open Source:** The MIT-licensed core and the commercial modules are separate works. Nothing in this Agreement shall cause the commercial modules to be subject to copyleft obligations. No Contributor may submit copyleft-licensed code to the MIT core in a manner that would infect the commercial modules.
- **DMCA:** Enterprise modules include technological measures that verify license validity and control access to the Software. Circumvention is prohibited under 17 U.S.C. §1201 and constitutes material breach. Licensor reserves all remedies under §1201.

---

*By using NeuralMind Enterprise features or signing an Order Form referencing this Agreement, Licensee agrees to these terms.*

**Cheval-Volant LLC d/b/a NeuralMind** — [hello@neuralmind.uk](mailto:hello@neuralmind.uk)
