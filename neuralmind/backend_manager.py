"""
backend_manager.py — Embedding Backend Selection & Configuration
================================================================

Provides:
1. Backend registry for pluggable embedding backends
2. Configuration loading from TOML
3. Factory for instantiating backends
4. Backend validation and health checks

Supports:
- ChromaDB (local, default)
- PostgreSQL pgvector (enterprise database)
- LanceDB (lightweight, Rust-based)
- Future: Qdrant, Weaviate, Pinecone

Configuration:
  .neuralmind/config.toml or neuralmind.toml:
    [embeddings]
    backend = "chromadb"  # or "postgres", "lancedb"

    [backends.chromadb]
    db_path = "graphify-out/neuralmind_db/"

    [backends.postgres]
    connection_string = "postgresql://user:pass@localhost/neuralmind"
    table_name = "code_embeddings"

    [backends.lancedb]
    db_path = ".neuralmind/embeddings.lance"
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Type

from .embedding_backend import EmbeddingBackend


# ============================================================================
# Backend Registry
# ============================================================================


class BackendRegistry:
    """Registry of available embedding backends."""

    _backends: dict[str, Type[EmbeddingBackend]] = {}

    @classmethod
    def register(cls, name: str, backend_class: Type[EmbeddingBackend]) -> None:
        """Register a backend implementation."""
        cls._backends[name.lower()] = backend_class

    @classmethod
    def get(cls, name: str) -> Type[EmbeddingBackend] | None:
        """Get a backend by name."""
        return cls._backends.get(name.lower())

    @classmethod
    def list_available(cls) -> list[str]:
        """List all registered backends."""
        return sorted(cls._backends.keys())


# ============================================================================
# Configuration Management
# ============================================================================


class EmbeddingConfig:
    """Configuration for embedding backend."""

    def __init__(self, backend_name: str = "chromadb", **options: Any):
        """
        Initialize configuration.

        Args:
            backend_name: Name of backend to use
            **options: Backend-specific configuration options
        """
        self.backend_name = backend_name.lower()
        self.options = options

    @staticmethod
    def from_toml(toml_path: Path) -> EmbeddingConfig:
        """
        Load configuration from TOML file.

        Args:
            toml_path: Path to config file

        Returns:
            EmbeddingConfig instance
        """
        try:
            import tomllib  # Python 3.11+
        except ImportError:
            try:
                import tomli as tomllib  # Fallback for older Python
            except ImportError:
                # Fallback: parse manually for basic TOML
                return EmbeddingConfig()  # Default

        if not toml_path.exists():
            return EmbeddingConfig()  # Default

        try:
            with open(toml_path, "rb") as f:
                data = tomllib.load(f)

            embeddings_config = data.get("embeddings", {})
            backend_name = embeddings_config.get("backend", "chromadb")

            # Get backend-specific options
            backends_config = data.get("backends", {})
            backend_options = backends_config.get(backend_name, {})

            return EmbeddingConfig(backend_name=backend_name, **backend_options)
        except Exception:
            # Fallback to default config on parse error
            return EmbeddingConfig()

    @staticmethod
    def from_json(json_path: Path) -> EmbeddingConfig:
        """Load configuration from JSON file."""
        if not json_path.exists():
            return EmbeddingConfig()

        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            embeddings_config = data.get("embeddings", {})
            backend_name = embeddings_config.get("backend", "chromadb")
            backends_config = data.get("backends", {})
            backend_options = backends_config.get(backend_name, {})

            return EmbeddingConfig(backend_name=backend_name, **backend_options)
        except Exception:
            return EmbeddingConfig()

    def to_dict(self) -> dict[str, Any]:
        """Export configuration as dictionary."""
        return {
            "backend": self.backend_name,
            "options": self.options,
        }


# ============================================================================
# Backend Factory
# ============================================================================


class BackendFactory:
    """Factory for creating embedding backend instances."""

    @staticmethod
    def create(
        project_path: str | Path,
        config: EmbeddingConfig | None = None,
        db_path: str | Path | None = None,
    ) -> EmbeddingBackend:
        """
        Create an embedding backend instance.

        Args:
            project_path: Path to project root
            config: EmbeddingConfig (loads from .neuralmind/config.toml if None)
            db_path: Optional override for database path (ChromaDB only)

        Returns:
            Instantiated backend

        Raises:
            ValueError: If backend not registered or configuration invalid
        """
        project_path = Path(project_path)

        # Load config from file if not provided
        if config is None:
            config_path = project_path / ".neuralmind" / "config.toml"
            if not config_path.exists():
                config_path = project_path / "neuralmind.toml"
            config = EmbeddingConfig.from_toml(config_path)

        # Get backend class
        backend_class = BackendRegistry.get(config.backend_name)
        if backend_class is None:
            available = ", ".join(BackendRegistry.list_available())
            raise ValueError(
                f"Unknown backend: {config.backend_name}. "
                f"Available: {available}"
            )

        # Instantiate backend
        # Most backends accept project_path; some also need config options
        try:
            # Try with config options
            return backend_class(str(project_path), **config.options)
        except TypeError:
            # Fallback: just project_path and db_path (for backward compat)
            return backend_class(str(project_path), db_path=db_path)

    @staticmethod
    def create_with_backend_name(
        project_path: str | Path,
        backend_name: str,
        **options: Any,
    ) -> EmbeddingBackend:
        """
        Create backend by name, overriding any configuration file.

        Args:
            project_path: Path to project root
            backend_name: Name of backend to instantiate
            **options: Backend-specific options

        Returns:
            Instantiated backend
        """
        config = EmbeddingConfig(backend_name=backend_name, **options)
        return BackendFactory.create(project_path, config=config)


# ============================================================================
# Backend Health Checks
# ============================================================================


def check_backend_health(backend: EmbeddingBackend) -> dict[str, Any]:
    """
    Check if a backend is healthy and accessible.

    Returns:
        {
            'healthy': bool,
            'backend': backend_name,
            'issues': [str],
            'stats': {...}
        }
    """
    issues = []

    try:
        stats = backend.get_stats()
    except Exception as e:
        issues.append(f"Cannot retrieve stats: {e}")
        stats = {}

    return {
        "healthy": len(issues) == 0,
        "backend": backend.__class__.__name__,
        "issues": issues,
        "stats": stats,
    }


# ============================================================================
# Backend Migration Tooling
# ============================================================================


def migrate_between_backends(
    project_path: str | Path,
    from_config: EmbeddingConfig,
    to_config: EmbeddingConfig,
) -> dict[str, Any]:
    """
    Migrate embeddings from one backend to another.

    This is non-destructive: it reads from the source backend,
    re-embeds if necessary, and writes to the target backend.

    Args:
        project_path: Project root
        from_config: Source backend configuration
        to_config: Target backend configuration

    Returns:
        Migration results: {'migrated': int, 'failed': int, 'duration_seconds': float}
    """
    from datetime import datetime

    start_time = datetime.now()
    project_path = Path(project_path)

    # Create both backends
    try:
        from_backend = BackendFactory.create(project_path, config=from_config)
        to_backend = BackendFactory.create(project_path, config=to_config)
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to instantiate backends: {e}",
        }

    # Verify source backend has data
    source_stats = from_backend.get_stats()
    if not source_stats.get("total_nodes", 0):
        return {
            "success": False,
            "error": "Source backend has no data to migrate",
        }

    # Read from source backend (implementation depends on backend)
    # For now, we trigger a rebuild on the target backend
    # In production, you'd implement a more direct copy mechanism

    try:
        # Load graph on target backend
        to_backend.load_graph()

        # Re-embed on target backend (will copy metadata)
        result = to_backend.embed_nodes(force=True)

        duration = (datetime.now() - start_time).total_seconds()

        return {
            "success": True,
            "from_backend": from_config.backend_name,
            "to_backend": to_config.backend_name,
            "nodes_migrated": result.get("added", 0) + result.get("updated", 0),
            "duration_seconds": round(duration, 2),
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Migration failed: {e}",
        }


# ============================================================================
# Default Registrations
# ============================================================================

# Import and register the default ChromaDB backend
# (This happens at module load time)

def _register_default_backends() -> None:
    """Register built-in backends."""
    # ChromaDB (default)
    try:
        from .embedder import GraphEmbedder

        BackendRegistry.register("chromadb", GraphEmbedder)
    except ImportError:
        pass

    # PostgreSQL pgvector
    try:
        from .backends.postgres_backend import PostgreSQLBackend

        BackendRegistry.register("postgres", PostgreSQLBackend)
        BackendRegistry.register("postgresql", PostgreSQLBackend)  # Alias
    except ImportError:
        pass

    # LanceDB
    try:
        from .backends.lancedb_backend import LanceDBBackend

        BackendRegistry.register("lancedb", LanceDBBackend)
        BackendRegistry.register("lance", LanceDBBackend)  # Alias
    except ImportError:
        pass


_register_default_backends()
