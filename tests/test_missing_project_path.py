"""A project path that doesn't exist is an error, and nothing is created there.

Regression: ``neuralmind query/search/wakeup/stats <typo>`` and the MCP tools
created ``<typo>/.neuralmind/neuralmind_turbovec/store.sqlite`` (plus the MCP
audit log), and ``neuralmind decisions ... <typo>`` created ``memory.db`` —
every state store makes its directory with ``parents=True``, so a mistyped
path quietly became a new, empty project.
"""

from __future__ import annotations

import json
from unittest.mock import patch

import pytest

from neuralmind.paths import ProjectNotFoundError, require_project_dir


@pytest.fixture
def missing(tmp_path):
    return tmp_path / "no-such-project"


@pytest.fixture(autouse=True)
def _direct_mode(monkeypatch):
    # Never route through a developer's running daemon.
    monkeypatch.setenv("NEURALMIND_NO_DAEMON", "1")


def _run_main(argv):
    from neuralmind.cli import main

    with patch("sys.argv", ["neuralmind", *argv]):
        with pytest.raises(SystemExit) as exc:
            main()
    return exc.value.code


# ------------------------------------------------------------------ #
# The shared check
# ------------------------------------------------------------------ #


def test_require_project_dir_accepts_an_existing_directory(tmp_path):
    assert require_project_dir(str(tmp_path)) == tmp_path.resolve()


def test_require_project_dir_rejects_a_missing_path(missing):
    with pytest.raises(ProjectNotFoundError, match="does not exist"):
        require_project_dir(str(missing))


def test_require_project_dir_rejects_a_file(tmp_path):
    f = tmp_path / "file.txt"
    f.write_text("x")
    with pytest.raises(ProjectNotFoundError, match="is not a directory"):
        require_project_dir(str(f))


def test_require_project_dir_names_where_a_relative_path_resolved(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ProjectNotFoundError) as exc:
        require_project_dir("typo")
    assert str(tmp_path.resolve() / "typo") in str(exc.value)


def _invalid_paths(tmp_path) -> list[str]:
    """Paths whose resolve() raises instead of OSError: an embedded NUL
    (ValueError) and, before Python 3.13, a symlink loop (RuntimeError)."""
    paths = [str(tmp_path / "proj\x00ect")]
    loop = tmp_path / "loop"
    try:
        loop.symlink_to(tmp_path / "loop2")
        (tmp_path / "loop2").symlink_to(loop)
        paths.append(str(loop))
    except OSError:  # no symlink privilege (Windows)
        pass
    return paths


def test_require_project_dir_rejects_an_invalid_path(tmp_path):
    for bad in _invalid_paths(tmp_path):
        with pytest.raises(ProjectNotFoundError):
            require_project_dir(bad)


def test_neuralmind_refuses_a_missing_project(missing):
    from neuralmind import NeuralMind

    with pytest.raises(ProjectNotFoundError):
        NeuralMind(str(missing))
    assert not missing.exists()


def test_decision_store_refuses_a_missing_project(missing):
    from neuralmind.memory.store import DecisionStore

    with pytest.raises(ProjectNotFoundError):
        DecisionStore(str(missing))
    assert not missing.exists()


# ------------------------------------------------------------------ #
# CLI
# ------------------------------------------------------------------ #


@pytest.mark.parametrize(
    "argv",
    [
        ["query", "{p}", "how does auth work?"],
        ["search", "{p}", "auth"],
        ["wakeup", "{p}"],
        ["stats", "{p}"],
        ["decisions", "record", "--title", "t", "--rationale", "r", "--commit", "abc", "{p}"],
        ["decisions", "query", "auth", "{p}"],
        ["decisions", "amend", "some-id", "{p}"],
        ["decisions", "audit", "{p}"],
        ["decisions", "export", "{p}"],
        ["decisions", "restore", "some-id", "{p}", "--commit", "abc"],
        ["decisions", "invalidate", "some-id", "{p}"],
    ],
    ids=lambda argv: "-".join(a for a in argv[:2] if a != "{p}"),
)
def test_cli_rejects_a_missing_project_path(argv, missing, capsys):
    code = _run_main([a.replace("{p}", str(missing)) for a in argv])
    assert code not in (0, None)
    err = capsys.readouterr().err
    assert "does not exist" in err
    assert str(missing) in err
    assert not missing.exists()


def test_cli_fallback_for_commands_without_an_up_front_check(missing, capsys):
    """Commands that build a NeuralMind without a parser-level check still
    exit with a one-line error (no traceback) and create nothing."""
    code = _run_main(["skeleton", "foo.py", "--project-path", str(missing)])
    assert code == 2
    err = capsys.readouterr().err
    assert "does not exist" in err
    assert "Traceback" not in err
    assert not missing.exists()


# ------------------------------------------------------------------ #
# MCP
# ------------------------------------------------------------------ #


@pytest.mark.parametrize(
    "tool, extra",
    [
        ("neuralmind_stats", {}),
        ("neuralmind_query", {"question": "how does auth work?"}),
        ("neuralmind_search", {"query": "auth"}),
        ("neuralmind_wakeup", {}),
        ("neuralmind_build", {}),
        ("neuralmind_health", {}),
        ("neuralmind_synapse_stats", {"role": "admin"}),
        ("neuralmind_query_decisions", {"query": "auth"}),
        ("neuralmind_audit_decisions", {}),
        ("neuralmind_record_decision", {"title": "t", "rationale": "r", "commit_sha": "abc"}),
        ("neuralmind_memory_search", {"query": "auth"}),
    ],
)
def test_mcp_rejects_a_missing_project_path(tool, extra, missing):
    from neuralmind.mcp_server import handle_tool_call

    data = json.loads(handle_tool_call(tool, {"project_path": str(missing), **extra}))
    assert data["code"] == "project_not_found", data
    assert "does not exist" in data["error"]
    # Not even the security manager's audit log.
    assert not missing.exists()


def test_mcp_missing_relative_path_says_to_pass_an_absolute_one(tmp_path, monkeypatch):
    from neuralmind.mcp_server import handle_tool_call

    monkeypatch.chdir(tmp_path)
    data = json.loads(handle_tool_call("neuralmind_stats", {"project_path": "typo"}))
    assert data["code"] == "project_not_found"
    assert "absolute path" in data["hint"]
    assert not (tmp_path / "typo").exists()


def test_mcp_answers_an_invalid_project_path_with_project_not_found(tmp_path):
    # The path check runs before the dispatcher's own error handling, so a
    # ValueError or RuntimeError from resolve() escaped the tool call.
    from neuralmind.mcp_server import handle_tool_call

    for bad in _invalid_paths(tmp_path):
        data = json.loads(handle_tool_call("neuralmind_stats", {"project_path": bad}))
        assert data["code"] == "project_not_found", data


def test_memory_dispatcher_reports_a_missing_project(missing):
    """The decision tools' own dispatcher, called directly."""
    from neuralmind.memory.mcp_tools import handle_tool_call

    data = json.loads(
        handle_tool_call("neuralmind_audit_decisions", {"project_path": str(missing)})
    )
    assert data["code"] == "project_not_found"
    assert not missing.exists()


def test_existing_project_still_gets_its_state_dir(tmp_path):
    """The guard only refuses missing paths: an existing directory still
    gets .neuralmind/ created on first use, as before."""
    from neuralmind.memory.store import DecisionStore

    DecisionStore(str(tmp_path))
    assert (tmp_path / ".neuralmind" / "memory.db").exists()
