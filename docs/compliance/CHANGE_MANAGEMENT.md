# Change Management Policy

**Date:** 2026-10-18
**Version:** 1.2
**SOC 2 Control:** CC8.1

---

## 1. Purpose

Define how changes to NeuralMind code, documentation, and infrastructure are proposed, reviewed, approved, and deployed.

Version 1.1 said every change needed review and green CI before merging. That
has been the practice since October 2026, but no rule enforces it, and before
then most changes were pushed to `main` directly ([SSDF PS.1](SSDF.md)). Much
of the code is written with AI coding agents for the maintainer
([SSDF §5](SSDF.md#5-how-neuralmind-is-developed)).

## 2. Scope

All changes to:
- Source code (`neuralmind/`, `tests/`, `scripts/`)
- Documentation (`docs/`, `CLAUDE.md`, `SECURITY.md`)
- CI/CD pipelines (`.github/workflows/`)
- Dependencies (`pyproject.toml`, `package.json`)
- Infrastructure (Cloudflare Pages, GitHub settings)

## 3. Change Process

### 3.1 Change Proposal

Every change starts with a commit to a feature branch:

```bash
git checkout -b feat/<description>
# or
git checkout -b fix/<description>
```

Commit messages follow conventional commits:
- `feat:` — new feature
- `fix:` — bug fix
- `docs:` — documentation
- `ci:` — CI/CD changes
- `refactor:` — code restructuring
- `chore:` — maintenance

### 3.2 Change Review

Each pull request is reviewed before it merges to `main`:

1. **Automated review:** GitHub Copilot code review and OpenAI Codex review the PR
2. **Maintainer review:** the maintainer reads the diff and the reviews
3. **CI validation:** GitHub Actions runs linting, tests, security scans, and benchmarks

This is practice. `main`'s ruleset doesn't require a PR, a review, or passing
checks ([SSDF PS.1](SSDF.md)).

### 3.3 Change Approval

For solo maintainer (current state):
- The maintainer merges after CI passes and the automated reviews finish
- No merge while a CI check fails or a review is still running. #672 (v4.17.1)
  merged while Codex was still reviewing it, and Codex's finding needed a
  follow-up fix (#674)
- Breaking changes require a new major version

For future team state:
- 1 approval from another maintainer required
- Security-related changes require security review
- Infrastructure changes require ops review

### 3.4 Deployment

Changes are deployed via GitHub Actions:
- Push to `main` triggers CI
- Merging release-please's release PR tags the release, which triggers the PyPI and GHCR publish
- Cloudflare Pages deploy triggers on `site/**` changes
- GitHub Pages publishes `docs/` on every push to `main`, without waiting for CI

No manual deployment steps.

## 4. Rollback Procedure

If a deployed change causes issues:

1. Revert the commit: `git revert <sha>`
2. Push to `main`
3. CI automatically deploys the revert
4. For PyPI/GHCR: tag a new release with the revert

## 5. Audit Trail

Every change is recorded in:
- Git commit history (immutable)
- GitHub PR history (if applicable)
- CI run logs (GitHub Actions artifacts)

## 6. Exceptions

Hotfixes for critical security vulnerabilities may be fast-tracked:
- Direct commit to `main` with `[HOTFIX]` prefix
- CI still runs (must pass)
- Post-merge review within 24 hours

Generated files are pushed to `main` directly, with `[skip ci]`, so CI doesn't
run on them: SBOMs (`sbom.yml`), the benchmark chart (`update-chart.yml`) and
the team-memory snapshot (`neuralmind-autoindex.yml`). These workflows hold a
deploy key that can push past any ruleset, so they install only pinned
packages.

---

*This policy is reviewed annually. Last reviewed: 2026-10-18.*
