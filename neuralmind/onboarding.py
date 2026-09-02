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
import json
import os
import sys
from datetime import datetime, timezone
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


def _os_user() -> str:
    """Current OS username, or ``"unknown"`` where it can't be determined.

    ``getpass.getuser()`` raises when no LOGNAME/USER/LNAME/USERNAME is set
    and the uid has no passwd entry — common in slim containers.
    """
    try:
        return getpass.getuser()
    except Exception:
        return "unknown"


def _stdin_is_tty() -> bool:
    """True only when stdin is a real terminal we can prompt on.

    ``isatty()`` raises on a closed or detached stdin, which is exactly
    the shape of a CI runner or an agent shell — the environment that
    produced ``tcsetattr: Inappropriate ioctl for device``. Treating any
    failure as "not a terminal" keeps the wizard on its non-interactive
    path instead of blocking on a prompt nobody can answer.
    """
    try:
        return bool(sys.stdin is not None and sys.stdin.isatty())
    except Exception:
        return False


def _interactive(args) -> bool:
    """Whether to prompt at all: not ``--quick``, and stdin is a terminal."""
    return not _is_quiet(args) and _stdin_is_tty()


def _yes(args, prompt: str, default: bool = True) -> bool:
    if not _interactive(args):
        return default
    suffix = " [Y/n]" if default else " [y/N]"
    while True:
        try:
            ans = input(prompt + suffix + " ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return default
        if not ans:
            return default
        if ans in ("y", "yes"):
            return True
        if ans in ("n", "no"):
            return False
        print("Please answer y or n.")


def _ask(args, prompt: str, default: str = "") -> str:
    if not _interactive(args):
        return default
    suffix = f" [{default}]" if default else ""
    try:
        ans = input(prompt + suffix + " ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return default
    return ans or default


def _step(n: int, total: int, title: str) -> None:
    bar = "─" * 50
    print(f"\n{bar}")
    print(f"  Step {n}/{total}: {title}")
    print(bar)


def _cmd_onboarding_license(args) -> int:
    """Run Step 1: License activation / free tier."""
    _step(1, 5, "License activation")
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


def _cmd_onboarding_eula(args) -> int:
    """Run Step 2: EULA acceptance (clickwrap)."""
    _step(2, 5, "License Agreement")

    config = load_config(getattr(args, "config_path", None))
    eula_path = Path(config.license_file).with_suffix(".eula_accepted")

    if eula_path.exists():
        print("✓ EULA already accepted — skipping.")
        return 0

    # Display EULA summary
    print("\n" + "─" * 50)
    print("  NEURALMIND TEAM LICENSE AGREEMENT")
    print("─" * 50)
    print(
        """
  By using NeuralMind Team, you agree to:

  1. LICENSE SCOPE
     - Use on up to the licensed number of seats
     - Not redistribute or sublicense the software

  2. RESTRICTIONS
     - No reverse engineering or decompiling
     - No removal of proprietary notices
     - No use to develop competing products

  3. DATA & PRIVACY
     - You retain rights to your data
     - We collect anonymized usage statistics

  4. TERM & TERMINATION
     - License is valid until the expiry date
     - May be terminated for breach or non-payment
     - 30-day grace period after expiration

  5. WARRANTY & LIABILITY
     - Software provided "AS IS" without warranty
     - Liability limited to fees paid in last 12 months

  Full agreement: docs/NEURALMIND-LICENSE-AGREEMENT.md
  Contact: legal@neuralmind.uk
"""
    )

    if _yes(args, "Do you accept the NeuralMind Team License Agreement?", default=True):
        # Record acceptance
        acceptance = {
            "accepted_at": datetime.now(timezone.utc).isoformat(),
            "agreement_version": "1.0",
            "acceptor": _os_user(),
        }
        with open(eula_path, "w") as f:
            json.dump(acceptance, f, indent=2)
        print("✓ EULA accepted.")
        return 0
    print("✗ You must accept the EULA to continue.")
    print("  To decline, exit and use the free tier instead.")
    return 1


def _cmd_onboarding_governance(args) -> int:
    """Run Step 3: Governance defaults (scope, threshold)."""
    _step(3, 5, "Governance defaults")
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
    """Run Step 4: Admin email setup."""
    _step(4, 5, "Admin setup")
    config = load_config(getattr(args, "config_path", None))

    # Detect current user email from OS. Non-interactive runs (--quick, or a
    # pipe/CI/agent shell with no TTY) can't answer the prompt, so they need
    # the derived default rather than an empty answer.
    default_user = f"{_os_user()}@local" if not _interactive(args) else ""
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
    """Run Step 5: Verify installation."""
    _step(5, 5, "Verification")
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
    rc = _cmd_onboarding_eula(args)
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
