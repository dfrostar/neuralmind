"""`neuralmind savings` counts queries and wakeups — nothing else.

The audit log records every action NeuralMind takes (build, search, MCP
calls, probes, ingestion, peer review...). Only a ``query`` is a turn that
would otherwise have loaded the whole codebase, and only a ``wakeup`` is the
session-start context; counting the rest as zero-token queries credited a
full baseline of "savings" per build or search and dragged the average
reduction toward zero. An MCP query logs both ``query`` and ``mcp_call``, so
it was counted twice. Stdlib-only, plus one end-to-end check on a real index.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from neuralmind import memory
from neuralmind.savings import compute_savings

BASE = 50_000  # naive_50k=True pins the baseline so the arithmetic is exact

# Every non-query, non-wakeup action the package writes to audit_events.jsonl
# (`grep -rn 'action="' neuralmind/`).
OTHER_ACTIONS = [
    "build",
    "search",
    "mcp_call",
    "mcp_call_denied",
    "probe",
    "ingest_document",
    "ingest_cmmc",
    "switch_backend",
    "auto_promote",
    "reject",
    "review_required",
    "storage_check",
]


def _audit(project: Path, records: list[dict]) -> None:
    path = project / ".neuralmind" / "audit_events.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    for i, rec in enumerate(records):
        lines.append(
            json.dumps(
                {
                    "category": "audit",
                    "status": "success",
                    "target": project.name,
                    "timestamp": f"2026-10-05T10:00:{i:02d}+00:00",
                    **rec,
                }
            )
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _query(question: str, tokens: int, **extra) -> dict:
    return {
        "action": "query",
        "details": {"question": question, "tokens": tokens, "search_hits": 3, **extra},
    }


class TestAuditLogCounting:
    def test_only_query_and_wakeup_actions_count(self, tmp_path: Path):
        records = [{"action": "build", "details": {"nodes": 122, "duration": 6.5}}]
        records.append(_query("how is an invoice paid?", 1_000))
        records.append({"action": "wakeup", "details": {"tokens": 600}})
        records += [{"action": a, "details": {"query": "x"}} for a in OTHER_ACTIONS]
        _audit(tmp_path, records)

        report = compute_savings(tmp_path, naive_50k=True)

        assert report["total_queries"] == 1
        assert report["total_wakeups"] == 1
        assert report["total_tokens_used"] == 1_600
        assert report["est_total_full_cost"] == 2 * BASE
        assert report["total_tokens_saved"] == 2 * BASE - 1_600
        assert report["avg_reduction_ratio"] == 50.0
        assert [q["query"] for q in report["recent_queries"]] == ["how is an invoice paid?"]

    def test_mcp_query_is_counted_once(self, tmp_path: Path):
        # The MCP server logs the tool call beside the query it ran.
        _audit(
            tmp_path,
            [
                {"action": "mcp_call", "details": {"tool": "neuralmind_query"}},
                _query("where is auth?", 2_000),
            ],
        )
        report = compute_savings(tmp_path, naive_50k=True)
        assert report["total_queries"] == 1
        assert report["total_tokens_saved"] == BASE - 2_000

    def test_log_with_no_queries_or_wakeups_reports_zero(self, tmp_path: Path):
        _audit(tmp_path, [{"action": a, "details": {}} for a in OTHER_ACTIONS])
        report = compute_savings(tmp_path, naive_50k=True)
        assert report["queries"] == 0
        assert report["total_tokens_saved"] == 0

    def test_read_only_queries_still_excluded(self, tmp_path: Path):
        _audit(
            tmp_path,
            [_query("usage", 1_000), _query("eval probe", 1_000, learn=False)],
        )
        report = compute_savings(tmp_path, naive_50k=True)
        assert report["total_queries"] == 1

    def test_avg_ratio_ignores_queries_without_tokens(self, tmp_path: Path):
        # A query logged without a token count has no ratio to average.
        _audit(tmp_path, [_query("a", 1_000), {"action": "query", "details": {"question": "b"}}])
        report = compute_savings(tmp_path, naive_50k=True)
        assert report["total_queries"] == 2
        assert report["avg_reduction_ratio"] == 50.0


class TestQueryEventsLogCounting:
    def _write(self, project: Path, events: list[dict]) -> None:
        path = memory.project_query_events_file(project)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("\n".join(json.dumps(e) for e in events) + "\n", encoding="utf-8")

    def test_only_query_and_wakeup_event_types_count(self, tmp_path: Path):
        self._write(
            tmp_path,
            [
                {
                    "event_type": "query",
                    "query": "q",
                    "retrieval_summary": {"tokens": 1_000, "reduction_ratio": 9.0},
                },
                {"event_type": "wakeup", "retrieval_summary": {"tokens": 500}},
                {"event_type": "feedback", "retrieval_summary": {}},
            ],
        )
        report = compute_savings(tmp_path, naive_50k=True)
        assert report["total_queries"] == 1
        assert report["total_wakeups"] == 1
        assert report["total_tokens_saved"] == 2 * BASE - 1_500
        assert report["avg_reduction_ratio"] == 50.0


@pytest.mark.integration
def test_real_build_query_wakeup_search_counts_one_query(tmp_path: Path):
    """The reported repro: build + 1 query + 1 wakeup + 1 search."""
    pytest.importorskip("turbovec")
    from neuralmind import graphgen

    if not graphgen.is_available():
        pytest.skip("tree-sitter not installed")
    from tests.test_index_freshness import _mind, _write_files

    _write_files(tmp_path, ["billing/invoices.py", "auth/handlers.py"])
    mind = _mind(tmp_path)
    mind.build()
    q = mind.query("invoices helper")
    w = mind.wakeup()
    mind.search("handlers")

    report = compute_savings(tmp_path, naive_50k=True)
    assert report["total_queries"] == 1
    assert report["total_wakeups"] == 1
    used = q.budget.total + w.budget.total
    assert report["total_tokens_used"] == used
    assert report["total_tokens_saved"] == 2 * BASE - used
