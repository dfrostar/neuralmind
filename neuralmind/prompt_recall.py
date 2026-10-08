"""prompt_recall.py — the code a prompt is about, for the per-turn hook.

The ``prompt-submit`` hook action (Claude Code's ``UserPromptSubmit``, the
Hermes plugin's ``pre_llm_call``) adds a short block to each prompt naming the
code it concerns. It used to list only the spreading-activation neighbours of
the prompt's four nearest index nodes, as raw node ids. Three things made that
weak on a freshly built index:

- Spreading activation returns a seed's *neighbours*, never the seeds, so the
  code that matched the prompt best was never named.
- Documentation headings are often the nearest matches to a question, and on a
  fresh index their only edges lead to the other headings of the same page.
  Those filled the list, with activations as low as 0.004 shown as ``0.00``.
- Node ids (``src_click_core_py__command_cls__make_parser_fn``) aren't paths,
  so the agent still had to work out which file to open.

The block now names files, each with its matching symbols and their lines, in
up to three parts:

- **Code matching this prompt.** A docstring (rationale) node counts as the
  symbol its ``rationale_for`` edge describes. Files rank by the summed scores
  of their matching symbols, so a file with several matches outranks a single
  stray one. Test files come after the code they test unless the prompt is
  about tests: they repeat the code's vocabulary, so they often match as well
  as the code does.
- **Connected to it in the synapse graph.** Other files that the synapse
  graph links directly to the listed code, mostly code, though a doc that is
  edited with it (a runbook, say) can appear: structural edges (calls,
  imports, inheritance) on a fresh index, learned co-activation as the project
  is used. A hub's activation is damped the way :meth:`SynapseStore.spread`
  damps a hub's outgoing activation, and anything left below ``LINK_FLOOR`` of
  the strongest seed is dropped.
- **Docs:** one line naming the documentation files that match.

When none of a prompt's matches is code (a book, a docs repository, or a
question only the docs answer), its document matches are the main list
instead. Nothing here writes to the index.
"""

from __future__ import annotations

import math
import os
import re
from dataclasses import dataclass, field
from typing import Any

# Nearest index nodes to read per prompt. Documentation headings crowd the top
# of the list for many questions, so the old four often held no code at all.
SEARCH_N = 16
# Seeds for spreading activation (as before: 4), from the files listed first.
SEED_K = 4
# One hop: the code linked directly to what's listed. Two hops named the same
# expected files on every measured prompt, but a depth-2 spread from a node in
# a much co-edited file reads the edges of its ~200 neighbours: 0.44 s against
# 0.03 s at depth 1, for each prompt that seeds there (Click, 2026-10-06).
SPREAD_DEPTH = 1
# Spreading-activation results to keep, counted after hub damping and after the
# ones in files already listed are dropped: co-editing links every node in a
# file to every other, so a large listed file's own nodes would fill the list
# by themselves.
SPREAD_CANDIDATES = 256
# Nodes the graph file lacks, fetched from the index this many at a time.
FETCH_CHUNK = 64
# Linked node ids the opt-in cohesion check reads (the old list's length).
COHESION_CLUSTER = 8
MATCH_FILES = 4
LINKED_FILES = 3
DOC_FILES = 3
SYMBOLS_PER_FILE = 3
# A linked file is named for being linked; two symbols say where.
LINKED_SYMBOLS = 2
# A linked node needs at least this fraction of the strongest seed's
# activation. A structural edge passes (base weight 0.25, shared-namespace
# factor 0.5, hop decay 0.6: 0.075 of the seed), as do learned co-activation
# edges, which carry more weight. A doc heading's edge to its page (0.146:
# 0.044) doesn't, nor does an edge that has decayed to a third of its weight.
LINK_FLOOR = 0.05
LABEL_MAX = 60
# Control characters, including line and paragraph separators: a path or label
# containing one could otherwise forge extra lines in the injected block.
_CONTROL_RUN = re.compile("[\x00-\x1f\x7f-\x9f\u2028\u2029]+")
# spread() costs the walk, not the cut: read every result, then cut.
_UNCUT = 1 << 30

# The node types a graph marks code with: the built-in generator's "code", and
# the older per-symbol types (TurboVecEmbedder.SCOPE_FILTERS["code"]).
_CODE_TYPES = frozenset({"code", "function", "class", "method", "module"})
# The types that mark prose (TurboVecEmbedder.SCOPE_FILTERS["content"]). A node
# of any other type, or none, is code when its file has a code suffix, as the
# index's own code scope decides.
_PROSE_TYPES = frozenset(
    {"document", "rationale", "content", "policy", "sop", "decision", "meeting_note"}
)
_TEST_DIRS = frozenset({"test", "tests", "__tests__", "spec", "specs"})
_TEST_STEM = re.compile(r"^tests?$|^test_|_tests?$|Tests?$")
_TEST_NAME = re.compile(r"\.(test|spec)\.")
_TEST_PROMPT = re.compile(r"\b(tests?|testing|specs?|pytest|unittest)\b", re.IGNORECASE)


@dataclass
class FileRecall:
    """One file in the block, with the symbols in it that the prompt reached."""

    path: str
    score: float = 0.0
    best: float = 0.0
    symbols: list[str] = field(default_factory=list)


@dataclass
class PromptRecall:
    """What the hook injects for one prompt. Empty lists mean nothing to say."""

    similarity: float = 0.0
    matches: list[FileRecall] = field(default_factory=list)
    linked: list[FileRecall] = field(default_factory=list)
    docs: list[str] = field(default_factory=list)
    # Node ids behind ``linked``, strongest first, for the opt-in cohesion check.
    linked_ids: list[str] = field(default_factory=list)
    code: bool = True

    @property
    def count(self) -> int:
        """Files the block names."""
        return len(self.matches) + len(self.linked) + len(self.docs)


def recall(mind: Any, prompt: str) -> PromptRecall:
    """Search, then spread from the best code matches. Raises on index errors.

    ``mind`` is a loaded :class:`~neuralmind.core.NeuralMind`. ``similarity``
    is the best match's score over every node type: the value the hook's
    ``NEURALMIND_RECALL_MIN_SIMILARITY`` gate compares.
    """
    from .core import _rationale_owners, _spread_with_aliases, _synapse_node

    hits = mind.embedder.search(prompt, n=SEARCH_N)
    nodes = _node_index(mind)
    owners = _rationale_owners(mind)
    code: dict[str, float] = {}
    other: dict[str, float] = {}
    info: dict[str, dict] = {}
    # A rationale hit's own id and score, by the code node it belongs to.
    rationale_ids: dict[str, dict[str, float]] = {}
    # The raw best score: a cosine backend's can be negative.
    similarity: float | None = None
    for hit in hits or []:
        raw_id = hit.get("id")
        if not raw_id:
            continue
        score = float(hit.get("score", 0.0))
        similarity = score if similarity is None else max(similarity, score)
        node_id = _synapse_node(str(raw_id), owners)
        node = nodes.get(node_id)
        if node is None:
            node_id = str(raw_id)
            node = nodes.get(node_id) or dict(hit.get("metadata") or {})
        elif node_id != str(raw_id):
            own = rationale_ids.setdefault(node_id, {})
            own[str(raw_id)] = max(score, own.get(str(raw_id), score))
        info[node_id] = node
        bucket = code if is_code_node(node) else other
        bucket[node_id] = max(score, bucket.get(node_id, score))

    result = PromptRecall(similarity=0.0 if similarity is None else similarity, code=bool(code))
    primary, secondary = (code, other) if code else (other, {})
    tests_last = not _TEST_PROMPT.search(prompt)
    result.matches = _by_file(primary, info, MATCH_FILES, tests_last=tests_last)
    # Only the files the block lists: a match past MATCH_FILES can still be linked.
    matched = {entry.path for entry in result.matches}

    seeds = _seeds(primary, info, result.matches)
    store = getattr(mind, "synapses", None)
    if store is not None and seeds:
        # Query feedback can have learned edges on a docstring node's own id:
        # spread from it too, at its own score, without counting its symbol's
        # score twice.
        aliases = {nid: rationale_ids[nid] for nid, _ in seeds if nid in rationale_ids}
        spread = _spread_with_aliases(store, dict(seeds), aliases, depth=SPREAD_DEPTH, top_k=_UNCUT)
        floor = LINK_FLOOR * max(score for _, score in seeds)
        # Damping only lowers an activation: what starts under the floor stays there.
        ranked = _linked(store, [(nid, e) for nid, e in spread if e >= floor], floor)
        linked = _outside(mind, ranked, nodes, info, owners, matched)
        linked = _one_per_symbol(linked, owners, nodes, info)
        result.linked = _by_file(
            linked, info, LINKED_FILES, tests_last=tests_last, symbols=LINKED_SYMBOLS
        )
        # The cohesion check reads the cluster the block shows: only nodes in
        # the linked files it lists.
        listed = {entry.path for entry in result.linked}
        result.linked_ids = [nid for nid in linked if _path(info.get(nid)) in listed][
            :COHESION_CLUSTER
        ]

    shown = matched | {entry.path for entry in result.linked}
    docs = _by_file(secondary, info, DOC_FILES, shown, rank_by_best=True)
    result.docs = [entry.path for entry in docs]
    return result


def format_block(result: PromptRecall) -> str:
    """The markdown the hook injects, or '' when there is nothing to name."""
    if not result.count:
        return ""
    lines = ["## NeuralMind associative recall", ""]
    if result.matches:
        lines.append("Code matching this prompt:" if result.code else "Files matching this prompt:")
        lines.extend(_file_line(entry) for entry in result.matches)
    if result.linked:
        lines.append("Connected to it in the synapse graph:")
        lines.extend(_file_line(entry) for entry in result.linked)
    if result.docs:
        lines.append("Docs: " + ", ".join(result.docs))
    return "\n".join(lines)


def is_code_node(node: dict) -> bool:
    """Whether an index node is code: by its type, else by its file's suffix."""
    kind = node.get("file_type")
    if kind in _CODE_TYPES:
        return True
    if kind in _PROSE_TYPES:
        return False
    from .graphgen import _CODE_SUFFIXES
    from .ir import CODE_SCOPE_EXTENSIONS

    suffix = os.path.splitext(str(node.get("source_file") or ""))[1].lower()
    # The index's code scope, and every language the built-in graph parses.
    return suffix in CODE_SCOPE_EXTENSIONS or suffix in _CODE_SUFFIXES


def is_test_path(path: str) -> bool:
    """Whether ``path`` looks like a test file in the common layouts."""
    parts = path.replace("\\", "/").split("/")
    if _TEST_DIRS.intersection(part.lower() for part in parts[:-1]):
        return True
    name = parts[-1]
    return bool(_TEST_STEM.search(name.split(".")[0]) or _TEST_NAME.search(name))


def _seeds(
    scored: dict[str, float], info: dict[str, dict], files: list[FileRecall]
) -> list[tuple[str, float]]:
    """The best node of each listed file, then their next best, up to ``SEED_K``.

    Seeding from the files the block names keeps "connected to it" true of the
    code listed above it. The top nodes overall can all sit in one file, or in
    a test file listed after the code it tests.
    """
    per_file: dict[str, list[tuple[str, float]]] = {f.path: [] for f in files}
    for node_id, score in sorted(scored.items(), key=lambda kv: kv[1], reverse=True):
        nodes = per_file.get(_path(info.get(node_id)))
        if nodes is not None:
            nodes.append((node_id, score))
    best = [nodes[0] for nodes in per_file.values() if nodes]
    rest = sorted(
        (n for nodes in per_file.values() for n in nodes[1:]), key=lambda kv: kv[1], reverse=True
    )
    return (best + rest)[:SEED_K]


def _linked(store: Any, spread: list[tuple[str, float]], floor: float) -> dict[str, float]:
    """Damp the hubs among spread results, drop what's under ``floor``, strongest first."""
    from .synapses import HUB_DEGREE

    if not spread:
        return {}
    degrees = store.degrees([nid for nid, _ in spread])
    damped = [
        (nid, energy * _hub_factor(degrees.get(nid, 0), HUB_DEGREE)) for nid, energy in spread
    ]
    kept = [(nid, energy) for nid, energy in damped if energy >= floor]
    return dict(sorted(kept, key=lambda kv: kv[1], reverse=True))


def _outside(
    mind: Any,
    ranked: dict[str, float],
    nodes: dict[str, dict],
    info: dict[str, dict],
    owners: dict[str, str],
    matched: set[str],
) -> dict[str, float]:
    """The ``SPREAD_CANDIDATES`` strongest links in files the block doesn't list yet.

    A node the graph file lacks is fetched from the index, ``FETCH_CHUNK`` at a
    time and only until enough are found: a much-linked seed can reach
    thousands of nodes, and some backends look each one up separately.
    """
    from .core import _synapse_node

    items = list(ranked.items())
    kept: dict[str, float] = {}
    for start in range(0, len(items), FETCH_CHUNK):
        chunk = items[start : start + FETCH_CHUNK]
        missing = [
            nid for nid, _ in chunk if nid not in nodes and _synapse_node(nid, owners) not in nodes
        ]
        for node in _fetch(mind, missing):
            nodes[node["id"]] = node
        for nid, energy in chunk:
            # Co-editing activates a function's docstring node too: name the function.
            info.setdefault(
                nid, nodes.get(_synapse_node(nid, owners)) or nodes.get(nid) or {"id": nid}
            )
            path = _path(info[nid])
            if path and path not in matched:
                kept[nid] = energy
                if len(kept) == SPREAD_CANDIDATES:
                    return kept
    return kept


def _one_per_symbol(
    linked: dict[str, float], owners: dict[str, str], nodes: dict[str, dict], info: dict[str, dict]
) -> dict[str, float]:
    """A function and its docstring node, both linked, count once: at the higher activation.

    Query feedback reinforces raw hit ids, so both can carry edges to a seed;
    the block shows them as one symbol, and summing them would promote its file.
    """
    from .core import _synapse_node

    merged: dict[str, float] = {}
    for nid, energy in linked.items():
        owner = _synapse_node(nid, owners)
        key = owner if owner in nodes else nid
        info.setdefault(key, nodes.get(key) or info.get(nid) or {"id": key})
        merged[key] = max(energy, merged.get(key, 0.0))
    return dict(sorted(merged.items(), key=lambda kv: kv[1], reverse=True))


def _hub_factor(degree: int, hub_degree: int) -> float:
    return math.sqrt(hub_degree / degree) if degree > hub_degree else 1.0


def _by_file(
    scored: dict[str, float],
    info: dict[str, dict],
    limit: int,
    exclude: set[str] | None = None,
    *,
    tests_last: bool = False,
    rank_by_best: bool = False,
    symbols: int = SYMBOLS_PER_FILE,
) -> list[FileRecall]:
    """Group scored nodes by source file, best files first, up to ``limit``."""
    files: dict[str, FileRecall] = {}
    for node_id, score in sorted(scored.items(), key=lambda kv: kv[1], reverse=True):
        node = info.get(node_id) or {}
        path = _path(node)
        if not path or (exclude and path in exclude):
            continue
        entry = files.setdefault(path, FileRecall(path=path))
        # A cosine score can be negative: a dissimilar hit isn't evidence
        # against the file its best match is in.
        entry.score += max(score, 0.0)
        entry.best = max(entry.best, score)
        symbol = _symbol(node, path)
        if symbol and symbol not in entry.symbols and len(entry.symbols) < symbols:
            entry.symbols.append(symbol)

    def key(entry: FileRecall) -> tuple:
        rank = entry.best if rank_by_best else entry.score
        return (not (tests_last and is_test_path(entry.path)), rank)

    return sorted(files.values(), key=key, reverse=True)[:limit]


def _path(node: dict | None) -> str:
    return _one_line(str((node or {}).get("source_file") or ""))


def _one_line(text: str) -> str:
    """Control characters become one space; other whitespace is kept (a path can hold it)."""
    return _CONTROL_RUN.sub(" ", text).strip()


def _file_line(entry: FileRecall) -> str:
    if not entry.symbols:
        return f"- {entry.path}"
    return f"- {entry.path}: " + ", ".join(entry.symbols)


def _symbol(node: dict, path: str) -> str:
    """``label Lnn`` for a symbol node; '' for the node that is the file itself."""
    label = " ".join(_one_line(str(node.get("label") or "")).split())
    if not label or label == os.path.basename(path):
        return ""
    if len(label) > LABEL_MAX:
        label = label[: LABEL_MAX - 1].rstrip() + "…"
    location = _one_line(str(node.get("source_location") or ""))
    return f"{label} {location}" if location.startswith("L") else label


def _node_index(mind: Any) -> dict[str, dict]:
    """The loaded graph's nodes by id (the hook has already loaded the graph)."""
    nodes = getattr(mind.embedder, "nodes", None) or []
    return {str(n["id"]): n for n in nodes if isinstance(n, dict) and n.get("id")}


def _fetch(mind: Any, node_ids: list[str]) -> list[dict]:
    """Nodes the graph file doesn't hold (ingested content), from the vector store."""
    if not node_ids:
        return []
    try:
        fetched = mind.embedder.get_nodes_by_ids(node_ids)
    except Exception:
        return []
    return [{"id": f["id"], **(f.get("metadata") or {})} for f in fetched if f.get("id")]
