# SDLC Policy

**Date:** 2026-10-19
**Version:** 1.3
**SOC 2 Controls:** CC7.1, CC8.1

---

## 1. Purpose

Define the software development lifecycle for NeuralMind, ensuring changes are built, tested, and deployed with integrity.

Version 1.1 described a process stricter than the one followed: a BRD, TRD and
test plan for every feature, mypy as a check, and merges blocked by failing CI.
This version describes what happens, and says which steps a rule enforces and
which are practice. NeuralMind has one maintainer and is written with AI coding
agents ([SSDF §5](SSDF.md#5-how-neuralmind-is-developed)).

## 2. SDLC Phases

### 2.1 Planning

- A larger feature (a new subsystem, a new storage format, a benchmark) gets
  a spec in `docs/specs/` before implementation: problem, design, how it's
  tested.
- Smaller changes start from a GitHub issue or a plan in the pull request.
- Business requirements and strategy documents live in a private repository
  (see `CLAUDE.md`).

### 2.2 Implementation

1. Create feature branch from `main`
2. Write code following project conventions (CLAUDE.md)
3. Write tests alongside code
4. Document with inline comments and docstrings

### 2.3 Testing

CI runs these on every pull request and every push to `main`. Each fails its
check on a problem:
- **Unit tests:** `pytest tests/` on Linux, macOS and Windows, Python 3.10–3.12
- **Type checks:** mypy against a baseline (`scripts/check_mypy_baseline.py`). The 305 errors it reported when it became a check on 2026-10-19 are listed in `scripts/mypy-baseline.txt`; a new one fails, and so does a fixed one until the list is lowered in the same change
- **Lint:** ruff, black, `scripts/check_unreachable.py` and the docs and terms guards
- **Benchmarks:** the hermetic self-benchmark (`ci-benchmark.yml`), failing below a 4× reduction floor
- **Security scans (CI):** CodeQL; bandit, where high severity fails the change; and `pip-audit` over the installed dependencies, failing on any advisory not marked `not_affected` in `security/neuralmind.openvex.json`
- **FIPS mode (CI):** the test suite with the OpenSSL FIPS provider enforced

### 2.4 Review

- Two automated reviewers, GitHub Copilot code review and OpenAI Codex, review
  each pull request
- The maintainer reads the diff and the reviews, and merges
- No rule makes a merge wait for green CI or a finished review; the maintainer
  waits for both by practice. `main`'s ruleset requires neither (SSDF PS.1)

### 2.5 Deployment

- Push to `main` triggers CI
- Merging release-please's release PR tags `vX.Y.Z`, which triggers the PyPI
  and GHCR publish. A smoke test runs before the PyPI upload, and the image's
  signature, provenance and a smoke test must pass before `:latest` moves
- Cloudflare Pages deploys on `site/**` changes

### 2.6 Monitoring

- GitHub Actions dashboard for CI health
- Dependabot for dependency vulnerabilities
- Manual review of benchmark trends

## 3. Quality Gates

| Gate | Criteria | Enforced by |
|------|----------|-------------|
| Pre-merge | All CI checks pass, reviews read | Practice. No rule blocks a merge |
| Pre-merge | Benchmark ratio ≥ 4× floor | A failing check, which no rule makes a merge wait for |
| Release | The release PR's CI is green | Practice |
| Publish | Smoke test before the PyPI upload; the image's signature, provenance and smoke test before `:latest` moves | The release workflows (`release.yml`, `docker-publish.yml`) stop on a failure |

## 4. Documentation Standards

Every user-facing change ships, in the same pull request, with:
- Release notes (`docs/releases/RELEASE_NOTES_vX.Y.Z.md`), including how to
  reproduce what they claim
- Updates to the README, CLI reference and use-case walkthroughs it touches
  (the checklist in `CLAUDE.md`)

Larger features also have a spec in `docs/specs/` (2.1). Policy documents are
dated and versioned.

## 5. Versioning

NeuralMind follows semantic versioning:
- **Patch (Z+1):** Bug fixes, no API changes
- **Minor (Y+1):** New features, backward-compatible
- **Major (X+1):** Breaking changes

Version bump is automated via release-please on `feat:` / `fix:` commits.

---

*This policy is reviewed annually. Last reviewed: 2026-10-18.*
