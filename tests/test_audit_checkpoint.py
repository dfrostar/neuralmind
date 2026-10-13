"""Signed, anchored audit checkpoints (CMMC AU.L2-3.3.8).

The hash chain alone can't show records removed from the end of the log, or a
chain recomputed by anyone who can write the file. A checkpoint signed with a
key the developer can't read, and anchored where the developer can't write,
shows both for every record it covers.

Also the exit-code contract for `audit keygen`, `audit checkpoint` and
`audit verify` with checkpoints (see tests/test_cli_exit_codes.py).
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

from neuralmind import audit_checkpoint as ac
from neuralmind import cli
from neuralmind.audit import AuditTrail


def _project(tmp_path: Path, records: int = 5) -> Path:
    project = tmp_path / "proj"
    project.mkdir()
    trail = AuditTrail(project)
    for i in range(records):
        trail.append_event("query", "run", target=f"q{i}")
    return project


def _key(tmp_path: Path, name: str = "key.pem") -> tuple[Path, str]:
    path = tmp_path / name
    return path, ac.generate_key(path)


def _pin(project: Path, public: str | None = None, anchor: Path | None = None) -> None:
    lines = ["security:"]
    if public:
        lines.append(f"  audit_checkpoint_key: {public}")
    if anchor:
        lines.append(f"  audit_anchor_dir: {anchor}")
    (project / "neuralmind-backend.yaml").write_text("\n".join(lines) + "\n")


def _log(project: Path) -> Path:
    return AuditTrail(project).events_file


def _rehash_log(project: Path, keep: int) -> None:
    """What someone who can write the file does: keep `keep` records, edit one,
    and recompute every hash so the chain verifies."""
    path = _log(project)
    records = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    records = records[:keep]
    records[0]["target"] = "edited"
    prev = "0" * 64
    for record in records:
        body = {k: v for k, v in record.items() if k not in ("sha256", "prev_sha256")}
        record["prev_sha256"] = prev
        record["sha256"] = hashlib.sha256(
            (prev + json.dumps(body, sort_keys=True, separators=(",", ":"))).encode()
        ).hexdigest()
        prev = record["sha256"]
    path.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in records))


# --- keys --------------------------------------------------------------------


def test_keygen_writes_a_private_key_only_its_owner_can_read(tmp_path):
    path, public = _key(tmp_path)
    assert path.read_text().startswith("-----BEGIN PRIVATE KEY-----")
    if sys.platform != "win32":
        assert path.stat().st_mode & 0o777 == 0o600
    assert ac.public_key_b64(ac.load_private_key(path).public_key()) == public


def test_keygen_refuses_to_overwrite(tmp_path):
    path, _ = _key(tmp_path)
    with pytest.raises(ac.CheckpointError, match="already exists"):
        ac.generate_key(path)
    ac.generate_key(path, force=True)


def test_a_non_p256_key_is_refused(tmp_path):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    path = tmp_path / "p384.pem"
    path.write_bytes(
        ec.generate_private_key(ec.SECP384R1()).private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    with pytest.raises(ac.CheckpointError, match="P-256"):
        ac.load_private_key(path)


# --- writing -----------------------------------------------------------------


def test_a_checkpoint_covers_the_log_and_is_recorded_in_it(tmp_path):
    project = _project(tmp_path)
    key, public = _key(tmp_path)
    _pin(project, public)
    checkpoint = ac.create_checkpoint(project, key_path=key)
    assert (checkpoint["seq"], checkpoint["records"]) == (1, 5)
    assert checkpoint["prev_checkpoint"] == "0" * 64
    last = json.loads(_log(project).read_text().splitlines()[-1])
    assert (last["action"], last["details"]["seq"]) == ("audit_checkpoint", 1)
    report = ac.verify_checkpoints(project)
    assert report.ok and report.checked == 1 and report.key_id == checkpoint["key_id"]


def test_checkpoints_chain_to_each_other(tmp_path):
    project = _project(tmp_path)
    key, public = _key(tmp_path)
    _pin(project, public)
    first = ac.create_checkpoint(project, key_path=key)
    AuditTrail(project).append_event("query", "run")
    second = ac.create_checkpoint(project, key_path=key)
    assert second["seq"] == 2
    assert second["prev_checkpoint"] == ac.checkpoint_digest(first)
    assert ac.verify_checkpoints(project).checked == 2


def test_a_pinned_key_requires_a_signature(tmp_path):
    project = _project(tmp_path)
    _, public = _key(tmp_path)
    _pin(project, public)
    with pytest.raises(ac.CheckpointError, match="must be signed"):
        ac.create_checkpoint(project)


def test_a_key_that_doesnt_match_the_pinned_one_is_refused(tmp_path):
    project = _project(tmp_path)
    _, public = _key(tmp_path)
    other, _ = _key(tmp_path, "other.pem")
    _pin(project, public)
    with pytest.raises(ac.CheckpointError, match="doesn't match"):
        ac.create_checkpoint(project, key_path=other)


def test_a_broken_chain_is_never_checkpointed(tmp_path):
    project = _project(tmp_path)
    path = _log(project)
    path.write_text(path.read_text().replace('"q1"', '"edited"'))
    with pytest.raises(ac.CheckpointError, match="doesn't verify"):
        ac.create_checkpoint(project)
    assert not ac.local_checkpoints_path(project).exists()


def test_an_empty_log_has_nothing_to_checkpoint(tmp_path):
    project = tmp_path / "proj"
    project.mkdir()
    with pytest.raises(ac.CheckpointError, match="no hashed record"):
        ac.create_checkpoint(project)


def test_an_unwritable_anchor_writes_nothing(tmp_path):
    project = _project(tmp_path)
    blocker = tmp_path / "not-a-dir"
    blocker.write_text("")
    with pytest.raises(ac.CheckpointError, match="anchored"):
        ac.create_checkpoint(project, anchor_dir=blocker)
    assert not ac.local_checkpoints_path(project).exists()


# --- what verification catches -----------------------------------------------


def test_records_removed_from_the_end_are_detected(tmp_path):
    project = _project(tmp_path)
    key, public = _key(tmp_path)
    _pin(project, public)
    ac.create_checkpoint(project, key_path=key)
    lines = _log(project).read_text().splitlines(keepends=True)
    _log(project).write_text("".join(lines[:3]))
    assert AuditTrail(project).verify()["ok"]  # the chain alone can't tell
    report = ac.verify_checkpoints(project)
    assert not report.ok and "2 record(s) removed from the end" in report.reason


def test_a_recomputed_chain_is_detected(tmp_path):
    project = _project(tmp_path)
    key, public = _key(tmp_path)
    _pin(project, public)
    ac.create_checkpoint(project, key_path=key)
    _rehash_log(project, keep=6)
    assert AuditTrail(project).verify()["ok"]  # the chain alone can't tell
    report = ac.verify_checkpoints(project)
    assert not report.ok and "no longer matches" in report.reason


def test_a_recomputed_chain_with_extra_records_is_detected(tmp_path):
    project = _project(tmp_path)
    ac.create_checkpoint(project)
    path = _log(project)
    records = [json.loads(line) for line in path.read_text().splitlines()]
    records[2]["target"] = "edited"
    path.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in records[:3]))
    _rehash_log(project, keep=3)
    # Pad it back past the checkpoint's length with fresh, chained records.
    for _ in range(5):
        AuditTrail(project).append_event("query", "run")
    report = ac.verify_checkpoints(project)
    assert not report.ok


def test_a_forged_checkpoint_is_detected(tmp_path):
    project = _project(tmp_path)
    key, public = _key(tmp_path)
    attacker, _ = _key(tmp_path, "attacker.pem")
    _pin(project, public)
    ac.create_checkpoint(project, key_path=key)
    local = ac.local_checkpoints_path(project)
    checkpoint = json.loads(local.read_text())
    checkpoint["records"] = 3
    checkpoint["signature"] = ac._sign(ac.load_private_key(attacker), checkpoint)
    local.write_text(json.dumps(checkpoint) + "\n")
    report = ac.verify_checkpoints(project)
    assert not report.ok and "signature doesn't verify" in report.reason


def test_an_unsigned_checkpoint_fails_once_a_key_is_pinned(tmp_path):
    project = _project(tmp_path)
    ac.create_checkpoint(project)
    _, public = _key(tmp_path)
    _pin(project, public)
    report = ac.verify_checkpoints(project)
    assert not report.ok and "unsigned" in report.reason


def test_a_missing_checkpoint_is_detected(tmp_path):
    project = _project(tmp_path)
    for _ in range(3):
        ac.create_checkpoint(project)
    local = ac.local_checkpoints_path(project)
    lines = local.read_text().splitlines(keepends=True)
    local.write_text(lines[0] + lines[2])
    report = ac.verify_checkpoints(project)
    assert not report.ok and "checkpoint 2 is missing" in report.reason


def test_two_checkpoints_claiming_one_seq_are_detected(tmp_path):
    project = _project(tmp_path)
    anchor = tmp_path / "anchor"
    ac.create_checkpoint(project, anchor_dir=anchor)
    local = ac.local_checkpoints_path(project)
    forged = json.loads(local.read_text())
    forged["records"] = 1
    local.write_text(json.dumps(forged) + "\n")
    report = ac.verify_checkpoints(project, anchor_dir=anchor)
    assert not report.ok and "claim seq 1" in report.reason


def test_the_anchored_copy_survives_deletion_of_the_local_one(tmp_path):
    project = _project(tmp_path)
    anchor = tmp_path / "anchor"
    key, public = _key(tmp_path)
    _pin(project, public, anchor)
    ac.create_checkpoint(project, key_path=key)
    assert ac.anchor_checkpoints_path(project, anchor).exists()
    ac.local_checkpoints_path(project).unlink()
    lines = _log(project).read_text().splitlines(keepends=True)
    _log(project).write_text("".join(lines[:2]))
    report = ac.verify_checkpoints(project)
    assert not report.ok and "removed from the end" in report.reason


def test_a_checkpoint_kept_elsewhere_can_be_checked(tmp_path):
    project = _project(tmp_path)
    ac.create_checkpoint(project)
    exported = tmp_path / "siem.jsonl"
    exported.write_text(ac.local_checkpoints_path(project).read_text())
    ac.local_checkpoints_path(project).unlink()
    lines = _log(project).read_text().splitlines(keepends=True)
    _log(project).write_text("".join(lines[:2]))
    assert ac.verify_checkpoints(project).ok  # nothing local left to compare
    report = ac.verify_checkpoints(project, extra_sources=[exported])
    assert not report.ok and "removed from the end" in report.reason


def test_a_named_checkpoint_file_must_exist(tmp_path):
    project = _project(tmp_path)
    report = ac.verify_checkpoints(project, extra_sources=[tmp_path / "missing.jsonl"])
    assert not report.ok and "not found" in report.reason


def test_records_appended_after_a_checkpoint_are_fine(tmp_path):
    project = _project(tmp_path)
    ac.create_checkpoint(project)
    for _ in range(3):
        AuditTrail(project).append_event("query", "run")
    assert ac.verify_checkpoints(project).ok


def test_checkpoints_from_before_a_rotation_are_not_compared(tmp_path):
    project = _project(tmp_path)
    ac.create_checkpoint(project)
    AuditTrail(project).rotate(max_bytes=1)
    AuditTrail(project).append_event("query", "run")
    report = ac.verify_checkpoints(project)
    assert report.ok and report.predate_rotation == 1
    assert ac.create_checkpoint(project)["seq"] == 2


# --- settings fail closed ------------------------------------------------------


@pytest.mark.parametrize(
    "text, needle",
    [
        ("security:\n  audit_checkpoint_key: not-a-key\n", "isn't a base64 DER public key"),
        ("security:\n  audit_checkpoint_key:\n", "must be a public key"),
        ("security:\n  audit_anchor_dir:\n", "must be a directory path"),
        ("security: [\n  audit_checkpoint_key: x\n", "does not parse"),
        ("security:\n  - audit_anchor_dir: /x\n", "must be a mapping"),
    ],
)
def test_a_broken_setting_fails_verification(tmp_path, text, needle):
    project = _project(tmp_path)
    (project / "neuralmind-backend.yaml").write_text(text)
    report = ac.verify_checkpoints(project)
    assert not report.ok and needle in report.reason


def test_a_relative_anchor_dir_is_relative_to_the_project(tmp_path):
    project = _project(tmp_path)
    (project / "neuralmind-backend.yaml").write_text("security:\n  audit_anchor_dir: ../anchor\n")
    settings = ac.load_checkpoint_settings(project)
    assert settings.anchor_dir == project.resolve() / ".." / "anchor"


# --- doctor ------------------------------------------------------------------


def test_doctor_without_checkpoints(tmp_path):
    from neuralmind import doctor

    check = doctor._check_audit_checkpoints(_project(tmp_path))
    assert check.status == doctor.OK and check.detail.startswith("none")


def test_doctor_with_a_signed_anchored_checkpoint(tmp_path):
    from neuralmind import doctor

    project = _project(tmp_path)
    key, public = _key(tmp_path)
    _pin(project, public, tmp_path / "anchor")
    ac.create_checkpoint(project, key_path=key)
    check = doctor._check_audit_checkpoints(project)
    assert check.status == doctor.OK
    assert "signed with key" in check.detail and "anchored" in check.detail


def test_doctor_fails_when_a_checkpoint_shows_truncation(tmp_path):
    from neuralmind import doctor

    project = _project(tmp_path)
    ac.create_checkpoint(project)
    lines = _log(project).read_text().splitlines(keepends=True)
    _log(project).write_text("".join(lines[:2]))
    assert doctor._check_audit_checkpoints(project).status == doctor.FAIL


def test_doctor_warns_under_the_cui_profile_without_key_or_anchor(tmp_path):
    from neuralmind import doctor

    project = _project(tmp_path)
    (project / "neuralmind-backend.yaml").write_text("security:\n  profile: cui\n")
    check = doctor._check_audit_checkpoints(project)
    assert check.status == doctor.WARN
    assert "audit_checkpoint_key" in check.detail and "audit_anchor_dir" in check.detail


def test_doctor_warns_when_the_newest_checkpoint_is_stale(tmp_path, monkeypatch):
    from neuralmind import doctor

    project = _project(tmp_path)
    key, public = _key(tmp_path)
    _pin(project, public, tmp_path / "anchor")
    ac.create_checkpoint(project, key_path=key)
    monkeypatch.setattr(ac, "latest_checkpoint_age_days", lambda _r: 30.0)
    check = doctor._check_audit_checkpoints(project)
    assert check.status == doctor.WARN and "30 days old" in check.detail


# --- CLI ---------------------------------------------------------------------


def _run(argv: list[str], monkeypatch) -> int:
    monkeypatch.setattr(sys, "argv", ["neuralmind", *argv])
    try:
        cli.main()
    except SystemExit as exc:
        return 0 if exc.code is None else int(exc.code)
    return 0


def test_cli_keygen_exit_codes(tmp_path, monkeypatch, capsys):
    key = tmp_path / "key.pem"
    assert _run(["audit", "keygen", str(key)], monkeypatch) == 0
    assert "audit_checkpoint_key:" in capsys.readouterr().out
    assert _run(["audit", "keygen", str(key)], monkeypatch) == 1


def test_cli_checkpoint_and_verify_exit_codes(tmp_path, monkeypatch, capsys):
    project = _project(tmp_path)
    key, public = _key(tmp_path)
    _pin(project, public)
    assert _run(["audit", "checkpoint", str(project)], monkeypatch) == 1  # unsigned
    monkeypatch.setenv(ac.KEY_ENV, str(key))
    assert _run(["audit", "checkpoint", str(project)], monkeypatch) == 0
    assert _run(["audit", "verify", str(project)], monkeypatch) == 0
    assert "signatures verified with key" in capsys.readouterr().out

    lines = _log(project).read_text().splitlines(keepends=True)
    _log(project).write_text("".join(lines[:2]))
    assert _run(["audit", "verify", str(project)], monkeypatch) == 1
    assert "removed from the end" in capsys.readouterr().err
    assert _run(["audit", "verify", str(project), "--json"], monkeypatch) == 1
    result = json.loads(capsys.readouterr().out)
    assert result["ok"] is False and result["checkpoints"]["ok"] is False


def test_cli_verify_without_checkpoints_says_what_it_cant_see(tmp_path, monkeypatch, capsys):
    project = _project(tmp_path)
    assert _run(["audit", "verify", str(project)], monkeypatch) == 0
    assert "No checkpoints" in capsys.readouterr().out


def test_cli_checkpoint_json_prints_the_record(tmp_path, monkeypatch, capsys):
    project = _project(tmp_path)
    assert _run(["audit", "checkpoint", str(project), "--json"], monkeypatch) == 0
    record = json.loads(capsys.readouterr().out)
    assert record["format"] == ac.FORMAT and record["signature"] is None
