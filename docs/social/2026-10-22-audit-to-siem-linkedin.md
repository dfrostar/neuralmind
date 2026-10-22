# LinkedIn post — 2026-10-22: audit to your SIEM, SP 800-53 paperwork, a baseline that checks itself

**Draft, ready to post** once v4.20.0 is on PyPI (the features shipped in
v4.19.0; v4.20.0 puts them on the redesigned `/security` page this post links
to).

Company-page post for compliance leads at defense contractors and federal
suppliers. It covers three v4.19.0 features: audit forwarding to syslog with
the write-failure alert, the OSCAL component definition, and
`neuralmind hardening`. Drafted here so `tests/test_docs_claims.py` vets it
before it is posted.

## Before posting

- [ ] v4.20.0 is on PyPI and https://neuralmind.uk/security shows the controls
      as released (the page judges "released" against the latest release it
      reads at build time).
- [ ] The OSCAL link below resolves on `main`.
- [ ] Don't add "compliant", "certified" or "CMMC-ready": NeuralMind supports
      controls in *your* system; your assessment decides compliance.

## Post text

Your AI coding tool reads your source code. In a CMMC enclave or an
800-53 system, that makes it part of the system, and your assessor will ask
what it logs, where the logs go, and how you know it's configured the way your
plan says.

NeuralMind v4.19.0 gives you an answer to each of those.

Where the logs go: every audit record goes to syslog as it is written, from
the CLI, the MCP server, the editor hooks and the daemon. Each record carries
its hash-chain fields, so your SIEM can check that none were altered or
dropped. If a record can't be written (say, a full disk), an alert-severity
message goes straight to syslog, without going through the log that failed.
That's AU.L2-3.3.4 and 3.3.5. Under the hardened profile, records go only to
the local syslog daemon, which forwards to your SIEM over TLS.

What it does for your SSP: we publish an OSCAL component definition, NIST's
machine-readable format, stating which SP 800-53 controls NeuralMind
implements and which stay yours. Import it into your System Security Plan
tooling.

How you know it's configured: `neuralmind hardening` checks a 17-rule
baseline, each rule mapped to its 800-53 controls, and reports pass, fail or
n/a with the fix for each failure. It exits 1 on any failure, and `--json`
keeps the result as assessment evidence. Run it on a schedule as part of
continuous monitoring.

None of this makes a system compliant on its own. It gives you the logs, the
paperwork and the checks for the part of your system that NeuralMind is.

Security page, with release verification (signatures, SBOM, VEX):
https://neuralmind.uk/security

## Fact check

| Claim | Source |
|---|---|
| Every record to syslog as written, from CLI, MCP server, hooks and daemon | `docs/releases/RELEASE_NOTES_v4.19.0.md` ("Each record goes out right after it is written") |
| Records carry `sha256` and `prev_sha256` | same, and `docs/SECURITY-GUIDE.md#forwarding-to-syslog-v4190` |
| Alert-severity `audit_write_failed` sent straight to syslog, not through the log | release notes, "The AU.L2-3.3.4 alert" |
| Under `security.profile: cui`, only a unix socket or loopback target | release notes, "Under `security.profile: cui`, the target must be on this machine" |
| OSCAL component definition | `security/neuralmind.oscal-component-definition.json` |
| 17 rules mapped to SP 800-53, pass/fail/n/a, fix, exit 1, `--json` | `docs/compliance/SP800-53-HARDENING.md`, `tests/test_cli_exit_codes.py` |
| SBOM, VEX, signatures on `/security` | `site/src/app/security/` (#695) |
