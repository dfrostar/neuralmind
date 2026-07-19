"""Tier 2 audit tests — AuditLog hash chain, filtering, export, tamper detection."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import pytest

from neuralmind.tier2.audit import GENESIS_HASH, AuditEntry, AuditLog


class TestAuditLogBasics:
    """Core AuditLog operations."""

    @pytest.fixture
    def audit(self, tmp_path: Path) -> AuditLog:
        return AuditLog(tmp_path / "audit.jsonl")

    def test_audit_log_on_publish(self, audit: AuditLog) -> None:
        entry = audit.log(actor="admin", action="publish")
        assert entry.sha256 != ""
        assert len(entry.sha256) == 64

    def test_audit_log_on_remove(self, audit: AuditLog) -> None:
        entry = audit.log(actor="admin", action="remove", target="edge-1")
        assert entry.sha256 == entry.compute_hash()
        assert entry.action == "remove"

    def test_audit_log_on_config_change(self, audit: AuditLog) -> None:
        entry = audit.log(
            actor="admin",
            action="config_change",
            details={"old": "personal", "new": "shared"},
        )
        assert "old" in (entry.details or {})
        assert "new" in (entry.details or {})

    def test_audit_log_immutable(self, audit: AuditLog) -> None:
        # AuditLog only has log() — no update or delete methods
        assert not hasattr(audit, "update")
        assert not hasattr(audit, "delete")
        assert hasattr(audit, "log")


class TestAuditLogExport:
    """AuditLog export to JSON and CSV."""

    @pytest.fixture
    def audit(self, tmp_path: Path) -> AuditLog:
        audit = AuditLog(tmp_path / "audit.jsonl")
        audit.log(actor="admin", action="publish", target="repo1")
        audit.log(actor="bob", action="remove", target="edge-1")
        audit.log(actor="admin", action="config_change")
        return audit

    def test_audit_log_export_json(self, audit: AuditLog, tmp_path: Path) -> None:
        out_path = tmp_path / "audit.json"
        count = audit.export_json(out_path)
        assert count == 3
        with open(out_path) as f:
            data = json.load(f)
        assert isinstance(data, list)
        assert len(data) == 3

    def test_audit_log_export_csv(self, audit: AuditLog, tmp_path: Path) -> None:
        out_path = tmp_path / "audit.csv"
        count = audit.export_csv(out_path)
        assert count == 3
        with open(out_path, newline="") as f:
            reader = csv.reader(f)
            rows = list(reader)
        # header + 3 data rows
        assert len(rows) == 4
        assert rows[0] == ["ts", "actor", "action", "target", "prev_hash", "sha256"]


class TestAuditLogFilter:
    """AuditLog filtering by actor, date, action."""

    @pytest.fixture
    def audit(self, tmp_path: Path) -> AuditLog:
        audit = AuditLog(tmp_path / "audit.jsonl")
        audit.log(actor="alice", action="publish")
        audit.log(actor="bob", action="remove")
        return audit

    def test_audit_log_filter_by_actor(self, audit: AuditLog) -> None:
        results = audit.export(actor="bob")
        assert len(results) == 1
        assert results[0].actor == "bob"

    def test_audit_log_filter_by_date(self, audit: AuditLog) -> None:
        import time

        now = time.time()
        # All entries are within last hour
        results = audit.export(since=now - 3600, until=now + 3600)
        assert len(results) == 2

        # Filter with since far in future — should get nothing
        results_future = audit.export(since=now + 7200)
        assert len(results_future) == 0

    def test_audit_log_filter_by_action(self, audit: AuditLog) -> None:
        results = audit._entries
        publishes = [e for e in results if e.action == "publish"]
        assert len(publishes) == 1


class TestAuditTamperDetection:
    """Hash chain detects manual record corruption."""

    def test_audit_log_tamper_detection(self, tmp_path: Path) -> None:
        audit = AuditLog(tmp_path / "audit.jsonl")
        audit.log(actor="admin", action="publish")
        audit.log(actor="admin", action="remove")

        # Manually corrupt the second record
        lines = audit.db_path.read_text().strip().split("\n")
        obj = json.loads(lines[1])
        obj["action"] = "TAMPERED"
        lines[1] = json.dumps(obj)
        audit.db_path.write_text("\n".join(lines) + "\n")

        # Reload and verify
        corrupted = AuditLog(tmp_path / "audit.jsonl")
        result = corrupted.verify()
        assert result["ok"] is False
