# NeuralMind v3.10.0 — the v3.9.0 retrieval correction, and a public benchmark page

**Release Date:** 2026-09-10

## Summary

Two threads: the faithfulness-gate regression that v3.9.0's adversarial
retrieval work introduced (found after release, root-caused, and fixed
here — see the correction note in
[`RELEASE_NOTES_v3.9.0.md`](RELEASE_NOTES_v3.9.0.md)), and a first-class
public benchmark page on the marketing site plus SEO/indexability work.

## Retrieval: v3.9.0's adversarial-retrieval pull-in made opt-in

v3.9.0 shipped three retrieval "fixes" (synapse-seeded expansion,
dependency-graph traversal, code-snippet extraction) that pulled extra
candidate nodes into the L3 context slice. Measured after release: on the
faithfulness fixture, appending those candidates moved the delta from
`+0.041` to `-0.065` against a `+0.000` gate floor — worse, not better.
Making the pull-in budget-neutral (displacing a hit instead of appending)
made it worse still (`-0.107`), because displacement evicts a real hit per
candidate, and a candidate worse than what it replaces costs facts, not
just tokens.

- Restored the faithfulness gate as blocking, and gated the v3.9.0 pull-in
  behind `NEURALMIND_RETRIEVAL_EXPANSION` (default off — see
  [CLI Reference](../wiki/CLI-Reference.md#environment-variables)). Intent
  classification and the code-signal boost, the other two v3.9.0 changes,
  are unaffected and stay on by default — they re-rank existing hits
  rather than adding to them, and measured bit-for-bit neutral.
- Reset learned synapse state between faithfulness samples, and averaged
  the gate over 3 samples to absorb HNSW-index jitter — the earlier
  single-sample gate was measuring noise as often as signal.
- Ranked the merged L3 slice before flattening it, so an expansion
  candidate has to actually outrank what it would replace rather than
  being appended regardless of score.
- **docs:** corrected faithfulness figures that had been computed on a
  fixture that included its own answers — i.e., training on themselves.

## Site

- **Public benchmark page** — the benchmark NeuralMind runs against itself
  is now a first-class page on the marketing site rather than only a
  results file in the repo.
- Fixed six pages that were canonicalizing to the homepage instead of
  themselves, and moved FAQ answers into the actual page HTML (they were
  previously JS-rendered only, invisible to a crawler that doesn't execute
  JS).
- Added a 2026 SEO plan with a live indexability audit, and a comparison
  page against Graft and codebase-memory-mcp.
- Synced the Agent Zero / a0-plugins ecosystem listing status now that the
  a0-plugins registry submission (staged in v3.6.0) has actually merged,
  and documented both live registries.

## Release tooling

- Repaired a release-please baseline drift and added a guard against
  orphaned release tags / manifest drift, after a version-manifest
  mismatch surfaced the gap. Added a ClawHub publish script.

## What the agent sees post-install

`NEURALMIND_RETRIEVAL_EXPANSION=1` opts back into the v3.9.0 pull-in
behavior if you want it — it is a research setting, not a recommended
default; see the correction note in
[`RELEASE_NOTES_v3.9.0.md`](RELEASE_NOTES_v3.9.0.md) for the measured
tradeoff. No other agent-visible behavior changed; the site/SEO work has
no effect on the installed package.

## Upgrading

```bash
pip install --upgrade neuralmind
```

If you had set `NEURALMIND_RETRIEVAL_EXPANSION` or relied on the v3.9.0
pull-in behavior being on by default, it is now off by default — set
`NEURALMIND_RETRIEVAL_EXPANSION=1` explicitly to keep it.
