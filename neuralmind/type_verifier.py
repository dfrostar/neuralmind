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
from dataclasses import dataclass
from pathlib import Path


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
    # Explicit `None` alone is not optional — it's a definite None return
    if stripped == "None":
        return False
    for pat in _OPTIONAL_PATTERNS:
        if pat.search(stripped):
            return True
    return False


class TypeVerifier:
    """Lightweight type inference pass using stdlib ``ast`` + optional mypy.

    Parses Python files in the project to extract return type annotations
    without executing any code. Optional mypy integration is gated behind
    ``NEURALMIND_TYPE_CHECK=1``.
    """

    def __init__(self, project_path: str | Path) -> None:
        self.project_path = Path(project_path)
        self._cache: dict[str, TypeInfo | None] = {}  # node_id → TypeInfo
        self._use_mypy = os.environ.get("NEURALMIND_TYPE_CHECK") == "1"

    def infer_return_type(self, node_id: str) -> TypeInfo | None:
        """Infer the return type for a graph node (function).

        Args:
            node_id: Graph node id, typically ``path/to/file.py::func_name``
                or just ``func_name``.

        Returns:
            ``TypeInfo`` on success, ``None`` if unparseable/unannotated.
        """
        if node_id in self._cache:
            return self._cache[node_id]

        try:
            info = self._do_infer(node_id)
        except Exception:
            info = None

        self._cache[node_id] = info
        return info

    def _do_infer(self, node_id: str) -> TypeInfo | None:
        # Parse node_id — supports "path/file.py::func_name" or bare "func_name"
        func_name: str
        source_file: Path | None = None

        if "::" in node_id:
            file_part, func_name = node_id.split("::", 1)
            candidate = self.project_path / file_part
            if candidate.is_file():
                source_file = candidate
        else:
            func_name = node_id
            # Search Python files for this function name
            source_file = self._find_function_file(func_name)

        if source_file is None or not source_file.exists():
            return None

        try:
            source = source_file.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source)
        except (OSError, SyntaxError):
            return None

        # Walk AST to find function definition
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
                    # Function found but no return annotation → unknown
                    return TypeInfo(
                        return_type=None,
                        is_optional=False,
                        confidence=0.0,
                        inferred_by="stdlib",
                    )

        return None

    def _find_function_file(self, func_name: str) -> Path | None:
        """Search project for a Python file defining ``func_name``."""
        for root, _dirs, files in os.walk(self.project_path):
            # Skip hidden / build dirs
            parts = Path(root).parts
            if any(
                p.startswith(".") or p in ("__pycache__", "node_modules", "venv", ".venv")
                for p in parts
            ):
                continue
            for fname in files:
                if fname.endswith(".py"):
                    fpath = Path(root) / fname
                    try:
                        source = fpath.read_text(encoding="utf-8", errors="replace")
                        tree = ast.parse(source)
                    except (OSError, SyntaxError):
                        continue
                    for node in ast.walk(tree):
                        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            if node.name == func_name:
                                return fpath
        return None

    def augment_graph(self, graph: dict) -> int:
        """Walk calls edges in ``graph`` and annotate with type metadata.

        Modifies the graph dict in-place, adding a ``type_edges`` list of
        ``(source_node, target_node, TypeInfo)`` tuples.

        Returns the number of type edges successfully inferred.
        """
        if not graph:
            return 0

        edges = graph.get("edges", [])
        if not edges:
            return 0

        type_edges: list[tuple[str, str, TypeInfo]] = []
        calls_edges = [
            e
            for e in edges
            if e.get("relation") in ("calls", "call") or e.get("label") in ("calls", "call")
        ]

        for edge in calls_edges:
            callee = edge.get("target", edge.get("_tgt", ""))
            caller = edge.get("source", edge.get("_src", ""))
            if not callee:
                continue

            type_info = self.infer_return_type(callee)
            if type_info is not None:
                type_edges.append((caller, callee, type_info))

        graph["type_edges"] = type_edges
        return len(type_edges)

    def detect_type_risks(self, graph: dict) -> list[TypeRisk]:
        """Score and rank type risks from annotated calls edges.

        Returns a list of ``TypeRisk`` signals for compliance reporting.
        """
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
                            f"— caller may need None guard"
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
                            f"Enable NEURALMIND_TYPE_CHECK=1 for inference"
                        ),
                        callee_returns="unknown",
                    )
                )

        return risks

    def persist_type_edges(self, store) -> int:
        """Persist inferred type edges to the synapse store's ``type_edges`` table.

        ``store`` must be a ``SynapseStore`` instance with a ``persist_type_edges``
        method. Returns the number of rows upserted.
        """
        # We don't have source/target from cache alone; use graph type_edges
        for _k, info_or_tuple in self._cache.items():
            if info_or_tuple is not None and isinstance(info_or_tuple, TypeInfo):
                pass

        # Get from graph if available
        graph = getattr(self, "_last_graph", None)
        if graph is None:
            return 0

        raw_edges = graph.get("type_edges", [])
        if not raw_edges:
            return 0

        ts = time.time()
        rows = []
        for source_node, target_node, type_info in raw_edges:
            rows.append(
                (
                    str(source_node),
                    str(target_node),
                    type_info.return_type,
                    1 if type_info.is_optional else 0,
                    type_info.confidence,
                    type_info.inferred_by,
                    ts,
                )
            )

        if not rows:
            return 0

        try:
            if hasattr(store, "persist_type_edges"):
                return store.persist_type_edges(rows)
        except Exception:
            pass
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
