"""Retrieval-quality eval suite (PRD 2).

Measures whether NeuralMind retrieves the *right* code, not just *less* of it:
precision@k / recall@k / MRR / answerability over golden query sets, with a
CI regression gate and baseline comparison. Pure metrics live in
``neuralmind.quality``; this package wires them to real retrieval over the
committed polyglot fixtures (Python / TypeScript / Go).

Run from the source repo root:

    python -m evals.quality.runner --selfcheck       # deps-free gate
    python -m evals.quality.runner --run             # all suites
    python -m evals.quality.runner --run --suite go  # one suite
"""
