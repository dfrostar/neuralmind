"""The task-outcome benchmark's statistics, checked against hand-computed values.

The benchmark's verdict is only as good as these functions, so each is pinned
to a case small enough to work out on paper. Stdlib-only.
"""

from __future__ import annotations

import json

from evals.task_outcome import analyze, run


def test_wilcoxon_all_negative_is_one_over_two_to_the_n() -> None:
    # Five decreases: W+ = 0, and only the all-negative sign pattern gets there.
    result = analyze.wilcoxon_signed_rank([-1, -2, -3, -4, -5])
    assert result["w_plus"] == 0
    assert result["p_less"] == 1 / 32
    assert result["p_greater"] == 1.0


def test_wilcoxon_drops_zeros_and_averages_ties() -> None:
    result = analyze.wilcoxon_signed_rank([0, 2, -2, 3])
    # Ranks of |2|, |2|, |3| are 1.5, 1.5, 3; W+ = 1.5 + 3 = 4.5 of a possible 6.
    assert result["n"] == 3
    assert result["w_plus"] == 4.5
    # Every sign pattern's W+, enumerated by hand: only the all-positive one exceeds 4.5.
    patterns = [0, 1.5, 1.5, 3, 3, 4.5, 4.5, 6]
    assert result["p_less"] == sum(w <= 4.5 for w in patterns) / 8


def test_wilcoxon_symmetric_data_is_not_significant() -> None:
    result = analyze.wilcoxon_signed_rank([-1, 1, -2, 2, -3, 3])
    assert result["p_less"] > 0.5 and result["p_greater"] > 0.5


def test_mcnemar_exact_matches_binomial() -> None:
    assert analyze.mcnemar_exact(0, 5) == 2 * (1 / 32)
    assert analyze.mcnemar_exact(0, 0) == 1.0
    assert analyze.mcnemar_exact(3, 3) == 1.0


def test_bootstrap_is_seeded() -> None:
    values = [0.1, -0.2, -0.3, 0.05, -0.1]
    assert analyze.bootstrap_ci(values) == analyze.bootstrap_ci(values)


def _runs(costs_base: list[float], costs_nm: list[float], solved: bool = True) -> list[dict]:
    runs = []
    for i, (b, n) in enumerate(zip(costs_base, costs_nm, strict=True)):
        runs.append(
            {"task": f"t{i}", "arm": "baseline", "seed": 0, "cost_usd": b, "solved": solved}
        )
        runs.append(
            {"task": f"t{i}", "arm": "neuralmind", "seed": 0, "cost_usd": n, "solved": solved}
        )
    return runs


def test_decision_requires_every_condition() -> None:
    cheaper = analyze.analyze(_runs([1.0] * 8, [0.6] * 8))
    assert cheaper["decision"]["claim_supported"] is True

    no_change = analyze.analyze(_runs([1.0, 0.8, 1.2, 0.9], [1.1, 0.7, 1.3, 0.8]))
    assert no_change["decision"]["claim_supported"] is False

    runs = _runs([1.0] * 8, [0.6] * 8)
    for r in runs:  # cheaper, but NeuralMind solves nothing
        if r["arm"] == "neuralmind":
            r["solved"] = False
    worse = analyze.analyze(runs)
    assert worse["decision"]["cost_lower_p_lt_alpha"] is True
    assert worse["decision"]["solve_rate_not_worse"] is False
    assert worse["decision"]["claim_supported"] is False


def test_parse_stream_counts_exploration_before_the_first_edit() -> None:
    def tool(name: str) -> str:
        return json.dumps(
            {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": name}]}}
        )

    lines = [
        tool("Grep"),
        tool("Read"),
        tool("mcp__neuralmind__neuralmind_query"),
        tool("Edit"),
        tool("Read"),
        json.dumps(
            {
                "type": "result",
                "total_cost_usd": 0.42,
                "num_turns": 5,
                "usage": {"input_tokens": 10, "output_tokens": 20},
            }
        ),
    ]
    parsed = run.parse_stream(lines)
    assert parsed["explore_calls_before_first_edit"] == 3
    assert parsed["cost_usd"] == 0.42
    assert parsed["tool_counts"]["Read"] == 2
    assert parsed["edited"] is True


def test_plan_is_deterministic_and_complete() -> None:
    tasks = [{"id": "a"}, {"id": "b"}]
    first = run.plan(tasks, ("baseline", "neuralmind"), 3, order_seed=7)
    assert first == run.plan(tasks, ("baseline", "neuralmind"), 3, order_seed=7)
    assert len(first) == len(set(first)) == 12


def test_analyzer_refuses_an_incomplete_run_matrix() -> None:
    runs = _runs([1.0] * 4, [0.6] * 4)
    runs.append({"task": "t0", "arm": "baseline", "seed": 1, "cost_usd": 1.0, "solved": True})
    try:
        analyze.analyze(runs)
    except analyze.IncompleteRunsError as exc:
        assert "t0/neuralmind" in str(exc)
    else:
        raise AssertionError("a task with an extra baseline seed was analysed")


def test_a_run_without_a_cost_is_scored_at_its_budget_cap_and_unsolved() -> None:
    runs = _runs([1.0] * 8, [0.6] * 8)
    for r in runs:
        r["budget_usd"] = 2.0
    timed_out = next(r for r in runs if r["arm"] == "neuralmind")
    timed_out.update(cost_usd=None, timed_out=True)
    result = analyze.analyze(runs)
    assert result["cost"]["tasks_dearer_with_neuralmind"] == 1
    assert result["timed_out_runs"]["neuralmind"] == 1
    assert analyze.run_cost(timed_out) == 2.0


def test_harvest_enforces_the_pre_registered_gates() -> None:
    from evals.task_outcome import harvest

    ok = ["neuralmind/a.py"]
    assert harvest.eligible("fix: x", "2026-07-01T00:00:00+00:00", ok) is None
    assert "fix" in harvest.eligible("feat: x", "2026-08-01T00:00:00+00:00", ok)
    assert "before" in harvest.eligible("fix: x", "2026-06-30T23:59:59+00:00", ok)
    four = [f"neuralmind/{i}.py" for i in range(4)]
    assert "4 source" in harvest.eligible("fix: x", "2026-08-01T00:00:00+00:00", four)


def test_baseline_path_drops_directories_holding_neuralmind(tmp_path) -> None:
    import os

    nm_dir, other = tmp_path / "nm", tmp_path / "other"
    nm_dir.mkdir()
    other.mkdir()
    exe = nm_dir / "neuralmind"
    exe.write_text("#!/bin/sh\n")
    exe.chmod(0o755)
    assert run._clean_path(os.pathsep.join([str(nm_dir), str(other)])) == [str(other)]
