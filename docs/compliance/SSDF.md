# Secure Software Development (NIST SP 800-218 SSDF)

**Date:** 2026-10-18
**Version:** 1.2
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

Version 1.1 said `main` required a pull request and passing CI, that every
change was reviewed in a pull request, and that mypy ran as a check. None of
that was true: §3 now says what is enforced and what is only practice, and §5
says how the software is written.

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
| **PO.2** Roles and responsibilities | [`GOVERNANCE.md`](../../GOVERNANCE.md): one maintainer, acting for Cheval-Volant LLC, owns every path ([`.github/CODEOWNERS`](../../.github/CODEOWNERS)). Outside contributions are signed off under the [DCO](../DCO.md), checked by the maintainer at review | Security training records |
| **PO.3** Supporting toolchains | GitHub Actions workflows under `.github/workflows/`, with every third-party action pinned to a full commit SHA, so a moved tag can't change what runs (`tests/test_workflow_pins.py` fails on an unpinned one). Dependabot for pip, npm and Actions, which keeps those pins current ([`.github/dependabot.yml`](../../.github/dependabot.yml)). CodeQL default setup | |
| **PO.4** Criteria for security checks | CI fails a change on high-severity bandit findings, on any dependency advisory not marked `not_affected` in the [VEX](../../security/neuralmind.openvex.json), and on weak-hash use that breaks FIPS-mode hosts (`tests/test_fips_hash_usage.py`) | |
| **PO.5** Secure development environments | Builds run on ephemeral GitHub-hosted runners. The CI and release workflows (`ci.yml`, `release.yml`, `docker-publish.yml`, `sbom.yml`) give the token `contents: read` by default, and only the jobs that sign, attest, publish or upload scan results get write scopes, each in its own `permissions:` block | Maintainer account 2FA and workstation security |

### PS: Protect the Software

| Practice | Evidence | Not shown here |
|---|---|---|
| **PS.1** Protect code from unauthorized access and tampering | `main`'s ruleset blocks deleting the branch and force pushes, and requests a GitHub Copilot code review on each pull request. **It doesn't require a pull request or passing checks.** Since October 2026, code changes have landed through pull requests by practice, with one exception (`1405792`, a planning document). Before then most changes were pushed to `main` directly, among them fixes from an automated CI watcher: from July to September 2026, about 500 commits reached `main` without a pull request number in their message, against 146 merged pull requests. Three workflows (`sbom.yml`, `neuralmind-autoindex.yml`, `update-chart.yml`) push generated files straight to `main` with a deploy key, and install only pinned packages because they hold it (`requirements-pinned.txt`) | The ruleset lives in repository settings: `gh api repos/dfrostar/neuralmind/rules/branches/main` shows it |
| **PS.2** Mechanism to verify release integrity | Container images are signed keylessly with cosign, bound to the release workflow's GitHub OIDC identity and logged in Sigstore's transparency log (`.github/workflows/docker-publish.yml`). The wheel, sdist and image carry GitHub build-provenance attestations (`release.yml`, `docker-publish.yml`). PyPI uploads use trusted publishing with PEP 740 attestations. Commands in §2 | |
| **PS.3** Archive and protect each release | Immutable GitHub releases, version tags, provenance attestations stored by GitHub, and a VEX document in every tagged tree (`security/neuralmind.openvex.json`). A CycloneDX SBOM for each release since v3.0.0 except v3.8.0 and v3.10.0–v3.13.0, generated by `.github/workflows/sbom.yml`, served under `neuralmind.uk/sbom/` and linked from [neuralmind.uk/security](https://neuralmind.uk/security) rather than attached to the release, because a published release can't take a new asset | The eight missing SBOMs |

### PW: Produce Well-Secured Software

| Practice | Evidence | Not shown here |
|---|---|---|
| **PW.1** Design to meet security requirements | Local-first architecture with no telemetry. The only outbound call by default is the first build's download of the embedding model from a pinned URL, checked against a pinned SHA256, and none when the model is pre-staged ([Compliance Summary](../COMPLIANCE-SUMMARY.md)). The threat model is in [`SECURITY-GUIDE.md`](../SECURITY-GUIDE.md) | |
| **PW.2** Review the design | Design changes land as pull requests reviewed by the automated reviewers in PW.7. Larger features have a spec in `docs/specs/`, and every user-facing change has release notes ([SDLC policy](SDLC_POLICY.md) §2.1) | No second human reviews a design |
| **PW.4** Reuse well-secured components | Dependency floors raised for advisories, a pinned set in `requirements-pinned.txt`, Dependabot alerts, and `pip-audit` on every change. Chosen dispositions follow the [vulnerability management policy](../VULNERABILITY-MANAGEMENT-POLICY.md) | |
| **PW.5** Secure coding practices | ruff (including flake8-bugbear), black and `scripts/check_unreachable.py` fail CI. mypy runs on every change but is advisory: it reported 277 errors on 2026-10-18 and doesn't fail CI. Secrets are scanned before indexing (`neuralmind scan-for-secrets`) | |
| **PW.6** Secure build configuration | A pure-Python wheel built with `python -m build` in a clean CI job. The container image runs as a non-root user and installs offline from pre-downloaded wheels (`Dockerfile`) | |
| **PW.7** Review and analyze code for vulnerabilities | Pull requests are reviewed by two automated reviewers, GitHub Copilot code review and OpenAI Codex, and merged by the maintainer, who reads the diff; no rule makes a merge wait for either. CodeQL (Python, JavaScript/TypeScript, Actions) and bandit run on every change. Bandit's full report goes to code scanning, and high severity fails CI | A second human reviewer |
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

## 5. How NeuralMind is developed

NeuralMind has one maintainer, acting for Cheval-Volant LLC, and much of it is
written with AI coding agents, among them Claude Code, GitHub Copilot's coding
agent and Hermes-Agent. Since October 2026 an agent-drafted commit names its agent in a
`Co-Authored-By` trailer or a session link. Earlier commits didn't do so
consistently: of the 692 commits to `main` from July 2026 that aren't
release-please's, Dependabot's or generated-file pushes, 238 name an agent, and
136 more came from an automated CI watcher (`ci-watcher@neuralmind.uk`).

An assessor should weigh the controls above with that in mind, because they
are what stands between an agent's mistake and a release:

- **Checks on every change** (PO.4, PW.5, PW.7, PW.8): the test suite on three
  operating systems, a FIPS-mode run, bandit, pip-audit, CodeQL and the lint
  gates run on an agent's change as on any other. No rule makes a merge wait
  for them (PS.1).
- **Behaviour contracts** ([`CLAUDE.md`](../../CLAUDE.md)): rules the agents
  read, each from a regression that happened, such as a test for every
  documented exit code and lint commits that never delete code.
- **Automated review** (PW.7): a second model reviews each pull request, and
  catches what the first missed. In v4.17.1, Codex found that a machine policy
  holding an invalid value didn't hold projects to the strictest settings
  (#672, fixed in #674), then that a misspelled `require_encrypted_storage`
  still slipped through that fix (#674, fixed in v4.17.2).
- **What isn't there:** a second human reading each change, and a rule that
  makes a merge wait for the checks and reviews (PS.1). #672 and #674 were
  each merged before Codex had finished reviewing them, which is how both gaps
  reached `main`.
