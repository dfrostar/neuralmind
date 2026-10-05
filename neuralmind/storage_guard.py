"""storage_guard.py — is this project's state on an encrypted volume?

NeuralMind does not encrypt ``.neuralmind/`` itself. CMMC (SC.L2-3.13.11 and
3.13.16) asks for FIPS-validated cryptography protecting CUI at rest, and the
OpenSSL inside a pip-installed ``cryptography`` wheel is not FIPS-validated,
so encrypting in-process would not satisfy the control. The accepted answer is
full-disk encryption the OS provides — FileVault, BitLocker, dm-crypt/LUKS —
and this module verifies it is there.

``check_storage()`` reports what it can see and never raises. With
``security.require_encrypted_storage: true``, ``enforce_storage_policy()``
turns anything short of a positive answer into a refusal: "couldn't tell"
counts as not encrypted. Each verdict is written to the audit log once per
process, so an assessor gets a dated record of the check.

What it does not prove: that the encryption module is FIPS-validated for your
OS build, or that the volume stays encrypted after the check. ``fips_mode``
reports the OS FIPS switch where one exists (Linux, Windows); macOS has none,
and FileVault's validation status is a matter of Apple's CMVP certificates.
"""

from __future__ import annotations

import plistlib
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from .security_config import load_security_settings
from .state_dir import STATE_DIR_NAME

_TIMEOUT_SECONDS = 10


@dataclass(frozen=True)
class StorageStatus:
    """``encrypted`` is True, False, or None when the check couldn't tell."""

    encrypted: bool | None
    method: str
    fips_mode: bool | None
    detail: str

    def to_dict(self) -> dict:
        return asdict(self)


class StorageNotVerifiedError(PermissionError):
    """``require_encrypted_storage`` is on and the volume isn't verified encrypted."""


# --- parsers: pure functions over command output, so tests run anywhere ----


def parse_macos(diskutil_plist: bytes) -> StorageStatus:
    """Read ``diskutil info -plist <mount point>``.

    Apple silicon encrypts every internal APFS volume in hardware, so
    ``Encryption`` is true even with FileVault off — but then the key is
    available without the user's password, which is not protection at rest.
    Only ``FileVault`` counts.
    """
    try:
        info = plistlib.loads(diskutil_plist)
    except Exception as exc:
        return StorageStatus(None, "", None, f"could not read diskutil output ({exc})")
    mount = info.get("MountPoint", "?")
    if info.get("FileVault") is True:
        return StorageStatus(
            True,
            "FileVault",
            None,
            f"{mount}: FileVault on (macOS has no FIPS mode switch; FileVault uses "
            "Apple corecrypto, whose validation is listed in Apple's CMVP certificates)",
        )
    if info.get("Encryption") is True:
        return StorageStatus(
            False,
            "",
            None,
            f"{mount}: hardware-encrypted but FileVault is off, so the key isn't "
            "protected by a password; turn on FileVault",
        )
    return StorageStatus(False, "", None, f"{mount}: not encrypted")


def parse_linux(source: str, lsblk_types: str, fips_enabled: str | None) -> StorageStatus:
    """Read ``findmnt``'s source device and ``lsblk -s -o TYPE`` for it.

    ``lsblk -s`` lists the device and every device beneath it, so a
    filesystem on LUKS shows a ``crypt`` layer somewhere in that list.
    """
    fips = None if fips_enabled is None else fips_enabled.strip() == "1"
    types = {line.strip() for line in lsblk_types.splitlines() if line.strip()}
    if not source.startswith("/dev/"):
        return StorageStatus(
            None,
            "",
            fips,
            f"{source or 'unknown source'} is not a block device, so it can't be checked",
        )
    if "crypt" in types:
        return StorageStatus(True, "dm-crypt/LUKS", fips, f"{source}: dm-crypt layer present")
    if not types:
        return StorageStatus(None, "", fips, f"{source}: lsblk reported nothing")
    return StorageStatus(
        False, "", fips, f"{source}: no dm-crypt layer ({', '.join(sorted(types))})"
    )


# Shell.Application's System.Volume.BitLockerProtection values. Only "on"
# states count; encrypting, decrypting and suspended are not verified.
_BITLOCKER_ON = {"1": "on", "6": "on (locked)"}
_BITLOCKER_OTHER = {
    "2": "off",
    "3": "encrypting",
    "4": "decrypting",
    "5": "suspended",
}


def parse_windows(drive: str, protection: str, fips_policy: int | None) -> StorageStatus:
    fips = None if fips_policy is None else fips_policy == 1
    value = protection.strip()
    if value in _BITLOCKER_ON:
        return StorageStatus(True, "BitLocker", fips, f"{drive} BitLocker {_BITLOCKER_ON[value]}")
    if value == "2":
        return StorageStatus(False, "", fips, f"{drive} BitLocker off")
    state = _BITLOCKER_OTHER.get(value, f"state {value!r}" if value else "no answer")
    return StorageStatus(
        None, "", fips, f"{drive} BitLocker {state}, not verified as protecting the volume"
    )


# --- probes -----------------------------------------------------------------


def _run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, timeout=_TIMEOUT_SECONDS, check=False)


def _check_macos(path: Path) -> StorageStatus:
    df = _run(["df", "-P", str(path)])
    lines = df.stdout.decode("utf-8", "replace").strip().splitlines()
    if df.returncode != 0 or len(lines) < 2:
        return StorageStatus(None, "", None, "df could not find the mount point")
    mount = lines[-1].split(None, 5)[-1]
    info = _run(["diskutil", "info", "-plist", mount])
    if info.returncode != 0:
        return StorageStatus(None, "", None, f"diskutil could not describe {mount}")
    return parse_macos(info.stdout)


def _check_linux(path: Path) -> StorageStatus:
    try:
        fips_text: str | None = Path("/proc/sys/crypto/fips_enabled").read_text()
    except OSError:
        fips_text = None
    found = _run(["findmnt", "-n", "-o", "SOURCE", "--target", str(path)])
    source = found.stdout.decode("utf-8", "replace").strip().splitlines()
    source_dev = source[0].split("[", 1)[0] if source else ""
    if not source_dev.startswith("/dev/"):
        return parse_linux(source_dev, "", fips_text)
    lsblk = _run(["lsblk", "-n", "-s", "-o", "TYPE", source_dev])
    return parse_linux(source_dev, lsblk.stdout.decode("utf-8", "replace"), fips_text)


def _check_windows(path: Path) -> StorageStatus:
    drive = path.drive or "C:"
    script = (
        "(New-Object -ComObject Shell.Application).NameSpace('"
        + drive
        + "\\').Self.ExtendedProperty('System.Volume.BitLockerProtection')"
    )
    result = _run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script])
    fips_policy = None
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Control\Lsa\FipsAlgorithmPolicy",
        ) as key:
            fips_policy = int(winreg.QueryValueEx(key, "Enabled")[0])
    except (ImportError, OSError, ValueError):
        pass
    return parse_windows(drive, result.stdout.decode("utf-8", "replace"), fips_policy)


def check_storage(path: str | Path) -> StorageStatus:
    """Report whether ``path`` sits on an encrypted volume. Never raises."""
    target = Path(path).resolve()
    try:
        if sys.platform == "darwin":
            return _check_macos(target)
        if sys.platform.startswith("linux"):
            return _check_linux(target)
        if sys.platform == "win32":
            return _check_windows(target)
        return StorageStatus(None, "", None, f"no storage check for platform {sys.platform}")
    except (OSError, subprocess.SubprocessError) as exc:
        return StorageStatus(None, "", None, f"storage check failed ({exc})")


# --- enforcement ------------------------------------------------------------

# One verdict per location per process: encryption doesn't change between two
# tool calls, and the audit log should get one record, not one per call.
_VERDICTS: dict[str, StorageStatus] = {}


def enforce_storage_policy(
    project_path: str | Path, *also: str | Path | None
) -> StorageStatus | None:
    """Refuse to go on when the project requires encrypted storage and lacks it.

    Checks every place state can land: the project root, ``.neuralmind/``
    (following a symlink to wherever it points), and each path in ``also`` —
    callers pass a custom vector-index location there, which may sit on
    another volume entirely. Returns None when the project doesn't require
    encryption, the project root's status when every location is verified,
    and raises ``StorageNotVerifiedError`` naming the first that isn't.
    """
    project = Path(project_path).resolve()
    settings = load_security_settings(project)
    if not settings.require_encrypted_storage:
        return None

    targets = [project, project / STATE_DIR_NAME, *(Path(p) for p in also if p)]
    first: StorageStatus | None = None
    for target in targets:
        location = _nearest_existing(target.resolve())
        key = str(location)
        status = _VERDICTS.get(key)
        if status is None:
            status = check_storage(location)
            _VERDICTS[key] = status
            _audit(project, location, status)
        if status.encrypted is not True:
            reason = f"{location}: {status.detail}"
            if settings.problem:
                reason += f" ({settings.problem})"
            raise StorageNotVerifiedError(
                "security.require_encrypted_storage is on and this project's state "
                f"location is not verified as encrypted: {reason}"
            )
        first = first or status
    return first


def _nearest_existing(path: Path) -> Path:
    """The path itself, or its closest ancestor that exists, so a not-yet-
    created directory is checked on the volume it will be created on."""
    for candidate in (path, *path.parents):
        if candidate.exists():
            return candidate
    return path


def _audit(project: Path, location: Path, status: StorageStatus) -> None:
    try:
        from .audit import get_audit_trail

        get_audit_trail(project).append_event(
            category="security",
            action="storage_check",
            status="success" if status.encrypted is True else "denied",
            target=str(location),
            details=status.to_dict(),
        )
    except Exception:
        pass  # the refusal itself must not depend on the audit write
