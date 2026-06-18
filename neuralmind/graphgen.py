"""Built-in tree-sitter graph backend — emit graphify-compatible ``graph.json``.

The entire NeuralMind retrieval stack (``embedder`` → ``context_selector`` →
communities → synapses → graph-view server) consumes graphify's
``graphify-out/graph.json``: a NetworkX node-link document of symbol-level
``code`` nodes (files, classes, functions/methods) joined by ``contains`` /
``calls`` / ``imports_from`` / ``inherits`` edges, plus a docstring-derived
``rationale`` layer (``rationale_for`` edges).

This module reproduces that contract from a pure `tree-sitter` parse, so
``neuralmind build`` works on ``pip install neuralmind`` alone — no separate
graphify clone/install. Everything downstream is unchanged: we only replace the
*graph producer*.

Multi-language: each file is dispatched by suffix (``_SUFFIX_LANG``) to a
per-language extractor (``_EXTRACTORS``). Python, TypeScript, Go, and Rust ship
today, each mapping its grammar's node types onto the same node/edge model;
registering another grammar adds a language with no change downstream of
``graph.json``.

Design notes:
- **Pure Python + tree-sitter** (no networkx). Balanced per-file communities
  stand in for graphify's modularity clustering.
- **Ids need only be internally consistent**, not byte-identical to graphify:
  edges reference the ids we mint, the embedder uses them as ChromaDB ids, and
  the selector matches on them. So we are free to choose a stable id scheme.
- **Parity with graphify is *measured*, not asserted** — the faithfulness eval
  (`evals/faithfulness`) + self-benchmark gate Python, and a per-language
  structural symbol-coverage check gates TypeScript, Go, and Rust
  (`evals/parity`).
"""

from __future__ import annotations

import re
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
        # Rust build output (analogous to node_modules/dist/build).
        "target",
    }
)

_SLUG_RE = re.compile(r"[^a-zA-Z0-9]+")

# Bumped when the emitted graph.json contract changes (new node/edge kinds,
# field semantics). v1 = symbol-level code nodes + contains/calls/imports_from/
# inherits + docstring rationale, graphify-compatible.
SCHEMA_VERSION = 1

# Suffix → tree-sitter language. The walk dispatches per file to the matching
# extractor, so adding a grammar is additive — no re-architecting. Python ships
# first; TypeScript, Go, and Rust are registered here behind the same seam.
_SUFFIX_LANG: dict[str, str] = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".go": "go",
    ".rs": "rust",
}

SUPPORTED_SUFFIXES: frozenset[str] = frozenset(_SUFFIX_LANG)

# Markdown files become graphify-style ``document`` nodes (the file plus one
# node per heading). This mirrors graphify's document layer, which the context
# selector surfaces in L0/L1/L2 — prose that carries query-relevant facts the
# code symbols alone don't (architecture notes, "why", endpoint descriptions).
_DOC_SUFFIXES: frozenset[str] = frozenset({".md", ".markdown"})


def _load_language(name: str):
    """Return the tree-sitter ``Language`` for ``name``, or None if its grammar
    package isn't importable. Only Python is a hard dependency; TS/Go grammars
    are optional and a project is parsed only for the languages present."""
    from tree_sitter import Language

    try:
        if name == "python":
            import tree_sitter_python as ts

            return Language(ts.language())
        if name == "typescript":
            import tree_sitter_typescript as ts

            return Language(ts.language_typescript())
        if name == "go":
            import tree_sitter_go as ts

            return Language(ts.language())
        if name == "rust":
            import tree_sitter_rust as ts

            return Language(ts.language())
    except Exception:
        return None
    return None


def is_available() -> bool:
    """True when the core tree-sitter Python stack is importable.

    Python is the bundled baseline backend; TypeScript/Go grammars are optional
    and checked per-file at build time, so their absence never blocks a build.
    """
    try:
        import tree_sitter  # noqa: F401
        import tree_sitter_python  # noqa: F401
    except Exception:
        return False
    return True


def language_available(name: str) -> bool:
    """True when ``name``'s tree-sitter grammar is importable."""
    return _load_language(name) is not None


def _slug(text: str) -> str:
    """Stable id fragment: collapse non-alphanumerics to single underscores."""
    return _SLUG_RE.sub("_", text).strip("_").lower()


def _make_parser(language: str = "python"):
    """Construct a tree-sitter Parser bound to ``language``'s grammar.

    Tolerant of the API churn between tree-sitter 0.21 and 0.23+. Raises
    ``RuntimeError`` if the requested grammar isn't installed.
    """
    from tree_sitter import Parser

    lang = _load_language(language)
    if lang is None:
        raise RuntimeError(f"tree-sitter grammar for {language!r} is not installed")
    try:
        return Parser(lang)  # tree-sitter >= 0.23
    except TypeError:
        parser = Parser()
        try:
            parser.set_language(lang)  # tree-sitter 0.21
        except AttributeError:
            parser.language = lang
        return parser


def _iter_files(root: Path, ignores: frozenset[str], suffixes: frozenset[str]) -> list[Path]:
    """All files under ``root`` with a suffix in ``suffixes``, skipping ignores."""
    out: list[Path] = []

    def walk(d: Path) -> None:
        try:
            entries = sorted(d.iterdir(), key=lambda p: p.name)
        except (OSError, PermissionError):
            return
        for p in entries:
            if p.name in ignores or p.name.startswith("."):
                # Skip dot-directories and ignored names; files matching a
                # wanted suffix still pass below even if dotfile-named (rare).
                if p.is_dir():
                    continue
            if p.is_dir():
                if p.name not in ignores:
                    walk(p)
            elif p.suffix in suffixes:
                out.append(p)

    walk(root)
    return out


def _iter_source_files(root: Path, ignores: frozenset[str]) -> list[Path]:
    """All supported code source files under ``root``."""
    return _iter_files(root, ignores, SUPPORTED_SUFFIXES)


def _node_text(node, src: bytes) -> str:
    return src[node.start_byte : node.end_byte].decode("utf-8", "replace")


# Cap on the rationale text pulled from a docstring. Wide enough to keep the
# summary line *and* the descriptive body sentences that carry query-relevant
# facts (what a function looks up, verifies, returns) — these are the phrases
# retrieval scores against — but bounded so the rationale layer stays cheap.
_RATIONALE_MAX_CHARS = 200


def _docstring(body_node, src: bytes) -> str | None:
    """First-statement string literal of a block/module → its rationale text.

    Returns the docstring collapsed to a single line (the summary plus the
    descriptive body), capped at ``_RATIONALE_MAX_CHARS``. Keeping the body —
    not just the first line — matters: the facts a query asks about ("looks the
    user up by email", "verifies the password hash") live there, and the
    context selector surfaces rationale nodes by exactly that text.
    """
    if body_node is None:
        return None
    for child in body_node.named_children:
        if child.type == "expression_statement" and child.named_child_count:
            inner = child.named_children[0]
            if inner.type == "string":
                raw = _node_text(inner, src)
                text = raw.strip().strip("\"'").strip()
                # Strip leftover triple-quote remnants, then collapse all
                # whitespace (newlines, indentation) to single spaces.
                text = text.lstrip("\"'").strip()
                collapsed = " ".join(text.split())
                if not collapsed:
                    return None
                if len(collapsed) > _RATIONALE_MAX_CHARS:
                    collapsed = collapsed[:_RATIONALE_MAX_CHARS].rstrip()
                return collapsed
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
        # relpath-without-ext (dotted/posix) → file node id, for import
        # resolution (Python dotted module, TS relative module key).
        self.file_by_module: dict[str, str] = {}
        # Go package directory's last segment → file node ids in it (Go imports
        # a package/dir, not a single file).
        self.go_pkg_files: dict[str, list[str]] = {}

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


_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")


def _extract_markdown(b: _GraphBuilder, md_path: Path, rel: str) -> None:
    """Emit a ``document`` node for a markdown file plus one per heading.

    Headings become the document layer's searchable labels — they're the
    prose anchors graphify exposes and the selector folds into L1/L2 (e.g.
    "Why this fixture?", "POST /api/auth/login"). The file node anchors them
    with a ``contains`` edge, mirroring code files' structure.
    """
    try:
        text = md_path.read_text(encoding="utf-8")
    except OSError:
        return
    file_id = _slug(rel)
    b.add_node(file_id, md_path.name, "document", rel, 1)

    in_fence = False
    for i, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        # Don't treat '#' inside fenced code blocks as headings.
        if stripped.startswith(("```", "~~~")):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        m = _HEADING_RE.match(line)
        if not m:
            continue
        heading = m.group(2).strip()
        if not heading:
            continue
        hid = f"{file_id}__h{i}"
        b.add_node(hid, heading, "document", rel, i)
        b.add_edge("contains", file_id, hid, rel, i)


def _assign_communities(b: _GraphBuilder) -> None:
    """Assign each node a community keyed by its source file.

    A deterministic stand-in for graphify's modularity clustering. Grouping a
    file's symbols (+ its rationale/document children) into one community gives
    balanced, feature-aligned clusters — which is what the context selector's
    L1 summary and L2 "relevant areas" actually read. The previous
    label-propagation pass collapsed almost every node into a single giant
    community on these small, densely-connected code graphs, starving both
    layers of signal; per-file grouping fixes that without networkx.
    """
    files_sorted = sorted({n["source_file"] for n in b.nodes.values()})
    comm_of_file = {f: i for i, f in enumerate(files_sorted)}
    for node in b.nodes.values():
        node["community"] = comm_of_file[node["source_file"]]


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
    b = _GraphBuilder()

    files = _iter_source_files(root, _DEFAULT_IGNORES)

    # Group files by language and process each with its own extractor. A
    # language whose grammar isn't installed is skipped (Python is the only
    # hard dependency), so a missing TS/Go grammar degrades gracefully rather
    # than failing the whole build.
    by_lang: dict[str, list[Path]] = {}
    for fpath in files:
        lang = _SUFFIX_LANG.get(fpath.suffix)
        if lang:
            by_lang.setdefault(lang, []).append(fpath)

    for lang in sorted(by_lang):
        spec = _EXTRACTORS.get(lang)
        if spec is None or not language_available(lang):
            continue
        extract_symbols, resolve_edges = spec
        parser = _make_parser(lang)

        parsed: list[tuple[str, bytes, Any]] = []
        for fpath in by_lang[lang]:
            rel = fpath.relative_to(root).as_posix()
            try:
                src = fpath.read_bytes()
            except OSError:
                continue
            tree = parser.parse(src)
            file_id = _slug(rel)
            b.add_node(file_id, fpath.name, "code", rel, 1)
            parsed.append((rel, src, tree))
            # pass 1: file-level + symbol nodes (+ module-key registration).
            extract_symbols(b, tree.root_node, src, rel, file_id)

        # pass 2: cross-symbol edges (imports/inherits/calls), once every
        # file's symbols + module keys are registered.
        for rel, src, tree in parsed:
            resolve_edges(b, tree.root_node, src, rel, _slug(rel))

    # ---- markdown → document nodes ---------------------------------------- #
    for md_path in _iter_files(root, _DEFAULT_IGNORES, _DOC_SUFFIXES):
        _extract_markdown(b, md_path, md_path.relative_to(root).as_posix())

    # ---- communities (per-file, balanced) --------------------------------- #
    _assign_communities(b)

    return {
        "directed": False,
        "multigraph": False,
        "graph": {},
        "nodes": list(b.nodes.values()),
        "links": b.edges,
        "hyperedges": [],
        "built_at_commit": commit,
        # Producer + contract version: lets the stack evolve the graph schema
        # and lets a future backend (SCIP/LSP precision pass, more languages)
        # be slotted in behind the same graph.json seam without ambiguity.
        "generated_by": "neuralmind.graphgen (tree-sitter)",
        "schema_version": SCHEMA_VERSION,
    }


# --------------------------------------------------------------------------- #
# Python extractor
# --------------------------------------------------------------------------- #
def _py_extract_symbols(b: _GraphBuilder, root_node, src: bytes, rel: str, file_id: str) -> None:
    """Pass 1 for Python: module key, module docstring, classes/functions/symbols."""
    b.file_by_module[_module_dotted(rel)] = file_id
    mod_doc = _docstring(root_node, src)
    if mod_doc:
        rid = f"{file_id}__rationale"
        b.add_node(rid, mod_doc, "rationale", rel, 1)
        b.add_edge("rationale_for", rid, file_id, rel, 1)
    _walk_top_level(b, root_node, src, rel, file_id)


def _py_resolve_edges(b: _GraphBuilder, root_node, src: bytes, rel: str, file_id: str) -> None:
    """Pass 2 for Python: imports / inherits / calls."""
    _resolve_imports(b, root_node, src, rel, file_id)
    _resolve_inherits(b, root_node, src, rel)
    _resolve_calls(b, root_node, src, rel)


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
        elif child.type == "expression_statement":
            _emit_assignment(b, child, src, rel, container=file_id)


def _emit_assignment(b: _GraphBuilder, stmt_node, src: bytes, rel: str, *, container: str) -> None:
    """Emit a ``code`` node for a module/class-level assignment's simple target.

    Module constants (``SESSION_TTL = …``) and class/dataclass fields
    (``password_hash: str``) are first-class symbols a query can ask about
    ("how long is a session?", "what fields does a user record have?"), but
    they live in neither a function nor a docstring. Surfacing them as named
    code nodes lets the selector retrieve them by name. Only simple identifier
    targets are taken — tuple/attribute/subscript LHS (``self.x``, ``a, b = …``)
    are skipped to avoid noise.
    """
    if not stmt_node.named_child_count:
        return
    assign = stmt_node.named_children[0]
    if assign.type != "assignment":
        return
    left = assign.child_by_field_name("left")
    if left is None or left.type != "identifier":
        return
    name = _node_text(left, src)
    # Skip dunders (``__all__`` etc.) — structural noise, not domain symbols.
    if not name or (name.startswith("__") and name.endswith("__")):
        return
    line = left.start_point[0] + 1
    sid = f"{container}__{_slug(name)}_sym"
    b.add_node(sid, name, "code", rel, line)
    b.add_edge("contains", container, sid, rel, line)


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
        elif member.type == "expression_statement":
            # Class/dataclass fields (``password_hash: str``) → code nodes.
            _emit_assignment(b, member, src, rel, container=cid)


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


# --------------------------------------------------------------------------- #
# Comment-based rationale (TypeScript / Go) — docstrings live in the comment(s)
# immediately preceding a declaration, not in a first-statement string literal.
# --------------------------------------------------------------------------- #
def _clean_comment(raw: str) -> str:
    """Strip ``//`` / ``/* */`` / leading-``*`` markers from a comment and
    collapse it to a single capped line."""
    raw = raw.strip()
    if raw.startswith("/*"):
        raw = raw[2:]
        if raw.endswith("*/"):
            raw = raw[:-2]
    out: list[str] = []
    for ln in raw.splitlines():
        s = ln.strip().lstrip("/*").strip()
        if s.endswith("*/"):
            s = s[:-2].strip()
        if s:
            out.append(s)
    collapsed = " ".join(" ".join(out).split())
    if len(collapsed) > _RATIONALE_MAX_CHARS:
        collapsed = collapsed[:_RATIONALE_MAX_CHARS].rstrip()
    return collapsed


def _leading_comment_text(node, src: bytes) -> str | None:
    """Concatenated text of the contiguous ``comment`` siblings immediately
    preceding ``node`` (its doc comment), cleaned to rationale text."""
    comments: list[str] = []
    sib = node.prev_named_sibling
    while sib is not None and sib.type == "comment":
        comments.append(_node_text(sib, src))
        sib = sib.prev_named_sibling
    if not comments:
        return None
    cleaned = _clean_comment("\n".join(reversed(comments)))
    return cleaned or None


def _attach_comment_rationale(
    b: _GraphBuilder, comment_node, src: bytes, rel: str, target_id: str
) -> None:
    """Attach a ``rationale`` node from ``comment_node``'s leading comment."""
    doc = _leading_comment_text(comment_node, src)
    if not doc:
        return
    line = comment_node.start_point[0] + 1
    rid = f"{target_id}__rationale"
    b.add_node(rid, doc, "rationale", rel, line)
    b.add_edge("rationale_for", rid, target_id, rel, line)


# --------------------------------------------------------------------------- #
# TypeScript extractor
# --------------------------------------------------------------------------- #
def _ts_module_key(rel: str) -> str:
    """``src/db/connection.ts`` → ``src/db/connection`` (extension dropped)."""
    for suf in (".tsx", ".ts"):
        if rel.endswith(suf):
            return rel[: -len(suf)]
    return rel


def _ts_resolve_import(importing_rel: str, spec: str) -> str | None:
    """Resolve a relative import specifier to a module key, or None if external."""
    if not spec.startswith("."):
        return None  # bare/package import — not a project file
    import posixpath

    base = posixpath.dirname(importing_rel)
    return posixpath.normpath(posixpath.join(base, spec))


def _ts_extract_symbols(b: _GraphBuilder, root_node, src: bytes, rel: str, file_id: str) -> None:
    """Pass 1 for TypeScript: functions, classes, interfaces, const/let symbols."""
    b.file_by_module[_ts_module_key(rel)] = file_id
    for child in root_node.named_children:
        decl = child
        if child.type == "export_statement":
            inner = child.child_by_field_name("declaration")
            if inner is None:
                continue
            decl = inner
        _ts_emit_decl(b, decl, child, src, rel, file_id)


def _ts_emit_decl(b: _GraphBuilder, decl, outer, src: bytes, rel: str, file_id: str) -> None:
    line = decl.start_point[0] + 1
    if decl.type == "function_declaration":
        name = _name_of(decl, src)
        if not name:
            return
        fid = f"{file_id}__{_slug(name)}_fn"
        b.add_node(fid, f"{name}()", "code", rel, line)
        b.func_by_name.setdefault(name, []).append(fid)
        b.add_edge("contains", file_id, fid, rel, line)
        _attach_comment_rationale(b, outer, src, rel, fid)
    elif decl.type in ("class_declaration", "abstract_class_declaration", "interface_declaration"):
        name = _name_of(decl, src)
        if not name:
            return
        cid = f"{file_id}__{_slug(name)}_cls"
        b.add_node(cid, name, "code", rel, line)
        b.class_by_name.setdefault(name, []).append(cid)
        b.add_edge("contains", file_id, cid, rel, line)
        _attach_comment_rationale(b, outer, src, rel, cid)
        body = decl.child_by_field_name("body")
        if body is not None:
            for member in body.named_children:
                if member.type in ("method_definition", "method_signature"):
                    mname = _name_of(member, src)
                    if not mname:
                        continue
                    mline = member.start_point[0] + 1
                    mid = f"{cid}__{_slug(mname)}_fn"
                    b.add_node(mid, f"{mname}()", "code", rel, mline)
                    b.func_by_name.setdefault(mname, []).append(mid)
                    b.add_edge("contains", cid, mid, rel, mline)
                    _attach_comment_rationale(b, member, src, rel, mid)
    elif decl.type == "lexical_declaration":
        for vd in decl.named_children:
            if vd.type != "variable_declarator":
                continue
            nm = vd.child_by_field_name("name")
            if nm is None or nm.type != "identifier":
                continue
            name = _node_text(nm, src)
            sid = f"{file_id}__{_slug(name)}_sym"
            b.add_node(sid, name, "code", rel, line)
            b.add_edge("contains", file_id, sid, rel, line)
            _attach_comment_rationale(b, outer, src, rel, sid)


def _ts_resolve_edges(b: _GraphBuilder, root_node, src: bytes, rel: str, file_id: str) -> None:
    """Pass 2 for TypeScript: imports (relative) + inherits (extends/implements) + calls."""
    # imports
    for child in root_node.named_children:
        if child.type != "import_statement":
            continue
        srcnode = child.child_by_field_name("source")
        if srcnode is None:
            continue
        spec = _node_text(srcnode, src).strip("\"'`")
        key = _ts_resolve_import(rel, spec)
        target = b.file_by_module.get(key) if key else None
        if target and target != file_id:
            b.add_edge(
                "imports_from", file_id, target, rel, child.start_point[0] + 1, context="import"
            )

    # inherits + calls
    _ts_resolve_inherits(b, root_node, src, rel, file_id)
    _ts_resolve_calls(b, root_node, src, rel, file_id)


def _ts_resolve_inherits(b: _GraphBuilder, root_node, src: bytes, rel: str, file_id: str) -> None:
    def handle_class(decl) -> None:
        name = _name_of(decl, src)
        cid = next((c for c in b.class_by_name.get(name, []) if c.startswith(file_id)), None)
        if not cid:
            return
        for h in decl.named_children:
            if h.type not in (
                "class_heritage",
                "extends_clause",
                "implements_clause",
                "extends_type_clause",
            ):
                continue
            for base in _ts_iter_type_names(h, src):
                targets = b.class_by_name.get(base)
                line = decl.start_point[0] + 1
                if targets:
                    for base_id in targets:
                        b.add_edge("inherits", cid, base_id, rel, line)
                else:
                    # External base (e.g. Error) — synthesize a node so the
                    # inherits edge survives, mirroring graphify's behaviour.
                    base_id = f"ext__{_slug(base)}_cls"
                    b.add_node(base_id, base, "code", rel, line)
                    b.add_edge("inherits", cid, base_id, rel, line)

    for child in root_node.named_children:
        decl = (
            child.child_by_field_name("declaration") if child.type == "export_statement" else child
        )
        if decl is not None and decl.type in (
            "class_declaration",
            "abstract_class_declaration",
            "interface_declaration",
        ):
            handle_class(decl)


def _ts_iter_type_names(node, src: bytes):
    """Yield base type names from an extends/implements clause (one level of
    nesting, unwrapping ``generic_type`` to its name)."""
    for ch in node.named_children:
        if ch.type in ("identifier", "type_identifier"):
            yield _node_text(ch, src)
        elif ch.type == "generic_type":
            nm = ch.child_by_field_name("name")
            if nm is not None:
                yield _node_text(nm, src)
        elif ch.type in ("extends_clause", "implements_clause", "extends_type_clause"):
            yield from _ts_iter_type_names(ch, src)


def _ts_resolve_calls(b: _GraphBuilder, root_node, src: bytes, rel: str, file_id: str) -> None:
    def enclosing_fn_id(name: str | None) -> str | None:
        if not name:
            return None
        cands = b.func_by_name.get(name, [])
        return next((c for c in cands if c.startswith(file_id)), cands[0] if cands else None)

    def visit(node, current_fn: str | None) -> None:
        for child in node.named_children:
            if child.type in ("function_declaration", "method_definition"):
                fid = enclosing_fn_id(_name_of(child, src))
                body = child.child_by_field_name("body")
                if body is not None:
                    visit(body, fid)
                continue
            if child.type == "call_expression" and current_fn is not None:
                fn_field = child.child_by_field_name("function")
                if fn_field is not None:
                    callee = _node_text(fn_field, src).split(".")[-1].split("(")[0].strip()
                    for target in b.func_by_name.get(callee, []):
                        if target != current_fn:
                            b.add_edge("calls", current_fn, target, rel, child.start_point[0] + 1)
                            break
            visit(child, current_fn)

    visit(root_node, None)


# --------------------------------------------------------------------------- #
# Go extractor
# --------------------------------------------------------------------------- #
def _go_extract_symbols(b: _GraphBuilder, root_node, src: bytes, rel: str, file_id: str) -> None:
    """Pass 1 for Go: funcs, methods, type/struct/interface decls + fields, const/var."""
    import posixpath

    # Map the package directory's last segment → this file id (Go imports a
    # package/dir, not a file; we link to the files in the matching dir).
    pkg_dir = posixpath.dirname(rel)
    seg = posixpath.basename(pkg_dir) if pkg_dir else posixpath.basename(rel)
    b.go_pkg_files.setdefault(seg, []).append(file_id)

    for child in root_node.named_children:
        line = child.start_point[0] + 1
        if child.type in ("function_declaration", "method_declaration"):
            name = _name_of(child, src)
            if not name:
                continue
            fid = f"{file_id}__{_slug(name)}_fn"
            b.add_node(fid, f"{name}()", "code", rel, line)
            b.func_by_name.setdefault(name, []).append(fid)
            b.add_edge("contains", file_id, fid, rel, line)
            _attach_comment_rationale(b, child, src, rel, fid)
        elif child.type == "type_declaration":
            for spec in child.named_children:
                if spec.type != "type_spec":
                    continue
                nm = spec.child_by_field_name("name")
                if nm is None:
                    continue
                name = _node_text(nm, src)
                cid = f"{file_id}__{_slug(name)}_cls"
                b.add_node(cid, name, "code", rel, line)
                b.class_by_name.setdefault(name, []).append(cid)
                b.add_edge("contains", file_id, cid, rel, line)
                _attach_comment_rationale(b, child, src, rel, cid)
                _go_emit_struct_fields(b, spec, src, rel, cid)
        elif child.type in ("const_declaration", "var_declaration"):
            _go_emit_const_var(b, child, src, rel, file_id)


def _go_emit_struct_fields(
    b: _GraphBuilder, type_spec, src: bytes, rel: str, container: str
) -> None:
    body = type_spec.child_by_field_name("type")
    if body is None or body.type != "struct_type":
        return
    field_list = body.child_by_field_name("body") or (
        body.named_children[0] if body.named_children else None
    )
    if field_list is None:
        return
    for fld in field_list.named_children:
        if fld.type != "field_declaration":
            continue
        for nm in fld.named_children:
            if nm.type == "field_identifier":
                name = _node_text(nm, src)
                line = nm.start_point[0] + 1
                sid = f"{container}__{_slug(name)}_sym"
                b.add_node(sid, name, "code", rel, line)
                b.add_edge("contains", container, sid, rel, line)


def _go_emit_const_var(b: _GraphBuilder, decl, src: bytes, rel: str, file_id: str) -> None:
    for spec in decl.named_children:
        if spec.type not in ("const_spec", "var_spec"):
            continue
        for nm in spec.named_children:
            if nm.type == "identifier":
                name = _node_text(nm, src)
                line = nm.start_point[0] + 1
                sid = f"{file_id}__{_slug(name)}_sym"
                b.add_node(sid, name, "code", rel, line)
                b.add_edge("contains", file_id, sid, rel, line)


def _go_resolve_edges(b: _GraphBuilder, root_node, src: bytes, rel: str, file_id: str) -> None:
    """Pass 2 for Go: imports (by package dir) + calls. Go has no inheritance."""
    import posixpath

    for child in root_node.named_children:
        if child.type != "import_declaration":
            continue
        for spec in _go_iter_import_specs(child):
            path = _node_text(spec, src).strip('"`')
            seg = posixpath.basename(path)
            for target in b.go_pkg_files.get(seg, []):
                if target != file_id:
                    b.add_edge(
                        "imports_from",
                        file_id,
                        target,
                        rel,
                        child.start_point[0] + 1,
                        context="import",
                    )
    _go_resolve_calls(b, root_node, src, rel, file_id)


def _go_iter_import_specs(import_decl):
    for ch in import_decl.named_children:
        if ch.type == "import_spec":
            path = ch.child_by_field_name("path")
            if path is not None:
                yield path
        elif ch.type == "import_spec_list":
            for spec in ch.named_children:
                if spec.type == "import_spec":
                    path = spec.child_by_field_name("path")
                    if path is not None:
                        yield path


def _go_resolve_calls(b: _GraphBuilder, root_node, src: bytes, rel: str, file_id: str) -> None:
    def enclosing_fn_id(name: str | None) -> str | None:
        if not name:
            return None
        cands = b.func_by_name.get(name, [])
        return next((c for c in cands if c.startswith(file_id)), cands[0] if cands else None)

    def visit(node, current_fn: str | None) -> None:
        for child in node.named_children:
            if child.type in ("function_declaration", "method_declaration"):
                fid = enclosing_fn_id(_name_of(child, src))
                body = child.child_by_field_name("body")
                if body is not None:
                    visit(body, fid)
                continue
            if child.type == "call_expression" and current_fn is not None:
                fn_field = child.child_by_field_name("function")
                if fn_field is not None:
                    callee = _node_text(fn_field, src).split(".")[-1].strip()
                    for target in b.func_by_name.get(callee, []):
                        if target != current_fn:
                            b.add_edge("calls", current_fn, target, rel, child.start_point[0] + 1)
                            break
            visit(child, current_fn)

    visit(root_node, None)


# --------------------------------------------------------------------------- #
# Rust extractor
# --------------------------------------------------------------------------- #
# Leading path qualifiers in a ``use`` path that name no module of their own —
# stripped before resolving the remaining segments against the module-key table.
_RUST_PATH_QUALIFIERS: frozenset[str] = frozenset(
    {"crate", "self", "super", "std", "core", "alloc"}
)


def _rust_module_keys(rel: str):
    """Yield the module keys a ``use`` path may name this file by.

    ``src/auth/jwt_utils.rs`` → ``auth::jwt_utils`` and ``jwt_utils``;
    ``src/auth/mod.rs`` → ``auth``. Crate roots (``lib.rs``/``main.rs``) collapse
    to their parent path, since ``use crate::x`` names items under the root, not
    the root file itself."""
    no_ext = rel[:-3] if rel.endswith(".rs") else rel
    parts = [p for p in no_ext.split("/") if p]
    if parts and parts[0] == "src":
        parts = parts[1:]
    if parts and parts[-1] in ("mod", "lib", "main"):
        parts = parts[:-1]
    if not parts:
        return
    yield "::".join(parts)
    if len(parts) > 1:
        yield parts[-1]


def _rust_type_name(node, src: bytes) -> str:
    """Bare type name from an impl/trait reference, unwrapping one level of
    ``generic_type`` / ``scoped_type_identifier`` / ``reference_type``."""
    if node is None:
        return ""
    if node.type == "type_identifier":
        return _node_text(node, src)
    inner = node.child_by_field_name("type") or node.child_by_field_name("name")
    if inner is not None:
        return _rust_type_name(inner, src)
    for c in node.named_children:
        if c.type == "type_identifier":
            return _node_text(c, src)
    return _node_text(node, src).strip()


def _rust_leading_doc(node, src: bytes) -> str | None:
    """Rust doc comments are ``line_comment``/``block_comment`` nodes (``///``,
    ``//!``, ``/** */``) — not the ``comment`` type ``_leading_comment_text``
    matches — so Rust needs its own contiguous-leading-comment grabber."""
    comments: list[str] = []
    sib = node.prev_named_sibling
    while sib is not None and sib.type in ("line_comment", "block_comment"):
        comments.append(_node_text(sib, src))
        sib = sib.prev_named_sibling
    if not comments:
        return None
    return _clean_comment("\n".join(reversed(comments))) or None


def _rust_attach_doc(b: _GraphBuilder, node, src: bytes, rel: str, target_id: str) -> None:
    doc = _rust_leading_doc(node, src)
    if not doc:
        return
    line = node.start_point[0] + 1
    rid = f"{target_id}__rationale"
    b.add_node(rid, doc, "rationale", rel, line)
    b.add_edge("rationale_for", rid, target_id, rel, line)


def _rust_emit_fn(b: _GraphBuilder, fn_node, src: bytes, rel: str, container: str) -> None:
    name = _name_of(fn_node, src)
    if not name:
        return
    line = fn_node.start_point[0] + 1
    fid = f"{container}__{_slug(name)}_fn"
    b.add_node(fid, f"{name}()", "code", rel, line)
    b.func_by_name.setdefault(name, []).append(fid)
    b.add_edge("contains", container, fid, rel, line)
    _rust_attach_doc(b, fn_node, src, rel, fid)


def _rust_type_node_id(b: _GraphBuilder, file_id: str, name: str, line: int, rel: str) -> str:
    """Ensure (idempotently) a type node for ``name`` in this file and return its
    id. Used by impls, which may precede the type's own declaration."""
    cid = f"{file_id}__{_slug(name)}_cls"
    b.add_node(cid, name, "code", rel, line)
    return cid


def _rust_emit_type(b: _GraphBuilder, type_node, src: bytes, rel: str, file_id: str) -> str | None:
    name = _name_of(type_node, src)
    if not name:
        return None
    line = type_node.start_point[0] + 1
    cid = f"{file_id}__{_slug(name)}_cls"
    is_new = cid not in b.nodes
    b.add_node(cid, name, "code", rel, line)
    if is_new:
        b.class_by_name.setdefault(name, []).append(cid)
    b.add_edge("contains", file_id, cid, rel, line)
    _rust_attach_doc(b, type_node, src, rel, cid)
    return cid


def _rust_emit_sym(b: _GraphBuilder, name: str, line: int, rel: str, container: str) -> None:
    sid = f"{container}__{_slug(name)}_sym"
    b.add_node(sid, name, "code", rel, line)
    b.add_edge("contains", container, sid, rel, line)


def _rust_emit_struct_fields(b: _GraphBuilder, struct_node, src: bytes, rel: str, cid: str) -> None:
    body = struct_node.child_by_field_name("body")
    if body is None:
        return
    for fld in body.named_children:
        if fld.type != "field_declaration":
            continue
        nm = fld.child_by_field_name("name")
        if nm is None:
            nm = next((c for c in fld.named_children if c.type == "field_identifier"), None)
        if nm is not None:
            _rust_emit_sym(b, _node_text(nm, src), fld.start_point[0] + 1, rel, cid)


def _rust_emit_enum_variants(b: _GraphBuilder, enum_node, src: bytes, rel: str, cid: str) -> None:
    body = enum_node.child_by_field_name("body")
    if body is None:
        return
    for v in body.named_children:
        if v.type != "enum_variant":
            continue
        nm = v.child_by_field_name("name") or (v.named_children[0] if v.named_children else None)
        if nm is not None:
            _rust_emit_sym(b, _node_text(nm, src), v.start_point[0] + 1, rel, cid)


def _rust_extract_symbols(b: _GraphBuilder, root_node, src: bytes, rel: str, file_id: str) -> None:
    """Pass 1 for Rust: register module keys, then emit fns / types / fields /
    variants / consts, descending into inline ``mod`` blocks and attaching impl
    methods to their type node."""
    for key in _rust_module_keys(rel):
        b.file_by_module.setdefault(key, file_id)
    _rust_walk_items(b, root_node, src, rel, file_id)


def _rust_walk_items(b: _GraphBuilder, node, src: bytes, rel: str, file_id: str) -> None:
    for child in node.named_children:
        t = child.type
        if t == "function_item":
            _rust_emit_fn(b, child, src, rel, file_id)
        elif t in ("struct_item", "union_item", "type_item"):
            cid = _rust_emit_type(b, child, src, rel, file_id)
            if cid and t != "type_item":
                _rust_emit_struct_fields(b, child, src, rel, cid)
        elif t == "enum_item":
            cid = _rust_emit_type(b, child, src, rel, file_id)
            if cid:
                _rust_emit_enum_variants(b, child, src, rel, cid)
        elif t == "trait_item":
            cid = _rust_emit_type(b, child, src, rel, file_id)
            body = child.child_by_field_name("body")
            if cid and body is not None:
                for m in body.named_children:
                    if m.type in ("function_item", "function_signature_item"):
                        _rust_emit_fn(b, m, src, rel, cid)
        elif t in ("const_item", "static_item"):
            name = _name_of(child, src)
            if name:
                _rust_emit_sym(b, name, child.start_point[0] + 1, rel, file_id)
        elif t == "impl_item":
            type_node = child.child_by_field_name("type")
            type_name = _rust_type_name(type_node, src) if type_node is not None else ""
            if not type_name:
                continue
            cid = _rust_type_node_id(b, file_id, type_name, child.start_point[0] + 1, rel)
            body = child.child_by_field_name("body")
            if body is not None:
                for m in body.named_children:
                    if m.type == "function_item":
                        _rust_emit_fn(b, m, src, rel, cid)
        elif t == "mod_item":
            body = child.child_by_field_name("body")
            if body is not None:
                _rust_walk_items(b, body, src, rel, file_id)


def _rust_use_keys(use_node, src: bytes):
    """Yield candidate module keys for a ``use`` declaration, longest path first
    then bare stems, so the resolver matches the most specific module it can."""
    arg = use_node.child_by_field_name("argument")
    raw = _node_text(arg if arg is not None else use_node, src)
    raw = raw.split(" as ")[0].strip()
    # `prefix::{a, b}` resolves to the prefix module (items live under it).
    if "{" in raw:
        raw = raw[: raw.index("{")].strip().rstrip(":")
    segs = [s.strip() for s in raw.split("::") if s.strip() and s.strip() != "*"]
    segs = [s for s in segs if s not in _RUST_PATH_QUALIFIERS]
    if not segs:
        return
    for n in range(len(segs), 0, -1):
        yield "::".join(segs[:n])
    yield from reversed(segs)


def _rust_resolve_imports(b: _GraphBuilder, node, src: bytes, rel: str, file_id: str) -> None:
    for child in node.named_children:
        if child.type == "mod_item":
            body = child.child_by_field_name("body")
            if body is not None:
                _rust_resolve_imports(b, body, src, rel, file_id)
            continue
        if child.type != "use_declaration":
            continue
        line = child.start_point[0] + 1
        for key in _rust_use_keys(child, src):
            target = b.file_by_module.get(key)
            if target and target != file_id:
                b.add_edge("imports_from", file_id, target, rel, line, context="use")
                break


def _rust_resolve_inherits(b: _GraphBuilder, node, src: bytes, rel: str, file_id: str) -> None:
    """``impl Trait for Type`` → ``inherits`` edge Type → Trait. External traits
    are synthesized as nodes so the edge never dangles (mirrors the TS path)."""
    for child in node.named_children:
        if child.type == "mod_item":
            body = child.child_by_field_name("body")
            if body is not None:
                _rust_resolve_inherits(b, body, src, rel, file_id)
            continue
        if child.type != "impl_item":
            continue
        trait_node = child.child_by_field_name("trait")
        type_node = child.child_by_field_name("type")
        if trait_node is None or type_node is None:
            continue
        type_name = _rust_type_name(type_node, src)
        trait_name = _rust_type_name(trait_node, src)
        if not type_name or not trait_name:
            continue
        line = child.start_point[0] + 1
        cid = next((c for c in b.class_by_name.get(type_name, []) if c.startswith(file_id)), None)
        if cid is None:
            cid = _rust_type_node_id(b, file_id, type_name, line, rel)
        targets = b.class_by_name.get(trait_name)
        if targets:
            for tid in targets:
                b.add_edge("inherits", cid, tid, rel, line)
        else:
            tid = f"ext__{_slug(trait_name)}_cls"
            b.add_node(tid, trait_name, "code", rel, line)
            b.add_edge("inherits", cid, tid, rel, line)


def _rust_resolve_calls(b: _GraphBuilder, root_node, src: bytes, rel: str, file_id: str) -> None:
    def enclosing_fn_id(name: str | None) -> str | None:
        if not name:
            return None
        cands = b.func_by_name.get(name, [])
        return next((c for c in cands if c.startswith(file_id)), cands[0] if cands else None)

    def visit(node, current_fn: str | None) -> None:
        for child in node.named_children:
            if child.type == "function_item":
                fid = enclosing_fn_id(_name_of(child, src))
                body = child.child_by_field_name("body")
                if body is not None:
                    visit(body, fid)
                continue
            if child.type == "call_expression" and current_fn is not None:
                fn_field = child.child_by_field_name("function")
                if fn_field is not None:
                    callee = (
                        _node_text(fn_field, src)
                        .split("::")[-1]
                        .split(".")[-1]
                        .split("(")[0]
                        .strip()
                    )
                    for target in b.func_by_name.get(callee, []):
                        if target != current_fn:
                            b.add_edge("calls", current_fn, target, rel, child.start_point[0] + 1)
                            break
            visit(child, current_fn)

    visit(root_node, None)


def _rust_resolve_edges(b: _GraphBuilder, root_node, src: bytes, rel: str, file_id: str) -> None:
    """Pass 2 for Rust: ``use`` imports + ``impl Trait`` inherits + calls."""
    _rust_resolve_imports(b, root_node, src, rel, file_id)
    _rust_resolve_inherits(b, root_node, src, rel, file_id)
    _rust_resolve_calls(b, root_node, src, rel, file_id)


# Suffix-language → (pass-1 symbol extractor, pass-2 edge resolver). The seam:
# registering a grammar + a pair of functions adds a language with no change to
# anything downstream of graph.json.
_EXTRACTORS: dict[str, tuple] = {
    "python": (_py_extract_symbols, _py_resolve_edges),
    "typescript": (_ts_extract_symbols, _ts_resolve_edges),
    "go": (_go_extract_symbols, _go_resolve_edges),
    "rust": (_rust_extract_symbols, _rust_resolve_edges),
}


# --------------------------------------------------------------------------- #
# Incremental per-file update
# --------------------------------------------------------------------------- #
class UpdateStats:
    """What an incremental update changed."""

    def __init__(self) -> None:
        self.files_reparsed = 0
        self.files_removed = 0
        self.nodes_before = 0
        self.nodes_after = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "files_reparsed": self.files_reparsed,
            "files_removed": self.files_removed,
            "nodes_before": self.nodes_before,
            "nodes_after": self.nodes_after,
        }


def _register_node_symbol(b: _GraphBuilder, node: dict[str, Any]) -> None:
    """Rebuild a builder's name tables from an already-emitted node, so a
    re-parsed file's edges can resolve against the unchanged files' symbols."""
    if node.get("file_type") != "code":
        return
    import posixpath

    nid = node["id"]
    label = str(node.get("label", ""))
    sf = str(node.get("source_file", ""))
    if nid == _slug(sf):  # the file node
        suffix = "." + sf.rsplit(".", 1)[-1] if "." in sf else ""
        lang = _SUFFIX_LANG.get(suffix)
        if lang == "python":
            b.file_by_module[_module_dotted(sf)] = nid
        elif lang == "typescript":
            b.file_by_module[_ts_module_key(sf)] = nid
        elif lang == "go":
            seg = posixpath.basename(posixpath.dirname(sf)) or posixpath.basename(sf)
            b.go_pkg_files.setdefault(seg, []).append(nid)
        elif lang == "rust":
            for key in _rust_module_keys(sf):
                b.file_by_module.setdefault(key, nid)
        return
    if nid.endswith("_fn"):
        b.func_by_name.setdefault(label.rstrip("()"), []).append(nid)
    elif nid.endswith("_cls"):
        b.class_by_name.setdefault(label, []).append(nid)


def update_files(
    project_path: str | Path,
    graph: dict[str, Any],
    changed: list[str],
    removed: list[str] | None = None,
) -> tuple[dict[str, Any], UpdateStats]:
    """Re-parse only ``changed`` files (relative posix paths) and splice their
    nodes/edges back into ``graph`` in place; drop ``removed`` files.

    Unchanged files keep their nodes, edges, **and community numbers** byte-for-
    byte — so the embedder's content-hash skips them and only the edited file's
    nodes are re-embedded. The edited file's *outgoing* edges are re-resolved
    against the whole project's symbols; stale cross-file edges into a removed
    or renamed symbol are pruned. Returns ``(graph, stats)``.
    """
    root = Path(project_path).resolve()
    removed = removed or []
    changed_set = set(changed)
    touched = changed_set | set(removed)

    stats = UpdateStats()
    original_nodes = graph.get("nodes", [])
    stats.nodes_before = len(original_nodes)
    # Preserve each unchanged/edited file's existing community number; a brand
    # new file gets the next free id. (Renumbering would change every node's
    # content hash and defeat the point of an incremental update.)
    comm_of_file: dict[str, int] = {}
    for n in original_nodes:
        comm_of_file.setdefault(n["source_file"], n["community"])
    next_comm = max(comm_of_file.values(), default=-1) + 1

    b = _GraphBuilder()
    for n in original_nodes:
        if n["source_file"] in touched:
            continue
        b.nodes[n["id"]] = dict(n)
        _register_node_symbol(b, n)
    for e in graph.get("links", []):
        if e.get("source_file") in touched:
            continue  # outgoing edges of touched files are re-derived below
        b.edges.append(dict(e))

    # Re-parse changed files: code via the per-language extractor, markdown via
    # the document extractor. Group code files by language for one parser each.
    code_by_lang: dict[str, list[str]] = {}
    for rel in sorted(changed_set):
        fpath = root / rel
        if not fpath.exists():
            continue
        if fpath.suffix in _DOC_SUFFIXES:
            _extract_markdown(b, fpath, rel)
            stats.files_reparsed += 1
            continue
        lang = _SUFFIX_LANG.get(fpath.suffix)
        if lang and lang in _EXTRACTORS and language_available(lang):
            code_by_lang.setdefault(lang, []).append(rel)

    for lang, rels in code_by_lang.items():
        extract_symbols, resolve_edges = _EXTRACTORS[lang]
        parser = _make_parser(lang)
        parsed: list[tuple[str, bytes, Any]] = []
        for rel in rels:
            try:
                src = (root / rel).read_bytes()
            except OSError:
                continue
            tree = parser.parse(src)
            file_id = _slug(rel)
            b.add_node(file_id, (root / rel).name, "code", rel, 1)
            extract_symbols(b, tree.root_node, src, rel, file_id)
            parsed.append((rel, src, tree))
            stats.files_reparsed += 1
        for rel, src, tree in parsed:
            resolve_edges(b, tree.root_node, src, rel, _slug(rel))

    stats.files_removed = len(removed)

    # Assign communities: preserved for known files, fresh for new ones.
    for node in b.nodes.values():
        sf = node["source_file"]
        if sf not in comm_of_file:
            comm_of_file[sf] = next_comm
            next_comm += 1
        node["community"] = comm_of_file[sf]

    # Prune dangling edges (into removed/renamed symbols).
    ids = set(b.nodes)
    b.edges = [e for e in b.edges if e["source"] in ids and e["target"] in ids]

    graph["nodes"] = list(b.nodes.values())
    graph["links"] = b.edges
    stats.nodes_after = len(graph["nodes"])
    return graph, stats


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
