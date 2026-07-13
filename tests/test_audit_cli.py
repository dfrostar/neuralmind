"""Tests for neuralmind.cli audit subcommands."""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from neuralmind.audit import AuditTrail
from neuralmind.cli import cmd_audit_export, cmd_audit_verify


class AuditExportArgs:
    def __init__(self, tmp, **kw):
        self.project_path = str(tmp)
        self.format = kw.get("format", "jsonl")
        self.category = kw.get("category", None)
        self.action = kw.get("action", None)
        self.actor = kw.get("actor", None)
        self.since = kw.get("since", None)
        self.until = kw.get("until", None)
        self.output = kw.get("output", None)


class AuditVerifyArgs:
    def __init__(self, tmp):
        self.project_path = str(tmp)
        self.json = False


@pytest.fixture
def audit_trail(tmp_path):
    trail = AuditTrail(tmp_path)
    trail.append_event("security", "mcp_call_denied", actor="eve", status="denied")
    trail.append_event("audit", "query", actor="alice")
    trail.append_event("audit", "search", actor="bob")
    return trail


def test_cmd_audit_export_jsonl(audit_trail, tmp_path):
    args = AuditExportArgs(tmp_path)
    with patch("sys.stdout.write") as mock_write:
        cmd_audit_export(args)
    written = "".join(call.args[0] for call in mock_write.call_args_list)
    lines = [l for l in written.strip().split("\n") if l.strip()]
    assert len(lines) == 3
    parsed = json.loads(lines[0])
    assert parsed["action"] == "mcp_call_denied"


def test_cmd_audit_export_cef(audit_trail, tmp_path):
    args = AuditExportArgs(tmp_path, format="cef")
    with patch("sys.stdout.write") as mock_write:
        cmd_audit_export(args)
    written = "".join(call.args[0] for call in mock_write.call_args_list)
    lines = [l for l in written.strip().split("\n") if l.strip()]
    assert len(lines) == 3
    assert lines[0].startswith("CEF:0|NeuralMind|audit_trail|")
    assert "suser=eve" in lines[0]


def test_cmd_audit_export_to_file(audit_trail, tmp_path):
    out = tmp_path / "out.jsonl"
    args = AuditExportArgs(tmp_path, output=out)
    cmd_audit_export(args)
    assert out.exists()
    lines = out.read_text().strip().split("\n")
    assert len(lines) == 3


def test_cmd_audit_verify_ok(audit_trail, tmp_path):
    args = AuditVerifyArgs(tmp_path)
    with patch("builtins.print") as mock_print:
        cmd_audit_verify(args)  # should not raise
    output = " ".join(str(call.args[0]) for call in mock_print.call_args_list)
    assert "OK" in output


def test_cmd_audit_verify_tamper_fails(audit_trail, tmp_path):
    events_file = tmp_path / ".neuralmind" / "audit_events.jsonl"
    data = events_file.read_text()
    data = data.replace("query", "SURPRIZY", 1)
    events_file.write_text(data)

    args = AuditVerifyArgs(tmp_path)
    with pytest.raises(SystemExit) as exc_info:
        cmd_audit_verify(args)
    assert exc_info.value.code == 1


def test_cmd_audit_verify_json_mode(audit_trail, tmp_path):
    args = AuditVerifyArgs(tmp_path)
    args.json = True
    with pytest.raises(SystemExit) as exc_info:
        with patch("builtins.print") as mock_print:
            cmd_audit_verify(args)
        output = "".join(str(call.args[0]) for call in mock_print.call_args_list)
        result = json.loads(output)
        assert result["ok"] is True
        assert result["total"] == 3
    assert exc_info.value.code == 0


def test_cmd_audit_export_filter_actor(audit_trail, tmp_path):
    args = AuditExportArgs(tmp_path, actor="alice")
    with patch("sys.stdout.write") as mock_write:
        cmd_audit_export(args)
    written = "".join(call.args[0] for call in mock_write.call_args_list)
    lines = [l for l in written.strip().split("\n") if l.strip()]
    assert len(lines) == 1
    parsed = json.loads(lines[0])
    assert parsed["actor"] == "alice"
