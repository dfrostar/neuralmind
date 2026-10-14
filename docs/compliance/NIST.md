# NIST and NeuralMind: what applies, where it stands, what's next

**Date:** 2026-10-11
**Version:** 1.0

---

## 1. There is no "NIST certification" for software

NIST publishes standards and frameworks. Other parties assess against them.
The one NIST program that certifies a product is the Cryptographic Module
Validation Program (FIPS 140-3), and it certifies cryptographic modules, not
applications. Which NIST documents matter for NeuralMind depends on who is
buying it and what they will run it on:

| If you are… | You will be asked about… |
|---|---|
| A US federal agency buying software | NIST SP 800-218 (SSDF), through CISA's Secure Software Development Attestation Form, which the producer signs |
| A defense contractor handling CUI | NIST SP 800-171 (CMMC Level 2), assessed against *your* environment, with NeuralMind inside its scope |
| An agency installing NeuralMind inside an authorized system | NIST SP 800-53 controls in *your* authorization (ATO). FedRAMP doesn't apply, because NeuralMind is local software with no hosted service |
| Anyone running FIPS-mode hosts | FIPS 140-3, for the host's own cryptographic modules |
| Anyone governing AI use | The NIST AI RMF, which is voluntary and has no certification |

## 2. Where NeuralMind stands

| Framework | Status | Evidence |
|---|---|---|
| **FIPS 140-3** | NeuralMind contains no cryptographic module of its own to validate. Data at rest is protected by the host's validated modules (full-disk encryption, the OS FIPS mode). *(v4.13.0+)* Its own hash calls work with the OS FIPS mode on, and CI runs the test suite with the OpenSSL FIPS provider enforced. *(v4.16.0+)* Audit checkpoints are signed with ECDSA P-256 through the `cryptography` package, which calls OpenSSL. The prebuilt `cryptography` wheel bundles its own OpenSSL, which is not FIPS-validated; on a FIPS host, rebuild it against the system OpenSSL (`pip install --force-reinstall --no-cache-dir --no-binary cryptography cryptography`; without `--force-reinstall`, pip keeps the wheel NeuralMind already installed) and confirm the host's OpenSSL uses its validated FIPS provider, so the signing runs in the host's validated module | [SECURITY-GUIDE: Requiring encrypted storage](../SECURITY-GUIDE.md#requiring-encrypted-storage) |
| **SP 800-218 (SSDF)** | *(v4.14.0+)* Container images are signed (cosign, keyless), and the image, wheel and sdist carry build-provenance attestations. CI scans with CodeQL, bandit and pip-audit on every change, and a VEX document publishes the dependency advisories that don't apply. Every practice is mapped to its evidence | [SSDF.md](SSDF.md) |
| **SP 800-171 / CMMC Level 2** | Practice-by-practice mapping, with what NeuralMind provides and what stays yours. In place today: OS-bound identity and roles (`security.identity: os`), a refusal to run without full-disk encryption (`security.require_encrypted_storage`), and a hash-chained audit log. *(v4.16.0+)* `security.profile: cui` turns these on as one unit, refuses to serve the project beyond loopback or without its token (SC.L2-3.13.8), refuses LLM documentation seeding, audits each refusal, and is checked as a unit by `neuralmind doctor`, which fails when the OS FIPS mode is off. It also adds signed, anchored audit checkpoints, which detect removal of the newest records and a recomputed chain (AU.L2-3.3.8) | [Compliance Summary: CMMC 2.0](../COMPLIANCE-SUMMARY.md#cmmc-20--practice-evidence) · [CUI enclave walkthrough](../use-cases/cmmc-cui-enclave.md) |
| **SP 800-53** | No control mapping published yet. Section 3 says what's planned | — |
| **AI RMF** | Evidence for each function (Govern, Map, Measure, Manage) | [Compliance Summary: NIST AI RMF](../COMPLIANCE-SUMMARY.md#nist-ai-rmf-ai-risk-management-framework--full-coverage) |

## 3. What's next

The work is done in this order, one release at a time. Items move to section 2
when they ship.

**SP 800-171 / CMMC hardening**

- **Live audit forwarding.** Today the log is exported to a SIEM after the
  fact. The plan is to forward it live over syslog, and to alert when audit
  logging fails (AU.L2-3.3.4, 3.3.5).

**SP 800-53**

- **An OSCAL component definition.** This is a machine-readable statement of
  how NeuralMind implements each relevant control, with a customer
  responsibility matrix, so an agency can drop it into its authorization
  package.
- **A hardening guide** with settings that can be checked automatically.

## 4. What stays yours

NeuralMind runs inside your environment, so most controls are met by that
environment, not by the tool:

- the OS FIPS mode and FIPS-validated full-disk encryption on the host;
- OS accounts and their authentication;
- audit retention and forwarding to your SIEM;
- **your coding agent's model provider.** NeuralMind hands code slices to the
  agent, and the agent sends them to its model. If that code is CUI, the
  provider must meet DFARS 252.204-7012 (FedRAMP Moderate or equivalent).
  NeuralMind reduces how much code goes out; it can't make a provider
  eligible.

Each table in the [Compliance Summary](../COMPLIANCE-SUMMARY.md) has a "Still
yours" column with the details.
