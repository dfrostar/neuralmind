"""Measure `neuralmind review` and `neuralmind drift` on real commits.

Pre-registered in ``docs/specs/REVIEW-DRIFT-EVAL-SPEC.md``. Three steps, each
a module with a ``main``:

    python -m evals.review_drift.select --repos <dir> --out <dir>/sets.json
    python -m evals.review_drift.run --sets <dir>/sets.json --out <dir> \\
        --neuralmind <venv>/bin/neuralmind
    python -m evals.review_drift.analyze <dir>

``select`` picks commits mechanically; ``run`` builds a cold index at each
parent commit and records what the two commands and the baselines say;
``analyze`` applies the spec's endpoints and decision rule. Stdlib only: the
commands under test run as subprocesses of the given ``neuralmind`` binary.
"""
