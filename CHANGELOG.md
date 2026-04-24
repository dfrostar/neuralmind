# Changelog

## [0.3.5](https://github.com/dfrostar/neuralmind/compare/v0.3.4...v0.3.5) (2026-04-24)


### Features

* Add plugin.yaml for Agent Zero plugin compatibility ([96098ee](https://github.com/dfrostar/neuralmind/commit/96098eedeba7048af3659c3eec6d247e045126fd))


### Bug Fixes

* add backend_name property, fix exception types ([536518b](https://github.com/dfrostar/neuralmind/commit/536518bc469e15a7fcbd8e947fbe4a67d796d520))
* add missing MCPSecurityManager import ([132ea19](https://github.com/dfrostar/neuralmind/commit/132ea19557ee0712e76af3df1958e361f7f541fd))
* Correct auditability claims and enhance enterprise SEO ([164d41b](https://github.com/dfrostar/neuralmind/commit/164d41b99a26dde7201c0da82944f1f0722f9392))
* remove duplicate backend key, fix import conflict ([9bed6ce](https://github.com/dfrostar/neuralmind/commit/9bed6ce6a70e0cba0891cef6371dd9f664ada935))
* remove unreachable audit code from property ([34d6d79](https://github.com/dfrostar/neuralmind/commit/34d6d79b0f276a894b734456d8a934a0612a82ce))
* replace audit.log_event with _emit_audit ([6e35e59](https://github.com/dfrostar/neuralmind/commit/6e35e5905a9ec3f52331c223d9d2d0666dd17445))
* resolve merge conflict in core.py ([dbb4e82](https://github.com/dfrostar/neuralmind/commit/dbb4e8297df6072fa3f5a2063842fec39f458d8c))
* resolve merge conflicts in mcp_server.py ([d2adc47](https://github.com/dfrostar/neuralmind/commit/d2adc47c78ec31d26e6412e3c66814950174a4c8))
* **security:** bump mcp, black, pytest to clear 6 Dependabot alerts ([#68](https://github.com/dfrostar/neuralmind/issues/68)) ([4990a08](https://github.com/dfrostar/neuralmind/commit/4990a0803522f9e71dc74b2b69eaef5300b93a01))


### Documentation

* add benchmark proof section to Pages + wiki, commit initial chart ([f4940e6](https://github.com/dfrostar/neuralmind/commit/f4940e66cbcb68160313a9f3cd52180519ac7845))
* Add corporate-readiness security & compliance messaging ([14444ce](https://github.com/dfrostar/neuralmind/commit/14444ceb90a0f6e4afe34cf6d23cf1fd091ce677))
* add recursive query, document RAG, and NVIDIA NIM integration ([37f8e91](https://github.com/dfrostar/neuralmind/commit/37f8e91790c6a078bdbd4cd1e10276d6437515cf))
* enhance security & compliance documentation for enterprises ([1430ad0](https://github.com/dfrostar/neuralmind/commit/1430ad0f0ba3bc05a3affb9b3d00679a69babbce))
* full SEO pass — og:image, twitter cards, JSON-LD, sitemap, robots ([0f18c90](https://github.com/dfrostar/neuralmind/commit/0f18c90145a92b27d96592a55a48cbb9df03a580))

## [0.3.4] - 2026-04-20

### Documentation

- **CLI Reference** — Corrected all CLI flag documentation to match the actual implementation
  - Removed non-existent `--verbose`, `--export`, `--db-path`, `--type`, `--community`, `--queries` flags
  - Renamed `--limit` to `--n` for the `search` command (matches implementation)
  - Removed unsupported `--quiet` flag from `build` examples in Usage and Integration guides
- **Installation Guide** — Added missing `toml>=0.10` core dependency; fixed `python -m neuralmind` references to use the installed `neuralmind` entry point
- **Troubleshooting** — Fixed `python -m neuralmind` reference and removed non-existent `--verbose` option from examples
- **Setup Guide** — Created missing `docs/wiki/Setup-Guide.md`, fixing broken link referenced in Home and README
- **README** — Updated "What's New" to reflect the full v0.3.x feature set including 0.3.3 stability fixes

### Changed
- Version bumped from 0.3.3.2 → 0.3.4 for this documentation polish release

---

## [0.3.3.2] - 2026-04-20

### Fixed
- **Version sync for smoke test** — Fixed hardcoded __version__ in __init__.py to match pyproject.toml
  - Smoke test was failing due to version mismatch between package metadata and runtime

---

## [0.3.3.1] - 2026-04-20

### Fixed
- **Test expectations** — Fixed all remaining test expectations for embedder stat counting
  - `test_embed_nodes_force_reembeds` corrected to expect updated count

---

## [0.3.3] - 2026-04-20

### Fixed
- **Incremental embedding stat counting** — Fixed bug where `force=True` re-embed incorrectly counted all nodes as "added"
  - Now correctly distinguishes between "added" (new) and "updated" (existing) nodes
  - Critical for accurate build statistics and incremental updates
  
- **Test expectations** — Updated `test_build_force_reembeds_all` to expect correct behavior
  - Existing nodes on force rebuild now correctly reported as "updated"
  - Integration test marked as skipped in restricted network environments

### Quality Improvements
- Improved embed_nodes logic for accurate stat reporting

---

## [0.3.2] - 2026-04-20

### Added

#### Cooccurrence-Based Reranking (v0.3.2)
- **Reranker integration** — Applies learned module patterns to improve search relevance
  - `CooccurrenceIndex` class loads learned patterns from JSON
  - `SemanticReranker` class applies patterns to search results
  - Lazy-loads reranker in context selector for zero overhead if patterns unavailable
  - Boost factor (0-1) amplifies semantic relevance by up to 30%
  
- **Learning pipeline** — Analyzes query history to discover module relationships
  - `neuralmind learn .` command builds cooccurrence patterns from events
  - Extracts module pairs that frequently appear together
  - Saves patterns to `.neuralmind/learned_patterns.json`
  - Shows top patterns and statistics to user

- **Seamless integration** — Automatic reranking in retrieval pipeline
  - L2 context tracks loaded modules for reranker context
  - L3 search automatically reranks results if patterns available
  - Displays reranker boost scores in search output
  - Enable/disable via `enable_reranking` flag (default: enabled)

### Changed
- **NeuralMind class** — Added `enable_reranking` parameter for control
- **ContextSelector** — Integrated reranking into L3 search pipeline
- **CLI** — `learn` command now functional (was scaffold)

### Quality Improvements
- 30 new tests for reranker classes and functions
- 8 tests for pattern learning and cooccurrence analysis
- 3 tests for learn CLI command integration
- 7 integration tests for context selector + reranker pipeline
- Token savings measurement foundation

---

## [0.3.1] - 2026-04-20

### Added
- **EmbeddingBackend abstraction layer** — Decouples ChromaDB from core logic
  - New abstract base class enables backend swaps and mocking
  - Improves testability (no ChromaDB overhead in tests)
  - Future-proofs architecture for Pinecone/Weaviate integration

- **Comprehensive integration tests** — 14 tests validating 4-layer retrieval pipeline
  - End-to-end retrieval pipeline tests
  - Query-aware context validation
  - Token reduction verification
  - Community detection and file skeleton tests
  - Incremental embedding validation

### Changed
- **GraphEmbedder** — Now implements EmbeddingBackend interface
  - Adds `clear()` and `close()` methods
  - Maintains full backward compatibility
  
### Fixed
- Version string sync (__init__.py was v0.2.0, now v0.3.1)
- Wiki navigation updated to highlight new guides

### Quality Improvements
- Better code organization with clear abstractions
- Improved documentation discoverability
- Foundation for swappable embedding backends

---

## [0.3.0] - 2026-04-20

### Added

#### Brain-Like Learning (v0.3.0)
- **Local-first memory infrastructure** — JSONL storage for query patterns (project + global scopes)
- **Opt-in consent system** — One-time TTY-only prompt, respects env vars (`NEURALMIND_MEMORY=0`, `NEURALMIND_LEARNING=0`)
- **Memory logging** — Implicit tracking of queries and retrieved modules
- **CLI commands**:
  - `neuralmind learn .` — Scaffold command, safe no-op when learning disabled
  - `neuralmind stats --memory` — Show memory statistics (v0.3.1+)
  - `neuralmind memory reset` — Clear learned patterns anytime
- **Comprehensive documentation** (`docs/brain_like_learning.md`)
  - Why learning matters (repeated queries, context fatigue)
  - Before/after examples showing token improvements
  - Privacy-first design (100% local, no telemetry)
  - Role-based examples (developers, data scientists, DevOps, onboarding)
  - Troubleshooting guide

#### Setup & Documentation
- **Setup-Guide** (`docs/wiki/Setup-Guide.md`) — Complete first-time setup for all platforms
  - 30-second minimal setup
  - Platform decision tree
  - Version requirements and compatibility matrix
  - Cost breakdown (token savings per platform)
  - Performance expectations and optimization
- **Wiki navigation updates** — Learning and Setup-Guide as primary links
- **README updates** — Feature overview and learning guide link

### Changed
- **Memory module** (`neuralmind/memory.py`) — New persistence layer for query patterns
- **Core module** — Integration of memory logging into `NeuralMind.query()`
- **CLI** — New memory commands and options
- **PyPI metadata** — Keywords include brain-like-learning, continual-learning, copilot, cursor

### Coming in v0.3.1+
- Cooccurrence-based reranking algorithm
- Active `neuralmind learn .` execution (not just scaffold)
- Token savings measurement
- Memory decay and freshness controls

---

## [0.2.2] - 2026-04-15

### Fixed
- CI: Declare toml dependency to fix collection failures
- Release CI: Gate GitHub release on PyPI install/import smoke test

### Changed
- CI: Migrate workflow action pins to Node 24-compatible majors

---

## Earlier Versions

See [GitHub Releases](https://github.com/dfrostar/neuralmind/releases) for v0.2.1 and earlier.
