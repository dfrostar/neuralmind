"""``update_files`` honours ``.neuralmind.yaml`` include/exclude like a build.

``neuralmind watch --reindex`` re-indexes edited files through
``NeuralMind.update_files``. It filtered paths through the ignore files but
not through the config's ``include:``/``exclude:`` globs, so after
``exclude: ['tests/**']`` editing a test file put it into the graph.

Embeddings use a deterministic hashing function injected into the turbovec
backend, so nothing here needs the ONNX model.
"""

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path

import numpy as np
import pytest

from neuralmind import graphgen

pytest.importorskip("turbovec")
pytestmark = pytest.mark.skipif(not graphgen.is_available(), reason="tree-sitter not installed")

_DIM = 32


def _fake_embed(texts: list[str]) -> list[list[float]]:
    out = []
    for t in texts:
        vec = np.zeros(_DIM, dtype=np.float32)
        for tok in t.lower().replace("\n", " ").split():
            vec[int.from_bytes(hashlib.md5(tok.encode()).digest()[:4], "little") % _DIM] += 1.0
        out.append(vec.tolist())
    return out


def _mind(root: Path):
    from neuralmind.core import NeuralMind

    mind = NeuralMind(str(root), backend_type="turbovec", enable_synapses=False)
    mind.embedder._embed_fn = _fake_embed
    mind.notice_stream = io.StringIO()
    return mind


def _graph_files(root: Path) -> set[str]:
    graph = json.loads((root / ".neuralmind" / "graph.json").read_text(encoding="utf-8"))
    return {n["source_file"] for n in graph["nodes"]}


def _project(root: Path, config: str) -> Path:
    files = {
        ".neuralmind.yaml": config,
        "src/app.py": "def f():\n    return 1\n",
        "tests/test_app.py": "def test_f():\n    pass\n",
        "notes/todo.md": "# Todo\n\nShip it.\n",
    }
    for rel, text in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return root


@pytest.mark.parametrize(
    "config, edited",
    [
        ("exclude:\n  - 'tests/**'\n", "tests/test_app.py"),
        ("include:\n  - 'src/**'\n", "tests/test_app.py"),
        ("include:\n  - 'src/**'\n", "notes/todo.md"),
    ],
)
def test_update_files_skips_files_the_config_excludes(tmp_path, config, edited):
    root = _project(tmp_path / "proj", config)
    mind = _mind(root)
    try:
        assert mind.build(regenerate_graph=True)["success"]
        assert edited not in _graph_files(root)  # precondition: the build excluded it

        (root / edited).write_text((root / edited).read_text() + "\n# edited\n")
        stats = mind.update_files([str(root / edited)])

        assert stats["success"]
        assert edited not in _graph_files(root)
        assert edited not in {
            h["metadata"].get("source_file")
            for h in mind.query("test_f todo", learn=False).top_search_hits
        }
    finally:
        mind.close()


def test_update_files_still_reindexes_included_files(tmp_path):
    root = _project(tmp_path / "proj", "exclude:\n  - 'tests/**'\n")
    mind = _mind(root)
    try:
        assert mind.build(regenerate_graph=True)["success"]
        (root / "src" / "app.py").write_text("def f():\n    return 1\n\n\ndef g():\n    return 2\n")
        stats = mind.update_files([str(root / "src" / "app.py")])
    finally:
        mind.close()
    assert stats["success"] and stats["files_reparsed"] == 1
    graph = json.loads((root / ".neuralmind" / "graph.json").read_text(encoding="utf-8"))
    assert any(
        n["label"].startswith("g") and n["source_file"] == "src/app.py" for n in graph["nodes"]
    )
