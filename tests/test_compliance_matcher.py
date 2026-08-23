"""Guard the compliance annotation matcher against false positives.

``neuralmind/compliance_matcher.py`` had no tests, and two of its six patterns
made their framework marker optional. That reduced them to "one to three
letters, digits, a dot, digits" — a shape shared by version strings, SVG path
commands, and milestone ids. Scanning this repo produced 147 SOC 2
"annotations" of which 129 were noise.

That matters more than a noisy scan: these annotations feed ``neuralmind
export --controls``, documented as producing control-to-code mappings for
evidence submission. A fabricated control in an audit export is a
materially worse failure than a missed one, so these tests pin precision.

Stdlib-only, like the other guard modules, so they run without the full dep
set.

neuralmind:example-file — every annotation in this file is a fixture, not
evidence, and must not reach ``neuralmind export --controls``.
"""

from __future__ import annotations

from neuralmind.compliance_matcher import (
    SCANNABLE_SUFFIXES,
    find_compliance_annotations,
    iter_scannable_files,
)


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


# --------------------------------------------------------------------------- #
# Scan scope, label capture and comma lists
#
# These three shipped broken together and are what made the compliance surfaces
# report nothing useful on a repo that holds real annotations.
# --------------------------------------------------------------------------- #


def test_markdown_is_scannable() -> None:
    """Policy documents are where control annotations actually live.

    `neuralmind compliance` had a code-only suffix allowlist and
    `neuralmind_compliance_report` did rglob("*.py"). Neither could see
    docs/compliance/*.md, so both reported zero while seven real annotations
    sat on disk.
    """
    for suffix in (".md", ".mdx", ".rst", ".txt"):
        assert suffix in SCANNABLE_SUFFIXES, suffix
    # source files must keep working too
    for suffix in (".py", ".ts", ".go", ".rs"):
        assert suffix in SCANNABLE_SUFFIXES, suffix


def test_scanner_skips_noise_directories(tmp_path) -> None:
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "policy.md").write_text("**SOC 2 Control:** CC6.1\n")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "junk.md").write_text("**SOC 2 Control:** CC6.1\n")

    found = {f.name for f in iter_scannable_files(tmp_path)}
    assert "policy.md" in found
    assert "junk.md" not in found


def test_label_is_never_taken_from_the_next_line() -> None:
    """The documented form puts the id last on its line, followed by a rule.

    The separator before the label group matches newlines, so every one of this
    repo's genuine annotations exported label='---' — the markdown rule beneath
    it — straight into `neuralmind export --audit` and its CSV label column.
    """
    hits = find_compliance_annotations("**SOC 2 Control:** CC6.1\n---\n")
    assert [h["control_id"] for h in hits] == ["CC6.1"]
    assert hits[0]["label"] == ""


def test_same_line_label_is_still_captured() -> None:
    hits = find_compliance_annotations(
        "# Compliance: CC6.1: Logical access controls restrict access.\n"
    )
    assert hits[0]["label"] == "Logical access controls restrict access"


def test_comma_separated_control_lists_yield_every_id() -> None:
    """`**SOC 2 Controls:** CC3.1, CC8.1, A1.1` used to yield only A1.1.

    The pattern requires a separator after the id and a comma is not one, so
    the engine walked past the first two. docs/compliance/SDLC_POLICY.md and
    CHANGE_MANAGEMENT.md were each under-reporting two controls.
    """
    hits = find_compliance_annotations("**SOC 2 Controls:** CC3.1, CC8.1, A1.1\n---\n")
    assert {h["control_id"] for h in hits} == {"CC3.1", "CC8.1", "A1.1"}


def test_comma_list_recovery_does_not_reintroduce_false_positives() -> None:
    """The sibling pass only reads lines a real marker already validated."""
    for text in (
        "Shipped in v0.13.0, v2.0 and v0.22 today.\n",
        '<path d="M13.5 3H7a2 2 0 0 0-2 2v14, M3.2 12h17" />\n',
        "noncompliance: CC3.1, CC8.1, A1.1\n",
    ):
        assert find_compliance_annotations(text) == [], text


# --------------------------------------------------------------------------- #
# ci-check --framework
# --------------------------------------------------------------------------- #


def test_detect_framework_maps_user_input() -> None:
    from neuralmind.ci_check import _detect_framework

    assert _detect_framework("cmmc") == ["CMMC"]
    assert _detect_framework("soc2") == ["SOC2"]
    assert _detect_framework("soc 2") == ["SOC2"]
    assert _detect_framework("iso") == ["ISO 27001"]
    # "all" must include SOC2 — it was omitted, so wiring the filter without
    # this would have silently dropped every SOC 2 finding.
    assert "SOC2" in _detect_framework("all")


def test_ci_check_framework_actually_filters(tmp_path, monkeypatch) -> None:
    """`--framework` was accepted, echoed, and ignored.

    _detect_framework had zero callers, so `ci-check --framework cmmc` printed
    "Framework: CMMC" and then reported findings from every framework.
    """
    from neuralmind import ci_check

    (tmp_path / "policy.md").write_text(
        "**SOC 2 Control:** CC6.1\n// CMMC AC.L2-3.1.1: Authorized Access Control\n"
    )
    monkeypatch.setattr(ci_check, "_get_diff_files", lambda *a, **k: ["policy.md"])

    every = ci_check.run_ci_check(tmp_path, framework="all")
    frameworks = {f["framework"] for f in every["findings"]}
    assert {"SOC2", "CMMC"} <= frameworks, frameworks

    only_cmmc = ci_check.run_ci_check(tmp_path, framework="cmmc")
    assert {f["framework"] for f in only_cmmc["findings"]} == {"CMMC"}
    assert "CC6.1" not in only_cmmc["affected_controls"]


# --------------------------------------------------------------------------- #
# Opt-out markers
# --------------------------------------------------------------------------- #
# Documentation has to *show* an annotation, and a shown one is byte-identical
# to a real one. This repo reported 37 annotations of which 12 were evidence.
# The markers are spelled by concatenation here so this file's own tests do not
# trip the file-level marker before it is under test.

_LINE = "neuralmind:" + "example"
_FILE = "neuralmind:" + "example-file"


def test_same_line_marker_drops_that_annotation() -> None:
    assert find_compliance_annotations(f"# NIST AC-1: Access policy  {_LINE}") == []


def test_same_line_marker_leaves_other_lines_alone() -> None:
    text = f"# NIST AC-1: Access policy  {_LINE}\n# NIST AU-3: Audit review"
    assert [a["control_id"] for a in find_compliance_annotations(text)] == ["AU-3"]


def test_file_marker_drops_every_annotation_in_the_text() -> None:
    text = f"{_FILE}\n# NIST AC-1: x\n# CMMC AC.L2-3.1.1: y"
    assert find_compliance_annotations(text) == []


def test_markers_do_not_themselves_match() -> None:
    assert find_compliance_annotations(f"{_LINE} {_FILE}") == []


def test_marker_suppresses_a_whole_comma_list() -> None:
    """The #455 sibling pass must not resurrect ids from a suppressed line."""
    text = f"**SOC 2 Controls:** CC3.1, CC8.1, A1.1 - change mgmt  {_LINE}"
    assert find_compliance_annotations(text) == []


def test_unsuppressed_comma_list_still_yields_every_id() -> None:
    text = "**SOC 2 Controls:** CC3.1, CC8.1, A1.1 - change mgmt"
    assert len(find_compliance_annotations(text)) == 3


def test_markers_do_not_weaken_the_false_positive_guards() -> None:
    """The #453 guards must survive the marker work."""
    assert find_compliance_annotations("Shipped in v0.13.0, v2.0 and v0.22 today.") == []
    assert find_compliance_annotations("noncompliance: CC3.1, CC8.1 - nope") == []
