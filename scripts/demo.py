"""30-second NeuralMind demo on the bundled sample fixture.

Runs three pre-canned questions against ``tests/fixtures/sample_project/``
and prints a punchy before/after report. Designed as the first thing a
repo evaluator runs after cloning — proves the headline reduction claim
on real code in under a minute.

Prerequisites the wrapper script (``scripts/demo.sh``) sets up for you:
    pip install -e . tiktoken graphifyy
    graphify update tests/fixtures/sample_project
    neuralmind build tests/fixtures/sample_project --force

Run directly:
    python -m scripts.demo
    python scripts/demo.py

If you've installed neuralmind from PyPI and just want the demo, run
``neuralmind demo`` — it ships its own bundled fixture and graph.json
and doesn't require this script or a git checkout.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "sample_project"


def _die(msg: str, hint: str = "") -> None:
    print(f"\n[demo] {msg}", file=sys.stderr)
    if hint:
        print(f"[demo] {hint}", file=sys.stderr)
    sys.exit(1)


def _check_prereqs() -> None:
    if not FIXTURE_DIR.exists():
        _die(
            f"Fixture not found at {FIXTURE_DIR}",
            "Run this from a NeuralMind git checkout, or use `bash scripts/demo.sh`. "
            "If you installed from PyPI, run `neuralmind demo` instead.",
        )
    try:
        import neuralmind  # noqa: F401
    except ImportError:
        _die(
            "neuralmind is not installed.",
            "Run `pip install -e .` from the repo root, then re-run.",
        )


def _ensure_built() -> None:
    """Verify the fixture has been built. Don't auto-build — that needs
    graphify, which the wrapper script handles. Failing here with a clear
    pointer is friendlier than half-running and crashing inside chromadb.
    """
    db_dir = FIXTURE_DIR / "graphify-out" / "neuralmind_db"
    graph_path = FIXTURE_DIR / "graphify-out" / "graph.json"
    if not graph_path.exists():
        _die(
            "Knowledge graph missing.",
            "Run `bash scripts/demo.sh` once to install graphify and build the index.",
        )
    if not db_dir.exists():
        _die(
            "Vector index not built yet.",
            f"Run `neuralmind build {FIXTURE_DIR} --force` and try again.",
        )


def main() -> int:
    _check_prereqs()
    _ensure_built()

    from neuralmind import _demo_report

    return _demo_report.run_demo_report(
        FIXTURE_DIR,
        header_label="tests/fixtures/sample_project",
    )


if __name__ == "__main__":
    raise SystemExit(main())
