"""In-memory embedding backend for tests and offline backend switching."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .embedding_backend import EmbeddingBackend


class InMemoryEmbeddingBackend(EmbeddingBackend):
    """Simple in-memory backend with lexical scoring."""

    def __init__(self, project_path: str, db_path: str | None = None):
        self._project_path = Path(project_path)
        self.db_path = db_path or ":memory:"
        self.graph_path = self._project_path / "graphify-out" / "graph.json"
        self.graph: dict[str, Any] = {}
        self.nodes: list[dict[str, Any]] = []
        self.edges: list[dict[str, Any]] = []
        self._docs: dict[str, tuple[str, dict[str, Any]]] = {}

    @property
    def project_path(self) -> Path:
        return self._project_path

    def load_graph(self) -> bool:
        if not self.graph_path.exists():
            return False
        self.graph = json.loads(self.graph_path.read_text())
        self.nodes = self.graph.get("nodes", [])
        self.edges = self.graph.get("edges", self.graph.get("links", []))
        return True

    def _node_to_text(self, node: dict[str, Any]) -> str:
        return " ".join(
            str(v)
            for v in (
                node.get("label", node.get("id", "")),
                node.get("file_type", ""),
                node.get("source_file", ""),
                node.get("description", ""),
            )
            if v
        )

    def embed_nodes(self, force: bool = False) -> dict[str, int]:
        if not self.nodes and not self.load_graph():
            return {"added": 0, "updated": 0, "skipped": 0, "error": "No graph loaded"}

        stats = {"added": 0, "updated": 0, "skipped": 0}
        for node in self.nodes:
            node_id = str(node.get("id", node.get("label", "")))
            if not node_id:
                continue
            doc = self._node_to_text(node)
            metadata = {
                "label": str(node.get("label", node_id)),
                "file_type": str(node.get("file_type", "unknown")),
                "source_file": str(node.get("source_file", "")),
                "community": int(node.get("community", -1)),
                "node_id": node_id,
            }
            if node_id not in self._docs:
                stats["added"] += 1
                self._docs[node_id] = (doc, metadata)
            elif force:
                stats["updated"] += 1
                self._docs[node_id] = (doc, metadata)
            else:
                if self._docs[node_id][0] == doc:
                    stats["skipped"] += 1
                else:
                    stats["updated"] += 1
                    self._docs[node_id] = (doc, metadata)
        return stats

    def _tokens(self, text: str) -> set[str]:
        return set(re.findall(r"[a-zA-Z0-9_]+", text.lower()))

    def search(self, query: str, n: int = 5, where: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        if not self._docs:
            self.embed_nodes(force=False)
        q = self._tokens(query)
        results: list[dict[str, Any]] = []
        for node_id, (doc, meta) in self._docs.items():
            if where and any(meta.get(k) != v for k, v in where.items()):
                continue
            tokens = self._tokens(doc)
            overlap = len(q & tokens)
            if overlap == 0:
                continue
            score = overlap / max(len(q), 1)
            results.append(
                {
                    "id": node_id,
                    "document": doc,
                    "metadata": meta,
                    "distance": 1 - score,
                    "score": score,
                }
            )
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:n]

    def get_community_summary(self, community_id: int, max_nodes: int = 20) -> dict[str, Any]:
        nodes = [
            {
                "id": node_id,
                "label": meta.get("label", node_id),
                "file_type": meta.get("file_type", "unknown"),
                "source_file": meta.get("source_file", ""),
            }
            for node_id, (_, meta) in self._docs.items()
            if int(meta.get("community", -1)) == community_id
        ][:max_nodes]
        if not nodes:
            return {"community": community_id, "nodes": [], "summary": "Empty community"}
        counts: dict[str, int] = {}
        for node in nodes:
            file_type = str(node.get("file_type", "unknown"))
            counts[file_type] = counts.get(file_type, 0) + 1
        return {
            "community": community_id,
            "node_count": len(nodes),
            "type_summary": ", ".join(f"{v} {k}s" for k, v in counts.items()),
            "nodes": nodes,
        }

    def get_file_nodes(self, source_file: str) -> list[dict]:
        if not self.nodes and not self.load_graph():
            return []
        normalized = str(source_file).replace("\\", "/").lstrip("./")
        return [n for n in self.nodes if str(n.get("source_file", "")).replace("\\", "/") == normalized]

    def get_file_edges(self, source_file: str, node_ids: set[str] | None = None) -> list[dict]:
        if not self.edges and not self.load_graph():
            return []
        ids = node_ids or {str(n.get("id")) for n in self.get_file_nodes(source_file)}
        return [
            e
            for e in self.edges
            if (e.get("_src") in ids or e.get("_tgt") in ids or e.get("source") in ids or e.get("target") in ids)
        ]

    def get_stats(self) -> dict[str, Any]:
        communities = {int(meta.get("community", -1)) for _, meta in self._docs.values()}
        return {
            "total_nodes": len(self._docs),
            "communities": len([c for c in communities if c >= 0]),
            "community_distribution": {},
            "db_path": self.db_path,
        }

    def clear(self) -> None:
        self._docs.clear()

    def close(self) -> None:
        return
