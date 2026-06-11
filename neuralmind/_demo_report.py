"""Shared demo report logic.

Single source of truth for the 30-second demo numbers, used by both the
``neuralmind demo`` CLI subcommand (works after ``pip install neuralmind``,
no git checkout required) and the ``scripts/demo.py`` script (developer
convenience inside the repo). Keep them in sync by routing through here.
"""

from __future__ import annotations

import time
from collections.abc import Iterable
from pathlib import Path

# Three questions chosen to span the fixture: a cross-file flow, a focused
# single-module question, and a relationship question. Different shapes
# exercise different layers of the retrieval pipeline.
DEMO_QUERIES: list[tuple[str, str]] = [
    ("auth-flow", "How does authentication work in this codebase?"),
    ("api-endpoints", "What are the main API endpoints?"),
    ("billing-flow", "Explain the billing flow from a user perspective."),
]

# Claude 3.5 Sonnet input price per 1M tokens. Mirrors the constant of
# the same name in tests/benchmark/run.py so the demo and the CI
# self-benchmark report agreeing dollar figures. If you change it here
# you MUST change it there too.
CLAUDE_SONNET_INPUT_PER_MTOK = 3.0
QUERIES_PER_DAY = 100


def get_encoding():
    """Pick a tiktoken encoding, falling back to a char-count approximation.

    Mirrors the fallback chain in tests/benchmark/run.py: tiktoken
    downloads its vocab from an Azure blob the first time it's used,
    which fails in restricted networks (corporate firewalls, air-gapped
    CI) and on transient blob 5xx errors. Try modern → older →
    character-based approximation so the demo always produces a
    directional number.

    Returns a tuple ``(encoding, used_fallback)`` so callers can warn the
    user when absolute counts are rough.
    """
    try:
        import tiktoken
    except ImportError:
        return _CharApproxEncoding(), True

    for name in ("o200k_base", "cl100k_base"):
        try:
            candidate = tiktoken.get_encoding(name)
            candidate.encode("probe")
            return candidate, False
        except Exception:
            continue

    return _CharApproxEncoding(), True


class _CharApproxEncoding:
    """~4 chars/token approximation. Both sides of the comparison use it,
    so the *ratio* stays directionally correct even when absolute counts
    are rough."""

    def encode(self, text: str) -> list[int]:
        return [0] * max(1, len(text) // 4)


def naive_baseline_tokens(fixture_dir: Path, enc) -> int:
    """Concatenate every .py file in the fixture; the worst-case
    'load the whole repo' token count NeuralMind is pitched against."""
    total = 0
    for py_file in sorted(fixture_dir.rglob("*.py")):
        total += len(enc.encode(py_file.read_text()))
    return total


def _hr() -> str:
    return "─" * 68


def run_demo_report(
    fixture_dir: Path,
    *,
    queries: Iterable[tuple[str, str]] = DEMO_QUERIES,
    header_label: str = "tests/fixtures/sample_project",
) -> int:
    """Run the demo queries against ``fixture_dir`` and print the report.

    Returns the process exit code (0 on success). The fixture must
    already have a ``graphify-out/graph.json`` and (after build) a
    ``neuralmind_db`` populated by NeuralMind.
    """
    from neuralmind import NeuralMind

    enc, used_fallback = get_encoding()
    if used_fallback:
        print(
            "[demo] tiktoken vocab download blocked — using ~4 chars/token "
            "approximation. Ratios stay directional; absolute counts are rough."
        )

    print()
    print(_hr())
    print(f" NeuralMind 30-second demo  —  fixture: {header_label}")
    print(_hr())
    print(" Three real questions. Naive baseline = every .py file concatenated.")
    print(" NeuralMind output = what a coding agent actually sees.")
    print()

    naive_total = naive_baseline_tokens(fixture_dir, enc)
    nm = NeuralMind(str(fixture_dir))

    rows = []
    t0 = time.time()
    for _qid, question in queries:
        ctx = nm.query(question)
        after_tokens = len(enc.encode(ctx.context))
        ratio = naive_total / max(after_tokens, 1)
        rows.append((question, naive_total, after_tokens, ratio))
        print(f"  Q: {question}")
        print(
            f"     naive = {naive_total:>5,} tok   "
            f"neuralmind = {after_tokens:>4,} tok   "
            f"reduction = {ratio:>5.1f}×"
        )
        print()
    elapsed = time.time() - t0

    avg_after = sum(r[2] for r in rows) // len(rows)
    avg_ratio = sum(r[3] for r in rows) / len(rows)

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
    print("   pip install neuralmind")
    print("   cd /path/to/your-repo")
    print("   neuralmind build .")
    print("   neuralmind benchmark . --contribute")
    print()
    return 0
