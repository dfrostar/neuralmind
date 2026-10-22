# Verify a NeuralMind release before installing it

> Goal: before a NeuralMind wheel or container image goes onto a developer
> machine, a build agent or an enclave, check that the release's own GitHub
> workflow built it from this repository, and know what is inside it.

**Who this is for:** security reviewers, platform teams that mirror packages
internally, and anyone who has to answer the supply-chain questions in a
vendor review: who built it, from what, with what dependencies, and which
advisories apply. [neuralmind.uk/security](https://neuralmind.uk/security/#verify)
gives these commands with the latest release filled in. This page explains each
one: what it proves, what it doesn't, and what a failure looks like.

**What you can verify:** every release from **v4.14.0** on. Earlier releases
were not signed and have no attestation to check.

Set the version once. The examples use v4.20.0:

```bash
V=4.20.0
```

You need [`cosign`](https://docs.sigstore.dev/cosign/system_config/installation/)
for the container image and the [GitHub CLI](https://cli.github.com/) (`gh`,
logged in to any account) for attestations. Neither needs access to anything
beyond the public repository.

---

## 1. The container image: signed by the release workflow

```bash
cosign verify ghcr.io/dfrostar/neuralmind:v$V \
  --certificate-identity-regexp '^https://github\.com/dfrostar/neuralmind/\.github/workflows/docker-publish\.yml@refs/(heads/main|tags/v[0-9]+\.[0-9]+\.[0-9]+)$' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com
```

**What it proves:** the image digest the tag points to was signed, keyless, by
`docker-publish.yml` in `dfrostar/neuralmind`, running from `main` or a version
tag. The signature is recorded in Sigstore's public transparency log. Signing
uses no long-lived key that could leak. Each signature is bound to the identity
of the workflow run that made it.

**Why the long pattern:** it pins both the workflow file and the git ref it ran
from. A signature made by the same workflow on any other branch, such as a pull
request or a fork, fails it. Checking only the repository would accept that
signature.

**On failure** `cosign` prints `no matching signatures` and exits non-zero. Don't
pull the image. If you mirror images, verify by digest and mirror that digest.
A tag can be moved; the digest you verified can't.

## 2. The image's build provenance

```bash
gh attestation verify oci://ghcr.io/dfrostar/neuralmind:v$V --repo dfrostar/neuralmind \
  --cert-identity-regex '^https://github\.com/dfrostar/neuralmind/\.github/workflows/docker-publish\.yml@refs/(heads/main|tags/v[0-9]+\.[0-9]+\.[0-9]+)$'
```

**What it proves:** a signed SLSA build-provenance statement for this image
names the workflow, the commit and the runner that built it. Add
`--format json` to keep it as evidence. The commit it names is the source the
image was built from.

The release workflow runs steps 1 and 2 against every image it publishes, and
stops before `:latest` moves if either fails. You are re-running a check the
release already passed, on your own machine and against what you actually
pulled.

## 3. The wheel or sdist from PyPI

```bash
pip download --no-deps neuralmind==$V -d dist/
gh attestation verify dist/neuralmind-$V-py3-none-any.whl --repo dfrostar/neuralmind \
  --cert-identity-regex '^https://github\.com/dfrostar/neuralmind/\.github/workflows/release\.yml@refs/(heads/main|tags/v[0-9]+\.[0-9]+\.[0-9]+)$'
```

**What it proves:** the file you downloaded is byte-for-byte the one
`release.yml` built, because the attestation is over its SHA-256. The sdist
(`neuralmind-$V.tar.gz`, from `pip download --no-binary :all: --no-deps`) has
its own attestation and is checked the same way. PyPI also holds the PEP 740
attestations that trusted publishing uploads.

**Install what you verified:**

```bash
pip install --no-deps dist/neuralmind-$V-py3-none-any.whl
```

Use `--no-deps` only if you install the dependencies separately (for example
from your own mirror). Otherwise drop it. pip then resolves the dependencies
from your index, and they are covered by step 4, not by NeuralMind's
attestation.

## 4. What's inside: the SBOM

Every release since v4.0.0 has a CycloneDX SBOM. Releases on this repository
are immutable, so the SBOM can't be attached to them after they are published.
It is served from the site instead:

```bash
curl -fsSLO https://neuralmind.uk/sbom/neuralmind-v$V.sbom.json
```

It lists `neuralmind` itself and every package a default install brings in,
with versions and package URLs. Opt-in extras such as `chromadb` aren't in it.
Load it into the tool you already use (Dependency-Track, Grype, Trivy), or scan
it directly:

```bash
grype sbom:neuralmind-v$V.sbom.json
# or
trivy sbom neuralmind-v$V.sbom.json
```

**What it doesn't prove:** an SBOM says what a release depends on. Steps 1 to 3
are what show you have that release.

## 5. Which advisories don't apply: the VEX

[`security/neuralmind.openvex.json`](https://github.com/dfrostar/neuralmind/blob/main/security/neuralmind.openvex.json)
is an OpenVEX document. It lists the advisories in NeuralMind's dependencies
that NeuralMind is not affected by, each with the reason. Today those are four
ChromaDB advisories: ChromaDB is an opt-in extra, and NeuralMind uses only its
local, on-disk `PersistentClient`. It never starts ChromaDB's server.

They matter when you scan an environment that has the `chromadb` extra
installed. Pass the VEX with the scan, and those advisories show as not
affected, with the reason, instead of open:

```bash
curl -fsSLO https://raw.githubusercontent.com/dfrostar/neuralmind/main/security/neuralmind.openvex.json
grype dir:/path/to/venv --vex neuralmind.openvex.json
# or
trivy fs /path/to/venv --vex neuralmind.openvex.json
```

The VEX is a living statement, so it is read from `main`, not from a release
tag. Three checks keep it honest. CI's `pip-audit` ignores exactly the
advisories it lists, so any other advisory fails the build. A test fails if an
entry has no argument in [`SECURITY.md`](https://github.com/dfrostar/neuralmind/blob/main/SECURITY.md).
And when ChromaDB ships a fix, a watch workflow opens an issue, and the
statement comes out of the VEX.

## 6. Put it on file

For a vendor review or a System Security Plan, keep:

| Evidence | From |
|---|---|
| `cosign verify` output (JSON) for the image digest you deployed | Step 1 |
| The provenance statement (`gh attestation verify … --format json`) | Steps 2 and 3 |
| The SBOM for that version | Step 4 |
| The VEX as of the date you assessed | Step 5 |
| The [SSDF mapping](../compliance/SSDF.md): every NIST SP 800-218 practice, mapped to the workflow, file or check that is its evidence | The repository |

The same commands are in [SSDF.md §2](../compliance/SSDF.md#2-how-to-verify-a-release-yourself).
If the release is going onto a machine with no network, verify it on the
connected side before it crosses: [Run NeuralMind air-gapped](./air-gapped.md).
For an enclave, continue with
[Use NeuralMind in a CMMC CUI enclave](./cmmc-cui-enclave.md), and run
`neuralmind hardening` on the host after installing.

## What this doesn't cover

- **Who wrote the code.** Provenance proves which workflow built a release and
  from which commit. It doesn't review that commit. The source is public, and
  CI runs CodeQL, bandit and pip-audit on every change; the
  [SSDF mapping](../compliance/SSDF.md) lists the checks.
- **Your dependencies' own builds.** Step 3 covers NeuralMind's wheel. The
  packages pip resolves next to it come from your index, under that index's
  controls.
- **What your agent sends to its model.** By default NeuralMind sends no
  telemetry and transmits no repository content off your machine. Your agent
  still sends the context it selects to its own model provider.
  [What goes over the network](https://neuralmind.uk/security/#network) lists
  everything NeuralMind can send.

## Related

- [neuralmind.uk/security](https://neuralmind.uk/security/): these commands for
  the latest release, the network list, and the controls a regulated deployment
  turns on
- [SSDF mapping](../compliance/SSDF.md) and [NIST overview](../compliance/NIST.md)
- [v4.14.0 release notes](../releases/RELEASE_NOTES_v4.14.0.md): when signing
  and attestations began
- [v4.20.0 release notes](../releases/RELEASE_NOTES_v4.20.0.md): `/security`
  now opens with this
