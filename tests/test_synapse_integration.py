"""Integration smoke tests for the synapse layer's wiring into core + MCP.

These tests stub the embedder so they don't require chromadb or a built
graph — they verify only the wiring (activation paths, MCP handler shape,
and the SynapseStore lifecycle).
"""

from __future__ import annotations

from neuralmind.synapses import SynapseStore, default_db_path


class _FakeEmbedder:
    """Minimal embedder stub: get_file_nodes + search."""

    def __init__(self, file_to_nodes=None, search_hits=None):
        self.file_to_nodes = file_to_nodes or {}
        self._search_hits = search_hits or []
        self.project_path = None

    def get_file_nodes(self, source_file):
        return self.file_to_nodes.get(source_file, [])

    def search(self, query, n=10, **kwargs):
        return self._search_hits[:n]

    def get_stats(self):
        return {"total_nodes": 0, "communities": 0}

    def load_graph(self):
        return True

    def embed_nodes(self, force=False):
        return {"added": 0, "updated": 0, "skipped": 0}


class _FakeMind:
    """Stand-in NeuralMind that exposes only what activate_files needs."""

    def __init__(self, project_path, embedder, store):
        self.project_path = project_path
        self.embedder = embedder
        self._store = store
        self._built = True

    def _ensure_built(self):
        return None

    @property
    def synapses(self):
        return self._store

    def activate(self, node_ids, strength=1.0):
        if not node_ids:
            return 0
        return self._store.reinforce(node_ids, strength=strength)

    # Mirrors the real activate_files implementation.
    def activate_files(self, file_paths, strength=1.0):
        if not file_paths:
            return 0
        node_ids = []
        for path in file_paths:
            for node in self.embedder.get_file_nodes(path):
                nid = node.get("id")
                if nid:
                    node_ids.append(str(nid))
        if len(node_ids) < 2:
            return 0
        return self.activate(node_ids, strength=strength)


def test_activate_files_resolves_paths_to_node_ids(tmp_path):
    embedder = _FakeEmbedder(
        file_to_nodes={
            "auth.py": [{"id": "n1"}, {"id": "n2"}],
            "session.py": [{"id": "n3"}],
        }
    )
    store = SynapseStore(default_db_path(tmp_path))
    mind = _FakeMind(tmp_path, embedder, store)

    pairs = mind.activate_files(["auth.py", "session.py"])
    assert pairs == 3  # n1-n2, n1-n3, n2-n3
    n1_neighbors = dict(store.neighbors("n1"))
    assert "n2" in n1_neighbors and "n3" in n1_neighbors


def test_activate_files_with_unknown_path_is_noop(tmp_path):
    embedder = _FakeEmbedder()
    store = SynapseStore(default_db_path(tmp_path))
    mind = _FakeMind(tmp_path, embedder, store)
    assert mind.activate_files(["never_seen.py"]) == 0
    assert store.stats()["edges"] == 0


def test_activate_files_with_single_node_is_noop(tmp_path):
    embedder = _FakeEmbedder(file_to_nodes={"only.py": [{"id": "solo"}]})
    store = SynapseStore(default_db_path(tmp_path))
    mind = _FakeMind(tmp_path, embedder, store)
    assert mind.activate_files(["only.py"]) == 0


def test_synapse_store_path_is_inside_project(tmp_path):
    db = default_db_path(tmp_path)
    assert db.parent.name == ".neuralmind"
    assert db.name == "synapses.db"


def test_repeat_co_activation_strengthens_pair(tmp_path):
    embedder = _FakeEmbedder(
        file_to_nodes={
            "x.py": [{"id": "x"}],
            "y.py": [{"id": "y"}],
        }
    )
    store = SynapseStore(default_db_path(tmp_path))
    mind = _FakeMind(tmp_path, embedder, store)

    mind.activate_files(["x.py", "y.py"])
    first = dict(store.neighbors("x"))["y"]
    mind.activate_files(["x.py", "y.py"])
    second = dict(store.neighbors("x"))["y"]
    assert second > first
