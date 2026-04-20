"""
embedder.py — Graph Node Embedding System
==========================================

Converts graphify graph.json nodes into vector embeddings for semantic search.
Uses ChromaDB's native embedding functions (no external dependencies required).

Key Features:
- Embeds code entities (functions, classes, files, models)
- Preserves graph structure (community, relationships)
- Supports incremental updates (only re-embed changed nodes)
- Stores metadata for filtering (file_type, community, source_file)
"""

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings

from .embedding_backend import EmbeddingBackend


class GraphEmbedder(EmbeddingBackend):
    """
    Embeds graphify graph.json nodes into ChromaDB for semantic search.

    Usage:
        embedder = GraphEmbedder("/path/to/project")
        embedder.load_graph()
        embedder.embed_nodes()
        results = embedder.search("authentication logic", n=5)
    """

    COLLECTION_NAME = "neuralmind_nodes"

    def __init__(self, project_path: str, db_path: str = None):
        """
        Initialize the embedder for a project.

        Args:
            project_path: Path to project root (where graphify-out/ lives)
            db_path: Optional custom path for ChromaDB storage
        """
        self._project_path = Path(project_path)
        self.graph_path = self._project_path / "graphify-out" / "graph.json"

        # Default DB path in project's graphify-out
        if db_path is None:
            db_path = str(self._project_path / "graphify-out" / "neuralmind_db")

        self.db_path = db_path
        self.graph: dict = {}
        self.nodes: list[dict] = []
        self.edges: list[dict] = []

        # Initialize ChromaDB
        self.client = chromadb.PersistentClient(
            path=self.db_path, settings=Settings(anonymized_telemetry=False)
        )

        self._collection = None

    @property
    def project_path(self) -> Path:
        """Get the project path."""
        return self._project_path
    """
    Embeds graphify graph.json nodes into ChromaDB for semantic search.

    Usage:
        embedder = GraphEmbedder("/path/to/project")
        embedder.load_graph()
        embedder.embed_nodes()
        results = embedder.search("authentication logic", n=5)
    """

    COLLECTION_NAME = "neuralmind_nodes"

    def __init__(self, project_path: str, db_path: str = None):
        """
        Initialize the embedder for a project.

        Args:
            project_path: Path to project root (where graphify-out/ lives)
            db_path: Optional custom path for ChromaDB storage
        """
        self.project_path = Path(project_path)
        self.graph_path = self.project_path / "graphify-out" / "graph.json"

        # Default DB path in project's graphify-out
        if db_path is None:
            db_path = str(self.project_path / "graphify-out" / "neuralmind_db")

        self.db_path = db_path
        self.graph: dict = {}
        self.nodes: list[dict] = []
        self.edges: list[dict] = []

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

    def load_graph(self) -> bool:
        """
        Load graph.json from graphify output.

        Returns:
            True if loaded successfully, False otherwise
        """
        if not self.graph_path.exists():
            print(f"Graph not found: {self.graph_path}")
            return False

        with open(self.graph_path) as f:
            self.graph = json.load(f)

        self.nodes = self.graph.get("nodes", [])
        self.edges = self.graph.get("edges", self.graph.get("links", []))

        print(f"Loaded graph: {len(self.nodes)} nodes, {len(self.edges)} edges")
        return True

    def _node_to_text(self, node: dict) -> str:
        """
        Convert a node to searchable text representation.

        Combines label, file_type, source_file, and community info
        into a rich text description for embedding.
        """
        parts = []

        # Primary identifier
        label = node.get("label", node.get("id", "unknown"))
        parts.append(f"Entity: {label}")

        # Type information
        file_type = node.get("file_type", "unknown")
        parts.append(f"Type: {file_type}")

        # Source location
        source_file = node.get("source_file", "")
        if source_file:
            parts.append(f"File: {source_file}")

        source_loc = node.get("source_location", "")
        if source_loc:
            parts.append(f"Location: {source_loc}")

        # Community/cluster info
        community = node.get("community", -1)
        if community >= 0:
            parts.append(f"Community: {community}")

        # Normalized label (often more descriptive)
        norm_label = node.get("norm_label", "")
        if norm_label and norm_label != label:
            parts.append(f"Normalized: {norm_label}")

        return "\n".join(parts)

    def _node_metadata(self, node: dict) -> dict[str, Any]:
        """
        Extract metadata from node for filtering.
        """
        return {
            "label": str(node.get("label", node.get("id", "unknown"))),
            "file_type": str(node.get("file_type", "unknown")),
            "source_file": str(node.get("source_file", "")),
            "community": int(node.get("community", -1)),
            "node_id": str(node.get("id", "")),
        }

    def _content_hash(self, text: str) -> str:
        """Generate hash of content for change detection."""
        return hashlib.sha256(text.encode()).hexdigest()[:16]

    def embed_nodes(self, force: bool = False) -> dict[str, int]:
        """
        Embed all nodes into ChromaDB.

        Args:
            force: If True, re-embed all nodes. Otherwise, skip unchanged.

        Returns:
            Dict with counts: {"added": N, "updated": N, "skipped": N}
        """
        if not self.nodes:
            if not self.load_graph():
                return {
                    "added": 0,
                    "updated": 0,
                    "skipped": 0,
                    "error": "No graph loaded",
                }

        stats = {"added": 0, "updated": 0, "skipped": 0}

        # Batch process for efficiency
        batch_ids = []
        batch_docs = []
        batch_metas = []

        for node in self.nodes:
            node_id = str(node.get("id", node.get("label", "")))
            if not node_id:
                continue

            text = self._node_to_text(node)
            meta = self._node_metadata(node)
            meta["content_hash"] = self._content_hash(text)
            meta["embedded_at"] = datetime.now().isoformat()

            # Check if we need to update
            if not force:
                try:
                    existing = self.collection.get(ids=[node_id], include=["metadatas"])
                    if existing["ids"] and existing["metadatas"]:
                        old_hash = existing["metadatas"][0].get("content_hash", "")
                        if old_hash == meta["content_hash"]:
                            stats["skipped"] += 1
                            continue
                        stats["updated"] += 1
                    else:
                        stats["added"] += 1
                except Exception:
                    stats["added"] += 1
            else:
                stats["added"] += 1

            batch_ids.append(node_id)
            batch_docs.append(text)
            batch_metas.append(meta)

            # Process in batches of 100
            if len(batch_ids) >= 100:
                self.collection.upsert(ids=batch_ids, documents=batch_docs, metadatas=batch_metas)
                batch_ids, batch_docs, batch_metas = [], [], []

        # Final batch
        if batch_ids:
            self.collection.upsert(ids=batch_ids, documents=batch_docs, metadatas=batch_metas)

        print(f"Embedding complete: {stats}")
        return stats

    def search(
        self, query: str, n: int = 10, file_type: str = None, community: int = None
    ) -> list[dict]:
        """
        Semantic search for relevant nodes.

        Args:
            query: Natural language query
            n: Number of results to return
            file_type: Optional filter by file type
            community: Optional filter by community ID

        Returns:
            List of matching nodes with scores
        """
        where_filter = None
        conditions = []

        if file_type:
            conditions.append({"file_type": file_type})
        if community is not None:
            conditions.append({"community": community})

        if len(conditions) == 1:
            where_filter = conditions[0]
        elif len(conditions) > 1:
            where_filter = {"$and": conditions}

        results = self.collection.query(
            query_texts=[query],
            n_results=n,
            where=where_filter,
            include=["documents", "metadatas", "distances"],
        )

        # Format results
        formatted = []
        if results["ids"] and results["ids"][0]:
            for i, node_id in enumerate(results["ids"][0]):
                formatted.append(
                    {
                        "id": node_id,
                        "document": (results["documents"][0][i] if results["documents"] else ""),
                        "metadata": (results["metadatas"][0][i] if results["metadatas"] else {}),
                        "distance": (results["distances"][0][i] if results["distances"] else 0),
                        "score": 1
                        - (
                            results["distances"][0][i] if results["distances"] else 0
                        ),  # Convert distance to similarity
                    }
                )

        return formatted

    def get_file_nodes(self, source_file: str) -> list[dict]:
        """Return all graph nodes whose source_file matches the given path.

        Path matching is flexible: we try exact match, then a normalized
        match that handles windows/posix slashes and the repo-relative
        vs absolute variance that ships across graph builders.

        Args:
            source_file: File path (absolute or relative to project root)

        Returns:
            List of node dicts (empty if graph not loaded or no matches)
        """
        if not self.nodes:
            if not self.load_graph():
                return []

        # Build multiple candidate keys to match against node.source_file
        p = str(source_file).replace("\\", "/").lstrip("./")
        candidates = {p, p.replace("/", "\\")}
        # If it's under project_path, also try the relative form
        try:
            rel = str(Path(source_file).resolve().relative_to(self.project_path.resolve()))
            candidates.add(rel)
            candidates.add(rel.replace("\\", "/"))
            candidates.add(rel.replace("/", "\\"))
        except Exception:
            pass

        # Also try absolute forms — graphify stores absolute paths in
        # source_file, so relative inputs never match without these.
        try:
            candidates.add(str(Path(source_file).resolve()))
            candidates.add(str((self.project_path / p).resolve()))
        except Exception:
            pass

        matched = [
            n for n in self.nodes
            if any(c == n.get("source_file", "") for c in candidates)
        ]
        return matched

    def get_file_edges(self, source_file: str, node_ids: set[str] | None = None) -> list[dict]:
        """Return edges where either endpoint belongs to the given file.

        Args:
            source_file: File path to filter by
            node_ids: Optional pre-computed set of node ids for this file
                      (pass in from get_file_nodes to avoid recomputation)

        Returns:
            List of edge dicts
        """
        if not self.edges:
            if not self.load_graph():
                return []

        if node_ids is None:
            node_ids = {n["id"] for n in self.get_file_nodes(source_file)}

        if not node_ids:
            return []

        return [
            e for e in self.edges
            if (e.get("_src") in node_ids or e.get("_tgt") in node_ids
                or e.get("source") in node_ids or e.get("target") in node_ids)
        ]

    def get_community_summary(self, community_id: int, max_nodes: int = 20) -> dict:
        """
        Get a summary of nodes in a community for context injection.

        Args:
            community_id: The community/cluster ID
            max_nodes: Maximum nodes to include

        Returns:
            Dict with community summary and key nodes
        """
        results = self.collection.get(
            where={"community": community_id},
            include=["documents", "metadatas"],
            limit=max_nodes,
        )

        if not results["ids"]:
            return {
                "community": community_id,
                "nodes": [],
                "summary": "Empty community",
            }

        nodes = []
        for i, node_id in enumerate(results["ids"]):
            nodes.append(
                {
                    "id": node_id,
                    "label": results["metadatas"][i].get("label", node_id),
                    "file_type": results["metadatas"][i].get("file_type", "unknown"),
                    "source_file": results["metadatas"][i].get("source_file", ""),
                }
            )

        # Generate compact summary
        file_types = {}
        for n in nodes:
            ft = n["file_type"]
            file_types[ft] = file_types.get(ft, 0) + 1

        type_summary = ", ".join(f"{v} {k}s" for k, v in file_types.items())

        return {
            "community": community_id,
            "node_count": len(nodes),
            "type_summary": type_summary,
            "nodes": nodes,
        }

    def get_stats(self) -> dict:
        """
        Get embedding statistics.
        """
        count = self.collection.count()

        # Get community distribution
        communities = {}
        if count > 0:
            # Sample to get community distribution
            sample = self.collection.get(include=["metadatas"], limit=min(count, 1000))
            for meta in sample["metadatas"]:
                c = meta.get("community", -1)
                communities[c] = communities.get(c, 0) + 1

        return {
            "total_nodes": count,
            "communities": len(communities),
            "community_distribution": communities,
            "db_path": self.db_path,
        }

    def clear(self) -> None:
        """Clear all embeddings from the collection."""
        try:
            self.client.delete_collection(name=self.COLLECTION_NAME)
            self._collection = None
        except Exception:
            pass

    def close(self) -> None:
        """Close ChromaDB client and cleanup."""
        if hasattr(self, "client"):
            try:
                self.client.delete_collection(name=self.COLLECTION_NAME)
            except Exception:
                pass
