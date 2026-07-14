# Enterprise Deployment — Patterns and Governance

Deployment patterns, scaling considerations, and a procurement-aware view of
what ships today vs. what's on the roadmap. Pairs with
[COMPLIANCE-SUMMARY.md](COMPLIANCE-SUMMARY.md) — this document covers *how* to
deploy; that one covers *what auditors will ask*.

For the ROI argument, see [BUSINESS-CASE.md](BUSINESS-CASE.md). For what's
shipping when, see [ROADMAP.md](../ROADMAP.md).

---

## Deployment postures

From strictest to permissive — all four use the same NeuralMind binary; the
difference is which network paths you cut. Verbatim from the
[Compliance Summary](COMPLIANCE-SUMMARY.md):

| Posture | Setup | Use case |
|---|---|---|
| Air-gapped | [`use-cases/air-gapped.md`](use-cases/air-gapped.md) — no outbound network at any phase | Defence, classified, fully isolated |
| Offline runtime | Default install; cut network after `pip install` | Regulated industries, sensitive code |
| On-prem with internet | Default install; uses `pip` / GHCR | Most enterprises |
| Developer workstation | Default install | Individual devs, small teams |

Full walkthrough for regulated environments:
[`use-cases/offline-regulated.md`](use-cases/offline-regulated.md).

## Scaling considerations

- **Per-project isolation.** State lives in `<project>/.neuralmind/` — one
  index per repo, no cross-contamination. Multi-repo monorepos are a single
  index boundary today; per-subproject splitting is manual.
- **Team memory distribution.** Synapse state is committed as
  `.neuralmind-team-memory.json` (v0.30+, content-hash idempotent,
  fail-open). Teammates' agents inherit learned associations on pull.
- **CI auto-index.** Incremental re-index on every commit via
  `neuralmind init-hook .` (git post-commit hook). Full build paid once;
  subsequent runs touch only changed files.

## Missing enterprise features

These are on the [Roadmap "Commercial" lane](../ROADMAP.md) and require a
paid commercial license. They are **not** shipped in the MIT-licensed core:

- SSO / SAML / OAuth (Okta, Azure AD, JumpCloud)
- Admin console (org-wide seat management, audit-log viewer)
- Compliance export (SOC 2 / ISO 27001 / GDPR reports, DPA templates)
- Air-gap packaging (signed offline bundle with support SLA)
- Centralized audit-log shipping (not just local JSONL)

Private repo: `dfrostar/neuralmind-enterprise` — not public until first
enterprise beta.

## Procurement checklist

| Your requirement | Status |
|---|---|
| Full source available (MIT) | ✅ shipped |
| Air-gapped install | ✅ documented; validation pending |
| CycloneDX SBOM per release | ✅ shipped since v0.9.0 |
| Non-root container image | ✅ shipped since v0.9.0 |
| NIST AI RMF alignment | ✅ self-assessment; `neuralmind audit-report` outputs draft |
| SOC 2 Type I/II | ❌ *Self-assessment posture; architecture supports certification, not certified today.* See [COMPLIANCE-SUMMARY.md](COMPLIANCE-SUMMARY.md). |
| GDPR | ✅ Operator-controlled data residency; no third-party processor |

**Compliance questions beyond this page:** open a
[Discussion](https://github.com/dfrostar/neuralmind/discussions) tagged
"compliance", or email [hello@neuralmind.uk](mailto:hello@neuralmind.uk) for
procurement/commercial queries.
