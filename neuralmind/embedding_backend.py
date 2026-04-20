"""
embedding_backend.py — Abstract Embedding Backend Interface
===========================================================

Defines the contract for embedding backends (ChromaDB, Pinecone, Weaviate, mocks).
Enables testing without ChromaDB overhead and future backend swaps.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class EmbeddingBackend(ABC):
    """
    Abstract base class for embedding backends.

    Implementations must support:
    - Loading graph structures
    - Creating vector embeddings
    - Semantic search with metadata filtering
    - Community summary generation
    - Statistics tracking
    """

    @property
    @abstractmethod
    def project_path(self) -> Path:
        """Get the project path."""

    @abstractmethod
    def load_graph(self) -> bool:
        """
        Load graph from default location.

        Returns:
            True if loaded successfully, False otherwise
        """

    @abstractmethod
    def embed_nodes(self, force: bool = False) -> dict[str, int]:
        """
        Create embeddings for loaded nodes.

        Args:
            force: If True, re-embed even if already embedded

        Returns:
            Dictionary with counts: {'added': int, 'updated': int, 'skipped': int}
        """

    @abstractmethod
    def search(
        self,
        query: str,
        n: int = 5,
        where: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Semantic search for nodes.

        Args:
            query: Natural language query
            n: Number of results
            where: Optional metadata filter (backend-specific)

        Returns:
            List of results with 'id', 'text', 'metadata', 'distance'/'score'
        """

    @abstractmethod
    def get_community_summary(self, community_id: int, max_nodes: int = 20) -> dict[str, Any]:
        """
        Get summary of nodes in a community.

        Args:
            community_id: Community identifier
            max_nodes: Maximum nodes to return

        Returns:
            Dictionary with 'id', 'summary', 'node_count', 'nodes'
        """

    @abstractmethod
    def get_file_nodes(self, source_file: str) -> list[dict]:
        """Get all nodes from a source file."""

    @abstractmethod
    def get_file_edges(self, source_file: str, node_ids: set[str] | None = None) -> list[dict]:
        """Get edges (dependencies) for a source file."""

    @abstractmethod
    def get_stats(self) -> dict[str, Any]:
        """Get index statistics (total nodes, communities, etc.)."""

    @abstractmethod
    def clear(self) -> None:
        """Clear all embeddings."""

    @abstractmethod
    def close(self) -> None:
        """Close connections and cleanup."""
