# Changelog

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
