"""Tests for the `neuralmind doctor` diagnostics module."""

import json

import pytest

from neuralmind import doctor
from neuralmind.core import GraphNotBuiltError, NeuralMind


def test_overall_status_picks_worst():
    assert doctor.overall_status([]) == doctor.OK
    assert (
        doctor.overall_status(
            [doctor.Check("a", doctor.OK, ""), doctor.Check("b", doctor.WARN, "")]
        )
        == doctor.WARN
    )
    assert (
        doctor.overall_status(
            [
                doctor.Check("a", doctor.OK, ""),
                doctor.Check("b", doctor.WARN, ""),
                doctor.Check("c", doctor.FAIL, ""),
            ]
        )
        == doctor.FAIL
    )


def test_check_to_dict_shape():
    c = doctor.Check("Code graph", doctor.FAIL, "missing", fix="run it")
    assert c.to_dict() == {
        "name": "Code graph",
        "status": doctor.FAIL,
        "detail": "missing",
        "fix": "run it",
    }


def test_graph_check_ok_when_present(temp_project):
    check = doctor._check_graph(temp_project)
    assert check.status == doctor.OK
    assert "nodes" in check.detail


def test_graph_check_fail_when_missing(empty_project):
    check = doctor._check_graph(empty_project)
    assert check.status == doctor.FAIL
    assert "neuralmind build" in check.fix


def test_graph_check_fail_when_corrupt(empty_project):
    out = empty_project / "graphify-out"
    out.mkdir(parents=True)
    (out / "graph.json").write_text("{ not valid json", encoding="utf-8")
    check = doctor._check_graph(empty_project)
    assert check.status == doctor.FAIL
    assert "neuralmind build" in check.fix


def test_index_check_fail_when_not_built(temp_project):
    # Graph exists but nothing embedded yet -> actionable build hint.
    check = doctor._check_index(temp_project)
    assert check.status == doctor.FAIL
    assert "neuralmind build" in check.fix


def test_synapses_check_warns_when_absent(temp_project):
    check = doctor._check_synapses(temp_project)
    assert check.status == doctor.WARN
    assert "nothing learned" in check.detail


def test_synapses_check_ok_when_present(temp_project):
    from neuralmind.synapses import SynapseStore, default_db_path

    store = SynapseStore(default_db_path(temp_project))
    store.reinforce(["a", "b"], strength=1.0)
    check = doctor._check_synapses(temp_project)
    assert check.status == doctor.OK
    assert "edges" in check.detail


def test_mcp_check(monkeypatch):
    monkeypatch.setattr("neuralmind.mcp_server.MCP_AVAILABLE", True, raising=False)
    assert doctor._check_mcp().status == doctor.OK


def test_hooks_check_warn_when_none(tmp_path, monkeypatch, empty_project):
    # Isolate the global ~/.claude/settings.json lookup.
    monkeypatch.setenv("HOME", str(tmp_path))
    check = doctor._check_hooks(empty_project)
    assert check.status == doctor.WARN
    assert "install-hooks" in check.fix


def test_hooks_check_ok_when_installed(tmp_path, monkeypatch, empty_project):
    monkeypatch.setenv("HOME", str(tmp_path))
    settings_dir = empty_project / ".claude"
    settings_dir.mkdir(parents=True)
    (settings_dir / "settings.json").write_text(
        json.dumps(
            {
                "hooks": {
                    "PostToolUse": [
                        {
                            "matcher": "Read",
                            "hooks": [
                                {"type": "command", "command": "neuralmind _hook compress-read"}
                            ],
                        }
                    ]
                }
            }
        ),
        encoding="utf-8",
    )
    check = doctor._check_hooks(empty_project)
    assert check.status == doctor.OK
    assert "project" in check.detail


def test_memory_check_reflects_flag(monkeypatch):
    monkeypatch.setattr("neuralmind.memory.is_memory_logging_enabled", lambda: True)
    assert doctor._check_memory().status == doctor.OK
    monkeypatch.setattr("neuralmind.memory.is_memory_logging_enabled", lambda: False)
    off = doctor._check_memory()
    assert off.status == doctor.WARN
    assert "NEURALMIND_MEMORY" in off.fix


def test_backend_check_reports_auto_resolution(temp_project, monkeypatch):
    import neuralmind.backend_manager as bm

    # No yaml -> "auto". With turbovec absent it must resolve to chroma (graph)
    # and say so, plus point at how to pin a backend.
    monkeypatch.setattr(bm, "turbovec_available", lambda: False)
    check = doctor._check_backend(temp_project)
    assert check.status == doctor.OK
    assert "graph" in check.detail
    assert "auto-selected" in check.detail
    assert "not installed" in check.detail
    assert "neuralmind-backend.yaml" in check.fix

    # With the turbovec stack available, auto resolves to turbovec.
    monkeypatch.setattr(bm, "turbovec_available", lambda: True)
    assert "turbovec" in doctor._check_backend(temp_project).detail


def test_backend_check_reports_pinned_choice(temp_project):
    (temp_project / "neuralmind-backend.yaml").write_text("backend: graph\n", encoding="utf-8")
    check = doctor._check_backend(temp_project)
    assert check.status == doctor.OK
    assert "graph" in check.detail
    assert "pinned" in check.detail


def test_backend_check_treats_null_config_as_auto(temp_project, monkeypatch):
    import neuralmind.backend_manager as bm

    # `backend: null` parses to None — must be treated as auto (matching
    # BackendManager), not a pinned backend named "none".
    monkeypatch.setattr(bm, "turbovec_available", lambda: False)
    (temp_project / "neuralmind-backend.yaml").write_text("backend: null\n", encoding="utf-8")
    check = doctor._check_backend(temp_project)
    assert check.status == doctor.OK
    assert "auto-selected" in check.detail
    assert "graph" in check.detail


def test_run_diagnostics_returns_all_checks(temp_project):
    checks = doctor.run_diagnostics(str(temp_project))
    names = {c.name for c in checks}
    assert names == {
        "Code graph",
        "Backend",
        "Semantic index",
        "Synapse memory",
        "MCP server",
        "Claude Code hooks",
        "Query memory",
    }


def test_run_diagnostics_json_serialisable(empty_project):
    checks = doctor.run_diagnostics(str(empty_project))
    payload = {"status": doctor.overall_status(checks), "checks": [c.to_dict() for c in checks]}
    # Must round-trip through JSON for the --json output / agent consumption.
    assert json.loads(json.dumps(payload))["status"] in {doctor.OK, doctor.WARN, doctor.FAIL}


def test_query_without_graph_raises_friendly_error(empty_project):
    mind = NeuralMind(str(empty_project), backend_type="in_memory")
    with pytest.raises(GraphNotBuiltError) as exc:
        mind.query("anything")
    msg = str(exc.value)
    assert "graphify update" in msg
    assert "neuralmind build" in msg
