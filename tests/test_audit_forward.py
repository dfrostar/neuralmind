"""Live audit forwarding to syslog (CMMC AU.L2-3.3.4, 3.3.5).

Every record is sent to the syslog target in ``security.audit_syslog`` as it
is written, a record that can't be written raises an ``alert``, and records a
dead target missed are sent once it is back. The receivers here are real
sockets on this machine: UDP and TCP on the loopback address, and a unix
datagram socket.

Also the exit-code contract for `audit forward` reaching its target (see
tests/test_cli_exit_codes.py).
"""

from __future__ import annotations

import json
import re
import socket
import sys
import tempfile
import threading
from pathlib import Path

import pytest

from neuralmind import audit_forward as af
from neuralmind import cli
from neuralmind.audit import AuditTrail

unix_only = pytest.mark.skipif(
    sys.platform == "win32" or not hasattr(socket, "AF_UNIX"), reason="unix sockets"
)


def _configure(project: Path, target: str, extra: str = "") -> None:
    (project / "neuralmind-backend.yaml").write_text(
        f"security:\n  audit_syslog: {target}\n{extra}"
    )


def _project(tmp_path: Path) -> Path:
    project = tmp_path / "proj"
    (project / ".neuralmind").mkdir(parents=True)
    return project


def _body(message: bytes) -> dict:
    """The JSON record at the end of a syslog message."""
    text = message.decode("utf-8")
    return json.loads(text[text.index("{") :])


def _pri(message: bytes) -> int:
    return int(re.match(rb"<(\d+)>", message).group(1))


def _log_records(project: Path) -> list[dict]:
    return [json.loads(line) for line in AuditTrail(project).events_file.read_text().splitlines()]


class _Udp:
    def __init__(self) -> None:
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.settimeout(3)
        self.target = f"udp://127.0.0.1:{self.sock.getsockname()[1]}"

    def take(self, count: int) -> list[bytes]:
        return [self.sock.recv(70000) for _ in range(count)]

    def nothing_waiting(self) -> bool:
        self.sock.settimeout(0.2)
        try:
            self.sock.recv(70000)
            return False
        except TimeoutError:
            return True

    def close(self) -> None:
        self.sock.close()


@pytest.fixture
def udp():
    receiver = _Udp()
    yield receiver
    receiver.close()


class _Unix:
    def __init__(self, path: str) -> None:
        self.path = path
        self.sock: socket.socket | None = None

    def listen(self) -> None:
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        self.sock.bind(self.path)
        self.sock.settimeout(3)

    def take(self, count: int) -> list[bytes]:
        assert self.sock is not None
        return [self.sock.recv(70000) for _ in range(count)]

    def close(self) -> None:
        if self.sock is not None:
            self.sock.close()


@pytest.fixture
def unix_socket():
    # A short directory: a unix socket path is limited to about 100 bytes.
    folder = tempfile.mkdtemp(prefix="nmfwd")
    receiver = _Unix(str(Path(folder) / "log.sock"))
    yield receiver
    receiver.close()


# --- settings ------------------------------------------------------------------


@pytest.mark.parametrize(
    "value, expected",
    [
        ("/dev/log", af.Target("unix", path="/dev/log")),
        ("unix:/var/run/syslog", af.Target("unix", path="/var/run/syslog")),
        ("udp://127.0.0.1", af.Target("udp", host="127.0.0.1", port=514)),
        ("tcp://siem.example:6514", af.Target("tcp", host="siem.example", port=6514)),
        ("udp://[::1]:5140", af.Target("udp", host="::1", port=5140)),
    ],
)
def test_targets_parse(value, expected):
    assert af.parse_target(value) == expected


@pytest.mark.parametrize(
    "value", ["siem.example", "http://siem:514", "tcp://", "tcp://h:0", "tcp://h:x", "unix:rel"]
)
def test_malformed_targets_are_refused(value):
    with pytest.raises(af.ForwardError):
        af.parse_target(value)


def test_unset_means_off(tmp_path):
    project = _project(tmp_path)
    assert af.load_forward_settings(project) == af.ForwardSettings()


@pytest.mark.parametrize(
    "text, needle",
    [
        ("security:\n  audit_syslog: nowhere\n", "isn't a socket path"),
        ("security:\n  audit_syslog: ''\n", "must be a syslog target"),
        (
            "security:\n  audit_syslog: /dev/log\n  audit_syslog_facility: local9\n",
            "facility name",
        ),
        ("security:\n  audit_syslog: [unclosed\n", "does not parse"),
    ],
)
def test_malformed_settings_fail_closed(tmp_path, text, needle):
    project = _project(tmp_path)
    (project / "neuralmind-backend.yaml").write_text(text)
    settings = af.load_forward_settings(project)
    assert settings.target is None and needle in settings.problem


def test_the_cui_profile_refuses_a_target_off_this_machine(tmp_path):
    project = _project(tmp_path)
    _configure(project, "tcp://siem.example:514", "  profile: cui\n")
    assert "must be on this machine" in af.load_forward_settings(project).problem


@pytest.mark.parametrize("target", ["/dev/log", "udp://127.0.0.1:514", "tcp://localhost:514"])
def test_the_cui_profile_accepts_a_local_target(tmp_path, target):
    project = _project(tmp_path)
    _configure(project, target, "  profile: cui\n")
    settings = af.load_forward_settings(project)
    assert settings.problem is None and settings.target.local


# --- live forwarding -----------------------------------------------------------


def test_each_record_is_sent_as_it_is_written(tmp_path, udp):
    project = _project(tmp_path)
    _configure(project, udp.target)
    trail = AuditTrail(project)
    trail.append_event("query", "run", target="q1")
    trail.append_event("security", "mcp_call_denied", status="denied")
    first, second = udp.take(2)
    records = _log_records(project)
    assert _body(first)["sha256"] == records[0]["sha256"]
    assert _body(second)["sha256"] == records[1]["sha256"]
    assert _pri(first) == 16 * 8 + af.SEVERITY_INFO  # local0.info
    assert _pri(second) == 16 * 8 + af.SEVERITY_WARNING  # a denial is a warning
    assert re.match(rb"<\d+>1 \S+ \S+ neuralmind \d+ audit - \{", first)  # RFC 5424
    assert udp.nothing_waiting()


def test_the_facility_setting_is_used(tmp_path, udp):
    project = _project(tmp_path)
    _configure(project, udp.target, "  audit_syslog_facility: authpriv\n")
    AuditTrail(project).append_event("query", "run")
    assert _pri(udp.take(1)[0]) == 10 * 8 + af.SEVERITY_INFO


def test_tcp_uses_octet_counting(tmp_path):
    project = _project(tmp_path)
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(4)
    server.settimeout(3)
    received: list[bytes] = []

    def accept_all() -> None:
        for _ in range(2):
            conn, _ = server.accept()
            with conn:
                chunks = []
                while chunk := conn.recv(65536):
                    chunks.append(chunk)
                received.append(b"".join(chunks))

    thread = threading.Thread(target=accept_all)
    thread.start()
    _configure(project, f"tcp://127.0.0.1:{server.getsockname()[1]}")
    trail = AuditTrail(project)
    trail.append_event("query", "run", details={"text": "line one\nline two"})
    trail.append_event("query", "run")
    thread.join(5)
    server.close()
    frames = []
    for stream in received:
        while stream:
            length, _, rest = stream.partition(b" ")
            frames.append(rest[: int(length)])
            stream = rest[int(length) :]
    assert [_body(f)["sha256"] for f in frames] == [r["sha256"] for r in _log_records(project)]
    assert _body(frames[0])["details"]["text"] == "line one\nline two"


@unix_only
def test_a_unix_socket_gets_the_traditional_format(tmp_path, unix_socket):
    project = _project(tmp_path)
    unix_socket.listen()
    _configure(project, unix_socket.path)
    AuditTrail(project).append_event("query", "run")
    (message,) = unix_socket.take(1)
    assert re.match(rb"<134>[A-Z][a-z]{2} [ \d]\d \d\d:\d\d:\d\d neuralmind\[\d+\]: \{", message)


def test_a_record_too_big_for_a_datagram_keeps_its_hash(tmp_path, udp):
    project = _project(tmp_path)
    _configure(project, udp.target)
    AuditTrail(project).append_event("query", "run", details={"text": "x" * 50_000})
    (message,) = udp.take(1)
    assert len(message) <= af.MAX_DATAGRAM
    body = _body(message)
    assert body["sha256"] == _log_records(project)[0]["sha256"]
    assert body["truncated"]["original_bytes"] > 50_000 and "details" not in body


def test_unconfigured_projects_write_no_forwarding_state(tmp_path):
    project = _project(tmp_path)
    AuditTrail(project).append_event("query", "run")
    assert not af.cursor_path(project).exists()


# --- delivery ------------------------------------------------------------------


@unix_only
def test_records_a_dead_target_missed_are_sent_when_it_is_back(tmp_path, unix_socket):
    project = _project(tmp_path)
    _configure(project, unix_socket.path)  # nothing listens yet
    trail = AuditTrail(project)
    for i in range(3):
        trail.append_event("query", "run", target=f"q{i}")  # appends still succeed
    cursor = af.read_cursor(project)
    assert "can't send" in cursor["last_error"]
    assert len(af.pending(project)[0]) == 3

    unix_socket.listen()
    result = af.forward_pending(project)
    assert (result.sent, result.backlog, result.error) == (3, 0, None)
    sent = [_body(m)["target"] for m in unix_socket.take(3)]
    assert sent == ["q0", "q1", "q2"]
    assert "last_error" not in af.read_cursor(project)
    assert af.pending(project)[0] == []


def test_forwarding_continues_across_a_rotation(tmp_path, udp):
    project = _project(tmp_path)
    _configure(project, udp.target)
    trail = AuditTrail(project)
    trail.append_event("query", "run", target="before")
    udp.take(1)
    trail.rotate(max_bytes=1)
    trail.append_event("query", "run", target="after")
    marker, after = udp.take(2)
    assert _body(marker)["action"] == "rotation_continuation"
    assert _body(after)["target"] == "after"
    assert udp.nothing_waiting()  # nothing from before the rotation sent again


def test_a_rotation_before_the_backlog_went_out_loses_nothing(tmp_path, udp):
    project = _project(tmp_path)
    trail = AuditTrail(project)
    trail.append_event("query", "run", target="sent")
    _configure(project, udp.target)
    af.forward_pending(project)
    udp.take(1)
    (project / "neuralmind-backend.yaml").unlink()  # forwarding off for a while
    quiet = AuditTrail(project)
    quiet.append_event("query", "run", target="missed")
    quiet.rotate(max_bytes=1)
    quiet.append_event("query", "run", target="new")
    _configure(project, udp.target)
    result = af.forward_pending(project)
    assert not result.restarted
    sent = [_body(m).get("target") for m in udp.take(result.sent)]
    assert sent == ["missed", "", "new"]  # the archive's tail, the marker, the new log


def test_a_replaced_log_restarts_forwarding_and_says_so(tmp_path, udp):
    project = _project(tmp_path)
    _configure(project, udp.target)
    AuditTrail(project).append_event("query", "run")
    udp.take(1)
    AuditTrail(project).events_file.unlink()
    trail = AuditTrail(project)
    (project / "neuralmind-backend.yaml").unlink()
    trail.append_event("query", "run", target="fresh")
    _configure(project, udp.target)
    result = af.forward_pending(project)
    assert result.restarted and result.sent == 1
    note, record = udp.take(2)
    assert _body(note)["action"] == "audit_forward_restarted"
    assert _pri(note) == 16 * 8 + af.SEVERITY_WARNING
    assert _body(record)["target"] == "fresh"


def test_the_live_path_sends_a_bounded_batch(tmp_path, udp, monkeypatch):
    project = _project(tmp_path)
    trail = AuditTrail(project)
    for _ in range(5):
        trail.append_event("query", "run")
    _configure(project, udp.target)
    monkeypatch.setattr(af, "LIVE_BATCH", 2)
    AuditTrail(project).append_event("query", "run")
    udp.take(2)
    assert udp.nothing_waiting()
    assert len(af.pending(project)[0]) == 4


# --- the AU.L2-3.3.4 alert -----------------------------------------------------


def test_a_record_that_cannot_be_written_raises_an_alert(tmp_path, udp):
    project = _project(tmp_path)
    _configure(project, udp.target)
    trail = AuditTrail(project)
    trail.events_file.mkdir()  # a directory: the record can't be appended
    with pytest.raises(OSError):
        trail.append_event("query", "run")
    (alert,) = udp.take(1)
    assert _pri(alert) == 16 * 8 + af.SEVERITY_ALERT
    body = _body(alert)
    assert body["action"] == "audit_write_failed" and "query/run" in body["message"]


def test_a_gap_record_is_an_error(tmp_path, udp):
    project = _project(tmp_path)
    _configure(project, udp.target)
    trail = AuditTrail(project)
    trail.failures_file.write_text('{"event": "query/run", "timestamp": "t", "error": "x"}\n')
    trail.record_gap()
    (message,) = udp.take(1)
    assert _body(message)["action"] == "gap_recorded"
    assert _pri(message) == 16 * 8 + af.SEVERITY_ERR


# --- doctor --------------------------------------------------------------------


def _doctor(project: Path):
    from neuralmind import doctor

    return doctor, doctor._check_audit_forwarding(project)


def test_doctor_not_configured(tmp_path):
    doctor, check = _doctor(_project(tmp_path))
    assert check.status == doctor.OK and "not configured" in check.detail


def test_doctor_warns_under_the_cui_profile_without_forwarding(tmp_path):
    project = _project(tmp_path)
    (project / "neuralmind-backend.yaml").write_text("security:\n  profile: cui\n")
    doctor, check = _doctor(project)
    assert check.status == doctor.WARN and "stay on this host" in check.detail


def test_doctor_fails_on_a_refused_target(tmp_path):
    project = _project(tmp_path)
    _configure(project, "tcp://siem.example:514", "  profile: cui\n")
    doctor, check = _doctor(project)
    assert check.status == doctor.FAIL


@unix_only
def test_doctor_warns_while_records_wait(tmp_path, unix_socket):
    project = _project(tmp_path)
    _configure(project, unix_socket.path)
    AuditTrail(project).append_event("query", "run")
    doctor, check = _doctor(project)
    assert check.status == doctor.WARN
    assert "1 record(s) not yet forwarded" in check.detail and "can't send" in check.detail


def test_doctor_ok_when_everything_is_sent(tmp_path, udp):
    project = _project(tmp_path)
    _configure(project, udp.target)
    AuditTrail(project).append_event("query", "run")
    doctor, check = _doctor(project)
    assert check.status == doctor.OK and "nothing waiting" in check.detail


# --- CLI -----------------------------------------------------------------------


def _run(argv: list[str], monkeypatch) -> int:
    monkeypatch.setattr(sys, "argv", ["neuralmind", *argv])
    try:
        cli.main()
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 1
    return 0


def test_cli_forward_sends_the_backlog_and_exits_0(tmp_path, udp, monkeypatch, capsys):
    project = _project(tmp_path)
    trail = AuditTrail(project)
    for _ in range(3):
        trail.append_event("query", "run")
    _configure(project, udp.target)
    assert _run(["audit", "forward", str(project), "--json"], monkeypatch) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["sent"] == 3 and report["backlog"] == 0 and report["error"] is None
    assert len(udp.take(3)) == 3
    assert _run(["audit", "forward", str(project)], monkeypatch) == 0
    assert "Forwarded 0 record(s)" in capsys.readouterr().out


def test_the_live_path_reads_no_further_than_one_batch(tmp_path, udp, monkeypatch):
    project = _project(tmp_path)
    trail = AuditTrail(project)
    for _ in range(50):
        trail.append_event("query", "run")
    _configure(project, udp.target)
    parsed = []
    original = af._records

    def counting(log, start=0):
        for line in original(log, start):
            parsed.append(line)
            yield line

    monkeypatch.setattr(af, "_records", counting)
    result = af.forward_pending(project, limit=5)
    assert result.sent == 5 and result.backlog > 0
    assert len(parsed) < 20  # not the whole 50-record backlog


@unix_only
def test_appends_back_off_after_a_failed_send(tmp_path, unix_socket, monkeypatch):
    project = _project(tmp_path)
    _configure(project, unix_socket.path)  # nothing listens
    trail = AuditTrail(project)
    trail.append_event("query", "run")
    first_error = af.read_cursor(project)["last_error_at"]
    calls = []
    monkeypatch.setattr(af, "send", lambda *a, **k: calls.append(a))
    trail.append_event("query", "run")
    assert calls == []  # within the backoff: not even tried
    assert af.read_cursor(project)["last_error_at"] == first_error
    unix_socket.listen()
    monkeypatch.undo()
    result = af.forward_pending(project)  # `audit forward` always tries
    assert result.sent == 2 and result.error is None


def test_records_from_before_the_hash_chain_are_sent_once(tmp_path, udp):
    project = _project(tmp_path)
    log = AuditTrail(project).events_file
    log.write_text(
        "".join(json.dumps({"timestamp": f"t{i}", "action": "query"}) + "\n" for i in range(3))
    )
    _configure(project, udp.target)
    assert af.forward_pending(project).sent == 3
    udp.take(3)
    assert af.forward_pending(project).sent == 0 and udp.nothing_waiting()


def test_a_lost_position_with_nothing_to_send_is_reported_once(tmp_path, udp):
    project = _project(tmp_path)
    _configure(project, udp.target)
    AuditTrail(project).append_event("query", "run")
    udp.take(1)
    AuditTrail(project).events_file.write_text("")  # replaced by an empty log
    assert af.forward_pending(project).restarted
    udp.take(1)  # the restart note
    assert not af.forward_pending(project).restarted
    assert udp.nothing_waiting()
