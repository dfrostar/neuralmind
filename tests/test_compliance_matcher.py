"""Guard the compliance annotation matcher against false positives.

``neuralmind/compliance_matcher.py`` had no tests, and two of its six patterns
made their framework marker optional. That reduced them to "one to three
letters, digits, a dot, digits" — a shape shared by version strings, SVG path
commands, and milestone ids. Scanning this repo produced 147 SOC 2
"annotations" of which 129 were noise.

That matters more than a noisy scan: these annotations feed ``neuralmind
export --audit``, documented as producing "flat compliance reports (CSV/JSON)
for evidence submission". A fabricated control in an audit export is a
materially worse failure than a missed one, so these tests pin precision.

Stdlib-only, like the other guard modules, so they run without the full dep
set.
"""

from __future__ import annotations

from neuralmind.compliance_matcher import find_compliance_annotations


def _controls(text: str, framework: str) -> set[str]:
    return {
        h["control_id"] for h in find_compliance_annotations(text) if h["framework"] == framework
    }


# --------------------------------------------------------------------------- #
# SOC 2 — the pattern that regressed
# --------------------------------------------------------------------------- #


def test_soc2_matches_the_documented_annotation_forms() -> None:
    """Every form the repo's own docs and CLI help actually use."""
    # The form used throughout docs/compliance/*.md.
    assert "CC6.1" in _controls("**SOC 2 Control:** CC6.1\n---\n", "SOC2")
    # A comma list — the last id is the one that reaches a separator.
    assert "A1.1" in _controls("**SOC 2 Controls:** CC3.1, CC8.1, A1.1\n---\n", "SOC2")
    # The generic `Compliance:` keyword CLAUDE.md documents.
    assert "CC6.1" in _controls("# Compliance: CC6.1: Logical access controls.\n", "SOC2")
    # An inline code annotation.
    assert "CC7.2" in _controls("// SOC2 CC7.2: System monitoring detects anomalies.\n", "SOC2")


def test_soc2_does_not_match_svg_path_data() -> None:
    """M, L, C, A and S are SVG path verbs, not Trust Services Criteria.

    The regression that surfaced this: a 15-icon SVG set added to the
    marketing site produced 33 fabricated SOC 2 annotations in one PR.
    """
    icons = [
        '<path d="M13.5 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8.5Z" />',
        '<path d="M3.2 12h17.6" />',
        '<path d="M15.5 12h3" />',
        '<path d="M9.6 9.1 12.3 12" stroke="currentColor" />',
        '<path d="M4.5 12.5 9.5 17.5 19.5 6.5" />',
    ]
    for markup in icons:
        assert find_compliance_annotations(markup) == [], markup


def test_soc2_does_not_match_version_strings() -> None:
    """The single largest source of noise: 67 of the 129 false positives."""
    prose = [
        'Shipped in v0.13.0 — the "Measure" release is built around this.\n',
        "Roadmap: v2.0 Complete, v0.22 flipped the default backend to auto.\n",
        "pip install neuralmind==0.3 for the old format.\n",
    ]
    for text in prose:
        assert _controls(text, "SOC2") == set(), text


def test_soc2_does_not_match_toolchain_and_milestone_identifiers() -> None:
    """`python3.10` became HON3.10, `TLSv1.2` became LSV1.2, `llama3.1` AMA3.1."""
    for text in (
        "Install with python3.10 -m venv neuralmind-env\n",
        "Requires TLSv1.2 or newer for transport.\n",
        "Tested against llama3.1 70b locally.\n",
        "Milestone E1.4 deliverable) implemented in the harness.\n",
    ):
        assert _controls(text, "SOC2") == set(), text


def test_soc2_marker_must_be_a_whole_word() -> None:
    """The marker is matched with word boundaries, not as a substring.

    Raised by Copilot review on #453. Without boundaries, "noncompliance" —
    a word that appears constantly in compliance prose — ends in the generic
    marker, and "SOC 20" matches the real marker then absorbs the stray digit
    as intervening text.
    """
    for text in (
        "SOC 20 CC6.1: fabricated\n",
        "noncompliance: CC6.1: fabricated\n",
        "Our noncompliance with CC6.1: fabricated\n",
    ):
        assert _controls(text, "SOC2") == set(), text


def test_soc2_control_ids_are_case_sensitive() -> None:
    """Pins the scoped ``(?-i:)`` on the control id.

    The SVG tests above carry no marker, so they pass on the marker rule alone
    and would still pass if the case-sensitivity modifier were deleted. These
    supply a marker, so only the modifier can reject them — which matters
    because SVG path verbs are as often lowercase as upper.
    """
    for text in (
        "# Compliance: m13.5 3H7a2 2 0 0 0-2 2v14\n",
        "# Compliance: cc6.1 lowercase is not a control id\n",
    ):
        assert _controls(text, "SOC2") == set(), text


# --------------------------------------------------------------------------- #
# ISO 27001 — same latent flaw, found while fixing SOC 2
# --------------------------------------------------------------------------- #


def test_iso27001_matches_its_documented_form() -> None:
    assert "A.9.2.1" in _controls(
        "**ISO 27001:** A.9.2.1: User access provisioning.\n", "ISO 27001"
    )


def test_iso27001_does_not_match_minified_svg_arcs() -> None:
    """`a.5.5 0 0 1` is legal SVG arc shorthand; it parsed as control A.5.5."""
    markup = '<path d="M4 8a.5.5 0 0 1 .5-.5h7a.5.5 0 0 1 0 1h-7A.5.5 0 0 1 4 8Z"/>'
    assert find_compliance_annotations(markup) == []


def test_iso27001_marker_must_be_a_whole_word_and_control_id_case_sensitive() -> None:
    """Same two guards as SOC 2, on the pattern that shares the flaw."""
    for text in (
        "ISO 270010 A.9.2.1: fabricated\n",
        "Our noncompliance with A.9.2.1: fabricated\n",
        # Marker present, lowercase arc verb — only the scoped (?-i:) rejects this.
        "# Compliance: a.5.5 0 0 1 .5-.5h7\n",
    ):
        assert _controls(text, "ISO 27001") == set(), text


# --------------------------------------------------------------------------- #
# The four patterns that were already correct must stay correct
# --------------------------------------------------------------------------- #


def test_other_frameworks_still_match() -> None:
    cases = [
        ("CMMC", "// CMMC AC.L2-3.1.1: Authorized Access Control\n", "AC.L2-3.1.1"),
        # Note: the NIST pattern accepts "NIST AC-1" and "NIST SP 800-53: AC-1"
        # but not "NIST: AC-1" — its prefix group consumes exactly one
        # separator char. Pre-existing, and out of scope here; pinned so a
        # future change to that pattern is a deliberate one.
        ("NIST", "# NIST AC-1: Access control policy\n", "AC-1"),
        ("SOX ITGC", "// SOX ITGC-CM-001: Change approved via CAB\n", "ITGC-CM-001"),
        ("HIPAA", "/* HIPAA 164.312(a)(1): Access control required */\n", "164.312(A)(1)"),
    ]
    for framework, text, control_id in cases:
        assert control_id in _controls(text, framework), (framework, text)


def test_plain_source_code_yields_nothing() -> None:
    """A file with no compliance intent must produce no annotations at all."""
    source = (
        "def handle(request):\n"
        "    # Retry up to 3.5 seconds, see RFC 7231 section 6.5.\n"
        '    return {"status": 200, "version": "v1.2"}\n'
    )
    assert find_compliance_annotations(source) == []
