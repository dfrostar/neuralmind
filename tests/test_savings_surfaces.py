"""The savings report is served by every surface: CLI, MCP server, daemon.

The aggregation itself lives in neuralmind.savings.compute_savings; these
tests pin the shared module's contract and that both server surfaces expose
it. Stdlib-only (plus the package under test)."""

from __future__ import annotations

import json
from pathlib import Path

from neuralmind import memory
from neuralmind.savings import BASELINE_TOKENS_PER_QUERY, compute_savings


def _write_memory_event(project: Path, tokens: int = 500, ratio: float = 100.0) -> None:
    log_file = memory.project_query_events_file(project)
    log_file.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "event_type": "query",
        "timestamp": "2025-01-01T00:00:00+00:00",
        "project_path": str(project),
        "session_id": "s1",
        "query": "test question",
        "retrieval_summary": {"tokens": tokens, "reduction_ratio": ratio},
    }
    log_file.write_text(json.dumps(event) + "\n")


class TestComputeSavings:
    def test_missing_log_reports_in_band(self, tmp_path: Path):
        report = compute_savings(tmp_path)
        assert report["error"] == "no event log found"
        assert "path" in report

    def test_aggregates_memory_format_events(self, tmp_path: Path):
        _write_memory_event(tmp_path, tokens=500)
        report = compute_savings(tmp_path)
        assert report["total_queries"] == 1
        assert report["total_tokens_used"] == 500
        assert report["total_tokens_saved"] == BASELINE_TOKENS_PER_QUERY - 500
        assert report["recent_queries"][0]["query"] == "test question"
        assert "dollar_savings" not in report

    def test_cost_estimate_included_on_request(self, tmp_path: Path):
        _write_memory_event(tmp_path, tokens=500)
        report = compute_savings(tmp_path, cost=True, queries_per_day=10)
        dollars = report["dollar_savings"]
        assert dollars["estimated"] is True
        assert dollars["queries_per_day"] == 10
        assert dollars["saved_total"] > 0

    def test_audit_log_preferred_when_present(self, tmp_path: Path):
        audit = tmp_path / ".neuralmind" / "audit_events.jsonl"
        audit.parent.mkdir(parents=True, exist_ok=True)
        audit.write_text(
            json.dumps(
                {
                    "category": "query",
                    "action": "query",
                    "timestamp": "2025-01-01T00:00:00+00:00",
                    "details": {"question": "from audit", "tokens": 1000, "search_hits": 3},
                }
            )
            + "\n"
        )
        report = compute_savings(tmp_path)
        assert report["total_queries"] == 1
        assert report["total_tokens_used"] == 1000
        assert report["recent_queries"][0]["query"] == "from audit"


class TestServerSurfaces:
    def test_mcp_tool_returns_report(self, tmp_path: Path):
        from neuralmind.mcp_server import TOOLS, tool_savings

        _write_memory_event(tmp_path, tokens=500)
        report = tool_savings(str(tmp_path))
        assert report["total_queries"] == 1
        assert any(t["name"] == "neuralmind_savings" for t in TOOLS)

    def test_daemon_handler_returns_report(self, tmp_path: Path):
        from neuralmind.daemon import _savings

        _write_memory_event(tmp_path, tokens=500)
        report = _savings(None, str(tmp_path), False, None, 100)
        assert report["total_queries"] == 1
