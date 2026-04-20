# Changelog

## [0.3.0] - 2026-04-20

### Added

#### Setup & Documentation
- **New Setup-Guide** (`docs/wiki/Setup-Guide.md`) — Complete first-time setup guide for all platforms
  - 30-second quick start
  - Decision tree for choosing your setup path
  - Platform-specific instructions (Claude Code, Copilot, Cursor, VSCode, Cline, Continue, ChatGPT/Gemini)
  - Version requirements and compatibility matrix
  - Timing expectations and performance optimization
  - Cost breakdown showing token savings per platform

- **Brain-Like Learning Documentation** (`docs/brain_like_learning.md`) — Comprehensive user guide
  - Why learning matters (repeated questions, context fatigue)
  - Before/after examples showing token savings
  - How to enable/disable (one-time opt-in, TTY-only)
  - Privacy & data storage (100% local, reset anytime)
  - Examples by role (app developers, data scientists, DevOps, onboarding)
  - Troubleshooting (stale patterns, wrong data, privacy controls)
  - Technical design for contributors

#### CLI Improvements
- **Platform matrix in Setup-Guide** — Token reduction %, setup time, MCP support by platform
- **Cost breakdown** — Monthly savings examples for different platforms and models
- **Navigation updates** — Wiki Home now links to Setup-Guide and Learning Guide

### Changed
- **README.md** — Added Brain-Like Learning feature section with status and link to guide
- **Wiki Home.md** — Reorganized quick links with Setup-Guide and Learning Guide as primary entry points
- **PyPI metadata** — Updated description and keywords to include brain-like learning and multi-platform support

### Coming in v0.3.1
- Local-first memory collection infrastructure (JSONL storage)
- One-time opt-in consent system (TTY-only, respects env vars)
- Integration into `query()` for implicit logging
- CLI commands: `neuralmind stats --memory`, `neuralmind learn . --dry-run`
- Memory management: `neuralmind memory reset`

### Coming in v0.3.2
- Cooccurrence-based reranking algorithm
- `neuralmind learn .` actual execution (not just preview)
- Token savings measurement and reporting

---

## [0.2.2] - 2026-04-15

### Fixed
- CI: Declare toml dependency to fix collection failures
- Release CI: Gate GitHub release on PyPI install/import smoke test

### Changed
- CI: Migrate workflow action pins to Node 24-compatible majors

---

## [0.2.1] - Earlier

See [GitHub Releases](https://github.com/dfrostar/neuralmind/releases) for earlier versions.
