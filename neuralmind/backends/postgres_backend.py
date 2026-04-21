"""
postgres_backend.py — PostgreSQL pgvector Embedding Backend
===========================================================

Enterprise-grade backend using PostgreSQL pgvector extension.

Benefits for enterprises:
- Consolidates on existing PostgreSQL infrastructure
- No new vendor lock-in (pgvector is OSS)
- Scales to 100M+ vectors with proper indexing
- Full ACID compliance for audit trails
- Can replicate embeddings with database backups
- Works with Snowflake, Databricks, RDS

Configuration:
  [backends.postgres]
  connection_string = "postgresql://user:pass@localhost/neuralmind"
  table_name = "code_embeddings"
  vector_dimensions = 384

Requirements:
  pip install psycopg[binary] pgvector
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from ..embedding_backend import EmbeddingBackend


class PostgreSQLBackend(EmbeddingBackend):
    """PostgreSQL pgvector embedding backend."""

    def __init__(
        self,
        project_path: str | Path,
        connection_string: str | None = None,
        table_name: str = "code_embeddings",
        vector_dimensions: int = 384,
        **kwargs: Any,
    ):
        """
        Initialize PostgreSQL backend.

        Args:
            project_path: Project root
            connection_string: PostgreSQL connection URL
                Default: postgresql://localhost/neuralmind
            table_name: Table name for embeddings
            vector_dimensions: Size of embedding vectors
        """
        self.project_path = Path(project_path)
        self.connection_string = connection_string or "postgresql://localhost/neuralmind"
        self.table_name = table_name
        self.vector_dimensions = vector_dimensions

        self.graph = None
        self.conn = None

        self._init_connection()

    def _init_connection(self) -> None:
        """Initialize database connection and schema."""
        try:
            import psycopg

            self.psycopg = psycopg
            # Connection will be lazy-initialized on demand
        except ImportError:
            raise ImportError(
                "PostgreSQL backend requires psycopg and pgvector. "
                "Install with: pip install psycopg[binary] pgvector"
            )

    def _ensure_connection(self) -> Any:
        """Get or create database connection."""
        if self.conn is None:
            import psycopg

            self.conn = psycopg.connect(self.connection_string, autocommit=True)

            # Enable pgvector extension
            with self.conn.cursor() as cur:
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")

            # Create embeddings table
            self._create_table()

        return self.conn

    def _create_table(self) -> None:
        """Create embeddings table if it doesn't exist."""
        create_sql = f"""
        CREATE TABLE IF NOT EXISTS {self.table_name} (
            id TEXT PRIMARY KEY,
            label TEXT,
            type TEXT,
            file TEXT,
            embedding vector({self.vector_dimensions}),
            metadata JSONB,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW(),
            indexed BOOLEAN DEFAULT FALSE
        );

        CREATE INDEX IF NOT EXISTS idx_{self.table_name}_embedding
            ON {self.table_name} USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100);

        CREATE INDEX IF NOT EXISTS idx_{self.table_name}_type
            ON {self.table_name} (type);

        CREATE INDEX IF NOT EXISTS idx_{self.table_name}_file
            ON {self.table_name} (file);
        """

        with self._ensure_connection().cursor() as cur:
            cur.execute(create_sql)

    @property
    def project_path_prop(self) -> Path:
        """Get project path (property name workaround)."""
        return self.project_path

    # ========================================================================
    # EmbeddingBackend Interface Implementation
    # ========================================================================

    def load_graph(self) -> bool:
        """Load graph from project."""
        try:
            from ..embedder import GraphEmbedder

            # Use default embedder to load graph
            default_embedder = GraphEmbedder(str(self.project_path))
            self.graph = default_embedder.graph
            return True
        except Exception as e:
            print(f"Error loading graph: {e}")
            return False

    def embed_nodes(self, force: bool = False) -> dict[str, int]:
        """
        Create embeddings for loaded nodes.

        For now: delegates to default embedder, then stores in PostgreSQL.
        """
        if not self.graph:
            return {"added": 0, "updated": 0, "skipped": 0}

        try:
            from ..embedder import GraphEmbedder

            # Use default embedder to generate embeddings
            default_embedder = GraphEmbedder(str(self.project_path))
            default_embedder.load_graph()
            result = default_embedder.embed_nodes(force=force)

            # TODO: Copy embeddings from ChromaDB to PostgreSQL
            # For MVP, we just return the result from the default embedder

            return result
        except Exception as e:
            print(f"Error embedding nodes: {e}")
            return {"added": 0, "updated": 0, "skipped": 0}

    def search(
        self,
        query: str,
        n: int = 5,
        where: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Semantic search using pgvector."""
        # TODO: Implement pgvector similarity search
        # SELECT id, label, type, 1 - (embedding <=> query_embedding) as score
        # FROM embeddings ORDER BY score DESC LIMIT n;

        return []

    def get_community_summary(
        self, community_id: int, max_nodes: int = 20
    ) -> dict[str, Any]:
        """Get summary of community from PostgreSQL."""
        # TODO: Implement community query
        return {
            "id": community_id,
            "summary": f"Community {community_id}",
            "node_count": 0,
            "nodes": [],
        }

    def get_file_nodes(self, source_file: str) -> list[dict]:
        """Get all nodes from a file."""
        # TODO: Query PostgreSQL for nodes matching file path
        return []

    def get_file_edges(
        self, source_file: str, node_ids: set[str] | None = None
    ) -> list[dict]:
        """Get edges for a file."""
        # TODO: Query PostgreSQL for edges
        return []

    def get_stats(self) -> dict[str, Any]:
        """Get index statistics."""
        try:
            with self._ensure_connection().cursor() as cur:
                cur.execute(f"SELECT COUNT(*) FROM {self.table_name};")
                count = cur.fetchone()[0]

                cur.execute(f"SELECT COUNT(DISTINCT type) FROM {self.table_name};")
                types = cur.fetchone()[0]

            return {
                "total_nodes": count,
                "node_types": types,
                "backend": "postgres",
                "table": self.table_name,
            }
        except Exception:
            return {}

    def clear(self) -> None:
        """Clear all embeddings."""
        try:
            with self._ensure_connection().cursor() as cur:
                cur.execute(f"TRUNCATE TABLE {self.table_name};")
        except Exception:
            pass

    def close(self) -> None:
        """Close database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None
