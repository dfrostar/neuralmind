TIER 2 (TEAM) BUILD — NEURALMIND v1.0.0
========================================

You are building NeuralMind Tier 2 ("Team"): a paid tier adding governance, audit, self-hosted deployment, and seat management on top of the v0.52.0 MIT product. Price: $29/user/mo, annual contract, 5-50 seats.

DOCS (read in this order):
1. `/home/dtfrost/neuralmind/TIER2-BRD.md` — business requirements
2. `/home/dtfrost/neuralmind/TIER2-TRD.md` — technical design, architecture, data model
3. `/home/dtfrost/neuralmind/TIER2-TEST-PLAN.md` — 48 tests (unit + integration + CLI e2e + Docker e2e)
4. `/home/dtfrost/neuralmind/TIER2-DEEPSEEK-QA.md` — DeepSeek QA gate plan

CLAUSE FROM BRD FR-01: Team admin can enable/disable team memory publishing per repo.

KEY ARCHITECTURE:
- New `neuralmind/tier2/` package (governance, audit, self_hosted, license, seats, config, cli)
- New audit.db (append-only hash chain)
- Extended meta table for governance config
- Docker compose for self-hosted
- License.json with Ed25519 signing + 30-day offline grace

PHASE 1 — CODE (build → test → DeepSeek → patch):
  - Create `neuralmind/tier2/__init__.py` + empty module stubs
  - Implement `config.py` + `seats.py` (simplest, no inter-module deps)
  - Implement `audit.py` (append-only hash chain: SHA256(entry.data + entry.prev_hash))
  - Implement `governance.py` (weight threshold, publishing scope, admin check on every mutation)
  - Implement `license.py` (Ed25519 verify, offline grace, seat limit)
  - Implement `self_hosted.py` (data dir init, permissions, health check)
  - Implement `cli.py` + extend `neuralmind/cli.py` with `team` subcommands
  - Write all 48 tests from the test plan
  - Run tests, fix until 100% green
  - Dispatch DeepSeek QA per the QA plan (6 modules, then cross-module integration review)
  - Patch all CRITICAL + WARNING findings
  - Re-run tests until 100% green post-patch

PHASE 2 — DEPLOY (Docker + self-hosted + e2e):
  - Write `docker-compose.yml` at repo root
  - Write `scripts/install-team.sh` (one-command deploy)
  - Write `scripts/e2e_team_tier.sh` (CLI e2e per test plan)
  - Write `scripts/test_self_hosted.sh` (Docker e2e per test plan)
  - Run both e2e scripts, fixuntil pass

PHASE 3 — DOCS + RELEASE:
  - Update `README.md` banner to v1.0.0
  - Update `CHANGELOG.md` with Tier 2 entry
  - Run public-docs-refresh skill across README, docs/index.html, docs/about.html, wiki
  - Tag v1.0.0, push (main first, then tag)
  - Verify PyPI publish + GHCR image

CRITICAL PITFALLS (from neuralmind-release skill):
1. Audit log hash chain: verify SHA-256 chaining is correct, tamper detection works
2. Governance publish gate: verify edge weight comparison, no bypass paths
3. License validation: verify Ed25519 signature verification, offline grace logic
4. Config schema: verify pydantic validation covers all edge cases
5. Self-hosted init: verify data dir creation, file permissions, license file handling
6. Publish idempotency: verify content-hash gating works correctly under concurrency

VERIFICATION (post-build, before declaring Done):
- `pytest tests/test_tier2_*.py tests/test_tier2_integration.py` → 48 passed
- `bash scripts/e2e_team_tier.sh` → exit 0
- `bash scripts/test_self_hosted.sh` → exit 0
- DeepSeek QA: 0 CRITICAL, 0 WARNING unpatched
- `python -c "import neuralmind; assert neuralmind.__version__ == '1.0.0'"`
- `neuralmind --version` shows `1.0.0 (Team, N seats)`

DELIVERABLES:
- All Tier 2 features from BRD (FR-01 through FR-27)
- 48 tests passing
- Docker self-hosted deploy working
- DeepSeek QA report with all findings patched
- v1.0.0 tagged, pushed, published

CONSTRAINTS:
- execute_code tool is blocked → use terminal() with PYTHONPATH=src python3 -c "..."
- Don't break MIT user experience: Tier 2 only activates with license
- All data schema changes must be additive (no drops, no renames)
- The user expects checked-in evidence of QA, not just "it passed"

COPY THIS PROMPT INTO A NEW SESSION AND EXECUTE.
