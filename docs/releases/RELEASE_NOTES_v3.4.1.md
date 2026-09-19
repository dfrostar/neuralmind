# NeuralMind v3.4.1 — a compliance annotation that couldn't be mistaken for evidence

**Release Date:** 2026-08-24

## Summary

A patch release fixing two issues found in the SOC 2 annotation scanner and
the turbovec backend's index rebuild path. No new commands, hooks, or env
vars.

## Changes

- **compliance:** the scanner's example opt-out markers (used to demonstrate
  how a false-positive control match can be annotated and excluded) could
  themselves be mistaken for real evidence of a control being met if
  copy-pasted without context. The fix keeps the annotation mechanism but
  makes clear, in the CLI reference and in the marker format itself, that an
  annotation records "not applicable," never "implemented."
- **turbovec:** the backend rebuilt its vector index from the in-memory
  graph object, not from the persisted node store — so a rebuild after a
  process restart (which repopulates the graph from disk) could silently
  index a stale or partial node set. It now rebuilds from the node store
  directly.
- **docs:** the CLI reference now documents the example opt-out markers
  referenced above.

## What the agent sees post-install

No agent-visible behavior changed — both fixes are internal correctness
fixes (a documentation clarity fix and an index-rebuild-source fix), not new
surface area.

## Upgrading

```bash
pip install --upgrade neuralmind
```

If you rely on `turbovec --rebuild` after process restarts, upgrading picks
up the node-store-sourced rebuild automatically; no action needed.
