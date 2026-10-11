# Secure Software Development (NIST SP 800-218 SSDF)

**Date:** 2026-10-11
**Version:** 1.1
**Framework:** NIST SP 800-218 v1.1, Secure Software Development Framework (SSDF)

---

## 1. Purpose

Map each SSDF practice to the evidence in this repository, so a federal buyer,
an assessor, or the officer who signs CISA's Secure Software Development
Attestation Form can check it rather than take it on trust.

NIST doesn't certify software against the SSDF. A US federal agency buying
software asks its producer to **attest** to the SSDF practices (OMB M-22-18 and
M-23-16), on CISA's Secure Software Development Attestation Form, signed by
the producer's CEO or a designee. For NeuralMind that is Cheval-Volant LLC.
This document is the evidence behind that signature. It isn't the attestation
itself.

For the other NIST documents (FIPS 140-3, SP 800-171, SP 800-53, AI RMF)
and what's planned, see [NIST.md](NIST.md).

## 2. How to verify a release yourself

Every release from the version that ships this document onward is signed and
carries build provenance. These commands need no access to the repository
beyond reading it:

```bash
# The container image: a keyless Sigstore signature from the release workflow
cosign verify ghcr.io/dfrostar/neuralmind:vX.Y.Z \
  --certificate-identity-regexp '^https://github\.com/dfrostar/neuralmind/\.github/workflows/docker-publish\.yml@refs/(heads/main|tags/v[0-9]+\.[0-9]+\.[0-9]+)$' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com

# Its build provenance (which workflow, commit and runner built it)
gh attestation verify oci://ghcr.io/dfrostar/neuralmind:vX.Y.Z --repo dfrostar/neuralmind \
  --cert-identity-regex '^https://github\.com/dfrostar/neuralmind/\.github/workflows/docker-publish\.yml@refs/(heads/main|tags/v[0-9]+\.[0-9]+\.[0-9]+)$'

# The wheel or sdist you downloaded
pip download --no-deps neuralmind==X.Y.Z -d dist/
gh attestation verify dist/neuralmind-X.Y.Z-py3-none-any.whl --repo dfrostar/neuralmind \
  --cert-identity-regex '^https://github\.com/dfrostar/neuralmind/\.github/workflows/release\.yml@refs/(heads/main|tags/v[0-9]+\.[0-9]+\.[0-9]+)$'
```

The identity patterns pin both the workflow and the git ref it ran from:
`main`, where release-please dispatches releases, or a `vX.Y.Z` tag. A
signature from the same workflow run on any other branch fails them. `--repo`
alone would accept it.

The release workflow runs the first two against every image it publishes and
fails before `:latest` moves if either doesn't verify.

## 3. Practice-by-practice evidence

"Evidence" is what the repository shows. "Not shown here" is what the SSDF asks
for that a repository can't demonstrate, such as account security and
settings outside version control. The attesting officer confirms those
directly.

### PO: Prepare the Organization

| Practice | Evidence | Not shown here |
|---|---|---|
| **PO.1** Define security requirements for development | [`SECURITY.md`](../../SECURITY.md), [`SECURITY-GUIDE.md`](../SECURITY-GUIDE.md) threat model, the [SDLC policy](SDLC_POLICY.md) and the [risk assessment](RISK_ASSESSMENT.md) | |
| **PO.2** Roles and responsibilities | [`GOVERNANCE.md`](../../GOVERNANCE.md) (maintainer acting for Cheval-Volant LLC), [`.github/CODEOWNERS`](../../.github/CODEOWNERS), contributions under the [DCO](../DCO.md) | Security training records |
| **PO.3** Supporting toolchains | GitHub Actions workflows under `.github/workflows/`, with every third-party action pinned to a full commit SHA, so a moved tag can't change what runs (`tests/test_workflow_pins.py` fails on an unpinned one). Dependabot for pip, npm and Actions, which keeps those pins current ([`.github/dependabot.yml`](../../.github/dependabot.yml)). CodeQL default setup | |
| **PO.4** Criteria for security checks | CI fails a change on high-severity bandit findings, on any dependency advisory not marked `not_affected` in the [VEX](../../security/neuralmind.openvex.json), and on weak-hash use that breaks FIPS-mode hosts (`tests/test_fips_hash_usage.py`) | |
| **PO.5** Secure development environments | Builds run on ephemeral GitHub-hosted runners. The CI and release workflows (`ci.yml`, `release.yml`, `docker-publish.yml`, `sbom.yml`) give the token `contents: read` by default, and only the jobs that sign, attest, publish or upload scan results get write scopes, each in its own `permissions:` block | Maintainer account 2FA and workstation security |

### PS: Protect the Software

| Practice | Evidence | Not shown here |
|---|---|---|
| **PS.1** Protect code from unauthorized access and tampering | `main` is protected by a ruleset requiring a PR and passing CI, and the only bypass is a deploy key used by the SBOM publish job (see the comment in `.github/workflows/sbom.yml`). Contributions are made under the [DCO](../DCO.md) | The ruleset itself lives in repository settings |
| **PS.2** Mechanism to verify release integrity | Container images are signed keylessly with cosign, bound to the release workflow's GitHub OIDC identity and logged in Sigstore's transparency log (`.github/workflows/docker-publish.yml`). The wheel, sdist and image carry GitHub build-provenance attestations (`release.yml`, `docker-publish.yml`). PyPI uploads use trusted publishing with PEP 740 attestations. Commands in §2 | |
| **PS.3** Archive and protect each release | Immutable GitHub releases, version tags, a CycloneDX SBOM per release (`.github/workflows/sbom.yml`, served at [neuralmind.uk/security](https://neuralmind.uk/security)), provenance attestations stored by GitHub, and a VEX document in every tagged tree (`security/neuralmind.openvex.json`) | |

### PW: Produce Well-Secured Software

| Practice | Evidence | Not shown here |
|---|---|---|
| **PW.1** Design to meet security requirements | Local-first architecture with no telemetry and no outbound calls by default ([Compliance Summary](../COMPLIANCE-SUMMARY.md)), and the threat model in [`SECURITY-GUIDE.md`](../SECURITY-GUIDE.md) | |
| **PW.2** Review the design | Design changes land as reviewed PRs. Planning documents per the [SDLC policy](SDLC_POLICY.md) §2.1 | |
| **PW.4** Reuse well-secured components | Dependency floors raised for advisories, a pinned set in `requirements-pinned.txt`, Dependabot alerts, and `pip-audit` on every change. Chosen dispositions follow the [vulnerability management policy](../VULNERABILITY-MANAGEMENT-POLICY.md) | |
| **PW.5** Secure coding practices | ruff (including flake8-bugbear), black, mypy and `scripts/check_unreachable.py` in CI. Secrets are scanned before indexing (`neuralmind scan-for-secrets`) | |
| **PW.6** Secure build configuration | A pure-Python wheel built with `python -m build` in a clean CI job. The container image runs as a non-root user and installs offline from pre-downloaded wheels (`Dockerfile`) | |
| **PW.7** Review and analyze code for vulnerabilities | Every change is reviewed in a PR. CodeQL (Python, JavaScript/TypeScript, Actions) and bandit run on every change. Bandit's full report goes to code scanning, and high severity fails CI | |
| **PW.8** Test executable code | The pytest suite on Linux, macOS and Windows across Python 3.10–3.12, a run with the OpenSSL FIPS provider enforced, fresh-install and MCP stdio smoke tests, and the published-package and image smoke tests on release | Dynamic testing or fuzzing |
| **PW.9** Secure settings by default | No telemetry; the MCP server uses stdio by default; the graph server binds to `127.0.0.1` and requires an access token unless started with `--no-auth`; LLM seeding is off unless `NEURALMIND_LLM_SEED=1` ([`SECURITY-GUIDE.md`](../SECURITY-GUIDE.md)) | |

### RV: Respond to Vulnerabilities

| Practice | Evidence | Not shown here |
|---|---|---|
| **RV.1** Identify and confirm vulnerabilities on an ongoing basis | A disclosure policy with response targets ([`SECURITY.md`](../../SECURITY.md)), Dependabot alerts, `pip-audit` and CodeQL on every change, and `.github/workflows/chromadb-cve-watch.yml` watching unpatched advisories for a fix | |
| **RV.2** Assess, prioritize and remediate | The [vulnerability management policy](../VULNERABILITY-MANAGEMENT-POLICY.md) (fix, raise the floor, or a documented non-fix, with remediation targets). Not-affected decisions are published as OpenVEX (`security/neuralmind.openvex.json`), and the CI gate ignores exactly those | |
| **RV.3** Analyze root causes | The [incident response policy](INCIDENT_RESPONSE.md). Regressions get a guard where they happened: CLAUDE.md's "Behaviour contracts" came from the lost `doctor` exit code, and `tests/test_fips_hash_usage.py` from the FIPS-mode crash | |

## 4. The VEX document

`security/neuralmind.openvex.json` is an [OpenVEX](https://openvex.dev)
document listing the advisories in NeuralMind's dependencies that NeuralMind is
not affected by, and why. Today those are the four ChromaDB advisories argued in
[`SECURITY.md`](../../SECURITY.md): ChromaDB is an opt-in extra, and NeuralMind
uses only its local `PersistentClient`. Feed it to a scanner that reads VEX
(Grype `--vex`, Trivy `--vex`) together with the release SBOM, and those
advisories are shown as not affected rather than open.

Three things keep it honest:

- CI's `pip-audit` ignores exactly the advisories it lists (`scripts/vex_ignores.py`). Any other advisory fails the build.
- `tests/test_vex.py` fails if an entry lacks an argument in `SECURITY.md`, or if the list drifts from the advisories `chromadb-cve-watch.yml` watches.
- When ChromaDB ships a fix, the watch files an issue. The statement then comes out of VEX, and the pin moves.
