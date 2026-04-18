"""
embedder.py — Knowledge Base Search System
==========================================

Provides an interface to search the ChromaDB created by the `mempalace` tool.
"""

from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings

class KnowledgeSearcher:
    """
    Provides a search interface to the ChromaDB created by `mempalace`.

    Usage:
        searcher = KnowledgeSearcher("/path/to/project")
        results = searcher.search("authentication logic", n=5)
    """

    COLLECTION_NAME = "neuralmind_nodes"

    def __init__(self, project_path: str, db_path: str = None):
        """
        Initialize the searcher for a project.

        Args:
            project_path: Path to project root
            db_path: Optional custom path for ChromaDB storage
        """
        self.project_path = Path(project_path)

        # Default DB path in project's graphify-out
        if db_path is None:
            db_path = str(Path.home() / ".mempalace" / "palace")

        self.db_path = db_path

        # Initialize ChromaDB
        self.client = chromadb.PersistentClient(
            path=self.db_path, settings=Settings(anonymized_telemetry=False)
        )

        self._collection = None

    @property
    def collection(self):
        """Get or create the embeddings collection."""
        if self._collection is None:
            self._collection = self.client.get_or_create_collection(
                name=self.COLLECTION_NAME, metadata={"hnsw:space": "cosine"}
            )
        return self._collection

    def search(self, query: str, n: int = 10, **filters) -> list[dict]:
        """
        Perform semantic search on the knowledge base.

        Args:
            query: Search query
            n: Number of results
            **filters: Optional metadata filters (e.g., source_file)

        Returns:
            List of matching documents with scores
        """
        results = self.collection.query(
            query_texts=[query],
            n_results=n,
            where=filters if filters else None,
            include=["metadatas", "documents", "distances"],
        )
        # Format results to be more user-friendly
        formatted_results = []
        ids = results.get("ids", [[]])[0]
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        for i in range(len(ids)):
            formatted_results.append({
                "id": ids[i],
                "document": documents[i],
                "metadata": metadatas[i],
                "distance": distances[i],
            })
        return formatted_results

    def get_stats(self) -> dict:
        """
        Get statistics about the knowledge base collection.
        """
        try:
            count = self.collection.count()
            return {
                "db_path": self.db_path,
                "total_drawers": count,
            }
        except Exception as e:
            return {
                "db_path": self.db_path,
                "total_drawers": 0,
                "error": str(e),
            }
