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

This project and everyone participating in it is governed by our Code of Conduct. By participating, you are expected to uphold this code. Please report unacceptable behavior to the project maintainers.

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
# 1. Update the version in pyproject.toml
# 2. Update CHANGELOG.md
# 3. Update .release-please-manifest.json to match the new version
# 4. Commit with: chore(release): vX.Y.Z
# 5. Push the tag (must match pyproject.toml version):
git tag vX.Y.Z
git push origin vX.Y.Z
```

The `validate-version` gate in `release.yml` will reject the push if the tag and `pyproject.toml` version differ.

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
