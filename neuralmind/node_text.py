"""node_text.py — the text a graph node is embedded as
=====================================================

One definition, shared by every vector backend (turbovec, ChromaDB) so the
same node embeds the same way whichever one is in use.

A code node embeds as its qualified name, the module it lives in, and the
docstring that documents it::

    Session.send
    In module sessions
    Send a given PreparedRequest.

It used to embed as ``Entity / Type / File / Location: L512 / Community: 3 /
Normalized``: a method's class was missing (every ``save()`` embedded alike),
the docstring sat only on a separate node, and two numbers that carry no
meaning took up a third of a ~30-token text. Those numbers were also part of
the content hash, so inserting a line re-embedded every symbol below it and a
community renumbering re-embedded the whole repo. Measured on the public
benchmark and the 150-question retrieval eval (vector-only and end to end).

A docstring node embeds as the docstring alone. A document node (a markdown
heading with no body) keeps the old ``Entity: <label>`` first line; the orphan
sweeps on both backends recognise a row ``embed_nodes`` wrote by that line or
by a ``code`` / ``rationale`` file type (no ingested content row has either).
"""

from __future__ import annotations

from typing import Any

from .secret_scan import redact_if_enabled


class GraphContext:
    """What a node's text needs from the rest of the graph.

    ``parent`` maps a method to the class that contains it; ``docstring`` maps
    a symbol to the text of the rationale node that documents it.
    """

    __slots__ = ("labels", "parent", "docstring")

    def __init__(self, nodes: list[dict] | None, edges: list[dict] | None) -> None:
        self.labels = {str(n.get("id")): str(n.get("label", "")) for n in nodes or []}
        self.parent: dict[str, str] = {}
        self.docstring: dict[str, str] = {}
        for e in edges or []:
            relation = e.get("relation")
            src, dst = str(e.get("source")), str(e.get("target"))
            if relation == "contains" and _is_class_label(self.labels.get(src, "")):
                self.parent[dst] = src
            elif relation == "rationale_for":
                self.docstring.setdefault(dst, self.labels.get(src, ""))


def _is_class_label(label: str) -> bool:
    """A container that is a class: not a file (``auth.py``), not a callable."""
    return bool(label) and "." not in label and not label.endswith(")") and "/" not in label


def context_for(backend: Any) -> GraphContext:
    """The backend's :class:`GraphContext`, rebuilt when its graph changes."""
    nodes = getattr(backend, "nodes", None) or []
    edges = getattr(backend, "edges", None) or []
    cached = getattr(backend, "_node_text_ctx", None)
    if cached is not None and cached[0] is nodes and cached[1] is edges:
        hit: GraphContext = cached[2]
        return hit
    ctx = GraphContext(nodes, edges)
    try:
        backend._node_text_ctx = (nodes, edges, ctx)
    except AttributeError:  # a slotted or frozen stand-in; just don't cache
        pass
    return ctx


def module_of(source_file: str) -> str:
    """``src/requests/models.py`` → ``src.requests.models``."""
    path = source_file.replace("\\", "/")
    stem = path.rsplit(".", 1)[0] if "." in path.rsplit("/", 1)[-1] else path
    return stem.replace("/", ".")


def node_text(node: dict, ctx: GraphContext | None = None) -> str:
    """The text ``node`` is embedded and keyword-indexed as (redacted if enabled)."""
    label = str(node.get("label", node.get("id", "unknown")))
    file_type = node.get("file_type", "")
    source_file = str(node.get("source_file", "") or "")
    if file_type == "rationale":
        # A docstring is the text a behaviour question matches; on its own.
        return redact_if_enabled(label)
    if file_type == "document":
        parts = [f"Entity: {label}"]
        if source_file:
            parts.append(f"File: {source_file}")
        return redact_if_enabled("\n".join(parts))
    ctx = ctx or GraphContext([], [])
    node_id = str(node.get("id", ""))
    name = label
    cls = ctx.labels.get(ctx.parent.get(node_id, ""), "")
    if cls:
        name = f"{cls}.{label}"
    parts = [name]
    if source_file:
        parts.append(f"In module {module_of(source_file)}")
    docstring = ctx.docstring.get(node_id, "")
    if docstring:
        parts.append(docstring)
    return redact_if_enabled("\n".join(parts))
