"""The daemon's /stats tells the truth about a built project.

The registry hands out a NeuralMind that hasn't loaded its index yet, and
``NeuralMind.get_stats()`` reports ``built: False`` until something does — so
``/stats`` (and ``neuralmind stats``, which prefers a running daemon) said
"Built: False" for every built project. ``/stats`` now loads an existing
index as it stands before reporting, and still never builds one.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from neuralmind import daemon as daemon_mod

pytest.importorskip("turbovec")


@pytest.fixture
def builtin_available():
    from neuralmind import graphgen

    if not graphgen.is_available():
        pytest.skip("tree-sitter not installed")


def _registry():
    from tests.test_index_freshness import _mind

    # Same shape as the daemon's default factory — a fresh, unloaded
    # NeuralMind per project — with the test embedder.
    return daemon_mod.ProjectRegistry(mind_factory=lambda path: _mind(Path(path)))


def _ctx(registry):
    return daemon_mod.DaemonContext(registry=registry, jobs=daemon_mod.JobManager(), version="test")


@pytest.mark.usefixtures("builtin_available")
def test_stats_reports_a_built_project_as_built(tmp_path):
    from tests.test_index_freshness import _mind, _write_files

    _write_files(tmp_path, ["billing/invoices.py", "auth/handlers.py"])
    built = _mind(tmp_path).build()
    assert built.get("success", True)

    registry = _registry()
    status, payload = daemon_mod.dispatch(_ctx(registry), "GET", f"/stats?project={tmp_path}", None)

    assert status == 200
    assert payload["built"] is True
    assert payload["nodes"] > 0
    # The loaded index is the warm one later queries reuse.
    assert registry.is_built(str(tmp_path))


@pytest.mark.usefixtures("builtin_available")
def test_cli_stats_via_running_daemon_says_built(tmp_path, monkeypatch, capsys):
    """`neuralmind stats` prefers the daemon; it printed "Built: False"."""
    import threading
    from types import SimpleNamespace

    from neuralmind import cli
    from tests.test_index_freshness import _mind, _write_files

    project = tmp_path / "proj"
    _write_files(project, ["billing/invoices.py"])
    _mind(project).build()
    monkeypatch.setenv("NEURALMIND_DAEMON_HOME", str(tmp_path / "daemon"))
    monkeypatch.delenv("NEURALMIND_NO_DAEMON", raising=False)

    httpd, _ = daemon_mod.create_server(host="127.0.0.1", port=0, auth=True, registry=_registry())
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        cli.cmd_stats(SimpleNamespace(project_path=str(project), json=False))
    finally:
        httpd.shutdown()
        httpd.server_close()
        daemon_mod.clear_discovery()
        thread.join(timeout=5)

    out = capsys.readouterr().out
    assert "(via daemon)" in out
    assert "Built: True" in out


@pytest.mark.usefixtures("builtin_available")
def test_stats_never_builds_an_unbuilt_project(tmp_path):
    from tests.test_index_freshness import _write_files

    _write_files(tmp_path, ["billing/invoices.py"])
    registry = _registry()
    status, payload = daemon_mod.dispatch(_ctx(registry), "GET", f"/stats?project={tmp_path}", None)

    assert status == 200
    assert payload["built"] is False
    assert not (tmp_path / ".neuralmind" / "graph.json").exists()
    assert not registry.is_built(str(tmp_path))
