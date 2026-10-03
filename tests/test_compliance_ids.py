"""Keep the compliance IDs quoted on published surfaces real and correctly named.

The docs NeuralMind hands to auditors quote SOC 2 Trust Services Criteria and
CMMC 2.0 practice IDs. Two kinds of error shipped and sat unnoticed for months:

- a real ID under the wrong category name: "A1.1 - Processing Integrity" (A1 is
  Availability) and "C1.2 - Availability" (C1 is Confidentiality);
- a real ID that doesn't cover what the policy does: the risk assessment tagged
  CC2.1 (information quality), the incident response plan tagged CC4.2
  (reporting control deficiencies).

The second kind needs a reader who knows the criteria. This test catches the
first kind, IDs that don't exist, and CMMC practices whose domain doesn't match
their NIST SP 800-171 family. Stdlib-only, like the guard it borrows its file
list from.
"""

from __future__ import annotations

import re

from tests.test_docs_claims import REPO_ROOT, _published_paths

# Every criterion in the AICPA 2017 Trust Services Criteria (points of focus
# revised 2022; the criteria themselves did not change).
TSC_IDS = frozenset(
    [f"CC1.{i}" for i in range(1, 6)]
    + [f"CC2.{i}" for i in range(1, 4)]
    + [f"CC3.{i}" for i in range(1, 5)]
    + [f"CC4.{i}" for i in range(1, 3)]
    + [f"CC5.{i}" for i in range(1, 4)]
    + [f"CC6.{i}" for i in range(1, 9)]
    + [f"CC7.{i}" for i in range(1, 6)]
    + ["CC8.1", "CC9.1", "CC9.2"]
    + [f"A1.{i}" for i in range(1, 4)]
    + [f"PI1.{i}" for i in range(1, 6)]
    + ["C1.1", "C1.2"]
    + ["P1.1", "P2.1", "P3.1", "P3.2", "P4.1", "P4.2", "P4.3", "P5.1", "P5.2"]
    + [f"P6.{i}" for i in range(1, 8)]
    + ["P7.1", "P8.1"]
)

# The optional categories, keyed by the prefix of their IDs.
TSC_CATEGORY = {
    "A1": "Availability",
    "PI1": "Processing Integrity",
    "C1": "Confidentiality",
    "P": "Privacy",
}

# CMMC Level 2 practices are the 110 NIST SP 800-171 Rev. 2 requirements:
# domain -> (800-171 family, number of requirements in it).
CMMC_DOMAINS = {
    "AC": (1, 22),
    "AT": (2, 3),
    "AU": (3, 9),
    "CM": (4, 9),
    "IA": (5, 11),
    "IR": (6, 3),
    "MA": (7, 6),
    "MP": (8, 9),
    "PS": (9, 2),
    "PE": (10, 6),
    "RA": (11, 3),
    "CA": (12, 4),
    "SC": (13, 16),
    "SI": (14, 7),
}

# A SOC 2 header line in a policy: "**SOC 2 Controls:** CC6.1, CC6.2".
SOC2_HEADER_RE = re.compile(r"SOC\s?2 Controls?:")
TSC_ID_RE = re.compile(r"\b(?:CC\d{1,2}|A\d|PI\d|C\d|P\d)\.\d{1,2}\b")
# "CC" never starts anything else on these surfaces, so CC IDs are checked on
# every line. A1.1 or P2.1 could be anything, so those are checked only in a
# SOC 2 header or next to a category name.
CC_ID_RE = re.compile(r"\bCC\d{1,2}\.\d{1,2}\b")
CATEGORY_LABEL_RE = re.compile(
    r"\b(A1|PI1|C1|P[1-8])\.\d\b[\s*:|\-–—]{0,8}"
    r"(Availability|Processing Integrity|Confidentiality|Privacy)\b"
)
CMMC_L2_RE = re.compile(r"\b([A-Z]{2})\.L2-3\.(\d{1,2})\.(\d{1,2})\b")


def _series(control_id: str) -> str:
    prefix = control_id.split(".")[0]
    return "P" if re.fullmatch(r"P\d", prefix) else prefix


def _tsc_problems(line: str) -> list[str]:
    problems = []
    ids = set(CC_ID_RE.findall(line))
    if SOC2_HEADER_RE.search(line):
        ids |= set(TSC_ID_RE.findall(line))
    for control_id in sorted(ids):
        if control_id not in TSC_IDS:
            problems.append(f"{control_id} is not a Trust Services Criterion")
    for m in CATEGORY_LABEL_RE.finditer(line):
        expected = TSC_CATEGORY[_series(m.group(1))]
        if m.group(2) != expected:
            problems.append(f"{m.group(0)!r}: {m.group(1)} criteria are {expected}")
    return problems


def _cmmc_problems(line: str) -> list[str]:
    problems = []
    for m in CMMC_L2_RE.finditer(line):
        domain, family, number = m.group(1), int(m.group(2)), int(m.group(3))
        if domain not in CMMC_DOMAINS:
            problems.append(f"{m.group(0)}: {domain} is not a CMMC domain")
            continue
        expected_family, count = CMMC_DOMAINS[domain]
        if family != expected_family:
            problems.append(f"{m.group(0)}: {domain} practices are 3.{expected_family}.x")
        elif not 1 <= number <= count:
            problems.append(f"{m.group(0)}: 3.{family} has {count} requirements")
    return problems


def test_published_compliance_ids_exist_and_are_correctly_named() -> None:
    violations: list[str] = []
    for path in _published_paths():
        rel = path.relative_to(REPO_ROOT)
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        for index, line in enumerate(lines):
            for problem in _tsc_problems(line) + _cmmc_problems(line):
                violations.append(f"{rel}:{index + 1}: {problem}")
    assert not violations, (
        "A published surface quotes a compliance ID that doesn't exist or names "
        "the wrong category:\n  " + "\n  ".join(violations)
    )


def test_checks_trip_on_the_ids_that_shipped() -> None:
    # The lines as they were published, so a refactor can't turn the checks
    # into a silent no-op.
    assert _tsc_problems("✅ A1.1 - Processing Integrity")
    assert _tsc_problems("✅ C1.2 - Availability")
    assert _tsc_problems("| **A1.1 Processing Integrity** | Index validation |")
    assert _tsc_problems("**SOC 2 Controls:** CC10.1")
    assert _tsc_problems("**SOC 2 Control:** P9.1")
    assert _cmmc_problems("# CMMC AU.L2-3.1.1: audit")
    assert _cmmc_problems("// AC.L2-3.1.23: no such requirement")
    assert _cmmc_problems("// ZZ.L2-3.1.1: no such domain")
    # The corrected forms pass.
    assert not _tsc_problems("| **A1.2** | Backup and recovery | local SQLite |")
    assert not _tsc_problems("**SOC 2 Controls:** C1.2, P4.3")
    assert not _tsc_problems("**SOC 2 Controls:** CC7.3, CC7.4, CC7.5")
    assert not _tsc_problems("C1.2 - Disposing of confidential information")
    assert not _cmmc_problems("| **SC.L2-3.13.16** | Protect CUI at rest |")
    assert not _cmmc_problems("// AC.L2-3.1.22: last AC requirement")


def test_the_criteria_tables_are_scanned() -> None:
    scanned = {path.relative_to(REPO_ROOT).as_posix() for path in _published_paths()}
    assert "docs/COMPLIANCE-SUMMARY.md" in scanned
    assert "docs/compliance/ACCESS_CONTROL.md" in scanned
    assert len(TSC_IDS) == 61
    assert sum(count for _, count in CMMC_DOMAINS.values()) == 110
