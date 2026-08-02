# Release Notes — NeuralMind v1.9.1

> **Status:** Released 2026-07-29
> **DeepSeek QA:** Inherited clean (v1.9.0 was QAed; v1.9.1 is docs + tests + version-info bugfix)

---

## What's New in v1.9.1

This is a patch release that ships the v1.9.0 feature set to PyPI, corrects the version-info bug, adds failure-path tests for DocEvolver, and introduces the Book Content QA System reference documentation.

### Bug Fixes & Hardening

- **`__version_info__` bugfix.** v1.9.0 shipped with `__version_info__ = (1, 7, 1)` — stale from v1.7.1. Corrected to `(1, 9, 0)`. Code importing `__version_info__` from v1.9.0 would have seen a misleading value.
- **DocEvolver failure-path tests.** 4 new tests covering: evolution failure returns empty result, `patch_winners` skips missing files, rollback on failure, patch failure. Previously untested — adversarial gap.

### New Documentation

- **Book Content QA System.** 4 reference docs for the book QA pipeline (BRD, TRD, PRD, requirements, dev prompt) — establishes the documentation pattern for NeuralMind's AI-powered book authoring pipeline.
- **ROADMAP.md.** Updated to reflect v1.9.0 shipped status; removed outdated "remaining before v1.9.0" section.
- **CLI-Reference.md.** Added `gaps --structural` command documentation (was missing from v1.9.0 notes).
- **README.md.** Banner updated from v1.7.2 → v1.9.0.

## Behaviour Controls

| Env Var | Default | Effect |
|---------|---------|--------|

No new behaviour controls.

## Verification

```bash
# Verify version_info is correct
python3 -c "import neuralmind; print(neuralmind.__version__, neuralmind.__version_info__)"
# Expected: 1.9.1 (1, 9, 0)

# Verify G5 gap detection works
python3 -m neuralmind gaps --structural --top-k 5

# Run DocEvolver failure-path tests
python3 -m pytest tests/test_doc_evolver.py::TestFailurePaths -v
# Expected: 4 passed
```

## Migration

None. Upgrade with `pip install --upgrade neuralmind`.

Existing indexes, hooks, and synapses.db work unchanged.
