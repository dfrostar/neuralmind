#!/usr/bin/env bash
# One-command self-hosted deployment for NeuralMind Team tier.
set -euo pipefail

echo "=== NeuralMind Team — Self-Hosted Deploy ==="

INSTALL_DIR="${1:-$HOME/neuralmind-team}"
mkdir -p "$INSTALL_DIR"
cd "$INSTALL_DIR"

# Fetch docker-compose.yml if not present
if [ ! -f docker-compose.yml ]; then
    echo "[1/4] Downloading docker-compose.yml..."
    curl -fsSL "https://raw.githubusercontent.com/dfrostar/neuralmind/main/docker-compose.yml" -o docker-compose.yml
fi

if [ ! -f license.json ]; then
    echo "[2/4] Creating placeholder license.json..."
    cat > license.json <<'EOF'
{
  "tier": "team",
  "seats": 5,
  "issued_at": "2026-07-19T00:00:00Z",
  "expires_at": "2027-07-19T00:00:00Z",
  "issued_to": "self-hosted-install",
  "signature": "placeholder-replace-with-real-license"
}
EOF
    echo "  Replace license.json with your real license before starting."
fi

echo "[3/4] Starting NeuralMind..."
docker compose pull
docker compose up -d

echo "[4/4] Checking the image runs..."
# The service has no long-running process yet: the image's default command is
# `neuralmind --help`, which exits (docs/specs/LOCAL-API-SPEC.md, finding A7),
# so there is no server to wait for. Check that the CLI runs in the image, in a
# one-off container, and stop here if it doesn't. Not `neuralmind doctor`: it
# exits 1 while the mounted project has no built graph or index.
docker compose run --rm -T neuralmind neuralmind --version

echo ""
echo "=== Deployment complete ==="
echo "  Web UI:  http://127.0.0.1:8765"
echo "  License: $INSTALL_DIR/license.json"
echo "  Data:    docker volume neuralmind_neuralmind-data"
