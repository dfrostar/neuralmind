# NeuralMind Compliance Summary

**One-page reference for procurement, security review, and compliance teams.** Consolidates the NIST AI RMF, SOC 2, CMMC 2.0, and GDPR claims already documented across [`SECURITY-GUIDE.md`](SECURITY-GUIDE.md) and [`ENTERPRISE.md`](ENTERPRISE.md) into a single reviewable surface.

> **Honest scope:** NeuralMind itself is not certified to any compliance framework. The *architecture* supports certification of *your deployment* — every required control is either built in or available to switch on. The evidence below is auditable; the certifications are yours to obtain.

---

## At a glance

| Posture | NeuralMind support |
|---|---|
| Data leaves your machine | **Never by default** — fully local, no telemetry, no remote logging, no update checks. One opt-in exception: see below |
| Code uploaded to a cloud provider | **No** — all embeddings generated and stored locally via ChromaDB or the local ONNX backend |
| Outbound network at runtime | **None by default** — install-time only unless `NEURALMIND_LLM_SEED=1` + `ANTHROPIC_API_KEY` are explicitly set, which sends only README/architecture-doc prose (never code, never client files) to Anthropic for synapse seeding. See [`compliance/THIRD_PARTY_LLM_DISCLOSURE.md`](compliance/THIRD_PARTY_LLM_DISCLOSURE.md) and the [air-gapped walkthrough](use-cases/air-gapped.md) |
| Video/media file ingestion | **Not supported** — no code path accepts video, image, or audio files at any layer; see [`compliance/THIRD_PARTY_LLM_DISCLOSURE.md`](compliance/THIRD_PARTY_LLM_DISCLOSURE.md) §2 |
| Certifications held | **None.** NeuralMind has no SOC 2 report and no CMMC assessment. Both frameworks assess an organization's environment; the sections below show what NeuralMind gives your assessor |
| Audit trail | **Built-in** — `.neuralmind/audit_events.jsonl` append-only log + query provenance |
| Software Bill of Materials | **Auto-generated** — CycloneDX JSON attached to every tagged release |
| License | **MIT** — full source review, no vendor lock-in |
| Source available | **Yes** — entire codebase on GitHub, every claim verifiable |

---

## NIST AI RMF (AI Risk Management Framework) — full coverage

The four NIST AI RMF functions and the evidence NeuralMind provides for each:

### GOVERN — oversight, accountability, policies

- **Role-based access control (RBAC)** with documented user/permission model — see `SECURITY-GUIDE.md` §Access Control
- **Access audit trail** at `.neuralmind/audit_events.jsonl` — every query, search, build, and MCP call logged with timestamp, action, status, and details (the RBAC actor is captured at the MCP boundary)
- **Query provenance** — every retrieval result is traceable to the specific code nodes that produced it (no black-box "trust us")
- **Auto-generated NIST AI RMF report:** `neuralmind audit-report . --compliance nist-ai-rmf --output report.md`

### MAP — impact assessment, context

- **Per-query explanation:** which code nodes were retrieved, similarity scores, layer-by-layer disclosure (L0→L3)
- **Replay overlay** (v0.6.0+) shows the L3 hits a previous agent query received, on the live graph view
- **Confidence signals** — search results carry similarity scores; community detection labels nodes by code subsystem

### MEASURE — performance, quality

- **Token reduction** measured per query — the 12-50× real-repo range comes from field reports (`neuralmind benchmark`); CI verifies a conservative floor on a fixture at every commit (`tests/benchmark/`), and the public benchmark reproduces on demand (`python -m evals.public.run`)
- **Index quality metrics** — top-k retrieval hit rate, escalation rate, faithfulness eval framework scaffolded
- **Query latency** logged for every retrieval — performance regressions visible in `audit-report` output

### MANAGE — risk controls

- **Secret detection** runs before any retrieval result is returned (configurable scanners)
- **Rate limiting** enforceable at the MCP server boundary
- **Anomaly alerts** — `events.jsonl` + the live activity feed surface unexpected access patterns in real time

---

## SOC 2 — Trust Services Criteria evidence

A SOC 2 report is a CPA firm's attestation about a *service organization's* controls, measured against the AICPA Trust Services Criteria. Security (the Common Criteria, CC) is in every report; Availability (A), Processing Integrity (PI), Confidentiality (C), and Privacy (P) are optional. NeuralMind runs inside your environment and transmits no repository content to us, so in your audit it is software within your system boundary, not a subservice organization.

| Criterion | What it covers | NeuralMind evidence |
|---|---|---|
| **CC6.1** | Logical access security | RBAC at the MCP boundary (`neuralmind/mcp_security.py`), denials written to the audit log |
| **CC6.3** | Role-based access, least privilege | Three default roles (`admin`, `builder`, `reader`) with per-tool permissions |
| **CC6.7** | Restricting transmission of information | No telemetry; no repository content sent off the machine. The one outbound request is the embedding-model download, pre-seedable with `NEURALMIND_ONNX_MODEL_DIR` |
| **CC7.1** | Detecting vulnerabilities | CycloneDX SBOM on every tagged release, for your SCA scanner |
| **CC7.2** | Monitoring for anomalies | Hash-chained `.neuralmind/audit_events.jsonl` (`neuralmind audit verify` walks the chain), `/healthz` endpoint, live activity feed |
| **CC9.2** | Vendor and business-partner risk | MIT source, SBOM, and the [third-party LLM disclosure](compliance/THIRD_PARTY_LLM_DISCLOSURE.md) for the opt-in `NEURALMIND_LLM_SEED` path |
| **A1.2** | Backup and recovery | All state is local SQLite and files under `.neuralmind/`: back it up with your normal tooling, or rebuild it from source with `neuralmind build` |
| **C1.1 / C1.2** | Keeping and disposing of confidential information | The index and audit log stay in the project directory under your access controls; the [deletion procedure](compliance/DATA_DELETION.md) lists every location to remove, including the committed `.neuralmind-team-memory.json` |
| **P3.1 / P4.1** | Collecting and using personal information only for stated purposes | NeuralMind collects no personal data and sends no telemetry |

The policies the project itself runs under (access control, change management, incident response, and others) are in [`compliance/`](compliance/), each tagged with the criteria it addresses.

---

## CMMC 2.0 — practice evidence

CMMC assesses a defense contractor's environment, not a tool. Level 1 covers the 15 FAR 52.204-21 requirements for Federal Contract Information (FCI); Level 2 covers the 110 NIST SP 800-171 Rev. 2 requirements for Controlled Unclassified Information (CUI); Level 3 adds selected NIST SP 800-172 requirements.

If NeuralMind indexes source code that is CUI, the index, synapse store, and audit log derived from it are CUI too, and NeuralMind becomes an asset inside your assessment scope. The table shows what NeuralMind gives your assessor and what stays your environment's job. Practice IDs are Level 2.

| Practice | Requirement | NeuralMind provides | Still yours |
|---|---|---|---|
| **AC.L2-3.1.1** | Limit system access to authorized users | RBAC at the MCP boundary; the graph server and HTTP MCP transport bind to `127.0.0.1` | OS accounts and file permissions on `.neuralmind/` |
| **AC.L2-3.1.2** | Limit access to permitted functions | Per-role tool permissions (`admin`, `builder`, `reader`) | Assigning roles to people |
| **AC.L2-3.1.20** | Control connections to external systems | No telemetry; no repository content sent off the machine. `NEURALMIND_LLM_SEED` is off by default | Keeping `NEURALMIND_LLM_SEED` off in a CUI enclave; pre-seeding the model with `NEURALMIND_ONNX_MODEL_DIR` |
| **AU.L2-3.3.1** | Create and retain audit records | Append-only `.neuralmind/audit_events.jsonl` covering queries, searches, builds, and MCP calls | Retention period and forwarding to your SIEM |
| **AU.L2-3.3.2** | Trace actions to individual users | Actor recorded at the MCP boundary | Local CLI queries record a system-level actor; tie them to OS login records |
| **AU.L2-3.3.8** | Protect audit information | SHA-256 hash chain makes edits detectable; `neuralmind audit verify` checks it | Preventing deletion: file permissions, log forwarding |
| **CM.L2-3.4.1** | Baseline configurations and inventories | CycloneDX SBOM on every tagged release | Recording the pinned version in your baseline |
| **CM.L2-3.4.7** | Restrict nonessential ports and services | Stdio MCP transport by default; HTTP servers bind to localhost; [air-gapped install](use-cases/air-gapped.md) | Not exposing the HTTP transport beyond the enclave |
| **SC.L2-3.13.11** | FIPS-validated cryptography for CUI | Not provided: NeuralMind does not encrypt data at rest | FIPS-validated full-disk encryption on the host |
| **SC.L2-3.13.16** | Protect CUI at rest | Not provided | The same host encryption covers `.neuralmind/` |
| **SI.L2-3.14.1** | Identify and correct system flaws | [Vulnerability disclosure policy](../SECURITY.md), SBOM for your scanner | Staying on the latest release |

**The AI agent is the boundary that matters.** NeuralMind hands code slices to your coding agent, and the agent sends them to its model provider. If that code is CUI, the provider is a cloud service handling covered defense information and must meet DFARS 252.204-7012 (FedRAMP Moderate or equivalent). NeuralMind reduces how much code the agent sends; it does not make a provider eligible.

To point an assessor at where a practice is implemented in your own code, `neuralmind compliance .` lists annotations such as `// AC.L2-3.1.1: Authorized access control`. Finding an annotation shows where a practice is claimed, not that it works.

---

## GDPR considerations

NeuralMind processes code. Code can contain comments referencing names, emails, or other PII. The relevant GDPR posture:

- **Lawful basis** — operator-controlled (NeuralMind doesn't make the decision; you do)
- **Data minimisation** — NeuralMind retrieves only the ~800 tokens of context needed per query, not the full codebase
- **Purpose limitation** — retrieval is per-query; no profile-building, no cross-query aggregation by default
- **Storage limitation** — the synapse store decays unused edges automatically (configurable via `NEURALMIND_SYNAPSE_DECAY_HALF_LIFE`)
- **Right to erasure** — synapse store and audit log are local files; `rm -rf .neuralmind/` is a complete erasure path
- **Data residency** — entirely under operator control; no cross-border transfers initiated by NeuralMind
- **Pseudonymisation** — audit log actor field is system-level on local queries and operator-supplied at the MCP boundary; can be a hashed token rather than a username
- **Breach notification** — local files, no external surface area by default

NeuralMind does **not** act as a data processor in the GDPR sense in its
default configuration — there is no external entity to which data is
transferred, and the operator is the sole controller. The one exception is
the opt-in `NEURALMIND_LLM_SEED=1` documentation-synapse-seeding path,
which makes Anthropic a subprocessor for README/architecture-doc prose
only, if and only if an operator explicitly enables it. See
[`compliance/THIRD_PARTY_LLM_DISCLOSURE.md`](compliance/THIRD_PARTY_LLM_DISCLOSURE.md)
for the full disclosure, including how to verify it stays disabled.

---

## Software Bill of Materials (SBOM)

Every tagged release from v0.9.0 onward ships a **CycloneDX JSON SBOM** attached as a GitHub Release asset:

- **File:** `neuralmind-vX.Y.Z.sbom.json` on the release page
- **Format:** CycloneDX 1.x JSON — compatible with Grype, Trivy, Dependency-Track, FOSSology, and most enterprise SCA scanners
- **Scope:** NeuralMind package + every transitive runtime dependency with versions and licenses
- **Generator:** Anchore's syft via the official `anchore/sbom-action` ([workflow source](../.github/workflows/sbom.yml))

The SBOM is regenerated on every tag push; you can pin a specific release's SBOM by URL: `https://github.com/dfrostar/neuralmind/releases/download/vX.Y.Z/neuralmind-vX.Y.Z.sbom.json`.

---

## Container image provenance

Container builds from v0.9.0 onward are auto-published to GHCR ([workflow source](../.github/workflows/docker-publish.yml)):

- **Registry:** `ghcr.io/dfrostar/neuralmind:vX.Y.Z` and `:latest`
- **Platforms:** `linux/amd64` + `linux/arm64`
- **Base image:** `python:3.12-slim` (Debian slim, official Python upstream)
- **User:** non-root (`neuralmind` UID)
- **Network:** no outbound calls at build time (all transitive wheels pre-downloaded in the builder stage; runtime install uses `--no-index`)
- **OCI labels:** `org.opencontainers.image.source`, `version`, `licenses=MIT`

---

## Deployment postures (strict → permissive)

| Posture | Setup | Use case |
|---|---|---|
| **Air-gapped** | [`docs/use-cases/air-gapped.md`](use-cases/air-gapped.md) — no outbound network at any phase | Defence, classified, fully isolated |
| **Offline runtime** | Default install; cuts network after `pip install` | Regulated industries, sensitive code |
| **On-prem with internet** | Default install; uses `pip` and GHCR | Most enterprises |
| **Developer workstation** | Default install | Individual developers, small teams |

Choose the strictest your operational needs allow — all four use the same NeuralMind binary; the difference is which network paths you cut.

---

## Verification — every claim is verifiable

| Claim | How to verify yourself |
|---|---|
| "No outbound network at runtime" | `ss -tnp \| grep python` while running `neuralmind query` — no connections |
| "Audit trail captures every query" | `cat .neuralmind/audit_events.jsonl` after a session |
| "SBOM covers the full dep tree" | Run `syft .` on a local install, diff against the released SBOM |
| "Local processing" | After one build has cached the embedding model (or with `NEURALMIND_ONNX_MODEL_DIR` pre-seeded), disconnect the network: `neuralmind build . && neuralmind query . "where is auth handled?"` still works |
| "MIT core, source-available Team modules" | `LICENSING.md` draws the boundary; every file is readable at `https://github.com/dfrostar/neuralmind` |
| "Container image is non-root" | `docker run --rm --entrypoint id ghcr.io/dfrostar/neuralmind:latest` |

---

## Contact

- **Security disclosures:** see [`SECURITY.md`](../SECURITY.md)
- **Compliance questions for your specific environment:** open a [GitHub Discussion](https://github.com/dfrostar/neuralmind/discussions) tagged "compliance"
- **Procurement / commercial questions:** email [hello@neuralmind.uk](mailto:hello@neuralmind.uk). The software itself is MIT-licensed and free; commercial support for deployment, integration, and evaluation is available. Evaluating teams can request a **free AI-spend assessment** — we benchmark NeuralMind against one of your repos and report your actual token-reduction ratio.

---

## Document scope

This is the **summary** view. For depth:

- [`SECURITY-GUIDE.md`](SECURITY-GUIDE.md) — threat model, encryption, secrets management, SOC 2 and CMMC 2.0 summaries
- [`compliance/THIRD_PARTY_LLM_DISCLOSURE.md`](compliance/THIRD_PARTY_LLM_DISCLOSURE.md) — precise, code-cited answer to "does any client content (including media files) ever reach a third-party LLM"
- [`use-cases/air-gapped.md`](use-cases/air-gapped.md) — strictest deployment posture, step-by-step
- [`use-cases/offline-regulated.md`](use-cases/offline-regulated.md) — broader regulated-industry walkthrough
- [`SECURITY.md`](../SECURITY.md) — security policy, vulnerability disclosure
