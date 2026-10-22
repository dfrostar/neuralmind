"""Tests for backend manager and backend config loading."""

import importlib.util
import json

import pytest

from neuralmind import backend_manager as bm
from neuralmind.backend_manager import (
    DEFAULT_BACKEND_CONFIG,
    BackendManager,
    create_backend,
    load_backend_config,
    resolve_backend,
)
from neuralmind.in_memory_backend import InMemoryEmbeddingBackend

# ChromaDB is an opt-in extra as of v0.29.0 — the chroma (`graph`) backend tests
# skip cleanly on a ChromaDB-free install and run in the `[dev,chromadb]` CI job.
_HAS_CHROMADB = importlib.util.find_spec("chromadb") is not None
requires_chromadb = pytest.mark.skipif(
    not _HAS_CHROMADB, reason="needs the optional [chromadb] extra"
)


@requires_chromadb
def test_backend_factory_aliases(temp_project):
    from neuralmind.embedder import GraphEmbedder

    assert isinstance(create_backend("graph", str(temp_project)), GraphEmbedder)
    assert isinstance(create_backend("chroma", str(temp_project)), GraphEmbedder)
    assert isinstance(create_backend("chromadb", str(temp_project)), GraphEmbedder)
    assert isinstance(create_backend("in_memory", str(temp_project)), InMemoryEmbeddingBackend)


@pytest.mark.skipif(_HAS_CHROMADB, reason="only meaningful without the [chromadb] extra")
def test_create_backend_graph_without_chromadb_is_actionable(temp_project):
    # Selecting the chroma backend without the optional extra must raise an
    # actionable error pointing at `pip install neuralmind[chromadb]`, not an
    # opaque ModuleNotFoundError from deep in the import.
    with pytest.raises(ModuleNotFoundError, match=r"neuralmind\[chromadb\]"):
        create_backend("graph", str(temp_project))


def test_default_backend_is_turbovec():
    assert DEFAULT_BACKEND_CONFIG["backend"] == "turbovec"


def test_resolve_backend_explicit_passthrough():
    # Explicit, concrete names are normalised but never auto-resolved.
    assert resolve_backend("graph") == "graph"
    assert resolve_backend("Chroma") == "chroma"
    assert resolve_backend("turbovec") == "turbovec"
    assert resolve_backend("in_memory") == "in_memory"


def test_resolve_backend_auto_prefers_turbovec_when_available(monkeypatch):
    monkeypatch.setattr(bm, "turbovec_available", lambda: True)
    assert resolve_backend("auto") == "turbovec"
    assert resolve_backend(None) == "turbovec"
    assert resolve_backend("AUTO") == "turbovec"


def test_resolve_backend_chroma_deprecated(monkeypatch):
    # chroma/graph/chromadb are deprecated but still honored when [chromadb] is installed
    with pytest.warns(DeprecationWarning, match="ChromaDB"):
        assert resolve_backend("graph") == "graph"
    with pytest.warns(DeprecationWarning, match="ChromaDB"):
        assert resolve_backend("chroma") == "chroma"
    with pytest.warns(DeprecationWarning, match="ChromaDB"):
        assert resolve_backend("chromadb") == "chromadb"


def test_resolve_backend_non_string_or_blank_is_turbovec(monkeypatch):
    # YAML `backend: null` parses to None; blanks and non-strings must all mean
    # turbovec (never a pinned backend literally named "none"/"123"), and must not raise.
    assert resolve_backend(None) == "turbovec"
    assert resolve_backend("") == "turbovec"
    assert resolve_backend("   ") == "turbovec"
    assert resolve_backend(123) == "turbovec"  # type: ignore[arg-type]
    assert resolve_backend(True) == "turbovec"  # type: ignore[arg-type]


def _only_installed(monkeypatch, *modules):
    """Pretend only ``modules`` are importable, as on a given platform's install."""
    monkeypatch.setattr(bm, "_installed", lambda module: module in modules)


def test_default_falls_back_to_chromadb_where_turbovec_has_no_wheel(monkeypatch, recwarn):
    # Intel macOS and Windows ARM: pyproject.toml installs ChromaDB in place of
    # the turbovec stack. v0.46.0's hard default left them selecting turbovec
    # anyway, and every build failed with "No module named 'turbovec'".
    _only_installed(monkeypatch, "chromadb")
    for default in (None, "", "auto", "turbovec", DEFAULT_BACKEND_CONFIG["backend"]):
        assert resolve_backend(default) == "graph"
    # The user didn't choose ChromaDB, so no deprecation warning for it.
    assert not [w for w in recwarn if issubclass(w.category, DeprecationWarning)]


def test_default_stays_turbovec_where_its_stack_is_installed(monkeypatch):
    _only_installed(monkeypatch, "turbovec", "onnxruntime", "tokenizers", "chromadb")
    assert resolve_backend(None) == "turbovec"
    assert resolve_backend("turbovec") == "turbovec"


def test_default_stays_turbovec_when_neither_backend_is_installed(monkeypatch):
    # Nothing to fall back to: create_backend then says what to install.
    _only_installed(monkeypatch)
    assert resolve_backend(None) == "turbovec"


def test_explicit_non_default_backends_are_never_rerouted(monkeypatch):
    _only_installed(monkeypatch, "chromadb")
    assert resolve_backend("in_memory") == "in_memory"
    with pytest.warns(DeprecationWarning):
        assert resolve_backend("graph") == "graph"


def test_create_backend_turbovec_without_turbovec_is_actionable(temp_project, monkeypatch):
    # turbovec is imported only when the index loads, deep inside a build; the
    # missing module must be named up front, with what to install.
    _only_installed(monkeypatch)
    with pytest.raises(ModuleNotFoundError, match=r"pip install turbovec") as exc:
        create_backend("turbovec", str(temp_project))
    assert "neuralmind[chromadb]" in str(exc.value)


def test_load_backend_config_yaml(temp_project):
    config_file = temp_project / "neuralmind-backend.yaml"
    config_file.write_text("backend: in_memory\nhybrid_context: true\n", encoding="utf-8")

    config = load_backend_config(temp_project)
    assert config["backend"] == "in_memory"
    assert config["hybrid_context"] is True


def test_load_backend_config_json(temp_project):
    config_file = temp_project / "neuralmind-backend.json"
    config_file.write_text(json.dumps({"backend": "graph"}), encoding="utf-8")

    config = load_backend_config(temp_project)
    assert config["backend"] == "graph"


@requires_chromadb
def test_backend_manager_switches_backend(temp_project):
    from neuralmind.embedder import GraphEmbedder

    manager = BackendManager(str(temp_project), backend="in_memory")
    assert isinstance(manager.backend, InMemoryEmbeddingBackend)

    manager.switch_backend("graph")
    assert isinstance(manager.backend, GraphEmbedder)
