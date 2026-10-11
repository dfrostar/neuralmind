"""The published VEX, the pip-audit gate and the advisory watch must agree.

security/neuralmind.openvex.json is published with every tagged release and
read by CI: scripts/vex_ignores.py turns its `not_affected` statements into
pip-audit's ignore list. These checks keep it a document an assessor can rely
on rather than a way to quiet the gate:

- every statement is valid OpenVEX for its status (OpenVEX requires a
  justification or impact statement for `not_affected`);
- every advisory it marks not_affected is argued in SECURITY.md;
- it covers exactly the advisories .github/workflows/chromadb-cve-watch.yml
  watches, so one that gains a fix (and stops being ignorable) can't stay in
  VEX unnoticed, and a newly watched one can't be left out.

Stdlib-only.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VEX = ROOT / "security" / "neuralmind.openvex.json"
WATCH = ROOT / ".github" / "workflows" / "chromadb-cve-watch.yml"

STATUSES = {"not_affected", "affected", "fixed", "under_investigation"}
JUSTIFICATIONS = {
    "component_not_present",
    "vulnerable_code_not_present",
    "vulnerable_code_not_in_execute_path",
    "vulnerable_code_cannot_be_controlled_by_adversary",
    "inline_mitigations_already_exist",
}


def _doc() -> dict:
    return json.loads(VEX.read_text(encoding="utf-8"))


def test_document_header():
    doc = _doc()
    assert doc["@context"].startswith("https://openvex.dev/ns/")
    for key in ("@id", "author", "timestamp", "version", "statements"):
        assert doc.get(key), key


def test_statements_are_valid_openvex():
    for st in _doc()["statements"]:
        name = st["vulnerability"]["name"]
        assert st["status"] in STATUSES, name
        assert st["products"], name
        if st["status"] == "not_affected":
            assert st.get("justification") in JUSTIFICATIONS or st.get("impact_statement"), name
            assert st.get("impact_statement"), f"{name}: say why, for the assessor"
        if st["status"] == "affected":
            assert st.get("action_statement"), name


def test_not_affected_advisories_are_argued_in_security_md():
    security = (ROOT / "SECURITY.md").read_text(encoding="utf-8")
    for st in _doc()["statements"]:
        if st["status"] == "not_affected":
            assert st["vulnerability"]["name"] in security, st["vulnerability"]["name"]


def test_vex_matches_the_advisory_watch():
    watched = set(re.findall(r'"(CVE-\d{4}-\d+)":\s*\(', WATCH.read_text(encoding="utf-8")))
    assert watched, "chromadb-cve-watch.yml's WATCHED table moved; update this test"
    in_vex = {
        st["vulnerability"]["name"]
        for st in _doc()["statements"]
        if any(
            "chromadb" in sub["@id"] for p in st["products"] for sub in p.get("subcomponents", [])
        )
    }
    assert in_vex == watched


def test_ignore_flags_cover_every_alias():
    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        from vex_ignores import ignored_ids
    finally:
        sys.path.pop(0)
    ids = ignored_ids(VEX)
    for st in _doc()["statements"]:
        if st["status"] == "not_affected":
            vuln = st["vulnerability"]
            assert {vuln["name"], *vuln.get("aliases", [])} <= set(ids)
