"""turbovec_backend.py — EmbeddingBackend on Google TurboQuant (POC / spike)
============================================================================

Experimental vector backend that replaces the *index/search* half of
``GraphEmbedder`` with `TurboVec <https://github.com/RyanCodrai/turbovec>`_ — a
compressed approximate-nearest-neighbour index built on Google Research's
**TurboQuant** quantizer (data-oblivious: no training, no codebook). Tracks the
spike in issue #204.

Why this exists
---------------
``GraphEmbedder`` leans on ChromaDB for *both* embedding storage and ANN search
(and drags in onnxruntime + the CVE-2026-45829 advisory surface). TurboVec only
does the ANN half, so this backend splits responsibilities:

* **vectors** → a TurboVec ``IdMapIndex`` (≈8–16× smaller than float32),
  persisted to ``<db>/index.tvim``;
* **text + metadata + the node-id↔uint64 map** → a local SQLite file
  ``<db>/store.sqlite`` (SQLite is already a NeuralMind dependency for synapses);
* **embeddings** → owned here. For an apples-to-apples recall comparison this
  POC reuses ChromaDB's ``DefaultEmbeddingFunction`` (the same MiniLM ONNX model
  the shipping backend uses) via a lazy import, injectable through ``embed_fn``
  for tests. Production would vendor the ONNX model directly so ChromaDB can be
  dropped entirely.

Scope: this is opt-in (``backend: turbovec`` / ``create_backend("turbovec", …)``)
and never the default. It implements the full ``EmbeddingBackend`` contract plus
``get_nodes_by_ids``/``delete_nodes`` so the synapse boost and incremental
reindex paths work unchanged.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

from .embedding_backend import EmbeddingBackend

# Inner-product metric → cosine on unit-normalised vectors (ChromaDB uses cosine).
_DEFAULT_BIT_WIDTH = 4  # 4-bit keeps recall close to float32; 2-bit ~2x smaller.
_EPS = 1e-12


def _l2_normalize(matrix: np.ndarray) -> np.ndarray:
    matrix = np.asarray(matrix, dtype=np.float32)
    if matrix.ndim == 1:
        matrix = matrix.reshape(1, -1)
    norms = np.linalg.norm(matrix, axis=1, keepdims=True)
    return matrix / (norms + _EPS)


def _default_embed_fn() -> Callable[[list[str]], list[list[float]]]:
    """Lazily build ChromaDB's default MiniLM embedding function.

    Imported lazily so merely importing this module (e.g. for type checks) does
    not require chromadb; only constructing the real backend does.
    """
    from chromadb.utils import embedding_functions

    ef = embedding_functions.DefaultEmbeddingFunction()

    def embed(texts: list[str]) -> list[list[float]]:
        return ef(texts)

    return embed


class TurboVecEmbedder(EmbeddingBackend):
    """EmbeddingBackend backed by a TurboVec index + a SQLite metadata store."""

    def __init__(
        self,
        project_path: str,
        db_path: str | None = None,
        *,
        bit_width: int = _DEFAULT_BIT_WIDTH,
        embed_fn: Callable[[list[str]], list[list[float]]] | None = None,
    ):
        self._project_path = Path(project_path).resolve()
        self.graph_path = self._project_path / "graphify-out" / "graph.json"

        if db_path is None:
            db_path = str(self._project_path / "graphify-out" / "neuralmind_turbovec")
        self.db_path = db_path
        self._dir = Path(db_path)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._index_path = self._dir / "index.tvim"
        self._store_path = self._dir / "store.sqlite"

        self.bit_width = int(bit_width)
        self._embed_fn = embed_fn  # resolved lazily so tests can inject a fake
        self.graph: dict = {}
        self.nodes: list[dict] = []
        self.edges: list[dict] = []

        self._index = None  # turbovec IdMapIndex, lazily created/loaded
        self._dirty = False  # mutated since last prepare()
        self._conn = sqlite3.connect(str(self._store_path))
        self._conn.row_factory = sqlite3.Row
        self._init_store()

    # ------------------------------------------------------------------ store
    def _init_store(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS nodes (
                uid          INTEGER PRIMARY KEY,
                node_id      TEXT UNIQUE NOT NULL,
                document     TEXT,
                label        TEXT,
                file_type    TEXT,
                source_file  TEXT,
                community    INTEGER,
                content_hash TEXT,
                embedded_at  TEXT
            );
            CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
            """)
        self._conn.commit()

    def _meta_get(self, key: str) -> str | None:
        row = self._conn.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else None

    def _meta_set(self, key: str, value: str) -> None:
        self._conn.execute(
            "INSERT INTO meta(key, value) VALUES(?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, str(value)),
        )

    @property
    def embed_fn(self) -> Callable[[list[str]], list[list[float]]]:
        if self._embed_fn is None:
            self._embed_fn = _default_embed_fn()
        return self._embed_fn

    @property
    def project_path(self) -> Path:
        return self._project_path

    # ------------------------------------------------------------------ index
    def _dim(self) -> int | None:
        stored = self._meta_get("dim")
        return int(stored) if stored else None

    def _load_index(self):
        """Return the TurboVec index, loading from disk or returning None."""
        if self._index is not None:
            return self._index
        if self._index_path.exists():
            import turbovec

            self._index = turbovec.IdMapIndex.load(str(self._index_path))
            self._dirty = False
        return self._index

    def _ensure_index(self, dim: int):
        idx = self._load_index()
        if idx is None:
            import turbovec

            idx = turbovec.IdMapIndex(dim=dim, bit_width=self.bit_width)
            self._index = idx
            self._meta_set("dim", str(dim))
            self._meta_set("bit_width", str(self.bit_width))
            self._conn.commit()
        return idx

    def _persist_index(self) -> None:
        if self._index is None:
            return
        if self._dirty:
            self._index.prepare()
            self._dirty = False
        self._index.write(str(self._index_path))

    def _next_uid(self) -> int:
        row = self._conn.execute("SELECT COALESCE(MAX(uid), 0) AS m FROM nodes").fetchone()
        return int(row["m"]) + 1

    # ------------------------------------------------------------- graph load
    def load_graph(self) -> bool:
        if not self.graph_path.exists():
            return False
        with self.graph_path.open(encoding="utf-8") as f:
            self.graph = json.load(f)
        self.nodes = self.graph.get("nodes", [])
        self.edges = self.graph.get("edges", self.graph.get("links", []))
        return True

    # Pure node→text/metadata helpers — kept byte-identical to GraphEmbedder so
    # embeddings (and therefore the recall comparison) are apples-to-apples.
    # TODO(#204): if this backend graduates, lift these into a shared mixin
    # rather than duplicating them across backends.
    def _node_to_text(self, node: dict) -> str:
        parts = []
        label = node.get("label", node.get("id", "unknown"))
        parts.append(f"Entity: {label}")
        parts.append(f"Type: {node.get('file_type', 'unknown')}")
        source_file = node.get("source_file", "")
        if source_file:
            parts.append(f"File: {source_file}")
        source_loc = node.get("source_location", "")
        if source_loc:
            parts.append(f"Location: {source_loc}")
        community = node.get("community", -1)
        if community >= 0:
            parts.append(f"Community: {community}")
        norm_label = node.get("norm_label", "")
        if norm_label and norm_label != label:
            parts.append(f"Normalized: {norm_label}")
        return "\n".join(parts)

    def _node_metadata(self, node: dict) -> dict[str, Any]:
        return {
            "label": str(node.get("label", node.get("id", "unknown"))),
            "file_type": str(node.get("file_type", "unknown")),
            "source_file": str(node.get("source_file", "")),
            "community": int(node.get("community", -1)),
            "node_id": str(node.get("id", "")),
        }

    @staticmethod
    def _content_hash(text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()[:16]

    # ----------------------------------------------------------------- embed
    def embed_nodes(self, force: bool = False) -> dict[str, int]:
        if not self.nodes and not self.load_graph():
            return {"added": 0, "updated": 0, "skipped": 0, "error": "No graph loaded"}

        stats = {"added": 0, "updated": 0, "skipped": 0}
        pending: list[tuple[str, int, str, dict, str, bool]] = (
            []
        )  # (node_id, uid, text, meta, hash, is_update)
        next_uid = self._next_uid()

        for node in self.nodes:
            node_id = str(node.get("id", node.get("label", "")))
            if not node_id:
                continue
            text = self._node_to_text(node)
            content_hash = self._content_hash(text)
            row = self._conn.execute(
                "SELECT uid, content_hash FROM nodes WHERE node_id = ?", (node_id,)
            ).fetchone()

            if row is not None:
                if not force and row["content_hash"] == content_hash:
                    stats["skipped"] += 1
                    continue
                uid = int(row["uid"])
                is_update = True
                stats["updated"] += 1
            else:
                uid = next_uid
                next_uid += 1
                is_update = False
                stats["added"] += 1

            pending.append((node_id, uid, text, self._node_metadata(node), content_hash, is_update))

        if not pending:
            self._persist_index()
            self._conn.commit()
            return stats

        vectors = _l2_normalize(self.embed_fn([p[2] for p in pending]))
        dim = vectors.shape[1]
        idx = self._ensure_index(dim)

        now = datetime.now().isoformat()
        new_vecs: list[np.ndarray] = []
        new_ids: list[int] = []
        for (node_id, uid, text, meta, content_hash, is_update), vec in zip(
            pending, vectors, strict=True
        ):
            if is_update:
                # Reuse the stable uid: drop the stale vector, then re-add.
                try:
                    idx.remove(uid)
                except Exception:
                    pass
                idx.add_with_ids(vec.reshape(1, -1), np.array([uid], dtype=np.uint64))
            else:
                new_vecs.append(vec)
                new_ids.append(uid)
            self._conn.execute(
                """
                INSERT INTO nodes(uid, node_id, document, label, file_type,
                                  source_file, community, content_hash, embedded_at)
                VALUES(?,?,?,?,?,?,?,?,?)
                ON CONFLICT(node_id) DO UPDATE SET
                    document=excluded.document, label=excluded.label,
                    file_type=excluded.file_type, source_file=excluded.source_file,
                    community=excluded.community, content_hash=excluded.content_hash,
                    embedded_at=excluded.embedded_at
                """,
                (
                    uid,
                    node_id,
                    text,
                    meta["label"],
                    meta["file_type"],
                    meta["source_file"],
                    meta["community"],
                    content_hash,
                    now,
                ),
            )

        if new_ids:
            idx.add_with_ids(np.vstack(new_vecs), np.array(new_ids, dtype=np.uint64))

        self._dirty = True
        self._persist_index()
        self._conn.commit()
        return stats

    # ---------------------------------------------------------------- search
    def _allowlist_uids(self, where: dict[str, Any] | None) -> np.ndarray | None:
        """Translate a metadata filter into an allowlist of uint64 uids."""
        if not where:
            return None
        clauses: list[dict[str, Any]] = where["$and"] if "$and" in where else [where]
        sql = "SELECT uid FROM nodes"
        conds, params = [], []
        for clause in clauses:
            for key, value in clause.items():
                if key in {"file_type", "community", "source_file", "label", "node_id"}:
                    conds.append(f"{key} = ?")
                    params.append(value)
        if conds:
            sql += " WHERE " + " AND ".join(conds)
        rows = self._conn.execute(sql, params).fetchall()
        return np.array([int(r["uid"]) for r in rows], dtype=np.uint64)

    def search(
        self,
        query: str,
        n: int = 5,
        where: dict[str, Any] | None = None,
        file_type: str | None = None,
        community: int | None = None,
    ) -> list[dict[str, Any]]:
        idx = self._load_index()
        if idx is None:
            return []

        combined: dict[str, Any] = dict(where) if isinstance(where, dict) else {}
        if file_type is not None:
            combined["file_type"] = file_type
        if community is not None:
            combined["community"] = community
        allowlist = self._allowlist_uids(combined or None)
        if allowlist is not None and allowlist.size == 0:
            return []

        total = self._conn.execute("SELECT COUNT(*) AS c FROM nodes").fetchone()["c"]
        k = max(1, min(n, allowlist.size if allowlist is not None else total))
        q = _l2_normalize(self.embed_fn([query]))

        try:
            scores, ids = idx.search(q, k, allowlist=allowlist)
        except Exception:
            # A freshly mutated index may need (re)preparing before search.
            idx.prepare()
            scores, ids = idx.search(q, k, allowlist=allowlist)

        out: list[dict[str, Any]] = []
        for score, uid in zip(scores[0], ids[0], strict=True):
            row = self._conn.execute("SELECT * FROM nodes WHERE uid = ?", (int(uid),)).fetchone()
            if row is None:  # padding / removed id
                continue
            sim = float(score)
            out.append(
                {
                    "id": row["node_id"],
                    "document": row["document"] or "",
                    "metadata": self._row_metadata(row),
                    "distance": round(1.0 - sim, 6),
                    "score": round(sim, 6),
                }
            )
        return out

    @staticmethod
    def _row_metadata(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "label": row["label"],
            "file_type": row["file_type"],
            "source_file": row["source_file"],
            "community": row["community"],
            "node_id": row["node_id"],
        }

    def get_nodes_by_ids(self, node_ids: list[str]) -> list[dict]:
        """Fetch indexed nodes by id (synapse-recall pull-in). Missing ids skipped."""
        if not node_ids:
            return []
        out = []
        for node_id in node_ids:
            row = self._conn.execute(
                "SELECT * FROM nodes WHERE node_id = ?", (str(node_id),)
            ).fetchone()
            if row is None:
                continue
            out.append(
                {
                    "id": row["node_id"],
                    "document": row["document"] or "",
                    "metadata": self._row_metadata(row),
                }
            )
        return out

    # ----------------------------------------------------- graph-derived reads
    def get_community_summary(self, community_id: int, max_nodes: int = 20) -> dict[str, Any]:
        if not self.nodes and not self.load_graph():
            return {
                "community": community_id,
                "node_count": 0,
                "nodes": [],
                "summary": "Empty community",
            }
        nodes = [n for n in self.nodes if int(n.get("community", -1)) == community_id][:max_nodes]
        file_types: dict[str, int] = {}
        formatted = []
        for n in nodes:
            ft = str(n.get("file_type", "unknown"))
            file_types[ft] = file_types.get(ft, 0) + 1
            formatted.append(
                {
                    "id": str(n.get("id", "")),
                    "label": str(n.get("label", n.get("id", "unknown"))),
                    "file_type": ft,
                    "source_file": str(n.get("source_file", "")),
                }
            )
        type_summary = ", ".join(f"{v} {k}s" for k, v in file_types.items()) or "mixed"
        return {
            "community": community_id,
            "node_count": len(formatted),
            "type_summary": type_summary,
            "nodes": formatted,
        }

    def get_file_nodes(self, source_file: str) -> list[dict]:
        if not self.nodes and not self.load_graph():
            return []
        p = str(source_file).replace("\\", "/").lstrip("./")
        candidates = {p, p.replace("/", "\\")}
        try:
            rel = str(Path(source_file).resolve().relative_to(self.project_path.resolve()))
            candidates.update({rel, rel.replace("\\", "/"), rel.replace("/", "\\")})
        except Exception:
            pass
        try:
            candidates.add(str(Path(source_file).resolve()))
            candidates.add(str((self.project_path / p).resolve()))
        except Exception:
            pass
        return [n for n in self.nodes if n.get("source_file", "") in candidates]

    def get_file_edges(self, source_file: str, node_ids: set[str] | None = None) -> list[dict]:
        if not self.edges and not self.load_graph():
            return []
        if node_ids is None:
            node_ids = {n["id"] for n in self.get_file_nodes(source_file)}
        if not node_ids:
            return []
        return [
            e
            for e in self.edges
            if e.get("_src") in node_ids
            or e.get("_tgt") in node_ids
            or e.get("source") in node_ids
            or e.get("target") in node_ids
        ]

    def get_stats(self) -> dict[str, Any]:
        total = self._conn.execute("SELECT COUNT(*) AS c FROM nodes").fetchone()["c"]
        rows = self._conn.execute(
            "SELECT community, COUNT(*) AS c FROM nodes GROUP BY community"
        ).fetchall()
        dist = {int(r["community"]): int(r["c"]) for r in rows}
        return {
            "total_nodes": total,
            "communities": len([c for c in dist if c >= 0]),
            "community_distribution": dist,
            "db_path": self.db_path,
            "backend": "turbovec",
            "bit_width": self.bit_width,
        }

    def delete_nodes(self, node_ids) -> int:
        ids = [str(i) for i in node_ids]
        if not ids:
            return 0
        idx = self._load_index()
        removed = 0
        for node_id in ids:
            row = self._conn.execute(
                "SELECT uid FROM nodes WHERE node_id = ?", (node_id,)
            ).fetchone()
            if row is None:
                continue
            if idx is not None:
                try:
                    idx.remove(int(row["uid"]))
                except Exception:
                    pass
            self._conn.execute("DELETE FROM nodes WHERE node_id = ?", (node_id,))
            removed += 1
        if removed:
            self._dirty = True
            self._persist_index()
            self._conn.commit()
        return removed

    def clear(self) -> None:
        self._conn.execute("DELETE FROM nodes")
        self._conn.execute("DELETE FROM meta")
        self._conn.commit()
        self._index = None
        self._dirty = False
        try:
            self._index_path.unlink()
        except FileNotFoundError:
            pass

    def close(self) -> None:
        try:
            self._conn.commit()
            self._conn.close()
        except Exception:
            pass
