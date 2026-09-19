# NeuralMind v3.6.0 — listed on the a0-plugins registry

**Release Date:** 2026-08-28

## Summary

NeuralMind's plugin manifest was staged for Agent Zero's `a0-plugins`
registry, prevalidated against that registry's own CI before submission.
Alongside it, two hardening fixes: a loud failure mode for a detached-host
edge case, and a correction to an unsourced performance figure that had
crept into the plugin manifest itself.

## What's new

- **ecosystem:** added `plugin.yaml` at the repo root (Agent Zero's
  `a0-plugins` manifest format) and staged the registry submission,
  prevalidated against the a0-plugins CI so the submission doesn't fail on
  format issues after the fact.

## Fixes

- **claims:** `plugin.yaml`'s description had accumulated an unsourced
  "12-70x" figure — outside the sourced, `site/claims.json`-backed 12-50×
  range this repo's own claims-guard enforces everywhere else. Corrected
  to the sourced range, and registry manifests are now gated by the same
  claims check so this class of drift can't recur in a file the site's own
  test suite doesn't scan.
- Added a loud failure (rather than a silent fallback) when NeuralMind
  detects it's running with a detached host path, and made benchmark
  embeddings deterministic so benchmark runs are reproducible run-to-run.

## What the agent sees post-install

No new CLI commands, hooks, or env vars. If you discover NeuralMind
through Agent Zero's plugin registry rather than PyPI directly, the
listing you land on now carries the same figures as every other surface —
see `site/claims.json` for what's measured and how to reproduce it.
