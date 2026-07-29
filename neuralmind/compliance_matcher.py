"""
compliance_matcher.py — Detect compliance annotations in code comments.

When a developer writes::

    // CMMC AC-3: MFA required
    # SOX ITGC-CM-001: Change approved via CAB
    /* HIPAA 164.312(a)(1): Access control required */
    // NIST SP 800-53 AC-1: Access control policy

NeuralMind detects the annotation and creates a synapse linking that
code node to the referenced compliance control, making it retrievable
by queries like "what code implements AC-1?".

Supported frameworks:
- CMMC (Cybersecurity Maturity Model Certification)
- NIST SP 800-53
- SOX ITGC
- HIPAA Security Rule
"""

from __future__ import annotations

import re
from pathlib import Path

# --------------------------------------------------------------------------- #
# Regex patterns for compliance annotations
# --------------------------------------------------------------------------- #

# Each pattern has a named group ``control_id`` that captures the canonical
# control identifier (e.g. ``AC.L2-3.1.1``, ``ITGC-CM-001``).
_PATTERNS: list[tuple[str, re.Pattern]] = [
    # CMMC: AC.L2-3.1.1, IA.L2-3.5.1, etc. (with optional "CMMC" prefix)
    (
        "CMMC",
        re.compile(
            r"""
            (?:CMMC[:\s]+)?          # optional "CMMC" prefix
            (?P<control_id>
                [A-Z]{2,3}\.L[12]-   # domain + level  (e.g. AC.L2-)
                \d+(?:\.\d+)+        # practice number (e.g. 3.1.1)
            )
            [:\s]+                   # separator
            (?P<label>.+?)           # brief description
            (?:$|[.\n\r])
            """,
            re.IGNORECASE | re.VERBOSE,
        ),
    ),
    # NIST SP 800-53: AC-1, AU-3(1), IA-5(1)(a), etc.
    # Requires explicit NIST prefix to avoid false matches on SOX controls (ITGC-CM-001)
    (
        "NIST",
        re.compile(
            r"""
            (?:
                NIST\s+SP\s+800-53[\s:]+   # full prefix "NIST SP 800-53:"
                |NIST[\s:]                  # or just "NIST:"
            )
            (?P<control_id>
                [A-Z]{2}-\d+        # e.g. AC-1, AU-3, IA-5
                (?:\([^)]+\))*       # optional refinements e.g. (1)(a)
            )
            [:\s]+
            (?P<label>.+?)
            (?:$|[.\n\r])
            """,
            re.IGNORECASE | re.VERBOSE,
        ),
    ),
    # SOX ITGC: ITGC-CM-001, ITGC-PM-001, etc. (Control Mapping)
    (
        "SOX ITGC",
        re.compile(
            r"""
            (?:SOX[:\s]+)?           # optional "SOX" prefix
            (?P<control_id>
                ITGC-[A-Z]{2}-\d{3}  # e.g. ITGC-CM-001, ITGC-PM-001
            )
            [:\s]+
            (?P<label>.+?)
            (?:$|[.\n\r])
            """,
            re.IGNORECASE | re.VERBOSE,
        ),
    ),
    # HIPAA Security Rule: 164.312(a)(1), 164.308(a)(1)(ii)(A), etc.
    (
        "HIPAA",
        re.compile(
            r"""
            (?:HIPAA[:\s]+)?
            (?P<control_id>
                164\.\d{3}
                (?:\([^)]+\))+        # one or more parentheticals
            )
            [:\s]+
            (?P<label>.+?)
            (?:$|[.\n\r])
            """,
            re.IGNORECASE | re.VERBOSE,
        ),
    ),
    # ISO 27001: A.9.2.1, A.12.6.1, etc.
    (
        "ISO 27001",
        re.compile(
            r"""
            (?:ISO\s*27001[:\s]+)?
            (?P<control_id>
                A\.\d+(?:\.\d+)+     # e.g. A.9.2.1
            )
            [:\s]+
            (?P<label>.+?)
            (?:$|[.\n\r])
            """,
            re.IGNORECASE | re.VERBOSE,
        ),
    ),
]


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #


def find_compliance_annotations(text: str) -> list[dict]:
    """Scan ``text`` for compliance annotations of any supported framework.

    Returns a list of dicts::

        [
            {
                "framework": "CMMC",
                "control_id": "AC.L2-3.1.1",
                "label": "Authorized Access Control",
                "match_text": "CMMC AC.L2-3.1.1: Authorized Access Control",
            },
            ...
        ]

    Empty list when nothing matches.
    """
    results: list[dict] = []
    seen: set[tuple[str, str]] = set()  # dedup (framework, control_id)

    for framework, pattern in _PATTERNS:
        for m in pattern.finditer(text):
            control_id = m.group("control_id").strip().upper()
            label = m.group("label").strip()
            key = (control_id, framework)
            if key not in seen:
                seen.add(key)
                results.append(
                    {
                        "framework": framework,
                        "control_id": control_id,
                        "label": label,
                        "match_text": m.group(0).strip(),
                        "span": (m.start(), m.end()),
                    }
                )

    return results


def find_compliance_annotations_in_file(file_path: str | Path) -> list[dict]:
    """Read ``file_path`` and return all compliance annotations found."""
    try:
        text = Path(file_path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    return find_compliance_annotations(text)


def compliance_synapse_key(control_id: str, framework: str) -> str:
    """Canonical synapse edge id between a code node and a compliance control.

    The convention is ``compliance:{framework}:{control_id}`` so that
    queries like "what code implements AC.L2-3.1.1?" can find these easily.
    """
    return f"compliance:{framework.upper()}:{control_id.upper()}"


def compliance_node_key(control_id: str, framework: str) -> str:
    """Canonical virtual node id for a compliance control in the graph.

    These id's are used when ingesting a compliance framework so the
    control itself appears as a first-class graph node.
    """
    return f"__compliance__{framework.upper()}_{control_id.upper().replace('.', '_').replace('-', '_')}"
