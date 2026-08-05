# Release Notes — v3.0.1 (August 2026)

**Tag:** v3.0.1 | **Published:** 2026-08-03

---

## TL;DR

v3.0.1 is a maintenance release that republishes the SBOM for v3.0.0 (the
original release was missing the `.sbom.json` attachment), refreshes the
benchmark chart on the marketing site, fixes a seat-management deadlock in CI,
and starts the dashboard rebrand from "Agent OS" to "NeuralMind".

---

## What's Fixed

### SBOM Republish

The v3.0.0 release was missing the CycloneDX SBOM attachment. This release
republishes it as `neuralmind-v3.0.0.sbom.json` on the GitHub release page
and commits a copy to `site/public/sbom/` for the security page to link to.

### Benchmark Chart Refresh

The marketing site benchmark chart (`docs/benchmarks/`) was showing stale data
from v1.x. Refreshed to reflect current 12-50× measurements against realistic
baselines.

### Seat Management Deadlock Fix

`neuralmind/tier2/seats.py` used a non-reentrant `threading.Lock` in
`add_seat()`. Under concurrent CI test runs this caused deadlocks and CI
timeouts. Fixed by switching to `threading.RLock`.

### Dashboard Rebrand (partial)

Started removing "Agent/Agency OS" references from the public dashboard,
ROADMAP, and tests. The full rebrand completes in v3.0.2.

---

## Verification

```bash
# 1. Verify SBOM exists on release
curl -sL https://github.com/dfrostar/neuralmind/releases/download/v3.0.0/neuralmind-v3.0.0.sbom.json | head -5

# 2. Verify SBOM served from site
curl -sL https://neuralmind.uk/sbom/neuralmind-v3.0.0.sbom.json | head -5

# 3. Run tier2 tests (seats deadlock fix)
pytest tests/test_tier2.py -q -k seat
```

## Behaviour Changes

| Change | Impact |
|--------|--------|
| SBOM republish | Security page now links to a valid SBOM download |
| Benchmark chart refresh | Marketing site shows current 12-50× data |
| Seat RLock fix | CI no longer deadlocks under concurrent seat ops |

## Migration

```bash
pip install --upgrade neuralmind
```

No breaking changes. Upgrade is optional — only affects SBOM availability
and CI stability.

## What's Next

- **v3.0.2** — Complete dashboard rebrand, extract Agent OS to private repo
- **v3.1.0** — Synapse layer activation (reinforce on every query)
