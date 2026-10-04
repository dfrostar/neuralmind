"""Decision search: any query word can match, and better matches rank first.

Search used to require every word of the query (FTS5 reads space-separated
terms as AND), so ``store.query("sqlite wal")`` found a decision titled "Use
SQLite WAL for synapses" while ``store.query("how do we handle sqlite wal")``
returned nothing, and agents send questions. Each test runs on the FTS5 path
and on the LIKE fallback used when SQLite lacks FTS5.
"""

from __future__ import annotations

import pytest

import neuralmind.memory.store as store_mod
from neuralmind.memory.store import DecisionStore, _search_terms


@pytest.fixture(params=["fts5", "like"])
def store(request, tmp_path, monkeypatch):
    if request.param == "like":
        monkeypatch.setattr(store_mod, "_fts_available", lambda conn: False)
    return DecisionStore(str(tmp_path))


def _record(store, title, rationale="No further detail."):
    return store.record(title=title, rationale=rationale, commit_sha="a" * 40)


def test_a_question_finds_what_its_keywords_find(store):
    rec = _record(store, "Use SQLite WAL for synapses")
    assert [d.id for d in store.query("sqlite wal")] == [rec.id]
    assert [d.id for d in store.query("how do we handle sqlite wal")] == [rec.id]


def test_exact_title_ranks_first_among_overlapping_decisions(store):
    target = _record(store, "Use SQLite WAL for synapses", "Concurrent readers need WAL.")
    _record(
        store,
        "Pin SQLite to 3.35 for WAL mode support",
        "WAL mode needs SQLite 3.35, and the synapse store relies on WAL.",
    )
    _record(store, "Use SQLite for the synapse store", "One file and no server to run.")
    _record(store, "Checkpoint the WAL on shutdown", "Keeps the WAL file small.")
    hits = store.query("Use SQLite WAL for synapses")
    assert hits[0].id == target.id
    assert len(hits) == 4


def test_decisions_matching_more_words_rank_first(store):
    one = _record(store, "Tune the WAL checkpoint interval")
    three = _record(store, "Pool connections for the WAL database")
    hits = store.query("why do we pool wal connections?")
    assert [d.id for d in hits] == [three.id, one.id]


def test_stopwords_match_nothing(store):
    # "we" is a prefix of both words; under any-word matching it would hit.
    _record(store, "Weights decay weekly", "Unused edges fade.")
    assert store.query("how do we handle sqlite?") == []


def test_like_fallback_matches_underscore_literally(tmp_path, monkeypatch):
    monkeypatch.setattr(store_mod, "_fts_available", lambda conn: False)
    store = DecisionStore(str(tmp_path))
    rec = _record(store, "Use json_each for overlap queries")
    _record(store, "Parse jsonXeach records")  # "_" is a LIKE wildcard unless escaped
    assert [d.id for d in store.query("json_each")] == [rec.id]


def test_search_terms_drop_stopwords_and_contraction_fragments():
    # "what's" and "don't" split into "what" + "s" and "don" + "t"; as
    # prefixes, "s" and "t" would match every word starting with them.
    assert _search_terms("What's the SQLite WAL setting? Don't guess, don't.") == [
        "sqlite",
        "wal",
        "setting",
        "guess",
    ]


def test_a_query_of_only_stopwords_still_searches():
    assert _search_terms("how do we") == ["how", "do", "we"]
