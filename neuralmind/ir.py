"""NeuralMind canonical Intermediate Representation (IR).

The IR is the *one* versioned contract every downstream layer — retrieval,
memory, compression, benchmarking, UI, MCP — is meant to consume. Today the
stack reads a graphify-shaped ``graph.json`` (networkx node-link) directly;
that couples retrieval to one producer's field names and gives no place to
hang a schema version, migration metadata, or per-backend coverage signals.

This module introduces a canonical, ``ir_version``-stamped representation and
a **round-trip-faithful** graphify→IR adapter. Faithfulness is the
load-bearing property: any ``graph.json`` round-trips ``graph → IR → graph``
back to a dict that is equal on every field the stack consumes (node id /
label / file_type / source_file / source_location / community / norm_label;
edge relation / source / target / weight / confidence). Non-standard producer
fields are preserved verbatim in ``extra``; only producer-cosmetic fields no
consumer reads (e.g. an absent edge ``context``) may be normalized. Wiring the
IR in front of the existing embedder therefore changes *nothing* the embedder,
selector, skeleton, or graph-view sees — which is what makes the Phase-1
rollout ("hidden internal adapter, legacy mode default") safe.

Stdlib-only on purpose — like the synapse layer, the IR and its tests run
without the full embedding dep set.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# --------------------------------------------------------------------------- #
# Versioning
# --------------------------------------------------------------------------- #

# The canonical IR contract version. Bump on a breaking change to the IR shape
# and add a migration in ``migrate_payload``. Unsupported (newer) versions are
# rejected with an actionable error rather than silently mis-read.
IR_VERSION = 1

# IR versions this build knows how to load. Anything outside the range is a
# hard error on load (FR4: "reject unsupported IR versions").
SUPPORTED_IR_VERSIONS: frozenset[int] = frozenset({1})


# --------------------------------------------------------------------------- #
# Canonical vocabularies
# --------------------------------------------------------------------------- #

# Canonical node kinds. graphify's coarse ``file_type`` (code/rationale/
# document) can only populate a subset; richer backends (SCIP/LSP) specialize
# ``symbol`` into function/class/method/module. Unknown kinds are a validation
# *warning*, not an error — forward compatibility for new backends.
NODE_KINDS: frozenset[str] = frozenset(
    {
        "file",
        "module",
        "symbol",
        "function",
        "class",
        "method",
        "document",
        "cluster",
    }
)

# Canonical edge relations the current extractors emit (graphify + built-in
# tree-sitter). Unknown relations are a validation warning, not an error.
EDGE_RELATIONS: frozenset[str] = frozenset(
    {
        "contains",
        "calls",
        "imports",
        "imports_from",
        "inherits",
        "implements",
        "shares_data_with",
        "uses",
        "rationale_for",
        "references",
        "defines",
    }
)

# How completely a backend resolved a node's kind. graphify/tree-sitter cannot
# reliably split a code symbol into function vs class vs method, so it reports
# ``coarse`` — a future SCIP/LSP backend reports ``precise``. Recorded per
# build so benchmarking and validation can reason about coverage (technical
# requirement: "IR can represent partial parser coverage and confidence").
COVERAGE_COARSE = "coarse"
COVERAGE_PRECISE = "precise"

# Suffix → language, kept local so the IR has no tree-sitter dependency.
_SUFFIX_LANG: dict[str, str] = {
    ".py": "python",
    ".pyi": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".rb": "ruby",
    ".md": "markdown",
    ".markdown": "markdown",
    ".rst": "restructuredtext",
}

# Standard graphify node-link keys the adapter lifts into canonical fields.
# Anything outside these is preserved verbatim in ``extra`` for lossless
# round-trip (so an unknown graphify field survives graph → IR → graph).
_STD_NODE_KEYS = frozenset(
    {"id", "label", "file_type", "source_file", "source_location", "community", "norm_label"}
)
_STD_EDGE_KEYS = frozenset(
    {
        "relation",
        "context",
        "confidence",
        "source_file",
        "source_location",
        "weight",
        "source",
        "target",
        "confidence_score",
    }
)


class IRError(Exception):
    """Raised when an IR payload cannot be loaded (e.g. unsupported version)."""


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _line_from_location(loc: Any) -> int:
    """``"L42"`` → ``42``; tolerate ints and junk → 0."""
    if isinstance(loc, int):
        return loc
    if isinstance(loc, str):
        try:
            return int(loc.lstrip("Ll"))
        except ValueError:
            return 0
    return 0


def _language_for(source_file: str) -> str:
    return _SUFFIX_LANG.get(Path(source_file).suffix.lower(), "")


def _looks_like_filename(label: str) -> bool:
    suffix = Path(label).suffix.lower()
    return suffix in _SUFFIX_LANG


def project_artifact(project_path: str | Path, *parts: str) -> Path:
    """Resolve a fixed artifact path under a project root, refusing escapes.

    The daemon accepts a project path over HTTP and the CLI takes one as an
    argument, so a project root flows from external input into filesystem
    reads/writes. Normalizing the base and confirming the (constant-suffix)
    artifact stays within it — via ``os.path.commonpath`` — neutralizes any
    path traversal in the supplied root before it reaches a file operation. A
    single choke point so no caller builds an unchecked path from untrusted
    input. Pure string normalization (no symlink resolution), so it stays a
    barrier and never itself becomes a filesystem access.
    """
    base = os.path.abspath(project_path)
    target = os.path.normpath(os.path.join(base, *parts))
    if base != target and os.path.commonpath([base, target]) != base:
        raise ValueError(f"artifact path {target} escapes project root {base}")
    return Path(target)


def _kind_for_node(node: dict) -> str:
    """Best-effort canonical kind for a graphify node.

    The ``graph.json`` schema is intentionally locked to graphify's shape
    (built-in/graphify parity is enforced by a test), so the only kind signal
    available is ``file_type`` (code / rationale / document) plus the label
    convention. We use both:

    - ``document`` / ``rationale`` → ``document``;
    - a code node whose location anchors a file → ``file``;
    - a code node whose label is a call form (``name()`` — the convention the
      built-in tree-sitter backend emits for functions and methods) →
      ``function``;
    - everything else (classes, fields, constants, and any producer that
      doesn't follow the call-form convention) → the generic ``symbol``.

    This stays deliberately conservative — it never *guesses* a class — so the
    build records ``coarse`` coverage. A precise backend that carries real kind
    metadata is the path to ``precise`` (see :data:`COVERAGE_PRECISE`).
    """
    file_type = str(node.get("file_type", "")).lower()
    label = str(node.get("label", ""))
    location = node.get("source_location", "")
    is_file_anchor = location in ("L1", "L0", 1, 0) and _looks_like_filename(label)

    if file_type in ("document", "rationale"):
        return "document"
    if is_file_anchor:
        return "file"
    if label.endswith(")"):  # graphgen emits callables as ``name()``
        return "function"
    return "symbol"


# --------------------------------------------------------------------------- #
# Canonical entities
# --------------------------------------------------------------------------- #


@dataclass
class IRNode:
    """A canonical code/document entity.

    ``kind`` is from :data:`NODE_KINDS`. ``extra`` carries any non-standard
    producer fields verbatim so the adapter can reconstruct the exact source
    node. ``confidence`` is the backend's confidence in this node (1.0 for the
    deterministic graphify/tree-sitter extractors).
    """

    id: str
    kind: str
    label: str
    source_file: str = ""
    line: int = 0
    language: str = ""
    cluster: int = -1
    norm_label: str = ""
    confidence: float = 1.0
    # Original coarse ``file_type`` — kept so ``to_graph_json`` is lossless and
    # so coverage analysis can see what the producer actually labelled.
    raw_kind: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "label": self.label,
            "source_file": self.source_file,
            "line": self.line,
            "language": self.language,
            "cluster": self.cluster,
            "norm_label": self.norm_label,
            "confidence": self.confidence,
            "raw_kind": self.raw_kind,
            "extra": self.extra,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> IRNode:
        return cls(
            id=str(d.get("id", "")),
            kind=str(d.get("kind", "symbol")),
            label=str(d.get("label", "")),
            source_file=str(d.get("source_file", "")),
            line=int(d.get("line", 0) or 0),
            language=str(d.get("language", "")),
            cluster=int(d.get("cluster", -1)),
            norm_label=str(d.get("norm_label", "")),
            confidence=float(d.get("confidence", 1.0)),
            raw_kind=str(d.get("raw_kind", "")),
            extra=dict(d.get("extra", {})),
        )


@dataclass
class IREdge:
    """A canonical relationship between two nodes."""

    relation: str
    source: str
    target: str
    source_file: str = ""
    line: int = 0
    weight: float = 1.0
    confidence: str = "EXTRACTED"
    confidence_score: float = 1.0
    context: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "relation": self.relation,
            "source": self.source,
            "target": self.target,
            "source_file": self.source_file,
            "line": self.line,
            "weight": self.weight,
            "confidence": self.confidence,
            "confidence_score": self.confidence_score,
            "context": self.context,
            "extra": self.extra,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> IREdge:
        return cls(
            relation=str(d.get("relation", "")),
            source=str(d.get("source", "")),
            target=str(d.get("target", "")),
            source_file=str(d.get("source_file", "")),
            line=int(d.get("line", 0) or 0),
            weight=float(d.get("weight", 1.0)),
            confidence=str(d.get("confidence", "EXTRACTED")),
            confidence_score=float(d.get("confidence_score", 1.0)),
            context=str(d.get("context", "")),
            extra=dict(d.get("extra", {})),
        )


@dataclass
class IRCluster:
    """A community/cluster of nodes (graphify modularity stand-in).

    Derived from node ``cluster`` ids; modelled as a first-class entity so the
    selector's L1/L2 layers and the graph UI have a stable cluster contract.
    """

    id: int
    size: int = 0
    label: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "size": self.size, "label": self.label}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> IRCluster:
        return cls(
            id=int(d.get("id", -1)),
            size=int(d.get("size", 0)),
            label=str(d.get("label", "")),
        )


@dataclass
class IRSynapse:
    """A learned (Hebbian) association between two nodes.

    The live synapse store is SQLite-backed; this is the IR's portable,
    versioned shape for export/import and for the future team-memory bundles
    (PRD 8). Empty for a freshly-adapted graph — populated on demand.
    """

    source: str
    target: str
    weight: float = 0.0
    kind: str = "co_activation"

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "target": self.target,
            "weight": self.weight,
            "kind": self.kind,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> IRSynapse:
        return cls(
            source=str(d.get("source", "")),
            target=str(d.get("target", "")),
            weight=float(d.get("weight", 0.0)),
            kind=str(d.get("kind", "co_activation")),
        )


@dataclass
class IndexIR:
    """The canonical, versioned index representation.

    ``source_meta`` preserves the producer's top-level node-link keys
    (``directed``, ``built_at_commit``, the edge container key, …) so the
    adapter can reconstruct an equivalent ``graph.json``.
    """

    ir_version: int = IR_VERSION
    generated_by: str = "neuralmind.ir"
    source_backend: str = ""
    source_schema_version: int | None = None
    built_at_commit: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    coverage: str = COVERAGE_COARSE
    nodes: list[IRNode] = field(default_factory=list)
    edges: list[IREdge] = field(default_factory=list)
    clusters: list[IRCluster] = field(default_factory=list)
    synapses: list[IRSynapse] = field(default_factory=list)
    source_meta: dict[str, Any] = field(default_factory=dict)

    # -- summary ----------------------------------------------------------- #
    def summary(self) -> dict[str, Any]:
        """Compact, machine-readable metadata for stats / debug / benchmark."""
        kinds: dict[str, int] = {}
        for n in self.nodes:
            kinds[n.kind] = kinds.get(n.kind, 0) + 1
        langs: dict[str, int] = {}
        for n in self.nodes:
            if n.language:
                langs[n.language] = langs.get(n.language, 0) + 1
        return {
            "ir_version": self.ir_version,
            "generated_by": self.generated_by,
            "source_backend": self.source_backend,
            "source_schema_version": self.source_schema_version,
            "coverage": self.coverage,
            "built_at_commit": self.built_at_commit,
            "created_at": self.created_at,
            "nodes": len(self.nodes),
            "edges": len(self.edges),
            "clusters": len(self.clusters),
            "synapses": len(self.synapses),
            "node_kinds": kinds,
            "languages": langs,
        }

    # -- serialization ----------------------------------------------------- #
    def to_dict(self) -> dict[str, Any]:
        return {
            "ir_version": self.ir_version,
            "generated_by": self.generated_by,
            "source_backend": self.source_backend,
            "source_schema_version": self.source_schema_version,
            "built_at_commit": self.built_at_commit,
            "created_at": self.created_at,
            "coverage": self.coverage,
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "clusters": [c.to_dict() for c in self.clusters],
            "synapses": [s.to_dict() for s in self.synapses],
            "source_meta": self.source_meta,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> IndexIR:
        version = int(d.get("ir_version", 0))
        if version not in SUPPORTED_IR_VERSIONS:
            d = migrate_payload(d)  # may raise IRError
            version = int(d.get("ir_version", 0))
        return cls(
            ir_version=version,
            generated_by=str(d.get("generated_by", "neuralmind.ir")),
            source_backend=str(d.get("source_backend", "")),
            source_schema_version=d.get("source_schema_version"),
            built_at_commit=str(d.get("built_at_commit", "")),
            created_at=str(d.get("created_at", "")),
            coverage=str(d.get("coverage", COVERAGE_COARSE)),
            nodes=[IRNode.from_dict(n) for n in d.get("nodes", [])],
            edges=[IREdge.from_dict(e) for e in d.get("edges", [])],
            clusters=[IRCluster.from_dict(c) for c in d.get("clusters", [])],
            synapses=[IRSynapse.from_dict(s) for s in d.get("synapses", [])],
            source_meta=dict(d.get("source_meta", {})),
        )

    def write(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

    @classmethod
    def read(cls, path: str | Path) -> IndexIR:
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


# --------------------------------------------------------------------------- #
# Migration (FR3 / FR4)
# --------------------------------------------------------------------------- #


def migrate_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Upgrade an older IR payload to the current version in place.

    Raises :class:`IRError` for versions newer than this build understands
    (FR4: unsupported versions get an actionable error, never a silent
    mis-read). Currently IR v1 is the only version, so this exists to give a
    real upgrade seam the moment v2 lands.
    """
    version = int(payload.get("ir_version", 0))
    if version in SUPPORTED_IR_VERSIONS:
        return payload
    if version > IR_VERSION:
        raise IRError(
            f"IR payload is version {version}, but this NeuralMind build only "
            f"understands up to version {IR_VERSION}. Upgrade NeuralMind "
            f"(`pip install -U neuralmind`) to read this index."
        )
    # version < min supported: no historical versions exist yet. When v2
    # arrives, chain migrations here (v1→v2→…).
    raise IRError(
        f"IR payload version {version} is too old to migrate automatically. "
        f"Rebuild the index with `neuralmind build --force`."
    )


# --------------------------------------------------------------------------- #
# graphify ⇄ IR adapter
# --------------------------------------------------------------------------- #


def from_graph_json(graph: dict[str, Any], *, source_backend: str = "") -> IndexIR:
    """Adapt a graphify/tree-sitter ``graph.json`` dict into the canonical IR.

    Lossless: every standard node/edge field is lifted into a canonical field,
    and any non-standard field is preserved in ``extra``. Top-level keys are
    kept in ``source_meta``. :func:`to_graph_json` reverses this exactly.
    """
    raw_nodes = graph.get("nodes", []) or []
    # graphify uses "links"; some callers pass "edges". Remember which so we
    # can round-trip under the same key.
    if "edges" in graph and "links" not in graph:
        edge_key = "edges"
    else:
        edge_key = "links"
    raw_edges = graph.get(edge_key, []) or []

    backend = source_backend or str(graph.get("generated_by", "")) or "unknown"
    schema_version = graph.get("schema_version")

    nodes: list[IRNode] = []
    for n in raw_nodes:
        extra = {k: v for k, v in n.items() if k not in _STD_NODE_KEYS}
        source_file = str(n.get("source_file", ""))
        nodes.append(
            IRNode(
                id=str(n.get("id", n.get("label", ""))),
                kind=_kind_for_node(n),
                label=str(n.get("label", n.get("id", ""))),
                source_file=source_file,
                line=_line_from_location(n.get("source_location")),
                language=_language_for(source_file),
                cluster=int(n.get("community", -1)),
                norm_label=str(n.get("norm_label", str(n.get("label", "")).lower())),
                raw_kind=str(n.get("file_type", "")),
                extra=extra,
            )
        )

    edges: list[IREdge] = []
    for e in raw_edges:
        extra = {k: v for k, v in e.items() if k not in _STD_EDGE_KEYS}
        relation = str(e.get("relation", ""))
        edges.append(
            IREdge(
                relation=relation,
                source=str(e.get("source", "")),
                target=str(e.get("target", "")),
                source_file=str(e.get("source_file", "")),
                line=_line_from_location(e.get("source_location")),
                weight=float(e.get("weight", 1.0)),
                confidence=str(e.get("confidence", "EXTRACTED")),
                confidence_score=float(e.get("confidence_score", 1.0)),
                context=str(e.get("context", relation)),
                extra=extra,
            )
        )

    clusters = _derive_clusters(nodes)

    source_meta = {k: v for k, v in graph.items() if k not in ("nodes", "links", "edges")}
    source_meta["_edge_key"] = edge_key

    return IndexIR(
        ir_version=IR_VERSION,
        generated_by="neuralmind.ir.from_graph_json",
        source_backend=backend,
        source_schema_version=schema_version,
        built_at_commit=str(graph.get("built_at_commit", "")),
        coverage=COVERAGE_COARSE,
        nodes=nodes,
        edges=edges,
        clusters=clusters,
        source_meta=source_meta,
    )


def _derive_clusters(nodes: Iterable[IRNode]) -> list[IRCluster]:
    sizes: dict[int, int] = {}
    for n in nodes:
        if n.cluster is None or n.cluster < 0:
            continue
        sizes[n.cluster] = sizes.get(n.cluster, 0) + 1
    return [IRCluster(id=cid, size=size) for cid, size in sorted(sizes.items())]


def to_graph_json(ir: IndexIR) -> dict[str, Any]:
    """Reconstruct an equivalent graphify ``graph.json`` dict from the IR.

    The inverse of :func:`from_graph_json`. Standard fields are rebuilt from
    canonical fields; ``extra`` is merged back; the original edge container key
    and top-level metadata are restored from ``source_meta``.
    """
    meta = dict(ir.source_meta)
    edge_key = meta.pop("_edge_key", "links")

    nodes: list[dict[str, Any]] = []
    for n in ir.nodes:
        node: dict[str, Any] = {
            "label": n.label,
            "file_type": n.raw_kind or _coarse_file_type(n.kind),
            "source_file": n.source_file,
            # Preserve the exact line, including 0 -> "L0", so a graph using
            # "L0" round-trips identically (don't coerce 0 to "L1").
            "source_location": f"L{max(n.line, 0)}",
            "id": n.id,
            "community": n.cluster,
            "norm_label": n.norm_label,
        }
        node.update(n.extra)
        nodes.append(node)

    edges: list[dict[str, Any]] = []
    for e in ir.edges:
        edge: dict[str, Any] = {
            "relation": e.relation,
            "context": e.context or e.relation,
            "confidence": e.confidence,
            "source_file": e.source_file,
            "source_location": f"L{max(e.line, 0)}",  # preserve 0 -> "L0" (round-trip)
            "weight": e.weight,
            "source": e.source,
            "target": e.target,
            "confidence_score": e.confidence_score,
        }
        edge.update(e.extra)
        edges.append(edge)

    graph: dict[str, Any] = dict(meta)
    graph["nodes"] = nodes
    graph[edge_key] = edges
    return graph


def _coarse_file_type(kind: str) -> str:
    """Canonical kind → graphify ``file_type`` (fallback when ``raw_kind`` is
    absent, e.g. a node minted by a precise backend that never had one)."""
    if kind == "document":
        return "document"
    return "code"


# --------------------------------------------------------------------------- #
# Synapses
# --------------------------------------------------------------------------- #


def synapses_from_edges(edge_rows: Iterable[tuple]) -> list[IRSynapse]:
    """Build canonical synapses from a synapse store's ``edges()`` rows.

    Each row is ``(node_a, node_b, weight, activation_count)`` (the shape
    :meth:`neuralmind.synapses.SynapseStore.edges` returns). Learned
    co-activation associations are first-class IR entities so they travel with
    the index (and, later, with the portable team-memory bundles of PRD 8).
    """
    out: list[IRSynapse] = []
    for row in edge_rows:
        a, b, weight = row[0], row[1], float(row[2])
        out.append(IRSynapse(source=str(a), target=str(b), weight=weight, kind="co_activation"))
    return out


def load_synapses_for_project(project_path: str | Path) -> list[IRSynapse]:
    """Load learned synapses for a project from its SQLite store, if present.

    Backend-free (the synapse store is stdlib ``sqlite3``), so ``validate`` can
    fold synapses into the IR without standing up an embedding backend. Returns
    an empty list when there's no store or it can't be read.
    """
    db = project_artifact(project_path, ".neuralmind", "synapses.db")
    if not db.exists():
        return []
    try:
        from .synapses import SynapseStore

        store = SynapseStore(db)
        return synapses_from_edges(store.edges(min_weight=0.0, limit=5000))
    except Exception:  # pragma: no cover - defensive; synapses are optional
        return []


# --------------------------------------------------------------------------- #
# Synapse namespace bundles (PRD 4; the PRD 8 team-memory on-ramp)
# --------------------------------------------------------------------------- #

# A bundle is one namespace's learned memory as portable JSON. Entries reuse
# the IRSynapse shape (source/target/weight/kind) plus the lifetime counters
# the store needs to merge faithfully (activation_count / count). The format
# is versioned independently of the IR so PRD 8 can evolve bundles (signing,
# provenance) without touching the index contract.
SYNAPSE_BUNDLE_FORMAT = "neuralmind.synapse-bundle"
SYNAPSE_BUNDLE_VERSION = 1
SYNAPSE_BUNDLE_KIND_TRANSITION = "transition"
_SYNAPSE_BUNDLE_EXPORT_LIMIT = 100_000


def export_synapse_bundle(store: Any, namespace: str) -> dict[str, Any]:
    """Export one namespace from a synapse store as a portable bundle dict.

    Reads the namespace raw (no merged-mode multipliers), so the bundle
    carries exactly the weights the store learned.
    """
    edge_rows = store.edges(
        min_weight=0.0, limit=_SYNAPSE_BUNDLE_EXPORT_LIMIT, namespaces=[namespace]
    )
    transition_rows = store.transitions(
        min_weight=0.0, limit=_SYNAPSE_BUNDLE_EXPORT_LIMIT, namespaces=[namespace]
    )
    synapses = []
    for a, b, weight, count in edge_rows:
        entry = IRSynapse(source=str(a), target=str(b), weight=float(weight)).to_dict()
        entry["activation_count"] = int(count)
        synapses.append(entry)
    transitions = []
    for f, t, weight, count in transition_rows:
        entry = IRSynapse(
            source=str(f), target=str(t), weight=float(weight), kind=SYNAPSE_BUNDLE_KIND_TRANSITION
        ).to_dict()
        entry["count"] = int(count)
        transitions.append(entry)
    return {
        "format": SYNAPSE_BUNDLE_FORMAT,
        "version": SYNAPSE_BUNDLE_VERSION,
        "namespace": namespace,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "synapses": synapses,
        "transitions": transitions,
        "counts": {"synapses": len(synapses), "transitions": len(transitions)},
    }


def validate_synapse_bundle(bundle: Any) -> list[str]:
    """Structural validation for a synapse bundle. Returns error strings."""
    if not isinstance(bundle, dict):
        return ["bundle must be a JSON object"]
    errors: list[str] = []
    if bundle.get("format") != SYNAPSE_BUNDLE_FORMAT:
        errors.append(
            f"unrecognized bundle format {bundle.get('format')!r} "
            f"(expected {SYNAPSE_BUNDLE_FORMAT!r})"
        )
    version = bundle.get("version")
    if not isinstance(version, int) or version < 1:
        errors.append(f"invalid bundle version {version!r}")
    elif version > SYNAPSE_BUNDLE_VERSION:
        errors.append(
            f"bundle version {version} is newer than this NeuralMind supports "
            f"({SYNAPSE_BUNDLE_VERSION}) — upgrade neuralmind to import it"
        )
    namespace = bundle.get("namespace")
    if not isinstance(namespace, str) or not namespace.strip():
        errors.append("bundle is missing its source namespace")
    for key in ("synapses", "transitions"):
        entries = bundle.get(key, [])
        if not isinstance(entries, list):
            errors.append(f"{key!r} must be a list")
            continue
        for i, entry in enumerate(entries):
            if not isinstance(entry, dict) or not entry.get("source") or not entry.get("target"):
                errors.append(f"{key}[{i}] is missing source/target")
                continue
            weight = entry.get("weight", 0.0)
            if not isinstance(weight, (int, float)) or weight < 0:
                errors.append(f"{key}[{i}] has invalid weight {weight!r}")
    return errors


def import_synapse_bundle(
    store: Any, bundle: dict[str, Any], namespace: str | None = None
) -> dict[str, Any]:
    """Validate a bundle and merge it into a target namespace.

    The target defaults to the bundle's own namespace. Merging keeps the
    MAX of weight/count per edge (see ``SynapseStore.import_edges``), so
    re-importing a bundle is idempotent. Raises :class:`IRError` when the
    bundle fails validation — never partially imports a malformed bundle.
    """
    errors = validate_synapse_bundle(bundle)
    if errors:
        raise IRError("invalid synapse bundle: " + "; ".join(errors))
    target = namespace or str(bundle["namespace"]).strip()
    edge_rows = [
        (s["source"], s["target"], float(s.get("weight", 0.0)), int(s.get("activation_count", 1)))
        for s in bundle.get("synapses", [])
    ]
    transition_rows = [
        (t["source"], t["target"], float(t.get("weight", 0.0)), int(t.get("count", 1)))
        for t in bundle.get("transitions", [])
    ]
    return {
        "namespace": target,
        "synapses": store.import_edges(edge_rows, namespace=target),
        "transitions": store.import_transitions(transition_rows, namespace=target),
    }


# --------------------------------------------------------------------------- #
# Validation (FR5)
# --------------------------------------------------------------------------- #


@dataclass
class ValidationIssue:
    severity: str  # "error" | "warning"
    code: str
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {"severity": self.severity, "code": self.code, "message": self.message}


def validate_ir(ir: IndexIR) -> list[ValidationIssue]:
    """Report structural problems in an IR payload.

    Surfaces missing required fields, duplicate / orphaned ids, dangling edge
    endpoints, and unknown kinds/relations. Errors mean the IR is unsafe to
    index; warnings are forward-compatibility signals (a new backend emitting
    a kind this build doesn't know yet).
    """
    issues: list[ValidationIssue] = []

    if ir.ir_version not in SUPPORTED_IR_VERSIONS:
        issues.append(
            ValidationIssue(
                "error",
                "unsupported_version",
                f"ir_version {ir.ir_version} is not supported by this build "
                f"(supported: {sorted(SUPPORTED_IR_VERSIONS)}).",
            )
        )

    seen_ids: set[str] = set()
    node_ids: set[str] = set()
    for n in ir.nodes:
        if not n.id:
            issues.append(
                ValidationIssue(
                    "error", "node_missing_id", f"Node with label {n.label!r} has no id."
                )
            )
            continue
        if n.id in seen_ids:
            issues.append(
                ValidationIssue("error", "duplicate_node_id", f"Duplicate node id {n.id!r}.")
            )
        seen_ids.add(n.id)
        node_ids.add(n.id)
        if not n.label:
            issues.append(
                ValidationIssue("warning", "node_missing_label", f"Node {n.id!r} has no label.")
            )
        if n.kind not in NODE_KINDS:
            issues.append(
                ValidationIssue(
                    "warning",
                    "unknown_node_kind",
                    f"Node {n.id!r} has unknown kind {n.kind!r}.",
                )
            )

    # Edges: required endpoints + dangling references (orphaned edges).
    referenced: set[str] = set()
    for e in ir.edges:
        if not e.source or not e.target:
            issues.append(
                ValidationIssue(
                    "error",
                    "edge_missing_endpoint",
                    f"Edge {e.relation!r} is missing a source or target "
                    f"({e.source!r} → {e.target!r}).",
                )
            )
            continue
        referenced.add(e.source)
        referenced.add(e.target)
        if e.source not in node_ids:
            issues.append(
                ValidationIssue(
                    "error",
                    "dangling_edge_source",
                    f"Edge {e.relation!r} references unknown source node {e.source!r}.",
                )
            )
        if e.target not in node_ids:
            issues.append(
                ValidationIssue(
                    "error",
                    "dangling_edge_target",
                    f"Edge {e.relation!r} references unknown target node {e.target!r}.",
                )
            )
        if e.relation not in EDGE_RELATIONS:
            issues.append(
                ValidationIssue(
                    "warning",
                    "unknown_edge_relation",
                    f"Edge between {e.source!r} and {e.target!r} has unknown "
                    f"relation {e.relation!r}.",
                )
            )

    # Orphaned nodes: indexed but never connected. Not fatal (a lone module is
    # legal), but worth surfacing — it often means a resolution pass missed.
    orphaned = node_ids - referenced
    if orphaned and len(orphaned) != len(node_ids):
        # Only warn when *some* nodes are connected; an all-orphan graph is a
        # different (and louder) shape we don't want to spam one-per-node for.
        for nid in sorted(orphaned)[:50]:
            issues.append(
                ValidationIssue("warning", "orphaned_node", f"Node {nid!r} has no edges.")
            )

    # Synapses: learned associations may legitimately outlive the nodes they
    # were learned on (a file gets deleted, its memory lingers), so a synapse
    # pointing at an unknown node is a *warning* (stale), not an error — but an
    # empty endpoint is malformed.
    stale = 0
    for s in ir.synapses:
        if not s.source or not s.target:
            issues.append(
                ValidationIssue(
                    "error",
                    "synapse_missing_endpoint",
                    f"Synapse is missing a source or target ({s.source!r} → {s.target!r}).",
                )
            )
            continue
        if s.source not in node_ids or s.target not in node_ids:
            stale += 1
    if stale:
        issues.append(
            ValidationIssue(
                "warning",
                "stale_synapse",
                f"{stale} learned synapse(s) reference nodes not in the current index "
                "(memory predates a rebuild; harmless but prunable).",
            )
        )

    return issues


def has_errors(issues: list[ValidationIssue]) -> bool:
    return any(i.severity == "error" for i in issues)


def validation_summary(issues: list[ValidationIssue]) -> dict[str, Any]:
    errors = [i for i in issues if i.severity == "error"]
    warnings = [i for i in issues if i.severity == "warning"]
    return {
        "ok": not errors,
        "errors": len(errors),
        "warnings": len(warnings),
        "issues": [i.to_dict() for i in issues],
    }
