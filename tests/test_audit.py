"""Tests for audit trail and NIST RMF reporting."""

from neuralmind.audit import AuditTrail


def test_audit_trail_appends_events(tmp_path):
    audit = AuditTrail(tmp_path)
    event = audit.log_event(category="audit", action="query", actor="alice", target="in_memory")
    events = audit.list_events()
    assert len(events) == 1
    assert events[0]["event_id"] == event.event_id
    assert events[0]["actor"] == "alice"


def test_audit_filters_by_category_and_status(tmp_path):
    audit = AuditTrail(tmp_path)
    audit.log_event(category="security", action="rbac_check", status="success")
    audit.log_event(category="security", action="tool_call", status="denied")
    denied = audit.list_events(category="security", status="denied")
    assert len(denied) == 1
    assert denied[0]["action"] == "tool_call"


def test_nist_rmf_report_contains_control_counts(tmp_path):
    audit = AuditTrail(tmp_path)
    audit.log_event(category="security", action="rbac_check")
    audit.log_event(category="security", action="rate_limit_check")
    audit.log_event(category="backend", action="build")
    report = audit.generate_nist_rmf_report()
    assert report["rmf_step"] == "monitor"
    assert report["total_events"] == 3
    assert report["controls"]["AC-3"] >= 1
    assert report["controls"]["SI-4"] >= 1
    assert report["controls"]["AU-2"] >= 1
