# SPDX-License-Identifier: MIT
"""hardening.py — the SP 800-53 hardening baseline, checked automatically.

``docs/compliance/SP800-53-HARDENING.md`` is the guide: each rule, the SP
800-53 Rev. 5 controls it supports, why, and how to meet it. This module holds
the same rules as code, so ``neuralmind hardening`` can check a project and
the host it runs on, and an assessor gets the result as evidence instead of a
screenshot of a YAML file.

Every rule checks something NeuralMind can observe: a setting as NeuralMind
actually reads it (machine policy included), the volume and the OS FIPS mode
as ``storage_guard`` sees them, the audit log and its checkpoints as
``audit verify`` checks them, and the running daemon. What NeuralMind can't
observe (clock sync, the syslog daemon's TLS, the SIEM) stays in the guide's
"Checked by you" list.

A rule that can't be determined fails: a baseline check that passes what it
couldn't see is no check. The one exception is a rule that doesn't apply on
the platform (POSIX permission bits on Windows, the OS FIPS mode on macOS,
which has no switch to read), which is ``n/a``.
"""

from __future__ import annotations

import stat
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

PASS = "pass"  # nosec B105 - a rule status, not a password
FAIL = "fail"
NA = "n/a"

BASELINE = "neuralmind-sp800-53-hardening"


@dataclass
class Result:
    status: str
    detail: str
    fix: str = ""


@dataclass(frozen=True)
class Rule:
    id: str
    title: str
    controls: tuple[str, ...]
    check: Callable[[Path], Result]


def _ok(detail: str) -> Result:
    return Result(PASS, detail)


def _fail(detail: str, fix: str) -> Result:
    return Result(FAIL, detail, fix)


# --- configuration ----------------------------------------------------------


def _profile(project: Path) -> Result:
    from .security_config import PROFILE_CUI, load_security_settings

    settings = load_security_settings(project)
    if settings.problem:
        return _fail(
            f"the security settings are invalid: {settings.problem}",
            "Correct the security: section.",
        )
    if settings.profile != PROFILE_CUI:
        return _fail(
            "security.profile isn't cui, so listeners beyond loopback, listeners without "
            "their token, and LLM documentation seeding are allowed",
            "Set security.profile: cui in the machine policy.",
        )
    return _ok("security.profile: cui")


def _machine_policy(project: Path) -> Result:
    from . import security_config
    from .security_config import PROFILE_CUI, load_machine_policy

    path = security_config.MACHINE_POLICY_PATH
    machine = load_machine_policy()
    if machine is None:
        return _fail(
            f"no machine policy at {path}, so whoever owns the project directory can "
            "delete neuralmind-backend.yaml and switch its settings off",
            f"As root, write {path} with security.profile: cui, owned by root and "
            "writable only by root.",
        )
    if machine.problem:
        return _fail(machine.problem, f"Fix {path}.")
    if machine.profile != PROFILE_CUI:
        return _fail(
            f"{path} doesn't set security.profile: cui",
            f"Add security.profile: cui to {path}.",
        )
    return _ok(f"{path} sets security.profile: cui")


def _identity(project: Path) -> Result:
    from .mcp_security import role_policy_problem
    from .security_config import IDENTITY_OS, load_security_settings

    problem = role_policy_problem(project)
    if problem:
        return _fail(f"MCP calls are refused: {problem}", "Fix security.roles or rate_limit.")
    settings = load_security_settings(project)
    if settings.identity != IDENTITY_OS:
        return _fail(
            f"security.identity is {settings.identity}, so an MCP caller names its own "
            "actor and role",
            "Set security.identity: os (security.profile: cui sets it).",
        )
    return _ok(f"identity: os; {len(settings.users)} account(s) in security.users")


def _default_role(project: Path) -> Result:
    from .security_config import load_security_settings

    role = load_security_settings(project).default_role
    if role not in (None, "reader"):
        return _fail(
            f"security.default_role is {role}, so every OS account missing from "
            f"security.users gets {role}",
            "Leave security.default_role unset, or set it to reader, and name each "
            "account that needs more in security.users.",
        )
    if role is None:
        return _ok("unset: an account missing from security.users is refused")
    return _ok("reader")


def _posix_only() -> Result | None:
    if sys.platform == "win32":
        return Result(
            NA, "Windows permissions are ACLs, not mode bits; restrict them as the guide says"
        )
    return None


def _not_writable_by_others(path: Path, what: str, fix: str) -> Result:
    try:
        mode = path.stat().st_mode
    except OSError as exc:
        return _fail(f"can't check {path}: {exc}", fix)
    writers = [n for bit, n in ((stat.S_IWGRP, "group"), (stat.S_IWOTH, "others")) if mode & bit]
    if writers:
        return _fail(f"{what} {path} is writable by {' and '.join(writers)}", fix)
    return _ok(f"{what} {path} is writable by its owner only")


def _config_permissions(project: Path) -> Result:
    from .backend_manager import backend_config_path

    na = _posix_only()
    if na:
        return na
    path = backend_config_path(project)
    if path is None:
        return _ok("no project security file; the machine policy alone applies")
    return _not_writable_by_others(path, "the project's settings file", f"chmod go-w {path}")


def _state_permissions(project: Path) -> Result:
    na = _posix_only()
    if na:
        return na
    state = project / ".neuralmind"
    if not state.exists():
        return _ok("no .neuralmind/ yet")
    return _not_writable_by_others(state, "the state directory", f"chmod go-w {state}")


# --- host -------------------------------------------------------------------


def _storage(project: Path) -> Result:
    from .security_config import load_security_settings
    from .storage_guard import check_storage

    required = load_security_settings(project).require_encrypted_storage
    status = check_storage(project)
    if status.encrypted is not True:
        return _fail(
            f"the volume isn't verified as encrypted: {status.detail}",
            "Turn on FIPS-validated full-disk encryption (FileVault, BitLocker, LUKS).",
        )
    if not required:
        return _fail(
            f"{status.detail}, but security.require_encrypted_storage is off, so NeuralMind "
            "would run on an unencrypted volume",
            "Set security.require_encrypted_storage: true (security.profile: cui sets it).",
        )
    return _ok(f"{status.detail}; required")


def _os_fips(project: Path) -> Result:
    from .storage_guard import check_storage

    fips = check_storage(project).fips_mode
    if fips is True:
        return _ok("OS FIPS mode on")
    if fips is None and sys.platform == "darwin":
        return Result(
            NA,
            "macOS has no FIPS mode switch; FileVault uses Apple corecrypto, so check its "
            "CMVP certificate by hand",
        )
    state = "off" if fips is False else "could not be determined"
    return _fail(f"OS FIPS mode {state}", "Enable the OS FIPS mode.")


def _signing_openssl() -> tuple[str, bool]:
    """The OpenSSL that ``cryptography`` signs checkpoints with, and whether
    it runs in FIPS mode."""
    from cryptography.hazmat.bindings._rust import openssl as rust_openssl

    return rust_openssl.openssl_version_text(), bool(rust_openssl.is_fips_enabled())


def _checkpoint_crypto(project: Path) -> Result:
    try:
        version, fips = _signing_openssl()
    except Exception as exc:  # an old cryptography, or none: can't tell
        return _fail(
            f"can't tell whether checkpoint signing uses FIPS mode: {exc}",
            "Install a current cryptography, built against the system OpenSSL.",
        )
    if not fips:
        return _fail(
            f"checkpoint signing runs in {version} without FIPS mode; the prebuilt "
            "cryptography wheel bundles an OpenSSL that isn't FIPS-validated",
            "pip install --force-reinstall --no-cache-dir --no-binary cryptography "
            "cryptography, on a host whose OpenSSL uses its validated FIPS provider.",
        )
    return _ok(f"checkpoint signing runs in {version} with FIPS mode on")


def _daemon(project: Path) -> Result:
    from .doctor import _running_daemon_exposure

    exposure = _running_daemon_exposure()
    if exposure:
        return _fail(
            f"the running daemon is exposed: {exposure}",
            "Run `neuralmind daemon restart` (127.0.0.1, token on).",
        )
    return _ok("no daemon is listening beyond loopback or without its token")


# --- audit ------------------------------------------------------------------


def _audit_chain(project: Path) -> Result:
    from .audit import AuditTrail

    result = AuditTrail(project).verify()
    if not result["ok"]:
        line = result.get("first_bad_line")
        where = f" at line {line}" if line else ""
        return _fail(
            f"the audit log doesn't verify{where}: {result.get('reason')}",
            "Run `neuralmind audit verify` and investigate.",
        )
    return _ok(f"the hash chain verifies ({result['total']} record(s))")


def _audit_writes(project: Path) -> Result:
    from .audit import AuditTrail

    trail = AuditTrail(project)
    try:
        lines = trail.unrecorded_failures()
    except OSError as exc:
        return _fail(f"can't read {trail.failures_file}: {exc}", "Fix the permissions.")
    if lines:
        return _fail(
            f"{len(lines)} audit record(s) couldn't be written and the log doesn't say so",
            f"Fix the cause, then run `neuralmind audit record-gap {project}`.",
        )
    return _ok("every failed audit write, if any, is recorded in the log as a gap")


def _checkpoint_signed(project: Path) -> Result:
    from .audit_checkpoint import load_checkpoint_settings, verify_checkpoints

    settings = load_checkpoint_settings(project)
    if settings.problem:
        return _fail(settings.problem, "Fix security.audit_checkpoint_key.")
    if not settings.public_key_b64:
        return _fail(
            "security.audit_checkpoint_key isn't set, so checkpoints aren't signed",
            "Create one with `neuralmind audit keygen` in an administrator account.",
        )
    report = verify_checkpoints(project)
    if not report.ok:
        return _fail(
            report.reason or "the checkpoints don't verify",
            "Run `neuralmind audit verify` and investigate.",
        )
    return _ok(f"checkpoints verify against key {report.key_id or 'set'}")


def _checkpoint_anchored(project: Path) -> Result:
    from .audit_checkpoint import load_checkpoint_settings

    settings = load_checkpoint_settings(project)
    if settings.problem:
        return _fail(settings.problem, "Fix security.audit_anchor_dir.")
    if settings.anchor_dir is None:
        return _fail(
            "security.audit_anchor_dir isn't set, so every checkpoint copy is beside the log",
            "Set it to a directory only the administrator can write.",
        )
    if not settings.anchor_dir.is_dir():
        return _fail(
            f"the anchor directory {settings.anchor_dir} doesn't exist",
            "Create it, writable only by the administrator.",
        )
    return _ok(f"anchored in {settings.anchor_dir}")


def _checkpoint_recent(project: Path) -> Result:
    from .audit_checkpoint import latest_checkpoint_age_days, verify_checkpoints
    from .doctor import CHECKPOINT_MAX_AGE_DAYS

    report = verify_checkpoints(project)
    age = latest_checkpoint_age_days(report) if report.ok else None
    fix = "Schedule `neuralmind audit checkpoint` daily, as the key's owner."
    if age is None:
        return _fail("no verified checkpoint has been taken", fix)
    if age > CHECKPOINT_MAX_AGE_DAYS:
        return _fail(f"the newest checkpoint is {age:.0f} days old", fix)
    return _ok(f"the newest checkpoint is {age:.1f} days old")


def _forward_target(project: Path) -> Result:
    from .audit_forward import load_forward_settings

    settings = load_forward_settings(project)
    if settings.problem:
        return _fail(settings.problem, "Fix security.audit_syslog.")
    if settings.target is None:
        return _fail(
            "security.audit_syslog isn't set, so records stay on this host and a failed "
            "audit write raises no alert",
            "Set security.audit_syslog: /dev/log and let the host's syslog daemon forward "
            "to your SIEM over TLS.",
        )
    if not settings.target.local:
        return _fail(
            f"{settings.target} is off this machine, and NeuralMind sends records unencrypted",
            "Point it at /dev/log or a loopback address and let the host's syslog daemon "
            "forward over TLS.",
        )
    return _ok(f"forwarded to {settings.target}")


def _forward_current(project: Path) -> Result:
    from .audit_forward import load_forward_settings, pending, read_cursor

    settings = load_forward_settings(project)
    if settings.problem or settings.target is None:
        return _fail("forwarding isn't set up (NMH-16)", "Meet NMH-16 first.")
    try:
        waiting, _ = pending(project)
    except OSError as exc:
        return _fail(f"can't read the audit log: {exc}", "Fix the permissions.")
    if waiting:
        error = read_cursor(project).get("last_error")
        why = f"; the last attempt failed: {error}" if error else ""
        return _fail(
            f"{len(waiting)} record(s) not yet forwarded{why}",
            f"Check the syslog daemon, then run `neuralmind audit forward {project}`.",
        )
    return _ok("nothing waiting")


RULES: tuple[Rule, ...] = (
    Rule("NMH-01", "The hardened profile is on", ("cm-6", "cm-7", "sc-8"), _profile),
    Rule("NMH-02", "The machine policy sets it", ("cm-5", "cm-6"), _machine_policy),
    Rule("NMH-03", "Identity comes from the OS account", ("ia-2", "ac-3"), _identity),
    Rule("NMH-04", "No role beyond reader by default", ("ac-6",), _default_role),
    Rule(
        "NMH-05",
        "The project's settings file is writable by its owner only",
        ("ac-3", "cm-5"),
        _config_permissions,
    ),
    Rule(
        "NMH-06",
        "The state directory is writable by its owner only",
        ("au-9",),
        _state_permissions,
    ),
    Rule("NMH-07", "Encrypted storage is verified and required", ("sc-28",), _storage),
    Rule("NMH-08", "The OS FIPS mode is on", ("sc-13",), _os_fips),
    Rule(
        "NMH-09",
        "Checkpoint signing runs in a FIPS-mode OpenSSL",
        ("sc-13", "au-9.3"),
        _checkpoint_crypto,
    ),
    Rule(
        "NMH-10",
        "No daemon serves beyond loopback or without its token",
        ("cm-7", "sc-8"),
        _daemon,
    ),
    Rule("NMH-11", "The audit log's hash chain verifies", ("au-9",), _audit_chain),
    Rule("NMH-12", "No audit write failure is unrecorded", ("au-5",), _audit_writes),
    Rule("NMH-13", "Checkpoints are signed and verify", ("au-9", "au-9.3"), _checkpoint_signed),
    Rule(
        "NMH-14",
        "Checkpoints are anchored outside the project",
        ("au-9.2",),
        _checkpoint_anchored,
    ),
    Rule("NMH-15", "The newest checkpoint is under a week old", ("au-9",), _checkpoint_recent),
    Rule(
        "NMH-16",
        "Audit records are forwarded to a local syslog",
        ("au-4.1", "au-6.3", "sc-8"),
        _forward_target,
    ),
    Rule(
        "NMH-17",
        "No audit record is waiting to be forwarded",
        ("au-4.1", "au-5"),
        _forward_current,
    ),
)


@dataclass
class Finding:
    rule: Rule
    result: Result

    def to_dict(self) -> dict:
        return {
            "id": self.rule.id,
            "title": self.rule.title,
            "controls": list(self.rule.controls),
            "status": self.result.status,
            "detail": self.result.detail,
            "fix": self.result.fix,
        }


def check(project_path: str | Path) -> list[Finding]:
    """Every rule's result for this project on this host, in rule order.

    A rule that raises fails with the error: one subsystem that can't be read
    never hides the others, and never passes.
    """
    project = Path(project_path).resolve()
    findings = []
    for rule in RULES:
        try:
            result = rule.check(project)
        except Exception as exc:
            result = _fail(f"couldn't be checked: {exc}", "Investigate the error above.")
        findings.append(Finding(rule, result))
    return findings


def control_label(control_id: str) -> str:
    """``au-9.3`` -> ``AU-9(3)``, as SP 800-53 writes it."""
    family, _, rest = control_id.partition("-")
    base, _, enhancement = rest.partition(".")
    return f"{family.upper()}-{base}" + (f"({enhancement})" if enhancement else "")
