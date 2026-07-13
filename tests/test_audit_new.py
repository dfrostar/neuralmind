"""Tests for neuralmind.audit — new B-Audit features: actor resolution, hash chain, search, export, rotate."""

import json

from neuralmind.audit import AuditTrail, _resolve_actor


def test_audit_sha256_hash_chain(temp_project):
    """Each event must contain a hash of the prior event — tamper-evident chain."""
    trail = AuditTrail(temp_project)
    e1 = trail.append_event("audit", "query", actor="alice")
    e2 = trail.append_event("audit", "search", actor="alice")
    e3 = trail.append_event("audit", "query", actor="bob")

    for ev in (e1, e2, e3):
        assert "sha256" in ev
        assert len(ev["sha256"]) == 64

    assert e1["prev_sha256"] == "0" * 64
    assert e2["prev_sha256"] == e1["sha256"]
    assert e3["prev_sha256"] == e2["sha256"]

    result = trail.verify()
    assert result["ok"] is True
    assert result["first_bad_line"] is None
    assert result["total"] == 3


def test_audit_hash_chain_detects_tampering(tmp_path):
    """verify() detects a tampered line in the chain."""
    trail = AuditTrail(tmp_path)
    trail.append_event("audit", "query", actor="alice")
    trail.append_event("audit", "search", actor="alice")

    events_file = trail.events_file
    lines = events_file.read_text().strip().split("\n")
    obj = json.loads(lines[1])
    obj["action"] = "TAMPERED"
    lines[1] = json.dumps(obj)
    events_file.write_text("\n".join(lines) + "\n")

    result = trail.verify()
    assert result["ok"] is False
    assert result["first_bad_line"] == 2


def test_audit_verify_accepts_legacy_unchained_file(tmp_path):
    """Legacy events (pre-upgrade) are accepted as TOFU seed."""
    trail = AuditTrail(tmp_path)
    events_file = tmp_path / ".neuralmind" / "audit_events.jsonl"
    events_file.parent.mkdir(parents=True)
    legacy1 = {
        "category": "audit",
        "action": "query",
        "actor": "legacy",
        "status": "success",
        "target": "",
        "details": {},
        "timestamp": "2020-01-01T00:00:00+00:00",
    }
    legacy2 = {
        "category": "audit",
        "action": "search",
        "actor": "legacy",
        "status": "success",
        "target": "",
        "details": {},
        "timestamp": "2020-01-01T00:01:00+00:00",
    }
    events_file.write_text(json.dumps(legacy1) + "\n" + json.dumps(legacy2) + "\n")

    result = trail.verify()
    assert result["ok"] is True


def test_resolve_actor_priority():
    """Resolution order: explicit > env > OS > 'system'."""
    import os

    os.environ.pop("NEURALMIND_ACTOR", None)
    os.environ.pop("LOGNAME", None)
    os.environ.pop("USER", None)
    assert _resolve_actor("alice") == "alice"
    os.environ["NEURALMIND_ACTOR"] = "env-var"
    assert _resolve_actor(None) == "env-var"
    os.environ.pop("NEURALMIND_ACTOR")
    os.environ["LOGNAME"] = "login-name"
    assert _resolve_actor(None) == "login-name"
    os.environ.pop("LOGNAME")
    os.environ["USER"] = "user-name"
    assert _resolve_actor(None) == "user-name"
    os.environ.pop("USER")
    assert _resolve_actor(None) == "system"


def test_audit_search_filters(temp_project):
    """trail.search() filters by category, action, actor."""
    trail = AuditTrail(temp_project)
    trail.append_event("audit", "search", actor="alice")
    trail.append_event("audit", "query", actor="alice")
    trail.append_event("security", "mcp_call", actor="bob")
    trail.append_event("backend", "build", actor="system")

    assert len(trail.search(category="audit")) == 2
    assert len(trail.search(category="security")) == 1
    assert len(trail.search(actor="alice")) == 2
    assert len(trail.search(actor="bob")) == 1
    assert len(trail.search(action="build")) == 1
    assert len(trail.search(category="audit", actor="bob")) == 0


def test_audit_export_formats(temp_project):
    """export() yields JSONL by default or CEF lines."""
    trail = AuditTrail(temp_project)
    trail.append_event("security", "mcp_call_denied", actor="eve", status="denied")
    trail.append_event("audit", "query", actor="alice")

    lines = list(trail.export(format="jsonl"))
    assert len(lines) == 2
    parsed = json.loads(lines[0])
    assert parsed["action"] == "mcp_call_denied"

    cef_lines = list(trail.export(format="cef"))
    assert len(cef_lines) == 2
    assert cef_lines[0].startswith("CEF:0|NeuralMind|audit_trail|")
    assert "suser=eve" in cef_lines[0]


def test_audit_rotate_archives_oversized_file(temp_project):
    """rotate() archives oversized files, prunes old archives."""
    trail = AuditTrail(temp_project)
    trail.append_event("audit", "query")
    trail.append_event("audit", "search")

    result = trail.rotate(max_bytes=10, keep_days=90)
    assert result["rotated"] is True
    assert result["archived_to"] is not None

    events = trail.read_events()
    assert len(events) == 1
    assert events[0]["action"] == "rotation_continuation"


def test_audit_actor_role_and_ip_address(temp_project):
    """actor_role and ip_address passthrough."""
    trail = AuditTrail(temp_project)
    ev = trail.append_event(
        "security", "mcp_call", actor="alice", actor_role="admin", ip_address="10.0.0.1"
    )
    assert ev["actor_role"] == "admin"
    assert ev["ip_address"] == "10.0.0.1"
    events = trail.read_events()
    assert events[0]["actor_role"] == "admin"
    assert events[0]["ip_address"] == "10.0.0.1"
