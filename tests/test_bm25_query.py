"""BM25 query handling: stopwords and the inverted index. Stdlib-only."""

from __future__ import annotations

import math
import random

from neuralmind.bm25 import BM25Index


def _index(docs: dict[str, str]) -> BM25Index:
    idx = BM25Index()
    idx.add_documents(list(docs), list(docs.values()))
    idx.build()
    return idx


def _brute_force(idx: BM25Index, terms: list[str]) -> dict[str, float]:
    """The scan the inverted index replaced, for an equivalence check."""
    scores: dict[str, float] = {}
    for term in terms:
        if term not in idx._idf:
            continue
        for i, tf_map in enumerate(idx._tf):
            tf = tf_map.get(term, 0)
            if not tf:
                continue
            sub = 1 + math.log(tf)
            denom = sub + idx.k1 * (1 - idx.b + idx.b * idx._dl[i] / idx._avgdl)
            scores[idx._ids[i]] = (
                scores.get(idx._ids[i], 0.0) + idx._idf[term] * sub * (idx.k1 + 1) / denom
            )
    return scores


def test_inverted_index_scores_match_a_full_scan():
    rng = random.Random(7)
    vocab = "session cookie adapter request header auth token parse url retry".split()
    docs = {
        f"d{i}": " ".join(rng.choice(vocab) for _ in range(rng.randint(1, 30))) for i in range(200)
    }
    idx = _index(docs)
    query = "cookie retry header"
    expected = _brute_force(idx, ["cookie", "retry", "header"])
    got = {r["id"]: r["_bm25_raw"] for r in idx.search(query, top_k=len(docs))}
    assert got.keys() == expected.keys()
    for doc_id, score in expected.items():
        assert math.isclose(got[doc_id], score, rel_tol=1e-12)


def test_question_words_do_not_outvote_the_term_that_names_the_answer():
    # click's echo-util miss: "Aborts … error message" won on "the/message/program".
    idx = _index(
        {
            "abort": "the program of the user is aborted with the error",
            "echo": "echo prints text",
            "other": "unrelated words here",
        }
    )
    hits = idx.search("how does the echo of the user work", top_k=3)
    assert hits[0]["id"] == "echo"
    # Sharing only "of" and "the" with the query no longer lists a document.
    assert [h["id"] for h in idx.search("echo of the", top_k=3)] == ["echo"]


def test_a_query_of_only_stopwords_still_matches():
    idx = _index({"a": "how to do it", "b": "something else entirely"})
    assert [h["id"] for h in idx.search("how to", top_k=2)] == ["a"]


def test_adding_documents_after_a_search_is_seen():
    idx = _index({"a": "alpha"})
    assert idx.search("beta") == []
    idx.add_documents(["b"], ["beta"])
    idx.build()
    assert [h["id"] for h in idx.search("beta")] == ["b"]
