# Contributing to NeuralMind

First off, thank you for considering contributing to NeuralMind! It's people like you that make NeuralMind such a great tool.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Making Changes](#making-changes)
- [Pull Request Process](#pull-request-process)
- [Style Guidelines](#style-guidelines)
- [Testing](#testing)
- [Documentation](#documentation)
- [Release Process](#release-process)
- [Community](#community)

## Code of Conduct

This project and everyone participating in it is governed by our
[Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to
uphold this code. Please report unacceptable behavior to hello@neuralmind.uk.

### Our Standards

- Be respectful and inclusive
- Welcome newcomers and help them learn
- Focus on what is best for the community
- Show empathy towards other community members

## Getting Started

### Types of Contributions

There are many ways to contribute:

- 🐛 **Bug Reports**: Found a bug? Open an issue!
- ✨ **Feature Requests**: Have an idea? We'd love to hear it!
- 📝 **Documentation**: Help improve our docs
- 🔧 **Code**: Fix bugs or implement new features
- 🧪 **Testing**: Write tests or test new releases
- 💬 **Support**: Help others in discussions

### First Time Contributors

Look for issues tagged with:
- `good first issue` - Good for newcomers
- `help wanted` - Extra attention needed
- `documentation` - Documentation improvements

## Development Setup

### Prerequisites

- Python 3.10 or higher
- Git
- A virtual environment tool (venv, conda, etc.)

### Setup Steps

```bash
# 1. Fork the repository on GitHub

# 2. Clone your fork
git clone https://github.com/YOUR_USERNAME/neuralmind.git
cd neuralmind

# 3. Add upstream remote
git remote add upstream https://github.com/dfrostar/neuralmind.git

# 4. Create a virtual environment
python -m venv venv
source venv/bin/activate  # Linux/macOS
# or: venv\Scripts\activate  # Windows

# 5. Install in editable mode with dev dependencies
pip install -e ".[dev]"

# 6. Verify setup
pytest tests/ -v
```

> Note: there's no `pre-commit` config in this repo — Lint runs in CI
> via `black --check` + `ruff check`. To replicate locally before
> pushing: `black neuralmind/ tests/ && ruff check neuralmind/ tests/`.

### Project Structure

```
neuralmind/
├── neuralmind/                  # Main package
│   ├── __init__.py              # Package exports
│   ├── core.py                  # NeuralMind orchestrator (public API)
│   ├── embedder.py              # GraphEmbedder — graph → ChromaDB embeddings
│   ├── context_selector.py      # L0/L1/L2/L3 progressive disclosure
│   ├── synapses.py              # SQLite-backed Hebbian + directional graph (v0.4 + v0.11)
│   ├── synapse_memory.py        # Markdown export → Claude Code auto-memory
│   ├── watcher.py               # File activity → synapse co-activation + transitions
│   ├── compressors.py           # PostToolUse compressors (Read/Bash/Grep)
│   ├── output_cache.py          # Recovery cache for `neuralmind last` (v0.10+)
│   ├── reranker.py              # Cooccurrence reranker (deprecation tracked in #143)
│   ├── memory.py                # Query/event log + learned-patterns scaffold
│   ├── event_bus.py             # In-process pub/sub for live activity events
│   ├── event_log.py             # Cross-process JSONL bridge (v0.6+)
│   ├── server.py                # Graph-view HTTP + /api/events SSE
│   ├── hooks.py                 # Claude Code hook registration + runtime
│   ├── mcp_server.py            # MCP tools surface
│   ├── mcp_security.py          # RBAC + audit-trail integration
│   ├── audit.py                 # Audit log writer
│   ├── backend_manager.py       # Pluggable embedding backend (Chroma / in-memory)
│   ├── embedding_backend.py     # Backend abstraction
│   ├── in_memory_backend.py     # Test-only backend
│   ├── local_client.py          # Local-only MCP client helper
│   ├── config.py                # Config loader
│   ├── cli.py                   # `neuralmind` CLI entry point
│   ├── demo_data/               # Bundled fixture for `neuralmind demo`
│   └── web/                     # Graph-view canvas assets
├── tests/                       # Test suite (stdlib-only synapse tests)
├── docs/                        # README, wiki, use-cases, comparisons, landing pages
├── .github/                     # Workflows, dependabot, release-please config
├── scripts/                     # Demo + systemd/launchd templates
├── skills/                      # Reusable agent skills
├── pyproject.toml               # Project config (managed by release-please)
├── CLAUDE.md                    # Codebase-wide instructions for AI coding agents
├── CHANGELOG.md                 # Auto-written by release-please (do not edit)
└── README.md
```

## Making Changes

### Branch Naming

Use descriptive branch names:

- `feature/add-export-json` - New features
- `fix/query-empty-error` - Bug fixes
- `docs/update-api-reference` - Documentation
- `refactor/simplify-embedder` - Code refactoring
- `test/add-cli-tests` - Test additions

### Workflow

```bash
# 1. Create a new branch from main
git checkout main
git pull upstream main
git checkout -b feature/your-feature-name

# 2. Make your changes
# ... edit files ...

# 3. Run tests
pytest tests/ -v

# 4. Run linting
black .
ruff check .

# 5. Commit your changes
git add .
git commit -m "feat: add new feature description"

# 6. Push to your fork
git push origin feature/your-feature-name

# 7. Open a Pull Request on GitHub
```

### Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>

[optional body]

[optional footer(s)]
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `style`: Formatting (no code change)
- `refactor`: Code restructuring
- `test`: Adding tests
- `chore`: Maintenance tasks

**Examples:**
```
feat(cli): add --json output flag for stats command
fix(embedder): handle empty graph.json gracefully
docs(readme): update installation instructions
test(core): add tests for wakeup method
```

## Pull Request Process

### Before Submitting

- [ ] Tests pass locally (`pytest tests/ -v`)
- [ ] Code is formatted (`black .`)
- [ ] Linting passes (`ruff check .`)
- [ ] Documentation is updated if needed
- [ ] Commit messages follow conventions

### PR Guidelines

1. **Title**: Use conventional commit format
2. **Description**: Explain what and why
3. **Link Issues**: Reference related issues
4. **Small PRs**: Keep changes focused
5. **Tests**: Add tests for new functionality

### Review Process

1. A maintainer will review your PR
2. Address any feedback
3. Once approved, a maintainer will merge
4. Your contribution will be in the next release! 🎉

## Style Guidelines

### Python Style

- **Formatter**: Black (line length 100)
- **Linter**: Ruff
- **Type Hints**: Required for public APIs
- **Docstrings**: Google style

```python
def query(self, question: str, n: int = 10) -> ContextResult:
    """Query the codebase with natural language.
    
    Args:
        question: Natural language question about the codebase.
        n: Maximum number of search results to include.
    
    Returns:
        ContextResult with optimized context for AI consumption.
    
    Raises:
        ValueError: If question is empty.
        RuntimeError: If index not built.
    
    Example:
        >>> result = mind.query("How does auth work?")
        >>> print(result.context)
    """
```

### Code Quality

- Write self-documenting code
- Keep functions focused and small
- Use meaningful variable names
- Add comments for complex logic
- Handle errors gracefully

## Testing

### Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_core.py -v

# Run specific test
pytest tests/test_core.py::TestNeuralMindQuery::test_query_returns_context -v

# Run with coverage
pytest tests/ --cov=neuralmind --cov-report=html

# Run excluding slow tests
pytest tests/ -v -m "not slow"
```

### Writing Tests

```python
import pytest
from neuralmind import NeuralMind


class TestNeuralMindQuery:
    """Tests for NeuralMind.query() method."""
    
    def test_query_returns_context_result(self, temp_project):
        """Test that query returns a ContextResult."""
        mind = NeuralMind(str(temp_project))
        mind.build()
        
        result = mind.query("How does auth work?")
        
        assert result.context is not None
        assert result.budget.total > 0
    
    def test_query_empty_raises_error(self, temp_project):
        """Test that empty query raises ValueError."""
        mind = NeuralMind(str(temp_project))
        mind.build()
        
        with pytest.raises(ValueError):
            mind.query("")
```

### Test Categories

- **Unit Tests**: Test individual functions/methods
- **Integration Tests**: Test component interactions
- **CLI Tests**: Test command-line interface

## Documentation

### Types of Documentation

1. **Code Documentation**: Docstrings in code
2. **API Reference**: Auto-generated from docstrings
3. **User Guide**: How-to articles in wiki
4. **README**: Project overview

### Updating Documentation

- Update docstrings when changing APIs
- Update wiki for new features
- Keep examples working
- Add type hints

> **Standard process.** For any user-facing change (a CLI command, MCP tool,
> hook, env var, agent-visible behavior, or visible fix), follow the
> [Documentation Process](docs/DOCUMENTATION-PROCESS.md): docs ship in the
> *same PR* as the change, propagated across all five surfaces, and every doc
> answers *"what does the user/agent now see?"*. The PR template's
> "Documentation & discoverability" checklist operationalizes it.

## Release Process

Releases are managed with [release-please](https://github.com/googleapis/release-please). The process is fully automated once commits land on `main`.

### How it works

1. **Commit to `main` using [Conventional Commits](https://www.conventionalcommits.org/)**
   — `feat:` bumps the minor version, `fix:` bumps the patch version, `feat!:` or `BREAKING CHANGE:` bumps major.
2. **release-please opens a Release PR automatically.**
   The PR bumps the version in `pyproject.toml`, updates `CHANGELOG.md`, and proposes a new git tag.
3. **Merge the Release PR** when you're ready to ship.
   Merging it creates the git tag (e.g. `v0.4.0`), which triggers the existing `release.yml` workflow that publishes to PyPI and TestPyPI.

### Dry-run a version bump

To preview what a bump would look like without releasing:

```bash
# Install release-please CLI
npm install -g release-please

# Preview the next release PR (no writes)
release-please release-pr \
  --repo-url dfrostar/neuralmind \
  --config-file release-please-config.json \
  --manifest-file .release-please-manifest.json \
  --dry-run
```

### Manual release (emergency only)

If you must release manually (e.g. a hotfix not using release-please):

```bash
# 1. Update the version in pyproject.toml AND neuralmind/__init__.py
#    (release-please-config.json's actual version-file) — keep them equal.
# 2. Update CHANGELOG.md
# 3. Update .release-please-manifest.json to match the new version
# 4. Update skills/neuralmind/SKILL.md's `version:` line to match too —
#    keep the `# x-release-please-version` annotation on that line intact.
#    tests/test_skill_manifest.py checks this file against the manifest,
#    and it's what Hermes-Agent, OpenClaw's ClawHub, and Agent Zero's
#    registries all read; skipping this step is exactly how it drifted to
#    three releases behind before (fixed in #508).
# 5. Commit with: chore(release): vX.Y.Z
# 6. Push that commit and get it onto `main` FIRST, as its own push or a
#    fast-forward merge — never a squash- or rebase-merged PR. Either of
#    those rewrites the commit into a new SHA on main, silently orphaning
#    the tag you're about to create in step 7 (see "Tag the SHA that's
#    actually on main" below).
git push origin HEAD:main

# 7. Only now, tag the commit that landed on main — re-read its SHA from
#    main itself, don't reuse the SHA you had checked out locally:
git fetch origin main
git tag vX.Y.Z origin/main
git push origin vX.Y.Z
```

**Tag the SHA that's actually on `main`, not the one you committed locally.**
If step 5 goes through a PR that GitHub squash- or rebase-merges, the commit
that lands on `main` gets a *different SHA* than the one you tagged locally
— even with an identical message and near-identical content. The tag then
points at a commit unreachable from `main`: orphaned, invisible to anyone
browsing the branch, and invisible to release-please's own diffing (see the
next section). This happened for real on `v3.9.0` — this section was rewritten
after diagnosing it live in 2026-09.

The `validate-version` gate in `release.yml` checks three things before
anything publishes, and hard-fails the whole pipeline if any of them don't
hold: the tag matches `pyproject.toml`'s version, the tag matches
`.release-please-manifest.json`, and **the tag's commit is an ancestor of
`main`**. The third check is what would have caught the `v3.9.0` incident
immediately instead of letting it corrupt the next release-please PR two
weeks later.

### Release-please troubleshooting

**Symptom: Commits land on `main` but no Release PR ever appears.**

Check `git ls-remote origin 'release-please*'`. If a `release-please--branches--main`
branch exists with the correct manifest/CHANGELOG diff, release-please is running
fine — the failure is the PR creation step. The fix is a one-time repo setting:

> Settings → Actions → General → Workflow permissions → enable
> **"Allow GitHub Actions to create and approve pull requests"**

GitHub disables this by default, and the `pull-requests: write` permission in the
workflow YAML is silently ignored without it. After enabling, push any conventional
commit to `main` (or re-run the most recent workflow) and the PR will appear.

**Symptom: A `fix:` or `feat:` commit was merged but release-please ignored it.**

Conventional Commit prefixes are case-sensitive. `Fix:` and `FIX:` are not
recognized — only lowercase `fix:` triggers a patch bump. Same for `feat:`.
If you see this in history, the next valid lowercase commit will sweep them
into its release.

**Symptom: A `feat:` commit was merged but release-please proposed a patch bump
(0.x.Y → 0.x.Y+1) instead of a minor bump (0.x.Y → 0.(x+1).0).**

Check `release-please-config.json` for `"bump-patch-for-minor-pre-major": true`.
If it's set, every `feat:` is forced to a patch bump until v1.0 — regardless
of the conventional-commit type. The flag was dropped before v0.6.0 so this
should no longer be the default; if you see it again in the config, removing
it restores the standard pre-1.0 behavior (`feat:` → minor, `fix:` → patch,
`feat!:` → minor, capped at 0.x by `bump-minor-pre-major`).

To pin a specific version regardless of commit history, land an empty commit
with the `Release-As:` footer:

```bash
git commit --allow-empty -m "chore: release as v0.6.0" -m "Release-As: 0.6.0"
```

This was used to produce v0.4.0 before the config was sorted out.

**Symptom: release-please proposes a release with a huge, wrong changelog
reaching back through already-shipped work, or an unexpected major-version
bump.**

This means the git tag matching `.release-please-manifest.json`'s current
value is not actually an ancestor of `main` — release-please can't find it
in the branch's history, so it silently falls back to whatever earlier tag
*is* an ancestor and walks everything since, including work that already
shipped under a later version. Confirm with:

```bash
git merge-base --is-ancestor v<manifest-version> origin/main && echo OK || echo ORPHANED
```

If it prints `ORPHANED`, **check whether that tag has a published immutable
release before planning any repair** — it decides which of the two recoveries
below is even possible:

```bash
gh api repos/{owner}/{repo}/releases/tags/v<manifest-version> --jq .immutable
```

Read that as **four** outcomes, not two — the endpoint returns 404 when no
release exists for the tag, so `gh` exits nonzero having printed neither
`true` nor `false`:

| Result | Meaning | Go to |
|--------|---------|-------|
| `true` | Published immutable release. The tag is permanently pinned. | Recovery A |
| `false` | A release exists but is mutable. | Recovery B |
| HTTP 404 (`Not Found`, nonzero exit) | No release for this tag at all, so nothing pins it. | Recovery B |
| Any other error (auth, rate limit, network) | Unknown — resolve it first. | — |

Never read a non-404 failure as "no release." And note the 404 row is the
*usual* case for a bad tag this gate catches: `validate-version` fails long
before `github-release` would ever create a release, so a freshly-pushed
orphaned tag normally has none.

#### Recovery A — the tag has an immutable release (retagging is impossible)

This repo has release immutability enabled, so this is the normal case for
any tag that actually shipped. Per GitHub's documentation, once an immutable
release is published its tag "is locked to a specific commit, cannot be
changed, and cannot be deleted while the release exists," and if you delete
the release to free the tag, "you cannot reuse the same tag name." There is
no sequence of git commands that repoints such a tag. Don't try; the push is
rejected with `GH013 … Cannot update this protected ref`, and no ruleset
appears in Settings → Rules to explain it, because immutability is enforced
separately from rulesets.

Instead, tell release-please where the last release actually landed on `main`,
with a top-level `last-release-sha` in `release-please-config.json`:

```json
{
  "release-type": "python",
  "last-release-sha": "<full 40-char SHA on main of the released commit>",
  "packages": { ... }
}
```

Release-please then collects commits *after* that SHA instead of resolving
the orphaned tag, which fixes both the changelog range and the version bump
(the bump level is derived from the commits it collects). A full 40-character
SHA is required, and the key is only honored at the top level of the config,
not inside a `packages` entry. Find the SHA by locating the commit on `main`
that carries the released change (`git log --all --grep`), and verify it with
`git merge-base --is-ancestor <sha> origin/main`.

This is what `v3.9.0` needed: its tag points at `d748a65`, which never
reached `main`, while the same change landed as `73a4b0b`, which did.

**`last-release-sha` must be deleted once the next release PR merges. This
is required, not housekeeping.** Release-please's manifest documentation is
explicit that the two sha options behave differently: `bootstrap-sha` "will
subsequently be ignored" once a release PR exists, but `last-release-sha` is
"never ignored: remove/change it once a good release PR is merged." It is a
hard stop in the backward commit walk that keeps applying on every later run,
so a stale entry does *not* quietly stop mattering once a newer,
properly-reachable tag exists. Leaving it pinned re-walks already-released
commits into a later changelog — the same bug this entry exists to fix,
reintroduced from the other direction. After the next release lands, delete
the key and confirm the following release-please PR is still correctly
scoped.

#### Recovery B — the tag is mutable or has no release (retagging is possible)

Only when the check above returned `false` or a confirmed 404. Find a
commit on `main` that's a candidate for the
retag. Start from the commit with the equivalent change (same message,
`git log --all --grep`), but **don't stop at matching source content** —
`git diff <bad-tag> <candidate>` showing only cosmetic differences is
necessary but not sufficient. The candidate must ALSO satisfy
`validate-version`'s other two checks at that exact commit:

```bash
git show <candidate>:pyproject.toml | grep '^version'
git show <candidate>:.release-please-manifest.json
git show <candidate>:skills/neuralmind/SKILL.md | grep '^version:'
```

All three must read `v<manifest-version>` **at that commit** — not on
`main`'s current tip, at the candidate itself. This is easy to get wrong:
the commit with the matching *source* content is often an earlier one than
the commit where the manifest/SKILL.md bookkeeping actually got fixed (that
fix usually lands later, bundled with unrelated work, exactly as it did for
`v3.9.0` — the source-matching commit predated the manifest fix by a week,
which would have failed `validate-version`'s manifest check all over again
if tagged directly). Walk forward from the source-matching commit to the
nearest later one where all three agree, and tag that instead. Then:

```bash
git tag -f v<manifest-version> <correct-sha-on-main>
git push --force origin v<manifest-version>
```

This only rewrites a git ref — nothing already published (the PyPI wheel,
the GHCR image, the SBOM, the GitHub Release notes) changes, and none of
those republish as a side effect either: `release.yml`, `docker-publish.yml`
and `sbom.yml` all re-fire on this push (it's a real tag push, same as the
original), but PyPI publish uses `skip-existing: true` so an already-shipped
version succeeds as a no-op instead of failing on "file already exists",
GHCR image tags simply get overwritten with identical content, and
`sbom.yml` already no-ops when nothing changed. All three workflows share
one `validate-version` gate (`_validate-release-tag.yml`, a reusable
workflow) — before this section was written, only `release.yml` checked
the tag, so an orphaned or mismatched tag could still get a GHCR image
built and an SBOM published even though PyPI correctly rejected it.

**On immutability: it locks the tag, not just the assets.** An earlier
version of this section claimed the opposite — that Release immutability was
only about attaching *assets* after publish, and that a tag stayed an
ordinary force-pushable ref. That was wrong, and it sent someone through a
retag that could never have worked. Immutability covers both: assets are
frozen (which is why `github-release`'s job in `release.yml` warns and moves
on rather than failing when a late asset upload is refused) **and** the tag
is pinned to its commit for as long as the release exists. Confirm a given
release's status from the API's `immutable` field rather than assuming
either way:

```bash
gh api repos/{owner}/{repo}/releases/tags/vX.Y.Z --jq .immutable
```

The repo-level setting lives under Settings → General → Releases. Note that
already-published releases carry immutability as a property of the release
itself, so turning the setting off does not retroactively unlock tags that
were published while it was on.

Do the repair before merging or re-running release-please's next proposed
PR; merging it as-is would ship the bogus changelog and version bump. The
`validate-version` gate described above exists specifically to stop a
fresh instance of this from
reaching this point silently again.

## Community

### Where to post — quick triage

| You want to… | Use |
|---|---|
| Report a bug or unexpected behavior | [Issues](https://github.com/dfrostar/neuralmind/issues/new) |
| Ask "how do I…" / "why doesn't X work" | [Discussions → Q&A](https://github.com/dfrostar/neuralmind/discussions/categories/q-a) |
| Suggest a feature or "what if NeuralMind could…" | [Discussions → Ideas](https://github.com/dfrostar/neuralmind/discussions/categories/ideas) |
| Show how you use NeuralMind | [Discussions → Show and tell](https://github.com/dfrostar/neuralmind/discussions/categories/show-and-tell) |
| Send code | Pull request (this file is your guide) |
| Report a security vulnerability | [GitHub Security Advisories](https://github.com/dfrostar/neuralmind/security/advisories/new) or `darren.frost@gmail.com` — **not** a public Issue. See [SECURITY.md](SECURITY.md). |

Each Discussions category has a pre-filled template — use it. It makes triage faster and the answer better.

### Recognition

Contributors are recognized in:
- The squash-merge commit message and the auto-generated CHANGELOG entry (release-please attributes commit authors)
- The GitHub contributors page

---

## Thank You!

Every contribution, no matter how small, helps make NeuralMind better. Thank you for being part of our community!

If you have questions, don't hesitate to ask. We're here to help! 🙌
