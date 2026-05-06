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
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = REPO_ROOT / "tests" / "fixtures" / "sample_project"

# Three questions chosen to span the fixture: a cross-file flow, a
# focused single-module question, and a relationship question. Different
# shapes exercise different layers of the retrieval pipeline.
DEMO_QUERIES: list[tuple[str, str]] = [
    ("auth-flow", "How does authentication work in this codebase?"),
    ("api-endpoints", "What are the main API endpoints?"),
    ("billing-flow", "Explain the billing flow from a user perspective."),
]

# Claude 3.5 Sonnet input price per 1M tokens, used for the dollar
# estimate. Mirrors the constant of the same name in
# ``tests/benchmark/run.py`` so the demo and the CI self-benchmark
# report agreeing dollar figures. If you change the pricing here you
# MUST change it there too — search the repo for
# ``CLAUDE_SONNET_INPUT_PER_MTOK`` to find both call sites.
CLAUDE_SONNET_INPUT_PER_MTOK = 3.0
QUERIES_PER_DAY = 100


def _die(msg: str, hint: str = "") -> None:
    print(f"\n[demo] {msg}", file=sys.stderr)
    if hint:
        print(f"[demo] {hint}", file=sys.stderr)
    sys.exit(1)


def _check_prereqs() -> None:
    if not FIXTURE_DIR.exists():
        _die(
            f"Fixture not found at {FIXTURE_DIR}",
            "Run this from a NeuralMind git checkout, or use `bash scripts/demo.sh`.",
        )
    try:
        import tiktoken  # noqa: F401
    except ImportError:
        _die(
            "tiktoken is not installed.",
            "Run `bash scripts/demo.sh` (handles install) or `pip install tiktoken`.",
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


def _naive_baseline_tokens(enc) -> int:
    """Concatenate every .py file in the fixture; the worst-case 'load
    the whole repo' token count NeuralMind is pitched against."""
    total = 0
    for py_file in sorted(FIXTURE_DIR.rglob("*.py")):
        total += len(enc.encode(py_file.read_text()))
    return total


def _hr() -> str:
    return "─" * 68


def main() -> int:
    _check_prereqs()
    _ensure_built()

    import tiktoken

    from neuralmind import NeuralMind

    # Match the self-benchmark's tokenizer so the demo number agrees
    # with the CI number a reader sees on PRs. Mirrors the fallback
    # chain in tests/benchmark/run.py: tiktoken downloads its vocab
    # from an Azure blob the first time it's used, which fails in
    # restricted networks (corporate firewalls, air-gapped CI) and on
    # transient blob 5xx errors. Try modern → older → character-based
    # approximation so the demo always produces a directional number.
    enc = None
    for encoding_name in ("o200k_base", "cl100k_base"):
        try:
            candidate = tiktoken.get_encoding(encoding_name)
            candidate.encode("probe")
            enc = candidate
            break
        except Exception:
            continue

    if enc is None:
        # Both tiktoken encodings unreachable — fall back to a ~4
        # chars/token approximation. Crude but unblocks the demo on
        # restricted networks; both sides of the comparison use the
        # same approximation so the *ratio* stays directionally correct.
        class _CharApproxEncoding:
            def encode(self, text: str) -> list[int]:
                return [0] * max(1, len(text) // 4)

        enc = _CharApproxEncoding()
        print(
            "[demo] tiktoken vocab download blocked — using ~4 chars/token "
            "approximation. Ratios stay directional; absolute counts are rough."
        )

    print()
    print(_hr())
    print(" NeuralMind 30-second demo  —  fixture: tests/fixtures/sample_project")
    print(_hr())
    print(" Three real questions. Naive baseline = every .py file concatenated.")
    print(" NeuralMind output = what a coding agent actually sees.")
    print()

    naive_total = _naive_baseline_tokens(enc)

    nm = NeuralMind(str(FIXTURE_DIR))

    rows = []
    t0 = time.time()
    for qid, question in DEMO_QUERIES:
        ctx = nm.query(question)
        after_tokens = len(enc.encode(ctx.context))
        ratio = naive_total / max(after_tokens, 1)
        rows.append((qid, question, naive_total, after_tokens, ratio))
        print(f"  Q: {question}")
        print(
            f"     naive = {naive_total:>5,} tok   "
            f"neuralmind = {after_tokens:>4,} tok   "
            f"reduction = {ratio:>5.1f}×"
        )
        print()
    elapsed = time.time() - t0

    avg_after = sum(r[3] for r in rows) // len(rows)
    avg_ratio = sum(r[4] for r in rows) / len(rows)

    # Per-query input cost at Claude 3.5 Sonnet pricing, scaled to a
    # 100-query/day workload. Conservative — output tokens unchanged.
    # Clamp at 0 because on a contrived input where retrieval renders
    # more tokens than the naive baseline (small fixtures + heavy L1
    # boilerplate, retrieval regression, etc.), printing a negative
    # "saved" dollar amount is more confusing than informative.
    per_query_savings = (naive_total - avg_after) / 1_000_000 * CLAUDE_SONNET_INPUT_PER_MTOK
    monthly_saved = max(0.0, per_query_savings * QUERIES_PER_DAY * 30)

    print(_hr())
    print(f"  Average reduction:   {avg_ratio:.1f}×  across {len(rows)} queries")
    print(f"  Avg context size:    {avg_after:,} tokens  (vs {naive_total:,} naive)")
    print(
        f"  Est. monthly saved:  ~${monthly_saved:,.2f}  "
        f"@ {QUERIES_PER_DAY} queries/day on Claude 3.5 Sonnet"
    )
    print(f"  Wall time:           {elapsed:.2f}s")
    print(_hr())
    print()
    print(" The fixture is intentionally small (~500 lines).")
    print(" Real repos consistently hit 40–70× on the same pipeline.")
    print()
    print(" Try it on YOUR code:")
    print("   pip install neuralmind graphifyy")
    print("   cd /path/to/your-repo")
    print("   graphify update . && neuralmind build .")
    print("   neuralmind benchmark . --contribute")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
