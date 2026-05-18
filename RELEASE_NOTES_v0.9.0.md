# NeuralMind v0.9.0 — enterprise-ready

**Release Date:** May 2026

## TL;DR

Phase 3 of the release arc — turn the v0.6.0 → v0.7.0 → v0.8.0
foundation into something a CTO, security team, or regulated-industry
operator can actually adopt.

What ships:

- **GHCR auto-build.** Every tagged release publishes
  `ghcr.io/dfrostar/neuralmind:vX.Y.Z` and `:latest`, multi-platform
  (linux/amd64 + linux/arm64), non-root runtime, transitive deps
  pre-wheeled.
- **SBOM** (CycloneDX JSON) attached to every release as
  `neuralmind-vX.Y.Z.sbom.json` — auditable supply chain for
  Grype/Trivy/Dependency-Track/etc.
- **Air-gapped install walkthrough** (`docs/use-cases/air-gapped.md`)
  — bundle-and-sneakernet pattern for environments with no outbound
  network at install time.
- **Compliance one-pager** (`docs/COMPLIANCE-SUMMARY.md`) — NIST AI
  RMF + SOC 2 + GDPR claims consolidated into one reviewable surface
  for procurement.

No code changes in this release. Pure CI + docs.

No migration. Same `graph.json`, same `synapses.db`, same hooks. New
files are additive.

> Note on cross-doc rollout: the marketing artifacts (LinkedIn drafts,
> NotebookLM v0.9 pack, screencast script, About-page + wiki Home
> callouts, Hacker News submission) are deferred to a follow-up pass.
> This release is the CI infrastructure + docs. Frame the marketing
> arc once the pieces have proven out (first GHCR pull, first external
> SBOM ingestion, first compliance review).

## What's new

### GHCR auto-build

`.github/workflows/docker-publish.yml` builds and pushes the repo-root
`Dockerfile` to the GitHub Container Registry on every `v*` tag push.

- **Tags:** `ghcr.io/dfrostar/neuralmind:vX.Y.Z` and `:latest`
- **Platforms:** `linux/amd64` and `linux/arm64` via buildx + QEMU
- **Auth:** `GITHUB_TOKEN` with `packages: write` — no separate
  registry credentials required
- **OCI labels:** `source`, `version`, `licenses=MIT`,
  `title`/`description`
- **Cache:** GitHub Actions cache (`type=gha`, `mode=max`) so
  subsequent releases reuse the transitive-wheel pre-download layer

A `verify-pull` job pulls the published image and runs `neuralmind
--help` inside it as a sanity check before declaring success.

### SBOM publication

`.github/workflows/sbom.yml` generates a CycloneDX JSON SBOM via
Anchore's `sbom-action` (syft) and attaches it to the GitHub Release.

- **Format:** CycloneDX 1.x JSON — what most enterprise SCA scanners
  ingest
- **Scope:** the active Python environment after `pip install .`, so
  every transitive dep is captured with version + license
- **Asset name:** `neuralmind-vX.Y.Z.sbom.json` on the release page
- **Fallback:** if the release upload fails (immutable release), the
  SBOM is preserved as a 90-day workflow artifact

### Air-gapped install walkthrough

New page at `docs/use-cases/air-gapped.md` — the strictest deployment
posture NeuralMind supports.

Covers the two install-time network dependencies that have always
been the "but does it work behind a firewall" question:

1. **PyPI bundle** — `pip download neuralmind graphifyy --dest ...`
   on a connected machine, transfer the wheel set, install with
   `--no-index --find-links` on the air-gapped machine. Documented
   platform-tag selection so the wheels match the target.
2. **ChromaDB embedding model** — pre-cache the ONNX model
   (`~/.cache/chroma/onnx_models/`) on the connected machine and
   transfer alongside the wheel bundle.

End-to-end Docker variant included — `docker save` + sneakernet works
the same way thanks to the v0.7.0 multi-stage Dockerfile that
pre-wheels all transitive deps in the builder stage.

### Compliance one-pager

New `docs/COMPLIANCE-SUMMARY.md` — one-page reference for
procurement, security review, and compliance teams.

Consolidates claims previously scattered across `SECURITY-GUIDE.md`
and `ENTERPRISE.md`:

- **NIST AI RMF** — full coverage of GOVERN / MAP / MEASURE / MANAGE
  with line-item evidence
- **SOC 2 Type II** — CC6.1, CC7.1, CC7.2, A1.1, C1.2, P3.1/4.1 with
  evidence pointers
- **GDPR** — data minimisation, storage limitation, right to erasure,
  no controller/processor split (operator is the sole controller),
  no breach surface
- **Verification table** — every claim has a "how to verify yourself"
  command, so the doc isn't asking the reader to take our word

## Deferred

- **Cross-doc marketing rollout.** README hero callout, wiki Home
  "What's New" entry, GitHub Pages updates, LinkedIn drafts, NotebookLM
  v0.9 pack, screencast script, Hacker News submission — all deferred
  to a follow-up so this release ships infrastructure + docs.

## Behaviour controls (unchanged)

| Env var | Default | Effect |
|---|---|---|
| `NEURALMIND_EVENT_LOG` | `1` | `0` disables the cross-process JSONL bridge. |
| `NEURALMIND_BYPASS` | unset | `1` skips PostToolUse compression. |
| `NEURALMIND_SYNAPSE_INJECT` | `1` | `0` skips prompt-time synapse recall. |
| `NEURALMIND_SYNAPSE_EXPORT` | `1` | `0` skips memory export to Claude Code's auto-memory. |

## Verification

```bash
# Pull the GHCR image (works as soon as the v0.9.0 tag publishes)
docker pull ghcr.io/dfrostar/neuralmind:v0.9.0
docker run --rm ghcr.io/dfrostar/neuralmind:v0.9.0 neuralmind --help

# Verify the SBOM
curl -fsSL https://github.com/dfrostar/neuralmind/releases/download/v0.9.0/neuralmind-v0.9.0.sbom.json \
  | jq '.metadata.component.name, .metadata.component.version, (.components | length)'
# "neuralmind"
# "0.9.0"
# <number of transitive deps>
```

End-to-end air-gapped flow: see [`docs/use-cases/air-gapped.md`](docs/use-cases/air-gapped.md).

## What's next

- **v0.9.1+** — marketing rollout for v0.9 (LinkedIn for CTOs/security,
  NotebookLM, screencast, README + wiki + Pages callouts, optional HN
  submission).
- **v1.0.0** candidates — pinned Discussions thread for
  regulated-industry deployment Q&A, optional cosign image signing,
  optional GitHub App for release automation (per the long-term
  variant of #98).

## Thanks

The v0.7.0 install matrix + v0.8.0 always-on foundation are what
makes this release credible. A "containerized + SBOM + air-gapped"
story only lands if the user already trusts that `pip install
neuralmind` actually works for them. Distribution earned the
compliance pitch, not the other way around.
