"""Tests for neuralmind.audit."""

from neuralmind.audit import AuditTrail


def test_audit_trail_append_only_jsonl(temp_project):
    trail = AuditTrail(temp_project)
    trail.append_event("audit", "query", actor="user", status="success", target="project")
    trail.append_event(
        "backend", "switch_backend", actor="system", status="success", target="project"
    )

    events = trail.read_events()
    assert len(events) == 2
    assert events[0]["action"] == "query"
    assert events[1]["action"] == "switch_backend"


def test_audit_nist_rmf_summary_rollups(temp_project):
    trail = AuditTrail(temp_project)
    trail.append_event("audit", "query", status="success")
    trail.append_event("security", "mcp_call_denied", status="denied")
    trail.append_event("backend", "switch_backend", status="failure")

    summary = trail.nist_rmf_summary()
    assert summary["events_total"] == 3
    assert summary["by_category"]["audit"] == 1
    assert summary["by_category"]["security"] == 1
    assert summary["by_status"]["success"] == 1
    assert summary["by_status"]["denied"] == 1
    assert summary["controls"]["AU"] == 3
    assert summary["controls"]["AC"] >= 1
    assert summary["controls"]["SI"] >= 1
