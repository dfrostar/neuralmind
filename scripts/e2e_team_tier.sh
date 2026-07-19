#!/usr/bin/env bash
set -euo pipefail

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

export NEURALMIND_CONFIG_DIR="$TMP/config"
export NEURALMIND_DATA_DIR="$TMP/data"
export NEURALMIND_TIER2_TEST=1

mkdir -p "$NEURALMIND_CONFIG_DIR" "$NEURALMIND_DATA_DIR"

PASS=0
PASS_FAIL=0

ok() { echo "  PASS  $((++PASS))  $1"; }
bad() { echo "  FAIL  $1"; PASS_FAIL=$((PASS_FAIL + 1)); }

NM="python3 -m neuralmind.cli"

# 1. governance status — should print JSON
echo "[1] neuralmind team governance status"
out="$($NM team governance status --json 2>&1)" || true
echo "$out" | python3 -c "import sys,json; d=json.load(sys.stdin); assert 'enabled' in d" && ok "governance status json" || bad "governance status json"

# 2. license activate — writes test license.json
echo "[2] neuralmind team license activate TEST-KEY-12345"
$NM team license activate TEST-KEY-12345
test -f "$NEURALMIND_CONFIG_DIR/license.json" && ok "license.json written" || bad "license.json not written"

# 3. license status
echo "[3] neuralmind team license status"
out="$($NM team license status --json 2>&1)" || true
echo "$out" | python3 -c "import sys,json; d=json.load(sys.stdin); assert 'status' in d" && ok "license status" || bad "license status"

# 4. seats add <EMAIL>
echo "[4] neuralmind team seats add <EMAIL>"
$NM team seats add '<EMAIL>' --admin '<EMAIL>'
ok "seat add"

# 5. seats list — shows alice
echo "[5] neuralmind team seats list"
out="$($NM team seats list 2>&1)" || true
echo "$out" | grep -qi "alice" && ok "seats list shows alice" || bad "seats list missing alice"

# 6. seats list --json
echo "[6] neuralmind team seats list --json"
out="$($NM team seats list --json 2>&1)" || true
echo "$out" | python3 -c "import sys,json; d=json.load(sys.stdin); assert any('alice' in s['email'] for s in d)" && ok "seats list json" || bad "seats list json"

# 7. audit list — has events
echo "[7] neuralmind team audit list"
out="$($NM team audit list 2>&1)" || true
echo "$out" | grep -qiE "alice|seat_add|license_activate" && ok "audit list shows events" || bad "audit list empty"

# 8. audit list --json
echo "[8] neuralmind team audit list --json"
out="$($NM team audit list --json 2>&1)" || true
echo "$out" | python3 -c "import sys,json; d=json.load(sys.stdin); assert len(d) > 0" && ok "audit list json" || bad "audit list json"

# 9. audit verify
echo "[9] neuralmind team audit verify"
$NM team audit verify
ok "audit verify"

# 10. self-hosted init
echo "[10] neuralmind team self-hosted init --data-dir $NEURALMIND_DATA_DIR"
$NM team self-hosted init --data-dir "$NEURALMIND_DATA_DIR"
test -d "$NEURALMIND_DATA_DIR" && ok "self-hosted data dir created" || bad "self-hosted data dir missing"
mode="$(stat -c '%a' "$NEURALMIND_DATA_DIR")"
[ "$mode" = "700" ] && ok "data dir mode 700" || bad "data dir wrong mode ($mode)"

# 11. self-hosted status
echo "[11] neuralmind team self-hosted status"
out="$($NM team self-hosted status --json 2>&1)" || true
echo "$out" | python3 -c "import sys,json; d=json.load(sys.stdin); assert 'self_hosted' in d" && ok "self-hosted status" || bad "self-hosted status"

# 12. neuralmind doctor
echo "[12] neuralmind doctor"
$NM doctor
ok "doctor"

# 13. governance set-scope personal
echo "[13] neuralmind team governance set-scope personal"
$NM team governance set-scope personal --admin '<EMAIL>'
out="$($NM team governance status --json)" || true
echo "$out" | grep -q '"personal"' && ok "scope updated to personal" || bad "scope not updated"

echo ""
echo "============================================================"
echo "PASS: $PASS   FAIL: $PASS_FAIL"
echo "============================================================"
[ "$PASS_FAIL" = 0 ]
