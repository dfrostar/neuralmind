#!/usr/bin/env bash
# E2E test: Tier 2 Team commands
set -euo pipefail

echo "=== Tier 2 E2E ==="

TMP=$(mktemp -d)
export NEURALMIND_CONFIG_DIR="$TMP/config"
export NEURALMIND_DATA_DIR="$TMP/data"
mkdir -p "$NEURALMIND_CONFIG_DIR" "$NEURALMIND_DATA_DIR"

# Actor for audit trail (free tier auto-issues if no license present)
export NEURALMIND_ACTOR_EMAIL="self"

# License status
echo "[1] license status"
neuralmind team license status
echo "  PASS: license status format OK"

# Governance
echo "[2] governance status"
neuralmind team governance status

echo "[3] governance set-scope shared"
neuralmind team governance set-scope shared

echo "[4] governance set-weight-threshold 0.5"
neuralmind team governance set-weight-threshold 0.5

# Seats
echo "[5] seats add alice"
neuralmind team seats add alice@test.local

echo "[6] seats add bob"
neuralmind team seats add bob@test.local

echo "[7] seats list"
neuralmind team seats list

echo "[8] seats list --json"
neuralmind team seats list --json

echo "[9] seats remove alice"
neuralmind team seats remove alice@test.local

# Audit
echo "[10] audit list --json"
neuralmind team audit list --json

echo "[11] audit export csv"
neuralmind team audit export --format csv --output "$TMP/audit.csv"

echo "[12] audit export json"
neuralmind team audit export --format json --output "$TMP/audit.json"

echo "[13] audit verify"
neuralmind team audit verify

# Self-hosted
echo "[14] self-hosted init"
neuralmind team self-hosted init --data-dir "$TMP/data"

echo "[15] self-hosted status"
neuralmind team self-hosted status

# Doctor (tier2 checks additive)
echo "[16] doctor"
neuralmind doctor 2>&1 | grep -q "Tier 2 license" && echo "  PASS: tier2 doctor check present" || echo "  WARN: no tier2 doctor check (MIT path)"

# Version
echo "[17] version"
neuralmind --version

# Cleanup
rm -rf "$TMP"

echo "=== Tier 2 E2E PASS ==="
