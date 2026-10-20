"""`neuralmind hardening`: the SP 800-53 hardening baseline, checked.

A project set up as docs/compliance/SP800-53-HARDENING.md says passes every
rule and exits 0; each rule fails on its own when its one setting is undone;
a rule that can't be checked fails rather than passes; and the guide lists
exactly the rules and controls the code checks. The exit-1 case for a default
project is a row in tests/test_cli_exit_codes.py.

The host is faked where a test can't change it: the volume's encryption and
the OS FIPS mode (storage_guard.check_storage), the OpenSSL the checkpoint
signer uses, the running daemon, and the machine policy's root ownership.
The audit log, checkpoints and forwarding are real, to a real UDP listener.
"""

from __future__ import annotations

import json
import re
import socket
import sys
from pathlib import Path

import pytest

from neuralmind import audit_checkpoint as ac
from neuralmind import cli, doctor, hardening, security_config, storage_guard
from neuralmind.audit import AuditTrail
from neuralmind.audit_forward import forward_pending, load_forward_settings
from neuralmind.storage_guard import StorageStatus

ROOT = Path(__file__).resolve().parent.parent
GUIDE = ROOT / "docs" / "compliance" / "SP800-53-HARDENING.md"
CATALOG = Path(__file__).resolve().parent / "fixtures" / "oscal" / "sp800-53r5_control_ids.txt"

ENCRYPTED = StorageStatus(True, "dm-crypt/LUKS", True, "/dev/test: dm-crypt layer present")


class Host:
    """The parts of the host a test can't change, faked, and the project."""

    def __init__(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self.monkeypatch = monkeypatch
        self.storage = ENCRYPTED
        self.fips_openssl = True
        self.exposure: str | None = None
        monkeypatch.setattr(storage_guard, "check_storage", lambda _p: self.storage)
        monkeypatch.setattr(
            hardening, "_signing_openssl", lambda: ("OpenSSL 3.0.9 FIPS", self.fips_openssl)
        )
        monkeypatch.setattr(doctor, "_running_daemon_exposure", lambda: self.exposure)

        self.policy = tmp_path / "etc" / "neuralmind" / "policy.yaml"
        self.policy.parent.mkdir(parents=True)
        self.policy.write_text("security:\n  profile: cui\n")
        monkeypatch.setattr(security_config, "MACHINE_POLICY_PATH", self.policy)
        monkeypatch.setattr(security_config, "_untrusted_machine_policy", lambda _p: None)

        self.listener = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.listener.bind(("127.0.0.1", 0))
        self.syslog = f"udp://127.0.0.1:{self.listener.getsockname()[1]}"

        self.project = tmp_path / "proj"
        self.project.mkdir()
        self.key = tmp_path / "admin" / "key.pem"
        self.key.parent.mkdir()
        public = ac.generate_key(self.key)
        self.anchor = tmp_path / "anchor"
        self.anchor.mkdir()
        self.settings = {
            "profile": "cui",
            "users": "{alice: builder}",
            "audit_checkpoint_key": public,
            "audit_anchor_dir": str(self.anchor),
            "audit_syslog": self.syslog,
        }
        self.write_settings()

        trail = AuditTrail(self.project)
        for i in range(3):
            trail.append_event("query", "run", target=f"q{i}")
        ac.create_checkpoint(self.project, key_path=self.key, anchor_dir=self.anchor)
        forward_pending(self.project, load_forward_settings(self.project))
        (self.project / ".neuralmind").chmod(0o700)

    @property
    def config(self) -> Path:
        return self.project / "neuralmind-backend.yaml"

    def write_settings(self, **changes: str | None) -> None:
        self.settings.update(changes)
        lines = ["security:"] + [
            f"  {key}: {value}" for key, value in self.settings.items() if value is not None
        ]
        self.config.write_text("\n".join(lines) + "\n")
        self.config.chmod(0o600)

    def failed(self) -> set[str]:
        return {f.rule.id for f in hardening.check(self.project) if f.result.status == "fail"}

    def close(self) -> None:
        self.listener.close()


@pytest.fixture
def host(tmp_path, monkeypatch):
    h = Host(tmp_path, monkeypatch)
    yield h
    h.close()


def _run(argv: list[str], monkeypatch, capsys) -> tuple[int, str]:
    monkeypatch.setattr(sys, "argv", ["neuralmind", *argv])
    try:
        cli.main()
        code = 0
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
    return code, capsys.readouterr().out


def test_rules_are_numbered_in_order_and_name_catalog_controls():
    catalog = {line.strip() for line in CATALOG.read_text().splitlines() if line.strip()}
    ids = [rule.id for rule in hardening.RULES]
    assert ids == [f"NMH-{i:02d}" for i in range(1, len(ids) + 1)]
    for rule in hardening.RULES:
        assert rule.controls and set(rule.controls) <= catalog, rule.id


def test_a_hardened_project_passes_every_rule_and_exits_0(host, monkeypatch, capsys):
    findings = hardening.check(host.project)
    not_passing = {f.rule.id: f.result.detail for f in findings if f.result.status != "pass"}
    if sys.platform == "win32":
        assert set(not_passing) == {"NMH-05", "NMH-06"}
    else:
        assert not not_passing

    code, out = _run(["hardening", str(host.project), "--json"], monkeypatch, capsys)
    payload = json.loads(out)
    assert code == 0
    assert payload["baseline"] == hardening.BASELINE
    assert payload["failed"] == 0
    assert [r["id"] for r in payload["rules"]] == [r.id for r in hardening.RULES]
    assert payload["rules"][0]["controls"] == ["cm-6", "cm-7", "sc-8"]


def test_the_report_names_each_rule_and_its_controls(host, monkeypatch, capsys):
    host.fips_openssl = False
    code, out = _run(["hardening", str(host.project)], monkeypatch, capsys)
    assert code == 1
    assert "[FAIL] NMH-09 Checkpoint signing runs in a FIPS-mode OpenSSL (SC-13, AU-9(3))" in out
    assert "-> pip install --force-reinstall" in out
    assert "[pass] NMH-11" in out
    assert "; 1 fail." in out


def _no_machine_policy(h: Host) -> None:
    h.policy.unlink()


def _machine_policy_without_profile(h: Host) -> None:
    h.policy.write_text("security:\n  require_encrypted_storage: true\n")


def _broad_default_role(h: Host) -> None:
    h.write_settings(default_role="admin")


def _group_writable_settings(h: Host) -> None:
    h.config.chmod(0o660)


def _world_writable_state(h: Host) -> None:
    (h.project / ".neuralmind").chmod(0o707)


def _unencrypted(h: Host) -> None:
    h.storage = StorageStatus(False, "", True, "/dev/test: no dm-crypt layer (disk)")


def _fips_off(h: Host) -> None:
    h.storage = StorageStatus(True, "dm-crypt/LUKS", False, "/dev/test: dm-crypt layer present")


def _bundled_openssl(h: Host) -> None:
    h.fips_openssl = False


def _exposed_daemon(h: Host) -> None:
    h.exposure = "it listens on '0.0.0.0', beyond loopback"


def _unrecorded_write_failure(h: Host) -> None:
    (h.project / ".neuralmind" / "audit_write_failures.jsonl").write_text(
        '{"event": "query/run", "timestamp": "2026-10-20T00:00:00+00:00", "error": "disk full"}\n'
    )


def _no_anchor(h: Host) -> None:
    h.write_settings(audit_anchor_dir=None)


def _stale_checkpoint(h: Host) -> None:
    h.monkeypatch.setattr(ac, "latest_checkpoint_age_days", lambda _r: 30.0)


def _remote_syslog(h: Host) -> None:
    h.write_settings(audit_syslog="tcp://siem.example:514")


def _records_waiting(h: Host) -> None:
    h.listener.close()
    h.write_settings(audit_syslog="tcp://127.0.0.1:1")  # nothing listens there
    AuditTrail(h.project).append_event("query", "run", target="late")


BREAKS = [
    (_no_machine_policy, {"NMH-02"}),
    (_machine_policy_without_profile, {"NMH-02"}),
    (_broad_default_role, {"NMH-04"}),
    (_unencrypted, {"NMH-07"}),
    (_fips_off, {"NMH-08"}),
    (_bundled_openssl, {"NMH-09"}),
    (_exposed_daemon, {"NMH-10"}),
    (_unrecorded_write_failure, {"NMH-12"}),
    (_no_anchor, {"NMH-14"}),
    (_stale_checkpoint, {"NMH-15"}),
    # Under the profile a remote target is refused, so nothing is forwarded.
    (_remote_syslog, {"NMH-16", "NMH-17"}),
    (_records_waiting, {"NMH-17"}),
]
if sys.platform != "win32":
    BREAKS += [(_group_writable_settings, {"NMH-05"}), (_world_writable_state, {"NMH-06"})]


@pytest.mark.parametrize("undo, expected", BREAKS, ids=[b[0].__name__ for b in BREAKS])
def test_each_rule_fails_alone_when_its_setting_is_undone(host, undo, expected):
    undo(host)
    assert host.failed() == expected


def test_without_the_profile_the_settings_it_forces_fail_too(host):
    host.policy.unlink()
    host.write_settings(profile=None)
    assert host.failed() == {"NMH-01", "NMH-02", "NMH-03", "NMH-07"}


def test_a_changed_record_fails_the_chain_and_the_checkpoints(host):
    log = AuditTrail(host.project).events_file
    log.write_text(log.read_text().replace('"q1"', '"qX"'))
    failed = host.failed()
    assert {"NMH-11", "NMH-13"} <= failed
    assert "NMH-01" not in failed


def test_a_rule_that_cant_be_checked_fails(host, monkeypatch):
    def boom(_project):
        raise OSError("permission denied")

    rule = hardening.RULES[0]
    monkeypatch.setattr(
        hardening, "RULES", (hardening.Rule(rule.id, rule.title, rule.controls, boom),)
    )
    (finding,) = hardening.check(host.project)
    assert finding.result.status == "fail"
    assert "permission denied" in finding.result.detail


def test_an_unknown_signing_openssl_fails(host, monkeypatch):
    def unknown():
        raise ImportError("no cryptography")

    monkeypatch.setattr(hardening, "_signing_openssl", unknown)
    assert host.failed() == {"NMH-09"}


def test_permission_rules_dont_apply_on_windows(tmp_path, monkeypatch):
    monkeypatch.setattr(hardening.sys, "platform", "win32")
    assert hardening._config_permissions(tmp_path).status == "n/a"
    assert hardening._state_permissions(tmp_path).status == "n/a"


def test_an_unreadable_fips_mode_fails_except_on_macos(host, monkeypatch):
    host.storage = StorageStatus(True, "FileVault", None, "disk1s1: FileVault on")
    monkeypatch.setattr(hardening.sys, "platform", "linux")
    assert hardening._os_fips(host.project).status == "fail"
    monkeypatch.setattr(hardening.sys, "platform", "darwin")
    assert hardening._os_fips(host.project).status == "n/a"


def test_the_signing_probe_reads_the_installed_cryptography():
    version, fips = hardening._signing_openssl()
    assert "OpenSSL" in version or "LibreSSL" in version or "BoringSSL" in version
    assert isinstance(fips, bool)


def test_the_guide_lists_every_rule_with_its_controls():
    rows = re.findall(r"^\| \*\*(NMH-\d\d)\*\* \| ([^|]+) \| ([^|]+) \|", GUIDE.read_text(), re.M)
    in_guide = {rule_id: (title.strip(), controls.strip()) for rule_id, title, controls in rows}
    in_code = {
        rule.id: (rule.title, ", ".join(hardening.control_label(c) for c in rule.controls))
        for rule in hardening.RULES
    }
    assert in_guide == in_code


def test_control_labels():
    assert hardening.control_label("au-9.3") == "AU-9(3)"
    assert hardening.control_label("cm-6") == "CM-6"
