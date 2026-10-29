# SPDX-License-Identifier: MIT
"""type_verifier.py — Static type verification pass for NeuralMind.

Post-processing pass over the structural graph that augments ``calls`` edges
with type metadata extracted from Python source annotations. Emits
``TypeRisk`` signals for compliance review and persists ``type_edges`` to the
synapse store for cold-start weight boosting.

Design: fail-open. Any import/parse error degrades gracefully to "unknown
type" — type inference is observability, never a gate on the build.

Speed: each file is parsed and walked once, into a ``{function name:
TypeInfo}`` map, and the maps are kept in ``.neuralmind/type_cache.json``
between builds, keyed by the file's content hash, so a rebuild parses only
the files that changed. On hermes-agent (359,225 calls edges, 5,240 files)
the pass took 122 s when it walked a file's whole AST once per distinct
callee, 16 s on a first build with the maps, and ~1 s on a rebuild. The maps
give the same answers: a lookup returns the first matching function in the
order the old per-lookup walk visited them.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import secrets
import stat
import sys
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

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


# Bump when what a file's facts hold, or how they're computed, changes.
_CACHE_VERSION = 1
_CACHE_FILE = "type_cache.json"
# A file changed this recently is hashed again on the next build even when
# its stat matches: a second edit inside the filesystem's timestamp
# granularity can leave size and mtime as they were.
_RACY_NS = 10 * 10**9
# A file whose size, mtime, ctime and inode match the last build is taken as
# unchanged without reading it. Not on Windows, where ctime is the creation
# time, so an edit that restores the mtime would go unseen: there every file
# is hashed.
_TRUST_STAT = os.name != "nt"

# The nodes that can hold a function definition. A breadth-first walk over
# only these meets FunctionDefs in the same order as ``ast.walk`` over every
# node, because each FunctionDef's ancestors are all of these types.
_PY_BLOCKS = (ast.mod, ast.stmt, ast.excepthandler, ast.match_case)
_PY_FUNCS = (ast.FunctionDef, ast.AsyncFunctionDef)

# Tree-sitter grammar and function node types a lookup matches, per language.
_TS_GRAMMAR = {"ts": "typescript", "go": "go", "rs": "rust"}
_TS_FUNCS = {
    "ts": ("function_declaration", "method_definition", "arrow_function"),
    "go": ("function_declaration",),
    "rs": ("function_item",),
}
# Node types the function index records, by their first identifier child.
_INDEX_FUNCS = (
    "function_declaration",
    "method_definition",
    "arrow_function",
    "function_item",
    "method_declaration",
)
# The function index's file types. Rust files have never been indexed (the
# index asked for a grammar named "rs"), so bare-name lookups don't reach them.
_INDEX_SUFFIXES = (".py", ".ts", ".tsx", ".go")

# A file's facts: ``{function name: [return_type, is_optional, confidence,
# inferred_by] or None}`` (None when it can't be parsed), and the names the
# function index records for it. A name maps to None when inferring its first
# match raised, which returns None like a name that isn't there.
_Facts = tuple[dict[str, Any] | None, list[str]]
_NO_FACTS: _Facts = (None, [])
_UNSET = object()


def _index_skips(part: str) -> bool:
    return part.startswith(".") or part in ("__pycache__", "node_modules", "venv", ".venv")


def _kind(path: Path) -> str:
    """The language a file is inferred as: by suffix, Python by default."""
    ext = path.suffix.lower()
    if ext in (".ts", ".tsx"):
        return "ts"
    if ext == ".go":
        return "go"
    if ext == ".rs":
        return "rs"
    return "py"


def _raw(info: TypeInfo) -> list:
    return [info.return_type, info.is_optional, info.confidence, info.inferred_by]


def _py_return(node: ast.FunctionDef | ast.AsyncFunctionDef) -> TypeInfo:
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


def _py_facts(source: str) -> _Facts:
    try:
        tree = ast.parse(source)
    except Exception:
        return _NO_FACTS
    types: dict[str, Any] = {}
    todo: deque[ast.AST] = deque([tree])
    while todo:
        node = todo.popleft()
        if isinstance(node, _PY_FUNCS) and node.name not in types:
            try:
                types[node.name] = _raw(_py_return(node))
            except Exception:
                types[node.name] = None
        todo.extend(c for c in ast.iter_child_nodes(node) if isinstance(c, _PY_BLOCKS))
    return types, list(types)


def _cache_env() -> str:
    """What a cached file's facts depend on besides its text."""
    from importlib import metadata

    parts = [str(_CACHE_VERSION), sys.version]
    for dist in ("tree-sitter", "tree-sitter-typescript", "tree-sitter-go", "tree-sitter-rust"):
        try:
            parts.append(f"{dist}={metadata.version(dist)}")
        except Exception:
            parts.append(f"{dist}=-")
    return "|".join(parts)


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
        self._facts: dict[str, _Facts | None] = {}  # file path -> facts, None = not a file
        self._infos: dict[tuple, TypeInfo] = {}
        self._ts_langs: dict[str, Language] = {}
        self._use_mypy = os.environ.get("NEURALMIND_TYPE_CHECK") == "1"
        self._module_map: dict[str, str] = {}  # module_name -> file_path
        self._last_graph: dict | None = None
        self._func_index: dict[str, Path] = {}  # func_name -> file_path (lazy-built)
        self._func_index_built = False
        # The on-disk facts cache: what was loaded, and what this run used.
        self._disk_loaded = False
        self._disk_paths: dict[str, list] = {}
        self._disk_records: dict[str, list] = {}
        self._used_paths: dict[str, list] = {}
        self._used_records: dict[str, list] = {}

    def _build_func_index(self) -> None:
        """Build a function→file index for fast lookup. Called lazily.

        A name maps to the last file, in walk order, that defines it.
        """
        if self._func_index_built:
            return
        self._func_index_built = True
        for root, dirs, files in os.walk(self.project_path):
            if any(_index_skips(p) for p in Path(root).parts):
                dirs[:] = []
                continue
            dirs[:] = [d for d in dirs if not _index_skips(d)]
            for fname in files:
                if fname.endswith(_INDEX_SUFFIXES):
                    fpath = Path(root) / fname
                    facts = self._file_facts(fpath)
                    if facts is not None:
                        for name in facts[1]:
                            self._func_index[name] = fpath

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

    def _ts_facts(self, source: str, kind: str) -> _Facts | None:
        """One pre-order walk over a tree-sitter parse; None without the grammar.

        A lookup takes the first function node, in pre-order, with an
        identifier child of that name. When reading an identifier fails, a
        lookup that hadn't matched yet would have failed too, so the walk
        stops collecting names for that purpose and keeps what it has.
        """
        try:
            lang = self._ts_language(_TS_GRAMMAR[kind])
        except Exception:
            lang = None
        if lang is None:
            return None
        try:
            tree = self._ts_parse(source, lang)
        except Exception:
            return _NO_FACTS
        infer = {
            "ts": self._infer_ts_return,
            "go": self._infer_go_return,
            "rs": self._infer_rust_return,
        }[kind]
        funcs = _TS_FUNCS[kind]
        types: dict[str, Any] = {}
        names: list[str] = []
        collect_types = True
        collect_names = kind != "rs"
        cursor = tree.walk()
        while collect_types or collect_names:
            node = cursor.node
            if collect_types and node.type in funcs:
                raw: Any = _UNSET
                try:
                    for child in node.children:
                        if child.type == "identifier":
                            name = child.text.decode("utf8")
                            if name not in types:
                                if raw is _UNSET:
                                    try:
                                        info = infer(node)
                                        raw = None if info is None else _raw(info)
                                    except Exception:
                                        raw = None
                                types[name] = raw
                except Exception:
                    collect_types = False
            if collect_names and node.type in _INDEX_FUNCS:
                try:
                    for child in node.children:
                        if child.type == "identifier":
                            names.append(child.text.decode("utf8"))
                            break
                except Exception:
                    collect_names = False
            if cursor.goto_first_child():
                continue
            while not cursor.goto_next_sibling():
                if not cursor.goto_parent():
                    return types, names
        return types, names

    def _file_facts(self, path: Path) -> _Facts | None:
        """The facts for ``path``, or None when it isn't a readable regular file."""
        key = str(path)
        if key in self._facts:
            return self._facts[key]
        facts = self._read_facts(path, key)
        self._facts[key] = facts
        return facts

    def _read_facts(self, path: Path, key: str) -> _Facts | None:
        try:
            st = path.stat()
        except (OSError, ValueError):
            return None
        if not stat.S_ISREG(st.st_mode):
            return None
        sig = [st.st_size, st.st_mtime_ns, st.st_ctime_ns, st.st_ino]
        entry = self._disk_paths.get(key)
        if entry is not None and entry[0] == sig:
            record = self._disk_records.get(entry[1])
            if record is not None:
                self._used_paths[key] = entry
                self._used_records[entry[1]] = record
                return record[0], record[1]
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None
        kind = _kind(path)
        digest = hashlib.sha256(f"{kind}\0{source}".encode("utf-8", "surrogatepass")).hexdigest()
        record = self._disk_records.get(digest) or self._used_records.get(digest)
        if record is None:
            facts = _py_facts(source) if kind == "py" else self._ts_facts(source, kind)
            if facts is None:
                return _NO_FACTS
            record = [facts[0], facts[1]]
        self._used_records[digest] = record
        if _TRUST_STAT and time.time_ns() - max(st.st_mtime_ns, st.st_ctime_ns) >= _RACY_NS:
            self._used_paths[key] = [sig, digest]
        return record[0], record[1]

    def _cache_path(self) -> Path:
        from .paths import canonical_artifact

        return canonical_artifact(self.project_path, _CACHE_FILE)

    def _load_disk_cache(self) -> None:
        """Load ``.neuralmind/type_cache.json`` once; a bad or stale file is ignored."""
        if self._disk_loaded:
            return
        self._disk_loaded = True
        try:
            data = json.loads(self._cache_path().read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        if not isinstance(data, dict) or data.get("env") != _cache_env():
            return
        paths, records = data.get("paths"), data.get("records")
        if not isinstance(paths, dict) or not isinstance(records, dict):
            return
        self._disk_paths = {
            k: v
            for k, v in paths.items()
            if isinstance(v, list) and len(v) == 2 and isinstance(v[1], str)
        }
        self._disk_records = {
            k: v
            for k, v in records.items()
            if isinstance(v, list)
            and len(v) == 2
            and isinstance(v[0], (dict, type(None)))
            and isinstance(v[1], list)
        }

    def _save_disk_cache(self) -> None:
        """Write what this run used, when it differs from what was loaded. Fails open."""
        if self._used_paths == self._disk_paths and self._used_records.keys() == (
            self._disk_records.keys()
        ):
            return
        try:
            path = self._cache_path()
        except ValueError:
            return
        if not path.parent.is_dir():
            return
        tmp = path.with_name(f".{path.name}.{os.getpid()}.{secrets.token_hex(4)}.tmp")
        try:
            data = {"env": _cache_env(), "paths": self._used_paths, "records": self._used_records}
            tmp.write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
            os.replace(tmp, path)
        except (OSError, ValueError):
            try:
                tmp.unlink()
            except OSError:
                pass

    def _info(self, raw: list | None) -> TypeInfo | None:
        if raw is None:
            return None
        key = tuple(raw)
        info = self._infos.get(key)
        if info is None:
            info = self._infos[key] = TypeInfo(*key)
        return info

    def _do_infer(self, node_id: str) -> TypeInfo | None:
        func_name: str
        source_file: Path | None = None

        if "::" in node_id:
            file_part, func_name = node_id.split("::", 1)
            source_file = self.project_path / file_part
        else:
            func_name = node_id
            source_file = self._find_function_file(func_name)

        if source_file is None:
            return None
        facts = self._file_facts(source_file)
        if facts is None or facts[0] is None:
            return None
        return self._info(facts[0].get(func_name))

    def _find_function_file(self, func_name: str) -> Path | None:
        """Search project for a file defining ``func_name`` (any supported language).

        Uses lazy-built function index for O(1) lookup after first call.
        """
        if not self._func_index_built:
            self._build_func_index()
        return self._func_index.get(func_name)

    def augment_graph(self, graph: dict) -> int:
        """Walk calls edges in ``graph`` and annotate with type metadata.

        ``graph["type_edges"]`` lists ``(caller, callee, TypeInfo)`` in edge
        order. Files parsed on an earlier build are read from
        ``.neuralmind/type_cache.json`` when their content is unchanged.
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

        self._load_disk_cache()
        type_edges: list[tuple[str, str, TypeInfo]] = []
        for caller, callee, lookup in lookups:
            info = self.infer_return_type(lookup)
            if info is not None:
                type_edges.append((caller, callee, info))
        self._save_disk_cache()

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
                        detail=(f"{callee_id} returns 'any' — type safety lost at this boundary"),
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
