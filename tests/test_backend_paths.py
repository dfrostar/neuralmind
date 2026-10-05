"""A relative ``db_path`` names a directory in the project, not in the CWD.

``db_path: vecdb`` in ``neuralmind-backend.yaml`` resolved against the
current directory: a build from one directory wrote ``<cwd>/vecdb``, ``stats``
from another reported ``Built: False``, and a query there silently built a
second index. It now resolves against the project root, wherever the command
runs from.
"""

from __future__ import annotations

import hashlib
import io
from pathlib import Path

import numpy as np
import pytest

from neuralmind.backend_manager import BackendManager, resolve_db_path

_DIM = 32


def _fake_embed(texts: list[str]) -> list[list[float]]:
    out = []
    for t in texts:
        vec = np.zeros(_DIM, dtype=np.float32)
        for tok in t.lower().replace("\n", " ").split():
            vec[int.from_bytes(hashlib.md5(tok.encode()).digest()[:4], "little") % _DIM] += 1.0
        out.append(vec.tolist())
    return out


@pytest.fixture
def dirs(tmp_path) -> tuple[Path, Path, Path]:
    project = tmp_path / "proj"
    project.mkdir()
    (project / "neuralmind-backend.yaml").write_text("db_path: vecdb\n", encoding="utf-8")
    cwd_a = tmp_path / "cwdA"
    cwd_b = tmp_path / "cwdB"
    cwd_a.mkdir()
    cwd_b.mkdir()
    return project, cwd_a, cwd_b


def test_resolve_db_path(tmp_path):
    # Real absolute paths: "/srv/proj" has no drive on Windows, so it isn't one.
    root = tmp_path / "proj"
    absolute = tmp_path / "abs" / "vec"
    assert resolve_db_path(root, "vecdb") == str(root.resolve() / "vecdb")
    assert resolve_db_path(root, str(absolute)) == str(absolute)
    assert resolve_db_path(root, None) is None
    assert resolve_db_path(root, ":memory:") == ":memory:"
    assert resolve_db_path(root, "~/vec") == str(Path("~/vec").expanduser())


@pytest.mark.parametrize("backend", ["turbovec", "in_memory"])
def test_config_db_path_is_project_relative_from_any_cwd(dirs, monkeypatch, backend):
    pytest.importorskip("turbovec")
    project, cwd_a, cwd_b = dirs
    for cwd in (cwd_a, cwd_b):
        monkeypatch.chdir(cwd)
        manager = BackendManager(str(project), backend=backend)
        try:
            if backend == "turbovec":
                assert Path(manager.backend.db_path) == project.resolve() / "vecdb"
            else:
                assert manager.backend.db_path == str(project.resolve() / "vecdb")
        finally:
            if hasattr(manager.backend, "close"):
                manager.backend.close()
    assert not (cwd_a / "vecdb").exists()
    assert not (cwd_b / "vecdb").exists()


def test_turbovec_relative_db_path_is_project_relative(dirs, monkeypatch):
    pytest.importorskip("turbovec")
    from neuralmind.turbovec_backend import TurboVecEmbedder

    project, cwd_a, _ = dirs
    monkeypatch.chdir(cwd_a)
    backend = TurboVecEmbedder(str(project), db_path="elsewhere")
    try:
        assert Path(backend.db_path) == project.resolve() / "elsewhere"
        assert (project / "elsewhere").is_dir()
        assert not (cwd_a / "elsewhere").exists()
    finally:
        backend.close()


def test_build_in_one_cwd_is_found_from_another(dirs, monkeypatch):
    pytest.importorskip("turbovec")
    from neuralmind import graphgen
    from neuralmind.core import NeuralMind

    if not graphgen.is_available():
        pytest.skip("tree-sitter not installed")
    project, cwd_a, cwd_b = dirs
    (project / "billing.py").write_text(
        'def charge_card(amount):\n    """Charge a card."""\n    return amount\n',
        encoding="utf-8",
    )

    monkeypatch.chdir(cwd_a)
    mind = NeuralMind(str(project), enable_synapses=False)
    mind.embedder._embed_fn = _fake_embed
    mind.notice_stream = io.StringIO()
    try:
        assert mind.build(regenerate_graph=True)["success"]
        built_nodes = mind.embedder.get_stats()["total_nodes"]
    finally:
        mind.close()
    assert built_nodes > 0

    monkeypatch.chdir(cwd_b)
    mind = NeuralMind(str(project), enable_synapses=False)
    try:
        assert mind.embedder.get_stats()["total_nodes"] == built_nodes
    finally:
        mind.close()
    assert (project / "vecdb").is_dir()
    assert not (cwd_a / "vecdb").exists()
    assert not (cwd_b / "vecdb").exists()
