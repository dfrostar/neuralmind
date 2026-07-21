"""onboarding — interactive setup wizard for team tier.

Walks a new operator through:
1. License activation (or free tier)
2. Governance defaults (scope, threshold)
3. Admin email setup
4. Team seat audit
5. Verification

Entry: import into neuralmind.cli and register as ``onboarding`` subcommand.

Example:
    neuralmind onboarding           # interactive mode
    neuralmind onboarding --quick   # skip all prompts, defaults only
"""

from __future__ import annotations

import getpass
import os
from pathlib import Path

from neuralmind.tier2.audit import AuditLog
from neuralmind.tier2.config import (
    TIER2_CONFIG_DIR,
    load_config,
    save_config,
)
from neuralmind.tier2.license import issue_free_license, load_license
from neuralmind.tier2.seats import SeatManager


def _get_issuer_key() -> str:
    """Resolve Ed25519 issuer public key from env or tier2 default."""
    from neuralmind.tier2.license import _ISSUER_PUBLIC_KEY_HEX
    return os.environ.get("NEURALMIND_ISSUER_PUBLIC_KEY_HEX", _ISSUER_PUBLIC_KEY_HEX)


def _is_quiet(args) -> bool:
    return bool(getattr(args, "quick", False))


def _yes(args, prompt: str, default: bool = True) -> bool:
    if _is_quiet(args):
        return default
    suffix = " [Y/n]" if default else " [y/N]"
    while True:
        ans = input(prompt + suffix + " ").strip().lower()
        if not ans:
            return default
        if ans in ("y", "yes"):
            return True
        if ans in ("n", "no"):
            return False
        print("Please answer y or n.")


def _ask(args, prompt: str, default: str = "") -> str:
    if _is_quiet(args):
        return default
    suffix = f" [{default}]" if default else ""
    ans = input(prompt + suffix + " ").strip()
    return ans or default


def _step(n: int, total: int, title: str) -> None:
    bar = "─" * 50
    print(f"\n{bar}")
    print(f"  Step {n}/{total}: {title}")
    print(bar)


def _cmd_onboarding_license(args) -> int:
    """Run Step 1: License activation / free tier."""
    _step(1, 4, "License activation")
    config = load_config(getattr(args, "config_path", None))
    lic_path = Path(config.license_file)

    if lic_path.exists():
        print(f"License file exists: {lic_path}")
        status = load_license(lic_path, _get_issuer_key())
        if status == "VALID":
            print("✓ License is valid — skipping activation.")
            return 0
        print(f"License status: {status}")

    if _yes(args, "No valid license found. Activate free tier now?", default=True):
        try:
            issue_free_license(lic_path)
            print(f"✓ Free tier license issued: {lic_path}")
        except OSError as e:
            print(f"✗ Failed to create license: {e}")
            return 1
    else:
        print("— Skipped. Issue a team license with:")
        print("  neuralmind team license activate <signed-key-file>")
    return 0


def _cmd_onboarding_governance(args) -> int:
    """Run Step 2: Governance defaults (scope, threshold)."""
    _step(2, 4, "Governance defaults")
    config = load_config(getattr(args, "config_path", None))

    # Scope
    print("\nPublishing scope controls what memory is shared:")
    print("  personal — only private edges (default)")
    print("  shared   — publish to team namespace")
    print("  both     — personal + shared (recommended for teams)")
    scope = _ask(
        args,
        "Scope",
        default=config.governance.publishing_scope or "both",
    )
    if scope not in ("personal", "shared", "both"):
        print(f"Invalid scope '{scope}', defaulting to 'both'")
        scope = "both"
    config.governance.publishing_scope = scope  # type: ignore[assignment]

    # Threshold
    thr_str = _ask(
        args,
        "Weight threshold (0.0–1.0, edges below are rejected)",
        default=str(config.governance.weight_threshold),
    )
    try:
        thr = float(thr_str)
        config.governance.weight_threshold = max(0.0, min(1.0, thr))
    except ValueError:
        print("Invalid threshold, keeping default")

    # Decay
    decay_str = _ask(
        args,
        "Auto-decay half-life (days, higher = slower decay)",
        default=str(config.governance.auto_decay_half_life),
    )
    try:
        decay = float(decay_str)
        config.governance.auto_decay_half_life = max(1.0, decay)
    except ValueError:
        print("Invalid decay, keeping default")

    save_config(config)
    print(f"✓ Governance saved: scope={scope}, threshold={config.governance.weight_threshold}")
    return 0


def _cmd_onboarding_admin(args) -> int:
    """Run Step 3: Admin email setup."""
    _step(3, 4, "Admin setup")
    config = load_config(getattr(args, "config_path", None))

    # Detect current user email from OS
    default_user = f"{getpass.getuser()}@local" if _is_quiet(args) else ""
    email = _ask(
        args,
        "Admin email (used for governance audit trail)",
        default=default_user,
    )
    if email and "@" in email:
        email = email.strip().lower()
        if email not in config.governance.admin_emails:
            config.governance.admin_emails.append(email)
        save_config(config)
        print(f"✓ Admin registered: {email}")
    elif email:
        print("✗ Invalid email format, skipped.")
    else:
        print("— Skipped. Set admins later with:")
        print("  neuralmind team governance set-governance-enabled true --admin <email>")
    return 0


def _cmd_onboarding_verify(args) -> int:
    """Run Step 4: Verify installation."""
    _step(4, 4, "Verification")
    config = load_config(getattr(args, "config_path", None))
    lic_path = Path(config.license_file)
    seats_db = TIER2_CONFIG_DIR / "seats.json"

    # License check
    if lic_path.exists():
        status = load_license(lic_path, _get_issuer_key())
        if status == "VALID":
            print("✓ License valid")
        else:
            print(f"✗ License: {status}")
    else:
        print("— No license file (free tier or not yet activated)")

    # Seats
    if seats_db.exists():
        sm = SeatManager(seats_db)
        print(f"✓ Seats file: {sm.active_count()} active, limit {config.seats}")
    else:
        print("— No seats.json yet (will be created on first seat add)")

    # Governance / Audit
    audit_db = TIER2_CONFIG_DIR / "audit.db"
    if audit_db.exists():
        audit = AuditLog(audit_db)
        result = audit.verify()
        if result["ok"]:
            print(f"✓ Audit log: {result['total']} entries verified")
        else:
            print(f"✗ Audit log tampered at line {result['first_bad_line']}")
    else:
        print("— No audit log yet (governance actions will create it)")

    print(f"\nConfig: {TIER2_CONFIG_DIR / 'tier2.yaml'}")
    print(f"License: {lic_path}")
    print("\nTodo: \n  neuralmind doctor .   — validate full install health")
    return 0


def cmd_onboarding(args) -> int:
    """`onboarding` — interactive setup wizard."""
    # Ensure tier2 config dir exists
    if not TIER2_CONFIG_DIR.exists():
        TIER2_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        print(f"Created config dir: {TIER2_CONFIG_DIR}")

    if _is_quiet(args):
        print("Quick mode — using defaults for all prompts.")

    rc = _cmd_onboarding_license(args)
    if rc != 0:
        return rc
    _cmd_onboarding_governance(args)
    _cmd_onboarding_admin(args)
    _cmd_onboarding_verify(args)

    print("\n✓ Onboarding complete. Next steps:")
    print("  neuralmind team seats list        — view current seats")
    print("  neuralmind team governance status — view governance config")
    print("  neuralmind doctor .               — run full health check")
    return 0
