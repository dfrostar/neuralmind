"""Built-in tree-sitter graph backend — emit graphify-compatible ``graph.json``.

The entire NeuralMind retrieval stack (``embedder`` → ``context_selector`` →
communities → synapses → graph-view server) consumes graphify's
``graphify-out/graph.json``: a NetworkX node-link document of symbol-level
``code`` nodes (files, classes, functions/methods) joined by ``contains`` /
``calls`` / ``imports_from`` / ``inherits`` edges, plus a docstring-derived
``rationale`` layer (``rationale_for`` edges).

This module reproduces that contract from a pure `tree-sitter` parse of a
Python project, so ``neuralmind build`` works on ``pip install neuralmind``
alone — no separate graphify clone/install. Everything downstream is unchanged:
we only replace the *graph producer*.

Design notes:
- **Pure Python + tree-sitter** (no networkx). A lightweight, deterministic
  label-propagation pass stands in for graphify's community clustering.
- **Ids need only be internally consistent**, not byte-identical to graphify:
  edges reference the ids we mint, the embedder uses them as ChromaDB ids, and
  the selector matches on them. So we are free to choose a stable id scheme.
- **Parity with graphify is *measured*, not asserted** — the faithfulness eval
  (`evals/faithfulness`) and the self-benchmark are the gate that says whether
  a code-only-plus-docstring graph holds up against graphify's richer one.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Any

# Mirrors neuralmind.watcher.DEFAULT_IGNORES — directories we never descend.
_DEFAULT_IGNORES: frozenset[str] = frozenset(
    {
        ".git",
        ".neuralmind",
        "graphify-out",
        "__pycache__",
        "node_modules",
        ".venv",
        "venv",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "dist",
        "build",
    }
)

_SLUG_RE = re.compile(r"[^a-zA-Z0-9]+")


def is_available() -> bool:
    """True when the tree-sitter Python stack is importable."""
    try:
        import tree_sitter  # noqa: F401
        import tree_sitter_python  # noqa: F401
    except Exception:
        return False
    return True


def _slug(text: str) -> str:
    """Stable id fragment: collapse non-alphanumerics to single underscores."""
    return _SLUG_RE.sub("_", text).strip("_").lower()


def _make_parser():
    """Construct a tree-sitter Parser bound to the Python grammar.

    Tolerant of the API churn between tree-sitter 0.21 and 0.23+.
    """
    import tree_sitter_python as tspython
    from tree_sitter import Language, Parser

    lang = Language(tspython.language())
    try:
        return Parser(lang)  # tree-sitter >= 0.23
    except TypeError:
        parser = Parser()
        try:
            parser.set_language(lang)  # tree-sitter 0.21
        except AttributeError:
            parser.language = lang
        return parser


def _iter_py_files(root: Path, ignores: frozenset[str]) -> list[Path]:
    """All ``*.py`` files under ``root``, skipping ignored directories."""
    out: list[Path] = []

    def walk(d: Path) -> None:
        try:
            entries = sorted(d.iterdir(), key=lambda p: p.name)
        except (OSError, PermissionError):
            return
        for p in entries:
            if p.name in ignores or p.name.startswith("."):
                # Always allow .py files even if dotfile-named (rare); skip
                # dot-directories and ignored names.
                if p.is_dir():
                    continue
            if p.is_dir():
                if p.name not in ignores:
                    walk(p)
            elif p.suffix == ".py":
                out.append(p)

    walk(root)
    return out


def _node_text(node, src: bytes) -> str:
    return src[node.start_byte : node.end_byte].decode("utf-8", "replace")


def _docstring(body_node, src: bytes) -> str | None:
    """First-statement string literal of a block/module → its first line."""
    if body_node is None:
        return None
    for child in body_node.named_children:
        if child.type == "expression_statement" and child.named_child_count:
            inner = child.named_children[0]
            if inner.type == "string":
                raw = _node_text(inner, src)
                text = raw.strip().strip("\"'").strip()
                # Strip leftover triple-quote remnants and take first line.
                text = text.lstrip("\"'").strip()
                first = next((ln.strip() for ln in text.splitlines() if ln.strip()), "")
                return first or None
        # Only the very first statement can be a docstring.
        break
    return None


class _GraphBuilder:
    """Accumulates nodes/edges for one project, then assembles ``graph.json``."""

    def __init__(self) -> None:
        self.nodes: dict[str, dict[str, Any]] = {}
        self.edges: list[dict[str, Any]] = []
        # name → set of node ids, for best-effort call/inherit resolution.
        self.func_by_name: dict[str, list[str]] = {}
        self.class_by_name: dict[str, list[str]] = {}
        # relpath-without-ext (dotted) → file node id, for import resolution.
        self.file_by_module: dict[str, str] = {}

    # -- node/edge helpers ------------------------------------------------- #
    def add_node(
        self,
        node_id: str,
        label: str,
        file_type: str,
        source_file: str,
        line: int,
    ) -> None:
        if node_id in self.nodes:
            return
        self.nodes[node_id] = {
            "label": label,
            "file_type": file_type,
            "source_file": source_file,
            "source_location": f"L{max(line, 1)}",
            "id": node_id,
            "community": -1,
            "norm_label": label.lower(),
        }

    def add_edge(
        self,
        relation: str,
        source: str,
        target: str,
        source_file: str,
        line: int,
        context: str = "",
    ) -> None:
        self.edges.append(
            {
                "relation": relation,
                "context": context or relation,
                "confidence": "EXTRACTED",
                "source_file": source_file,
                "source_location": f"L{max(line, 1)}",
                "weight": 1.0,
                "source": source,
                "target": target,
                "confidence_score": 1.0,
            }
        )


def _module_dotted(rel: str) -> str:
    """``users/crud.py`` → ``users.crud``; ``a/__init__.py`` → ``a``."""
    no_ext = rel[:-3] if rel.endswith(".py") else rel
    parts = [p for p in no_ext.split("/") if p]
    if parts and parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def build_graph(project_path: str | Path, *, commit: str = "") -> dict[str, Any]:
    """Parse ``project_path`` and return a graphify-compatible graph dict.

    Raises ``RuntimeError`` if the tree-sitter Python stack is unavailable.
    """
    if not is_available():
        raise RuntimeError(
            "the built-in graph backend needs tree-sitter — "
            "`pip install tree-sitter tree-sitter-python` (bundled with neuralmind)."
        )

    root = Path(project_path).resolve()
    parser = _make_parser()
    b = _GraphBuilder()

    files = _iter_py_files(root, _DEFAULT_IGNORES)

    # ---- pass 1: nodes (files, classes, functions/methods) + structure ---- #
    for fpath in files:
        rel = fpath.relative_to(root).as_posix()
        try:
            src = fpath.read_bytes()
        except OSError:
            continue
        tree = parser.parse(src)
        file_id = _slug(rel)
        b.add_node(file_id, fpath.name, "code", rel, 1)
        b.file_by_module[_module_dotted(rel)] = file_id

        # module docstring → rationale
        mod_doc = _docstring(tree.root_node, src)
        if mod_doc:
            rid = f"{file_id}__rationale"
            b.add_node(rid, mod_doc, "rationale", rel, 1)
            b.add_edge("rationale_for", rid, file_id, rel, 1)

        _walk_top_level(b, tree.root_node, src, rel, file_id)

    # ---- pass 2: cross-symbol edges (inherits, imports, calls) ------------ #
    for fpath in files:
        rel = fpath.relative_to(root).as_posix()
        try:
            src = fpath.read_bytes()
        except OSError:
            continue
        tree = parser.parse(src)
        file_id = _slug(rel)
        _resolve_imports(b, tree.root_node, src, rel, file_id)
        _resolve_inherits(b, tree.root_node, src, rel)
        _resolve_calls(b, tree.root_node, src, rel)

    # ---- communities (label propagation) ---------------------------------- #
    communities = _detect_communities(list(b.nodes), b.edges)
    for nid, comm in communities.items():
        b.nodes[nid]["community"] = comm

    return {
        "directed": False,
        "multigraph": False,
        "graph": {},
        "nodes": list(b.nodes.values()),
        "links": b.edges,
        "hyperedges": [],
        "built_at_commit": commit,
        "generated_by": "neuralmind.graphgen (tree-sitter)",
    }


def _walk_top_level(b: _GraphBuilder, root_node, src: bytes, rel: str, file_id: str) -> None:
    """Emit class/function nodes + contains edges for one file."""
    for child in root_node.named_children:
        if child.type == "function_definition":
            _emit_function(b, child, src, rel, file_id, container=file_id)
        elif child.type == "class_definition":
            _emit_class(b, child, src, rel, file_id)
        elif child.type == "decorated_definition":
            inner = child.child_by_field_name("definition")
            if inner is None:
                continue
            if inner.type == "function_definition":
                _emit_function(b, inner, src, rel, file_id, container=file_id)
            elif inner.type == "class_definition":
                _emit_class(b, inner, src, rel, file_id)


def _name_of(defn_node, src: bytes) -> str | None:
    name_node = defn_node.child_by_field_name("name")
    return _node_text(name_node, src) if name_node is not None else None


def _emit_function(
    b: _GraphBuilder, fn_node, src: bytes, rel: str, file_id: str, *, container: str
) -> str | None:
    name = _name_of(fn_node, src)
    if not name:
        return None
    line = fn_node.start_point[0] + 1
    fid = f"{container}__{_slug(name)}_fn"
    b.add_node(fid, f"{name}()", "code", rel, line)
    b.func_by_name.setdefault(name, []).append(fid)
    b.add_edge("contains", container, fid, rel, line)
    doc = _docstring(fn_node.child_by_field_name("body"), src)
    if doc:
        rid = f"{fid}__rationale"
        b.add_node(rid, doc, "rationale", rel, line)
        b.add_edge("rationale_for", rid, fid, rel, line)
    return fid


def _emit_class(b: _GraphBuilder, cls_node, src: bytes, rel: str, file_id: str) -> None:
    name = _name_of(cls_node, src)
    if not name:
        return
    line = cls_node.start_point[0] + 1
    cid = f"{file_id}__{_slug(name)}_cls"
    b.add_node(cid, name, "code", rel, line)
    b.class_by_name.setdefault(name, []).append(cid)
    b.add_edge("contains", file_id, cid, rel, line)
    doc = _docstring(cls_node.child_by_field_name("body"), src)
    if doc:
        rid = f"{cid}__rationale"
        b.add_node(rid, doc, "rationale", rel, line)
        b.add_edge("rationale_for", rid, cid, rel, line)
    body = cls_node.child_by_field_name("body")
    if body is None:
        return
    for member in body.named_children:
        fn = member
        if member.type == "decorated_definition":
            fn = member.child_by_field_name("definition")
        if fn is not None and fn.type == "function_definition":
            _emit_function(b, fn, src, rel, file_id, container=cid)


def _resolve_imports(b: _GraphBuilder, root_node, src: bytes, rel: str, file_id: str) -> None:
    """`from x.y import ...` / `import x.y` → imports_from edges within project."""
    for child in root_node.named_children:
        module_dotted = None
        if child.type == "import_from_statement":
            mod = child.child_by_field_name("module_name")
            if mod is not None:
                module_dotted = _node_text(mod, src).lstrip(".")
        elif child.type == "import_statement":
            for n in child.named_children:
                if n.type in ("dotted_name", "aliased_import"):
                    base = n.child_by_field_name("name") if n.type == "aliased_import" else n
                    module_dotted = _node_text(base, src) if base is not None else None
                    break
        if not module_dotted:
            continue
        target = b.file_by_module.get(module_dotted)
        if target is None:
            # try package __init__ match: a.b -> a/b/__init__.py registered as a.b
            target = b.file_by_module.get(module_dotted.rstrip("."))
        if target and target != file_id:
            b.add_edge(
                "imports_from", file_id, target, rel, child.start_point[0] + 1, context="import"
            )


def _resolve_inherits(b: _GraphBuilder, root_node, src: bytes, rel: str) -> None:
    """class Foo(Base): → inherits edge Foo → Base when Base is known."""

    def visit(node, file_id: str) -> None:
        for child in node.named_children:
            target_defn = child
            if child.type == "decorated_definition":
                target_defn = child.child_by_field_name("definition")
            if target_defn is not None and target_defn.type == "class_definition":
                name = _name_of(target_defn, src)
                supers = target_defn.child_by_field_name("superclasses")
                if name and supers is not None:
                    cid_candidates = b.class_by_name.get(name, [])
                    cid = next((c for c in cid_candidates if c.startswith(file_id)), None)
                    if cid:
                        for arg in supers.named_children:
                            base = _node_text(arg, src).split(".")[-1].split("[")[0].strip()
                            for base_id in b.class_by_name.get(base, []):
                                b.add_edge(
                                    "inherits", cid, base_id, rel, target_defn.start_point[0] + 1
                                )
            if target_defn is not None and target_defn.type in (
                "class_definition",
                "function_definition",
            ):
                body = target_defn.child_by_field_name("body")
                if body is not None:
                    visit(body, file_id)

    visit(root_node, _slug(rel))


def _resolve_calls(b: _GraphBuilder, root_node, src: bytes, rel: str) -> None:
    """Best-effort call edges: each function's body → callees by bare name.

    No scope/type resolution — a callee name that uniquely (or first) matches a
    project function node yields one ``calls`` edge. Imperfect by design; the
    eval measures whether this is good enough vs graphify's resolved calls.
    """
    file_id = _slug(rel)

    def enclosing_fn_id(name: str | None, container: str) -> str | None:
        if not name:
            return None
        cands = b.func_by_name.get(name, [])
        return next((c for c in cands if c.startswith(container)), cands[0] if cands else None)

    def visit(node, current_fn: str | None) -> None:
        for child in node.named_children:
            if child.type == "function_definition":
                fname = _name_of(child, src)
                fid = enclosing_fn_id(fname, file_id)
                body = child.child_by_field_name("body")
                if body is not None:
                    visit(body, fid)
                continue
            if child.type == "call" and current_fn is not None:
                fn_field = child.child_by_field_name("function")
                if fn_field is not None:
                    callee = _node_text(fn_field, src).split(".")[-1].strip()
                    for target in b.func_by_name.get(callee, []):
                        if target != current_fn:
                            b.add_edge("calls", current_fn, target, rel, child.start_point[0] + 1)
                            break
            visit(child, current_fn)

    visit(root_node, None)


def _detect_communities(node_ids: list[str], edges: list[dict[str, Any]]) -> dict[str, int]:
    """Deterministic label propagation over the undirected edge graph.

    A dependency-free stand-in for graphify's clustering: each node starts in
    its own community and iteratively adopts the most common label among its
    neighbours (ties broken by lowest label, scanning in sorted id order for
    reproducibility). Final labels are renumbered to a dense ``0..k`` range.
    """
    adj: dict[str, set[str]] = {nid: set() for nid in node_ids}
    for e in edges:
        s, t = e["source"], e["target"]
        if s in adj and t in adj and s != t:
            adj[s].add(t)
            adj[t].add(s)

    labels = {nid: i for i, nid in enumerate(sorted(node_ids))}
    order = sorted(node_ids)
    for _ in range(20):
        changed = False
        for nid in order:
            nbrs = adj[nid]
            if not nbrs:
                continue
            counts = Counter(labels[n] for n in nbrs)
            best = min(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0]
            if labels[nid] != best:
                labels[nid] = best
                changed = True
        if not changed:
            break

    remap: dict[int, int] = {}
    for nid in sorted(node_ids):
        lab = labels[nid]
        if lab not in remap:
            remap[lab] = len(remap)
        labels[nid] = remap[lab]
    return labels


def write_graph(project_path: str | Path, *, commit: str = "") -> Path:
    """Build the graph and write ``<project>/graphify-out/graph.json``.

    Returns the path written. Mirrors the location graphify uses so the rest of
    the stack finds it with no configuration.
    """
    import json

    root = Path(project_path)
    graph = build_graph(root, commit=commit)
    out_dir = root / "graphify-out"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "graph.json"
    out_path.write_text(json.dumps(graph, indent=2), encoding="utf-8")
    return out_path
