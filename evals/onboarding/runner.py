"""Onboarding-lift eval runner — CLI entry (E1.5).

``--selfcheck`` validates the committed team baseline + the gold set + the
harness math with **no heavy deps** (stdlib only), so CI can confirm the eval
is wired before the full A/B runs. ``--run`` executes the real cold-vs-onboarded
A/B (needs chromadb + a built index) and prints the lift report.

Pure standard library at import time; the heavy A/B machinery is imported lazily
by ``--run``.
"""

from __future__ import annotations

import sys
from pathlib import Path


def _import_harness():
    try:
        from . import harness
    except ImportError:
        # Allow running as a plain script: put the repo root on the path.
        sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
        from evals.onboarding import harness  # type: ignore[no-redef]
    return harness


def _arg_value(argv: list[str], flag: str) -> str | None:
    if flag in argv:
        i = argv.index(flag)
        if i + 1 < len(argv):
            return argv[i + 1]
    return None


def _selfcheck() -> int:
    """Validate the seed history, gold set, and harness math offline.

    Uses stub providers (cold sees nothing; onboarded sees a perfect answer) so
    the A/B + report machinery is exercised with no chromadb — the lift must be
    strictly positive and the cold arm zero.
    """
    harness = _import_harness()

    seed = harness.load_seed_history()
    qs = harness.load_query_set()
    print(
        f"loaded seed history: {len(seed.sessions)} sessions x{seed.repeats} "
        f"= {seed.total_activations} activations; fixture {seed.fixture}"
    )
    print(f"loaded query set: {len(qs)} queries; fixture {qs.fixture}")

    def cold(_q):
        return ""

    def onboarded(q):
        # A "perfect" onboarded answer names every gold fact for the query.
        return " ".join(f.fact for f in q.expected_facts)

    def onboarded_retrieval(q):
        # A "perfect" onboarded top-k surfaces every expected module.
        return " ".join(q.expected_modules)

    results = harness.run_ab(
        qs,
        seed=seed,
        cold_provider=cold,
        onboarded_provider=onboarded,
        cold_retrieval=cold,
        onboarded_retrieval=onboarded_retrieval,
    )
    report = harness.build_report(qs, results, seed=seed)
    print(
        f"stub onboarding lift (top-k hit-rate): {report.onboarding_lift:+.3f} "
        f"(cold {report.cold_mean_hit_rate:.3f} -> onboarded "
        f"{report.onboarded_mean_hit_rate:.3f}); fact-recall lift "
        f"{report.recall_lift:+.3f}"
    )
    ok = (
        report.onboarding_lift > 0
        and report.cold_mean_hit_rate == 0.0
        and report.recall_lift > 0
        and report.cold_mean_recall == 0.0
    )
    print("ok" if ok else "WARN: stub lift not as expected")
    return 0 if ok else 1


def _run(argv: list[str]) -> int:
    """Run the real cold-vs-onboarded A/B and print the lift report."""
    harness = _import_harness()
    try:
        report = harness.run_and_report(_arg_value(argv, "--project"))
    except RuntimeError as exc:
        print(f"onboarding A/B unavailable: {exc}", file=sys.stderr)
        print(
            "Run with --selfcheck to validate the seed history + scorer without "
            "the retrieval stack.",
            file=sys.stderr,
        )
        return 2
    print(harness.render_json(report) if "--json" in argv else harness.render_markdown(report))
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if "--selfcheck" in argv:
        return _selfcheck()
    if "--run" in argv:
        return _run(argv)

    print("Onboarding-lift eval. Usage:")
    print("  --selfcheck            validate the team baseline + gold set + scorer (no deps)")
    print("  --run [--project P]    run the cold-vs-onboarded A/B + lift report")
    print("  --run --json           emit the report as JSON")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
