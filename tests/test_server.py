"""Tests for the local graph-view server (auth, editor open, first-run, SSE)."""

from __future__ import annotations

import http.client
import json
import threading
import time
from http.server import ThreadingHTTPServer
from types import SimpleNamespace

import pytest

from neuralmind.event_bus import publish
from neuralmind.server import (
    _compute_allowed_open_paths,
    _editor_command,
    _ensure_graph_or_explain,
    _Handler,
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
    # The supported graphify entrypoint is `graphify update`; the package
    # on PyPI is `graphifyy` (yes, two y's). Lock in both so we don't
    # quietly regress to the deprecated `graphify build` guidance.
    assert "graphifyy" in msg
    assert "graphify update" in msg


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


def _run_handler_server():
    """Spin up a ThreadingHTTPServer bound to ephemeral port; returns (server, thread, port)."""
    # SSE handler reads from the event bus and ignores `mind` / open paths,
    # so a minimal stub keeps the handler attributes well-formed for class init.
    _Handler.mind = None
    _Handler.auth_token = None
    _Handler.editor = None
    _Handler.allowed_open_paths = set()
    _Handler._graph_cache = None

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd, thread, httpd.server_address[1]


def test_sse_endpoint_streams_published_events():
    httpd, thread, port = _run_handler_server()
    try:
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", "/api/events")
        resp = conn.getresponse()
        assert resp.status == 200
        assert resp.getheader("Content-Type", "").startswith("text/event-stream")

        # Give the handler a tick to subscribe before we publish.
        for _ in range(40):
            time.sleep(0.025)
            from neuralmind.event_bus import get_event_bus

            if get_event_bus().subscriber_count() >= 1:
                break
        publish("synapse", {"nodes": ["a", "b"], "pair_count": 1, "strength": 1.0})

        deadline = time.time() + 5.0
        events: list[dict] = []
        buf = b""
        while time.time() < deadline and len(events) < 2:
            chunk = resp.fp.readline()
            if not chunk:
                break
            buf += chunk
            if buf.endswith(b"\n"):
                for line in buf.splitlines():
                    if line.startswith(b"data: "):
                        try:
                            events.append(json.loads(line[6:].decode("utf-8")))
                        except ValueError:
                            pass
                buf = b""

        types = [e["type"] for e in events]
        assert "hello" in types
        assert any(e.get("type") == "synapse" and e.get("pair_count") == 1 for e in events)
        conn.close()
    finally:
        httpd.shutdown()
        thread.join(timeout=2.0)
        httpd.server_close()


def test_allowed_open_paths_only_includes_in_project_files(tmp_path):
    # In-project file -> allowed; missing/outside files -> excluded.
    keep = tmp_path / "auth" / "handlers.py"
    keep.parent.mkdir(parents=True)
    keep.write_text("x")

    outside = tmp_path.parent / "evil.py"
    outside.write_text("x")

    try:
        mind = SimpleNamespace(
            project_path=tmp_path,
            embedder=SimpleNamespace(
                nodes=[
                    {"id": "ok", "source_file": "auth/handlers.py"},
                    {"id": "missing", "source_file": "auth/missing.py"},
                    {"id": "escape", "source_file": str(outside)},
                    {"id": "blank", "source_file": ""},
                ]
            ),
        )
        allowed = _compute_allowed_open_paths(mind)
        assert allowed == {str(keep.resolve())}
    finally:
        outside.unlink()
