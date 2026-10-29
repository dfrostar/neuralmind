"""The task-outcome benchmark's statistics, checked against hand-computed values.

The benchmark's verdict is only as good as these functions, so each is pinned
to a case small enough to work out on paper. Stdlib-only.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from evals.task_outcome import analyze, hermes_sessions, run


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


def test_a_logged_out_cli_is_a_harness_failure_not_an_outcome() -> None:
    # What Claude Code 2.1.287 prints when it isn't logged in: a result event,
    # subtype "success", that ends on an API error before any model call.
    logged_out = json.dumps(
        {
            "type": "result",
            "subtype": "success",
            "is_error": True,
            "num_turns": 1,
            "total_cost_usd": 0,
            "terminal_reason": "api_error",
            "result": "Not logged in · Please run /login",
        }
    )
    assert run.harness_failure(run.parse_stream([logged_out]), timed_out=False)
    assert run.harness_failure(run.parse_stream([]), timed_out=False)
    assert not run.harness_failure(run.parse_stream([]), timed_out=True)

    # A run that hits --max-budget-usd is the agent's outcome, not a harness failure.
    capped = json.dumps(
        {
            "type": "result",
            "subtype": "error_max_budget_usd",
            "is_error": True,
            "num_turns": 30,
            "terminal_reason": "budget_exhausted",
        }
    )
    assert not run.harness_failure(run.parse_stream([capped]), timed_out=False)


def _hermes_event(kind: str, **fields) -> str:
    return json.dumps({"type": kind, **fields, "timestamp": 1793240324820})


def test_hermes_stream_counts_tools_and_reads_tokens() -> None:
    # The event shapes Hermes Agent v0.22.5 prints with `chat -Q --format stream-json`.
    lines = [
        _hermes_event("system", subtype="init", model="", session_id=""),
        _hermes_event("tool_use", name="search_files", tool_call_id="c1", input={}),
        _hermes_event("tool_result", name="search_files", tool_call_id="c1", output="{}"),
        _hermes_event("tool_use", name="read_file", tool_call_id="c2", input={}),
        _hermes_event("text", text="Fixing"),
        _hermes_event("tool_use", name="patch", tool_call_id="c3", input={}),
        _hermes_event("tool_use", name="terminal", tool_call_id="c4", input={}),
        _hermes_event(
            "result",
            session_id="local-abc",
            exit_code=0,
            text="Done",
            tokens={"input": 900, "output": 100, "total": 1000, "cache_read": 800},
            duration_ms=5000,
        ),
    ]
    parsed = run.parse_hermes_stream(lines)
    assert parsed["explore_calls_before_first_edit"] == 2
    assert parsed["edited"] is True
    assert parsed["tool_counts"] == {"search_files": 1, "read_file": 1, "patch": 1, "terminal": 1}
    assert parsed["total_tokens"] == 1000
    assert parsed["cost_usd"] is None
    assert parsed["session_id"] == "local-abc"
    assert not run.harness_failure(parsed, timed_out=False)
    # No result event: Hermes never got as far as the agent.
    assert run.harness_failure(run.parse_hermes_stream(lines[:-1]), timed_out=False)


def test_hermes_runs_get_no_mcp_and_no_memory(tmp_path) -> None:
    cmd = run.hermes_command("/bin/hermes", tmp_path / "p.txt", 40)
    assert cmd[cmd.index("-t") + 1] == "file,terminal,no_mcp"
    assert "--ignore-rules" in cmd
    assert cmd[cmd.index("--query-file") + 1] == str(tmp_path / "p.txt")


def _state_db(path, sessions=(), admissions=()):
    """A Hermes state.db cut down to the columns the runner reads."""
    import sqlite3

    db = sqlite3.connect(path)
    db.execute(
        "CREATE TABLE sessions (id TEXT, model TEXT, api_call_count INT, billing_base_url TEXT,"
        " input_tokens INT, output_tokens INT, cwd TEXT, started_at REAL, last_activity_at REAL)"
    )
    db.execute("CREATE TABLE session_admissions (target_session_id TEXT, status TEXT)")
    db.executemany("INSERT INTO sessions VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", sessions)
    db.executemany("INSERT INTO session_admissions VALUES (?, ?)", admissions)
    db.commit()
    db.close()
    return path


def test_hermes_session_reads_the_model_the_run_used(tmp_path) -> None:
    db_path = _state_db(
        tmp_path / "state.db",
        sessions=[("s1", "gpt-oss:20b-64k", 7, "http://127.0.0.1:11434/v1", 900, 100, "/w", 1, 1)],
    )
    assert run.hermes_session("s1", db_path) == {
        "model": "gpt-oss:20b-64k",
        "api_calls": 7,
        "base_url": "http://127.0.0.1:11434/v1",
        "input_tokens": 900,
        "output_tokens": 100,
    }
    assert run.hermes_session("missing", db_path) == {}
    assert run.hermes_session(None, db_path) == {}


def test_a_timed_out_run_finds_its_session_by_the_resolved_workspace(tmp_path) -> None:
    ws = tmp_path / "real" / "ws"
    ws.mkdir(parents=True)
    link = tmp_path / "link"
    link.symlink_to(tmp_path / "real")
    real = os.path.realpath(ws)
    db_path = _state_db(
        tmp_path / "state.db",
        sessions=[
            ("old", "m", 1, "", 0, 0, real, 1.0, 1.0),
            ("new", "m", 1, "", 0, 0, real, 2.0, 2.0),
        ],
    )
    # Hermes records the resolved directory; the runner may hold a symlinked path.
    assert run.hermes_session_in(link / "ws", db_path) == "new"
    assert run.hermes_session_in(tmp_path / "elsewhere", db_path) is None


def test_hermes_is_idle_only_with_no_queued_turn_and_no_recent_activity(tmp_path) -> None:
    import time

    quiet = _state_db(
        tmp_path / "quiet.db",
        sessions=[("s", "m", 1, "", 0, 0, "/w", 1.0, time.time() - 120)],
        admissions=[("s", "terminal")],
    )
    assert run.wait_hermes_idle("s", quiet, quiet=30, limit=1, poll=0.01) is not None
    queued = _state_db(
        tmp_path / "queued.db",
        sessions=[("s", "m", 1, "", 0, 0, "/w", 1.0, time.time() - 120)],
        admissions=[("s", "terminal"), ("s", "running")],
    )
    assert run.wait_hermes_idle("s", queued, quiet=30, limit=0.05, poll=0.01) is None
    recent = _state_db(
        tmp_path / "recent.db",
        sessions=[("s", "m", 1, "", 0, 0, "/w", 1.0, time.time())],
    )
    assert run.wait_hermes_idle("s", recent, quiet=30, limit=0.05, poll=0.01) is None
    assert run.wait_hermes_idle(None, quiet) == 0.0


@pytest.mark.skipif(not Path("/proc/self/cwd").exists(), reason="reads /proc (Linux)")
def test_processes_left_running_in_the_workspace_are_stopped(tmp_path) -> None:
    import subprocess
    import sys

    ws = tmp_path / "ws"
    ws.mkdir()
    inside = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"], cwd=ws)
    outside = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"], cwd=tmp_path)
    try:
        assert run.stop_workspace_processes(ws) == 1
        assert inside.wait(timeout=10) != 0
        assert outside.poll() is None
    finally:
        for p in (inside, outside):
            p.kill()
            p.wait()


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


def _hermes_runs(solved: dict[tuple[str, str, int], bool], seeds=(0,)) -> list[dict]:
    """Four tasks, both arms; ``solved`` marks which (task, arm, seed) runs solved."""
    runs = []
    for i in range(4):
        for arm in ("baseline", "neuralmind"):
            for seed in seeds:
                runs.append(
                    {
                        "task": f"t{i}",
                        "arm": arm,
                        "seed": seed,
                        "agent": "hermes",
                        "solved": solved.get((f"t{i}", arm, seed), False),
                        "input_tokens": 1000 if arm == "baseline" else 800,
                        "output_tokens": 100,
                        "total_tokens": 1100 if arm == "baseline" else 900,
                        "duration_ms": 600_000,
                        "num_turns": 50,
                        "explore_calls_before_first_edit": 20,
                        "gold_touched": True,
                        "timed_out": False,
                        "cost_usd": None,
                        "budget_usd": None,
                    }
                )
    return runs


def test_mcnemar_one_sided_counts_only_neuralmind_wins() -> None:
    assert analyze.mcnemar_exact_greater(0, 5) == 1 / 32
    assert analyze.mcnemar_exact_greater(5, 0) == 1.0
    assert analyze.mcnemar_exact_greater(1, 4) == 6 / 32
    assert analyze.mcnemar_exact_greater(0, 0) == 1.0


def test_hermes_tokens_are_input_plus_output_even_when_total_reads_zero() -> None:
    # Hermes reports total_tokens 0 for a session that ends in an error.
    run = {"input_tokens": 3_618_022, "output_tokens": 93_495, "total_tokens": 0}
    assert analyze.run_tokens(run) == 3_711_517
    assert analyze.run_tokens({"total_tokens": 5}) is None


def test_hermes_runs_are_judged_on_solve_rate_not_cost() -> None:
    runs = _hermes_runs({("t0", "neuralmind", 0): True, ("t1", "baseline", 0): True})
    # analyze() is cost-primary and has no cost for a local model.
    with pytest.raises(analyze.IncompleteRunsError):
        analyze.analyze(runs)
    result = analyze.analyze_hermes(runs)
    assert result["solve"]["only_neuralmind"] == 1
    assert result["solve"]["only_baseline"] == 1
    assert result["solve"]["mcnemar_p_greater"] == 0.75
    assert result["decision"]["claim_supported"] is False
    assert result["tokens"]["median_relative_change"] == -200 / 1100
    assert "Claim supported: NO" in analyze.report_hermes(result)


def test_hermes_majority_of_seeds_decides_a_task_and_a_timeout_never_solves() -> None:
    solved = {("t0", "neuralmind", 0): True, ("t0", "neuralmind", 1): True}
    solved.update({("t1", "neuralmind", 0): True})
    runs = _hermes_runs(solved, seeds=(0, 1, 2))
    result = analyze.analyze_hermes(runs)
    assert result["solve"]["neuralmind_tasks_solved"] == 1  # t1 solved 1 of 3 seeds
    assert result["solve"]["solved_runs"] == {"baseline": 0, "neuralmind": 3}
    timed_out = next(r for r in runs if (r["task"], r["arm"], r["seed"]) == ("t0", "neuralmind", 1))
    timed_out.update(timed_out=True)
    assert analyze.analyze_hermes(runs)["solve"]["neuralmind_tasks_solved"] == 0


def test_hermes_stage_one_pools_both_arms_over_seed_zero() -> None:
    four = {("t0", "baseline", 0), ("t1", "baseline", 0), ("t2", "neuralmind", 0)}
    four.add(("t3", "neuralmind", 1))  # seed 1 isn't stage 1
    runs = _hermes_runs(dict.fromkeys(four, True), seeds=(0, 1))
    assert analyze.stage_one(runs) == {
        "runs": 8,
        "solved_runs": 3,
        "min_solved_runs": 5,
        "run_stage_two": False,
    }
    five = {(f"t{i}", "baseline", 0) for i in range(4)} | {("t0", "neuralmind", 0)}
    assert analyze.stage_one(_hermes_runs(dict.fromkeys(five, True)))["run_stage_two"] is True


def test_runs_from_two_agents_are_never_pooled(tmp_path) -> None:
    runs = _hermes_runs({})
    runs[0]["agent"] = "claude"
    (tmp_path / "runs.jsonl").write_text("".join(json.dumps(r) + "\n" for r in runs))
    assert analyze.main([str(tmp_path)]) == 1
    del runs[0]["agent"]  # records before the field are Claude Code's
    with pytest.raises(analyze.IncompleteRunsError, match="more than one agent"):
        analyze.agent_of(runs)


def test_analyze_main_picks_the_hermes_endpoints(tmp_path, capsys) -> None:
    runs = _hermes_runs({("t0", "neuralmind", 0): True})
    (tmp_path / "runs.jsonl").write_text("".join(json.dumps(r) + "\n" for r in runs))
    assert analyze.main([str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "Agent: Hermes" in out
    assert "Stage 1 (seed 0, both arms): 1 of 8 runs solved" in out


def _usage_db(path, sessions):
    """Hermes's sessions table, cut down to the usage columns."""
    import sqlite3

    db = sqlite3.connect(path)
    db.execute(
        "CREATE TABLE sessions (id TEXT, api_call_count INT, input_tokens INT,"
        " cache_read_tokens INT, cache_write_tokens INT, output_tokens INT,"
        " started_at REAL, last_activity_at REAL)"
    )
    db.executemany("INSERT INTO sessions VALUES (?, ?, ?, ?, ?, ?, ?, ?)", sessions)
    db.commit()
    db.close()
    return path


def test_session_usage_counts_cache_reads_as_prompt_tokens(tmp_path) -> None:
    # A timed-out run's record took input_tokens alone; the session row keeps
    # the cached part of every prompt apart.
    db = _usage_db(tmp_path / "state.db", [("s1", 74, 128_193, 2_339_645, 0, 43_138, 0.0, 4650.0)])
    assert hermes_sessions.session_usage(["s1", "gone"], db) == {
        "s1": {
            "api_calls": 74,
            "prompt_tokens": 2_467_838,
            "output_tokens": 43_138,
            "minutes": 77.5,
        }
    }


def test_hermes_sessions_writes_beside_the_runs_and_flags_missing_sessions(tmp_path) -> None:
    db = _usage_db(tmp_path / "state.db", [("s1", 3, 10, 90, 0, 5, 0.0, 60.0)])
    out = tmp_path / "out"
    out.mkdir()
    runs = [{"agent": "hermes", "session_id": "s1"}, {"agent": "hermes", "session_id": "s2"}]
    (out / "runs.jsonl").write_text("".join(json.dumps(r) + "\n" for r in runs))
    assert hermes_sessions.main([str(out), "--state-db", str(db)]) == 1
    assert json.loads((out / "sessions.json").read_text()) == {
        "s1": {"api_calls": 3, "prompt_tokens": 100, "output_tokens": 5, "minutes": 1.0}
    }


def test_hermes_tokens_and_minutes_come_from_the_whole_session() -> None:
    record = {"input_tokens": 3_583_267, "output_tokens": 30_977, "duration_ms": 1_518_000}
    session = {"api_calls": 215, "prompt_tokens": 7_145_464, "output_tokens": 55_441}
    (run_with,) = analyze.with_sessions(
        [{**record, "session_id": "s"}], {"s": {**session, "minutes": 42.4}}
    )
    assert analyze.run_tokens(run_with) == 7_200_905
    assert analyze.run_minutes(run_with) == 42.4
    assert analyze.run_tokens(record) == 3_614_244
    assert analyze.run_minutes(record) == 25.3
    # A timed-out run has no duration: unknown, not zero minutes.
    assert analyze.run_minutes({"timed_out": True}) is None


def test_analyze_main_uses_sessions_json_and_says_when_it_is_missing(tmp_path, capsys) -> None:
    runs = _hermes_runs({})
    for i, r in enumerate(runs):
        r["session_id"] = f"s{i}"
    (tmp_path / "runs.jsonl").write_text("".join(json.dumps(r) + "\n" for r in runs))
    assert analyze.main([str(tmp_path)]) == 0
    assert "8 of 8 runs have no session usage" in capsys.readouterr().out
    sessions = {
        f"s{i}": {"api_calls": 1, "prompt_tokens": 2000, "output_tokens": 0, "minutes": 1.0}
        for i in range(len(runs))
    }
    (tmp_path / "sessions.json").write_text(json.dumps(sessions))
    assert analyze.main([str(tmp_path), "--json"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["runs_without_session"] == 0
    assert result["tokens"]["median_per_task"] == {"baseline": 2000, "neuralmind": 2000}


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


def test_test_keys_hide_parameters_but_keep_cases_distinct() -> None:
    from evals.task_outcome.harness import test_key

    assert test_key("tests.test_x::test_y") == "tests.test_x::test_y"
    a = test_key("tests.test_s::test_t[slack-xoxb-fake-1]")
    b = test_key("tests.test_s::test_t[slack-xoxb-fake-2]")
    assert a != b and "xoxb" not in a + b
    assert a.startswith("tests.test_s::test_t[") and a.endswith("]")
