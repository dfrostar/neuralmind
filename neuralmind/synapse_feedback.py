"""
synapse_feedback.py — the synapse write-path
=============================================

Feedback signals that feed the associative synapse layer: file-level
co-activation from the watcher, reuse detection from Edit/Write hooks,
decay acceleration for deleted files, and Hebbian reinforcement from
queries. Extracted from ``core.py``; each function takes the
:class:`~neuralmind.core.NeuralMind` instance and operates through its
public surface (``mind.synapses``, ``mind.embedder``, ``mind.activate``),
mirroring the free-function pattern in :mod:`neuralmind.server` and
:mod:`neuralmind.self_improve`.

Stdlib-only, like the rest of the synapse layer.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .context_selector import ContextResult
    from .core import NeuralMind

# Language-agnostic identifier tokenizer for reuse detection: we never
# parse source syntax, only match bare identifiers against graph labels,
# so this works uniformly across every tree-sitter extractor.
REUSE_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")

# Graph node file_types that are prose, not symbols — their labels are
# docstrings/file paths, never identifiers, so they're excluded from the
# reuse index.
NON_SYMBOL_FILE_TYPES = frozenset({"rationale", "document"})


def symbol_name(label: str) -> str:
    """Bare identifier for a graph label ("login_endpoint()" -> "login_endpoint").

    Generated graphs label functions with signature punctuation; the code we
    tokenize yields bare identifiers, so we key the reuse index on the
    leading identifier of each label to make the two comparable.
    """
    m = REUSE_IDENT_RE.search(str(label or ""))
    return m.group(0) if m else ""


def external_symbol_index(mind: NeuralMind) -> dict[str, list[str]]:
    """Map normalized symbol name -> node ids that define it, across the graph.

    Cached on the mind instance and invalidated when the node count changes
    (build/reindex), so repeated Edit/Write feedback calls don't re-scan the
    whole graph each time — per-edit work is then ~O(#tokens), not O(#nodes).
    Edited-file ownership is filtered at match time, not here.
    """
    nodes = getattr(mind.embedder, "nodes", None) or []
    sig = len(nodes)
    cached = getattr(mind, "_symbol_index_cache", None)
    if cached is not None and getattr(mind, "_symbol_index_sig", None) == sig:
        return cached
    index: dict[str, list[str]] = {}
    for n in nodes:
        if n.get("file_type") in NON_SYMBOL_FILE_TYPES:
            continue
        nid = str(n.get("id", ""))
        if not nid:
            continue
        name = symbol_name(n.get("label", ""))
        if name:
            index.setdefault(name, []).append(nid)
    mind._symbol_index_cache = index
    mind._symbol_index_sig = sig
    return index


def activate_files(mind: NeuralMind, file_paths: list[str], strength: float = 1.0) -> int:
    """Resolve file paths to graph node ids and feed them as one batch.

    Used by the file watcher: when a cluster of files is edited together,
    we treat them as having co-fired and let the synapse store strengthen
    the edges between every node living in those files.

    Two parallel updates run from one call:

    - Undirected co-activation across every node inside the touched
      files (the existing Hebbian signal).
    - Directional file-level transitions (``A -> B``) for each
      consecutive pair in ``file_paths``, so callers can ask
      ``next_likely(file)`` for what typically follows. *(v0.11.0+)*
    """
    if not file_paths:
        return 0
    mind._ensure_built()

    store = mind.synapses
    if store is not None and len(file_paths) >= 2:
        try:
            store.record_sequence(file_paths, strength=strength)
        except Exception:
            pass

    node_ids: list[str] = []
    for path in file_paths:
        try:
            for node in mind.embedder.get_file_nodes(path):
                nid = node.get("id")
                if nid:
                    node_ids.append(str(nid))
        except Exception:
            continue
    if len(node_ids) < 2:
        return 0
    return mind.activate(node_ids, strength=strength)


def record_edit_activity(mind: NeuralMind, file_path: str, new_code: str) -> dict:
    """Learn from an Edit/Write: did the new code reuse existing symbols?

    When an agent edits ``file_path``, identifiers in ``new_code`` that
    already name a symbol defined *elsewhere* in the graph are treated as
    a **reuse** signal — the edited file and the reused definitions fired
    together in one thought, so we reinforce their synapse edges. The
    existing L2/L3 synapse boost then surfaces those reused nodes more
    readily on future queries, closing the loop between what got reused
    and what is worth remembering.

    Symbols ``new_code`` *defines* whose name also exists in another file
    are reported as possible duplication, but in this MVP that is surfaced
    only in the return value — not acted on.

    Operates on graph nodes + identifier tokens, never on source syntax,
    so it is language-agnostic. A **pure side effect**: it never triggers a
    build (only the cheap graph load via ``get_file_nodes``), and fails open
    — if the graph isn't available it returns empty rather than pay build
    cost in a hook. Writes land in the project's active namespace (same as
    ``activate``). Returns a summary dict for the hook to log and tests to
    assert on.
    """
    empty = {"reused": [], "possible_dupes": [], "pairs": 0}
    if mind.synapses is None or not file_path or not new_code:
        return empty

    # Nodes already defined in the edited file. get_file_nodes lazily loads
    # graph.json (cheap) but never embeds — so no build is forced here.
    try:
        file_nodes = mind.embedder.get_file_nodes(file_path)
    except Exception:
        file_nodes = []
    file_node_ids = {str(n.get("id")) for n in file_nodes if n.get("id")}

    index = external_symbol_index(mind)
    if not index:
        return empty

    tokens = set(REUSE_IDENT_RE.findall(new_code))

    reused_ids: list[str] = []
    reused_labels: list[str] = []
    for name in tokens & index.keys():
        ext_ids = [i for i in index[name] if i not in file_node_ids]
        if ext_ids:
            reused_ids.extend(ext_ids)
            reused_labels.append(name)

    # Possible duplication: a symbol defined in this file whose name also
    # exists in another file. Reported only (MVP does not penalize).
    possible_dupes = sorted(
        {
            name
            for n in file_nodes
            if n.get("file_type") not in NON_SYMBOL_FILE_TYPES
            and (name := symbol_name(n.get("label", ""))) in index
            and any(i not in file_node_ids for i in index[name])
        }
    )

    pairs = 0
    coactivate = list(file_node_ids) + reused_ids
    if reused_ids and len(coactivate) >= 2:
        pairs = mind.activate(coactivate, strength=mind.REUSE_FEEDBACK_STRENGTH)

    return {
        "reused": sorted(set(reused_labels)),
        "possible_dupes": possible_dupes,
        "pairs": pairs,
    }


def deactivate_files(mind: NeuralMind, file_paths: list[str]) -> int:
    """Accelerate synapse decay for nodes belonging to deleted files.

    When a file is removed from the project (rename, refactor, deletion),
    its graph nodes should lose influence quickly so they stop surfacing in
    context and spreading activation. Calls ``decay_node`` once per node
    found in the deleted files — one targeted tick is enough to sink
    non-LTP edges below the prune threshold within a few normal decay
    cycles, while LTP-protected edges (heavily-used, long-established)
    survive and fade gracefully.

    Returns the number of nodes targeted.
    """
    if not file_paths:
        return 0
    store = mind.synapses
    if store is None:
        return 0
    if not mind._built:
        return 0

    targeted = 0
    for path in file_paths:
        try:
            for node in mind.embedder.get_file_nodes(path):
                nid = node.get("id")
                if nid:
                    try:
                        store.decay_node(str(nid))
                        targeted += 1
                    except Exception:
                        pass
        except Exception:
            continue
    return targeted


def reinforce_from_query(mind: NeuralMind, question: str, result: ContextResult) -> None:
    """Hebbian update: nodes co-activated by a query wire together.

    Reuses the search hits the selector already fetched for L2/L3 so
    we don't pay for a third round trip to the embedder. Falls back
    to a fresh search only if the result didn't surface any hits
    (e.g. an L0/L1-only call).
    """
    store = mind.synapses
    if store is None:
        return
    hits = result.top_search_hits
    if not hits:
        try:
            hits = mind.embedder.search(question, n=6)
        except Exception:
            return
    node_ids: list[str] = []
    for hit in hits[:6]:
        nid = hit.get("id")
        if nid:
            node_ids.append(str(nid))
    for comm_id in result.communities_loaded or []:
        node_ids.append(f"community_{comm_id}")
    if len(node_ids) >= 2:
        try:
            store.reinforce(node_ids)
        except Exception:
            pass
