# NeuralMind Compliance Summary

**One-page reference for procurement, security review, and compliance teams.** Consolidates the NIST AI RMF, SOC 2, and GDPR claims already documented across [`SECURITY-GUIDE.md`](SECURITY-GUIDE.md) and [`ENTERPRISE.md`](ENTERPRISE.md) into a single reviewable surface.

> **Honest scope:** NeuralMind itself is not certified to any compliance framework. The *architecture* supports certification of *your deployment* — every required control is either built in or available to switch on. The evidence below is auditable; the certifications are yours to obtain.

---

## At a glance

| Posture | NeuralMind support |
|---|---|
| Data leaves your machine | **Never** — fully local, no telemetry, no remote logging, no update checks |
| Code uploaded to a cloud provider | **No** — all embeddings generated and stored locally via ChromaDB |
| Outbound network at runtime | **None** — install-time only; see [air-gapped walkthrough](use-cases/air-gapped.md) |
| Audit trail | **Built-in** — `.neuralmind/audit/` access log + query provenance |
| Software Bill of Materials | **Auto-generated** — CycloneDX JSON attached to every tagged release |
| License | **MIT** — full source review, no vendor lock-in |
| Source available | **Yes** — entire codebase on GitHub, every claim verifiable |

---

## NIST AI RMF (AI Risk Management Framework) — full coverage

The four NIST AI RMF functions and the evidence NeuralMind provides for each:

### GOVERN — oversight, accountability, policies

- **Role-based access control (RBAC)** with documented user/permission model — see `SECURITY-GUIDE.md` §Access Control
- **Access audit trail** at `.neuralmind/audit/access.log` — every read, query, and export logged with timestamp + actor + result
- **Query provenance** — every retrieval result is traceable to the specific code nodes that produced it (no black-box "trust us")
- **Auto-generated NIST AI RMF report:** `neuralmind audit-report . --compliance nist-ai-rmf --output report.md`

### MAP — impact assessment, context

- **Per-query explanation:** which code nodes were retrieved, similarity scores, layer-by-layer disclosure (L0→L3)
- **Replay overlay** (v0.6.0+) shows the L3 hits a previous agent query received, on the live graph view
- **Confidence signals** — search results carry similarity scores; community detection labels nodes by code subsystem

### MEASURE — performance, quality

- **Token reduction** measured per query (the headline 40-70× claim); benchmark CI-verified at every commit (`tests/benchmark/`)
- **Index quality metrics** — top-k retrieval hit rate, escalation rate, faithfulness eval framework scaffolded
- **Query latency** logged for every retrieval — performance regressions visible in `audit-report` output

### MANAGE — risk controls

- **Secret detection** runs before any retrieval result is returned (configurable scanners)
- **Rate limiting** enforceable at the MCP server boundary
- **Anomaly alerts** — `events.jsonl` + the live activity feed surface unexpected access patterns in real time

---

## SOC 2 Type II — control evidence

The five Trust Service Criteria categories and where NeuralMind provides evidence:

| SOC 2 Criterion | NeuralMind evidence |
|---|---|
| **CC6.1 Access Control** | RBAC implementation, `.neuralmind/audit/access.log` |
| **CC7.1 Monitoring** | Query logging, performance metrics, live activity feed |
| **CC7.2 System Monitoring** | `/healthz` endpoint (v0.8+), error tracking, structured logging |
| **A1.1 Processing Integrity** | Index validation on every build, audit trail of state changes |
| **C1.2 Availability** | Backup/recovery via standard SQLite/filesystem ops; no external state |
| **P3.1/4.1 Privacy** | No PII collection; data residency under operator control |

Full mapping with line-item evidence pointers: `docs/SOC2_COMPLIANCE_MAPPING.md` (separate detail doc).

---

## GDPR considerations

NeuralMind processes code. Code can contain comments referencing names, emails, or other PII. The relevant GDPR posture:

- **Lawful basis** — operator-controlled (NeuralMind doesn't make the decision; you do)
- **Data minimisation** — NeuralMind retrieves only the ~800 tokens of context needed per query, not the full codebase
- **Purpose limitation** — retrieval is per-query; no profile-building, no cross-query aggregation by default
- **Storage limitation** — the synapse store decays unused edges automatically (configurable via `NEURALMIND_SYNAPSE_DECAY_HALF_LIFE`)
- **Right to erasure** — synapse store and audit log are local files; `rm -rf .neuralmind/` is a complete erasure path
- **Data residency** — entirely under operator control; no cross-border transfers initiated by NeuralMind
- **Pseudonymisation** — audit log actor field is operator-provided; can be a hashed token rather than a username
- **Breach notification** — local files, no external surface area, no third-party processor

NeuralMind does **not** act as a data processor in the GDPR sense — there is no external entity to which data is transferred. The operator is the sole controller.

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
| "Audit trail captures every query" | `cat .neuralmind/audit/access.log` after a session |
| "SBOM covers the full dep tree" | Run `syft .` on a local install, diff against the released SBOM |
| "100% local processing" | Pull internet, `neuralmind build && neuralmind query .` still works |
| "MIT licensed, full source" | `https://github.com/dfrostar/neuralmind` — every file readable |
| "Container image is non-root" | `docker run --rm --entrypoint id ghcr.io/dfrostar/neuralmind:latest` |

---

## Contact

- **Security disclosures:** see [`SECURITY.md`](../SECURITY.md)
- **Compliance questions for your specific environment:** open a [GitHub Discussion](https://github.com/dfrostar/neuralmind/discussions) tagged "compliance"
- **Procurement / commercial questions:** standard issue tracker; NeuralMind is MIT and there is no commercial entity behind it — your support contract is with whoever you choose to engage for deployment

---

## Document scope

This is the **summary** view. For depth:

- [`SECURITY-GUIDE.md`](SECURITY-GUIDE.md) — threat model, encryption, secrets management, line-by-line SOC 2 control evidence
- [`ENTERPRISE.md`](ENTERPRISE.md) — deployment patterns, scaling, multi-team usage
- [`use-cases/air-gapped.md`](use-cases/air-gapped.md) — strictest deployment posture, step-by-step
- [`use-cases/offline-regulated.md`](use-cases/offline-regulated.md) — broader regulated-industry walkthrough
- [`SECURITY.md`](../SECURITY.md) — security policy, vulnerability disclosure
