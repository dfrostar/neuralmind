"""cli.py — Tier 2 Team admin commands (commands under `neuralmind team ...`).

All tier2 admin commands are gated: if no valid license is active, the
MIT user sees a helpful message instead of team-management output.

Entry: called from `neuralmind.cli` via `build_team_subparsers(subparsers)`.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from .audit import AuditLog
from .config import TIER2_CONFIG_DIR, Tier2Config, load_config, save_config
from .governance import TeamGovernance
from .license import _ISSUER_PUBLIC_KEY_HEX, LicenseValidator, issue_free_license, load_license
from .seats import SeatLimitError, SeatManager
from .self_hosted import (
    _resolve_license_path,
    get_data_dir,
    get_self_hosted_status,
    init_data_dir,
)


def build_team_subparsers(subparsers) -> None:
    """Add `team` subcommands to the main argparse subparsers.

    Call this from neuralmind.cli.main() to wire Tier 2 commands.

    subparsers is the argparse._SubParsersAction from the main CLI.
    """
    team = subparsers.add_parser(
        "team", help="Team tier administration (governance, seats, license)"
    )
    team_sub = team.add_subparsers(dest="team_subcommand")
    team_sub.required = True

    # governance
    gov_g = team_sub.add_parser("governance", help="Team memory governance")
    gov_g_sub = gov_g.add_subparsers(dest="subcommand")
    gov_g_sub.required = True
    gov_g_sub.add_parser("status")
    scope_p = gov_g_sub.add_parser("set-scope")
    scope_p.add_argument("scope", choices=["personal", "shared", "both"])
    scope_p.add_argument("--admin")
    thr_p = gov_g_sub.add_parser("set-weight-threshold")
    thr_p.add_argument("value", type=float)
    thr_p.add_argument("--admin")
    en_p = gov_g_sub.add_parser("set-governance-enabled")
    en_p.add_argument("value")
    en_p.add_argument("--admin")
    list_p = gov_g_sub.add_parser("list-shared")
    list_p.add_argument("--json", action="store_true")
    rm_p = gov_g_sub.add_parser("remove-edge")
    rm_p.add_argument("edge_id")
    rm_p.add_argument("--admin")
    gov_g.set_defaults(func=cmd_team_governance)

    # audit
    audit_p = team_sub.add_parser("audit", help="Audit log")
    audit_sub = audit_p.add_subparsers(dest="subcommand")
    audit_sub.required = True
    list_a = audit_sub.add_parser("list")
    list_a.add_argument("--since", type=str)
    list_a.add_argument("--until", type=str)
    list_a.add_argument("--actor", type=str)
    list_a.add_argument("--json", action="store_true")
    exp_p = audit_sub.add_parser("export")
    exp_p.add_argument("--format", choices=["csv", "json"], required=True)
    exp_p.add_argument("--output", required=True)
    audit_sub.add_parser("verify")
    audit_p.set_defaults(func=cmd_team_audit)

    # seats
    seats_p = team_sub.add_parser("seats", help="Seat management")
    seats_sub = seats_p.add_subparsers(dest="subcommand")
    seats_sub.required = True
    seats_list_p = seats_sub.add_parser("list")
    seats_list_p.add_argument("--json", action="store_true")
    seats_add_p = seats_sub.add_parser("add")
    seats_add_p.add_argument("email")
    seats_add_p.add_argument("--admin")
    seats_rm_p = seats_sub.add_parser("remove")
    seats_rm_p.add_argument("email")
    seats_rm_p.add_argument("--admin")
    seats_sync_p = seats_sub.add_parser("sync", help="Sync seats from signed manifest")
    seats_sync_p.add_argument("manifest", help="Path to signed manifest JSON")
    seats_sync_p.add_argument("--admin")
    seats_p.set_defaults(func=cmd_team_seats)

    # self-hosted
    sh_p = team_sub.add_parser("self-hosted", help="Self-hosted deployment")
    sh_sub = sh_p.add_subparsers(dest="subcommand")
    sh_sub.required = True
    sh_init_p = sh_sub.add_parser("init")
    sh_init_p.add_argument("--data-dir")
    sh_sub.add_parser("status")
    sh_sub.add_parser("validate-license")
    sh_p.set_defaults(func=cmd_team_self_hosted)

    # license
    lic_p = team_sub.add_parser("license", help="License management")
    lic_sub = lic_p.add_subparsers(dest="subcommand")
    lic_sub.required = True
    lic_sub.add_parser("status")
    act_p = lic_sub.add_parser("activate")
    act_p.add_argument("key")
    lic_sub.add_parser("portal")
    lic_p.set_defaults(func=cmd_team_license)


def _ensure_tier2_activated(args) -> tuple[Tier2Config, AuditLog] | tuple[None, None]:
    """Load config + audit. Auto-issues free license if none exists (R09 gate).

    R09 fix: Before any free-tier auto-issue, check config.tier.
    If "team" or "enterprise", print error and return failure instead of
    silently regenerating a free-tier license.
    """
    config = load_config(getattr(args, "config_path", None))
    lic_path = Path(config.license_file)
    # R09 gate: paid-tier customers must NOT auto-downgrade to free
    if not lic_path.exists():
        if config.tier in ("team", "enterprise"):
            print(
                "License file missing. Run `neuralmind team license activate <key>` to re-activate."
            )
            return None, None
        # Also guard: if config shows a paid tier was previously active
        # (seats > 1 indicates paid tier allocation)
        if config.seats > 1:
            print(
                "License file missing. Run `neuralmind team license activate <key>` to re-activate."
            )
            return None, None
        try:
            issue_free_license(lic_path)
        except OSError as e:
            print(f"Cannot create license file: {e}")
            return None, None

    # Validate license (free or team)
    issuer_key = os.environ.get("NEURALMIND_ISSUER_PUBLIC_KEY_HEX", _ISSUER_PUBLIC_KEY_HEX)
    lic_status = load_license(lic_path, issuer_key)
    if lic_status == "INVALID":
        print("License file is corrupted. Run `neuralmind team license activate <key>` to replace.")
        return None, None
    if lic_status == "EXPIRED":
        print("License has expired. Run `neuralmind team license activate <key>` to renew.")
        return None, None

    # Valid (free or team) — sync seats/expires from license into config
    validator = LicenseValidator(_ISSUER_PUBLIC_KEY_HEX, lic_path)
    lic_info = validator._load_raw()
    if lic_info:
        config.tier = lic_info.tier
        config.seats = lic_info.seats
        config.expires_at = lic_info.expires_at
        config.issued_to = lic_info.issued_to
        # For free tier, set a default admin so governance commands work
        if lic_info.tier == "free" and not config.governance.admin_emails:
            config.governance.admin_emails = ["self"]

    return config, AuditLog(Path(config.audit_db))


def cmd_team_governance(args) -> int:
    config, audit = _ensure_tier2_activated(args)
    if config is None:
        return 1

    gov = TeamGovernance(Path(config.audit_db), config, audit)

    if args.subcommand == "status":
        print(
            json.dumps(
                {
                    "enabled": config.governance.enabled,
                    "publishing_scope": config.governance.publishing_scope,
                    "weight_threshold": config.governance.weight_threshold,
                    "auto_decay_half_life": config.governance.auto_decay_half_life,
                    "admin_count": len(config.governance.admin_emails),
                },
                indent=2,
            )
        )
        return 0

    if args.subcommand == "set-scope":
        scope = args.scope
        admin = args.admin or os_get_actor_email()
        gov.set_publishing_scope(scope, admin)
        save_config(config)
        print(f"Publishing scope set to: {scope}")
        return 0

    if args.subcommand == "set-weight-threshold":
        v = float(args.value)
        admin = args.admin or os_get_actor_email()
        gov.set_weight_threshold(v, admin)
        save_config(config)
        print(f"Weight threshold set to: {v}")
        return 0

    if args.subcommand == "set-governance-enabled":
        enabled = args.value.lower() in ("1", "true", "yes", "on")
        admin = args.admin or os_get_actor_email()
        gov.set_governance_enabled(enabled, admin)
        save_config(config)
        print(f"Governance {'enabled' if enabled else 'disabled'}")
        return 0

    if args.subcommand == "list-shared":
        # Placeholder — real shared-namespace listing comes from team_memory.py
        print(json.dumps([], indent=2))
        return 0

    if args.subcommand == "remove-edge":
        admin = args.admin or os_get_actor_email()
        gov.remove_edge_from_shared(args.edge_id, admin)
        save_config(config)
        print(f"Edge removed: {args.edge_id}")
        return 0

    print(f"Unknown governance subcommand: {args.subcommand}")
    return 1


def cmd_team_audit(args) -> int:
    config, audit = _ensure_tier2_activated(args)
    if config is None:
        return 1

    db = AuditLog(Path(config.audit_db))

    if args.subcommand == "list":
        since = float(args.since) if getattr(args, "since", None) else None
        until = float(args.until) if getattr(args, "until", None) else None
        actor = args.actor if getattr(args, "actor", None) else None
        entries = db.export(since=since, until=until, actor=actor)
        if args.json:
            print(json.dumps([e.to_dict() for e in entries], indent=2))
        else:
            for e in entries:
                print(f"  {e.ts}  {e.actor:30s} {e.action:20s} {e.target}")
        return 0

    if args.subcommand == "export":
        fmt = args.format
        out_path = Path(args.output)
        if fmt == "csv":
            count = db.export_csv(out_path)
        else:
            count = db.export_json(out_path)
        print(f"Exported {count} records -> {out_path}")
        return 0

    if args.subcommand == "verify":
        result = db.verify()
        if result["ok"]:
            print(f"Audit log OK: {result['total']} entries verified")
            return 0
        print(f"Audit log TAMPERED at line {result['first_bad_line']}")
        return 1

    print(f"Unknown audit subcommand: {args.subcommand}")
    return 1


def cmd_team_seats(args) -> int:
    config, audit = _ensure_tier2_activated(args)
    if config is None:
        return 1

    gov = TeamGovernance(Path(config.audit_db), config, audit)
    seats_db = TIER2_CONFIG_DIR / "seats.json"
    sm = SeatManager(seats_db)

    if args.subcommand == "list":
        seats = sm.list_seats()
        if args.json:
            print(json.dumps([s.to_dict() for s in seats], indent=2))
        else:
            for s in seats:
                status = "active" if s.active else "inactive"
                print(f"  {s.email:40s} {status:10s} added={s.added_at}")
        return 0

    admin = args.admin or os_get_actor_email()

    # Wave 13: seat sync from signed manifest
    if args.subcommand == "sync":
        return cmd_team_seats_sync(args, config=config, audit=audit)

    # Every seat mutation requires admin authentication.
    # Free-tier seats bypass the limit check (handled inside sm.add_seat),
    # but admin authentication still applies for auditability.
    if args.subcommand == "add":
        try:
            gov.require_admin(admin)
            sm.add_seat(args.email, config.seats, tier=config.tier)
            audit.log(actor=admin, action="seat_add", target=args.email)
            print(f"Seat added: {args.email}")
            return 0
        except PermissionError as e:
            print(f"Permission denied: {e}")
            return 1
        except SeatLimitError as e:
            print(f"Seat limit reached: {e}")
            return 1

    if args.subcommand == "remove":
        try:
            gov.require_admin(admin)
            sm.remove_seat(args.email)
            audit.log(actor=admin, action="seat_remove", target=args.email)
            print(f"Seat removed: {args.email}")
            return 0
        except PermissionError as e:
            print(f"Permission denied: {e}")
            return 1
        except KeyError:
            print(f"Seat not found: {args.email}")
            return 1

    print(f"Unknown seats subcommand: {args.subcommand}")
    return 1


def cmd_team_seats_sync(args, config=None, audit=None) -> int:
    """Sync local seats from a signed manifest (Wave 13 / R02).

    Usage:
        neuralmind team seats sync <manifest.json> --admin <EMAIL>

    Returns:
        0 on full success, 1 on hard failure, 2 on partial sync.
    """
    from .seats import sync_seats, verify_manifest_signature

    # File existence check
    manifest_path = Path(args.manifest)
    if not manifest_path.exists():
        print(f"ERROR: Manifest not found: {manifest_path}")
        return 1

    # JSON parse
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"ERROR: Malformed JSON in manifest: {e}")
        return 1

    # Version check
    if manifest.get("version") != 1:
        print(f"ERROR: Unsupported manifest version: {manifest.get('version')}")
        return 1

    # Expiry check
    expires_at = manifest.get("expires_at", "")
    if expires_at:
        try:
            from datetime import datetime as _dt
            from datetime import timezone as _tz

            exp = _dt.fromisoformat(expires_at.replace("Z", "+00:00"))
            # Normalize naive expires_at to UTC so comparison with
            # UTC-aware now() never raises TypeError.
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=_tz.utc)
            if _dt.now(_tz.utc) > exp:
                print(f"ERROR: Manifest expired at {expires_at}")
                return 1
        except ValueError:
            pass

    # Signature verification - read key at call time for testability
    issuer_key = os.environ.get(
        "NEURALMIND_ISSUER_PUBLIC_KEY_HEX",
        _ISSUER_PUBLIC_KEY_HEX,
    )
    if not verify_manifest_signature(manifest, issuer_key):
        print("ERROR: Manifest signature invalid — rejected.")
        return 1

    # Admin identity
    admin = args.admin or os_get_actor_email()
    if not admin:
        print("ERROR: No admin identity available. Set --admin or $NEURALMIND_ADMIN_EMAIL.")
        return 1

    # Load config if not already loaded
    if config is None:
        config, audit = _ensure_tier2_activated(args)
        if config is None:
            return 1
    else:
        # config is provided; construct audit log only if caller omitted it.
        # (The previous and-chain redundantly re-loaded config.)
        if audit is None:
            audit = AuditLog(Path(config.audit_db))

    gov = TeamGovernance(Path(config.audit_db), config, audit)
    try:
        gov.require_admin(admin)
    except PermissionError as e:
        print(f"Permission denied: {e}")
        return 1

    # Sync seats
    from . import config as _cfg_mod

    seats_db = _cfg_mod.TIER2_CONFIG_DIR / "seats.json"
    result = sync_seats(
        seats_db,
        manifest,
        license_limit=config.seats,
        tier=config.tier,
        admin=admin,
    )

    # Audit log top-level sync event
    audit.log(
        actor=admin,
        action="seat_sync",
        target=f"sync:{manifest.get('manifest_id', 'unknown')}",
        details={"added": result.get("added", []), "failed": result.get("failed", [])},
    )

    print(json.dumps(result, indent=2))

    status = result.get("status")
    if status == "ok":
        return 0
    if status == "partial":
        return 2
    return 1


def cmd_team_self_hosted(args) -> int:
    if args.subcommand == "init":
        data_dir = Path(args.data_dir) if getattr(args, "data_dir", None) else get_data_dir()
        result = init_data_dir(data_dir)
        if result.get("error"):
            print(f"ERROR: {result['error']}")
            return 1
        print(f"Self-hosted data dir ready: {result['path']} (mode {result['mode']})")
        return 0

    if args.subcommand == "status":
        status = get_self_hosted_status()
        print(json.dumps(status, indent=2))
        return 0

    if args.subcommand == "validate-license":
        from .license import _ISSUER_PUBLIC_KEY_HEX, load_license

        path = _resolve_license_path()
        status = load_license(path, _ISSUER_PUBLIC_KEY_HEX)
        print(f"License status: {status}")
        return 0

    print(f"Unknown self-hosted subcommand: {args.subcommand}")
    return 1


def cmd_team_license(args) -> int:

    if args.subcommand == "status":
        config = load_config(getattr(args, "config_path", None))
        path = Path(config.license_file)
        validator = LicenseValidator(_ISSUER_PUBLIC_KEY_HEX, path)
        info = validator.status_dict()
        print(json.dumps(info, indent=2))
        return 0

    if args.subcommand == "activate":
        config = load_config(getattr(args, "config_path", None))
        path = Path(config.license_file)
        # Read the signed license JSON from the provided path
        src_path = Path(args.key)
        if not src_path.exists():
            print(f"License file not found: {src_path}")
            return 1
        src_text = src_path.read_text(encoding="utf-8")
        src_status = load_license(src_path, _ISSUER_PUBLIC_KEY_HEX)
        if src_status != "VALID":
            print(
                f"License validation failed: {src_status}. Run `autopilot license status --license-id <id>` to check."
            )
            return 1
        # Signature validated — install
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(src_text, encoding="utf-8")
        validator = LicenseValidator(_ISSUER_PUBLIC_KEY_HEX, path)
        lic_info = validator._load_raw()
        if lic_info:
            config.seats = lic_info.seats
            config.expires_at = lic_info.expires_at
            config.issued_to = lic_info.issued_to
            config.tier = lic_info.tier
        save_config(config)
        print(
            f"License activated: {lic_info.tier} tier, {lic_info.seats} seats, expires {lic_info.expires_at}"
        )
        return 0

    if args.subcommand == "portal":
        config = load_config(getattr(args, "config_path", None))
        path = Path(config.license_file)
        if not path.exists():
            print(json.dumps({"error": "no_installed_license", "status": "UNLICENSED"}, indent=2))
            return 0
        validator = LicenseValidator(_ISSUER_PUBLIC_KEY_HEX, path)
        info = validator.status_dict()
        # Calculate days until expiry
        try:
            from datetime import datetime
            from datetime import timezone as _tz

            expires_at = info.get("expires_at", "")
            if expires_at == "never":
                info["days_until_expiry"] = "never"
            else:
                exp = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
                days = (exp - datetime.now(_tz.utc)).days
                info["days_until_expiry"] = days
        except Exception as _e:
            info["days_until_expiry"] = "unknown"
        print(json.dumps(info, indent=2, default=str))
        return 0

    print(f"Unknown license subcommand: {args.subcommand}")
    return 1


def os_get_actor_email() -> str:
    """Resolve actor email from env var."""

    email = os.environ.get("NEURALMIND_ACTOR_EMAIL") or os.environ.get("NEURALMIND_ACTOR") or ""
    return email.strip() or "unknown"


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="neuralmind team")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.required = True

    # --- governance ---
    gov_p = subparsers.add_parser("governance", help="Team memory governance")
    gov_sub = gov_p.add_subparsers(dest="subcommand")
    gov_sub.required = True
    gov_sub.add_parser("status")
    scope_p = gov_sub.add_parser("set-scope")
    scope_p.add_argument("scope", choices=["personal", "shared", "both"])
    scope_p.add_argument("--admin")
    thr_p = gov_sub.add_parser("set-weight-threshold")
    thr_p.add_argument("value", type=float)
    thr_p.add_argument("--admin")
    en_p = gov_sub.add_parser("set-governance-enabled")
    en_p.add_argument("value")
    en_p.add_argument("--admin")
    list_p = gov_sub.add_parser("list-shared")
    list_p.add_argument("--json", action="store_true")
    rm_p = gov_sub.add_parser("remove-edge")
    rm_p.add_argument("edge_id")
    rm_p.add_argument("--admin")
    gov_p.set_defaults(func=cmd_team_governance)

    # --- audit ---
    audit_p = subparsers.add_parser("audit", help="Audit log")
    audit_sub = audit_p.add_subparsers(dest="subcommand")
    audit_sub.required = True
    list_a = audit_sub.add_parser("list")
    list_a.add_argument("--since", type=str)
    list_a.add_argument("--until", type=str)
    list_a.add_argument("--actor", type=str)
    list_a.add_argument("--json", action="store_true")
    list_a.set_defaults(func=cmd_team_audit)
    exp_p = audit_sub.add_parser("export")
    exp_p.add_argument("--format", choices=["csv", "json"], required=True)
    exp_p.add_argument("--output", required=True)
    audit_sub.add_parser("verify").set_defaults(func=cmd_team_audit)
    audit_p.set_defaults(func=cmd_team_audit)

    # --- seats ---
    seats_p = subparsers.add_parser("seats", help="Seat management")
    seats_sub = seats_p.add_subparsers(dest="subcommand")
    seats_sub.required = True
    seats_list_p = seats_sub.add_parser("list")
    seats_list_p.add_argument("--json", action="store_true")
    seats_add_p = seats_sub.add_parser("add")
    seats_add_p.add_argument("email")
    seats_add_p.add_argument("--admin")
    seats_rm_p = seats_sub.add_parser("remove")
    seats_rm_p.add_argument("email")
    seats_rm_p.add_argument("--admin")
    seats_p.set_defaults(func=cmd_team_seats)

    # --- self-hosted ---
    sh_p = subparsers.add_parser("self-hosted", help="Self-hosted deployment")
    sh_sub = sh_p.add_subparsers(dest="subcommand")
    sh_sub.required = True
    sh_init_p = sh_sub.add_parser("init")
    sh_init_p.add_argument("--data-dir")
    sh_sub.add_parser("status")
    sh_sub.add_parser("validate-license")
    sh_p.set_defaults(func=cmd_team_self_hosted)

    # --- license ---
    lic_p = subparsers.add_parser("license", help="License management")
    lic_sub = lic_p.add_subparsers(dest="subcommand")
    lic_sub.required = True
    lic_sub.add_parser("status")
    act_p = lic_sub.add_parser("activate")
    act_p.add_argument("key")
    lic_sub.add_parser("portal")
    lic_p.set_defaults(func=cmd_team_license)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
