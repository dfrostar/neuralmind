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
    # Marker required — see the SOC 2 note below. Without one, minified SVG arc
    # shorthand (``a.5.5 0 0 1``) parses as control ``A.5.5``.
    (
        "ISO 27001",
        re.compile(
            r"""
            (?:\bISO\s*27001|\bCOMPLIANCE)\b   # required marker, whole word
            [^\n]{0,32}?                  # optional intervening words, same line
            \b
            (?P<control_id>
                (?-i:A)\.\d+(?:\.\d+)+   # e.g. A.9.2.1 — never lowercase
            )
            [:\s]+
            (?P<label>.+?)
            (?:$|[.\n\r])
            """,
            re.IGNORECASE | re.VERBOSE,
        ),
    ),
    # SOC 2: CC6.1, CC7.2, P1.1, PI1.4, etc. (Trust Services Criteria)
    #
    # The marker is REQUIRED. It used to be optional, which left the pattern as
    # "any 1-3 letters, digits, a dot, digits" — a shape that matches far more
    # than SOC 2 criteria. Scanning this repo produced 147 SOC 2 "annotations"
    # of which 129 were noise: 67 version strings (``v0.13``, ``v2.0``), 39 SVG
    # path commands (``M13.5``, ``A1.5`` — ``M``/``L``/``C``/``A``/``S`` are
    # path verbs), 18 eval milestone ids (``E1.4``), plus ``python3.10``,
    # ``TLSv1.2`` and ``llama3.1``. Those flowed into ``neuralmind export
    # --audit``, which users submit as compliance evidence.
    #
    # NIST above already required its prefix for exactly this reason. The
    # marker may be the framework name or the generic ``Compliance:`` keyword,
    # and intervening words are allowed so the documented form
    # ``**SOC 2 Control:** CC6.1`` keeps working.
    #
    # The marker needs word boundaries or it matches as a substring: without
    # them ``noncompliance: CC6.1`` matches on the tail of "noncompliance" —
    # a word that appears constantly in compliance prose — and ``SOC 20`` /
    # ``ISO 270010`` match the real marker and absorb the trailing digit as
    # intervening text.
    (
        "SOC2",
        re.compile(
            r"""
            (?:\bSOC\s*2|\bCOMPLIANCE)\b  # required marker, whole word
            [^\n]{0,32}?                 # optional intervening words, same line
            \b
            (?P<control_id>
                (?-i:[A-Z]{1,3})\d+\.\d+  # e.g. CC6.1 — never lowercase, so
                                          # ``v0.13`` and ``m13.5`` cannot match
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
# What counts as a scannable file
# --------------------------------------------------------------------------- #

#: Suffixes every compliance surface scans.
#:
#: This lived twice, differently: ``neuralmind compliance`` had a code-only
#: allowlist and ``neuralmind_compliance_report`` did ``rglob("*.py")``.
#: Neither included ``.md`` — and every genuine annotation in this repository
#: lives in ``docs/compliance/*.md``, so both surfaces reported zero while
#: seven real annotations sat on disk. Defined once here so the two cannot
#: drift apart again.
SCANNABLE_SUFFIXES: frozenset[str] = frozenset(
    {
        # source
        ".py",
        ".ts",
        ".tsx",
        ".js",
        ".jsx",
        ".go",
        ".rs",
        ".java",
        ".cs",
        ".rb",
        ".php",
        ".c",
        ".cpp",
        ".h",
        # policy and evidence documents — where control annotations actually live
        ".md",
        ".mdx",
        ".rst",
        ".txt",
    }
)

#: Directories never worth scanning.
SCAN_EXCLUDE_DIRS: frozenset[str] = frozenset(
    {
        ".git",
        "node_modules",
        "__pycache__",
        ".neuralmind",
        ".next",
        "out",
        "htmlcov",
        ".venv",
        "venv",
    }
)


def iter_scannable_files(root):
    """Yield every scannable file under ``root``, skipping noise directories."""
    from pathlib import Path as _Path

    for f in _Path(root).rglob("*"):
        if not f.is_file() or f.suffix not in SCANNABLE_SUFFIXES:
            continue
        if any(part in SCAN_EXCLUDE_DIRS for part in f.parts):
            continue
        yield f


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
            label = _same_line_label(text, m)
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

            # Comma-separated lists: the pattern can only accept one id per
            # match, so pick up the rest from the line it already validated.
            for sibling in _sibling_control_ids(text, m, framework):
                sib_key = (sibling.upper(), framework)
                if sib_key in seen:
                    continue
                seen.add(sib_key)
                results.append(
                    {
                        "framework": framework,
                        "control_id": sibling.upper(),
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


def _same_line_label(text: str, m: re.Match) -> str:
    r"""Return the label, but only if it is on the same line as the control id.

    The ``label`` group is ``.+?``, and ``.`` does not match a newline — but the
    separator before it (``[:\s]+``) does. So when a control id ends its line,
    the separator swallows the newline and the label is captured from the line
    *below*. Every one of this repository's seven genuine SOC 2 annotations is
    written as ``**SOC 2 Control:** CC6.1`` followed by a markdown rule, and so
    every one of them exported ``label='---'`` into ``neuralmind export
    --audit``, the CSV evidence column, and the ci-check findings table.
    """
    line_end = text.find("\n", m.end("control_id"))
    if line_end == -1:
        line_end = len(text)
    tail = text[m.end("control_id") : line_end]
    # Drop a leading separator (": ", " - ", " — ") before the description.
    tail = re.sub(r"^[\s:\-\u2013\u2014]+", "", tail)
    return tail.strip().rstrip(".").strip()


#: Control-id shapes for the frameworks that permit comma-separated lists.
#: Uppercase-only and boundary-anchored, matching the strictness of the main
#: patterns — these run only on a line that already carried a valid marker.
_SIBLING_ID_RES: dict[str, re.Pattern] = {
    "SOC2": re.compile(r"(?<![A-Za-z0-9.])([A-Z]{1,3}\d+\.\d+)(?![\d.])"),
    "ISO 27001": re.compile(r"(?<![A-Za-z0-9.])(A\.\d+(?:\.\d+)+)(?![\d.])"),
}


def _sibling_control_ids(text: str, m: re.Match, framework: str) -> list[str]:
    r"""Other control ids listed on the same line as an accepted match.

    ``**SOC 2 Controls:** CC3.1, CC8.1, A1.1`` yielded only ``A1.1``: the
    pattern requires ``[:\s]+`` after the id and a comma is neither, so the
    engine walked past the first two. Rather than loosen the pattern — which is
    what let version strings and SVG path data in — this re-reads the line the
    match already validated and picks up its siblings.
    """
    sib_re = _SIBLING_ID_RES.get(framework)
    if sib_re is None:
        return []
    line_start = text.rfind("\n", 0, m.start("control_id")) + 1
    line_end = text.find("\n", m.end("control_id"))
    if line_end == -1:
        line_end = len(text)
    return sib_re.findall(text[line_start:line_end])


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
