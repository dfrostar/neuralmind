#!/bin/bash
# Publish skills/neuralmind/ to ClawHub (the OpenClaw skill registry).
#
# Why this exists: the ClawHub listing at clawhub.ai/dfrostar/skills/neuralmind
# was published once by hand on 2026-08-26 and never updated. It still serves
# the v3.4.1-era SKILL.md while the repo has moved on (v3.9.0 as of this
# writing) — see docs/wiki/Integration-Guide.md's OpenClaw section, which now
# documents that staleness as a known caveat for users. This script is the
# fix going forward: a single, auditable command instead of an unrepeated
# manual upload.
#
# This script is NOT wired into CI. Publishing to an external registry
# from an unattended pipeline needs the exact reusable-workflow contract
# (inputs, secret name, OIDC vs. static token) verified against a live
# account first — get that right once by running this manually, then wire
# a CI job with confidence. Until then, run it by hand on release.
#
# Requires:
#   - the `clawhub` CLI (https://docs.openclaw.ai/clawhub) on PATH
#   - CLAWHUB_TOKEN in the environment (`clawhub login` prints how to get one,
#     or generate one from your ClawHub account settings)
#
# Usage:
#   scripts/publish_clawhub.sh            # dry run — prints what would publish
#   scripts/publish_clawhub.sh --publish  # the real thing
#
# The version published is whatever skills/neuralmind/SKILL.md's frontmatter
# `version:` line says. That field is release-please-owned (see
# tests/test_skill_manifest.py) — never hand-edit it; it should already match
# .release-please-manifest.json by the time you run this.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
SKILL_DIR="$REPO_ROOT/skills/neuralmind"
SKILL_MD="$SKILL_DIR/SKILL.md"

if [ ! -f "$SKILL_MD" ]; then
  echo "error: $SKILL_MD not found — run this from a neuralmind checkout" >&2
  exit 1
fi

VERSION="$(grep -m1 '^version:' "$SKILL_MD" | sed -E 's/^version:\s*([0-9.]+).*/\1/')"
if [ -z "$VERSION" ]; then
  echo "error: could not read a version: line from $SKILL_MD" >&2
  exit 1
fi

if ! command -v clawhub >/dev/null 2>&1; then
  cat >&2 <<'EOF'
error: the `clawhub` CLI is not on PATH.
Install it per https://docs.openclaw.ai/clawhub, then re-run this script.
EOF
  exit 1
fi

DRY_RUN=1
if [ "${1:-}" = "--publish" ]; then
  DRY_RUN=0
fi

if [ "$DRY_RUN" -eq 1 ]; then
  echo "Dry run: would publish skills/neuralmind (SKILL.md version ${VERSION}) to ClawHub."
  echo "Nothing was sent. Re-run with --publish to actually do it."
  echo
  echo "Before you do, confirm CLAWHUB_TOKEN is set:"
  if [ -z "${CLAWHUB_TOKEN:-}" ]; then
    echo "  CLAWHUB_TOKEN is NOT set in this shell."
  else
    echo "  CLAWHUB_TOKEN is set (value not shown)."
  fi
  exit 0
fi

if [ -z "${CLAWHUB_TOKEN:-}" ]; then
  echo "error: --publish requires CLAWHUB_TOKEN in the environment." >&2
  echo "Run 'clawhub login' or set CLAWHUB_TOKEN from your ClawHub account settings." >&2
  exit 1
fi

echo "Publishing skills/neuralmind (SKILL.md version ${VERSION}) to ClawHub..."
clawhub skill publish "$SKILL_DIR" --version "$VERSION"
echo "Done. Verify at https://clawhub.ai/dfrostar/skills/neuralmind"
