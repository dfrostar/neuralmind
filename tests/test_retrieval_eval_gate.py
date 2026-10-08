"""The retrieval eval's paired keep rule (evals/retrieval/run.py). Stdlib-only."""

from __future__ import annotations

from evals.retrieval import run


def _results(base_ranks, cand_ranks, base_tokens=1000.0, cand_tokens=1000.0):
    return {
        repo: {
            "baseline": {"ranks": b, "avg_tokens": base_tokens},
            "cand": {"ranks": c, "avg_tokens": cand_tokens},
        }
        for repo, (b, c) in {
            "r1": (base_ranks[0], cand_ranks[0]),
            "r2": (base_ranks[1], cand_ranks[1]),
        }.items()
    }


def test_mcnemar_exact_matches_the_binomial_tail():
    assert run.mcnemar_exact(0, 0) == 1.0
    assert run.mcnemar_exact(5, 5) == 1.0
    # 10 wins, 1 loss: 2 * P(X <= 1 | n=11, p=.5) = 2 * 12 / 2048
    assert abs(run.mcnemar_exact(10, 1) - 24 / 2048) < 1e-12


def test_significant_gain_with_no_repo_dropping_is_kept():
    base = ([None] * 10 + [1] * 20, [1] * 30)
    cand = ([2] * 10 + [1] * 20, [1] * 30)
    g = run.gate(_results(base, cand), "cand")
    assert (g["wins"], g["losses"]) == (10, 0)
    assert g["keep"]
    assert g["mean_mrr_delta"] > 0


def test_a_gain_that_is_not_significant_is_not_kept():
    base = ([None, None, 1] + [1] * 27, [1] * 30)
    cand = ([1, 1, None] + [1] * 27, [1] * 30)
    g = run.gate(_results(base, cand), "cand")
    assert (g["wins"], g["losses"]) == (2, 1)
    assert not g["keep"]


def test_one_repo_dropping_three_questions_blocks_it():
    base = ([None] * 12 + [1] * 18, [1] * 30)
    cand = ([1] * 12 + [1] * 18, [None] * 3 + [1] * 27)
    g = run.gate(_results(base, cand), "cand")
    assert g["worst_repo_delta_questions"] == -3
    assert not g["keep"]


def test_more_than_ten_percent_more_tokens_blocks_it():
    base = ([None] * 12 + [1] * 18, [1] * 30)
    cand = ([1] * 30, [1] * 30)
    assert not run.gate(_results(base, cand, cand_tokens=1200.0), "cand")["keep"]


def test_bootstrap_interval_is_deterministic():
    diffs = [0.0, 0.5, -0.25, 1.0, 0.0]
    assert run.bootstrap_ci(diffs) == run.bootstrap_ci(diffs)
    lo, hi = run.bootstrap_ci(diffs)
    assert lo <= sum(diffs) / len(diffs) <= hi
