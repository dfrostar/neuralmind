# Next Session Prompt — NeuralMind Wave 4 (G3+G4 IMPLEMENTING, RELEASE BLOCKED)

**Date:** 2026-07-21
**Autopilot:** v0.7.0 (running — systemd service live)
**NeuralMind:** v1.4.0 (unreleased — tag push blocked by repo rules)
**Index:** rebuilt, fresh — 11,530 nodes / 593 communities

---

## Where We Are

G3 (Louvain modularity clustering) and G4 (incremental re-extraction) are **implemented and tested** but **not yet on PyPI**. Tag push blocked by repo rules — release-please PR #394 is the path forward.

---

## Recap: What Shipped (code complete, release blocked)

| Item | Commit | Tests | DeepSeek QA |
|------|--------|-------|-------------|
| G3 — Louvain modularity clustering | `f49b535` | 11 pass | CLEAN (0 CRITICAL, 3 WARNINGs patched) |
| G4 — Incremental re-extraction + dangling edge prune | `0a1feb8` | 12 pass | PENDING (deleg_dacce20f) |

**All targeted tests green:** 35 (G3) + 26 (G4) = 61 tests pass.

---

## Blockers (in priority order)

### 1. Tag push blocked by repo rules (CRITICAL)
- `git push origin v1.4.0` fails: "push declined due to repository rule violations"
- `gh release create v1.4.0` fails: "Cannot create ref due to creations being restricted"
- `RELEASE_PLEASE_TOKEN` secret not set in repo — only `GITHUB_TOKEN` available
- **Path:** Merge release-please PR #394 (v1.5.0 scan) once CI passes → triggers release.yml → tag auto-created by release-please action as `github-actions` actor

### 2. DeepSeek QA on G4 pending
- Subagent `deleg_dacce20f` running ~5-10 min
- When it returns: verify findings, patch if CRITICAL, push to main

### 3. Release-please manifest drift
- `release-please-manifest.json` at `{".":"1.4.0"}` (local) but remote still resolves from old scan
- PR #394 should resolve once CI passes

---

## Files to Read FIRST (if resuming)

1. `neuralmind/modularity.py` — G3 Louvain (already shipped, not to be re-patched unless DeepSeek G4 review flags new issues)
2. `neuralmind/incremental_extract.py` — G4 IncrementalExtractor + build_importer_index_from_graph()
3. `neuralmind/graphgen.py` — `build_graph()` + `_assign_communities()` wiring
4. `docs/research/f4-g3-research-backlog.md` — original research, known bugs, deferred items
5. `docs/specs/G3-{BRD,TRD,TEST-PLAN}.md` — governance docs (shipped)
6. `docs/specs/G4-{BRD,TRD,TEST-PLAN}.md` — governance docs (shipped)

---

## Key Decisions Made (Don't Reverse)

### G3 — Modularity
- Pure Python Louvain (stdlib-only, no Leiden/igraph dependency)
- O(n·k) Phase 1 via incremental community weight updates
- Resolution parameter γ applied in null-model term: `γ·Σ·k/(2m)`
- Phase 2 single-collapse (not full multilevel)
- Deterministic output via sorted node iteration, no `hash()` path
- Cluster ID carry-over from existing_graph for incremental stability
- Fail-open: collapse to per-file grouping if Louvain returns ≤1 community
- **DeepSeek fix (CRITICAL):** Removed `seen` dedup in Phase 2 coarse adjacency — was halving self-loop weights and corrupting modularity

### G4 — Incremental Re-extraction
- `IncrementalExtractor` tracks file mtime + SHA-256 content hashes
- `get_changed_with_dependents()` transitively invalidates importers via reverse-edge resolution
- `build_importer_index_from_graph()` inverts imports/calls/inherits edges
- Dangling edge prune: edges to non-existent nodes dropped in incremental path
- Persistence: `.neuralmind/extraction_cache.json` + `.neuralmind/importer_index.json`

### Conventions Honored
- Claim tiers: G3 and G4 both tier B (no overclaims)
- "What's NOT shipping" documented in TRD §8
- Public-facing copy staged first, applied AFTER DeepSeek QA cleared
- Triple-alignment: pyproject.toml + __init__.py + release-please-manifest.json

---

## Conventions (Honest, KISS/DRY, No Overclaim)

- **Claim tiers:** Every BRD/TRD claim classified A/B/C/D.
- **Honest framing:** Document what's NOT done yet.
- **Private repo discipline:** Autopilot stays private.
- **No phone-home:** All operations local.
- **Fresh verification:** Run `pytest` before claiming done.
- **After 'approved'/'go':** work is done — don't re-summarize.

---

## Parallelization Strategy (validated this session)

### What works
- DeepSeek QA on one module while the parent patches another
- Public-facing copy staged in parallel with test verification
- Doc audit dispatched in parallel with version bump

### What DOESN'T work (lessons learned)
- `pytest tests/` after every patch — hangs on CI-network tests. Targeted suites only.
- Re-running tests that already passed in the same turn — trust first green.
- Re-reading files just patched — wastes context window.
- Serial execution with narration — user preference violated.

---

## Versioning
- autopilot: v0.7.0 (running)
- neuralmind: v1.4.0 (committed, unreleased) → v1.5.0 (next target via release-please PR #394)

---

## Release Path Resolution

```
Current state:
  main has v1.4.0 code
  release-please-manifest.json: {".":"1.4.0"}
  git tag v1.4.0: exists locally, not on origin
  PyPI: empty (no tag → no publish trigger)

Resolution:
  1. Wait for release-please PR #394 CI to pass
  2. Merge PR #394 (triggers v1.5.0 release via conventional commits)
  3. CI creates tag v1.5.0 + publishes to PyPI + GHCR
  4. If DeepSeek G4 QA returns CRITICAL findings before merge: patch, amend commit, force-push to PR branch, re-run CI

Post-merge cleanup:
  - Verify PyPI: `curl -s https://pypi.org/pypi/neuralmind/json | python3 -c "import json,sys; print(json.load(sys.stdin)['info']['version'])"`
  - Verify GitHub Release: `gh release list --limit 3`
  - Verify GHCR: `gh api repos/dfrostar/neuralmind/packages/container/neuralmind/versions`
  - Reindex local hermes: `cd /home/dtfrost/neuralmind && neuralmind build --force`
```

---

## Skills to Load (in priority order)

1. `neuralmind-release` — release workflow (updated with waste patterns + tag push recovery)
2. `neuralmind-graphgen` — community assignment + G4 wiring pitfalls (updated)
3. `neuralmind-modularity` — Louvain API + pitfalls (new, G3)
4. `deepseek-qa` — phase-gate QA dispatch (updated with re-dispatch rules)
5. `git-workflow` — GitHub operations (token verification)
6. `git-repo-cleanup` — pre-release hygiene

---

## Next Actions (when session resumes)

1. Check `deleg_dacce20f` DeepSeek QA result on G4
2. Patch any CRITICAL findings + verify tests
3. Wait for PR #394 CI to complete
4. Merge PR #394 → triggers v1.5.0 release
5. Verify PyPI publish + GitHub Release + GHCR
6. Update CHANGELOG.md with v1.5.0 G3/G4 entries

---

*Next session prompt v1.0. G3+G4 implemented, release blocked on repo rules. Release-please PR #394 the path forward.*
