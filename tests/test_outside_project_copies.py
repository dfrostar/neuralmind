"""The copies NeuralMind writes outside the project, and audit records it can't write.

Three gaps the compliance documents named in v4.17.2:

- Claude Code's synapse export and the global query log are written under the
  home directory, and ``security.require_encrypted_storage`` checked only the
  project's volumes, so code symbol names and query text could land on an
  unencrypted home.
- The MCP ``neuralmind_export_synapse_memory`` tool wrote the export even with
  ``NEURALMIND_SYNAPSE_EXPORT=0``, which switches off the hooks' export.
- Every caller swallows a failed audit append, so a record that couldn't be
  written left a gap nobody saw. Now it's noted, ``doctor`` reports it, and
  ``neuralmind audit record-gap`` records the gap in the hash-chained log
  itself; the note is kept, so clearing the warning doesn't erase the evidence.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from neuralmind import doctor, memory, storage_guard
from neuralmind.audit import AuditTrail
from neuralmind.storage_guard import StorageStatus
from neuralmind.synapse_memory import (
    CLAUDE_AUTO_FILENAME,
    PROJECT_MEMORY_FILENAME,
    claude_auto_memory_dir,
    export_synapse_memory,
)
from neuralmind.synapses import SynapseStore, default_db_path

ENCRYPTED = StorageStatus(True, "LUKS", None, "encrypted")
PLAIN = StorageStatus(False, "", None, "not encrypted")


@pytest.fixture(autouse=True)
def fresh_verdicts(monkeypatch):
    monkeypatch.setattr(storage_guard, "_VERDICTS", {})


@pytest.fixture
def home(tmp_path, monkeypatch):
    path = tmp_path / "home"
    path.mkdir()
    monkeypatch.setenv("HOME", str(path))
    monkeypatch.setenv("USERPROFILE", str(path))
    return path


@pytest.fixture
def project(tmp_path):
    path = tmp_path / "project"
    path.mkdir()
    return path


def _require_encryption(project: Path) -> None:
    (project / "neuralmind-backend.yaml").write_text(
        "security:\n  require_encrypted_storage: true\n", encoding="utf-8"
    )


def _volumes(monkeypatch, project: Path, home_status: StorageStatus) -> None:
    """The project's volume is encrypted; the home directory's is ``home_status``."""
    root = str(project.resolve())

    def fake(path):
        return ENCRYPTED if str(path).startswith(root) else home_status

    monkeypatch.setattr(storage_guard, "check_storage", fake)


# --- Claude Code's synapse export ---------------------------------------------


def _export(project: Path) -> list[str]:
    SynapseStore(default_db_path(project)).reinforce(["a", "b"])
    claude_auto_memory_dir(project).mkdir(parents=True)
    return [p.name for p in export_synapse_memory(project)]


def test_an_unencrypted_home_gets_no_synapse_export(project, home, monkeypatch):
    _require_encryption(project)
    _volumes(monkeypatch, project, PLAIN)
    assert _export(project) == [PROJECT_MEMORY_FILENAME]
    assert not (claude_auto_memory_dir(project) / CLAUDE_AUTO_FILENAME).exists()


def test_an_encrypted_home_gets_the_synapse_export(project, home, monkeypatch):
    _require_encryption(project)
    _volumes(monkeypatch, project, ENCRYPTED)
    assert _export(project) == [PROJECT_MEMORY_FILENAME, CLAUDE_AUTO_FILENAME]


def test_without_the_requirement_the_export_is_unchanged(project, home, monkeypatch):
    _volumes(monkeypatch, project, PLAIN)
    assert _export(project) == [PROJECT_MEMORY_FILENAME, CLAUDE_AUTO_FILENAME]


def _symlink_to_plain_volume(monkeypatch, link: Path, plain: Path) -> None:
    """``link`` points into ``plain``, the one unencrypted volume."""
    plain.mkdir(parents=True, exist_ok=True)
    link.parent.mkdir(parents=True, exist_ok=True)
    try:
        link.symlink_to(plain / link.name)
    except OSError:
        pytest.skip("can't create a symlink here")
    monkeypatch.setattr(
        storage_guard,
        "check_storage",
        lambda path: PLAIN if str(path).startswith(str(plain.resolve())) else ENCRYPTED,
    )


def test_a_symlinked_export_on_an_unencrypted_volume_isnt_written(
    project, home, monkeypatch, tmp_path
):
    _require_encryption(project)
    target = claude_auto_memory_dir(project) / CLAUDE_AUTO_FILENAME
    _symlink_to_plain_volume(monkeypatch, target, tmp_path / "plain")
    SynapseStore(default_db_path(project)).reinforce(["a", "b"])
    assert [p.name for p in export_synapse_memory(project)] == [PROJECT_MEMORY_FILENAME]
    assert not (tmp_path / "plain" / CLAUDE_AUTO_FILENAME).exists()


# --- the global query log -----------------------------------------------------


class _Result:
    layers_used = ["L0"]
    communities_loaded: list = []
    search_hits = 1
    reduction_ratio = 2.0
    budget = None


def _log_query(project: Path, monkeypatch) -> tuple[Path, Path]:
    monkeypatch.setattr(memory, "is_memory_logging_enabled", lambda: True)
    assert memory.log_query_event(project, "where is auth handled?", _Result())
    return memory.project_query_events_file(project), memory.global_query_events_file()


def test_an_unencrypted_home_gets_no_copy_of_the_query(project, home, monkeypatch):
    _require_encryption(project)
    _volumes(monkeypatch, project, PLAIN)
    local, global_ = _log_query(project, monkeypatch)
    assert "where is auth handled?" in local.read_text(encoding="utf-8")
    assert not global_.exists()


def test_an_encrypted_home_gets_the_copy_of_the_query(project, home, monkeypatch):
    _require_encryption(project)
    _volumes(monkeypatch, project, ENCRYPTED)
    _, global_ = _log_query(project, monkeypatch)
    assert "where is auth handled?" in global_.read_text(encoding="utf-8")


def test_without_the_requirement_the_query_log_is_unchanged(project, home, monkeypatch):
    _volumes(monkeypatch, project, PLAIN)
    _, global_ = _log_query(project, monkeypatch)
    assert global_.exists()


def test_a_symlinked_query_log_on_an_unencrypted_volume_isnt_written(
    project, home, monkeypatch, tmp_path
):
    _require_encryption(project)
    link = memory.global_query_events_file()
    _symlink_to_plain_volume(monkeypatch, link, tmp_path / "plain")
    local, _ = _log_query(project, monkeypatch)
    assert "where is auth handled?" in local.read_text(encoding="utf-8")
    assert not (tmp_path / "plain" / link.name).exists()


# --- the MCP export tool ------------------------------------------------------


def test_the_mcp_export_tool_honours_the_off_switch(project, monkeypatch):
    import neuralmind.synapse_memory as synapse_memory
    from neuralmind.mcp_server import tool_export_synapse_memory

    def must_not_run(*_a, **_k):
        raise AssertionError("exported with NEURALMIND_SYNAPSE_EXPORT=0")

    monkeypatch.setattr(synapse_memory, "export_synapse_memory", must_not_run)
    monkeypatch.setenv("NEURALMIND_SYNAPSE_EXPORT", "0")
    result = tool_export_synapse_memory(str(project))
    assert result == {"enabled": False, "written": [], "reason": "NEURALMIND_SYNAPSE_EXPORT=0"}


# --- audit records that couldn't be written -----------------------------------


def _failing_append(project: Path, monkeypatch) -> AuditTrail:
    trail = AuditTrail(project)

    def disk_full():
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(trail, "_last_sha256_from_file", disk_full)
    with pytest.raises(OSError):
        trail.append_event(category="query", action="query")
    return trail


def test_a_failed_audit_write_is_noted(project, monkeypatch, caplog):
    with caplog.at_level(logging.WARNING, logger="neuralmind.audit"):
        trail = _failing_append(project, monkeypatch)
    (note,) = trail.failures_file.read_text(encoding="utf-8").splitlines()
    record = json.loads(note)
    assert record["event"] == "query/query"
    assert "No space left on device" in record["error"]
    assert "query/query was not written" in caplog.text


def test_a_note_that_cant_be_written_is_still_logged(project, monkeypatch, caplog):
    trail = AuditTrail(project)
    trail.failures_file.mkdir(parents=True)  # a directory: the note can't be appended
    monkeypatch.setattr(
        trail, "_last_sha256_from_file", lambda: (_ for _ in ()).throw(OSError("disk full"))
    )
    with caplog.at_level(logging.WARNING, logger="neuralmind.audit"), pytest.raises(OSError):
        trail.append_event(category="query", action="query")
    assert "couldn't be noted" in caplog.text


def test_doctor_is_ok_with_no_failed_writes(project):
    check = doctor._check_audit_writes(project)
    assert check.status == doctor.OK


def test_doctor_warns_on_a_failed_write(project, monkeypatch):
    _failing_append(project, monkeypatch)
    check = doctor._check_audit_writes(project)
    assert check.status == doctor.WARN
    assert "1 audit record(s) couldn't be written" in check.detail
    assert "query/query" in check.detail
    assert "neuralmind audit record-gap" in check.fix


def test_doctor_fails_on_a_failed_write_under_the_cui_profile(project, monkeypatch):
    (project / "neuralmind-backend.yaml").write_text(
        "security:\n  profile: cui\n  users:\n    alice: reader\n", encoding="utf-8"
    )
    _failing_append(project, monkeypatch)
    assert doctor._check_audit_writes(project).status == doctor.FAIL


# --- recording the gap in the log ---------------------------------------------


def test_record_gap_writes_the_gap_into_the_log(project, monkeypatch):
    _failing_append(project, monkeypatch)
    trail = AuditTrail(project)
    record = trail.record_gap()
    assert record["category"] == "audit" and record["action"] == "gap_recorded"
    assert record["status"] == "failure"
    assert record["details"]["missing_records"] == 1
    assert record["details"]["events"] == {"query/query": 1}
    assert "No space left on device" in record["details"]["last_error"]
    assert trail.read_events()[-1]["sha256"] == record["sha256"]
    assert trail.verify()["ok"]
    # The note is kept; doctor passes because the log now says what's missing.
    assert len(trail.failure_notes()) == 1
    check = doctor._check_audit_writes(project)
    assert check.status == doctor.OK
    assert "all recorded in the log as gaps" in check.detail
    assert trail.record_gap() is None


def test_a_failure_after_the_gap_record_is_unrecorded(project, monkeypatch):
    _failing_append(project, monkeypatch)
    AuditTrail(project).record_gap()
    _failing_append(project, monkeypatch)
    check = doctor._check_audit_writes(project)
    assert check.status == doctor.WARN
    assert check.detail.startswith("1 audit record(s)")
    assert AuditTrail(project).record_gap()["details"]["missing_records"] == 1


def test_deleting_the_notes_doesnt_make_new_failures_look_recorded(project, monkeypatch):
    _failing_append(project, monkeypatch)
    trail = AuditTrail(project)
    trail.record_gap()
    trail.failures_file.unlink()
    _failing_append(project, monkeypatch)
    assert len(trail.unrecorded_failures()) == 1
    assert doctor._check_audit_writes(project).status == doctor.WARN


def test_a_gap_that_cant_be_written_stays_unrecorded(project, monkeypatch):
    _failing_append(project, monkeypatch)
    trail = AuditTrail(project)
    monkeypatch.setattr(
        trail, "_last_sha256_from_file", lambda: (_ for _ in ()).throw(OSError("disk full"))
    )
    with pytest.raises(OSError):
        trail.record_gap()
    assert not trail.failures_recorded_file.exists()
    # The original failure, and the failed gap record, both still unrecorded.
    assert len(AuditTrail(project).unrecorded_failures()) == 2


def test_a_cut_off_note_is_still_counted(project):
    trail = AuditTrail(project)
    trail.failures_file.parent.mkdir(parents=True)
    trail.failures_file.write_bytes(b'{"event": "query/query", "error": "No space \xe2\x80')
    check = doctor._check_audit_writes(project)
    assert check.status == doctor.WARN
    assert check.detail.startswith("1 audit record(s)")
    assert trail.record_gap()["details"]["missing_records"] == 1
    assert doctor._check_audit_writes(project).status == doctor.OK
