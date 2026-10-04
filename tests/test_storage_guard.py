"""security.require_encrypted_storage — refuse to write state to an unverified volume.

NeuralMind doesn't encrypt ``.neuralmind/`` itself (in-process crypto from a
pip wheel isn't FIPS-validated, so it wouldn't satisfy CMMC 3.13.11); it
verifies the OS's full-disk encryption and refuses when it can't.
"""

from __future__ import annotations

import io
import json
import plistlib
import sys
from pathlib import Path

import pytest

from neuralmind import storage_guard
from neuralmind.audit import AuditTrail
from neuralmind.storage_guard import (
    StorageNotVerifiedError,
    StorageStatus,
    check_storage,
    enforce_storage_policy,
    parse_linux,
    parse_macos,
    parse_windows,
)

ENCRYPTED = StorageStatus(True, "FileVault", None, "/: FileVault on")
PLAIN = StorageStatus(False, "", None, "/: not encrypted")
UNKNOWN = StorageStatus(None, "", None, "overlay is not a block device")


@pytest.fixture(autouse=True)
def fresh_verdicts(monkeypatch):
    monkeypatch.setattr(storage_guard, "_VERDICTS", {})


def _require(project: Path) -> None:
    (Path(project) / "neuralmind-backend.yaml").write_text(
        "security:\n  require_encrypted_storage: true\n", encoding="utf-8"
    )


def _volume(monkeypatch, status: StorageStatus) -> list:
    calls: list = []

    def fake(path):
        calls.append(path)
        return status

    monkeypatch.setattr(storage_guard, "check_storage", fake)
    return calls


# --- parsers --------------------------------------------------------------------


def _plist(**info) -> bytes:
    return plistlib.dumps({"MountPoint": "/System/Volumes/Data", **info})


def test_macos_counts_filevault_only():
    assert parse_macos(_plist(FileVault=True, Encryption=True)).encrypted is True
    hardware_only = parse_macos(_plist(FileVault=False, Encryption=True))
    assert hardware_only.encrypted is False
    assert "FileVault is off" in hardware_only.detail
    assert parse_macos(_plist(FileVault=False, Encryption=False)).encrypted is False
    assert parse_macos(b"not a plist").encrypted is None


def test_linux_looks_for_a_dm_crypt_layer():
    luks = parse_linux("/dev/mapper/luks-1", "crypt\npart\ndisk\n", "1\n")
    assert (luks.encrypted, luks.method, luks.fips_mode) == (True, "dm-crypt/LUKS", True)
    plain = parse_linux("/dev/nvme0n1p2", "part\ndisk\n", "0\n")
    assert (plain.encrypted, plain.fips_mode) == (False, False)
    assert parse_linux("overlay", "", None).encrypted is None
    assert parse_linux("/dev/sda1", "", None).encrypted is None


def test_windows_counts_only_bitlocker_on_states():
    assert parse_windows("C:", "1\r\n", 1).encrypted is True
    assert parse_windows("C:", "1", 1).fips_mode is True
    assert parse_windows("C:", "6", None).encrypted is True
    assert parse_windows("C:", "2", 0).encrypted is False
    for unverified in ("3", "4", "5", "", "garbage"):
        assert parse_windows("C:", unverified, None).encrypted is None, unverified


def test_check_storage_never_raises_on_this_machine(tmp_path):
    status = check_storage(tmp_path)
    assert isinstance(status, StorageStatus)
    assert status.encrypted in (True, False, None)


# --- enforcement ----------------------------------------------------------------


def test_not_required_means_no_check(temp_project, monkeypatch):
    calls = _volume(monkeypatch, PLAIN)
    assert enforce_storage_policy(temp_project) is None
    assert calls == []


def test_required_and_encrypted_passes_and_is_audited_once(temp_project, monkeypatch):
    _require(temp_project)
    calls = _volume(monkeypatch, ENCRYPTED)
    assert enforce_storage_policy(temp_project) == ENCRYPTED
    assert enforce_storage_policy(temp_project) == ENCRYPTED
    assert len(calls) == 1
    checks = [e for e in AuditTrail(temp_project).read_events() if e["action"] == "storage_check"]
    assert len(checks) == 1
    assert checks[0]["status"] == "success"
    assert checks[0]["details"]["method"] == "FileVault"


@pytest.mark.parametrize("status", [PLAIN, UNKNOWN])
def test_required_and_unverified_is_refused(temp_project, monkeypatch, status):
    _require(temp_project)
    _volume(monkeypatch, status)
    with pytest.raises(StorageNotVerifiedError, match="not verified as encrypted"):
        enforce_storage_policy(temp_project)
    check = next(
        e for e in AuditTrail(temp_project).read_events() if e["action"] == "storage_check"
    )
    assert check["status"] == "denied"


# --- every entry point that writes state ----------------------------------------


@pytest.fixture
def unverified(temp_project, monkeypatch):
    _require(temp_project)
    _volume(monkeypatch, PLAIN)
    return temp_project


def test_neuralmind_refuses_to_start(unverified):
    from neuralmind.core import NeuralMind

    with pytest.raises(StorageNotVerifiedError):
        NeuralMind(str(unverified))


def test_mcp_tool_calls_are_refused(unverified):
    from neuralmind.mcp_server import handle_tool_call

    data = json.loads(handle_tool_call("neuralmind_stats", {"project_path": str(unverified)}))
    assert data["code"] == "security_denied"
    assert data["reason"] == "storage"


def test_decision_store_refuses_to_open(unverified):
    from neuralmind.memory.store import DecisionStore

    with pytest.raises(StorageNotVerifiedError):
        DecisionStore(str(unverified))
    assert not (Path(unverified) / ".neuralmind" / "memory.db").exists()


def test_command_output_is_not_cached(unverified):
    from neuralmind.output_cache import cache_path, write_last_output

    assert write_last_output(unverified, "secret output", "", 0, command="cat cui.txt") is None
    assert not cache_path(unverified).exists()


def _hook(monkeypatch, action: str, payload: dict) -> int:
    from neuralmind.hooks import run_hook

    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    return run_hook(action)


def test_hooks_write_nothing(unverified, monkeypatch):
    from neuralmind.output_cache import cache_path
    from neuralmind.synapses import default_db_path

    monkeypatch.delenv("NEURALMIND_NO_LEARN", raising=False)
    bash = {"cwd": str(unverified), "tool_input": {"command": "cat cui.txt"}}
    assert _hook(monkeypatch, "compress-bash", {**bash, "tool_response": {"stdout": "secret"}}) == 0
    assert not cache_path(unverified).exists()
    # The Read hook records a file transition in the synapse store, which has
    # no gate of its own: only the hook-level check keeps it off the volume.
    read = {"cwd": str(unverified), "tool_input": {"file_path": "cui.txt"}}
    assert _hook(monkeypatch, "compress-read", {**read, "tool_response": {"content": "x"}}) == 0
    assert not Path(default_db_path(str(unverified))).exists()


def test_hooks_still_learn_when_storage_is_not_required(temp_project, monkeypatch):
    """Control for the test above: the same Read hook does write the store."""
    from neuralmind.synapses import default_db_path

    monkeypatch.delenv("NEURALMIND_NO_LEARN", raising=False)
    read = {"cwd": str(temp_project), "tool_input": {"file_path": "a.py"}}
    _hook(monkeypatch, "compress-read", {**read, "tool_response": {"content": "x"}})
    _hook(
        monkeypatch,
        "compress-read",
        {**read, "tool_input": {"file_path": "b.py"}, "tool_response": {"content": "x"}},
    )
    assert Path(default_db_path(str(temp_project))).exists()


# --- doctor ---------------------------------------------------------------------


def _storage_check(project):
    from neuralmind.doctor import _check_storage_encryption

    return _check_storage_encryption(Path(project).resolve())


def test_doctor_fails_when_required_and_unverified(unverified):
    check = _storage_check(unverified)
    assert check.status == "fail"
    assert "refuses to run here" in check.detail


def test_doctor_is_ok_when_not_required(temp_project, monkeypatch):
    _volume(monkeypatch, PLAIN)
    check = _storage_check(temp_project)
    assert check.status == "ok"
    assert "not required" in check.detail


def test_doctor_warns_when_required_without_fips_mode(temp_project, monkeypatch):
    _require(temp_project)
    _volume(monkeypatch, StorageStatus(True, "dm-crypt/LUKS", False, "/dev/mapper/x: dm-crypt"))
    check = _storage_check(temp_project)
    assert check.status == "warn"
    assert "FIPS" in check.fix


def test_cli_refuses_with_a_reason_not_a_traceback(unverified, monkeypatch, capsys):
    from neuralmind.cli import main

    monkeypatch.setattr(sys, "argv", ["neuralmind", "query", str(unverified), "what is f"])
    with pytest.raises(SystemExit) as exit_info:
        main()
    assert exit_info.value.code == 1
    err = capsys.readouterr().err
    assert "not verified as encrypted" in err
    assert "neuralmind doctor" in err


def test_doctor_still_runs_on_an_unverified_volume(unverified):
    from neuralmind.doctor import run_diagnostics

    names = {check.name: check.status for check in run_diagnostics(str(unverified))}
    assert names["Storage encryption"] == "fail"
