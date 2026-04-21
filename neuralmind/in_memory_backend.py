"""In-memory EmbeddingBackend implementation for deterministic offline usage."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .embedding_backend import EmbeddingBackend


class InMemoryEmbeddingBackend(EmbeddingBackend):
    """A pure in-memory backend that supports backend switching and offline tests."""

    def __init__(self, project_path: str, db_path: str | None = None):
        self._project_path = Path(project_path).resolve()
        self.graph_path = self._project_path / "graphify-out" / "graph.json"
        self.db_path = db_path or ":memory:"
        self.graph: dict[str, Any] = {}
        self.nodes: list[dict[str, Any]] = []
        self.edges: list[dict[str, Any]] = []
        self._index: dict[str, dict[str, Any]] = {}

    @property
    def project_path(self) -> Path:
        return self._project_path

    def load_graph(self) -> bool:
        if not self.graph_path.exists():
            return False
        with self.graph_path.open(encoding="utf-8") as file:
            self.graph = json.load(file)
        self.nodes = self.graph.get("nodes", [])
        self.edges = self.graph.get("edges", self.graph.get("links", []))
        return True

    def _node_to_text(self, node: dict[str, Any]) -> str:
        parts = [
            str(node.get("label", node.get("id", "unknown"))),
            str(node.get("description", "")),
            str(node.get("file_type", node.get("type", "unknown"))),
            str(node.get("source_file", "")),
        ]
        return "\n".join(part for part in parts if part).strip()

    def _node_metadata(self, node: dict[str, Any]) -> dict[str, Any]:
        return {
            "label": str(node.get("label", node.get("id", "unknown"))),
            "file_type": str(node.get("file_type", node.get("type", "unknown"))),
            "source_file": str(node.get("source_file", "")),
            "community": int(node.get("community", -1)),
            "node_id": str(node.get("id", "")),
            "embedded_at": datetime.now().isoformat(),
        }

    def _content_hash(self, text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()[:16]

    def embed_nodes(self, force: bool = False) -> dict[str, int]:
        if not self.nodes and not self.load_graph():
            return {"added": 0, "updated": 0, "skipped": 0, "error": "No graph loaded"}

        stats = {"added": 0, "updated": 0, "skipped": 0}
        for node in self.nodes:
            node_id = str(node.get("id", node.get("label", "")))
            if not node_id:
                continue

            text = self._node_to_text(node)
            content_hash = self._content_hash(text)
            existing = self._index.get(node_id)

            if existing and not force and existing.get("content_hash") == content_hash:
                stats["skipped"] += 1
                continue

            if existing:
                stats["updated"] += 1
            else:
                stats["added"] += 1

            self._index[node_id] = {
                "id": node_id,
                "document": text,
                "metadata": self._node_metadata(node),
                "content_hash": content_hash,
            }
        return stats

    def search(
        self,
        query: str,
        n: int = 5,
        where: dict[str, Any] | None = None,
        file_type: str | None = None,
        community: int | None = None,
    ) -> list[dict[str, Any]]:
        if not self._index:
            self.embed_nodes(force=False)

        query_terms = {part for part in query.lower().split() if part}
        if not query_terms:
            return []

        def _score(doc: str) -> float:
            doc_terms = set(doc.lower().split())
            overlap = len(query_terms & doc_terms)
            return overlap / max(len(query_terms), 1)

        def _match_rule(metadata: dict[str, Any], rule: dict[str, Any]) -> bool:
            for key, value in rule.items():
                if metadata.get(key) != value:
                    return False
            return True

        combined_where = where.copy() if isinstance(where, dict) else {}
        if file_type is not None:
            combined_where["file_type"] = file_type
        if community is not None:
            combined_where["community"] = community

        def _match(metadata: dict[str, Any]) -> bool:
            if not combined_where:
                return True
            if "$and" in combined_where:
                return all(_match_rule(metadata, rule) for rule in combined_where["$and"])
            return _match_rule(metadata, combined_where)

        scored: list[dict[str, Any]] = []
        for entry in self._index.values():
            metadata = entry["metadata"]
            if not _match(metadata):
                continue
            score = _score(entry["document"])
            if score <= 0:
                continue
            scored.append(
                {
                    "id": entry["id"],
                    "document": entry["document"],
                    "metadata": metadata,
                    "distance": round(1 - score, 6),
                    "score": round(score, 6),
                }
            )

        scored.sort(key=lambda item: item["score"], reverse=True)
        return scored[:n]

    def get_community_summary(self, community_id: int, max_nodes: int = 20) -> dict[str, Any]:
        if not self.nodes and not self.load_graph():
            return {
                "community": community_id,
                "node_count": 0,
                "nodes": [],
                "summary": "Empty community",
            }
        nodes = [node for node in self.nodes if int(node.get("community", -1)) == community_id][
            :max_nodes
        ]
        file_types: dict[str, int] = {}
        formatted_nodes: list[dict[str, Any]] = []
        for node in nodes:
            file_type = str(node.get("file_type", node.get("type", "unknown")))
            file_types[file_type] = file_types.get(file_type, 0) + 1
            formatted_nodes.append(
                {
                    "id": str(node.get("id", "")),
                    "label": str(node.get("label", node.get("id", "unknown"))),
                    "file_type": file_type,
                    "source_file": str(node.get("source_file", "")),
                }
            )
        type_summary = (
            ", ".join(f"{count} {name}s" for name, count in file_types.items()) or "mixed"
        )
        return {
            "community": community_id,
            "node_count": len(formatted_nodes),
            "type_summary": type_summary,
            "nodes": formatted_nodes,
        }

    def get_file_nodes(self, source_file: str) -> list[dict]:
        if not self.nodes and not self.load_graph():
            return []
        normalized = str(source_file).replace("\\", "/").lstrip("./")
        candidates = {normalized, normalized.replace("/", "\\")}
        try:
            candidates.add(str(Path(source_file).resolve()))
            candidates.add(str((self.project_path / normalized).resolve()))
        except Exception:
            pass
        return [node for node in self.nodes if str(node.get("source_file", "")) in candidates]

    def get_file_edges(self, source_file: str, node_ids: set[str] | None = None) -> list[dict]:
        if not self.edges and not self.load_graph():
            return []
        ids = (
            node_ids
            if node_ids is not None
            else {n.get("id", "") for n in self.get_file_nodes(source_file)}
        )
        if not ids:
            return []
        return [
            edge
            for edge in self.edges
            if edge.get("_src") in ids
            or edge.get("_tgt") in ids
            or edge.get("source") in ids
            or edge.get("target") in ids
            or edge.get("from") in ids
            or edge.get("to") in ids
        ]

    def get_stats(self) -> dict[str, Any]:
        communities = {
            int(entry["metadata"].get("community", -1))
            for entry in self._index.values()
            if "metadata" in entry
        }
        return {
            "total_nodes": len(self._index),
            "communities": len([community for community in communities if community >= 0]),
            "community_distribution": {},
            "db_path": self.db_path,
        }

    def clear(self) -> None:
        self._index.clear()

    def close(self) -> None:
        self.clear()
