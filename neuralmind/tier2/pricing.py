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


def calculate_price(
    pricing: dict,
    tier: str,
    seats: int,
    term_months: int,
) -> float:
    """Calculate total price for a license."""
    if tier == "free":
        return 0.0
    tier_pricing = pricing.get("team", {})
    if term_months == 1:
        base = tier_pricing.get("monthly", {}).get("base_per_seat", 29.0)
    elif term_months == 3:
        base = tier_pricing.get("quarterly", {}).get("base_per_seat", 87.0)
    elif term_months == 12:
        base = tier_pricing.get("annual", {}).get("base_per_seat", 348.0)
    elif term_months == 24:
        base = tier_pricing.get("biennial", {}).get("base_per_seat", 696.0)
    else:
        # Monthly rate for other terms
        base = tier_pricing.get("monthly", {}).get("base_per_seat", 29.0)
    return base * seats
