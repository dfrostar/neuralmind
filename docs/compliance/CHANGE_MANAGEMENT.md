# Change Management Policy

**Date:** 2026-07-27
**Version:** 1.0
**SOC 2 Controls:** CC3.1, CC3.2, CC8.1

---

## 1. Purpose

Define how changes to NeuralMind code, documentation, and infrastructure are proposed, reviewed, approved, and deployed.

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

All changes require review before merging to `main`:

1. **Self-review (solo maintainer):** The author reviews their own diff before opening a PR
2. **CI validation:** GitHub Actions runs linting, tests, and benchmarks
3. **Automated checks:** Release-please for version bumps, SBOM generation

### 3.3 Change Approval

For solo maintainer (current state):
- Author approves own changes after CI passes
- No merge if any CI check fails
- Breaking changes require a new minor version

For future team state:
- 1 approval from another maintainer required
- Security-related changes require security review
- Infrastructure changes require ops review

### 3.4 Deployment

Changes are deployed via GitHub Actions:
- Push to `main` triggers CI
- Tag push triggers PyPI + GHCR publish
- Cloudflare Pages deploy triggers on `site/**` changes

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
- Vanta evidence collection (quarterly export)

## 6. Exceptions

Hotfixes for critical security vulnerabilities may be fast-tracked:
- Direct commit to `main` with `[HOTFIX]` prefix
- CI still runs (must pass)
- Post-merge review within 24 hours

---

*This policy is reviewed annually. Last reviewed: 2026-07-27.*
