"""Quality eval harness: run retrieval over a golden suite and score it (PRD 2).

Lazily imports the embedding stack so the runner's ``--selfcheck`` stays
dependency-free. For each query it asks the real NeuralMind index for its
top-k ranked hits, projects them to source-file modules, and scores that
ranking against the suite's ``expected_modules`` with ``neuralmind.quality``.
"""

from __future__ import annotations

import contextlib
import json
import sys
from dataclasses import dataclass

from neuralmind import quality

from .runner import Suite, load_suite

# Retrieval depth fed to the metrics. The largest reported cutoff is 5, so 10
# hits give MRR room to find a relevant module past the top few.
SEARCH_K = 10
REPORT_KS = (1, 3, 5)

# Conservative CI floors — far below NeuralMind's real retrieval quality, so
# the gate catches genuine ranking regressions, not noise.
DEFAULT_THRESHOLDS = quality.QualityThresholds(
    min_mrr=0.5,
    min_answerability=0.7,
    min_recall_at_k=0.5,
    recall_k=5,
)


@dataclass
class SuiteReport:
    suite: quality.SuiteQuality
    failures: list[str]

    @property
    def passed(self) -> bool:
        return not self.failures


def _ranked_modules(nm, question: str, k: int) -> list[str]:
    """Top-k retrieved source-file modules, in rank order."""
    results = nm.search(question, n=k)
    return [
        str(r.get("metadata", {}).get("source_file", ""))
        for r in results
        if r.get("metadata", {}).get("source_file")
    ]


def run_suite(
    name: str,
    *,
    thresholds: quality.QualityThresholds | None = None,
    fixture_dir: str | None = None,
) -> SuiteReport:
    """Build the suite's fixture index, run every query, and score retrieval.

    ``fixture_dir`` overrides the suite's committed fixture path — tests pass a
    throwaway copy so the run never mutates a committed fixture or leaks build
    artifacts into the tree. Raises ``RuntimeError`` (deps / no built graph) so
    the CLI degrades gracefully; ``ValueError`` for an unknown/malformed suite.
    """
    suite: Suite = load_suite(name)
    thresholds = thresholds or DEFAULT_THRESHOLDS
    build_dir = fixture_dir or str(suite.fixture_dir)

    # Build + query with stdout redirected to stderr: the embedder prints graph
    # load / embedding progress (and a one-time model download bar) to stdout,
    # which would corrupt `--json`. Humans still see it on stderr; stdout stays
    # pure for machine consumption.
    with contextlib.redirect_stdout(sys.stderr):
        # Construct + build inside one guard: the embedding backend is imported
        # lazily at NeuralMind() construction (chromadb/turbovec), so a missing
        # stack surfaces here, not at the `import neuralmind` above. Convert any
        # such failure into a RuntimeError so the CLI degrades to a clean
        # message instead of a traceback.
        try:
            from neuralmind import NeuralMind
            from neuralmind.core import GraphNotBuiltError

            nm = NeuralMind(build_dir)
            build = nm.build()
            if not build.get("success", True):
                raise RuntimeError(build.get("error", "build failed"))
        except GraphNotBuiltError as exc:  # pragma: no cover - needs real env
            raise RuntimeError(
                f"no code graph for {build_dir}; run `neuralmind build` first ({exc})"
            ) from exc
        except RuntimeError:
            raise
        except Exception as exc:  # pragma: no cover - only without deps
            raise RuntimeError(
                f"the quality A/B needs the retrieval stack (chromadb/turbovec etc.) ({exc})"
            ) from exc

        per_query: list[quality.QueryQuality] = []
        for q in suite.queries:
            ranked = _ranked_modules(nm, q.question, SEARCH_K)
            per_query.append(quality.evaluate_query(q.id, ranked, q.expected_modules, ks=REPORT_KS))

    agg = quality.aggregate(name, per_query, ks=REPORT_KS)
    return SuiteReport(suite=agg, failures=thresholds.check(agg))


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #


def _suite_baseline(baseline: dict | None, suite_name: str) -> dict | None:
    """Resolve one suite's baseline metrics.

    Accepts either a flat ``{suite: metrics}`` mapping or the committed
    ``{"suites": {suite: metrics}, ...}`` wrapper (which also carries
    ``_comment`` / provenance). Returns ``None`` when the suite is absent so a
    partial baseline degrades gracefully.
    """
    if not baseline:
        return None
    suites = baseline.get("suites", baseline)
    entry = suites.get(suite_name)
    return entry if isinstance(entry, dict) else None


def render_json(reports: list[SuiteReport], baseline: dict | None = None) -> str:
    out: dict = {"suites": []}
    for rep in reports:
        entry = rep.suite.to_dict()
        entry["passed"] = rep.passed
        entry["failures"] = rep.failures
        base = _suite_baseline(baseline, rep.suite.suite)
        if base is not None:
            entry["baseline_deltas"] = [
                d.to_dict() for d in quality.compare_to_baseline(rep.suite, base)
            ]
        out["suites"].append(entry)
    out["passed"] = all(r.passed for r in reports)
    return json.dumps(out, indent=2)


def render_markdown(reports: list[SuiteReport], baseline: dict | None = None) -> str:
    lines = ["## NeuralMind retrieval-quality eval", ""]
    lines.append("| Suite | Queries | MRR | Answerability | Recall@5 | Precision@5 | Gate |")
    lines.append("|-------|--------:|----:|--------------:|---------:|------------:|:----:|")
    for rep in reports:
        s = rep.suite
        lines.append(
            f"| `{s.suite}` | {s.n_queries} | {s.mrr:.3f} | "
            f"{s.answerability:.0%} | {s.mean_recall.get(5, 0):.3f} | "
            f"{s.mean_precision.get(5, 0):.3f} | {'PASS' if rep.passed else 'FAIL'} |"
        )
    lines.append("")
    for rep in reports:
        if rep.failures:
            lines.append(f"**`{rep.suite.suite}` regressions:**")
            for f in rep.failures:
                lines.append(f"- {f}")
            lines.append("")
        base = _suite_baseline(baseline, rep.suite.suite)
        if base is not None:
            deltas = quality.compare_to_baseline(rep.suite, base)
            if deltas:
                lines.append(f"**`{rep.suite.suite}` vs baseline:**")
                for d in deltas:
                    # Treat sub-0.0005 movement as unchanged so display rounding
                    # never shows a misleading "▼ -0.000".
                    arrow = "▲" if d.delta > 5e-4 else ("▼" if d.delta < -5e-4 else "=")
                    lines.append(f"- {d.metric}: {d.current:.3f} ({arrow} {d.delta:+.3f})")
                lines.append("")
    lines.append(f"**Overall: {'PASS' if all(r.passed for r in reports) else 'FAIL'}**")
    return "\n".join(lines)


def emit(reports: list[SuiteReport], *, baseline: dict | None = None, as_json: bool = False) -> int:
    """Print a report and return an exit code (0 pass, 1 regression)."""
    print(render_json(reports, baseline) if as_json else render_markdown(reports, baseline))
    return 0 if all(r.passed for r in reports) else 1
