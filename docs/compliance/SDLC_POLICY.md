# SDLC Policy

**Date:** 2026-07-27
**Version:** 1.0
**SOC 2 Controls:** CC3.1, CC8.1, A1.1

---

## 1. Purpose

Define the software development lifecycle for NeuralMind, ensuring changes are built, tested, and deployed with integrity.

## 2. SDLC Phases

### 2.1 Planning

Every feature starts with:
- **BRD** (Business Requirements Document) — problem, success criteria
- **TRD** (Technical Requirements Document) — architecture, data model
- **Test Plan** — what to test, how, acceptance criteria

Documents are committed to `docs/specs/<feature>/` before implementation.

### 2.2 Implementation

1. Create feature branch from `main`
2. Write code following project conventions (CLAUDE.md)
3. Write tests alongside code
4. Document with inline comments and docstrings

### 2.3 Testing

All changes must pass:
- **Unit tests:** `pytest tests/` (targeted suites, not full 1582)
- **Type checks:** `mypy neuralmind/` (where configured)
- **Lint:** `ruff check neuralmind/`
- **Benchmarks:** `neuralmind benchmark .` (for retrieval changes)

### 2.4 Review

- Author reviews own diff
- CI validates linting, tests, benchmarks
- No merge if any CI check fails

### 2.5 Deployment

- Push to `main` triggers CI
- Tag push (`vX.Y.Z`) triggers PyPI + GHCR publish
- Cloudflare Pages deploys on `site/**` changes

### 2.6 Monitoring

- GitHub Actions dashboard for CI health
- Vanta for compliance monitoring
- Dependabot for dependency vulnerabilities
- Manual review of benchmark trends

## 3. Quality Gates

| Gate | Criteria | Blocking |
|------|----------|----------|
| Pre-commit | No `print()` in production, no `TODO` in shipped code | No |
| Pre-merge | All CI checks pass | Yes |
| Pre-release | Benchmark ratio ≥ 3.5× floor | Yes |
| Post-deploy | `/healthz` returns 200 | No |

## 4. Documentation Standards

Every feature ships with:
- BRD (`docs/specs/<feature>/<date>-BRD.md`)
- TRD (`docs/specs/<feature>/<date>-TRD.md`)
- Test Plan (`docs/specs/<feature>/<date>-TEST-PLAN.md`)
- Test Results (in same directory, after execution)
- Release Notes (`RELEASE_NOTES_vX.Y.Z.md`)

All documents are dated and versioned.

## 5. Versioning

NeuralMind follows semantic versioning:
- **Patch (Z+1):** Bug fixes, no API changes
- **Minor (Y+1):** New features, backward-compatible
- **Major (X+1):** Breaking changes

Version bump is automated via release-please on `feat:` / `fix:` commits.

---

*This policy is reviewed annually. Last reviewed: 2026-07-27.*
