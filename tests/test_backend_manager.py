"""Tests for NeuralMind backend manager (pluggable embedding backends)."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from neuralmind.backend_manager import (
    BackendFactory,
    BackendRegistry,
    EmbeddingConfig,
    check_backend_health,
    migrate_between_backends,
)
from neuralmind.embedding_backend import EmbeddingBackend


# ============================================================================
# Test Fixtures
# ============================================================================


class MockBackend(EmbeddingBackend):
    """Mock embedding backend for testing."""

    def __init__(self, project_path: str, **kwargs):
        self._project_path = Path(project_path)
        self.options = kwargs
        self._initialized = True

    @property
    def project_path(self) -> Path:
        return self._project_path

    def get_stats(self):
        return {"total_nodes": 100, "total_embeddings": 100}

    def load_graph(self):
        return True

    def embed_nodes(self, force=False):
        return {"added": 50, "updated": 0}

    def search(self, query: str, n: int = 5, where=None):
        return []

    def get_community_summary(self, community_id: int, max_nodes: int = 20):
        return {"id": community_id, "summary": "test", "node_count": 0}

    def get_file_nodes(self, source_file: str):
        return []

    def get_file_edges(self, source_file: str, node_ids=None):
        return []

    def clear(self):
        pass

    def close(self):
        pass


class BrokenBackend(EmbeddingBackend):
    """Backend that fails on initialization."""

    def __init__(self, project_path: str, **kwargs):
        raise RuntimeError("Backend initialization failed")

    @property
    def project_path(self) -> Path:
        return Path(".")

    def get_stats(self):
        return {}

    def load_graph(self):
        return False

    def embed_nodes(self, force=False):
        return {}

    def search(self, query: str, n: int = 5, where=None):
        return []

    def get_community_summary(self, community_id: int, max_nodes: int = 20):
        return {}

    def get_file_nodes(self, source_file: str):
        return []

    def get_file_edges(self, source_file: str, node_ids=None):
        return []

    def clear(self):
        pass

    def close(self):
        pass


@pytest.fixture
def temp_project(tmp_path):
    """Create a temporary project directory."""
    project_path = tmp_path / "test_project"
    project_path.mkdir()
    (project_path / ".neuralmind").mkdir()
    return project_path


@pytest.fixture
def clean_registry():
    """Clean registry before each test."""
    # Store original backends
    original_backends = BackendRegistry._backends.copy()
    BackendRegistry._backends.clear()

    yield

    # Restore original backends
    BackendRegistry._backends = original_backends


# ============================================================================
# Test BackendRegistry
# ============================================================================


def test_backend_registry_register_and_get(clean_registry):
    """Test registering and retrieving a backend."""
    BackendRegistry.register("mock", MockBackend)

    backend_class = BackendRegistry.get("mock")
    assert backend_class is MockBackend


def test_backend_registry_case_insensitive(clean_registry):
    """Test that registry is case-insensitive."""
    BackendRegistry.register("MockBackend", MockBackend)

    assert BackendRegistry.get("mockbackend") is MockBackend
    assert BackendRegistry.get("MOCKBACKEND") is MockBackend


def test_backend_registry_get_nonexistent(clean_registry):
    """Test getting a non-existent backend."""
    result = BackendRegistry.get("nonexistent")
    assert result is None


def test_backend_registry_list_available(clean_registry):
    """Test listing available backends."""
    BackendRegistry.register("mock1", MockBackend)
    BackendRegistry.register("mock2", MockBackend)

    available = BackendRegistry.list_available()
    assert "mock1" in available
    assert "mock2" in available
    assert available == sorted(available)  # Should be sorted


def test_backend_registry_register_override(clean_registry):
    """Test that re-registering overrides previous."""
    BackendRegistry.register("mock", MockBackend)
    BackendRegistry.register("mock", BrokenBackend)

    backend_class = BackendRegistry.get("mock")
    assert backend_class is BrokenBackend


# ============================================================================
# Test EmbeddingConfig
# ============================================================================


def test_embedding_config_default():
    """Test default config."""
    config = EmbeddingConfig()

    assert config.backend_name == "chromadb"
    assert config.options == {}


def test_embedding_config_custom():
    """Test custom config."""
    config = EmbeddingConfig(
        backend_name="postgres",
        connection_string="postgresql://localhost/test",
        table_name="embeddings"
    )

    assert config.backend_name == "postgres"
    assert config.options["connection_string"] == "postgresql://localhost/test"
    assert config.options["table_name"] == "embeddings"


def test_embedding_config_case_insensitive():
    """Test that backend names are case-insensitive."""
    config = EmbeddingConfig(backend_name="ChromaDB")
    assert config.backend_name == "chromadb"


def test_embedding_config_to_dict():
    """Test exporting config to dict."""
    config = EmbeddingConfig(
        backend_name="postgres",
        connection_string="postgresql://localhost"
    )

    result = config.to_dict()
    assert result["backend"] == "postgres"
    assert result["options"]["connection_string"] == "postgresql://localhost"


def test_embedding_config_from_toml_default(tmp_path):
    """Test loading config from missing TOML file."""
    config_path = tmp_path / "missing.toml"
    config = EmbeddingConfig.from_toml(config_path)

    assert config.backend_name == "chromadb"


def test_embedding_config_from_toml_basic(tmp_path):
    """Test loading config from TOML file."""
    config_path = tmp_path / "neuralmind.toml"
    config_path.write_text("""
[embeddings]
backend = "postgres"

[backends.postgres]
connection_string = "postgresql://localhost/neuralmind"
table_name = "code_embeddings"
""")

    config = EmbeddingConfig.from_toml(config_path)

    assert config.backend_name == "postgres"
    assert config.options["connection_string"] == "postgresql://localhost/neuralmind"
    assert config.options["table_name"] == "code_embeddings"


def test_embedding_config_from_toml_parse_error(tmp_path):
    """Test loading from invalid TOML."""
    config_path = tmp_path / "invalid.toml"
    config_path.write_text("[invalid syntax [[[")

    config = EmbeddingConfig.from_toml(config_path)

    # Should fall back to default
    assert config.backend_name == "chromadb"


def test_embedding_config_from_json_default(tmp_path):
    """Test loading config from missing JSON file."""
    config_path = tmp_path / "missing.json"
    config = EmbeddingConfig.from_json(config_path)

    assert config.backend_name == "chromadb"


def test_embedding_config_from_json_basic(tmp_path):
    """Test loading config from JSON file."""
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({
        "embeddings": {
            "backend": "lancedb"
        },
        "backends": {
            "lancedb": {
                "db_path": ".neuralmind/embeddings.lance"
            }
        }
    }))

    config = EmbeddingConfig.from_json(config_path)

    assert config.backend_name == "lancedb"
    assert config.options["db_path"] == ".neuralmind/embeddings.lance"


def test_embedding_config_from_json_parse_error(tmp_path):
    """Test loading from invalid JSON."""
    config_path = tmp_path / "invalid.json"
    config_path.write_text("{invalid json")

    config = EmbeddingConfig.from_json(config_path)

    # Should fall back to default
    assert config.backend_name == "chromadb"


# ============================================================================
# Test BackendFactory
# ============================================================================


def test_backend_factory_create_with_config(temp_project, clean_registry):
    """Test creating backend with config."""
    BackendRegistry.register("mock", MockBackend)
    config = EmbeddingConfig(backend_name="mock", db_path="/tmp/test")

    backend = BackendFactory.create(temp_project, config=config)

    assert isinstance(backend, MockBackend)
    assert backend.project_path == Path(temp_project)


def test_backend_factory_create_default(temp_project, clean_registry):
    """Test creating backend with defaults."""
    BackendRegistry.register("chromadb", MockBackend)

    # Create a config file
    config_file = temp_project / ".neuralmind" / "config.toml"
    config_file.parent.mkdir(parents=True, exist_ok=True)
    config_file.write_text("""
[embeddings]
backend = "chromadb"

[backends.chromadb]
db_path = "/tmp/test"
""")

    backend = BackendFactory.create(temp_project)

    assert isinstance(backend, MockBackend)


def test_backend_factory_create_with_backend_name(temp_project, clean_registry):
    """Test creating backend by name."""
    BackendRegistry.register("mock", MockBackend)

    backend = BackendFactory.create_with_backend_name(
        temp_project,
        "mock",
        db_path="/tmp/test"
    )

    assert isinstance(backend, MockBackend)


def test_backend_factory_unknown_backend(temp_project, clean_registry):
    """Test error handling for unknown backend."""
    with pytest.raises(ValueError, match="Unknown backend"):
        BackendFactory.create_with_backend_name(
            temp_project,
            "nonexistent"
        )


def test_backend_factory_initialization_error(temp_project, clean_registry):
    """Test handling of backend initialization errors."""
    BackendRegistry.register("broken", BrokenBackend)
    config = EmbeddingConfig(backend_name="broken")

    with pytest.raises(RuntimeError, match="initialization failed"):
        BackendFactory.create(temp_project, config=config)


def test_backend_factory_fallback_instantiation(temp_project, clean_registry):
    """Test backward compatibility instantiation."""
    class LegacyBackend(EmbeddingBackend):
        def __init__(self, project_path: str, db_path=None):
            self._project_path = Path(project_path)
            self.db_path = db_path
        @property
        def project_path(self) -> Path:
            return self._project_path
        def get_stats(self):
            return {}
        def load_graph(self):
            return False
        def embed_nodes(self, force=False):
            return {}
        def search(self, query: str, n: int = 5, where=None):
            return []
        def get_community_summary(self, community_id: int, max_nodes: int = 20):
            return {}
        def get_file_nodes(self, source_file: str):
            return []
        def get_file_edges(self, source_file: str, node_ids=None):
            return []
        def clear(self):
            pass
        def close(self):
            pass

    BackendRegistry.register("legacy", LegacyBackend)
    config = EmbeddingConfig(backend_name="legacy", db_path="/tmp/test")

    backend = BackendFactory.create(temp_project, config=config)

    assert isinstance(backend, LegacyBackend)
    assert backend.db_path == "/tmp/test"


# ============================================================================
# Test Health Checks
# ============================================================================


def test_check_backend_health_healthy():
    """Test health check on healthy backend."""
    backend = MockBackend(".")

    result = check_backend_health(backend)

    assert result["healthy"] is True
    assert result["backend"] == "MockBackend"
    assert result["issues"] == []
    assert result["stats"]["total_nodes"] == 100


def test_check_backend_health_stats_error():
    """Test health check when stats fails."""
    class FailingBackend(EmbeddingBackend):
        @property
        def project_path(self) -> Path:
            return Path(".")

        def get_stats(self):
            raise RuntimeError("Database connection failed")
        def load_graph(self):
            return False
        def embed_nodes(self, force=False):
            return {}
        def search(self, query: str, n: int = 5, where=None):
            return []
        def get_community_summary(self, community_id: int, max_nodes: int = 20):
            return {}
        def get_file_nodes(self, source_file: str):
            return []
        def get_file_edges(self, source_file: str, node_ids=None):
            return []
        def clear(self):
            pass
        def close(self):
            pass

    backend = FailingBackend()
    result = check_backend_health(backend)

    assert result["healthy"] is False
    assert len(result["issues"]) > 0
    assert "Database connection failed" in result["issues"][0]


# ============================================================================
# Test Backend Migration
# ============================================================================


def test_migrate_between_backends_success(temp_project, clean_registry):
    """Test successful backend migration."""
    BackendRegistry.register("mock", MockBackend)

    from_config = EmbeddingConfig(backend_name="mock")
    to_config = EmbeddingConfig(backend_name="mock")

    result = migrate_between_backends(temp_project, from_config, to_config)

    assert result["success"] is True
    assert result["nodes_migrated"] == 50


def test_migrate_between_backends_no_source_data(temp_project, clean_registry):
    """Test migration when source has no data."""
    class EmptyBackend(EmbeddingBackend):
        def __init__(self, project_path: str, **kwargs):
            self._project_path = Path(project_path)
        @property
        def project_path(self) -> Path:
            return self._project_path
        def get_stats(self):
            return {"total_nodes": 0}
        def load_graph(self):
            return True
        def embed_nodes(self, force=False):
            return {}
        def search(self, query: str, n: int = 5, where=None):
            return []
        def get_community_summary(self, community_id: int, max_nodes: int = 20):
            return {}
        def get_file_nodes(self, source_file: str):
            return []
        def get_file_edges(self, source_file: str, node_ids=None):
            return []
        def clear(self):
            pass
        def close(self):
            pass

    BackendRegistry.register("empty", EmptyBackend)

    from_config = EmbeddingConfig(backend_name="empty")
    to_config = EmbeddingConfig(backend_name="empty")

    result = migrate_between_backends(temp_project, from_config, to_config)

    assert result["success"] is False
    assert "no data" in result["error"].lower()


def test_migrate_between_backends_instantiation_error(temp_project, clean_registry):
    """Test migration when backend instantiation fails."""
    BackendRegistry.register("broken", BrokenBackend)

    from_config = EmbeddingConfig(backend_name="broken")
    to_config = EmbeddingConfig(backend_name="broken")

    result = migrate_between_backends(temp_project, from_config, to_config)

    assert result["success"] is False
    assert "Failed to instantiate" in result["error"]


def test_migrate_between_backends_timing(temp_project, clean_registry):
    """Test that migration records duration."""
    BackendRegistry.register("mock", MockBackend)

    from_config = EmbeddingConfig(backend_name="mock")
    to_config = EmbeddingConfig(backend_name="mock")

    result = migrate_between_backends(temp_project, from_config, to_config)

    assert "duration_seconds" in result
    assert isinstance(result["duration_seconds"], float)
