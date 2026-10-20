# SPDX-License-Identifier: MIT
"""audit_forward.py — forward the audit log to syslog as it is written.

CMMC AU.L2-3.3.4 asks for an alert when audit logging fails, and AU.L2-3.3.5
for audit records that can be correlated across systems. Until now the log
left the host only when someone ran ``neuralmind audit export``. With
``security.audit_syslog`` set, every record is sent to syslog right after it
is written, and a record that can't be written raises an ``alert``-severity
message at once, which still gets out when the local disk is full.

Delivery is tracked, not assumed. ``.neuralmind/audit_forwarded.json`` notes
the last record sent; the next append, or ``neuralmind audit forward``, sends
everything after it, so a syslog daemon that was down gets the backlog when it
is back, across a rotation of the log too. A record is sent at least once:
after a failure part-way through a batch, some may arrive twice, and each
carries its ``sha256`` to deduplicate on.

NeuralMind does not encrypt the connection. Audit records hold query text,
which in a CUI enclave is CUI, so under ``security.profile: cui`` the target
must be on this machine (a unix socket, or a loopback address), and the host's
syslog daemon forwards to the SIEM over its own TLS, in the host's validated
module. Outside the profile a remote ``udp://`` or ``tcp://`` target is
accepted, in plain text.

Settings, under ``security:`` in ``neuralmind-backend.yaml``:

``audit_syslog``
    ``/dev/log`` (or ``unix:/dev/log``), ``udp://host[:port]`` or
    ``tcp://host[:port]``; the port defaults to 514.
``audit_syslog_facility``
    A syslog facility name, ``local0`` by default.
"""

from __future__ import annotations

import errno
import hashlib
import ipaddress
import json
import logging
import os
import socket
import time
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .audit import _ARCHIVE_NAME, AuditTrail, _exclusive_file_lock
from .backend_manager import backend_config_path, read_backend_config_file
from .security_config import config_mentions

logger = logging.getLogger(__name__)

CURSOR_FILE_NAME = "audit_forwarded.json"
LOCK_FILE_NAME = "audit_forward.lock"
APP_NAME = "neuralmind"
DEFAULT_PORT = 514
DEFAULT_FACILITY = "local0"
# How long one connect or send may take. The live path runs inside a query,
# a hook or a build, so a dead target must not hold it up for long.
TIMEOUT_SECONDS = 2.0
# After a failed send, appends don't try again for this long: a dead TCP
# target would otherwise add its connect timeout to every query and hook.
# `neuralmind audit forward` always tries.
RETRY_AFTER_SECONDS = 30.0
# Records sent per append at most; the rest wait for the next append or for
# `neuralmind audit forward`, so one append never sends a whole backlog.
LIVE_BATCH = 200
# A datagram must fit in one packet. RFC 5426 receivers take at least 2048
# bytes; 8 KiB is what common daemons accept. A larger record is sent without
# its `details`, which `audit export` still has.
MAX_DATAGRAM = 8192
_SETTING_KEYS = ("audit_syslog", "audit_syslog_facility")

FACILITIES = {
    "kern": 0,
    "user": 1,
    "mail": 2,
    "daemon": 3,
    "auth": 4,
    "syslog": 5,
    "lpr": 6,
    "news": 7,
    "uucp": 8,
    "cron": 9,
    "authpriv": 10,
    "ftp": 11,
    **{f"local{n}": 16 + n for n in range(8)},
}
SEVERITY_ALERT = 1
SEVERITY_ERR = 3
SEVERITY_WARNING = 4
SEVERITY_INFO = 6
_FAILED_STATUSES = {"failure", "failed", "denied", "refused", "error"}


class ForwardError(Exception):
    """The target can't be reached, or the settings can't be trusted."""


@dataclass(frozen=True)
class Target:
    kind: str  # "unix", "udp" or "tcp"
    path: str = ""
    host: str = ""
    port: int = DEFAULT_PORT

    def __str__(self) -> str:
        if self.kind == "unix":
            return self.path
        host = f"[{self.host}]" if ":" in self.host else self.host
        return f"{self.kind}://{host}:{self.port}"

    @property
    def local(self) -> bool:
        """On this machine: a unix socket, or a loopback address."""
        if self.kind == "unix":
            return True
        if self.host.lower() == "localhost":
            return True
        try:
            return ipaddress.ip_address(self.host).is_loopback
        except ValueError:
            return False


@dataclass(frozen=True)
class ForwardSettings:
    target: Target | None = None
    facility: int = FACILITIES[DEFAULT_FACILITY]
    # Why the settings can't be trusted; nothing is forwarded while it's set.
    problem: str | None = None


def parse_target(value: str) -> Target:
    """``/dev/log``, ``unix:/path``, ``udp://host[:port]`` or ``tcp://host[:port]``."""
    text = value.strip()
    if text.startswith("unix:"):
        text = text[len("unix:") :]
        if not text.startswith("/"):
            raise ForwardError(f"security.audit_syslog: {value!r} needs an absolute socket path")
        return Target("unix", path=text)
    if text.startswith("/"):
        return Target("unix", path=text)
    scheme, sep, rest = text.partition("://")
    if not sep or scheme not in ("udp", "tcp") or not rest:
        raise ForwardError(
            f"security.audit_syslog: {value!r} isn't a socket path, udp://host[:port] "
            "or tcp://host[:port]"
        )
    host, port = rest, DEFAULT_PORT
    if rest.startswith("["):
        host, _, tail = rest[1:].partition("]")
        if tail:
            if not tail.startswith(":"):
                raise ForwardError(f"security.audit_syslog: {value!r} has a malformed address")
            port = _port(tail[1:], value)
    elif rest.count(":") == 1:
        host, port_text = rest.split(":")
        port = _port(port_text, value)
    if not host or "/" in host:
        raise ForwardError(f"security.audit_syslog: {value!r} has no host")
    return Target(scheme, host=host, port=port)


def _port(text: str, value: str) -> int:
    if not text.isdigit() or not 0 < int(text) < 65536:
        raise ForwardError(f"security.audit_syslog: {value!r} has an invalid port")
    return int(text)


def load_forward_settings(project_path: str | Path) -> ForwardSettings:
    """Read ``security.audit_syslog`` and ``security.audit_syslog_facility``.

    Fails closed like the other security settings: a file that doesn't parse
    but names either setting, a malformed value, or under
    ``security.profile: cui`` a target off this machine is a ``problem``, and
    nothing is forwarded until it's fixed (``neuralmind doctor`` fails).
    """
    root = Path(project_path).resolve()
    path = backend_config_path(root)
    if path is None:
        return ForwardSettings()
    try:
        config = read_backend_config_file(path)
    except Exception as exc:
        if config_mentions(path, _SETTING_KEYS):
            return ForwardSettings(problem=f"{path.name} does not parse ({exc})")
        return ForwardSettings()
    security = config.get("security")
    if not isinstance(security, dict):
        if config_mentions(path, _SETTING_KEYS):
            return ForwardSettings(problem="`security` must be a mapping")
        return ForwardSettings()

    facility = FACILITIES[DEFAULT_FACILITY]
    if "audit_syslog_facility" in security:
        name = security["audit_syslog_facility"]
        if not isinstance(name, str) or name.strip().lower() not in FACILITIES:
            return ForwardSettings(
                problem="security.audit_syslog_facility must be a syslog facility name "
                f"({', '.join(FACILITIES)})"
            )
        facility = FACILITIES[name.strip().lower()]
    if "audit_syslog" not in security:
        return ForwardSettings(facility=facility)
    value = security["audit_syslog"]
    if not isinstance(value, str) or not value.strip():
        return ForwardSettings(problem="security.audit_syslog must be a syslog target")
    try:
        target = parse_target(value)
    except ForwardError as exc:
        return ForwardSettings(problem=str(exc))

    from .security_config import PROFILE_CUI, load_security_settings

    if not target.local and load_security_settings(root).profile == PROFILE_CUI:
        return ForwardSettings(
            problem=(
                f"security.profile: cui refuses security.audit_syslog {target}: audit records "
                "can hold CUI and NeuralMind sends them unencrypted, so the target must be on "
                "this machine (/dev/log or a loopback address). Let the host's syslog daemon "
                "forward to the SIEM over TLS."
            )
        )
    return ForwardSettings(target=target, facility=facility)


# --- messages ----------------------------------------------------------------


def severity_of(record: dict[str, Any]) -> int:
    action = str(record.get("action", ""))
    if action == "gap_recorded":
        return SEVERITY_ERR
    if str(record.get("status", "")).lower() in _FAILED_STATUSES:
        return SEVERITY_WARNING
    return SEVERITY_INFO


def _body(record: dict[str, Any], limit: int | None) -> str:
    body = json.dumps(record, sort_keys=True, separators=(",", ":"))
    if limit is None or len(body.encode("utf-8")) <= limit:
        return body
    # Keep what identifies the record (sha256 above all) and drop the bulk.
    short = {k: v for k, v in record.items() if k not in ("details", "target")}
    short["truncated"] = {"original_bytes": len(body.encode("utf-8"))}
    body = json.dumps(short, sort_keys=True, separators=(",", ":"))
    return body.encode("utf-8")[:limit].decode("utf-8", errors="ignore")


def format_message(
    record: dict[str, Any], target: Target, facility: int, severity: int | None = None
) -> bytes:
    """One syslog message for ``record``.

    RFC 5424 for a network target, timestamped with the record's own time;
    the traditional RFC 3164 form for a unix socket, which is what local
    daemons (rsyslog, syslog-ng, journald) read there. The message body is
    the record as JSON.
    """
    pri = facility * 8 + (severity_of(record) if severity is None else severity)
    pid = os.getpid()
    if target.kind == "unix":
        now = time.localtime()
        stamp = f"{time.strftime('%b', now)} {now.tm_mday:2d} {time.strftime('%H:%M:%S', now)}"
        header = f"<{pri}>{stamp} {APP_NAME}[{pid}]: "
        return (header + _body(record, MAX_DATAGRAM - len(header.encode("utf-8")))).encode()
    stamp = str(record.get("timestamp") or datetime.now(timezone.utc).isoformat())
    host = socket.gethostname() or "-"
    header = f"<{pri}>1 {stamp} {host} {APP_NAME} {pid} audit - "
    limit = MAX_DATAGRAM - len(header.encode("utf-8")) if target.kind == "udp" else None
    return (header + _body(record, limit)).encode("utf-8")


def send(target: Target, messages: list[bytes]) -> None:
    """Send ``messages`` over one connection; raise ``ForwardError`` if any fails."""
    if not messages:
        return
    try:
        if target.kind == "udp":
            family = socket.AF_INET6 if ":" in target.host else socket.AF_INET
            with socket.socket(family, socket.SOCK_DGRAM) as sock:
                sock.settimeout(TIMEOUT_SECONDS)
                for message in messages:
                    sock.sendto(message, (target.host, target.port))
        elif target.kind == "tcp":
            with socket.create_connection(
                (target.host, target.port), timeout=TIMEOUT_SECONDS
            ) as sock:
                # Octet-counting framing (RFC 6587), so a message may hold newlines.
                sock.sendall(b"".join(b"%d %s" % (len(m), m) for m in messages))
        else:
            _send_unix(target.path, messages)
    except OSError as exc:
        raise ForwardError(f"can't send to {target}: {exc}") from exc


def _send_unix(path: str, messages: list[bytes]) -> None:
    if not hasattr(socket, "AF_UNIX"):
        raise OSError("unix sockets aren't available on this platform")
    # /dev/log is a datagram socket on Linux; some daemons listen on a stream.
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as sock:
            sock.settimeout(TIMEOUT_SECONDS)
            sock.connect(path)
            for message in messages:
                sock.send(message)
        return
    except OSError as exc:
        if exc.errno != errno.EPROTOTYPE:
            raise
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.settimeout(TIMEOUT_SECONDS)
        sock.connect(path)
        sock.sendall(b"".join(m + b"\n" for m in messages))


# --- what's left to send -----------------------------------------------------


@dataclass
class _Line:
    log: Path
    start: int
    end: int
    record: dict[str, Any]


def cursor_path(project_path: str | Path) -> Path:
    return Path(project_path).resolve() / ".neuralmind" / CURSOR_FILE_NAME


def read_cursor(project_path: str | Path) -> dict[str, Any]:
    try:
        cursor = json.loads(cursor_path(project_path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return cursor if isinstance(cursor, dict) else {}


def _write_cursor(project_path: str | Path, cursor: dict[str, Any]) -> None:
    path = cursor_path(project_path)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(cursor, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _records(log: Path, start: int = 0) -> Iterator[_Line]:
    """Each complete record in ``log`` from byte ``start``.

    A last line without its newline may still be being written, so it waits
    for the next run. A line that isn't a record (damage `audit verify`
    reports) is passed over.
    """
    try:
        with log.open("rb") as handle:
            handle.seek(start)
            offset = start
            for raw in handle:
                end = offset + len(raw)
                if not raw.endswith(b"\n"):
                    return
                try:
                    record = json.loads(raw)
                except ValueError:
                    record = None
                if isinstance(record, dict):
                    yield _Line(log, offset, end, record)
                offset = end
    except FileNotFoundError:
        return


def _line_id(record: dict[str, Any]) -> str:
    """The record's ``sha256``, or for a record from before the hash chain
    (written before v0.46.2, with none), a hash of its content."""
    sha = record.get("sha256")
    if isinstance(sha, str) and sha:
        return sha
    return hashlib.sha256(json.dumps(record, sort_keys=True).encode("utf-8")).hexdigest()


def _first_sha(log: Path) -> str:
    """What names ``log`` in the cursor: its first record's id ("" if it has none)."""
    first = next(_records(log), None)
    return _line_id(first.record) if first else ""


def _chain(trail: AuditTrail) -> list[Path]:
    """The active log and the archives its rotation markers lead back to, oldest first."""
    logs = [trail.events_file]
    while True:
        first = next(_records(logs[0]), None)
        if first is None or first.record.get("action") != "rotation_continuation":
            break
        details = first.record.get("details")
        name = details.get("archive") if isinstance(details, dict) else None
        if not isinstance(name, str) or not _ARCHIVE_NAME.fullmatch(name):
            break
        archive = trail.events_file.parent / name
        if not archive.exists() or archive in logs:
            break
        logs.insert(0, archive)
    return logs


def pending(project_path: str | Path, limit: int | None = None) -> tuple[list[_Line], bool]:
    """The records not yet forwarded, oldest first, and whether the cursor was lost.

    With ``limit``, reading stops after that many: the live path runs on every
    append, and mustn't re-read a large backlog each time to send one batch.

    The cursor names the log it points into by that log's first hash, which a
    rotation's rename doesn't change, and the hash of the last record sent. If
    no log in the chain matches (the log was replaced, or the archive pruned),
    forwarding starts again from the oldest log still there.
    """
    trail = AuditTrail(project_path)
    logs = _chain(trail)
    cursor = read_cursor(project_path)
    first = cursor.get("log_first_sha256")
    last = cursor.get("last_sha256")
    start_log, start_offset, lost = 0, 0, bool(first)
    for index, log in enumerate(logs):
        if first and _first_sha(log) == first:
            try:
                at = int(cursor.get("line_start", -1))
            except (TypeError, ValueError):
                break
            line = next(_records(log, at), None) if at >= 0 else None
            if line is not None and _line_id(line.record) == last:
                start_log, start_offset, lost = index, line.end, False
            break
    lines: list[_Line] = []
    for index in range(start_log, len(logs)):
        for line in _records(logs[index], start_offset if index == start_log else 0):
            if limit is not None and len(lines) >= limit:
                return lines, lost
            lines.append(line)
    return lines, lost


# --- forwarding --------------------------------------------------------------


@dataclass
class ForwardResult:
    sent: int = 0
    # Records left after this run; with a ``limit``, at most one more than it
    # read, so only "some" or "none".
    backlog: int = 0
    error: str | None = None
    restarted: bool = False


def forward_pending(
    project_path: str | Path,
    settings: ForwardSettings | None = None,
    *,
    limit: int | None = None,
) -> ForwardResult:
    """Send the records not yet forwarded, up to ``limit``; never raises.

    One run at a time per project. The cursor moves past each batch only once
    it is sent; a failure is noted in the cursor file (``last_error``), where
    ``neuralmind doctor`` reports it, and the records wait for the next run.
    """
    root = Path(project_path).resolve()
    settings = settings or load_forward_settings(root)
    result = ForwardResult()
    if settings.problem:
        result.error = settings.problem
        return result
    target = settings.target
    if target is None:
        return result
    lock = root / ".neuralmind" / LOCK_FILE_NAME
    if not lock.parent.is_dir():
        return result
    try:
        with _exclusive_file_lock(lock):
            return _forward_locked(root, target, settings.facility, limit, result)
    except OSError as exc:
        result.error = f"can't lock {lock}: {exc}"
        return result


def _backing_off(cursor: dict[str, Any]) -> bool:
    """Whether the last send failed less than ``RETRY_AFTER_SECONDS`` ago."""
    try:
        failed = datetime.fromisoformat(str(cursor["last_error_at"]))
    except (KeyError, ValueError):
        return False
    age = (datetime.now(timezone.utc) - failed).total_seconds()
    return 0 <= age < RETRY_AFTER_SECONDS


def _forward_locked(
    root: Path, target: Target, facility: int, limit: int | None, result: ForwardResult
) -> ForwardResult:
    cursor = read_cursor(root)
    if limit is not None and _backing_off(cursor):
        # The live path: leave the records for the next try, without waiting.
        result.error = f"{cursor.get('last_error')} (retrying after {RETRY_AFTER_SECONDS:.0f} s)"
        result.backlog = 1
        return result
    # One more than the batch, to know whether any are left after it.
    lines, lost = pending(root, None if limit is None else limit + 1)
    messages: list[bytes] = []
    if lost:
        result.restarted = True
        messages.append(
            _note(
                target,
                facility,
                SEVERITY_WARNING,
                "audit_forward_restarted",
                "the forwarding position was lost (the log was replaced, or the archive "
                "holding it was pruned); forwarding again from the oldest log present, "
                "so some records may arrive twice",
            )
        )
    batch = lines if limit is None else lines[:limit]
    messages.extend(format_message(line.record, target, facility) for line in batch)
    result.backlog = len(lines) - len(batch)
    if not messages:
        return result
    now = datetime.now(timezone.utc).isoformat()
    try:
        send(target, messages)
    except ForwardError as exc:
        result.error = str(exc)
        result.backlog = len(lines)
        cursor.update(last_error=str(exc), last_error_at=now)
        _save(root, cursor)
        logger.warning("audit forwarding to %s failed: %s", target, exc)
        return result
    result.sent = len(batch)
    if lost and not batch:
        # Lost, with nothing to send: forget the old position, or the
        # restart message would be sent again on every run.
        for key in ("log_first_sha256", "line_start", "last_sha256"):
            cursor.pop(key, None)
    if batch:
        last = batch[-1]
        cursor.update(
            log_first_sha256=_first_sha(last.log),
            line_start=last.start,
            last_sha256=_line_id(last.record),
            last_forwarded_at=now,
            target=str(target),
        )
    cursor.pop("last_error", None)
    cursor.pop("last_error_at", None)
    _save(root, cursor)
    return result


def _save(root: Path, cursor: dict[str, Any]) -> None:
    try:
        _write_cursor(root, cursor)
    except OSError as exc:
        # The records went out; the next run sends them again rather than none.
        logger.warning("can't save the audit forwarding position: %s", exc)


def _note(target: Target, facility: int, severity: int, event: str, message: str) -> bytes:
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "category": "audit",
        "action": event,
        "message": message,
    }
    return format_message(record, target, facility, severity)


def send_write_failure_alert(project_path: str | Path, event: str, error: str) -> bool:
    """Raise an ``alert``-severity message for an audit record that wasn't written.

    The AU.L2-3.3.4 alert. Sent straight away rather than through the log,
    which is what failed. Returns whether it was sent; never raises.
    """
    try:
        settings = load_forward_settings(project_path)
        if settings.problem or settings.target is None:
            return False
        message = _note(
            settings.target,
            settings.facility,
            SEVERITY_ALERT,
            "audit_write_failed",
            f"audit record {event} couldn't be written to "
            f"{AuditTrail(project_path).events_file}: {error}",
        )
        send(settings.target, [message])
        return True
    except Exception as exc:
        logger.warning("couldn't send the audit write-failure alert: %s", exc)
        return False
