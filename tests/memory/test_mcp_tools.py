"""Unit tests for memory MCP tools — TRD 10.1 (tool validation, error handling)."""

from __future__ import annotations

import json

import pytest

from neuralmind.memory.mcp_tools import (
    TOOLS,
    handle_tool_call,
    tool_audit_decisions,
    tool_query_decisions,
    tool_record_decision,
)


@pytest.fixture
def project(tmp_path):
    (tmp_path / "src.py").write_text("x = 1\n")
    return str(tmp_path)


# ------------------------------------------------------------------ #
# Tool schema validation
# ------------------------------------------------------------------ #


def test_tools_have_required_fields():
    assert len(TOOLS) >= 4
    for tool in TOOLS:
        assert tool["name"].startswith("neuralmind_")
        assert "description" in tool
        schema = tool["inputSchema"]
        assert schema["type"] == "object"
        assert isinstance(schema["required"], list)
        assert "project_path" in schema["required"]


def test_tool_names_unique():
    names = [t["name"] for t in TOOLS]
    assert len(names) == len(set(names))


# ------------------------------------------------------------------ #
# Handler dispatch
# ------------------------------------------------------------------ #


def test_handle_tool_call_unknown_tool():
    result = json.loads(handle_tool_call("neuralmind_nonexistent", {}))
    assert "error" in result


def test_handle_tool_call_query(project):
    tool_record_decision(project, title="MCP decision", rationale="why", commit_sha="a" * 40)
    out = json.loads(
        handle_tool_call(
            "neuralmind_query_decisions", {"project_path": project, "query": "MCP decision"}
        )
    )
    assert out["count"] >= 1
    assert any(d["title"] == "MCP decision" for d in out["decisions"])


def test_handle_tool_call_missing_required_args(project):
    out = json.loads(handle_tool_call("neuralmind_query_decisions", {"project_path": project}))
    assert "error" in out


def test_handle_tool_call_record_and_invalidate(project):
    out = json.loads(
        handle_tool_call(
            "neuralmind_record_decision",
            {
                "project_path": project,
                "title": "Recorded via MCP",
                "rationale": "why not",
                "commit_sha": "b" * 40,
                "files": ["a.py"],
            },
        )
    )
    assert out.get("id"), "recorded decision must have an id"

    # find its id via audit
    audit = json.loads(handle_tool_call("neuralmind_audit_decisions", {"project_path": project}))
    dec_id = None
    for d in audit.get("decisions", []):
        if d.get("title") == "Recorded via MCP":
            dec_id = d["id"]
            break
    assert dec_id, "recorded decision must appear in audit"

    inv = json.loads(
        handle_tool_call(
            "neuralmind_invalidate_decision",
            {"project_path": project, "decision_id": dec_id, "reason": "test"},
        )
    )
    assert "error" not in inv


def test_handle_tool_call_record_passes_through_all_fields(project):
    """Regression: the MCP tool used to silently drop decision_type,
    confidence, evidence, rejected_alternatives, and tags, and only
    recognized the file list under "files" while the docs (and the
    direct tool_record_decision/store.record API) call it
    "files_affected" — so a caller following the documented schema had
    its file list silently ignored too. Verify the wire path round-trips
    every field DecisionStore.record() actually supports.
    """
    out = json.loads(
        handle_tool_call(
            "neuralmind_record_decision",
            {
                "project_path": project,
                "title": "Full-fidelity record",
                "rationale": "why",
                "commit_sha": "c" * 40,
                "files_affected": ["a.py", "b.py"],
                "decision_type": "DEPENDENCY",
                "confidence": 0.42,
                "evidence": ["docs/SECURITY.md#L10"],
                "rejected_alternatives": ["do nothing"],
                "tags": ["auth"],
            },
        )
    )
    assert out["files_affected"] == ["a.py", "b.py"]
    assert out["decision_type"] == "DEPENDENCY"
    assert out["confidence"] == 0.42
    assert out["evidence"] == ["docs/SECURITY.md#L10"]
    assert out["rejected_alternatives"] == ["do nothing"]
    assert out["tags"] == ["auth"]


def test_handle_tool_call_record_legacy_files_key_still_works(project):
    """The pre-fix "files" key must keep working for any existing caller."""
    out = json.loads(
        handle_tool_call(
            "neuralmind_record_decision",
            {
                "project_path": project,
                "title": "Legacy files key",
                "rationale": "why",
                "files": ["legacy.py"],
            },
        )
    )
    assert out["files_affected"] == ["legacy.py"]


def test_record_decision_schema_advertises_all_store_fields():
    """The inputSchema an MCP client introspects must match what the
    handler actually accepts — this is exactly the gap that let
    confidence/decision_type/evidence/rejected_alternatives be silently
    dropped even though DecisionStore.record() always supported them."""
    schema = next(t for t in TOOLS if t["name"] == "neuralmind_record_decision")["inputSchema"]
    for field in (
        "files_affected",
        "decision_type",
        "confidence",
        "evidence",
        "rejected_alternatives",
        "tags",
    ):
        assert (
            field in schema["properties"]
        ), f"{field} missing from neuralmind_record_decision schema"


# ------------------------------------------------------------------ #
# Tool functions
# ------------------------------------------------------------------ #


def test_query_returns_empty_on_fresh_project(tmp_path):
    result = tool_query_decisions(str(tmp_path), "anything")
    assert result["count"] == 0
    assert result["decisions"] == []


def test_audit_stale_only(project):
    """stale_only uses store.audit() which is age-based; verify plumbing."""

    rec = tool_record_decision(project, title="Audit me", rationale="r", commit_sha="c" * 40)
    result = tool_audit_decisions(project, stale_only=True)
    assert result["count"] == 0  # fresh decision is not stale by age
    assert all(d.get("status") == "ACTIVE" for d in result["decisions"])
    # full audit lists everything
    full = tool_audit_decisions(project)
    assert any(d["id"] == rec["id"] for d in full["decisions"])


def test_invalidate_via_mcp_then_query_excludes(project):
    rec = tool_record_decision(
        project, title="Invalidated marker ZZ", rationale="r", commit_sha="c" * 40
    )
    from neuralmind.memory.mcp_tools import tool_invalidate_decision

    tool_invalidate_decision(project, rec["id"], reason="test")
    out = json.loads(
        handle_tool_call(
            "neuralmind_query_decisions",
            {"project_path": project, "query": "Invalidated marker ZZ"},
        )
    )
    assert out["count"] == 0, "invalidated decisions must not surface in default query"


def test_handle_tool_call_non_json_args_returns_error():
    out = json.loads(handle_tool_call("neuralmind_query_decisions", {"query": 123}))
    assert "error" in out
