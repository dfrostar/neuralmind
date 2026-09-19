# NeuralMind v3.5.1 — dependency security floors raised, 20 advisories cleared

**Release Date:** 2026-08-27

## Summary

A dependency-security patch: pinned floors were raised across the
transitive dependency tree to clear 20 outstanding advisories, and a
vulnerability management policy was added documenting how NeuralMind
tracks and responds to dependency CVEs going forward. No functional
changes to NeuralMind's own code.

## Changes

- **deps:** raised minimum versions across the dependency tree to clear 20
  dependency-scanner advisories. See the SBOM attached to this release
  (`neuralmind-v3.5.1.sbom.json`) for the resulting version graph.
- **security:** added a vulnerability management policy describing the
  cadence and process for dependency-advisory triage (see
  [`docs/compliance/`](../compliance/) for the current compliance document
  set).
- **site:** the social preview card generation was made reproducible from
  source and gated behind the same claims-accuracy check that guards the
  rest of the marketing site's copy.

## What the agent sees post-install

No agent-visible behavior changed. This release only tightens dependency
floors and adds process documentation.

## Upgrading

```bash
pip install --upgrade neuralmind
```

Upgrading picks up the raised dependency floors automatically. If your
environment pins transitive dependencies independently (a lockfile, a
vendored requirements set), re-resolve against the new floors to actually
clear the advisories.
