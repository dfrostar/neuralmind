"""Tests for the type verification layer."""

from __future__ import annotations

import textwrap

import pytest

from neuralmind.type_verifier import (
    TypeInfo,
    TypeRisk,
    TypeVerifier,
    _is_optional_type,
    format_type_risks,
)


@pytest.fixture
def tmp_project(tmp_path):
    """Create a minimal Python project with type annotations."""
    project_dir = tmp_path / "myproject"
    project_dir.mkdir()

    src = project_dir / "module_a.py"
    src.write_text(textwrap.dedent("""
            from typing import Optional, Union, List

            def get_user(id: int) -> Optional[str]:
                if id > 0:
                    return "alice"
                return None

            def fetch_all() -> List[str]:
                return ["a", "b"]

            def no_annotation(x):
                return x

            def returns_none() -> None:
                pass

            def union_none(x: int) -> Union[int, None]:
                if x > 0:
                    return x
                return None

            def pipe_none(x: int) -> int | None:
                if x > 0:
                    return x
                return None
        """))

    caller = project_dir / "module_b.py"
    caller.write_text(textwrap.dedent("""
            from module_a import get_user, fetch_all, no_annotation

            def process():
                user = get_user(1)
                items = fetch_all()
                result = no_annotation("x")
                return user
        """))

    return project_dir


# --------------------------------------------------------------------------- #
# Test matrix from design doc
# --------------------------------------------------------------------------- #


def test_infer_optional_return(tmp_project):
    """def f() -> Optional[User] should produce TypeInfo with is_optional=True."""
    tv = TypeVerifier(tmp_project)
    info = tv.infer_return_type("module_a.py::get_user")
    assert info is not None
    assert info.return_type == "Optional[str]"
    assert info.is_optional is True
    assert info.confidence == 1.0
    assert info.inferred_by == "stdlib"


def test_infer_unannotated(tmp_project):
    """def f(): (no annotation) should return TypeInfo with return_type=None."""
    tv = TypeVerifier(tmp_project)
    info = tv.infer_return_type("module_a.py::no_annotation")
    assert info is not None
    assert info.return_type is None
    assert info.is_optional is False
    assert info.confidence == 0.0


def test_infer_list_return(tmp_project):
    """def f() -> List[str] should produce non-optional TypeInfo."""
    tv = TypeVerifier(tmp_project)
    info = tv.infer_return_type("module_a.py::fetch_all")
    assert info is not None
    assert info.return_type == "List[str]"
    assert info.is_optional is False
    assert info.confidence == 1.0


def test_infer_none_return(tmp_project):
    """def f() -> None should produce return_type='None'."""
    tv = TypeVerifier(tmp_project)
    info = tv.infer_return_type("module_a.py::returns_none")
    assert info is not None
    assert info.return_type == "None"
    assert info.is_optional is False


def test_infer_union_none(tmp_project):
    """def f() -> Union[int, None] should be detected as optional."""
    tv = TypeVerifier(tmp_project)
    info = tv.infer_return_type("module_a.py::union_none")
    assert info is not None
    assert info.is_optional is True


def test_infer_pipe_none(tmp_project):
    """def f() -> int | None should be detected as optional."""
    tv = TypeVerifier(tmp_project)
    info = tv.infer_return_type("module_a.py::pipe_none")
    assert info is not None
    assert info.is_optional is True


def test_is_optional_type_function():
    """Direct test of the _is_optional_type helper."""
    assert _is_optional_type("Optional[User]") is True
    assert _is_optional_type("Union[int, None]") is True
    assert _is_optional_type("Union[None, int]") is True
    assert _is_optional_type("int | None") is True
    assert _is_optional_type("None | int") is True
    assert _is_optional_type("None") is False
    assert _is_optional_type("List[str]") is False
    assert _is_optional_type("int") is False
    assert _is_optional_type(None) is False
    assert _is_optional_type("") is False


def test_augment_graph_count(tmp_project):
    """graph with 5 calls edges, 2 annotated with Optional should return 2 type_edges."""
    graph = {
        "edges": [
            {"source": "caller", "target": "module_a.py::get_user", "relation": "calls"},
            {"source": "caller", "target": "module_a.py::fetch_all", "relation": "calls"},
            {"source": "caller", "target": "module_a.py::no_annotation", "relation": "calls"},
            {"source": "caller", "target": "module_a.py::returns_none", "relation": "calls"},
            {"source": "caller", "target": "module_a.py::union_none", "relation": "calls"},
        ]
    }
    tv = TypeVerifier(tmp_project)
    count = tv.augment_graph(graph)
    assert count == 5
    assert "type_edges" in graph
    assert len(graph["type_edges"]) == 5


def test_augment_graph_empty(tmp_project):
    """Empty graph should return 0 type_edges."""
    tv = TypeVerifier(tmp_project)
    count = tv.augment_graph({})
    assert count == 0


def test_detect_risks_flags_optional(tmp_project):
    """type_edge with is_optional=1 should produce TypeRisk with severity='warn'."""
    graph = {
        "type_edges": [
            ("caller", "module_a.py::get_user", TypeInfo("Optional[str]", True, 1.0, "stdlib")),
        ]
    }
    tv = TypeVerifier(tmp_project)
    risks = tv.detect_type_risks(graph)
    assert len(risks) == 1
    assert risks[0].severity == "warn"
    assert risks[0].risk_type == "optional_return"
    assert risks[0].caller_id == "caller"
    assert risks[0].callee_id == "module_a.py::get_user"
    assert risks[0].callee_returns == "Optional[str]"


def test_detect_risks_clean(tmp_project):
    """type_edge with is_optional=0 should produce no risk."""
    graph = {
        "type_edges": [
            ("caller", "module_a.py::fetch_all", TypeInfo("List[str]", False, 1.0, "stdlib")),
        ]
    }
    tv = TypeVerifier(tmp_project)
    risks = tv.detect_type_risks(graph)
    assert len(risks) == 0


def test_detect_risks_unannotated(tmp_project):
    """Unannotated function should produce info-level any_fallthrough risk."""
    graph = {
        "type_edges": [
            ("caller", "unknown_func", TypeInfo(None, False, 0.0, "stdlib")),
        ]
    }
    tv = TypeVerifier(tmp_project)
    risks = tv.detect_type_risks(graph)
    assert len(risks) == 1
    assert risks[0].severity == "info"
    assert risks[0].risk_type == "any_fallthrough"


def test_detect_risks_implicit_none(tmp_project):
    """Explicit None return should produce info-level implicit_none risk."""
    graph = {
        "type_edges": [
            ("caller", "module_a.py::returns_none", TypeInfo("None", False, 1.0, "stdlib")),
        ]
    }
    tv = TypeVerifier(tmp_project)
    risks = tv.detect_type_risks(graph)
    assert len(risks) == 1
    assert risks[0].severity == "info"
    assert risks[0].risk_type == "implicit_none"


def test_persist_type_edges(tmp_project, tmp_path):
    """3 type_edge tuples should result in 3 rows in type_edges table."""
    from neuralmind.synapses import SynapseStore

    store = SynapseStore(tmp_path / "test.db")
    edges = [
        ("A", "B", "Optional[str]", 1, 1.0, "stdlib", 1000.0),
        ("C", "D", "List[int]", 0, 1.0, "stdlib", 1000.0),
        ("E", "F", None, 0, 0.0, "stdlib", 1000.0),
    ]
    count = store.persist_type_edges(edges)
    assert count == 3

    with store._connect() as conn:
        rows = conn.execute("SELECT COUNT(*) FROM type_edges").fetchone()[0]
    assert rows == 3


def test_fail_open_on_import_error(tmp_project):
    """If typing import fails, augment_graph returns 0 without crashing."""
    tv = TypeVerifier(tmp_project)
    # Corrupt the project path so it can't parse
    tv.project_path = tmp_project / "nonexistent"
    count = tv.augment_graph({"edges": []})
    assert count == 0


def test_format_type_risks_contains_severity():
    """format_type_risks should include severity labels."""
    risks = [
        TypeRisk("A", "B", "optional_return", "warn", "detail", "Optional[str]"),
        TypeRisk("C", "D", "any_fallthrough", "info", "detail2", "unknown"),
    ]
    report = format_type_risks(risks)
    assert "WARN" in report
    assert "INFO" in report
    assert "Optional[str]" in report


def test_format_type_risks_empty():
    """Empty risks should produce a clean report."""
    report = format_type_risks([])
    assert "0 signals" in report


def test_infer_return_type_nonexistent_function(tmp_project):
    """Inference for a function that doesn't exist returns None."""
    tv = TypeVerifier(tmp_project)
    info = tv.infer_return_type("module_a.py::nonexistent_func")
    assert info is None


def test_augment_graph_with_bare_name(tmp_project):
    """Node ids without '::' should still work if function is findable."""
    graph = {
        "edges": [
            {"source": "caller", "target": "get_user", "relation": "calls"},
        ]
    }
    tv = TypeVerifier(tmp_project)
    count = tv.augment_graph(graph)
    # Should find it by searching all .py files
    assert count == 1
    type_edges = graph["type_edges"]
    assert type_edges[0][2].is_optional is True


def test_all_optional_returns_flagged(tmp_project):
    """All functions with Optional[...] return type produce TypeRisk with severity >= warn."""
    tv = TypeVerifier(tmp_project)
    graph = {
        "type_edges": [
            ("caller", "module_a.py::get_user", TypeInfo("Optional[str]", True, 1.0, "stdlib")),
            (
                "caller",
                "module_a.py::union_none",
                TypeInfo("Union[int, None]", True, 1.0, "stdlib"),
            ),
            ("caller", "module_a.py::pipe_none", TypeInfo("int | None", True, 1.0, "stdlib")),
        ]
    }
    risks = tv.detect_type_risks(graph)
    assert len(risks) == 3
    for r in risks:
        assert r.severity in ("warn", "high")


def test_unannotated_returns_unknown(tmp_project):
    """Unannotated functions produce confidence=0.0, not a fake inferred type."""
    tv = TypeVerifier(tmp_project)
    info = tv.infer_return_type("module_a.py::no_annotation")
    assert info is not None
    assert info.return_type is None
    assert info.confidence == 0.0
    assert info.is_optional is False
