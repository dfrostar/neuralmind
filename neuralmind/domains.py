"""domains.py — Read-only domain taxonomy classifier for synapse nodes.

Labels every distinct synapse node as one of four coarse domains:

  - ``code``       programming-language artifacts (functions, classes,
                    variables, symbols, source files across 20+ languages)
  - ``document``   markdown/doc artifacts (section headings, .md files)
  - ``decision``   business-context artifacts (archives, rationale
                    annotations, community cluster ids)
  - ``unknown``    anything that does not match a known pattern (file
                    paths, uncategorized tokens)

Pure function ``classify_node(node_name: str) -> str`` is the public API.
``domain_breakdown(store)`` iterates every distinct node in a SynapseStore
and returns ``{domain: count}``.

Design: heuristic, fail-open. Every rule is grounded in observed naming
patterns from the synapse graph — no ML, no invented labels.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .synapses import SynapseStore

# --------------------------------------------------------------------------- #
# Pattern table — order matters: first match wins.
# --------------------------------------------------------------------------- #

# Document: markdown section headings (__h1, __h12, ...) or standalone .md
_DOC_HEADING_RE = re.compile(r"__h\d+$")

# Code: structural graphify suffixes (functions, classes, variables, symbols)
_CODE_SUFFIXES = frozenset({"__fn", "_fn", "__cls", "_cls", "__var", "_var"})
_CODE_SYM_RE = re.compile(r"__\w+_sym$")

# Code: source-file suffixes (underscore-separated multi-lang extensions)
_CODE_FILE_EXTS = frozenset({
    "_py", "_ts", "_tsx", "_js", "_jsx",
    "_c", "_h", "_cpp", "_hpp",
    "_cs", "_go", "_java", "_rb", "_rs", "_php",
    "_swift", "_kt", "_scala", "_lua", "_pl", "_sh",
    "_sql", "_toml", "_yaml", "_yml", "_json", "_txt",
    "_css", "_scss", "_html", "_xml",
})

# Decision: archival prefixes
_DECISION_PREFIXES = ("archive_", "decision_")

# Decision: rationale annotations (graphify attaches these to decisions)
_DECISION_RATIONALE_RE = re.compile(r"rationale")

# Decision: community cluster ids (community_<id>)
_DECISION_COMMUNITY_RE = re.compile(r"^community_-?\d+$")




def classify_node(node_name: str) -> str:
    """Label a synapse node as ``code``, ``document``, ``decision``, ``unknown``.

    Pure function — no DB access, no side effects, safe to call from any
    context (HTTP handler, CLI, test). Every rule below was derived from
    actual observed patterns in the synapse graph.
    """
    if not node_name or not isinstance(node_name, str):
        return "unknown"

    # --- Decision (prefix first — overrides suffix rules) ---------- #
    if node_name.startswith(_DECISION_PREFIXES):
        return "decision"
    if _DECISION_COMMUNITY_RE.match(node_name):
        return "decision"

    # --- Document (headings first — these are unambiguous) ---------- #
    if _DOC_HEADING_RE.search(node_name):
        return "document"
    if node_name.endswith("_md") and not node_name.startswith("archive_"):
        return "document"

    # --- Code (specific structural suffixes — check BEFORE decision's
    #     rationale rule so "foo_fn__rationale" stays code) ----------- #
    for suffix in _CODE_SUFFIXES:
        if node_name.endswith(suffix):
            return "code"
    if _CODE_SYM_RE.search(node_name):
        return "code"
    for ext in _CODE_FILE_EXTS:
        if node_name.endswith(ext):
            return "code"
    # Benchmark scripts are code (files that *run* benchmarks, not results)
    if node_name.startswith("benchmark_"):
        return "code"

    # --- Decision (rationale annotations — only after code rules) --- #
    # Standalone rationale annotations (graphify attaches these to
    # decisions; never fire on __fn/__cls/__sym nodes — handled above)
    if _DECISION_RATIONALE_RE.search(node_name):
        return "decision"

    # --- File paths (rare — recorded during transitions) ------------ #
    if node_name.startswith("/"):
        # Try to classify by real file extension
        lower = node_name.lower()
        if lower.endswith(('.py', '.ts', '.tsx', '.js', '.jsx',
                          '.c', '.h', '.cpp', '.hpp', '.cs', '.go',
                          '.java', '.rb', '.rs', '.php', '.swift',
                          '.kt', '.sql', '.sh', '.toml')):
            return "code"
        if lower.endswith(('.md', '.mdoc', '.rst', '.txt', '.doc',
                          '.docx')):
            return "document"
        return "unknown"

    return "unknown"


def distinct_nodes(store: SynapseStore) -> list[str]:
    """Return every distinct node name across all synapse tables.

    Read-only: issues a single UNION query against ``synapses``,
    ``synapse_transitions``, and ``node_activations``. No writes, no
    side effects.
    """
    with store._connect() as conn:
        cur = conn.execute("""
            SELECT DISTINCT node FROM (
                SELECT node_a AS node FROM synapses
                UNION
                SELECT node_b AS node FROM synapses
                UNION
                SELECT from_node AS node FROM synapse_transitions
                UNION
                SELECT to_node AS node FROM synapse_transitions
                UNION
                SELECT node_id AS node FROM node_activations
            )
            ORDER BY node
        """)
        return [row[0] for row in cur.fetchall()]


def domain_breakdown(store: SynapseStore) -> dict[str, int]:
    """Return ``{domain: count}`` for every distinct node in the store.

    Fail-open: if a node fails to classify, it is counted as ``unknown``
    rather than raising.
    """
    nodes = distinct_nodes(store)
    counts: Counter[str] = Counter()
    for node in nodes:
        counts[classify_node(node)] += 1
    return dict(counts)


def cross_domain_edges(store: SynapseStore) -> dict[str, int]:
    """Return ``{domain_a_domain_b: count}`` for edges spanning two domains.

    Only counts edges where *both* endpoints classify to a known domain
    (``unknown`` edges are excluded). Canonical ordering (alpha-sorted
    pair) so ``code_document`` and ``document_code`` collapse to the same
    key.
    """
    nodes = distinct_nodes(store)
    node_domain = {n: classify_node(n) for n in nodes}

    with store._connect() as conn:
        cur = conn.execute(
            "SELECT node_a, node_b FROM synapses WHERE namespace NOT IN ('shared', 'ephemeral')"
        )
        pairs = cur.fetchall()

    cross: Counter[str] = Counter()
    for a, b in pairs:
        da = node_domain.get(a, "unknown")
        db = node_domain.get(b, "unknown")
        if da == "unknown" or db == "unknown":
            continue
        if da == db:
            continue
        key = f"{min(da, db)}_{max(da, db)}"
        cross[key] += 1

    return dict(cross)
