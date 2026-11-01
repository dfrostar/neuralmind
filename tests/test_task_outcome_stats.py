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


@pytest.mark.skipif(not Path("/proc/self/cwd").exists(), reason="reads /proc (Linux)")
def test_a_process_started_in_the_workspace_is_stopped_after_it_moves_out(tmp_path) -> None:
    import subprocess

    # The agent's test runs change into pytest's temporary directories; the
    # shell that started them exported the workspace as PWD.
    ws = tmp_path / "ws"
    ws.mkdir()
    env = {**os.environ, "PWD": str(ws)}
    moved = subprocess.Popen(["sleep", "60"], cwd=tmp_path, env=env)
    elsewhere = subprocess.Popen(["sleep", "60"], cwd=tmp_path, env={**env, "PWD": str(tmp_path)})
    try:
        assert run.stop_workspace_processes(ws) == 1
        assert moved.wait(timeout=10) != 0
        assert elsewhere.poll() is None
    finally:
        for p in (moved, elsewhere):
            p.kill()
            p.wait()


def _settle(monkeypatch, scans: list[int], waits: list[float | None]):
    calls = {"scans": 0}

    def stop(ws):
        calls["scans"] += 1
        return scans.pop(0)

    monkeypatch.setattr(run, "stop_workspace_processes", stop)
    monkeypatch.setattr(run, "wait_hermes_idle", lambda session_id: waits.pop(0))
    return run.settle_workspace(Path("ws"), "s", settle=0), calls["scans"]


def test_a_command_started_while_waiting_for_hermes_is_stopped_before_judging(monkeypatch) -> None:
    # Nothing left running when the client returns, but a turn still running in
    # the gateway starts a command: the scan after the wait must find it.
    assert _settle(monkeypatch, scans=[0, 1, 0], waits=[40.0, 12.0, 0.0]) == ((1, 52.0, True), 3)


def test_the_workspace_settles_only_when_a_scan_and_the_session_are_both_quiet(monkeypatch) -> None:
    assert _settle(monkeypatch, scans=[0, 0], waits=[30.0, 0.0]) == ((0, 30.0, True), 2)
    assert _settle(monkeypatch, scans=[0], waits=[0.0]) == ((0, 0.0, True), 1)
    # Still busy after five rounds, or still running an hour later: a harness failure.
    assert _settle(monkeypatch, scans=[1] * 5, waits=[5.0] * 5) == ((5, 25.0, False), 5)
    assert _settle(monkeypatch, scans=[0], waits=[None]) == ((0, None, False), 1)


def test_a_pinned_hermes_plugin_is_refused(tmp_path) -> None:
    config = tmp_path / "config.json"
    config.write_text(json.dumps({"python": "/venv/bin/python", "project": None}))
    assert run.hermes_plugin_pin(config) is None
    config.write_text(json.dumps({"python": "/venv/bin/python", "project": "/home/u/other"}))
    assert run.hermes_plugin_pin(config) == "/home/u/other"


def test_a_neuralmind_run_without_a_recorded_prompt_is_a_harness_failure(tmp_path) -> None:
    ws = tmp_path / "ws"
    assert run.neuralmind_missing("neuralmind", run.hook_activity(ws))
    recaps = ws / ".neuralmind" / "recaps"
    recaps.mkdir(parents=True)
    (recaps / "s.jsonl").write_text(json.dumps({"kind": "prompt"}) + "\n")
    assert not run.neuralmind_missing("neuralmind", run.hook_activity(ws))
    assert not run.neuralmind_missing("baseline", {})


def test_a_carried_run_counts_only_its_own_recap(tmp_path) -> None:
    # The carried recaps aren't this session's. NeuralMind deletes the oldest as
    # the session starts, so subtracting their counts from the total can come to 0
    # for a session it reached: the memory track's false harness failures.
    recaps = tmp_path / ".neuralmind" / "recaps"
    recaps.mkdir(parents=True)
    for name in ("oldest.jsonl", "kept.jsonl"):
        (recaps / name).write_text(json.dumps({"kind": "prompt"}) + "\n")
    carried = frozenset(p.name for p in recaps.glob("*.jsonl"))
    assert run.neuralmind_missing("neuralmind", run.hook_activity(tmp_path, carried))
    (recaps / "oldest.jsonl").unlink()
    (recaps / "this-session.jsonl").write_text(
        json.dumps({"kind": "prompt"}) + "\n" + json.dumps({"kind": "edit"}) + "\n"
    )
    hooks = run.hook_activity(tmp_path, carried)
    assert hooks == {"hook_prompts_recorded": 1, "hook_edits_recorded": 1}
    assert not run.neuralmind_missing("neuralmind", hooks)


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


# The memory track: chains that carry NeuralMind's learned state, beside fresh runs.


def test_memory_plan_runs_each_position_together_and_each_chain_in_order() -> None:
    runs = run.memory_plan(set(run.MEMORY_ORDER), chains=3, fresh=3, order_seed=7)
    assert len(runs) == 120 and runs == run.memory_plan(set(run.MEMORY_ORDER), 3, 3, 7)
    for i, tid in enumerate(run.MEMORY_ORDER):
        group = runs[i * 6 : (i + 1) * 6]
        assert {(r[0], r[3]) for r in group} == {(tid, i + 1)}
        assert sorted(r[1:3] for r in group) == [("carried", c) for c in range(3)] + [
            ("fresh", s) for s in range(3)
        ]
    # Run on a subset, positions follow the order of what is left.
    smoke = run.memory_plan({"e303c7a287", "4e01f40e6a"}, chains=1, fresh=0, order_seed=7)
    assert smoke == [("4e01f40e6a", "carried", 0, 1), ("e303c7a287", "carried", 0, 2)]


def _store(ws, edges):
    import sqlite3

    state = ws / ".neuralmind"
    state.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(state / "synapses.db")
    db.execute("CREATE TABLE synapses (node_a TEXT, node_b TEXT, namespace TEXT)")
    db.executemany("INSERT INTO synapses VALUES (?, ?, ?)", edges)
    db.commit()
    db.close()


def test_a_chain_carries_learned_edges_and_recaps_and_counts_what_survives(tmp_path) -> None:
    first, chain, second = tmp_path / "first", tmp_path / "chain" / "state", tmp_path / "second"
    _store(
        first,
        [
            ("a", "b", "personal"),
            ("a", "gone", "main"),
            ("x", "y", "structural"),
            ("d", "e", "shared"),
        ],
    )
    (first / ".neuralmind" / "recaps").mkdir()
    (first / ".neuralmind" / "recaps" / "s1.jsonl").write_text(
        json.dumps({"kind": "prompt"}) + "\n"
    )
    (first / ".neuralmind" / "graph.json").write_text("{}")  # not carried: rebuilt
    run.carry_out(first, chain)
    assert sorted(p.name for p in chain.iterdir()) == ["recaps", "synapses.db"]

    second.mkdir()
    assert run.carry_in(chain, second) == {"carry_edges_in": 2, "carry_recaps_in": 1}
    assert not (second / ".neuralmind" / "graph.json").exists()
    graph = {"nodes": [{"id": n} for n in ("a", "b", "x", "y")]}
    (second / ".neuralmind" / "graph.json").write_text(json.dumps(graph))
    assert run.carry_check(second) == {"carry_edges_after_build": 2, "carry_edges_in_graph": 1}
    # A chain's first task has nothing to carry.
    third = tmp_path / "third"
    third.mkdir()
    assert run.carry_in(tmp_path / "chain" / "none", third) == {
        "carry_edges_in": 0,
        "carry_recaps_in": 0,
    }


BLOCK = """## NeuralMind associative recall

Code matching this prompt:
- neuralmind/secret_scan.py: line L138, _may_contain_secret() L424
- neuralmind/cli.py: cmd_scan_for_secrets() L176
Most matches are in neuralmind/secret_scan.py.
Connected to it in the synapse graph:
- neuralmind/_demo_report.py: encode() L66
- neuralmind/cli.py: main() L9"""


def test_the_block_names_files_in_order_and_says_whether_a_gold_one_comes_first() -> None:
    got = run.block_files(BLOCK, ["neuralmind/secret_scan.py"])
    assert got["block_files"] == [
        "neuralmind/secret_scan.py",
        "neuralmind/cli.py",
        "neuralmind/_demo_report.py",
    ]
    assert got["block_synapse_files"] == ["neuralmind/_demo_report.py", "neuralmind/cli.py"]
    assert got["block_names_gold"] and got["block_first_is_gold"]
    other = run.block_files(BLOCK, ["neuralmind/cli.py"])
    assert other["block_names_gold"] and not other["block_first_is_gold"]
    assert run.block_files("", ["x.py"]) == {
        "block_sha256": None,
        "block_files": [],
        "block_synapse_files": [],
        "block_names_gold": False,
        "block_first_is_gold": False,
    }


def test_the_block_is_what_the_plugin_appended_to_the_first_prompt(tmp_path) -> None:
    import sqlite3

    path = tmp_path / "state.db"
    db = sqlite3.connect(path)
    db.execute(
        "CREATE TABLE messages (id INTEGER, session_id TEXT, role TEXT, content TEXT,"
        " api_content TEXT)"
    )
    db.executemany(
        "INSERT INTO messages VALUES (?, ?, ?, ?, ?)",
        [
            (1, "nm", "user", "Fix it.", "Fix it.\n\n" + BLOCK),
            (2, "nm", "user", "later", "later\n\nanother block"),
            (3, "base", "user", "Fix it.", None),
        ],
    )
    db.commit()
    db.close()
    assert run.hermes_block("nm", path) == BLOCK
    assert run.hermes_block("base", path) == ""
    assert run.hermes_block("missing", path) == ""


def test_the_memory_track_hands_each_chain_its_own_state_once_a_run_is_recorded(
    tmp_path, monkeypatch
) -> None:
    tasks = tmp_path / "tasks.json"
    tasks.write_text(json.dumps([{"id": t, "prompt": "p"} for t in ("4e01f40e6a", "e303c7a287")]))
    out = tmp_path / "out"
    seen = []

    def fake_run(task, arm, seed, args, label=None, carry=None, carry_to=None):
        seen.append((task["id"], arm, label, seed, carry and carry.exists()))
        if carry_to is not None:
            carry_to.mkdir(parents=True)
            (carry_to / "from").write_text(task["id"])
        return {
            "task": task["id"],
            "arm": arm,
            "seed": seed,
            "solved": False,
            "total_tokens": 1,
            "num_turns": 1,
            **args.versions,
        }

    monkeypatch.setattr(run, "run_one", fake_run)
    monkeypatch.setattr(run.shutil, "which", lambda name: f"/bin/{name}")
    monkeypatch.setattr(run, "probe_versions", lambda *a: {"neuralmind_version": "nm"})
    monkeypatch.setattr(run, "hermes_plugin_pin", lambda: None)
    argv = [
        "--tasks",
        str(tasks),
        "--out",
        str(out),
        "--model",
        "m",
        "--tool-venv",
        "v",
        "--test-python",
        "p",
        "--work-dir",
        str(tmp_path / "w"),
        "--agent",
        "hermes",
        "--track",
        "memory",
        "--chains",
        "2",
        "--fresh",
        "1",
    ]
    assert run.main(argv) == 0
    carried = [s for s in seen if s[2] == "carried"]
    # Position 1 starts empty, position 2 from that chain's own position-1 state.
    assert sorted(carried) == [
        ("4e01f40e6a", "neuralmind", "carried", 0, False),
        ("4e01f40e6a", "neuralmind", "carried", 1, False),
        ("e303c7a287", "neuralmind", "carried", 0, True),
        ("e303c7a287", "neuralmind", "carried", 1, True),
    ]
    assert all(s[4] in (None, False) for s in seen if s[2] == "fresh")
    for c in (0, 1):
        assert (out / "carry" / f"chain{c}" / "state" / "from").read_text() == "e303c7a287"
    records = [json.loads(line) for line in (out / "runs.jsonl").read_text().splitlines()]
    assert len(records) == 6 and {r["condition"] for r in records} == {"carried", "fresh"}
    assert {(r["task"], r["position"]) for r in records} == {("4e01f40e6a", 1), ("e303c7a287", 2)}
    # A rerun finds every (task, condition, replicate) done.
    seen.clear()
    assert run.main(argv) == 0 and seen == []


def _memory_run(task, condition, seed, position, solved, **extra):
    return {
        "task": task,
        "arm": "neuralmind",
        "condition": condition,
        "seed": seed,
        "position": position,
        "track": "memory",
        "agent": "hermes",
        "solved": solved,
        "input_tokens": 100,
        "output_tokens": 10,
        **extra,
    }


def test_memory_track_compares_carried_with_fresh_on_solve_rate(tmp_path, capsys) -> None:
    # Five tasks only the carried chains solve: the smallest result that clears p < 0.05.
    tasks = sorted(analyze.MEMORY_REPEATS)[:5] + ["0db7d2c97d"]
    runs = []
    for pos, t in enumerate(tasks, 1):
        for s in range(3):
            first = pos == 1
            runs.append(
                _memory_run(
                    t,
                    "carried",
                    s,
                    pos,
                    t != "0db7d2c97d",
                    block_sha256="b",
                    block_names_gold=True,
                    block_first_is_gold=not first,
                    carry_recaps_in=pos - 1 if t != "0db7d2c97d" else 0,
                    carry_edges_in=0 if first else 40,
                    carry_edges_after_build=0 if first else 40,
                    carry_edges_in_graph=0 if first else 30,
                )
            )
            runs.append(_memory_run(t, "fresh", s, pos, False, block_sha256="b"))
    result = analyze.analyze_memory(runs)
    assert result["solve"]["only_neuralmind"] == 5 and result["solve"]["only_baseline"] == 0
    assert result["solve"]["mcnemar_p_greater"] == pytest.approx(1 / 32)
    assert result["decision"]["claim_supported"]
    assert result["mechanism"]["carried"]["tasks_block_names_gold"] == 6
    assert result["mechanism"]["carried"]["tasks_block_first_is_gold"] == 5
    assert result["mechanism"]["fresh"]["tasks_block_names_gold"] == 0
    assert result["prediction"]["repeats"] == {"fresh": 0, "carried": 5}
    assert result["prediction"]["held"]
    assert result["carry_over"]["edges_in_median"] == 40
    assert result["carry_over"]["share_with_both_ends_in_graph"] == pytest.approx(0.75)
    # The last position's chains claim no earlier recaps: off their chain.
    assert result["carry_over"]["runs_off_chain"] == 3
    assert result["solve_share_by_position"][1] == (1.0, 0.0)

    (tmp_path / "runs.jsonl").write_text("".join(json.dumps(r) + "\n" for r in runs))
    assert analyze.main([str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "memory track" in out and "only carried 5" in out and "Claim supported: YES" in out


def test_memory_and_task_runs_are_never_pooled(tmp_path, capsys) -> None:
    runs = [
        _memory_run("t", "fresh", 0, 1, True),
        {"task": "t", "arm": "baseline", "agent": "hermes"},
    ]
    (tmp_path / "runs.jsonl").write_text("".join(json.dumps(r) + "\n" for r in runs))
    assert analyze.main([str(tmp_path)]) == 1
    assert "more than one track" in capsys.readouterr().err


def _mark(path, task, position):
    path.mkdir(parents=True)
    (path / "run.json").write_text(json.dumps({"task": task, "position": position}))


def test_a_stop_between_recording_and_promoting_is_finished_on_resume(tmp_path) -> None:
    chain = tmp_path / "chain0"
    _mark(chain / "state", "a", 1)
    _mark(chain / "next", "b", 2)
    # b's run was recorded before the stop: its state is promoted.
    run.settle_chain(chain, {"task": "b", "position": 2})
    assert run._chain_mark(chain / "state") == {"task": "b", "position": 2}
    assert not (chain / "next").exists()
    # A run that wasn't recorded leaves its state discarded.
    _mark(chain / "next", "c", 3)
    run.settle_chain(chain, {"task": "b", "position": 2})
    assert run._chain_mark(chain / "state") == {"task": "b", "position": 2}
    assert not (chain / "next").exists()


def test_a_chain_whose_state_is_not_from_its_last_recorded_run_is_refused(tmp_path) -> None:
    chain = tmp_path / "chain0"
    run.settle_chain(chain, None)  # not started: nothing saved, nothing recorded
    with pytest.raises(run.ChainError):
        run.settle_chain(chain, {"task": "a", "position": 1})  # recorded, but no state
    _mark(chain / "state", "a", 1)
    with pytest.raises(run.ChainError):
        run.settle_chain(chain, {"task": "b", "position": 2})  # state lags the record
    with pytest.raises(run.ChainError):
        run.settle_chain(chain, None)  # state with nothing recorded
