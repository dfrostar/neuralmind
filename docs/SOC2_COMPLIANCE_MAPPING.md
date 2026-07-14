# SOC 2 Type II — Control Mapping & Evidence

**One-page evidence map for audit readiness.** This document
cross-references NeuralMind's capabilities against the AICPA Trust
Service Criteria. It is a **self-assessment**, not an audited
attestation. Scope: single-tenant, local-first deployment.

---

## Honest scope

NeuralMind itself is not SOC 2 certified. This map shows where the
*architecture* satisfies control objectives and where a customer
would need to supplement with their own policies and configurations.
A full SOC 2 Type II audit scopes the organization, not the tool.

For the companion summary, see [`COMPLIANCE-SUMMARY.md`](COMPLIANCE-SUMMARY.md).

---

## Control-by-control mapping

### CC6.1 — Access Control

| Sub-objective | NeuralMind evidence | Location | Gap |
|---|---|---|---|
| Logical access restrictions | Roles defined: viewer, developer, admin | `SECURITY-GUIDE.md` §Access Control | No SSO/SAML in OSS; RBAC enforced at MCP boundary only |
| Access authentication | Local user identity via OS; MCP bearer token | `neuralmind serve --token` | No centralized IdP integration in OSS |
| Network segmentation | localhost-only binding by default; air-gapped mode | `docs/use-cases/air-gapped.md` | TLS is opt-in, not default for local connections |

### CC7.1 — Monitoring

| Sub-objective | NeuralMind evidence | Location | Gap |
|---|---|---|---|
| Query and access logging | Append-only `.neuralmind/audit_events.jsonl` | `COMPLIANCE-SUMMARY.md` §Audit trail | Local-only; no centralized SIEM shipping in OSS |
| Anomaly detection | Live activity feed via SSE; `events.jsonl` | `neuralmind serve` + `neuralmind watch` | Manual review required; no automated alerting |

### CC7.2 — System Monitoring

| Sub-objective | NeuralMind evidence | Location | Gap |
|---|---|---|---|
| Health monitoring | `/healthz` endpoint (v0.8+) | `neuralmind serve --port` | External monitoring must scrape; no push-based alerting |
| Error tracking | Structured error logs to stderr + event log | `neuralmind doctor` | Log retention is operator-managed |

### A1.1 — Processing Integrity

| Sub-objective | NeuralMind evidence | Location | Gap |
|---|---|---|---|
| Index validation | CI-gated self-benchmark on every PR | `.github/workflows/ci-benchmark.yml` | Validates retrieval reduction, not faithfulness |
| Audit trail of state changes | Event log captures build/query/stats actions | `.neuralmind/events.jsonl` | Operator-managed retention |

### C1.2 — Availability

| Sub-objective | NeuralMind evidence | Location | Gap |
|---|---|---|---|
| Backup/recovery | `synapses.db` + index are local files; standard SQLite/filesystem ops | Project directory | No automated backup; operator responsibility |

### P3.1 / P4.1 — Privacy

| Sub-objective | NeuralMind evidence | Location | Gap |
|---|---|---|---|
| Data residency | Fully local; no cross-border transfers | `COMPLIANCE-SUMMARY.md` §GDPR | None for OSS tier |
| Right to erasure | `rm -rf .neuralmind/` is complete erasure | `COMPLIANCE-SUMMARY.md` | Data is operator-controlled; no third-party copies |

---

## Audit preparation checklist

What the customer provides:

- [ ] Documented access control policy for NeuralMind users
- [ ] Log retention policy for `.neuralmind/audit_events.jsonl`
- [ ] Backup policy for `synapses.db` + index files
- [ ] Incident response plan that covers the local tool
- [ ] Vendor risk management file for NeuralMind (MIT OSS, no vendor)

What NeuralMind provides:

- [ ] SBOM in CycloneDX format (attached to every release)
- [ ] Source code (MIT, auditable)
- [ ] Health endpoint for monitoring
- [ ] Audit trail with query provenance
- [ ] Air-gapped install documentation (strictest deployment)

---

## Gap summary

| Gap | Severity | Notes |
|-----|----------|-------|
| No SSO/SAML integration | Medium | Commercial module (roadmap, private repo) |
| No centralized audit-shipping | Medium | Commercial module with Splunk/Datadog/Elastic |
| No automated log rotation | Low | Operator-managed |
| No formal SOC 2 certification | High | Self-assessment only; customer can audit the deployment |

For procurement teams: these gaps are standard for a local-first,
single-tenant OSS tool. They are addressable either through the
commercial tier (SSO, admin console, audit-shipping) or through the
customer's own deployment configuration (log rotation, backup,
centralized monitoring of `events.jsonl`).
