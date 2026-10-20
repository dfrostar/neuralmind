"""The OSCAL component definition stays valid, and true to the code.

`security/neuralmind.oscal-component-definition.json` is what an agency loads
into its System Security Plan: NeuralMind's SP 800-53 Rev. 5 controls, with
what stays the customer's. It is hand-maintained, so these checks keep it from
drifting:

- it validates against the OSCAL 1.1.3 component-definition schema
  (vendored in tests/fixtures/oscal/, so no network is needed);
- every control ID is in the SP 800-53 Rev. 5 catalog and not withdrawn;
- every setting and command it names exists in the code;
- its version is the package's (release-please bumps both);
- its provider is the entity in commercial-terms.json;
- docs/compliance/SP800-53.md lists exactly the same controls.

The control-ID list is regenerated from the NIST catalog with:

    import json, urllib.request
    url = ("https://raw.githubusercontent.com/usnistgov/oscal-content/main/nist.gov/"
           "SP800-53/rev5/json/NIST_SP-800-53_rev5_catalog.json")
    catalog = json.load(urllib.request.urlopen(url))["catalog"]
    def walk(controls):
        for c in controls:
            if not any(p.get("name") == "status" and p.get("value") == "withdrawn"
                       for p in c.get("props", [])):
                yield c["id"]
            yield from walk(c.get("controls", []))
    ids = sorted(i for g in catalog["groups"] for i in walk(g.get("controls", [])))
"""

from __future__ import annotations

import contextlib
import io
import json
import re
import uuid
from pathlib import Path

import jsonschema
import pytest

import neuralmind
from neuralmind import cli

ROOT = Path(__file__).resolve().parent.parent
COMPONENT = ROOT / "security" / "neuralmind.oscal-component-definition.json"
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "oscal"
TABLE = ROOT / "docs" / "compliance" / "SP800-53.md"

# The schema's one pattern Python's `re` can't compile: Unicode property
# classes in the OSCAL token type. \p{L} becomes "a word character that isn't
# a digit or underscore", \p{N} a digit.
_TOKEN_PATTERN = r"^(\\p{L}|_)(\\p{L}|\\p{N}|[.\\-_])*$"
_TOKEN_PATTERN_RE = r"^([^\\W\\d_]|_)([^\\W\\d_]|\\d|[.\\-_])*$"


def _component() -> dict:
    return json.loads(COMPONENT.read_text(encoding="utf-8"))


def _requirements() -> list[dict]:
    components = _component()["component-definition"]["components"]
    return [
        req
        for component in components
        for impl in component["control-implementations"]
        for req in impl["implemented-requirements"]
    ]


def _validator() -> jsonschema.Draft7Validator:
    text = (FIXTURES / "oscal_component_schema_1.1.3.json").read_text(encoding="utf-8")
    assert _TOKEN_PATTERN in text, "the schema's token pattern changed; update the translation"
    text = text.replace(_TOKEN_PATTERN, _TOKEN_PATTERN_RE)
    assert "\\\\p{" not in text, "the schema has another Unicode property class to translate"
    return jsonschema.Draft7Validator(json.loads(text), format_checker=jsonschema.FormatChecker())


def test_it_validates_against_the_oscal_schema():
    errors = sorted(_validator().iter_errors(_component()), key=lambda e: list(e.path))
    assert not errors, "\n".join(f"{list(e.path)}: {e.message[:200]}" for e in errors)


def test_the_schema_check_rejects_a_broken_definition():
    broken = _component()
    del broken["component-definition"]["metadata"]["version"]
    assert list(_validator().iter_errors(broken))


def test_every_control_is_in_the_catalog_once():
    catalog = {
        line.strip()
        for line in (FIXTURES / "sp800-53r5_control_ids.txt").read_text().splitlines()
        if line.strip() and not line.startswith("#")
    }
    ids = [req["control-id"] for req in _requirements()]
    assert ids and len(ids) == len(set(ids))
    assert set(ids) <= catalog, sorted(set(ids) - catalog)


def _walk(node, key: str):
    """Every value stored under ``key`` anywhere in ``node``."""
    if isinstance(node, dict):
        for k, v in node.items():
            if k == key:
                yield v
            yield from _walk(v, key)
    elif isinstance(node, list):
        for item in node:
            yield from _walk(item, key)


def test_uuids_are_unique_v4_and_party_references_resolve():
    doc = _component()
    defined = list(_walk(doc, "uuid"))
    assert len(defined) == len(set(defined))
    assert all(uuid.UUID(u).version == 4 for u in defined)
    parties = {p["uuid"] for p in doc["component-definition"]["metadata"]["parties"]}
    referenced = {u for refs in _walk(doc, "party-uuids") for u in refs}
    assert referenced and referenced <= parties


def test_every_requirement_says_what_stays_the_customers():
    for req in _requirements():
        assert req["remarks"].startswith("Customer responsibility: "), req["control-id"]
        roles = {r["role-id"] for r in req["responsible-roles"]}
        assert roles == {"provider", "customer"}, req["control-id"]


def test_its_version_is_the_packages():
    # release-please bumps both (release-please-config.json extra-files).
    assert _component()["component-definition"]["metadata"]["version"] == neuralmind.__version__


def test_release_please_bumps_its_version():
    config = json.loads((ROOT / "release-please-config.json").read_text())
    extra = config["packages"]["."]["extra-files"]
    assert {
        "type": "json",
        "path": "security/neuralmind.oscal-component-definition.json",
        "jsonpath": "$['component-definition'].metadata.version",
    } in extra


def test_the_provider_is_the_entity_in_commercial_terms():
    entity = json.loads((ROOT / "commercial-terms.json").read_text())["entity"]
    (party,) = _component()["component-definition"]["metadata"]["parties"]
    assert party["name"] == entity["legal_name"]
    assert party["email-addresses"] == [entity["contact_email"]]


def _source() -> str:
    return "\n".join(p.read_text(encoding="utf-8") for p in (ROOT / "neuralmind").rglob("*.py"))


def test_every_setting_it_names_exists():
    text = COMPONENT.read_text(encoding="utf-8")
    settings = set(re.findall(r"security\.([a-z_]+)", text))
    assert settings, "expected the definition to name its settings"
    source = _source()
    missing = sorted(s for s in settings if f'"{s}"' not in source)
    assert not missing, f"security settings the code never reads: {missing}"


def _parses(argv: list[str]) -> bool:
    err = io.StringIO()
    with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
        try:
            cli.build_parser().parse_args(argv)
        except SystemExit:
            return "invalid choice" not in err.getvalue()
    return True


def test_every_command_it_names_exists():
    text = COMPONENT.read_text(encoding="utf-8")
    commands = set(re.findall(r"`neuralmind ([a-z-]+(?: [a-z-]+)?)", text))
    assert commands, "expected the definition to name its commands"
    unknown = sorted(c for c in commands if not _parses(c.split()))
    assert not unknown, f"commands the CLI doesn't have: {unknown}"


def test_the_docs_table_lists_the_same_controls():
    def label(control_id: str) -> str:
        family, _, rest = control_id.partition("-")
        base, _, enhancement = rest.partition(".")
        return f"{family.upper()}-{base}" + (f"({enhancement})" if enhancement else "")

    in_file = {label(req["control-id"]) for req in _requirements()}
    in_table = set(re.findall(r"^\| \*\*([A-Z]{2}-\d+(?:\(\d+\))?)\*\*", TABLE.read_text(), re.M))
    assert in_file == in_table, {
        "in the file only": sorted(in_file - in_table),
        "in the table only": sorted(in_table - in_file),
    }


@pytest.mark.parametrize("argv", [["audit", "verify"], ["no-such-command"]])
def test_the_command_check_itself(argv):
    assert _parses(argv) is (argv[0] != "no-such-command")
