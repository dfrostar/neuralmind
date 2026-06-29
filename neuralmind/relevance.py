"""
relevance.py — structured relevance sidecar for downstream tools
================================================================

NeuralMind already computes, per retrieved node, three relevance signals:
a vector similarity ``score``, a learned ``_synapse_boost``, and a
``_synapse_recalled`` flag (see ``context_selector``). The ranked context
*string* renders these as prose ("score: 0.87 (+0.15 synapse) [recalled]"),
which is fine for the model but opaque to a downstream tool.

A compression proxy (e.g. Headroom) deciding which spans are load-bearing
needs that signal as **structured, parseable metadata** it can re-associate
with the payload regardless of pipeline order. ``build_relevance_sidecar``
turns ``ContextResult.top_search_hits`` into exactly that block, keyed by
source file, with best-effort line spans pulled from the graph.

The sidecar is intentionally backend-agnostic: it reads the scores already
attached to each hit, so it works identically across the turbovec, ONNX, and
ChromaDB backends.
"""

from __future__ import annotations

from typing import Any

# Bump when the wire shape changes so consumers can guard on it. Stable
# ``files{}`` / ``node_id`` keys let a tool running *after* NeuralMind
# re-attach the signal even if the payload was reordered or recompressed.
SIDECAR_VERSION = 1


def _line_of(node: dict) -> int | None:
    """Parse a node's start line from its ``source_location`` ("L42")."""
    loc = str(node.get("source_location", "") or "")
    if loc.startswith("L"):
        try:
            return int(loc[1:])
        except ValueError:
            return None
    return None


def _file_line_spans(mind, source_file: str) -> dict[str, list[int]]:
    """Best-effort map ``node_id -> [start, end]`` line span for a file.

    Start comes from the node's ``source_location``; end is approximated as
    the next code node's start minus one (definitions are contiguous enough
    for span protection). Returns ``{}`` on any failure so callers simply
    omit ``lines`` rather than crash.
    """
    try:
        nodes = mind.embedder.get_file_nodes(source_file)
    except Exception:
        return {}
    code: list[tuple[int, str]] = []
    for n in nodes:
        start = _line_of(n)
        nid = str(n.get("id", ""))
        if start is not None and nid:
            code.append((start, nid))
    code.sort()
    spans: dict[str, list[int]] = {}
    for i, (start, nid) in enumerate(code):
        end = code[i + 1][0] - 1 if i + 1 < len(code) else start
        spans[nid] = [start, max(start, end)]
    return spans


def build_relevance_sidecar(top_search_hits: list[dict] | None, mind: Any = None) -> dict:
    """Build a structured relevance block keyed by source file.

    Shape::

        {
          "version": 1,
          "files": {
            "<source_file>": {
              "max_score": float,
              "nodes": [
                {"node_id", "label", "score", "synapse_boost",
                 "recalled", "lines": [start, end]?}  # lines omitted if unknown
              ]
            }
          }
        }

    Args:
        top_search_hits: ``ContextResult.top_search_hits`` — raw ranked hits,
            each carrying ``score``, ``_synapse_boost``, ``_synapse_recalled``
            and ``metadata{label, source_file, node_id}``.
        mind: optional ``NeuralMind`` used to resolve line spans from the
            graph. When ``None`` (or lookup fails) ``lines`` is omitted and a
            consumer falls back to file-level protection.

    Returns:
        The relevance block (always at least ``{"version", "files": {}}``).
    """
    files: dict[str, dict] = {}
    line_cache: dict[str, dict[str, list[int]]] = {}

    def _lines_for(source_file: str, node_id: str) -> list[int] | None:
        if mind is None or not source_file or not node_id:
            return None
        if source_file not in line_cache:
            line_cache[source_file] = _file_line_spans(mind, source_file)
        return line_cache[source_file].get(str(node_id))

    for hit in top_search_hits or []:
        meta = hit.get("metadata") or {}
        source_file = meta.get("source_file") or hit.get("source_file") or ""
        if not source_file:
            continue
        node_id = meta.get("node_id") or hit.get("id") or ""
        label = meta.get("label") or hit.get("label") or ""
        score = round(float(hit.get("score", 0.0) or 0.0), 4)
        boost = round(float(hit.get("_synapse_boost", 0.0) or 0.0), 4)
        recalled = bool(hit.get("_synapse_recalled", False))

        entry = files.setdefault(source_file, {"max_score": 0.0, "nodes": []})
        node = {
            "node_id": str(node_id),
            "label": str(label),
            "score": score,
            "synapse_boost": boost,
            "recalled": recalled,
        }
        lines = _lines_for(source_file, node_id)
        if lines:
            node["lines"] = lines
        entry["nodes"].append(node)
        if score > entry["max_score"]:
            entry["max_score"] = score

    return {"version": SIDECAR_VERSION, "files": files}
