"""Optional SCIP precision pass — compiler-accurate calls/inherits edges.

The built-in tree-sitter backend (``graphgen.py``) resolves ``calls`` and
``inherits`` edges *heuristically*, by bare name: a call to ``handle()`` links
to the first project function named ``handle``, which is wrong when two classes
both define one. That's good enough to clear the parity gate, but a project
that has been indexed with a **SCIP** tool (scip-python, scip-typescript,
scip-go, …) carries *compiler-accurate* resolution we can fold in.

This module is that optional pass. Given a built graph and a SCIP index, it
**replaces** the heuristic ``calls``/``inherits`` edges for the files the index
covers with SCIP-resolved ones. Everything else — nodes, ``contains``,
``imports_from``, ``rationale``, communities — is untouched, so it slots in
behind the same ``graph.json`` seam.

**Off by default.** It runs only when ``NEURALMIND_PRECISION`` is set *and* a
``*.scip`` index is found; otherwise the graph is returned unchanged, so a
normal build is byte-for-byte what it was. SCIP is decoded with a tiny
dependency-free protobuf reader (we only read a handful of fields), so the
feature adds no runtime dependency and can't break on a protobuf-version
mismatch.

SCIP reference: https://github.com/sourcegraph/scip (`scip.proto`). Field
numbers below match that schema, so a real ``index.scip`` parses too.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# SCIP symbol-role bitmask: bit 0 (= 1) marks a *definition* occurrence; a
# reference (a use site) has the bit clear. See scip.proto SymbolRole.
_ROLE_DEFINITION = 0x1

# --------------------------------------------------------------------------- #
# Minimal protobuf wire decoder (varint + length-delimited; that's all SCIP
# needs for the fields we read). No protobuf runtime, no generated code.
# --------------------------------------------------------------------------- #
_WT_VARINT = 0
_WT_64BIT = 1
_WT_LEN = 2
_WT_32BIT = 5


def _read_varint(buf: bytes, pos: int) -> tuple[int, int]:
    result = 0
    shift = 0
    while True:
        b = buf[pos]
        pos += 1
        result |= (b & 0x7F) << shift
        if not b & 0x80:
            return result, pos
        shift += 7


def _iter_fields(buf: bytes):
    """Yield ``(field_number, wire_type, value)`` for one protobuf message.

    ``value`` is an int for varints and a ``bytes`` slice for length-delimited
    fields; 32/64-bit fields are returned as raw bytes (unused by SCIP here).
    """
    pos = 0
    n = len(buf)
    while pos < n:
        tag, pos = _read_varint(buf, pos)
        field_no = tag >> 3
        wt = tag & 0x7
        if wt == _WT_VARINT:
            val, pos = _read_varint(buf, pos)
            yield field_no, wt, val
        elif wt == _WT_LEN:
            ln, pos = _read_varint(buf, pos)
            yield field_no, wt, buf[pos : pos + ln]
            pos += ln
        elif wt == _WT_64BIT:
            yield field_no, wt, buf[pos : pos + 8]
            pos += 8
        elif wt == _WT_32BIT:
            yield field_no, wt, buf[pos : pos + 4]
            pos += 4
        else:  # pragma: no cover - malformed input
            raise ValueError(f"unknown protobuf wire type {wt}")


def _packed_varints(buf: bytes) -> list[int]:
    out: list[int] = []
    pos = 0
    while pos < len(buf):
        val, pos = _read_varint(buf, pos)
        out.append(val)
    return out


# --------------------------------------------------------------------------- #
# SCIP model (only the fields the precision pass reads)
# --------------------------------------------------------------------------- #
@dataclass
class ScipOccurrence:
    range: list[int]
    symbol: str
    symbol_roles: int
    enclosing_range: list[int] = field(default_factory=list)

    @property
    def is_definition(self) -> bool:
        return bool(self.symbol_roles & _ROLE_DEFINITION)

    @property
    def body_range(self) -> list[int]:
        """The range that encloses the symbol's body (for definitions), falling
        back to the name range when the indexer didn't emit one."""
        return self.enclosing_range or self.range


@dataclass
class ScipRelationship:
    symbol: str
    is_implementation: bool


@dataclass
class ScipSymbol:
    symbol: str
    relationships: list[ScipRelationship] = field(default_factory=list)


@dataclass
class ScipDocument:
    relative_path: str
    occurrences: list[ScipOccurrence] = field(default_factory=list)
    symbols: list[ScipSymbol] = field(default_factory=list)


@dataclass
class ScipIndex:
    documents: list[ScipDocument] = field(default_factory=list)


def _parse_occurrence(buf: bytes) -> ScipOccurrence:
    rng: list[int] = []
    enclosing: list[int] = []
    symbol = ""
    roles = 0
    for f, wt, v in _iter_fields(buf):
        if f == 1 and wt == _WT_LEN:  # range (packed int32)
            rng = _packed_varints(v)
        elif f == 1 and wt == _WT_VARINT:  # range as single field (unpacked)
            rng.append(v)
        elif f == 2 and wt == _WT_LEN:  # symbol
            symbol = v.decode("utf-8", "replace")
        elif f == 3 and wt == _WT_VARINT:  # symbol_roles
            roles = v
        elif f == 7 and wt == _WT_LEN:  # enclosing_range (packed int32)
            enclosing = _packed_varints(v)
    return ScipOccurrence(range=rng, symbol=symbol, symbol_roles=roles, enclosing_range=enclosing)


def _parse_relationship(buf: bytes) -> ScipRelationship:
    symbol = ""
    is_impl = False
    for f, wt, v in _iter_fields(buf):
        if f == 1 and wt == _WT_LEN:
            symbol = v.decode("utf-8", "replace")
        elif f == 3 and wt == _WT_VARINT:  # is_implementation
            is_impl = bool(v)
    return ScipRelationship(symbol=symbol, is_implementation=is_impl)


def _parse_symbol(buf: bytes) -> ScipSymbol:
    symbol = ""
    rels: list[ScipRelationship] = []
    for f, wt, v in _iter_fields(buf):
        if f == 1 and wt == _WT_LEN:
            symbol = v.decode("utf-8", "replace")
        elif f == 4 and wt == _WT_LEN:  # relationships
            rels.append(_parse_relationship(v))
    return ScipSymbol(symbol=symbol, relationships=rels)


def _parse_document(buf: bytes) -> ScipDocument:
    rel = ""
    occs: list[ScipOccurrence] = []
    syms: list[ScipSymbol] = []
    for f, wt, v in _iter_fields(buf):
        if f == 1 and wt == _WT_LEN:  # relative_path
            rel = v.decode("utf-8", "replace")
        elif f == 2 and wt == _WT_LEN:  # occurrences
            occs.append(_parse_occurrence(v))
        elif f == 3 and wt == _WT_LEN:  # symbols
            syms.append(_parse_symbol(v))
    return ScipDocument(relative_path=rel, occurrences=occs, symbols=syms)


def parse_scip_index(data: bytes) -> ScipIndex:
    """Decode a SCIP index (``Index`` message) — documents only (field 2)."""
    docs: list[ScipDocument] = []
    for f, wt, v in _iter_fields(data):
        if f == 2 and wt == _WT_LEN:  # documents
            docs.append(_parse_document(v))
    return ScipIndex(documents=docs)


# --------------------------------------------------------------------------- #
# Symbol → graph-node mapping
# --------------------------------------------------------------------------- #
def _parse_descriptor(symbol: str) -> tuple[str | None, str, bool]:
    """Parse a SCIP symbol into ``(enclosing_type, name, is_callable)``.

    SCIP symbols look like ``scip-python python . . app/A#handle().``. The last
    whitespace token is the descriptor path; its final segment names the symbol,
    with ``#`` separating an enclosing type from a member and ``().`` marking a
    method/function. The enclosing type matters: two classes can each define a
    ``handle`` method, so name alone is ambiguous — the class disambiguates.
    """
    s = symbol.strip()
    token = s.split()[-1] if s.split() else s
    is_callable = token.rstrip().endswith("().")
    seg = token.split("/")[-1]
    enclosing: str | None = None
    name = seg
    if "#" in seg:
        left, right = seg.rsplit("#", 1)
        if right.strip("()."):  # member of a type
            enclosing = left
            name = right
        else:  # the type itself ("A#")
            name = left
    name = name.replace("(", "").replace(")", "").strip(".").strip()
    if enclosing:
        enclosing = enclosing.split("/")[-1].strip(".").strip() or None
    return enclosing, name, is_callable


@dataclass
class RefineStats:
    """What the precision pass changed."""

    calls_added: int = 0
    inherits_added: int = 0
    heuristic_calls_removed: int = 0
    heuristic_inherits_removed: int = 0
    documents: int = 0

    def to_dict(self) -> dict:
        return {
            "calls_added": self.calls_added,
            "inherits_added": self.inherits_added,
            "heuristic_calls_removed": self.heuristic_calls_removed,
            "heuristic_inherits_removed": self.heuristic_inherits_removed,
            "documents": self.documents,
        }


def _range_contains(outer: list[int], inner: list[int]) -> bool:
    """Does SCIP range ``outer`` enclose ``inner``? Ranges are
    ``[startLine, startChar, endLine, endChar]`` (or 3-element when single-line)."""
    if len(outer) < 3 or not inner:
        return False
    o_sl, o_sc = outer[0], outer[1]
    o_el = outer[2] if len(outer) >= 4 else outer[0]
    o_ec = outer[3] if len(outer) >= 4 else outer[2]
    i_sl, i_sc = inner[0], inner[1]
    after_start = (i_sl, i_sc) >= (o_sl, o_sc)
    before_end = (i_sl, i_sc) <= (o_el, o_ec)
    return after_start and before_end


def refine_graph(graph: dict[str, Any], index: ScipIndex) -> tuple[dict[str, Any], RefineStats]:
    """Replace heuristic ``calls``/``inherits`` edges with SCIP-resolved ones,
    for the files the SCIP index covers. Returns ``(graph, stats)``.

    A defensive, additive design: only files present in the index are touched;
    a SCIP symbol that doesn't map to a known graph node is skipped (no dangling
    edges). The graph dict is mutated in place and also returned.
    """
    stats = RefineStats()
    nodes = graph.get("nodes", [])
    node_by_id = {n["id"]: n for n in nodes}

    # Parent map from ``contains`` edges (edge source = container, target =
    # child), used to recover each symbol's enclosing type: a function whose
    # parent's parent exists is a *method* of that parent class; a function
    # whose parent is the file (no grandparent) is module-level.
    parent_of: dict[str, str] = {}
    for e in graph.get("links", []):
        if e.get("relation") == "contains":
            parent_of[e["target"]] = e["source"]

    def enclosing_type(node_id: str) -> str | None:
        p = parent_of.get(node_id)
        if p is None or parent_of.get(p) is None:
            return None  # top-level (parent is the file, or no parent)
        parent = node_by_id.get(p)
        return str(parent["label"]) if parent else None

    # (source_file, enclosing_type, bare_name) → node id, for resolving SCIP
    # symbols to graph nodes (class-aware, so same-named methods don't collide).
    by_key: dict[tuple[str, str | None, str], str] = {}
    for n in nodes:
        if n.get("file_type") != "code":
            continue
        sf = n.get("source_file", "")
        bare = str(n.get("label", "")).rstrip("()")
        by_key[(sf, enclosing_type(n["id"]), bare)] = n["id"]

    def resolve(symbol: str, source_file: str) -> str | None:
        enclosing, name, _ = _parse_descriptor(symbol)
        if not name:
            return None
        hit = by_key.get((source_file, enclosing, name))
        if hit:
            return hit
        # Fall back to a name-only match anywhere (external/base symbols).
        return next((nid for (sf, _t, lbl), nid in by_key.items() if lbl == name), None)

    covered_files = {d.relative_path for d in index.documents}
    if not covered_files:
        return graph, stats

    # Global symbol → defining node id (definitions across all documents).
    sym_def: dict[str, str] = {}
    for doc in index.documents:
        for occ in doc.occurrences:
            if occ.is_definition and occ.symbol:
                node_id = resolve(occ.symbol, doc.relative_path)
                if node_id:
                    sym_def[occ.symbol] = node_id

    new_calls: list[dict[str, Any]] = []
    new_inherits: list[dict[str, Any]] = []
    for doc in index.documents:
        stats.documents += 1
        # Function-definition occurrences in this doc, with their body ranges,
        # to find which function encloses a given reference occurrence.
        fn_defs = [
            occ
            for occ in doc.occurrences
            if occ.is_definition and _parse_descriptor(occ.symbol)[2] and occ.symbol in sym_def
        ]
        # calls: a reference occurrence to a known function definition, inside a
        # function's body range → caller → callee.
        for occ in doc.occurrences:
            if occ.is_definition or not occ.symbol:
                continue
            if not _parse_descriptor(occ.symbol)[2]:  # not a callable
                continue
            callee = sym_def.get(occ.symbol)
            if not callee:
                continue
            enclosing = next(
                (fd for fd in fn_defs if _range_contains(fd.body_range, occ.range)), None
            )
            if enclosing is None:
                continue
            caller = sym_def.get(enclosing.symbol)
            if caller and caller != callee:
                new_calls.append(_edge("calls", caller, callee, doc.relative_path, occ.range))
        # inherits: SymbolInformation relationships flagged is_implementation.
        for sym in doc.symbols:
            child = resolve(sym.symbol, doc.relative_path)
            if not child:
                continue
            for rel in sym.relationships:
                if not rel.is_implementation:
                    continue
                base = resolve(rel.symbol, doc.relative_path)
                if base and base != child:
                    new_inherits.append(_edge("inherits", child, base, doc.relative_path, []))

    # Drop heuristic calls/inherits for covered files, then splice in SCIP ones.
    kept: list[dict[str, Any]] = []
    for e in graph.get("links", []):
        if e.get("relation") in ("calls", "inherits") and e.get("source_file") in covered_files:
            if e["relation"] == "calls":
                stats.heuristic_calls_removed += 1
            else:
                stats.heuristic_inherits_removed += 1
            continue
        kept.append(e)

    # De-dup the SCIP edges (same source/target/relation).
    seen: set[tuple[str, str, str]] = set()
    for e in new_calls + new_inherits:
        key = (e["relation"], e["source"], e["target"])
        if key in seen:
            continue
        seen.add(key)
        kept.append(e)
        if e["relation"] == "calls":
            stats.calls_added += 1
        else:
            stats.inherits_added += 1

    graph["links"] = kept
    graph["precision"] = "scip"
    return graph, stats


def _edge(relation: str, source: str, target: str, rel_path: str, rng: list[int]) -> dict[str, Any]:
    line = (rng[0] + 1) if rng else 1
    return {
        "relation": relation,
        "context": f"{relation} (scip)",
        "confidence": "PRECISE",
        "source_file": rel_path,
        "source_location": f"L{max(line, 1)}",
        "weight": 1.0,
        "source": source,
        "target": target,
        "confidence_score": 1.0,
    }


# --------------------------------------------------------------------------- #
# Enablement + discovery
# --------------------------------------------------------------------------- #
def is_enabled() -> bool:
    """True when the precision pass is explicitly turned on. Off by default."""
    return os.environ.get("NEURALMIND_PRECISION", "") not in ("", "0", "false", "False")


def find_scip_index(project_path: str | Path) -> Path | None:
    """Locate a SCIP index in the project root (``index.scip`` or any ``*.scip``)."""
    root = Path(project_path)
    direct = root / "index.scip"
    if direct.exists():
        return direct
    matches = sorted(root.glob("*.scip"))
    return matches[0] if matches else None


def maybe_refine(
    project_path: str | Path, graph: dict[str, Any]
) -> tuple[dict[str, Any], RefineStats | None]:
    """Apply the SCIP precision pass if enabled and an index is present.

    Returns ``(graph, stats)`` — ``stats`` is None when the pass didn't run
    (disabled or no index), so the graph is returned unchanged and a normal
    build is byte-for-byte what it was.
    """
    if not is_enabled():
        return graph, None
    index_path = find_scip_index(project_path)
    if index_path is None:
        return graph, None
    try:
        index = parse_scip_index(index_path.read_bytes())
    except Exception:
        return graph, None
    return refine_graph(graph, index)
