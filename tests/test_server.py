"""Tests for the local graph-view server (auth, editor open, first-run)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from neuralmind.server import (
    _editor_command,
    _ensure_graph_or_explain,
    _resolve_open_target,
)


def test_editor_command_vscode_family():
    cmd = _editor_command("code", "/x/y.py", 42)
    assert cmd == ["code", "--goto", "/x/y.py:42"]

    cmd = _editor_command("cursor", "/x/y.py", None)
    assert cmd == ["cursor", "--goto", "/x/y.py"]

    # shlex parsing preserves user flags like `code -n`.
    cmd = _editor_command("code -n", "/x/y.py", 7)
    assert cmd == ["code", "-n", "--goto", "/x/y.py:7"]


def test_editor_command_vim_family():
    assert _editor_command("vim", "/x/y.py", 12) == ["vim", "+12", "/x/y.py"]
    assert _editor_command("nvim", "/x/y.py", None) == ["nvim", "/x/y.py"]


def test_editor_command_unknown_drops_line():
    cmd = _editor_command("weirdeditor", "/x/y.py", 9)
    assert cmd == ["weirdeditor", "/x/y.py"]


def test_editor_command_empty_returns_empty():
    assert _editor_command("", "/x/y.py", 1) == []


def test_ensure_graph_or_explain_missing(tmp_path):
    with pytest.raises(RuntimeError) as exc:
        _ensure_graph_or_explain(tmp_path)
    msg = str(exc.value)
    assert "no graph found" in msg
    assert "graphify build" in msg


def test_ensure_graph_or_explain_present(tmp_path):
    (tmp_path / "graphify-out").mkdir()
    (tmp_path / "graphify-out" / "graph.json").write_text("{}")
    # Should not raise.
    _ensure_graph_or_explain(tmp_path)


def test_resolve_open_target_happy_path(tmp_path):
    # Build a fake mind with an embedder exposing one in-project node.
    src = tmp_path / "auth" / "handlers.py"
    src.parent.mkdir(parents=True)
    src.write_text("def login(): pass\n")
    mind = SimpleNamespace(
        project_path=tmp_path,
        embedder=SimpleNamespace(
            nodes=[
                {
                    "id": "n1",
                    "label": "login",
                    "source_file": "auth/handlers.py",
                    "source_location": "L17",
                }
            ]
        ),
    )
    path, line, label = _resolve_open_target(mind, "n1")
    assert path == src.resolve()
    assert line == 17
    assert label == "login"


def test_resolve_open_target_escapes_project_root(tmp_path):
    # A node whose source_file points outside the project must be rejected.
    outside = tmp_path.parent / "elsewhere.py"
    outside.write_text("x")
    try:
        mind = SimpleNamespace(
            project_path=tmp_path,
            embedder=SimpleNamespace(
                nodes=[
                    {
                        "id": "n1",
                        "source_file": str(outside),
                        "source_location": "L1",
                    }
                ]
            ),
        )
        path, line, reason = _resolve_open_target(mind, "n1")
        assert path is None
        assert "outside the project root" in reason
    finally:
        outside.unlink()


def test_resolve_open_target_unknown_node(tmp_path):
    mind = SimpleNamespace(project_path=tmp_path, embedder=SimpleNamespace(nodes=[]))
    path, line, reason = _resolve_open_target(mind, "missing")
    assert path is None
    assert reason == "unknown node id"


def test_resolve_open_target_no_source_file(tmp_path):
    mind = SimpleNamespace(
        project_path=tmp_path,
        embedder=SimpleNamespace(nodes=[{"id": "n1", "source_file": ""}]),
    )
    path, line, reason = _resolve_open_target(mind, "n1")
    assert path is None
    assert reason == "node has no source file"
