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
* **embeddings** → owned here via ``onnx_embedder.OnnxMiniLMEmbedder``, which
  produces vectors *byte-identical* to ChromaDB's ``DefaultEmbeddingFunction``
  (same ``all-MiniLM-L6-v2`` model + pipeline) on just onnxruntime + tokenizers.
  Injectable through ``embed_fn`` for tests. **No ChromaDB import on this path.**

Scope: this is opt-in (``backend: turbovec`` / ``create_backend("turbovec", …)``)
and never the default. It implements the full ``EmbeddingBackend`` contract plus
``get_nodes_by_ids``/``delete_nodes`` so the synapse boost and incremental
reindex paths work unchanged.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import sqlite3
from collections.abc import Callable
from datetime import datetime
from functools import cached_property
from pathlib import Path
from typing import Any

import numpy as np

from .embedding_backend import EmbeddingBackend
from .progress import ProgressReporter
from .secret_scan import redact_if_enabled

logger = logging.getLogger(__name__)

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
    """Build the ChromaDB-free MiniLM embedder.

    Produces vectors byte-identical to ChromaDB's ``DefaultEmbeddingFunction``
    (same model + pipeline) on just onnxruntime + tokenizers, so the TurboVec
    backend needs no ChromaDB at all. Imported lazily so merely importing this
    module doesn't require onnxruntime; only constructing the backend does.
    """
    from .onnx_embedder import OnnxMiniLMEmbedder

    return OnnxMiniLMEmbedder()


class TurboVecEmbedder(EmbeddingBackend):
    """EmbeddingBackend backed by a TurboVec index + a SQLite metadata store."""

    # Scope definitions: maps scope name -> set of file_type values to INCLUDE
    SCOPE_FILTERS: dict[str, frozenset[str]] = {
        "code": frozenset({"code", "function", "class", "method", "module"}),
        "content": frozenset(
            {"document", "rationale", "content", "policy", "sop", "decision", "meeting_note"}
        ),
        "docs": frozenset({"document", "rationale"}),
        "all": frozenset(),  # empty = no filtering
    }

    # File-type extension-based fallback for when file_type is generic/missing
    SCOPE_EXTENSIONS: dict[str, frozenset[str]] = {
        "code": frozenset(
            {
                ".py",
                ".js",
                ".ts",
                ".tsx",
                ".jsx",
                ".go",
                ".rs",
                ".java",
                ".cs",
                ".c",
                ".cpp",
                ".h",
                ".rb",
                ".php",
                ".swift",
                ".kt",
            }
        ),
        "content": frozenset({".md", ".mdx", ".txt", ".rst", ".docx", ".pdf"}),
        "docs": frozenset({".md", ".mdx", ".txt", ".rst"}),
        "all": frozenset(),
    }

    def __init__(
        self,
        project_path: str,
        db_path: str | None = None,
        *,
        bit_width: int = _DEFAULT_BIT_WIDTH,
        embed_fn: Callable[[list[str]], list[list[float]]] | None = None,
        scope: str = "all",
    ):
        self._project_path = Path(project_path).resolve()
        self.graph_path = self._project_path / "graphify-out" / "graph.json"

        if db_path is None:
            db_path = str(self._project_path / "graphify-out" / "neuralmind_turbovec")
        self.db_path = db_path
        self._dir = Path(db_path)
        self._dir.mkdir(parents=True, exist_ok=True)

        # Per-scope store + index file naming to prevent collisions
        self._scope = scope
        if scope != "all":
            self._store_path = self._dir / f"store.{scope}.sqlite"
            self._index_path = self._dir / f"index.{scope}.tvim"
        else:
            self._store_path = self._dir / "store.sqlite"
            self._index_path = self._dir / "index.tvim"

        self.bit_width = int(bit_width)
        self._embed_fn = embed_fn  # resolved lazily so tests can inject a fake
        self.graph: dict = {}
        self.nodes: list[dict] = []
        self.edges: list[dict] = []

        self._index = None  # turbovec IdMapIndex, lazily created/loaded
        self._dirty = False  # mutated since last prepare()
        self._conn = sqlite3.connect(str(self._store_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_store()

    def _node_matches_scope(self, node: dict) -> bool:
        """Check if a node should be included based on the current scope."""
        if self._scope == "all":
            return True
        file_type = str(node.get("file_type", ""))
        source_file = str(node.get("source_file", ""))
        ext = Path(source_file).suffix.lower() if source_file else ""

        allowed_types = self.SCOPE_FILTERS.get(self._scope, frozenset())
        allowed_exts = self.SCOPE_EXTENSIONS.get(self._scope, frozenset())

        # If file_type is set and recognized, use type-based filtering
        if file_type and file_type in allowed_types:
            return True
        # If file_type is missing or unrecognized, fall back to extension
        if ext and ext in allowed_exts:
            return True
        # file_type is set but not in scope, and no extension match
        return False

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
                embedded_at  TEXT,
                content_category TEXT,
                tags         TEXT
            );
            CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
            """)
        # Additive columns for existing DBs (don't fail if already present)
        try:
            self._conn.execute("ALTER TABLE nodes ADD COLUMN content_category TEXT")
        except Exception:
            pass
        try:
            self._conn.execute("ALTER TABLE nodes ADD COLUMN tags TEXT")
        except Exception:
            pass
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

    def _embed_matrix(self, texts: list[str]) -> np.ndarray:
        """Embed ``texts`` into an ``(n, dim)`` array, numpy-native where possible.

        The default ``OnnxMiniLMEmbedder`` exposes ``embed()`` returning an
        ``ndarray`` directly. Its ``__call__`` (the ChromaDB-compatible interface)
        instead returns ``list[list[float]]`` via ``.tolist()`` — and the caller
        immediately rebuilds an array from it. For a large graph that round-trip
        materialises one Python ``float`` per element (n × 384), ~150 MB of
        transient heap that inflates peak RSS during indexing. Prefer ``embed()``
        when the embedder offers it; injected callables still work via the
        ``__call__`` fallback.
        """
        fn = self.embed_fn
        embed = getattr(fn, "embed", None)
        return embed(texts) if callable(embed) else fn(texts)

    @property
    def project_path(self) -> Path:
        return self._project_path

    def turbovec_index_version(self) -> str | None:
        """Return the turbovec index version if detectable, else None.

        The ``.tvim`` binary format embeds a version stamp that ``turbovec``
        checks on load. When the on-disk version is incompatible with the
        installed turbovec, ``IdMapIndex.load`` raises ``ValueError``. Since the
        C extension doesn't expose the version directly, we infer it from the
        quarantine file left behind by ``_load_index``: if a ``.stale`` file
        exists, the index was quarantined for incompatibility.

        Returns the installed turbovec version string, or ``None`` if
        turbovec is not installed.
        """
        try:
            import importlib.util

            if importlib.util.find_spec("turbovec") is None:
                return None
        except ImportError:
            return None
        # The version is in the dist-info metadata, but the C extension
        # doesn't expose it at runtime. Best effort from packaging metadata.
        try:
            import importlib.metadata

            return importlib.metadata.version("turbovec")
        except Exception:
            return "installed"

    def check_turbovec_compatibility(self) -> str | None:
        """Pre-flight check: return a warning string if the turbovec index
        was quarantined due to version incompatibility, else None.

        This surfaces the issue BEFORE the slow embed loop so the operator
        knows a rebuild is coming and why. The recovery itself happens in
        ``embed_nodes`` (via ``_rebuild_index_from_store``) — this check
        is just the user-visible heads-up.
        """
        stale_path = self._index_path.with_name(self._index_path.name + ".stale")
        if not stale_path.exists():
            return None
        tv_version = self.turbovec_index_version()
        return (
            f"The vector index was quarantined (likely a turbovec version mismatch).\n"
            f"Installed turbovec: {tv_version or 'unknown'}.\n"
            f"The stale index is backed up at: {stale_path.name}\n"
            f"Recovery will attempt to rebuild from stored vectors. If that fails,\n"
            f"a full re-embedding will be triggered automatically."
        )

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

            try:
                self._index = turbovec.IdMapIndex.load(str(self._index_path))
            except (OSError, ValueError):
                # Written by an incompatible turbovec version (e.g. a pre-v5
                # index after upgrading) or corrupted. Quarantine it, then
                # rebuild from the rows we already persisted.
                self._index_path.replace(
                    self._index_path.with_name(self._index_path.name + ".stale")
                )
                if self._rebuild_index_from_store():
                    return self._index
                return None
            self._dirty = False
        return self._index

    def _rebuild_index_from_store(self) -> int:
        """Re-embed every persisted row into a fresh index. Returns the count.

        Quarantining an unreadable index is only half a recovery. ``embed_nodes``
        escalates to ``force=True`` when the index has gone, but it re-embeds
        ``self.nodes`` — the graph — so anything ingested through
        ``embed_content`` (docs, compliance practices) is left behind: its rows
        survive in SQLite asserting a ``content_hash`` that makes the next
        ``embed_content`` skip them, while its vectors no longer exist. Searches
        then silently return nothing for that content, and a document-only store
        has no graph for ``embed_nodes`` to rebuild from at all.

        The ``document`` column holds the exact text each vector was built from,
        so the store is sufficient to rebuild every vector regardless of how it
        was ingested. Doing it here means any entry point — ``search``,
        ``embed_nodes``, ``embed_content`` — recovers on first touch instead of
        depending on the caller to know it must force a re-ingest.

        Best-effort: if embedding is unavailable (no ONNX runtime, no model),
        this returns 0 and the caller falls back to the previous behaviour
        rather than turning a degraded search into a crash.
        """
        rows = self._conn.execute(
            "SELECT uid, document FROM nodes "
            "WHERE document IS NOT NULL AND document != '' ORDER BY uid"
        ).fetchall()
        if not rows:
            return 0

        try:
            import turbovec

            vectors = _l2_normalize(self._embed_matrix([r["document"] for r in rows]))
            uids = np.array([int(r["uid"]) for r in rows], dtype=np.uint64)
            # Built directly rather than via _ensure_index: that calls
            # _load_index, and we are inside it.
            idx = turbovec.IdMapIndex(dim=vectors.shape[1], bit_width=self.bit_width)
            idx.add_with_ids(vectors, uids)
        except Exception:
            logger.warning(
                "Could not rebuild the vector index for %s after quarantining an "
                "unreadable one; %d stored node(s) stay unsearchable until the "
                "next forced re-embed.",
                self._index_path.parent,
                len(rows),
            )
            return 0

        self._index = idx
        self._meta_set("dim", str(vectors.shape[1]))
        self._meta_set("bit_width", str(self.bit_width))
        self._conn.commit()
        self._dirty = True
        self._persist_index()
        logger.info(
            "Rebuilt %d vector(s) from the node store after an unreadable index.",
            len(rows),
        )
        return len(rows)

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
    def _prefer_ir_over_graph(self) -> bool:
        """True when the persisted IR is present and not stale vs graph.json."""
        if not self.ir_path.exists():
            return False
        if not self.graph_path.exists():
            return True
        try:
            return self.ir_path.stat().st_mtime >= self.graph_path.stat().st_mtime
        except OSError:
            return False

    def load_graph(self) -> bool:
        from . import ir as ir_mod

        if self._prefer_ir_over_graph():
            try:
                ir_data = json.loads(self.ir_path.read_text(encoding="utf-8"))
                index_ir = ir_mod.IndexIR.from_dict(ir_data)
                self.graph = ir_mod.to_graph_json(index_ir)
            except (json.JSONDecodeError, ir_mod.IRError, KeyError, ValueError):
                if not self.graph_path.exists():
                    return False
                with self.graph_path.open(encoding="utf-8") as f:
                    self.graph = json.load(f)
        else:
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
        return redact_if_enabled("\n".join(parts))

    def _node_metadata(self, node: dict) -> dict[str, Any]:
        return {
            "label": str(node.get("label", node.get("id", "unknown"))),
            "file_type": str(node.get("file_type", "unknown")),
            "source_file": str(node.get("source_file", "")),
            "community": int(node.get("community", -1)),
            "node_id": str(node.get("id", "")),
        }

    def _content_node_metadata(self, node: dict) -> dict[str, Any]:
        """Extract metadata from a content node for filtering."""
        meta = self._node_metadata(node)
        # Preserve business-context metadata
        node_meta = node.get("metadata", {}) or {}
        for key in ("practice_id", "title", "domain", "framework", "content_category"):
            if key in node_meta:
                meta[key] = str(node_meta[key])
        # Serialize tags as JSON for SQLite storage
        if "tags" in node_meta:
            import json

            meta["tags"] = json.dumps(node_meta["tags"])
        return meta

    def get_all_nodes(self) -> list[dict]:
        """Return all indexed nodes as a list of dicts."""
        nodes: list[dict] = []
        try:
            rows = self._conn.execute(
                "SELECT node_id, document, label, file_type, source_file, community, content_category, tags FROM nodes"
            ).fetchall()
        except Exception:
            # Fallback if columns don't exist yet (legacy DB without the columns)
            try:
                rows = self._conn.execute(
                    "SELECT node_id, document, label, file_type, source_file, community, '' as content_category, '' as tags FROM nodes"
                ).fetchall()
            except Exception:
                return nodes
        for row in rows:
            nodes.append(
                {
                    "id": row["node_id"],
                    "label": row["label"] or row["node_id"],
                    "content_text": row["document"] or "",
                    "metadata": {
                        "label": row["label"],
                        "file_type": row["file_type"],
                        "source_file": row["source_file"],
                        "community": row["community"],
                        "node_id": row["node_id"],
                        "content_category": row["content_category"] or "",
                        "tags": row["tags"] or "",
                    },
                }
            )
        return nodes

    @staticmethod
    def _content_hash(text: str) -> str:
        return hashlib.sha256(text.encode()).hexdigest()[:16]

    # ----------------------------------------------------------------- embed
    def embed_content(self, content_nodes: list[dict], force: bool = False) -> dict[str, int]:
        """Embed non-code content nodes (compliance practices, docs, etc.)."""
        stats = {"added": 0, "updated": 0, "skipped": 0}
        if not content_nodes:
            return stats

        pending = []
        next_uid = self._next_uid()

        for node in content_nodes:
            node_id = str(node.get("id", node.get("label", "")))
            if not node_id:
                continue
            content_text = node.get("content_text", "")
            text = redact_if_enabled(content_text) if content_text else self._node_to_text(node)
            content_hash = self._content_hash(text)
            row = self._conn.execute(
                "SELECT uid, content_hash, content_category FROM nodes WHERE node_id = ?",
                (node_id,),
            ).fetchone()

            if row is not None:
                if not force and row["content_hash"] == content_hash:
                    stats["skipped"] += 1
                    continue
                uid = int(row["uid"])
                is_update = True
                stats["updated"] += 1
                existing_cc = row["content_category"] or ""
            else:
                uid = next_uid
                next_uid += 1
                is_update = False
                stats["added"] += 1
                existing_cc = ""

            meta = self._content_node_metadata(node)
            # Don't overwrite content_category from DB with empty graph value
            if existing_cc and not meta.get("content_category"):
                meta["content_category"] = existing_cc
            meta["content_hash"] = content_hash
            meta["embedded_at"] = datetime.now().isoformat()
            pending.append((node_id, uid, text, meta, content_hash, is_update))

        if not pending:
            self._persist_index()
            self._conn.commit()
            return stats

        vectors = _l2_normalize(self._embed_matrix([p[2] for p in pending]))
        dim = vectors.shape[1]
        idx = self._ensure_index(dim)

        now = datetime.now().isoformat()
        new_vecs = []
        new_ids = []
        for (node_id, uid, text, meta, content_hash, is_update), vec in zip(
            pending, vectors, strict=True
        ):
            if is_update:
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
                                  source_file, community, content_hash, embedded_at,
                                  content_category, tags)
                VALUES(?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(node_id) DO UPDATE SET
                    document=excluded.document, label=excluded.label,
                    file_type=excluded.file_type, source_file=excluded.source_file,
                    community=excluded.community, content_hash=excluded.content_hash,
                    embedded_at=excluded.embedded_at,
                    content_category=excluded.content_category, tags=excluded.tags
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
                    meta.get("content_category", ""),
                    meta.get("tags", ""),
                ),
            )

        if new_ids:
            idx.add_with_ids(np.vstack(new_vecs), np.array(new_ids, dtype=np.uint64))

        self._dirty = True
        self._persist_index()
        self._conn.commit()

        # Refresh the keyword index, the same way embed_nodes() does. Without
        # this, freshly ingested content is invisible to BM25 — and so to
        # hybrid retrieval — until the next full build. A content-only corpus
        # feels that hardest: it may never run one.
        self.build_bm25_index()
        return stats

    def embed_nodes(self, force: bool = False) -> dict[str, int]:
        if not self.nodes and not self.load_graph():
            return {"added": 0, "updated": 0, "skipped": 0, "error": "No graph loaded"}

        # Detect index version mismatch before the slow embed loop.
        # If _load_index returns None but the SQLite store has rows, the
        # index was quarantined as unreadable (version mismatch, corrupt).
        # Recover incrementally from the stored vectors instead of forcing
        # a full re-embed.
        idx = self._load_index()
        if idx is None:
            row = self._conn.execute("SELECT COUNT(*) AS c FROM nodes").fetchone()
            if int(row["c"]) > 0:
                # Try incremental recovery from stored vectors first.
                logger.info(
                    "Index version mismatch detected. Attempting incremental "
                    "rebuild from %d stored vectors...",
                    int(row["c"]),
                )
                if self._rebuild_index_from_store():
                    # Success — index recovered, proceed with incremental update.
                    stats_rebuilt = int(row["c"])
                    logger.info(
                        "Successfully recovered %d vectors from store. "
                        "Proceeding with incremental update.",
                        stats_rebuilt,
                    )
                    # Fall through to incremental loop below — don't force.
                else:
                    # Recovery failed (no ONNX, no model). Force full re-embed.
                    force = True
                    logger.warning("Incremental recovery failed. Forcing full re-embedding.")

        stats = {"added": 0, "updated": 0, "skipped": 0}
        pending: list[tuple[str, int, str, dict, str, bool]] = (
            []
        )  # (node_id, uid, text, meta, hash, is_update)
        next_uid = self._next_uid()

        total_nodes = len(self.nodes)
        scope_filtered = 0
        with ProgressReporter(total_nodes, label="Embedding") as bar:
            for node in self.nodes:
                node_id = str(node.get("id", node.get("label", "")))
                if not node_id:
                    continue
                # Apply scope filter — skip nodes not matching the current scope
                if not self._node_matches_scope(node):
                    scope_filtered += 1
                    bar.advance()
                    continue
                text = self._node_to_text(node)
                content_hash = self._content_hash(text)
                row = self._conn.execute(
                    "SELECT uid, content_hash, content_category FROM nodes WHERE node_id = ?",
                    (node_id,),
                ).fetchone()

                if row is not None:
                    if not force and row["content_hash"] == content_hash:
                        stats["skipped"] += 1
                        bar.advance()
                        continue
                    uid = int(row["uid"])
                    is_update = True
                    stats["updated"] += 1
                    existing_cc = row["content_category"] or ""
                else:
                    uid = next_uid
                    next_uid += 1
                    is_update = False
                    stats["added"] += 1
                    existing_cc = ""

                meta = self._node_metadata(node)
                if existing_cc and not meta.get("content_category"):
                    meta["content_category"] = existing_cc

                pending.append((node_id, uid, text, meta, content_hash, is_update))
                bar.advance(detail=node_id[:40])

        if not pending:
            self._persist_index()
            self._conn.commit()
            self.build_bm25_index()
            return stats

        vectors = _l2_normalize(self._embed_matrix([p[2] for p in pending]))
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
                                  source_file, community, content_hash, embedded_at,
                                  content_category, tags)
                VALUES(?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(node_id) DO UPDATE SET
                    document=excluded.document, label=excluded.label,
                    file_type=excluded.file_type, source_file=excluded.source_file,
                    community=excluded.community, content_hash=excluded.content_hash,
                    embedded_at=excluded.embedded_at,
                    content_category=excluded.content_category, tags=excluded.tags
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
                    meta.get("content_category", ""),
                    meta.get("tags", ""),
                ),
            )

        if new_ids:
            idx.add_with_ids(np.vstack(new_vecs), np.array(new_ids, dtype=np.uint64))

        self._dirty = True
        self._persist_index()
        self._conn.commit()
        self.build_bm25_index()
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
        q = _l2_normalize(self._embed_matrix([query]))

        try:
            scores, ids = idx.search(q, k, allowlist=allowlist)
        except Exception:
            # A freshly mutated index may need (re)preparing before search.
            # If the retry still fails (e.g., allowlist has dangling uids not in index),
            # return empty results instead of crashing.
            try:
                idx.prepare()
                scores, ids = idx.search(q, k, allowlist=allowlist)
            except Exception:
                return []

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
            "content_category": row["content_category"] or "",
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
                    "text": str(n.get("text", n.get("document", "")))[:200],
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

    # ------------------------------------------------------------------
    # BM25 keyword index — hybrid search
    # ------------------------------------------------------------------

    @cached_property
    def _bm25_path(self) -> Path:
        return self._dir / "bm25_index.json"

    def _load_bm25(self):
        """Load or build the BM25 keyword index."""
        if hasattr(self, "_bm25_cached"):
            return self._bm25_cached
        from .bm25 import BM25Index

        if self._bm25_path.exists():
            self._bm25_cached = BM25Index.load(self._bm25_path)
            return self._bm25_cached
        return None

    def build_bm25_index(self) -> None:
        """Build and persist the BM25 keyword index from the SQLite store.

        Called automatically at the end of embed_nodes() so the BM25 index
        stays in sync with the vector index.
        """
        from .bm25 import BM25Index

        ids, texts, metas = [], [], []
        rows = self._conn.execute(
            "SELECT node_id, document, label, file_type, source_file, community FROM nodes"
        ).fetchall()
        for r in rows:
            ids.append(r["node_id"])
            texts.append(r["document"] or r["label"] or r["node_id"])
            metas.append(
                {
                    "label": r["label"],
                    "file_type": r["file_type"],
                    "source_file": r["source_file"],
                    "community": r["community"],
                    "node_id": r["node_id"],
                }
            )
        if not ids:
            self._bm25_cached = None
            try:
                self._bm25_path.unlink()
            except (FileNotFoundError, AttributeError):
                pass
            return
        idx = BM25Index()
        idx.add_documents(ids, texts, metas)
        idx.build()
        idx.save(self._bm25_path)
        self._bm25_cached = idx

    def bm25_search(self, query: str, n: int = 10) -> list[dict[str, Any]]:
        """BM25 keyword search — same result shape as search().

        Returns an empty list when the index hasn't been built yet or when
        NEURALMIND_BM25=0 is set.
        """
        if os.environ.get("NEURALMIND_BM25") == "0":
            return []
        idx = self._load_bm25()
        if idx is None or idx._N == 0:
            return []
        raw = idx.search(query, top_k=n)
        out = []
        for r in raw:
            sim = float(r["score"])
            out.append(
                {
                    "id": r["id"],
                    "document": r["document"],
                    "metadata": r["metadata"],
                    "distance": round(1.0 - sim, 6),
                    "score": round(sim, 6),
                    "_bm25_raw": r.get("_bm25_raw"),
                }
            )
        return out

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
            self.build_bm25_index()
        return removed

    def clear(self) -> None:
        self._conn.execute("DELETE FROM nodes")
        self._conn.execute("DELETE FROM meta")
        self._conn.commit()
        self._index = None
        self._dirty = False
        # Invalidate BM25 index — nodes are gone
        self._bm25_cached = None
        try:
            self._bm25_path.unlink()
        except (FileNotFoundError, AttributeError):
            pass
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
