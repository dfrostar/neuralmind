#!/usr/bin/env bash
#
# benchmarks/run_all.sh — one-command runner for NeuralMind's benchmark harnesses.
#
# This is a thin sequencer over harnesses that already live under evals/, bench/,
# and tests/benchmark/. It runs each as its own process and stops on the first
# gate failure (set -e), so a non-zero exit means a real regression.
#
# Usage:
#   bash benchmarks/run_all.sh              # deterministic, offline, CI-gated suite
#   bash benchmarks/run_all.sh --public     # + public benchmark (clones pinned repos; needs network)
#   bash benchmarks/run_all.sh --competitor # + scored vs codebase-memory-mcp (needs that pip install)
#   bash benchmarks/run_all.sh --all        # everything except the opt-in LLM-judged arm
#
# The LLM-judged answerability arm is intentionally NOT run here: it needs
# ANTHROPIC_API_KEY, never runs in CI, and the recall table is byte-identical with
# or without it. Run it explicitly with:
#   neuralmind benchmark . --public --judge

set -euo pipefail

# Resolve the repo root from this script's location so it works from any CWD.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${REPO_ROOT}"

RUN_PUBLIC=0
RUN_COMPETITOR=0
PYTHON="${PYTHON:-python}"

for arg in "$@"; do
  case "${arg}" in
    --public)     RUN_PUBLIC=1 ;;
    --competitor) RUN_COMPETITOR=1 ;;
    --all)        RUN_PUBLIC=1; RUN_COMPETITOR=1 ;;
    -h|--help)
      sed -n '2,22p' "${BASH_SOURCE[0]}"
      exit 0
      ;;
    *)
      echo "unknown flag: ${arg} (try --help)" >&2
      exit 2
      ;;
  esac
done

run_step() {
  # run_step "<label>" <command...>
  local label="$1"; shift
  echo ""
  echo "=============================================================="
  echo ">> ${label}"
  echo "   \$ $*"
  echo "=============================================================="
  "$@"
}

# --- Deterministic, offline, CI-gated suite (always runs) --------------------
run_step "1/4  Token reduction + learning + synapse A/B (CI floor 4.0x)" \
  "${PYTHON}" -m tests.benchmark.run
run_step "2/4  Answer quality — faithfulness delta at matched budget" \
  "${PYTHON}" -m evals.faithfulness.runner --run
run_step "3/4  Onboarding lift — committed team memory" \
  "${PYTHON}" -m evals.onboarding.runner --run
run_step "4/4  Backend parity — turbovec vs ChromaDB + multi-language" \
  "${PYTHON}" -m evals.parity.run

# --- Opt-in: public benchmark on real OSS repos (network) --------------------
if [[ "${RUN_PUBLIC}" -eq 1 ]]; then
  run_step "public  Cost + recall vs full-file/ripgrep/vector-RAG on real repos" \
    "${PYTHON}" -m evals.public.run
fi

# --- Opt-in: scored competitor head-to-head ----------------------------------
if [[ "${RUN_COMPETITOR}" -eq 1 ]]; then
  if ! "${PYTHON}" -c "import codebase_memory_mcp" >/dev/null 2>&1; then
    echo "" >&2
    echo "competitor step needs the competitor installed:" >&2
    echo "  pip install codebase-memory-mcp==0.8.1" >&2
    exit 1
  fi
  run_step "competitor  Scored retrieval ranking vs codebase-memory-mcp 0.8.1" \
    "${PYTHON}" -m evals.public.competitor
fi

echo ""
echo "All requested benchmarks passed their gates."
