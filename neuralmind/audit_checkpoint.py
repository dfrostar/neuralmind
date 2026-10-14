"""audit_checkpoint.py — signed, anchored checkpoints of the audit log.

The audit log's hash chain (``audit.py``) shows a record changed or removed in
the middle of the log. It can't show records removed from the end, or a chain
recomputed from scratch by anyone who can write the file: the hash has no
secret. A checkpoint closes both gaps for everything it covers.

A checkpoint records how many records the log held and the hash of the last
one (and of the first, to tell a rotation from a rewrite). It is signed with an
ECDSA P-256 key that the developer's account can't read, and the matching
public key is pinned in the admin-owned ``neuralmind-backend.yaml``. Each
checkpoint chains to the one before it. ``neuralmind audit verify`` then
fails when:

- the log holds fewer records than a checkpoint covers (records removed from
  the end);
- the record a checkpoint ends on no longer has the hash it recorded (the
  chain was rewritten);
- a checkpoint's signature doesn't verify, is missing while a key is pinned,
  or the checkpoints' own chain has a gap or a fork.

Checkpoints are written to ``.neuralmind/audit_checkpoints.jsonl`` and, when
``security.audit_anchor_dir`` is set, to a file in that directory too. The
local copy is a convenience the developer can delete; the anchored copy, in a
directory only the administrator can write, is what makes deletion visible.
Records written after the newest checkpoint are covered only by the hash chain
until the next one, so the checkpoint interval is the detection window.

ECDSA P-256 with SHA-256 (FIPS 186-5) is used rather than Ed25519 because
every OpenSSL FIPS provider offers it, and CMMC SC.L2-3.13.11 hosts run one.

Settings, under ``security:`` in ``neuralmind-backend.yaml``:

``audit_checkpoint_key``
    The base64 DER public key printed by ``neuralmind audit keygen``. When
    set, every checkpoint must carry a valid signature from it.
``audit_anchor_dir``
    A directory for the anchored copy, relative to the project or absolute.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .audit import _ARCHIVE_NAME, AUDIT_FILE_NAME, AuditTrail
from .backend_manager import backend_config_path, read_backend_config_file
from .security_config import config_mentions

CHECKPOINTS_FILE_NAME = "audit_checkpoints.jsonl"
FORMAT = "neuralmind-audit-checkpoint-v1"
KEY_ENV = "NEURALMIND_AUDIT_KEY"
_GENESIS = "0" * 64
_SETTING_KEYS = ("audit_checkpoint_key", "audit_anchor_dir")
_SHA256_HEX = re.compile(r"[0-9a-f]{64}")


class CheckpointError(Exception):
    """A checkpoint can't be written, or the checkpoints can't be trusted."""


# --- keys --------------------------------------------------------------------


def generate_key(path: str | Path, *, force: bool = False) -> str:
    """Write a new ECDSA P-256 private key to ``path`` (mode 0600).

    Returns the public key as base64 DER, the value for
    ``security.audit_checkpoint_key``. Refuses to overwrite a file unless
    ``force``.
    """
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    target = Path(path).expanduser()
    if target.exists() and not force:
        raise CheckpointError(f"{target} already exists; pass --force to replace it")
    key = ec.generate_private_key(ec.SECP256R1())
    pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    # The key only ever goes into a file this call creates, mode 0600. Opening
    # an existing file keeps its permissions, so --force writes a new file
    # and moves it over the old one rather than truncating it in place.
    staging = target.with_name(f".{target.name}.{os.getpid()}.tmp") if force else target
    try:
        fd = os.open(staging, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise CheckpointError(f"{target} already exists; pass --force to replace it") from exc
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(pem)
        if force:
            os.replace(staging, target)
    finally:
        if force:
            staging.unlink(missing_ok=True)
    return public_key_b64(key.public_key())


def load_private_key(path: str | Path):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    try:
        data = Path(path).expanduser().read_bytes()
    except OSError as exc:
        raise CheckpointError(f"can't read the signing key: {exc}") from exc
    try:
        key = serialization.load_pem_private_key(data, password=None)
    except (ValueError, TypeError) as exc:
        raise CheckpointError(f"{path} isn't an unencrypted PEM private key") from exc
    if not isinstance(key, ec.EllipticCurvePrivateKey) or key.curve.name != "secp256r1":
        raise CheckpointError(f"{path} isn't an ECDSA P-256 key (neuralmind audit keygen)")
    return key


def public_key_b64(public_key) -> str:
    from cryptography.hazmat.primitives import serialization

    der = public_key.public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    return base64.b64encode(der).decode("ascii")


def load_public_key(value: str):
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    try:
        key = serialization.load_der_public_key(base64.b64decode(value, validate=True))
    except (ValueError, TypeError) as exc:
        raise CheckpointError(
            "security.audit_checkpoint_key isn't a base64 DER public key"
        ) from exc
    if not isinstance(key, ec.EllipticCurvePublicKey) or key.curve.name != "secp256r1":
        raise CheckpointError("security.audit_checkpoint_key isn't an ECDSA P-256 key")
    return key


def key_id(public_key) -> str:
    """A short, stable name for a public key: its DER's sha256, 16 hex digits."""
    der = base64.b64decode(public_key_b64(public_key))
    return hashlib.sha256(der).hexdigest()[:16]


# --- settings ----------------------------------------------------------------


@dataclass(frozen=True)
class CheckpointSettings:
    public_key_b64: str | None = None
    anchor_dir: Path | None = None
    # Why the settings can't be trusted; verification fails while it's set.
    problem: str | None = None

    @property
    def configured(self) -> bool:
        return bool(self.public_key_b64 or self.anchor_dir)


def load_checkpoint_settings(project_path: str | Path) -> CheckpointSettings:
    """Read ``security.audit_checkpoint_key`` and ``security.audit_anchor_dir``.

    A file that doesn't parse but names either setting, a malformed value, or
    a key that doesn't load is a ``problem``: verification fails rather than
    quietly checking less.
    """
    root = Path(project_path).resolve()
    path = backend_config_path(root)
    if path is None:
        return CheckpointSettings()
    try:
        config = read_backend_config_file(path)
    except Exception as exc:
        if config_mentions(path, _SETTING_KEYS):
            return CheckpointSettings(problem=f"{path.name} does not parse ({exc})")
        return CheckpointSettings()
    security = config.get("security")
    if not isinstance(security, dict):
        if config_mentions(path, _SETTING_KEYS):
            return CheckpointSettings(problem="`security` must be a mapping")
        return CheckpointSettings()

    key = security.get("audit_checkpoint_key")
    anchor = security.get("audit_anchor_dir")
    if "audit_checkpoint_key" in security and (not isinstance(key, str) or not key.strip()):
        return CheckpointSettings(problem="security.audit_checkpoint_key must be a public key")
    if "audit_anchor_dir" in security and (not isinstance(anchor, str) or not anchor.strip()):
        return CheckpointSettings(problem="security.audit_anchor_dir must be a directory path")
    if key:
        try:
            load_public_key(key.strip())
        except CheckpointError as exc:
            return CheckpointSettings(problem=str(exc))
    anchor_dir = None
    if anchor:
        anchor_dir = Path(os.path.expanduser(anchor.strip()))
        if not anchor_dir.is_absolute():
            anchor_dir = root / anchor_dir
    return CheckpointSettings(
        public_key_b64=key.strip() if key else None,
        anchor_dir=anchor_dir,
    )


# --- checkpoint files --------------------------------------------------------


def local_checkpoints_path(project_path: str | Path) -> Path:
    return Path(project_path).resolve() / ".neuralmind" / CHECKPOINTS_FILE_NAME


def anchor_checkpoints_path(project_path: str | Path, anchor_dir: Path) -> Path:
    """The project's file in the anchor directory.

    Named after the project and a hash of its path, so one anchor directory
    can hold checkpoints for several projects.
    """
    root = Path(project_path).resolve()
    digest = hashlib.sha256(str(root).encode("utf-8")).hexdigest()[:12]
    stem = re.sub(r"[^A-Za-z0-9._-]", "_", root.name) or "project"
    return anchor_dir / f"{stem}-{digest}.{CHECKPOINTS_FILE_NAME}"


def _canonical(obj: dict[str, Any]) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def checkpoint_digest(checkpoint: dict[str, Any]) -> str:
    """What the next checkpoint's ``prev_checkpoint`` names: the whole record's hash."""
    return hashlib.sha256(_canonical(checkpoint)).hexdigest()


def _signed_part(checkpoint: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in checkpoint.items() if k != "signature"}


def read_checkpoint_file(path: Path) -> list[dict[str, Any]]:
    """Every checkpoint in ``path``, strictly: a line that isn't one fails."""
    if not path.exists():
        return []
    checkpoints = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        raise CheckpointError(f"can't read {path}: {exc}") from exc
    for line_no, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:
            raise CheckpointError(f"{path.name} line {line_no} isn't valid JSON") from exc
        problem = _shape_problem(obj)
        if problem:
            raise CheckpointError(f"{path.name} line {line_no}: {problem}")
        checkpoints.append(obj)
    return checkpoints


def _shape_problem(obj: Any) -> str | None:
    if not isinstance(obj, dict) or obj.get("format") != FORMAT:
        return f"not a {FORMAT} record"
    if not isinstance(obj.get("seq"), int) or isinstance(obj.get("seq"), bool) or obj["seq"] < 1:
        return "seq must be a positive integer"
    records = obj.get("records")
    if not isinstance(records, int) or isinstance(records, bool) or records < 1:
        return "records must be a positive integer"
    for name in ("first_sha256", "last_sha256", "prev_checkpoint"):
        if not isinstance(obj.get(name), str) or not _SHA256_HEX.fullmatch(obj[name]):
            return f"{name} must be a sha256"
    if not isinstance(obj.get("created_at"), str):
        return "created_at must be a timestamp"
    signature = obj.get("signature")
    if signature is not None and not isinstance(signature, str):
        return "signature must be base64 or null"
    return None


# --- writing -----------------------------------------------------------------


def _log_hashes(trail: AuditTrail) -> list[str]:
    """Each record's sha256 in file order ('' for a pre-chain record).

    Only called once the chain has verified, so every line is a record.
    """
    lines, _ = trail._read_lines_strict()
    return [str(evt.get("sha256", "")) for _, evt, _ in lines]


def create_checkpoint(
    project_path: str | Path,
    *,
    key_path: str | Path | None = None,
    anchor_dir: Path | None = None,
    extra_sources: list[Path] | None = None,
) -> dict[str, Any]:
    """Verify the log, then write a checkpoint covering it as it stands.

    Raises :class:`CheckpointError` when the chain or the existing checkpoints
    don't verify (a checkpoint must never vouch for a log already tampered
    with), when the log has no hashed record, or when the key doesn't match
    the pinned public key. Returns the checkpoint written.
    """
    root = Path(project_path).resolve()
    settings = load_checkpoint_settings(root)
    if settings.problem:
        raise CheckpointError(settings.problem)
    anchor_dir = anchor_dir or settings.anchor_dir

    trail = AuditTrail(root)
    chain = trail.verify()
    if not chain["ok"]:
        raise CheckpointError(f"the audit log doesn't verify: {chain.get('reason')}")
    report = verify_checkpoints(root, extra_sources=extra_sources, anchor_dir=anchor_dir)
    if not report.ok:
        raise CheckpointError(f"the existing checkpoints don't verify: {report.reason}")

    hashes = _log_hashes(trail)
    if not hashes or not hashes[-1]:
        raise CheckpointError("the audit log has no hashed record to checkpoint yet")
    first = next(h for h in hashes if h)

    private_key = load_private_key(key_path) if key_path else None
    if settings.public_key_b64:
        if private_key is None:
            raise CheckpointError(
                f"security.audit_checkpoint_key is set, so a checkpoint must be signed: "
                f"pass --key or set {KEY_ENV}"
            )
        if public_key_b64(private_key.public_key()) != settings.public_key_b64:
            raise CheckpointError("the signing key doesn't match security.audit_checkpoint_key")

    latest = report.latest
    checkpoint: dict[str, Any] = {
        "format": FORMAT,
        "seq": (latest["seq"] + 1) if latest else 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "project": str(root),
        "log": f".neuralmind/{AUDIT_FILE_NAME}",
        "records": len(hashes),
        "first_sha256": first,
        "last_sha256": hashes[-1],
        "prev_checkpoint": checkpoint_digest(latest) if latest else _GENESIS,
        "key_id": key_id(private_key.public_key()) if private_key else None,
    }
    checkpoint["signature"] = _sign(private_key, checkpoint) if private_key else None
    line = json.dumps(checkpoint, sort_keys=True) + "\n"

    # The anchored copy first: if it can't be written, write nothing, so the
    # local file never runs ahead of the copy that matters.
    if anchor_dir is not None:
        anchor_path = anchor_checkpoints_path(root, anchor_dir)
        try:
            anchor_path.parent.mkdir(parents=True, exist_ok=True)
            _append(anchor_path, line)
        except OSError as exc:
            raise CheckpointError(f"can't write the anchored checkpoint: {exc}") from exc
    local = local_checkpoints_path(root)
    local.parent.mkdir(parents=True, exist_ok=True)
    _append(local, line)

    trail.append_event(
        category="security",
        action="audit_checkpoint",
        target=str(anchor_dir) if anchor_dir else str(local),
        details={
            "seq": checkpoint["seq"],
            "records": checkpoint["records"],
            "key_id": checkpoint["key_id"],
            "anchored": anchor_dir is not None,
        },
    )
    return checkpoint


def _append(path: Path, line: str) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line)
        handle.flush()
        os.fsync(handle.fileno())


def _sign(private_key, checkpoint: dict[str, Any]) -> str:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec

    signature = private_key.sign(_canonical(_signed_part(checkpoint)), ec.ECDSA(hashes.SHA256()))
    return base64.b64encode(signature).decode("ascii")


def _signature_valid(public_key, checkpoint: dict[str, Any]) -> bool:
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec

    try:
        signature = base64.b64decode(checkpoint["signature"], validate=True)
        public_key.verify(
            signature, _canonical(_signed_part(checkpoint)), ec.ECDSA(hashes.SHA256())
        )
    except (InvalidSignature, ValueError, TypeError):
        return False
    return True


# --- verifying ---------------------------------------------------------------


@dataclass
class CheckpointReport:
    ok: bool = True
    reason: str | None = None
    checked: int = 0
    # Older checkpoints whose rotated archive has been pruned, so there is
    # nothing left to compare them with. Never the newest checkpoint.
    archive_pruned: int = 0
    signed: bool = False
    key_id: str | None = None
    latest: dict[str, Any] | None = None
    sources: list[str] = field(default_factory=list)
    configured: bool = False

    def fail(self, reason: str) -> CheckpointReport:
        self.ok = False
        self.reason = reason
        return self

    def to_dict(self) -> dict[str, Any]:
        latest = self.latest or {}
        return {
            "ok": self.ok,
            "reason": self.reason,
            "checked": self.checked,
            "archive_pruned": self.archive_pruned,
            "signed": self.signed,
            "key_id": self.key_id,
            "latest_seq": latest.get("seq"),
            "latest_created_at": latest.get("created_at"),
            "records_covered": latest.get("records"),
            "sources": self.sources,
            "configured": self.configured,
        }


def verify_checkpoints(
    project_path: str | Path,
    *,
    extra_sources: list[Path] | None = None,
    anchor_dir: Path | None = None,
) -> CheckpointReport:
    """Check every checkpoint for the project against the log.

    Reads the local file, the anchored file and any ``extra_sources`` (for
    example checkpoints exported from a SIEM), merges them by ``seq``, and
    checks signatures, the checkpoints' own chain, and each checkpoint
    against the log as it is now.
    """
    root = Path(project_path).resolve()
    settings = load_checkpoint_settings(root)
    report = CheckpointReport(configured=settings.configured)
    if settings.problem:
        return report.fail(f"checkpoint settings: {settings.problem}")
    anchor_dir = anchor_dir or settings.anchor_dir

    sources = [local_checkpoints_path(root)]
    anchor_path = anchor_checkpoints_path(root, anchor_dir) if anchor_dir is not None else None
    if anchor_path is not None:
        sources.append(anchor_path)
    named = [Path(p) for p in extra_sources or []]
    sources.extend(named)

    by_seq: dict[int, dict[str, Any]] = {}
    for source in sources:
        if not source.exists():
            # A file asked for by name must exist; the default ones may not yet.
            if source in named:
                return report.fail(f"checkpoint file not found: {source}")
            continue
        try:
            found = read_checkpoint_file(source)
        except CheckpointError as exc:
            return report.fail(str(exc))
        report.sources.append(str(source))
        for checkpoint in found:
            known = by_seq.get(checkpoint["seq"])
            if known is not None and checkpoint_digest(known) != checkpoint_digest(checkpoint):
                return report.fail(f"two different checkpoints claim seq {checkpoint['seq']}")
            by_seq[checkpoint["seq"]] = checkpoint
    if not by_seq:
        return report
    # The anchored copy is the one the developer can't edit. If it's gone
    # (deleted, or its volume unmounted) while other copies hold checkpoints,
    # those copies alone could have been rolled back along with the log.
    if anchor_path is not None and not anchor_path.exists():
        return report.fail(
            f"the anchored checkpoint copy {anchor_path} is missing, so the local copy "
            "can't be trusted on its own (if the anchor was set up after the first "
            f"checkpoint, copy {local_checkpoints_path(root)} there)"
        )

    ordered = [by_seq[seq] for seq in sorted(by_seq)]
    problem = _check_signatures(ordered, settings, report)
    if problem:
        return report.fail(problem)
    problem = _check_sequence(ordered)
    if problem:
        return report.fail(problem)

    trail = AuditTrail(root)
    # Each log a checkpoint can cover, keyed by its first hashed record: the
    # active log and the rotated archives its rotation markers lead back to.
    # An archive-named file nothing links to doesn't count, or a copy of the
    # original log could vouch for a replaced one. A checkpoint is
    # compared with the log it began on, so one taken before a rotation is
    # checked against its archive. The active log's rotation marker is never
    # taken on trust: anyone who can write the log can write one. A log's
    # stored hashes count only once its chain verifies, or a record's body
    # could be edited with its sha256 left as it was.
    logs: dict[str, tuple[list[str], str | None]] = {}
    for path in _linked_logs(trail):
        hashes, problem = _log_chain(root, path)
        first = next((h for h in hashes if h), None)
        if first:
            logs[first] = (hashes, problem)

    # Newest first, so a failure reports the most the log has lost.
    for checkpoint in reversed(ordered):
        found_log = logs.get(checkpoint["first_sha256"])
        if found_log is None:
            # rotate() prunes old archives, so an older checkpoint can outlive
            # its log. The newest can't: it must always be found and match.
            if checkpoint is not ordered[-1]:
                report.archive_pruned += 1
                continue
            return report.fail(
                f"neither the log nor a rotated archive begins with the record "
                f"checkpoint {checkpoint['seq']} ({checkpoint['created_at']}) starts "
                "from: the log was replaced or rewritten"
            )
        hashes, chain_problem = found_log
        if chain_problem:
            return report.fail(
                f"the log checkpoint {checkpoint['seq']} ({checkpoint['created_at']}) "
                f"covers fails its hash chain: {chain_problem}"
            )
        covered = checkpoint["records"]
        if len(hashes) < covered:
            return report.fail(
                f"{covered - len(hashes)} record(s) removed from the end of the log since "
                f"checkpoint {checkpoint['seq']} ({checkpoint['created_at']}), which "
                f"covers {covered}"
            )
        if hashes[covered - 1] != checkpoint["last_sha256"]:
            return report.fail(
                f"record {covered} no longer has the hash checkpoint {checkpoint['seq']} "
                f"({checkpoint['created_at']}) recorded: the chain was rewritten"
            )
        report.checked += 1
    report.latest = ordered[-1]
    return report


def _linked_logs(trail: AuditTrail) -> list[Path]:
    """The active log, then each archive its rotation markers name, newest first.

    Follows ``rotation_continuation`` markers back from the active log for as
    long as the archive a marker names is still beside it. Whether each link
    holds (the marker's ``prev_sha256`` against the archive's last hash) is
    checked when that log's chain is walked.
    """
    logs = [trail.events_file]
    current = trail.events_file
    while True:
        probe = AuditTrail(trail.project_path)
        probe.events_file = current
        lines, _ = probe._read_lines_strict()
        if not lines or lines[0][1].get("action") != "rotation_continuation":
            return logs
        details = lines[0][1].get("details")
        name = details.get("archive") if isinstance(details, dict) else None
        if not isinstance(name, str) or not _ARCHIVE_NAME.fullmatch(name):
            return logs
        current = trail.events_file.parent / name
        if not current.exists() or current in logs:
            return logs
        logs.append(current)


def _log_chain(root: Path, path: Path) -> tuple[list[str], str | None]:
    """Each record's sha256 in ``path``, in file order, and why its chain fails.

    The chain is walked as ``audit verify`` walks the active log. The hashes
    are returned either way, so a failing log can still be matched to the
    checkpoint that covers it and reported.
    """
    trail = AuditTrail(root)
    trail.events_file = path
    result = trail.verify()
    lines, _ = trail._read_lines_strict()
    hashes = [str(evt.get("sha256", "")) for _, evt, _ in lines]
    if result["ok"]:
        return hashes, None
    where = f"{path.name} line {result['first_bad_line']}: " if result["first_bad_line"] else ""
    return hashes, f"{where}{result['reason']}"


def _check_signatures(
    ordered: list[dict[str, Any]], settings: CheckpointSettings, report: CheckpointReport
) -> str | None:
    report.signed = all(c.get("signature") for c in ordered)
    if not settings.public_key_b64:
        return None
    public_key = load_public_key(settings.public_key_b64)
    report.key_id = key_id(public_key)
    for checkpoint in ordered:
        if not checkpoint.get("signature"):
            return (
                f"checkpoint {checkpoint['seq']} is unsigned, but "
                "security.audit_checkpoint_key requires a signature"
            )
        if not _signature_valid(public_key, checkpoint):
            return (
                f"checkpoint {checkpoint['seq']}'s signature doesn't verify with "
                "security.audit_checkpoint_key"
            )
    return None


def _check_sequence(ordered: list[dict[str, Any]]) -> str | None:
    """The checkpoints must run 1, 2, 3 … each naming the one before it."""
    prev = None
    for checkpoint in ordered:
        expected_seq = prev["seq"] + 1 if prev else 1
        if checkpoint["seq"] != expected_seq:
            return (
                f"checkpoint {expected_seq} is missing from every copy "
                f"(the next is {checkpoint['seq']})"
            )
        expected_prev = checkpoint_digest(prev) if prev else _GENESIS
        if checkpoint["prev_checkpoint"] != expected_prev:
            return f"checkpoint {checkpoint['seq']} doesn't follow checkpoint {expected_seq - 1}"
        prev = checkpoint
    return None


def latest_checkpoint_age_days(report: CheckpointReport) -> float | None:
    if not report.latest:
        return None
    try:
        created = datetime.fromisoformat(report.latest["created_at"])
    except ValueError:
        return None
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - created).total_seconds() / 86400
