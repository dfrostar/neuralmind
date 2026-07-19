# Tier 2 (Team) — Test Plan

**Product:** NeuralMind
**Tier:** Team ($29/user/mo, annual)
**Version:** v0.52.0 → v1.0.0
**Author:** Darren Frost
**Date:** 2026-07-19

---

## 1. Executive Summary

This test plan defines the acceptance criteria and verification strategy for NeuralMind Tier 2 (Team). Four layers: unit, integration, CLI e2e, and Docker self-hosted. DeepSeek QA gates methodology-encoding work.

---

## 2. Test Layers

| Layer | Tool | Goal |
|-------|------|------|
| **Unit** | pytest | 90%+ coverage on governance, audit, license, seats, config |
| **Integration** | pytest | synapses.db + audit.db interactions |
| **CLI e2e** | bash script | All Tier 2 CLI commands |
| **Docker self-hosted** | bash script | One-command deploy, data persistence, license |

---

## 3. Unit Tests

### 3.1 Governance (`tests/test_tier2_governance.py`)

| Test | Assertion |
|------|-----------|
| `test_governance_default_allows_publishing` | Default scope = "both", publishing allowed |
| `test_governance_disable_publishing` | Admin disables → publishing blocked |
| `test_governance_scope_personal_only` | Scope "personal" → no edges to shared |
| `test_governance_scope_shared_only` | Scope "shared" → only shared namespace published |
| `test_governance_weight_threshold` | Edges below threshold rejected |
| `test_governance_remove_edge` | Admin can remove edge from shared |
| `test_governance_idempotent_publish` | Same bundle twice → no duplicates |
| `test_governance_non_admin_cannot_modify` | Non-admin attempt raises PermissionError |

### 3.2 Audit Log (`tests/test_tier2_audit.py`)

| Test | Assertion |
|------|-----------|
| `test_audit_log_on_publish` | publish event logged with actor, ts, target |
| `test_audit_log_on_remove` | remove event logged with actor, ts, target |
| `test_audit_log_on_config_change` | config change logged with old+new values |
| `test_audit_log_immutable` | Attempting to edit/delete audit record raises error |
| `test_audit_log_export_json` | Export returns valid JSON with all records |
| `test_audit_log_export_csv` | Export returns valid CSV with header |
| `test_audit_log_filter_by_actor` | Filter by actor returns only that actor's records |
| `test_audit_log_filter_by_date` | Filter by date range returns correct window |
| `test_audit_log_filter_by_action` | Filter by action returns only matching records |
| `test_audit_log_tamper_detection` | Hash chain detects modified record |

### 3.3 License (`tests/test_tier2_license.py`)

| Test | Assertion |
|------|-----------|
| `test_license_valid` | Valid license returns VALID |
| `test_license_expired` | Expired license returns EXPIRED |
| `test_license_invalid_signature` | Tampered license returns INVALID |
| `test_license_offline_within_grace` | Offline < 30 days returns OFFLINE_OK |
| `test_license_offline_beyond_grace` | Offline > 30 days returns EXPIRED |
| `test_license_seat_limit` | License with N seats rejects seat N+1 |
| `test_license_tier_mismatch` | Enterprise license on Tier 2 returns INVALID |

### 3.4 Seats (`tests/test_tier2_seats.py`)

| Test | Assertion |
|------|-----------|
| `test_seats_add` | Admin can add seat up to license limit |
| `test_seats_remove` | Admin can remove seat |
| `test_seats_add_beyond_limit` | Adding beyond license limit raises SeatLimitError |
| `test_seats_list` | List returns all seats with status |
| `test_seats_is_active` | Active seat returns True |
| `test_seats_inactive_after_removal` | Removed seat returns False |
| `test_seats_duplicate_add` | Adding same email twice is idempotent |

### 3.5 Config (`tests/test_tier2_config.py`)

| Test | Assertion |
|------|-----------|
| `test_config_default_values` | Default config has expected values |
| `test_config_load_from_yaml` | Load returns Tier2Config |
| `test_config_save_roundtrip` | Save → load returns identical config |
| `test_config_invalid_scope` | Invalid scope raises ValidationError |
| `test_config_invalid_threshold` | Threshold > 1.0 raises ValidationError |
| `test_config_negative_half_life` | Negative half-life raises ValidationError |

---

## 4. Integration Tests

### 4.1 Synapses + Audit (`tests/test_tier2_integration.py`)

| Test | Assertion |
|------|-----------|
| `test_publish_creates_audit_record` | Publishing creates audit log entry |
| `test_remove_creates_audit_record` | Removing edge creates audit log entry |
| `test_governance_gates_publish` | Low-weight edge blocked by governance |
| `test_self_hosted_persists_across_restart` | Self-hosted mode restarts with data intact |
| `test_self_hosted_license_survives_restart` | License validation persists across restarts |
| `test_mit_user_unaffected` | MIT user (no license) has zero Tier 2 features |
| `test_team_memory_import_respects_governance` | Auto-import respects publishing scope |

---

## 5. CLI E2E Tests

### 5.1 Script: `scripts/e2e_team_tier.sh`

```bash
#!/usr/bin/env bash
# E2E test: Tier 2 Team commands
set -euo pipefail

echo "=== Tier 2 E2E ==="

# Setup
TMP=$(mktemp -d)
export NEURALMIND_CONFIG_DIR="$TMP/config"
export NEURALMIND_DATA_DIR="$TMP/data"

# License
neuralmind team license activate TEST-LICENSE-KEY-12345
neuralmind team license status

# Seats
neuralmind team seats add <EMAIL>
neuralmind team seats add <EMAIL>
neuralmind team seats list --json
neuralmind team seats remove <EMAIL>
neuralmind team seats list --json

# Governance
neuralmind team governance set-scope shared
neuralmind team governance set-weight-threshold 0.5
neuralmind team governance status
neuralmind team governance list-shared --json

# Audit
neuralmind team audit list --json
neuralmind team audit export --format csv --output "$TMP/audit.csv"
neuralmind team audit export --format json --output "$TMP/audit.json"

# Self-hosted
neuralmind team self-hosted init --data-dir "$TMP/data"
neuralmind team self-hosted status
neuralmind team self-hosted validate-license

# Doctor
neuralmind doctor

# Version shows tier
neuralmind --version

# Cleanup
rm -rf "$TMP"

echo "=== Tier 2 E2E PASS ==="
```

---

## 6. Docker Self-Hosted Tests

### 6.1 Script: `scripts/test_self_hosted.sh`

```bash
#!/usr/bin/env bash
# Self-hosted deployment test
set -euo pipefail

echo "=== Self-Hosted E2E ==="

TMP=$(mktemp -d)
cd "$TMP"

# One-command deploy
curl -fsSL https://neuralmind.uk/install-team.sh | bash

# Data persists across restart
docker compose down
docker compose up -d
sleep 5

# Health check passes
docker compose exec neuralmind neuralmind doctor

# License validation
docker compose exec neuralmind neuralmind team license status

# Web UI reachable
curl -sf http://127.0.0.1:8765/healthz

# Cleanup
docker compose down
rm -rf "$TMP"

echo "=== Self-Hosted E2E PASS ==="
```

---

## 7. Acceptance Criteria (summary)

| Feature | Acceptance Test | Pass Criteria |
|---------|-----------------|---------------|
| Team memory governance | `test_governance_*` | Admin can disable publishing, set weight threshold, view shared |
| Audit log | `test_audit_log_*` | Every publish/remove/config change logged; exportable as CSV/JSON |
| Self-hosted | `scripts/test_self_hosted.sh` | One-command deploy; data persists across restarts |
| Seat management | `test_seats_*` | Admin can add/remove seats; usage visible |
| License | `test_license_*` | Valid, expired, invalid, offline all handled correctly |
| Backward compat | `test_mit_user_unaffected` | MIT user sees zero changes |
| CLI e2e | `scripts/e2e_team_tier.sh` | All commands execute without error |

**Done definition:** All unit + integration tests pass, both e2e scripts exit 0, DeepSeek QA clean on methodology work.

---

## 8. DeepSeek QA Gate

DeepSeek review required on:

1. **Audit log hash chain** — verify SHA-256 chaining is correct, tamper detection works
2. **Governance publish gate** — verify edge weight comparison, no bypass paths
3. **License validation** — verify Ed25519 signature verification, offline grace logic
4. **Config schema** — verify pydantic validation covers all edge cases
5. **Self-hosted init** — verify data dir creation, file permissions, license file handling
6. **Publish idempotency** — verify content-hash gating works correctly under concurrency

Dispatch: one module at a time, inline code, patch critical+warnings.

---

## 9. Test Metrics

| Metric | Target |
|--------|--------|
| Unit test coverage | 90%+ |
| Integration test coverage | 80%+ |
| CLI e2e pass rate | 100% |
| Docker e2e pass rate | 100% |
| DeepSeek findings patched | 100% of CRITICAL + WARNING |

---

## 10. Summary of Test Files

| File | Tests |
|------|-------|
| `tests/test_tier2_governance.py` | 8 |
| `tests/test_tier2_audit.py` | 10 |
| `tests/test_tier2_license.py` | 7 |
| `tests/test_tier2_seats.py` | 7 |
| `tests/test_tier2_config.py` | 6 |
| `tests/test_tier2_integration.py` | 7 |
| `scripts/e2e_team_tier.sh` | 1 (CLI e2e) |
| `scripts/test_self_hosted.sh` | 1 (Docker e2e) |
| **Total** | **48** |

---

*Test Plan complete. Next: DeepSeek QA → Kickoff prompt.*
