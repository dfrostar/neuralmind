"""Tests for the project registry module."""

from pathlib import Path

from neuralmind.project_registry import REGISTRY_PATH, ProjectRegistry


def test_default_registry_path():
    assert REGISTRY_PATH == Path.home() / ".config" / "neuralmind" / "projects.json"


def test_empty_registry_on_first_use(tmp_path, monkeypatch):
    monkeypatch.setenv("NEURALMIND_CONFIG_DIR", str(tmp_path))
    reg = ProjectRegistry()
    assert reg.list_projects() == []


def test_add_and_list_project(tmp_path, monkeypatch):
    monkeypatch.setenv("NEURALMIND_CONFIG_DIR", str(tmp_path))
    reg = ProjectRegistry()
    # Use tmp_path-based paths to avoid cross-platform resolve() differences
    cmmc20 = str(tmp_path / "cmmc20")
    neuralmind = str(tmp_path / "neuralmind")
    reg.add_project(cmmc20, scopes=["code", "content"])
    reg.add_project(neuralmind, scopes=["code"])
    projects = reg.list_projects()
    assert len(projects) == 2
    assert projects[0]["path"] == str(Path(cmmc20).resolve())
    assert projects[0]["scopes"] == ["code", "content"]


def test_remove_project(tmp_path, monkeypatch):
    monkeypatch.setenv("NEURALMIND_CONFIG_DIR", str(tmp_path))
    reg = ProjectRegistry()
    cmmc20 = str(tmp_path / "cmmc20")
    reg.add_project(cmmc20, scopes=["code"])
    reg.remove_project(cmmc20)
    assert reg.list_projects() == []


def test_persist_to_disk(tmp_path, monkeypatch):
    monkeypatch.setenv("NEURALMIND_CONFIG_DIR", str(tmp_path))
    reg = ProjectRegistry()
    cmmc20 = str(tmp_path / "cmmc20")
    reg.add_project(cmmc20, scopes=["code", "content"])

    # Reload from disk
    reg2 = ProjectRegistry()
    projects = reg2.list_projects()
    assert len(projects) == 1
    assert projects[0]["path"] == str(Path(cmmc20).resolve())


def test_get_project(tmp_path, monkeypatch):
    monkeypatch.setenv("NEURALMIND_CONFIG_DIR", str(tmp_path))
    reg = ProjectRegistry()
    cmmc20 = str(tmp_path / "cmmc20")
    reg.add_project(cmmc20, scopes=["code", "content"])
    proj = reg.get_project(cmmc20)
    assert proj is not None
    assert proj["scopes"] == ["code", "content"]
    assert reg.get_project(str(tmp_path / "nonexistent")) is None


def test_update_existing_project(tmp_path, monkeypatch):
    monkeypatch.setenv("NEURALMIND_CONFIG_DIR", str(tmp_path))
    reg = ProjectRegistry()
    cmmc20 = str(tmp_path / "cmmc20")
    reg.add_project(cmmc20, scopes=["code"])
    reg.add_project(cmmc20, scopes=["code", "content"])
    projects = reg.list_projects()
    assert len(projects) == 1
    assert projects[0]["scopes"] == ["code", "content"]
