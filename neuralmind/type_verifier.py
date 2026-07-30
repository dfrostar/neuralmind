"""type_verifier.py — Static type verification pass for NeuralMind.

Post-processing pass over the structural graph that augments ``calls`` edges
with type metadata extracted from Python source annotations. Emits
``TypeRisk`` signals for compliance review and persists ``type_edges`` to the
synapse store for cold-start weight boosting.

Design: fail-open. Any import/parse error degrades gracefully to "unknown
type" — type inference is observability, never a gate on the build.
"""

from __future__ import annotations

import ast
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tree_sitter import Language


@dataclass(frozen=True)
class TypeInfo:
    """Inferred type metadata for a function's return type."""

    return_type: str | None  # stringified annotation, None = unannotated
    is_optional: bool  # True if Optional/Union[...,None]/X|None
    confidence: float  # 0.0=heuristic, 1.0=mypy-confirmed
    inferred_by: str  # "stdlib" | "mypy" | "scip"


@dataclass(frozen=True)
class TypeRisk:
    """A type-related risk signal for a calls edge."""

    caller_id: str
    callee_id: str
    risk_type: str  # "optional_return" | "implicit_none" | "type_mismatch" | "any_fallthrough"
    severity: str  # "info" | "warn" | "high"
    detail: str  # human-readable explanation
    callee_returns: str  # the inferred return type


# Optional/Union type patterns (stringified) that indicate None is a possible return
_OPTIONAL_PATTERNS = (
    re.compile(r"^Optional\["),
    re.compile(r"^Union\[.*,\s*None\s*\]"),
    re.compile(r"^Union\[\s*None\s*,"),
    re.compile(r"\|\s*None\s*$"),
    re.compile(r"^\s*None\s*\|"),
    re.compile(r"^None$"),
)


def _is_optional_type(type_str: str | None) -> bool:
    """Return True if ``type_str`` represents an Optional-like type."""
    if not type_str:
        return False
    stripped = type_str.strip()
    if stripped == "None":
        return False
    for pat in _OPTIONAL_PATTERNS:
        if pat.search(stripped):
            return True
    return False


class TypeVerifier:
    """Lightweight type inference pass using stdlib ``ast`` + tree-sitter.

    Parses Python files in the project to extract return type annotations
    without executing any code. Optional mypy integration is gated behind
    ``NEURALMIND_TYPE_CHECK=1``.

    Cross-language support (TypeScript, Go, Rust) uses tree-sitter grammars
    when available — same fail-open semantics as the Python path.
    """

    _TS_OPTIONAL = ("undefined", "null", "void", "never")
    _GO_OPTIONAL = ("error", "pointer", "interface", "nil")
    _RUST_OPTIONAL = ("Option<", "Result<", "None")

    def __init__(self, project_path: str | Path) -> None:
        self.project_path = Path(project_path)
        self._cache: dict[str, TypeInfo | None] = {}
        self._ast_cache: dict[str, ast.AST] = {}  # file_path -> parsed AST
        self._ts_langs: dict[str, Language] = {}
        self._use_mypy = os.environ.get("NEURALMIND_TYPE_CHECK") == "1"
        self._module_map: dict[str, str] = {}  # module_name -> file_path
        self._last_graph: dict | None = None
        self._func_index: dict[str, Path] = {}  # func_name -> file_path (lazy-built)

    def _build_func_index(self) -> None:
        """Build a function→file index for fast lookup. Called lazily."""
        if self._func_index:
            return
        for root, _dirs, files in os.walk(self.project_path):
            parts = Path(root).parts
            if any(
                p.startswith(".") or p in ("__pycache__", "node_modules", "venv", ".venv")
                for p in parts
            ):
                continue
            for fname in files:
                if fname.endswith((".py", ".ts", ".tsx", ".go", ".rs")):
                    fpath = Path(root) / fname
                    try:
                        source = fpath.read_text(encoding="utf-8", errors="replace")
                        if fname.endswith(".py"):
                            tree = ast.parse(source)
                            for node in ast.walk(tree):
                                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                                    self._func_index[node.name] = fpath
                        else:
                            ext = fpath.suffix.lower().lstrip(".")
                            lang_name = ext
                            if ext in ("ts", "tsx"):
                                lang_name = "typescript"
                            lang = self._ts_language(lang_name)
                            if lang is None:
                                continue
                            ts_tree = self._ts_parse(source, lang)
                            # Walk tree-sitter AST for function-like nodes
                            def walk_ts(node):
                                if node.type in (
                                    "function_declaration",
                                    "method_definition",
                                    "arrow_function",
                                    "function_item",
                                    "method_declaration",
                                ):
                                    for child in node.children:
                                        if child.type == "identifier":
                                            self._func_index[child.text.decode("utf8")] = fpath
                                            break
                                for child in node.children:
                                    walk_ts(child)
                            walk_ts(ts_tree.root_node)
                    except (OSError, SyntaxError, Exception):
                        continue

    def infer_return_type(self, node_id: str) -> TypeInfo | None:
        """Infer the return type for a graph node (function)."""
        if node_id in self._cache:
            return self._cache[node_id]

        try:
            info = self._do_infer(node_id)
        except Exception:
            info = None

        self._cache[node_id] = info
        return info

    def _get_ast(self, source_file: Path) -> ast.AST | None:
        """Get parsed AST for a file, using cache."""
        key = str(source_file)
        if key in self._ast_cache:
            return self._ast_cache[key]
        try:
            source = source_file.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source)
            self._ast_cache[key] = tree
            return tree
        except (OSError, SyntaxError):
            return None

    def _ts_language(self, name: str) -> Language | None:
        """Load a tree-sitter language grammar on demand (fail-open)."""
        from tree_sitter import Language

        if name in self._ts_langs:
            return self._ts_langs[name]
        try:
            if name == "typescript":
                import tree_sitter_typescript as ts
                lang = Language(ts.language_typescript())
            elif name == "go":
                import tree_sitter_go as ts
                lang = Language(ts.language())
            elif name == "rust":
                import tree_sitter_rust as ts
                lang = Language(ts.language())
            else:
                return None
            self._ts_langs[name] = lang
            return lang
        except Exception:
            return None

    def _ts_parse(self, source: str, lang: Language):
        """Parse source with a tree-sitter language."""
        import tree_sitter
        parser = tree_sitter.Parser(lang)
        return parser.parse(bytes(source, "utf8"))

    def _infer_ts_return(self, node) -> TypeInfo | None:
        """Infer return type from a TypeScript function node."""
        return_type = None
        for child in node.children:
            if child.type == "type_annotation":
                return_type = child.text.decode("utf8").lstrip(":").strip()
                break

        if return_type in self._TS_OPTIONAL or return_type is None:
            return TypeInfo(
                return_type=return_type or "void",
                is_optional=True,
                confidence=0.8,
                inferred_by="tree-sitter",
            )
        return TypeInfo(
            return_type=return_type,
            is_optional=False,
            confidence=0.8,
            inferred_by="tree-sitter",
        )

    def _infer_go_return(self, node) -> TypeInfo | None:
        """Infer return type from a Go function node."""
        # Check for method receivers: func (r *Receiver) Method() Type
        for child in node.children:
            if child.type == "result":
                result_text = child.text.decode("utf8").strip()
                is_opt = any(p in result_text for p in self._GO_OPTIONAL)
                return TypeInfo(
                    return_type=result_text or "error",
                    is_optional=is_opt,
                    confidence=0.7,
                    inferred_by="tree-sitter",
                )
        # No return type → void
        return TypeInfo(
            return_type="void",
            is_optional=True,
            confidence=0.7,
            inferred_by="tree-sitter",
        )

    def _infer_rust_return(self, node) -> TypeInfo | None:
        """Infer return type from a Rust function node.
        
        Tree-sitter versions vary:
        - Older: function_item -> [..., return_type -> [->, generic_type], ...]
        - Newer: function_item -> [..., ->, generic_type, ...]
        """
        for child in node.children:
            # Newer tree-sitter: generic_type/primitive_type is direct child
            if child.type in ("generic_type", "primitive_type", "type_identifier"):
                type_text = child.text.decode("utf8").strip()
                is_opt = any(type_text.startswith(p) for p in self._RUST_OPTIONAL)
                return TypeInfo(
                    return_type=type_text,
                    is_optional=is_opt,
                    confidence=0.9,
                    inferred_by="tree-sitter",
                )
            # Older tree-sitter: wrapped in return_type node
            if child.type == "return_type":
                for type_child in child.children:
                    if type_child.type in ("generic_type", "primitive_type", "type_identifier"):
                        type_text = type_child.text.decode("utf8").strip()
                        is_opt = any(type_text.startswith(p) for p in self._RUST_OPTIONAL)
                        return TypeInfo(
                            return_type=type_text,
                            is_optional=is_opt,
                            confidence=0.9,
                            inferred_by="tree-sitter",
                        )
                # Fallback: use entire return_type text
                type_text = child.text.decode("utf8").lstrip("->").strip()
                is_opt = any(type_text.startswith(p) for p in self._RUST_OPTIONAL)
                return TypeInfo(
                    return_type=type_text,
                    is_optional=is_opt,
                    confidence=0.9,
                    inferred_by="tree-sitter",
                )
        # No return type → () unit type
        return TypeInfo(
            return_type="()",
            is_optional=False,
            confidence=0.7,
            inferred_by="tree-sitter",
        )

    def _do_infer(self, node_id: str) -> TypeInfo | None:
        func_name: str
        source_file: Path | None = None

        if "::" in node_id:
            file_part, func_name = node_id.split("::", 1)
            candidate = self.project_path / file_part
            if candidate.is_file():
                source_file = candidate
        else:
            func_name = node_id
            source_file = self._find_function_file(func_name)

        if source_file is None or not source_file.exists():
            return None

        ext = source_file.suffix.lower()
        if ext in (".ts", ".tsx"):
            return self._do_ts_infer(func_name, source_file)
        if ext == ".go":
            return self._do_go_infer(func_name, source_file)
        if ext == ".rs":
            return self._do_rust_infer(func_name, source_file)

        # Default: Python via stdlib ast
        tree = self._get_ast(source_file)
        if tree is None:
            return None

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name == func_name:
                    if node.returns:
                        return_type_str = ast.unparse(node.returns)
                        is_opt = _is_optional_type(return_type_str)
                        return TypeInfo(
                            return_type=return_type_str,
                            is_optional=is_opt,
                            confidence=1.0,
                            inferred_by="stdlib",
                        )
                    return TypeInfo(
                        return_type=None,
                        is_optional=False,
                        confidence=0.0,
                        inferred_by="stdlib",
                    )
        return None

    def _do_ts_infer(self, func_name: str, source_file: Path) -> TypeInfo | None:
        """TypeScript type inference via tree-sitter."""
        lang = self._ts_language("typescript")
        if lang is None:
            return None
        try:
            source = source_file.read_text(encoding="utf-8", errors="replace")
            tree = self._ts_parse(source, lang)
        except (OSError, Exception):
            return None

        def walk(node):
            if node.type in ("function_declaration", "method_definition", "arrow_function"):
                for child in node.children:
                    if child.type == "identifier" and child.text.decode("utf8") == func_name:
                        return self._infer_ts_return(node)
            for child in node.children:
                result = walk(child)
                if result:
                    return result
            return None

        return walk(tree.root_node)

    def _do_go_infer(self, func_name: str, source_file: Path) -> TypeInfo | None:
        """Go type inference via tree-sitter."""
        lang = self._ts_language("go")
        if lang is None:
            return None
        try:
            source = source_file.read_text(encoding="utf-8", errors="replace")
            tree = self._ts_parse(source, lang)
        except (OSError, Exception):
            return None

        def walk(node):
            if node.type == "function_declaration":
                for child in node.children:
                    if child.type == "identifier" and child.text.decode("utf8") == func_name:
                        return self._infer_go_return(node)
            for child in node.children:
                result = walk(child)
                if result:
                    return result
            return None

        return walk(tree.root_node)

    def _do_rust_infer(self, func_name: str, source_file: Path) -> TypeInfo | None:
        """Rust type inference via tree-sitter."""
        lang = self._ts_language("rust")
        if lang is None:
            return None
        try:
            source = source_file.read_text(encoding="utf-8", errors="replace")
            tree = self._ts_parse(source, lang)
        except (OSError, Exception):
            return None

        def walk(node):
            if node.type == "function_item":
                for child in node.children:
                    if child.type == "identifier" and child.text.decode("utf8") == func_name:
                        return self._infer_rust_return(node)
            for child in node.children:
                result = walk(child)
                if result:
                    return result
            return None

        return walk(tree.root_node)

    def _find_function_file(self, func_name: str) -> Path | None:
        """Search project for a file defining ``func_name`` (any supported language).

        Uses lazy-built function index for O(1) lookup after first call.
        """
        if not self._func_index:
            self._build_func_index()
        return self._func_index.get(func_name)

    def augment_graph(self, graph: dict) -> int:
        """Walk calls edges in ``graph`` and annotate with type metadata.

        Uses thread pool for parallel type inference on large graphs.
        """
        if not graph:
            return 0

        edges = graph.get("edges", graph.get("links", []))
        if not edges:
            return 0

        node_map = {n.get("id"): n for n in graph.get("nodes", [])}

        calls_edges = [
            e
            for e in edges
            if e.get("relation") in ("calls", "call") or e.get("label") in ("calls", "call")
        ]

        if not calls_edges:
            graph["type_edges"] = []
            return 0

        # Build lookup list for parallel processing
        lookups = []
        for edge in calls_edges:
            callee = edge.get("target", edge.get("_tgt", ""))
            caller = edge.get("source", edge.get("_src", ""))
            if not callee:
                continue

            callee_node = node_map.get(callee, {})
            callee_label = callee_node.get("label", callee)
            func_name = callee_label.rstrip("()[]").split(".")[-1]
            source_file = callee_node.get("source_file", "")

            if "::" in callee:
                lookup = callee
            elif source_file:
                lookup = f"{source_file}::{func_name}"
            else:
                lookup = func_name

            lookups.append((caller, callee, lookup))

        # Parallel type inference
        type_edges: list[tuple[str, str, TypeInfo]] = []
        max_workers = min(8, len(lookups))

        def process_item(item):
            caller, callee, lookup = item
            info = self.infer_return_type(lookup)
            if info is not None:
                return (caller, callee, info)
            return None

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(process_item, item): item for item in lookups}
            for future in as_completed(futures):
                result = future.result()
                if result is not None:
                    type_edges.append(result)

        graph["type_edges"] = type_edges
        self._last_graph = graph
        return len(type_edges)

    def detect_type_risks(self, graph: dict) -> list[TypeRisk]:
        """Score and rank type risks from annotated calls edges."""
        type_edges = graph.get("type_edges", [])
        risks: list[TypeRisk] = []

        for caller_id, callee_id, type_info in type_edges:
            if type_info.is_optional:
                risks.append(
                    TypeRisk(
                        caller_id=caller_id,
                        callee_id=callee_id,
                        risk_type="optional_return",
                        severity="warn",
                        detail=(
                            f"{callee_id} returns {type_info.return_type} "
                            "— caller may need None guard"
                        ),
                        callee_returns=type_info.return_type or "None",
                    )
                )
            elif type_info.return_type == "None":
                risks.append(
                    TypeRisk(
                        caller_id=caller_id,
                        callee_id=callee_id,
                        risk_type="implicit_none",
                        severity="info",
                        detail=f"{callee_id} explicitly returns None",
                        callee_returns="None",
                    )
                )
            elif type_info.return_type is None and type_info.confidence == 0.0:
                risks.append(
                    TypeRisk(
                        caller_id=caller_id,
                        callee_id=callee_id,
                        risk_type="any_fallthrough",
                        severity="info",
                        detail=(
                            f"{callee_id} unannotated — type unknown. "
                            "Enable NEURALMIND_TYPE_CHECK=1 for inference"
                        ),
                        callee_returns="unknown",
                    )
                )
            elif type_info.return_type == "any":
                risks.append(
                    TypeRisk(
                        caller_id=caller_id,
                        callee_id=callee_id,
                        risk_type="any_fallthrough",
                        severity="warn",
                        detail=(
                            f"{callee_id} returns 'any' — "
                            "type safety lost at this boundary"
                        ),
                        callee_returns="any",
                    )
                )

        return risks

    def persist_type_edges(self, store) -> int:
        """Persist type edges to the synapse store."""
        if not self._last_graph:
            return 0

        type_edges = self._last_graph.get("type_edges", [])
        if not type_edges:
            return 0

        # Build tuples for batch insert: (source, target, return_type, is_optional, confidence, inferred_by, inferred_at)
        now = time.time()
        rows = [
            (
                caller,
                callee,
                type_info.return_type,
                type_info.is_optional,
                type_info.confidence,
                type_info.inferred_by,
                now,
            )
            for caller, callee, type_info in type_edges
        ]

        try:
            return store.persist_type_edges(rows)
        except Exception:
            return 0


def format_type_risks(risks: list[TypeRisk]) -> str:
    """Render type risks as a human-readable compliance report."""
    if not risks:
        return "## Type Risk Report — 0 signals detected\n\nNo type risks found.\n"

    lines = [f"## Type Risk Report — {len(risks)} signal(s) detected\n"]
    for r in risks:
        lines.append(f"{r.severity.upper()}  {r.caller_id} calls {r.callee_id}")
        lines.append(f"      → {r.detail}")
        lines.append(f"      → Return type: {r.callee_returns}")
        lines.append("")
    return "\n".join(lines)
