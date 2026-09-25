"""Tests for the 3-layer progressive decision retrieval (v4.3.0, Component B).

Layer 1 — neuralmind_memory_search: compact index rows.
Layer 2 — neuralmind_memory_timeline: chronological context.
Layer 3 — neuralmind_memory_get: full records, batch-capped at 20.

Covers the build-spec acceptance criteria:
- workflow answers a query in <=3 tool calls
- memory_get rejects >20 ids (forces filtering)
- compact rows are compact (no rationale/evidence fields)
- timeline returns chronological neighbors around an anchor
- missing ids are reported, not silently dropped
"""

from __future__ import annotations

import json

from neuralmind.memory.mcp_tools import (
    MEMORY_GET_MAX_IDS,
    TOOLS,
    handle_tool_call,
    tool_memory_get,
    tool_memory_search,
    tool_memory_timeline,
)
from neuralmind.memory.store import DecisionStore


def _seed(project_path, n: int = 5) -> list[str]:
    """Seed n decisions with distinct titles; return their ids in order."""
    store = DecisionStore(str(project_path))
    ids = []
    topics = ["auth", "database", "api", "caching", "logging", "queueing", "search"]
    for i in range(n):
        rec = store.record(
            title=f"Choose {topics[i % len(topics)]} approach {i}",
            rationale=f"Rationale number {i} for the {topics[i % len(topics)]} decision.",
            commit_sha=f"abc{i:04d}",
            files_affected=[f"src/mod{i}.py"],
        )
        ids.append(rec.id)
    return ids


class TestLayer1Search:
    def test_search_returns_compact_rows(self, tmp_path):
        _seed(tmp_path, 3)
        result = tool_memory_search(str(tmp_path), "auth")
        assert result["count"] >= 1
        row = result["results"][0]
        # Compact contract: exactly these keys, no rationale/evidence.
        assert set(row.keys()) == {
            "id",
            "title",
            "status",
            "type",
            "commit",
            "updated",
            "files",
        }
        assert "rationale" not in row
        assert row["commit"].startswith("abc")

    def test_search_limit_capped_at_25(self, tmp_path):
        _seed(tmp_path, 3)
        result = tool_memory_search(str(tmp_path), "approach", limit=100)
        assert result["count"] <= 25

    def test_search_next_hint_present(self, tmp_path):
        _seed(tmp_path, 2)
        result = tool_memory_search(str(tmp_path), "auth")
        assert "memory_get" in result["next"]

    def test_search_empty_project(self, tmp_path):
        result = tool_memory_search(str(tmp_path), "anything")
        assert result["count"] == 0
        assert result["results"] == []


class TestLayer2Timeline:
    def test_timeline_by_id_returns_neighbors(self, tmp_path):
        ids = _seed(tmp_path, 5)
        # Anchor on the middle decision (index 2).
        result = tool_memory_timeline(str(tmp_path), decision_id=ids[2])
        assert result["anchor"]["id"] == ids[2]
        assert len(result["before"]) == 2
        assert len(result["after"]) == 2
        # Chronological: before[0] is oldest.
        assert result["before"][0]["id"] == ids[0]
        assert result["before"][1]["id"] == ids[1]
        assert result["after"][0]["id"] == ids[3]

    def test_timeline_by_query_anchors_on_top_hit(self, tmp_path):
        _seed(tmp_path, 4)
        result = tool_memory_timeline(str(tmp_path), query="database")
        assert "anchor" in result
        assert "database" in result["anchor"]["title"].lower()

    def test_timeline_requires_id_or_query(self, tmp_path):
        result = tool_memory_timeline(str(tmp_path))
        assert "error" in result

    def test_timeline_unknown_query(self, tmp_path):
        _seed(tmp_path, 2)
        result = tool_memory_timeline(str(tmp_path), query="zzz-no-such-topic-qx")
        assert "error" in result

    def test_timeline_edge_anchor(self, tmp_path):
        ids = _seed(tmp_path, 3)
        result = tool_memory_timeline(str(tmp_path), decision_id=ids[0])
        assert result["before"] == []
        assert len(result["after"]) == 2


class TestLayer3Get:
    def test_get_returns_full_records(self, tmp_path):
        ids = _seed(tmp_path, 2)
        result = tool_memory_get(str(tmp_path), [ids[0]])
        assert result["count"] == 1
        rec = result["decisions"][0]
        # Full-record contract: rationale present.
        assert "Rationale number 0" in rec["rationale"]
        assert rec["files_affected"] == ["src/mod0.py"]

    def test_get_batch_cap_enforced(self, tmp_path):
        ids = _seed(tmp_path, 3)
        too_many = ids * (MEMORY_GET_MAX_IDS // len(ids) + 1)
        result = tool_memory_get(str(tmp_path), too_many[: MEMORY_GET_MAX_IDS + 1])
        assert "error" in result
        assert str(MEMORY_GET_MAX_IDS) in result["error"]

    def test_get_reports_missing_ids(self, tmp_path):
        ids = _seed(tmp_path, 1)
        result = tool_memory_get(str(tmp_path), [ids[0], "nonexistent-id"])
        assert result["count"] == 1
        assert result["missing"] == ["nonexistent-id"]

    def test_get_empty_ids_rejected(self, tmp_path):
        result = tool_memory_get(str(tmp_path), [])
        assert "error" in result


class TestThreeLayerWorkflow:
    """Build-spec B.3: the full workflow in <=3 calls."""

    def test_workflow_three_calls(self, tmp_path):
        _seed(tmp_path, 6)
        # Call 1: search
        s = tool_memory_search(str(tmp_path), "auth")
        assert s["count"] >= 1
        hit = s["results"][0]["id"]
        # Call 2 (optional): timeline context
        t = tool_memory_timeline(str(tmp_path), decision_id=hit)
        assert t["anchor"]["id"] == hit
        # Call 3: full record
        g = tool_memory_get(str(tmp_path), [hit])
        assert g["count"] == 1
        assert "rationale" in g["decisions"][0]

    def test_dispatch_via_handle_tool_call(self, tmp_path):
        _seed(tmp_path, 2)
        out = json.loads(
            handle_tool_call(
                "neuralmind_memory_search",
                {"project_path": str(tmp_path), "query": "auth"},
            )
        )
        assert out["count"] >= 1
        out2 = json.loads(
            handle_tool_call(
                "neuralmind_memory_get",
                {"project_path": str(tmp_path), "ids": [out["results"][0]["id"]]},
            )
        )
        assert out2["count"] == 1


class TestToolRegistration:
    def test_three_new_tools_registered(self):
        names = {t["name"] for t in TOOLS}
        assert "neuralmind_memory_search" in names
        assert "neuralmind_memory_timeline" in names
        assert "neuralmind_memory_get" in names

    def test_every_tool_has_required_fields(self):
        for tool in TOOLS:
            assert "name" in tool
            assert "description" in tool
            assert "inputSchema" in tool

    def test_tools_list_count(self):
        # 4 original memory tools + 3 progressive-retrieval tools.
        assert len(TOOLS) == 7
