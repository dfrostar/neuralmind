"""
lancedb_backend.py — LanceDB Embedding Backend
==============================================

Lightweight, Rust-based vector database for embedded deployments.

Benefits:
- No server required (embedded in Python)
- Blazing fast Rust implementation
- Great for offline/air-gapped environments
- Tiny footprint (ideal for edge/mobile)
- ACID compliance via DuckDB
- Apache 2.0 licensed (no vendor lock-in)

Configuration:
  [backends.lancedb]
  db_path = ".neuralmind/embeddings.lance"

Requirements:
  pip install lancedb
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..embedding_backend import EmbeddingBackend


class LanceDBBackend(EmbeddingBackend):
    """LanceDB embedding backend (lightweight, Rust-based)."""

    def __init__(
        self,
        project_path: str | Path,
        db_path: str | Path | None = None,
        **kwargs: Any,
    ):
        """
        Initialize LanceDB backend.

        Args:
            project_path: Project root
            db_path: Path to LanceDB database file
                Default: .neuralmind/embeddings.lance
        """
        self.project_path = Path(project_path)

        if db_path is None:
            db_path = self.project_path / ".neuralmind" / "embeddings.lance"

        self.db_path = Path(db_path)
        self.graph = None
        self.db = None

        self._init_db()

    def _init_db(self) -> None:
        """Initialize LanceDB connection."""
        try:
            import lancedb

            self.lancedb = lancedb
            # Lazy initialization on first use
        except ImportError:
            raise ImportError(
                "LanceDB backend requires lancedb. "
                "Install with: pip install lancedb"
            )

    def _ensure_db(self) -> Any:
        """Get or create database connection."""
        if self.db is None:
            self.db = self.lancedb.connect(str(self.db_path))
        return self.db

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

        For now: delegates to default embedder, then stores in LanceDB.
        """
        if not self.graph:
            return {"added": 0, "updated": 0, "skipped": 0}

        try:
            from ..embedder import GraphEmbedder

            # Use default embedder to generate embeddings
            default_embedder = GraphEmbedder(str(self.project_path))
            default_embedder.load_graph()
            result = default_embedder.embed_nodes(force=force)

            # TODO: Copy embeddings from ChromaDB to LanceDB
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
        """Semantic search using LanceDB."""
        # TODO: Implement LanceDB similarity search
        # table = db.open_table("embeddings")
        # results = table.search(query_embedding).limit(n).to_list()

        return []

    def get_community_summary(
        self, community_id: int, max_nodes: int = 20
    ) -> dict[str, Any]:
        """Get summary of community from LanceDB."""
        # TODO: Implement community query using LanceDB
        return {
            "id": community_id,
            "summary": f"Community {community_id}",
            "node_count": 0,
            "nodes": [],
        }

    def get_file_nodes(self, source_file: str) -> list[dict]:
        """Get all nodes from a file."""
        # TODO: Query LanceDB for nodes matching file path
        return []

    def get_file_edges(
        self, source_file: str, node_ids: set[str] | None = None
    ) -> list[dict]:
        """Get edges for a file."""
        # TODO: Query LanceDB for edges
        return []

    def get_stats(self) -> dict[str, Any]:
        """Get index statistics."""
        try:
            db = self._ensure_db()
            table_names = db.table_names()

            total_rows = 0
            for table_name in table_names:
                table = db.open_table(table_name)
                total_rows += len(table.to_arrow())

            return {
                "total_nodes": total_rows,
                "tables": len(table_names),
                "backend": "lancedb",
                "db_path": str(self.db_path),
            }
        except Exception:
            return {}

    def clear(self) -> None:
        """Clear all embeddings."""
        try:
            db = self._ensure_db()
            for table_name in db.table_names():
                db.drop_table(table_name)
        except Exception:
            pass

    def close(self) -> None:
        """Close database connection."""
        if self.db is not None:
            self.db = None
