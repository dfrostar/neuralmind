"""NeuralMind Tier 2 — Team-tier modules (governance, audit, licensing, seats).

Requires the [team] extra. All modules in this package are fail-open:
any error degrades to pre-existing behavior rather than blocking the
core product. Each module carries module + class + method docstrings
per docs/CODE-DOCUMENTATION-STANDARDS.md.

See Also:
    - ``neuralmind/tier2/governance.py`` — governance publish/scoping
    - ``neuralmind/tier2/audit.py`` — tamper-evident audit trail
    - ``neuralmind/tier2/license.py`` — Ed25519 license validation
    - ``neuralmind/tier2/seats.py`` — team seat management

Version:
    0.53.0
"""
