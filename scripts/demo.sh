#!/usr/bin/env bash
# 30-second NeuralMind demo on the bundled sample fixture.
#
# What it does:
#   1. Creates an isolated venv (.demo-venv/) so we don't touch your env.
#   2. Installs neuralmind + graphifyy + tiktoken into it.
#   3. Builds the knowledge graph and vector index for the bundled fixture.
#   4. Runs three real questions and prints a before/after report.
#
# Re-runs are fast — the venv and built index are reused.
#
# Usage:
#   bash scripts/demo.sh              # run the demo
#   bash scripts/demo.sh --clean      # delete .demo-venv and start fresh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV="${REPO_ROOT}/.demo-venv"
FIXTURE="${REPO_ROOT}/tests/fixtures/sample_project"
PYTHON="${PYTHON:-python3}"

if [[ "${1:-}" == "--clean" ]]; then
  echo "[demo] removing ${VENV} and built index"
  rm -rf "${VENV}" "${FIXTURE}/graphify-out"
  shift
fi

if [[ ! -d "${FIXTURE}" ]]; then
  echo "[demo] fixture not found at ${FIXTURE}" >&2
  echo "[demo] run this from a NeuralMind git checkout (the fixture isn't in the wheel)" >&2
  exit 1
fi

if ! command -v "${PYTHON}" >/dev/null 2>&1; then
  echo "[demo] ${PYTHON} not on PATH. Install Python 3.10+ or set PYTHON=/path/to/python" >&2
  exit 1
fi

if [[ ! -d "${VENV}" ]]; then
  echo "[demo] creating venv at ${VENV}"
  "${PYTHON}" -m venv "${VENV}"
fi

# shellcheck disable=SC1091
source "${VENV}/bin/activate"

# Marker file so re-runs skip the pip work entirely. First run takes
# ~30s; subsequent runs that hit this branch are instant. Use the
# venv's python explicitly via `python -m pip` rather than the bare
# `pip` shim — `set -e` would still fire on a shadowed pip, but this
# is one less thing that can go wrong on an oddly-configured shell.
INSTALL_MARKER="${VENV}/.deps-installed"
if [[ ! -f "${INSTALL_MARKER}" ]]; then
  echo "[demo] installing dependencies (~30s, first run only)"
  "${VENV}/bin/python" -m pip install --quiet --upgrade pip
  "${VENV}/bin/python" -m pip install --quiet -e "${REPO_ROOT}" tiktoken graphifyy
  touch "${INSTALL_MARKER}"
fi

if [[ ! -f "${FIXTURE}/graphify-out/graph.json" ]]; then
  echo "[demo] generating knowledge graph (graphify update)"
  ( cd "${FIXTURE}" && graphify update . >/dev/null )
fi

if [[ ! -d "${FIXTURE}/graphify-out/neuralmind_db" ]]; then
  echo "[demo] building vector index (neuralmind build)"
  neuralmind build "${FIXTURE}" --force >/dev/null
fi

# Hand off to the Python script — single source of truth for the report
# format so what a developer sees matches what CI publishes. Use the
# venv interpreter explicitly: `${PYTHON}` may point at a different
# install (e.g. when the user set PYTHON=/path/to/python to bootstrap
# the venv), but installs landed in `${VENV}` and we must run there.
exec "${VENV}/bin/python" "${REPO_ROOT}/scripts/demo.py"
