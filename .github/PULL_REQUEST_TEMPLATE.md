## Description

Please include a summary of the changes and the related issue. Include relevant motivation and context.

Fixes # (issue number)

## Type of Change

Please delete options that are not relevant.

- [ ] 🐛 Bug fix (non-breaking change which fixes an issue)
- [ ] ✨ New feature (non-breaking change which adds functionality)
- [ ] 💥 Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] 📝 Documentation update
- [ ] 🔧 Configuration change
- [ ] ♻️ Refactoring (no functional changes)
- [ ] 🧪 Test update
- [ ] 🎨 Style/formatting change

## How Has This Been Tested?

Please describe the tests that you ran to verify your changes.

- [ ] Unit tests
- [ ] Integration tests
- [ ] Manual testing

### Test Configuration

* **Python version**: 
* **Operating System**: 
* **Test command**: `pytest tests/ -v`

## Documentation & discoverability

Per the [Documentation Process](../docs/DOCUMENTATION-PROCESS.md). Required when
this PR adds/changes a CLI command, MCP tool, hook, env var, agent-visible
behavior, or a visible fix. Tick **N/A** for pure internal refactors.

- [ ] N/A — internal-only change, no user-facing surface
- [ ] Docs answer *"what does the user/agent now see?"* (not just what the code does)
- [ ] `README.md` updated (banner/sections) if user-facing
- [ ] `docs/index.html` + `docs/about.html` updated if user-facing (incl. the **Status & Future** block — keep "Current/Next" honest)
- [ ] `docs/wiki/*.md` (e.g. `CLI-Reference.md`) updated for new commands/env vars — syncs to the live wiki automatically
- [ ] Use-case walkthrough updated/added if a workflow was unlocked
- [ ] SEO refreshed (keywords / meta / sitemap) if a new noun entered the product surface
- [ ] I did **not** edit `CHANGELOG.md` or hand-bump the `pyproject.toml` version (release-please owns these)

## Checklist

- [ ] My code follows the style guidelines of this project
- [ ] I have performed a self-review of my code
- [ ] I have commented my code, particularly in hard-to-understand areas
- [ ] I have made corresponding changes to the documentation
- [ ] My changes generate no new warnings
- [ ] I have added tests that prove my fix is effective or that my feature works
- [ ] New and existing unit tests pass locally with my changes
- [ ] Any dependent changes have been merged and published in downstream modules

## Code Quality

- [ ] I have run `black .` for formatting
- [ ] I have run `ruff check .` for linting
- [ ] Type hints are added for new functions/methods
- [ ] Docstrings are added/updated for public APIs

## Screenshots (if applicable)

_Add screenshots to help explain your changes._

## Additional Notes

_Add any additional notes or context about the pull request here._
