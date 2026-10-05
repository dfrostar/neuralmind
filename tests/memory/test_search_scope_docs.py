"""The docs say exactly which decision fields search covers — side finding 7.

``docs/wiki/Memory-Layer.md`` said search covered "titles, rationales, and
evidence" while the FTS table indexed only title and rationale, and the MCP
tools called keyword search "natural language". This pins every place that
names the searched fields to the FTS table's real columns, in both
directions: when search starts indexing evidence and tags (spec §4.2, PR M),
these tests fail until the docs say so.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from neuralmind.memory.mcp_tools import TOOLS
from neuralmind.memory.store import DecisionRecord, DecisionStore

REPO = Path(__file__).resolve().parents[2]

# "search over titles and rationales" / "matched against decision titles
# and rationales" -> "titles and rationales"
# ", and " comes first in the alternation: with ", " first, "titles,
# rationales, and evidence" would end at "and" and drop "evidence".
_FIELD_LIST = re.compile(r"\b(?:over|against decision) (\w+(?:(?:, and |, | and )\w+)*)")


def _norm(name: str) -> str:
    """'Titles' / 'title' -> 'title'; 'tags' -> 'tag'."""
    return name.lower().rstrip("s")


# Every DecisionRecord field, so the list ends at the first word that isn't
# one ("titles and rationales, prefix-matched" stops before "prefix").
_RECORD_FIELDS = {_norm(name) for name in DecisionRecord.model_fields}


def _fields(text: str) -> set[str]:
    """The record fields named in the first "over …" / "against decision …" list."""
    match = _FIELD_LIST.search(text)
    assert match, f"no searched-field list found in: {text!r}"
    fields: set[str] = set()
    for word in re.split(r", and |, | and ", match.group(1)):
        if _norm(word) not in _RECORD_FIELDS:
            break
        fields.add(_norm(word))
    assert fields, f"the list after 'over' names no record field: {text!r}"
    return fields


@pytest.fixture(scope="module")
def indexed_fields(tmp_path_factory) -> set[str]:
    store = DecisionStore(str(tmp_path_factory.mktemp("scope")))
    with store._connect() as conn:
        columns = [row[1] for row in conn.execute("PRAGMA table_info(decisions_fts)")]
    if not columns:
        # The store supports such builds (LIKE fallback), but there are no
        # FTS columns to pin the docs to.
        pytest.skip("decisions_fts not created; FTS5 unavailable in this SQLite build")
    return {_norm(c) for c in columns if c != "id"}


def test_wiki_search_bullet_matches_fts_columns(indexed_fields):
    page = (REPO / "docs" / "wiki" / "Memory-Layer.md").read_text(encoding="utf-8")
    bullet = next(line for line in page.splitlines() if line.startswith("- **Search:**"))
    assert _fields(bullet) == indexed_fields


@pytest.mark.parametrize(
    "tool_name, where",
    [
        ("neuralmind_query_decisions", "description"),
        ("neuralmind_query_decisions", "query"),
        ("neuralmind_memory_search", "query"),
    ],
)
def test_tool_descriptions_match_fts_columns(indexed_fields, tool_name, where):
    tool = next(t for t in TOOLS if t["name"] == tool_name)
    text = (
        tool["description"]
        if where == "description"
        else tool["inputSchema"]["properties"][where]["description"]
    )
    assert _fields(text) == indexed_fields
    assert "natural language" not in text.lower()


def test_like_fallback_searches_the_same_fields(tmp_path, monkeypatch, indexed_fields):
    """Without FTS5 the LIKE scan must cover the same fields, no more."""
    import neuralmind.memory.store as store_mod

    monkeypatch.setattr(store_mod, "_fts_available", lambda conn: False)
    store = DecisionStore(str(tmp_path))
    rec = store.record(
        title="Zebra title",
        rationale="Quokka rationale",
        commit_sha="a" * 40,
        evidence=["Narwhal evidence"],
        tags=["axolotl"],
    )
    probes = {"title": "Zebra", "rationale": "Quokka", "evidence": "Narwhal", "tag": "axolotl"}
    found = {
        field for field, word in probes.items() if [d.id for d in store.query(word)] == [rec.id]
    }
    assert found == indexed_fields


def test_semantic_search_embeds_the_same_fields(tmp_path, indexed_fields):
    """Semantic and hybrid search embed the fields keyword search indexes, so
    the docs' one list of searched fields holds in every mode."""
    from neuralmind.memory.semantic import decision_text

    from .test_semantic_search import ConceptEmbedder

    probes = {"title": "Zebra", "rationale": "Quokka", "evidence": "Narwhal", "tag": "axolotl"}
    fake = ConceptEmbedder({word: {word.lower()} for word in probes.values()})
    store = DecisionStore(str(tmp_path), embedder=fake.embedder)
    rec = store.record(
        title="Zebra title",
        rationale="Quokka rationale",
        commit_sha="a" * 40,
        evidence=["Narwhal evidence"],
        tags=["axolotl"],
    )
    found = {
        field
        for field, word in probes.items()
        if [d.id for d in store.query(word, mode="semantic")] == [rec.id]
    }
    assert found == indexed_fields
    assert decision_text(rec.title, rec.rationale) == f"{rec.title}\n{rec.rationale}"
