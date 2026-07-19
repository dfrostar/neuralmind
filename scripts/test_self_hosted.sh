#!/usr/bin/env bash
# test_self_hosted.sh — Docker self-hosted test.
#
# Spins up a minimal docker-compose.yml with a neuralmind service, waits for
# healthy, runs `neuralmind doctor` inside the container, then tears down.
# Skips cleanly (exit 0) when docker/docker compose are unavailable.

set -euo pipefail

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# --- Check docker availability ------------------------------------------------
if ! command -v docker >/dev/null 2>&1; then
    echo "Docker not available (docker binary missing). SKIP."
    exit 0
fi

# Prefer "docker compose v2" CLI plugin; fall back to docker-compose v1
if docker compose version >/dev/null 2>&1; then
    COMPOSE="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
    COMPOSE="docker-compose"
else
    echo "Docker not available (no docker compose plugin). SKIP."
    exit 0
fi

# Verify daemon connectivity (avoids hanging on a broken install)
if ! docker info >/dev/null 2>&1; then
    echo "Docker not available (daemon unreachable). SKIP."
    exit 0
fi

cd "$TMP"

# --- Write minimal docker-compose.yml ------------------------------------------
cat > docker-compose.yml <<'YAMLEOF'
version: "3.8"

services:
  neuralmind:
    image: python:3.12-slim
    container_name: neuralmind-selfhosted-test
    working_dir: /app
    # Mount the repo so we can install from source without publish
    volumes:
      - ..:/app:rw
    environment:
      - NEURALMIND_SELF_HOSTED=true
      - NEURALMIND_CONFIG_DIR=/app/.test-config
      - NEURALMIND_DATA_DIR=/app/.test-data
    # Install neuralmind in editable mode with a test license fixture
    command: >
      bash -lc '
        set -e
        pip install -e /app >/dev/null 2>&1
        echo "NEURALMIND container ready"
        neuralmind doctor || true
        echo "Running neuralmind doctor inside container..."
        neuralmind doctor
        echo "Container-level self-hosted test PASSED"
      '
    healthcheck:
      test: ["CMD", "python3", "--version"]
      interval: 10s
      timeout: 3s
      retries: 3
YAMLEOF

# --- Write test license fixture ------------------------------------------------
mkdir -p "$TMP/.test-config"
cat > "$TMP/.test-config/license.json" <<'JSONEOF'
{
  "tier": "team",
  "seats": 5,
  "issued_at": "2026-07-19T00:00:00Z",
  "expires_at": "2027-07-19T00:00:00Z",
  "issued_to": "docker-selfhosted-test",
  "signature": "test-signature-placeholder"
}
JSONEOF

# --- Bring up, run doctor, tear down -------------------------------------------
echo "==> Starting docker self-hosted test in $TMP"
$COMPOSE up -d

echo "==> Waiting for container healthy..."
for i in $(seq 1 30); do
    state="$($COMPOSE ps --format json 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('State',''))" 2>/dev/null || echo "unknown")"
    health="$($COMPOSE ps --format json 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('Health',''))" 2>/dev/null || echo "unknown")"
    if [ "$state" = "running" ] || [ "$health" = "healthy" ]; then
        echo "Container state=$state health=$health — ready."
        break
    fi
    sleep 2
done

echo "==> Running neuralmind doctor inside container ($COMPOSE exec)..."
set +e
$COMPOSE exec neuralmind neuralmind doctor
DOCER_EXIT=$?
set -e

if [ "$DOCER_EXIT" = 0 ]; then
    echo "==> neuralmind doctor: PASSED"
else
    echo "==> neuralmind doctor: FAILED (exit $DOCER_EXIT)"
fi

# Also test the team self-hosted command surface
echo "==> Running team self-hosted init..."
set +e
$COMPOSE exec neuralmind neuralmind team self-hosted init --data-dir /app/.test-data
SH_INIT_EXIT=$?
set -e
[ "$SH_INIT_EXIT" = 0 ] && echo "==> team self-hosted init: PASSED" || echo "==> team self-hosted init: FAILED (exit $SH_INIT_EXIT)"

echo "==> Tearing down..."
$COMPOSE down --timeout 10

# Final verdict
TOTAL_FAIL=0
[ "$DOCER_EXIT" != 0 ] && TOTAL_FAIL=$((TOTAL_FAIL + 1))
[ "$SH_INIT_EXIT" != 0 ] && TOTAL_FAIL=$((TOTAL_FAIL + 1))

echo ""
echo "============================================================"
echo "Docker self-hosted test complete: $TOTAL_FAIL failures"
echo "============================================================"
exit "$TOTAL_FAIL"
