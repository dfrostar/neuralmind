# Copyright (c) 2026 Cheval-Volant LLC (d/b/a NeuralMind).
# Source-available under the NeuralMind Commercial Modules License
# (neuralmind/tier2/LICENSE) — NOT MIT. Free 1-seat use included; see LICENSING.md.
"""pricing.py — Pricing configuration for NeuralMind."""

from __future__ import annotations

from pathlib import Path

import yaml

# Per-seat prices must agree with commercial-terms.json ($29/user/mo, the
# CI-gated source of truth) — longer terms are the flat monthly rate, no
# invented discounts.
DEFAULT_PRICING = {
    "team": {
        "monthly": {"base_per_seat": 29.00, "currency": "USD"},
        "quarterly": {"base_per_seat": 87.00, "currency": "USD"},
        "annual": {"base_per_seat": 348.00, "currency": "USD"},
        "biennial": {"base_per_seat": 696.00, "currency": "USD"},
    },
    "free": {"seats": 1, "never_expires": True},
    "partners": {
        "default_commission_percent": 20,
        "tiers": {"bronze": 20, "silver": 25, "gold": 30, "platinum": 35},
    },
    "trial": {"default_days": 14, "max_seats": 5, "auto_convert": False},
}


def load_pricing(config_path: Path | None = None) -> dict:
    """Load pricing configuration from YAML."""
    if config_path is None:
        config_path = Path.home() / ".neuralmind" / "pricing.yaml"
    if config_path.exists():
        with open(config_path) as f:
            return yaml.safe_load(f) or DEFAULT_PRICING
    return DEFAULT_PRICING


# Named entries in the pricing table, by term length in months. Terms the
# CLI accepts but this table does not name (6 and 36) bill at the flat
# monthly rate for every month of the term — they used to fall through to a
# single month's rate, quoting a 36-month deal at 1/36th of its value.
_TERM_KEYS = {1: "monthly", 3: "quarterly", 12: "annual", 24: "biennial"}


def calculate_price(
    pricing: dict,
    tier: str,
    seats: int,
    term_months: int,
) -> float:
    """Calculate the total price for a license over its whole term.

    Args:
        pricing: Pricing table, as returned by :func:`load_pricing`.
        tier: ``"free"`` or ``"team"``.
        seats: Number of seats on the license.
        term_months: Term length in months.

    Returns:
        Total price in the table's currency for all seats over the term.
    """
    if tier == "free":
        return 0.0
    tier_pricing = pricing.get("team", {})
    monthly = tier_pricing.get("monthly", {}).get("base_per_seat", 29.0)
    key = _TERM_KEYS.get(term_months)
    base = tier_pricing.get(key, {}).get("base_per_seat") if key else None
    if base is None:
        base = monthly * term_months
    return base * seats
