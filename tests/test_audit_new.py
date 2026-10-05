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


def _write_lines(trail, records):
    trail.events_file.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in records))


def _forge(record, *, strip_hash):
    forged = dict(record, details={"question": "FORGED"})
    if strip_hash:
        forged.pop("sha256", None)
        forged.pop("prev_sha256", None)
    return forged


def _chained_trail(tmp_path, n=5):
    trail = AuditTrail(tmp_path)
    for i in range(n):
        trail.append_event("audit", "query", actor="alice", details={"question": f"q{i}"})
    return trail, trail.read_events()


def test_verify_rejects_last_record_edited_with_hash_stripped(tmp_path):
    """Dropping sha256 from an edited tail record used to pass as a legacy line."""
    trail, records = _chained_trail(tmp_path)
    _write_lines(trail, records[:4] + [_forge(records[4], strip_hash=True)])

    result = trail.verify()
    assert result["ok"] is False
    assert result["first_bad_line"] == 5
    assert "no sha256" in result["reason"]


def test_verify_rejects_stripped_suffix(tmp_path):
    trail, records = _chained_trail(tmp_path)
    tail = [_forge(r, strip_hash=True) for r in records[3:]]
    _write_lines(trail, records[:3] + tail)

    result = trail.verify()
    assert result["ok"] is False
    assert result["first_bad_line"] == 4


def test_verify_rejects_forged_record_appended_without_hash(tmp_path):
    trail, records = _chained_trail(tmp_path)
    forged = {
        "timestamp": "2026-10-04T00:00:00+00:00",
        "category": "audit",
        "action": "query",
        "actor": "mallory",
        "status": "success",
        "target": "x",
        "details": {},
    }
    _write_lines(trail, records + [forged])

    result = trail.verify()
    assert result["ok"] is False
    assert result["first_bad_line"] == 6


def test_verify_tamper_stays_visible_after_new_appends(tmp_path):
    """A later legitimate append restarts nothing: the hashless record still fails."""
    trail, records = _chained_trail(tmp_path, n=3)
    _write_lines(trail, records + [_forge(records[2], strip_hash=True)])
    trail.append_event("audit", "query", actor="alice")

    result = trail.verify()
    assert result["ok"] is False
    assert result["first_bad_line"] == 4


def test_verify_still_rejects_hash_stripped_mid_log(tmp_path):
    trail, records = _chained_trail(tmp_path)
    _write_lines(trail, records[:2] + [_forge(records[2], strip_hash=True)] + records[3:])

    result = trail.verify()
    assert result["ok"] is False
    assert result["first_bad_line"] == 3


def test_verify_counts_legacy_prefix_before_chain(tmp_path):
    """Pre-chain records stay accepted, and the result says the chain doesn't cover them."""
    trail = AuditTrail(tmp_path)
    trail.events_file.parent.mkdir(parents=True)
    legacy = {
        "category": "audit",
        "action": "query",
        "actor": "legacy",
        "status": "success",
        "target": "",
        "details": {},
        "timestamp": "2020-01-01T00:00:00+00:00",
    }
    _write_lines(trail, [legacy, dict(legacy, action="search")])
    trail.append_event("audit", "query", actor="alice")
    trail.append_event("audit", "search", actor="alice")

    result = trail.verify()
    assert result["ok"] is True
    assert result["unchained"] == 2
    assert result["total"] == 4


def test_verify_cannot_detect_records_deleted_from_the_end(tmp_path):
    """Known limit, kept as a test so the docs never claim otherwise."""
    trail, records = _chained_trail(tmp_path)
    _write_lines(trail, records[:3])

    assert trail.verify()["ok"] is True


def test_rotated_log_verifies_from_its_continuation_marker(temp_project):
    trail = AuditTrail(temp_project)
    trail.append_event("audit", "query")
    trail.append_event("audit", "search")
    rotated = trail.rotate(max_bytes=10, keep_days=90)
    trail.append_event("audit", "query")

    result = trail.verify()
    assert result["ok"] is True
    assert result["total"] == 2
    assert result["continues_from"] == rotated["archived_to"].rsplit("/", 1)[-1]
