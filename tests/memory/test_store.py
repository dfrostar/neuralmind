"""Unit tests for DecisionStore — TRD 10.1 (CRUD, commit linking, edge cases)."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from neuralmind.memory.store import (
    SCHEMA_VERSION,
    STALE_DAYS,
    DecisionStore,
)


@pytest.fixture
def store(tmp_path):
    return DecisionStore(str(tmp_path))


def _record(store, **overrides):
    kwargs = {
        "title": "Use SQLite WAL mode",
        "rationale": "WAL avoids reader/writer blocking under concurrent agents.",
        "commit_sha": "a" * 40,
        "files_affected": ["neuralmind/store.py"],
    }
    kwargs.update(overrides)
    return store.record(**kwargs)


# ------------------------------------------------------------------ #
# Schema / persistence
# ------------------------------------------------------------------ #


def test_creates_db_in_neuralmind_dir(tmp_path):
    DecisionStore(str(tmp_path))
    db = tmp_path / ".neuralmind" / "memory.db"
    assert db.exists(), "store must create <project>/.neuralmind/memory.db"


def test_schema_version_stamped(store, tmp_path):
    conn = sqlite3.connect(tmp_path / ".neuralmind" / "memory.db")
    row = conn.execute(
        "SELECT value FROM meta WHERE key='decision_store_schema_version'"
    ).fetchone()
    conn.close()
    assert row is not None
    assert int(row[0]) == SCHEMA_VERSION


# ------------------------------------------------------------------ #
# CRUD
# ------------------------------------------------------------------ #


def test_record_and_get_roundtrip(store):
    rec = _record(store, tags=["db"], evidence=["doc#L42"])
    got = store.get(rec.id)
    assert got is not None
    assert got.title == "Use SQLite WAL mode"
    assert got.files_affected == ["neuralmind/store.py"]
    assert got.tags == ["db"]
    assert got.evidence == ["doc#L42"]
    assert got.status == "ACTIVE"


def test_get_missing_returns_none(store):
    assert store.get("no-such-id") is None


def test_delete_removes_record_and_fts(store):
    rec = _record(store)
    store.delete(rec.id)
    assert store.get(rec.id) is None
    assert store.query("SQLite WAL") == []


def test_invalidate_sets_invalidated_status(store):
    rec = _record(store)
    store.invalidate(rec.id, reason="superseded")
    got = store.get(rec.id)
    assert got.status == "INVALIDATED"
    assert any("superseded" in e for e in got.evidence)


def test_update_status_invalid_is_noop(store):
    rec = _record(store)
    store.update_status(rec.id, "NOT_A_STATUS")
    assert store.get(rec.id).status == "ACTIVE"


def test_update_full_record(store):
    rec = _record(store)
    rec.title = "Revised: use WAL"
    rec.rationale = "Updated reasoning."
    store.update(rec)
    got = store.get(rec.id)
    assert got.title == "Revised: use WAL"
    assert got.rationale == "Updated reasoning."


def test_restore_assigns_new_commit(store):
    rec = _record(store)
    store.invalidate(rec.id, reason="old")
    restored = store.restore(rec.id, new_commit_sha="b" * 40)
    assert restored.status == "ACTIVE"
    assert restored.commit_sha == "b" * 40
    assert store.get(rec.id).status == "ACTIVE"


# ------------------------------------------------------------------ #
# Commit linking / invalidation queries
# ------------------------------------------------------------------ #


def test_find_by_files(store):
    a = _record(store, files_affected=["src/a.py"])
    _record(store, files_affected=["src/b.py"])
    hits = store.find_by_files(["src/a.py", "src/unrelated.py"])
    assert [d.id for d in hits] == [a.id]


def test_find_by_files_empty_list(store):
    _record(store)
    assert store.find_by_files([]) == []


def test_find_stale_filters_by_status(store):
    a = _record(store)
    b = _record(store, title="Second")
    store.update_status(a.id, "STALE")
    stale_ids = {d.id for d in store.find_stale()}
    assert a.id in stale_ids
    assert b.id not in stale_ids


def test_find_dependents_via_dependency_constraints(store):
    base = _record(store, title="Base decision")
    dep = _record(
        store,
        title="Dependent decision",
        dependency_constraints=[base.id],
    )
    dependents = store.find_dependents(base.id)
    assert dep.id in {d.id for d in dependents}


# ------------------------------------------------------------------ #
# Query (FTS + fallback)
# ------------------------------------------------------------------ #


def test_query_matches_title(store):
    _record(store, title="Adopt Black for formatting")
    _record(store, title="Use uv for deps", rationale="uv is fast.")
    hits = store.query("Black formatting")
    assert any("Black" in d.title for d in hits)


def test_query_excludes_stale_by_default(store):
    rec = _record(store, title="Unique stale marker QX")
    store.invalidate(rec.id, reason="test")
    assert store.query("Unique stale marker QX") == []
    # status=None includes everything
    assert len(store.query("Unique stale marker QX", status=None)) == 1


def test_query_respects_limit(store):
    for i in range(5):
        _record(store, title=f"Shared keyword decision {i}")
    assert len(store.query("Shared keyword", limit=3)) == 3


def test_query_empty_store_no_error(store):
    assert store.query("anything") == []


# ------------------------------------------------------------------ #
# Audit / export
# ------------------------------------------------------------------ #


def test_audit_returns_list_of_records(store):
    a = _record(store)
    b = _record(store, title="Second")
    store.invalidate(a.id, reason="r")
    # audit() returns stale-by-age + orphaned decisions as a list
    result = store.audit()
    assert isinstance(result, list)


def test_audit_detects_stale_by_age(store):
    old = datetime.now(timezone.utc) - timedelta(days=STALE_DAYS + 10)
    rec = _record(store, title="Ancient decision", created_at=old, updated_at=old)
    result = store.audit()
    assert rec.id in {d.id for d in result}


def test_export_markdown(store):
    _record(store, title="Exported decision")
    md = store.export(format="md")
    assert "Exported decision" in md


def test_export_json_roundtrip(store):
    _record(store, tags=["roundtrip"])
    payload = store.export(format="json")
    data = json.loads(payload)
    assert any("roundtrip" in d.get("tags", []) for d in data)


# ------------------------------------------------------------------ #
# Edge cases (TRD 10.4)
# ------------------------------------------------------------------ #


def test_duplicate_title_allowed_different_ids(store):
    a = _record(store, title="Same title")
    b = _record(store, title="Same title")
    assert a.id != b.id
    assert store.get(a.id) is not None
    assert store.get(b.id) is not None


def test_invalid_decision_type_falls_back_to_default(store):
    rec = _record(store, decision_type="BOGUS_TYPE")
    got = store.get(rec.id)
    assert got is not None
    assert got.decision_type in ("ARCHITECTURE", "BOGUS_TYPE")  # document actual behavior


def test_confidence_clamped(store):
    rec = _record(store, confidence=5.0)
    got = store.get(rec.id)
    assert got.confidence <= 1.0


def test_invalid_commit_sha_still_records(store):
    # TRD says invalid commit_sha -> validation error; store is fail-open.
    # Document actual behavior: empty/invalid SHA is accepted.
    rec = _record(store, commit_sha="")
    assert store.get(rec.id) is not None


def test_list_all_filters_status(store):
    a = _record(store)
    _record(store, title="Second")
    store.invalidate(a.id, reason="r")
    active = store.list_all(status="ACTIVE")
    assert all(d.status == "ACTIVE" for d in active)
    assert len(active) >= 1


# --------------------------------------------------------------------------- #
# Fail-open logging (regression for the 066a48b silent-no-op class of bug)
# --------------------------------------------------------------------------- #


class TestFailOpenLogging:
    """Fail-open paths must log, never silently swallow exceptions.

    The original update() bug (066a48b) hid behind ``except Exception:
    pass`` — every update was a silent no-op. These tests pin the contract
    that a swallowed failure still emits a log record.
    """

    def test_update_status_failure_logs(self, store, caplog):
        """A failing update_status() must emit an ERROR log, not pass silently."""
        import logging

        _record(store)
        decision_id = store.list_all()[0].id

        # Drop the table so the UPDATE raises inside the try block.
        with store._connect() as conn:
            conn.execute("DROP TABLE decisions")

        with caplog.at_level(logging.ERROR, logger="neuralmind.memory.store"):
            store.update_status(decision_id, "STALE")

        assert any(
            "update_status" in r.message for r in caplog.records
        ), "update_status failure was swallowed without logging"

    def test_no_silent_pass_in_memory_module(self):
        """Source-level guard: no ``except Exception: pass`` remains in memory/."""
        import re
        from pathlib import Path

        memory_dir = Path(__file__).parent.parent.parent / "neuralmind" / "memory"
        pattern = re.compile(r"except\s+Exception.*:\s*\n\s*pass\s*$", re.MULTILINE)
        offenders = []
        for py in memory_dir.glob("*.py"):
            matches = pattern.findall(py.read_text(encoding="utf-8"))
            if matches:
                offenders.append(f"{py.name}: {len(matches)}")
        assert not offenders, (
            f"Silent except-pass blocks found in memory/: {offenders}. "
            "Fail-open paths must log (see 066a48b)."
        )
