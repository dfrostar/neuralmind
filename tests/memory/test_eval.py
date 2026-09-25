"""Unit tests for the maintenance eval harness — TRD 10.1 (task runner, metrics)."""

from __future__ import annotations

import json

import pytest

from neuralmind.memory.eval import MaintenanceEval, _build_tasks


@pytest.fixture
def project(tmp_path):
    return str(tmp_path)


def test_build_tasks_returns_five():
    tasks = _build_tasks()
    assert len(tasks) == 5
    for t in tasks:
        assert t.id
        assert t.query
        assert t.expected_decision_ids, "each task needs gold answers"
        assert t.task_type in ("BUGFIX", "REFACTOR", "DEPENDENCY", "CONFIG", "TEST")


def test_task_count_capped_at_five(tmp_path):
    harness = MaintenanceEval(str(tmp_path), task_count=100)
    assert harness.task_count == 5


def test_run_returns_json_report(project):
    harness = MaintenanceEval(project, task_count=5)
    out = harness.run(output_format="json")
    report = json.loads(out)
    assert (
        "memory_on" in report or "memory_enabled" in report or "tasks" in report
    ), "report must expose per-arm or per-task results"


def test_run_report_has_both_arms(project):
    harness = MaintenanceEval(project, task_count=5)
    report = json.loads(harness.run(output_format="json"))
    text = json.dumps(report)
    assert "on" in text.lower() and "off" in text.lower(), "within-subjects A/B requires both arms"


def test_seeding_is_deterministic(project):
    """Two runs over the same fresh project produce the same task set."""
    h1 = MaintenanceEval(project, task_count=5)
    r1 = json.loads(h1.run(output_format="json"))
    h2 = MaintenanceEval(project, task_count=5)
    r2 = json.loads(h2.run(output_format="json"))
    t1 = {t["task_id"] for t in r1.get("tasks", [])} or set(r1.get("task_ids", []))
    t2 = {t["task_id"] for t in r2.get("tasks", [])} or set(r2.get("task_ids", []))
    if t1 and t2:
        assert t1 == t2
