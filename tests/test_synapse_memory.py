"""Tests for synapse_memory: rendering and writing the memory file."""

from __future__ import annotations

from pathlib import Path

from neuralmind.synapse_memory import (
    CLAUDE_AUTO_FILENAME,
    PROJECT_MEMORY_FILENAME,
    _claude_project_slug,
    claude_auto_memory_dir,
    export_synapse_memory,
    project_memory_file,
    render_synapse_memory,
)
from neuralmind.synapses import LTP_THRESHOLD, SynapseStore, default_db_path


class _FakeEmbedder:
    """Minimal embedder stub: just exposes a .nodes list for label resolution."""

    def __init__(self, nodes=None):
        self.nodes = nodes or []


def test_claude_project_slug_replaces_separators():
    slug = _claude_project_slug(Path("/home/user/myrepo"))
    assert slug == "-home-user-myrepo"


def test_claude_auto_memory_dir_under_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    target = claude_auto_memory_dir("/some/project")
    assert target.parent.parent.name == "projects"
    assert target.name == "memory"


def test_project_memory_file_path_layout(tmp_path):
    target = project_memory_file(tmp_path)
    assert target.parent.name == ".neuralmind"
    assert target.name == PROJECT_MEMORY_FILENAME


def test_render_handles_empty_store(tmp_path):
    SynapseStore(default_db_path(tmp_path))  # creates empty DB
    out = render_synapse_memory(tmp_path)
    assert "Synapse Memory" in out
    assert "Edges learned: 0" in out
    assert "_(none yet" in out


def test_render_includes_strong_pairs_and_hubs(tmp_path):
    db = default_db_path(tmp_path)
    store = SynapseStore(db)
    # build LTP edge a-b and several hub edges
    for _ in range(LTP_THRESHOLD + 2):
        store.reinforce(["a", "b"])
    for i in range(6):
        store.reinforce(["HUB", f"spoke_{i}"])

    out = render_synapse_memory(tmp_path)
    assert "Strongest associations" in out
    assert "`a` ↔ `b`" in out
    assert "long-term" in out  # LTP tag rendered
    assert "Hub nodes" in out
    assert "HUB" in out


def test_render_uses_labels_when_embedder_provided(tmp_path):
    store = SynapseStore(default_db_path(tmp_path))
    store.reinforce(["node_x", "node_y"])
    embedder = _FakeEmbedder(
        nodes=[
            {"id": "node_x", "label": "authenticate_user"},
            {"id": "node_y", "label": "issue_token"},
        ]
    )
    out = render_synapse_memory(tmp_path, embedder=embedder)
    assert "authenticate_user" in out
    assert "issue_token" in out
    # Raw id still present alongside the label.
    assert "node_x" in out


def test_export_writes_project_local_file(tmp_path, monkeypatch):
    # Force HOME to a clean dir so the auto-memory branch is skipped
    # unless we explicitly create it.
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))
    store = SynapseStore(default_db_path(tmp_path))
    store.reinforce(["a", "b", "c"])

    written = export_synapse_memory(tmp_path)
    assert len(written) == 1
    project_target = project_memory_file(tmp_path)
    assert project_target in written
    text = project_target.read_text()
    assert "Synapse Memory" in text
    assert "Edges learned: 3" in text


def test_export_writes_to_claude_auto_memory_when_dir_exists(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))

    project = tmp_path / "myproj"
    project.mkdir()
    store = SynapseStore(default_db_path(project))
    store.reinforce(["x", "y"])

    auto_dir = claude_auto_memory_dir(project)
    auto_dir.mkdir(parents=True, exist_ok=True)

    written = export_synapse_memory(project)
    written_names = [p.name for p in written]
    assert PROJECT_MEMORY_FILENAME in written_names
    assert CLAUDE_AUTO_FILENAME in written_names
    assert (auto_dir / CLAUDE_AUTO_FILENAME).read_text().startswith("# NeuralMind")


def test_export_skips_auto_memory_when_dir_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "no_claude"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "no_claude"))
    store = SynapseStore(default_db_path(tmp_path))
    store.reinforce(["a", "b"])
    written = export_synapse_memory(tmp_path)
    assert len(written) == 1
    assert written[0].name == PROJECT_MEMORY_FILENAME


def test_export_can_be_disabled_via_flag(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    project = tmp_path / "p"
    project.mkdir()
    store = SynapseStore(default_db_path(project))
    store.reinforce(["a", "b"])
    auto_dir = claude_auto_memory_dir(project)
    auto_dir.mkdir(parents=True, exist_ok=True)

    written = export_synapse_memory(project, write_claude_auto_memory=False)
    names = [p.name for p in written]
    assert PROJECT_MEMORY_FILENAME in names
    assert CLAUDE_AUTO_FILENAME not in names


def test_export_overwrites_on_repeat_call(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "h"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "h"))
    store = SynapseStore(default_db_path(tmp_path))
    store.reinforce(["a", "b"])
    export_synapse_memory(tmp_path)
    first = project_memory_file(tmp_path).read_text()
    # second reinforce shifts weights → output should change
    for _ in range(10):
        store.reinforce(["a", "b"])
    export_synapse_memory(tmp_path)
    second = project_memory_file(tmp_path).read_text()
    assert second != first
