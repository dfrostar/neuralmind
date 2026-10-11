# NeuralMind v4.14.0 — signed images, attested builds, and the evidence for a NIST SSDF attestation

**Type:** Minor release | **Theme:** you can check that the NeuralMind you install is the one this repository built, and a federal buyer's assessor can check how it was built

NIST doesn't certify software against its Secure Software Development
Framework (SP 800-218). A US federal agency buying software asks the producer
to attest to it on CISA's Secure Software Development Attestation Form, signed
by an officer of the company. Until now the repository was missing parts of
the evidence behind that signature. Releases weren't signed or attested,
nothing scanned the code or the installed dependencies on each change, and the
"not affected" decisions on dependency advisories existed only as prose in
SECURITY.md.

---

## What changed

### Releases you can verify

- **Container images are signed.** Each `ghcr.io/dfrostar/neuralmind` image is
  signed with cosign by the release workflow. The signing is keyless: the
  signature is bound to the workflow's GitHub OIDC identity and recorded in
  Sigstore's public transparency log, so there's no signing key to hold or
  leak.
- **Every artifact carries build provenance.** The image, the wheel and the
  sdist get GitHub build-provenance attestations naming the workflow, commit
  and runner that built them. PyPI already received PEP 740 attestations from
  trusted publishing.
- **The release checks itself.** Before `:latest` moves, the release workflow
  runs the same `cosign verify` and `gh attestation verify` commands it
  documents. An image that doesn't verify never becomes the default pull.

### Scanning on every change

- **bandit** runs on the package. High severity fails the change, and the full
  report goes to the repository's code scanning alongside CodeQL. The one
  high-severity exception is the SHA-256-pinned model archive's extraction,
  marked `# nosec B202` with its reason.
- **pip-audit** audits what users install, meaning the default install plus
  the `chromadb` extra, in its own environment. Any advisory fails the change
  unless the VEX document below marks it not affected.

### Dependency decisions as data (VEX)

- **`security/neuralmind.openvex.json`** records, in OpenVEX, the four
  ChromaDB advisories SECURITY.md has argued are unreachable. ChromaDB is an
  opt-in extra, and NeuralMind uses only its local `PersistentClient`. Give it
  to a VEX-aware scanner (Grype or Trivy `--vex`) with the release SBOM, and
  those advisories show as not affected rather than open.
- The CI gate ignores exactly what the VEX lists (`scripts/vex_ignores.py`),
  so the published decision and the gate can't disagree.
  `tests/test_vex.py` fails if an entry isn't argued in SECURITY.md or drifts
  from the advisories `chromadb-cve-watch.yml` watches.

### The SSDF mapping

- **[`docs/compliance/SSDF.md`](../compliance/SSDF.md)** maps every SP 800-218
  practice (PO, PS, PW, RV) to the evidence in the repository. It also says
  which parts a repository can't show, such as account 2FA and repository
  settings, which the attesting officer confirms directly.

## What the agent actually sees

Nothing changes. No hook, MCP tool, response field, command or default
changed. This release changes how NeuralMind is built and published, not how
it runs.

## Per-agent expectations

| Agent | What changes |
|---|---|
| Claude Code (hooks + MCP) | Nothing at runtime |
| Cursor / Cline / Continue (MCP) | Nothing at runtime |
| Hermes-Agent plugin | Nothing at runtime |
| Generic MCP client | Nothing at runtime |

## Upgrading

- No action needed, and no index format change.
- To verify what you installed, see
  [SSDF.md §2](../compliance/SSDF.md#2-how-to-verify-a-release-yourself).
  Releases before v4.14.0 have no signature or attestations to verify.
- Air-gapped installs can verify the wheel's provenance on the connected
  machine before transfer; see the
  [air-gapped walkthrough](../use-cases/air-gapped.md).

## Reproduce

```bash
pytest tests/test_vex.py -v

# The CI gates, locally
pip install bandit pip-audit
bandit -q -r neuralmind --severity-level high
python -m venv /tmp/audit && /tmp/audit/bin/pip install -e ".[chromadb]"
PIPAPI_PYTHON_LOCATION=/tmp/audit/bin/python \
  pip-audit --skip-editable $(python scripts/vex_ignores.py)

# A published image (v4.14.0 and later)
cosign verify ghcr.io/dfrostar/neuralmind:v4.14.0 \
  --certificate-identity-regexp '^https://github\.com/dfrostar/neuralmind/\.github/workflows/docker-publish\.yml@' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com
gh attestation verify oci://ghcr.io/dfrostar/neuralmind:v4.14.0 --repo dfrostar/neuralmind
```

## Related

- [Secure Software Development (SSDF) evidence](../compliance/SSDF.md)
- [Compliance Summary](../COMPLIANCE-SUMMARY.md)
- [Vulnerability Management Policy](../VULNERABILITY-MANAGEMENT-POLICY.md)
- [SECURITY.md — Verifying a Release](../../SECURITY.md#verifying-a-release)
