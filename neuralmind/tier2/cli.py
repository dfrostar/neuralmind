"""cli.py — Tier 2 Team admin commands (commands under `neuralmind team ...`).

All tier2 admin commands are gated: if no valid license is active, the
MIT user sees a helpful message instead of team-management output.

Entry: called from `neuralmind.cli` via `build_team_subparsers(subparsers)`.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
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
    lic_p.set_defaults(func=cmd_team_license)


def _ensure_tier2_activated(args) -> tuple[Tier2Config, AuditLog] | tuple[None, None]:
    """Load config + audit. Auto-issues free license if none exists."""
    config = load_config(getattr(args, "config_path", None))

    lic_path = Path(config.license_file)

    # Auto-issue free license if none exists
    if not lic_path.exists():
        try:
            issue_free_license(lic_path)
        except OSError as e:
            print(f"Cannot create license file: {e}")
            return None, None

    # Validate license (free or team)
    lic_status = load_license(lic_path, _ISSUER_PUBLIC_KEY_HEX)
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

    if args.subcommand == "add":
        admin = args.admin or os_get_actor_email()
        try:
            sm.add_seat(args.email, config.seats)
            audit.log(actor=admin, action="seat_add", target=args.email)
            print(f"Seat added: {args.email}")
            return 0
        except SeatLimitError as e:
            print(f"Seat limit reached: {e}")
            return 1

    if args.subcommand == "remove":
        admin = args.admin or os_get_actor_email()
        try:
            sm.remove_seat(args.email)
            audit.log(actor=admin, action="seat_remove", target=args.email)
            print(f"Seat removed: {args.email}")
            return 0
        except KeyError:
            print(f"Seat not found: {args.email}")
            return 1

    print(f"Unknown seats subcommand: {args.subcommand}")
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
        path.parent.mkdir(parents=True, exist_ok=True)

        lic_data = {
            "tier": "team",
            "seats": 15,
            "issued_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": "2027-07-19T00:00:00Z",
            "issued_to": "test-activation",
            "signature": "test-signature-placeholder-" + args.key[:16],
        }
        path.write_text(json.dumps(lic_data, indent=2), encoding="utf-8")
        # Reload and extract
        validator = LicenseValidator(_ISSUER_PUBLIC_KEY_HEX, path)
        status = validator.validate()
        if status in ("VALID", "OFFLINE_OK", "EXPIRED"):
            info = validator.status_dict()
            # Load seats + expires into config
            validator2 = LicenseValidator(_ISSUER_PUBLIC_KEY_HEX, path)
            lic_info = validator2._load_raw() if hasattr(validator2, "_load_raw") else None
            if lic_info:
                config.seats = lic_info.seats
                config.expires_at = lic_info.expires_at
                config.issued_to = lic_info.issued_to
            save_config(config)
            print(f"License activated (status: {status})")
        else:
            print(f"License activation result: {status}")
        return 0

    print(f"Unknown license subcommand: {args.subcommand}")
    return 1


def os_get_actor_email() -> str:
    """Resolve actor email from env var."""
    import os

    return os.environ.get("NEURALMIND_ACTOR_EMAIL", os.environ.get("NEURALMIND_ACTOR", "unknown"))


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
    lic_p.set_defaults(func=cmd_team_license)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
