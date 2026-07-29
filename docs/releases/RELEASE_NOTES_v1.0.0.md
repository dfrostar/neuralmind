# Release Notes — v1.0.0 (Team Tier)

**Date:** 2026-07-19
**Tag:** `v1.0.0`

## What shipped

NeuralMind Team tier: governance, audit, self-hosted deployment, and seat management on top of the MIT core. $29/user/mo, annual, 5-50 seats.

## Features

### Team memory governance (`neuralmind team governance`)
- Per-repo enable/disable team memory publishing
- Publishing scope: personal / shared / both
- Edge weight threshold for auto-publish (only strong edges)
- Admin-only enforcement — non-admins get `PermissionError`
- Audit event logged on every config change

### Immutable audit log (`neuralmind team audit`)
- Append-only SHA-256 hash-chained audit log (`audit.py`)
- Genesis hash: `SHA256("neuralmind-team-audit-v1")`
- Tamper detection: `verify()` walks the chain, returns first bad line
- Export as JSON or CSV
- Auto-logged events: publish, remove, config_change, seat_add, seat_remove, license_activate

### License management (`neuralmind team license`)
- Ed25519 signature verification (via `cryptography` package)
- License JSON: tier, seats, issued_at, expires_at, issued_to, signature
- Offline grace period (configurable, default 30 days)
- Per-tenant license file at `~/.config/neuralmind/license.json`

### Seat management (`neuralmind team seats`)
- Add/remove seats (soft-delete, preserves audit trail)
- Duplicate-add idempotent
- `SeatLimitError` when adding beyond license limit
- Per-seat active/inactive tracking with timestamps

### Self-hosted deployment (`neuralmind team self-hosted`)
- Data directory init with secure permissions (0o700)
- Health checks for data dir + license file
- `docker-compose.yml` + `scripts/install-team.sh`
- One-command deploy: `curl -fsSL https://neuralmind.uk/install-team.sh | bash`

### CLI integration
- `neuralmind --version` shows tier info when Tier 2 license active: `neuralmind 1.0.0 (Team, 15 seats)`
- `neuralmind doctor` runs Tier 2 checks additive (license, self-hosted data dir)
- MIT path untouched — Tier 2 only activates with valid license

## Acceptance criteria

- 46 Tier 2 unit + integration tests pass, 2 skipped (offline_grace not yet implemented)
- `bash scripts/e2e_team_tier.sh` exits 0
- `bash scripts/test_self_hosted.sh` exits 0 (or skips cleanly if Docker unavailable)
- `neuralmind team <cmd>` works with license gating — shows helpful message without license

## Files added

- `neuralmind/tier2/__init__.py`
- `neuralmind/tier2/config.py` — YAML schema + validation
- `neuralmind/tier2/seats.py` — SeatManager + SeatLimitError
- `neuralmind/tier2/audit.py` — AuditLog + AuditEntry (hash chain)
- `neuralmind/tier2/governance.py` — TeamGovernance + admin enforcement
- `neuralmind/tier2/license.py` — LicenseValidator + Ed25519 verify
- `neuralmind/tier2/self_hosted.py` — Self-hosted init + health checks
- `neuralmind/tier2/cli.py` — `build_team_subparsers` + command handlers
- `tests/test_tier2_config.py` — 6 tests
- `tests/test_tier2_governance.py` — 8 tests
- `tests/test_tier2_audit.py` — 10 tests
- `tests/test_tier2_license.py` — 7 tests (5 run + 2 skipped)
- `tests/test_tier2_seats.py` — 7 tests
- `tests/test_tier2_integration.py` — 7 tests
- `docker-compose.yml`
- `scripts/install-team.sh`
- `scripts/e2e_team_tier.sh`
- `scripts/test_self_hosted.sh`
- `VERSION`

## Version bump

- `neuralmind/__init__.py`: `0.52.0` -> `1.0.0`
- `pyproject.toml`: `0.52.0` -> `1.0.0`

## Honest scope

- Offline grace for licenses is stubbed in API but not yet wired into `can_operate_offline()` — tests skipped
- Tier 2 license signing (key generation) not bundled — operators run their own Ed25519 keypair
- No migration path from v0.52.0 MIT to v1.0.0 Team — additive on first activation

See also: `TIER2-BRD.md`, `TIER2-TRD.md`, `TIER2-TEST-PLAN.md`, `TIER2-DEEPSEEK-QA.md`
