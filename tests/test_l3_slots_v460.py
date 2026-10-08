"""v4.6.0 spec 7: how the four L3 slots are spent.

Each work item is behind a flag. These tests pin what each pass does on its
own, that the default path (no flags) is unchanged, and the four regression
shapes that sent "how does X work" questions to the docs.
"""

from __future__ import annotations

from collections import Counter

import pytest

from neuralmind import l3_slots
from neuralmind.context_selector import ContextSelector
from neuralmind.retrieval_enhancement import classify_behaviour_intent

FLAGS = (
    "NEURALMIND_L3_PER_FILE",
    "NEURALMIND_DOC_HANDOFF",
    "NEURALMIND_HUB_DAMPEN",
    "NEURALMIND_BM25_CODE",
    "NEURALMIND_INTENT_RULES",
    "NEURALMIND_BM25",
    "NEURALMIND_BM25_UNIFIED",
    "NEURALMIND_INTENT_POOL",
    "NEURALMIND_L3_ROLES",
)


@pytest.fixture(autouse=True)
def _clean_flags(monkeypatch):
    for name in FLAGS:
        monkeypatch.delenv(name, raising=False)


def hit(nid, sf, score, file_type="code", label=None, document=""):
    return {
        "id": nid,
        "document": document,
        "score": score,
        "metadata": {
            "label": label or nid,
            "file_type": file_type,
            "source_file": sf,
            "node_id": nid,
        },
    }


def node(nid, sf, file_type="code", label=None, document=""):
    return {
        "id": nid,
        "label": label or nid,
        "content_text": document,
        "metadata": {"label": label or nid, "file_type": file_type, "source_file": sf},
    }


class StubEmbedder:
    """Fixed ranked search results; no BM25; a node catalog for hand-offs."""

    def __init__(self, project, ranked, nodes=()):
        self.project_path = str(project)
        self._ranked = ranked
        self._nodes = list(nodes)

    def search(self, query, n=5, **_):
        return [dict(h, metadata=dict(h["metadata"])) for h in self._ranked[:n]]

    def bm25_search(self, query, n=10):
        return []

    def get_all_nodes(self):
        return list(self._nodes)


def files_of(selector):
    return [h["metadata"]["source_file"] for h in selector._last_l3_boosted]


# --------------------------------------------------------------------------- #
# Default path
# --------------------------------------------------------------------------- #
RANKED = [
    hit("a1", "app/a.py", 0.9),
    hit("a2", "app/a.py", 0.8),
    hit("a3", "app/a.py", 0.7),
    hit("b1", "app/b.py", 0.6),
    hit("c1", "app/c.py", 0.5),
    hit("d1", "app/d.py", 0.4),
]


def test_no_flags_means_no_slot_pass(tmp_path, monkeypatch):
    called = []
    monkeypatch.setattr(ContextSelector, "_spend_l3_slots", lambda *a, **k: called.append(1))
    sel = ContextSelector(StubEmbedder(tmp_path, RANKED), str(tmp_path))
    sel.get_l3_search("where is a handled")
    assert not called
    assert files_of(sel) == ["app/a.py", "app/a.py", "app/a.py", "app/b.py"]


def test_flags_off_by_default():
    assert l3_slots.per_file_cap() == 0
    assert not l3_slots.any_slot_pass_enabled()
    assert not l3_slots.code_bm25_enabled()
    assert l3_slots.unified_bm25_enabled()  # the one item the eval kept (v4.6.0)


# --------------------------------------------------------------------------- #
# Item 1: per-file cap
# --------------------------------------------------------------------------- #
def test_per_file_cap_refills_from_the_same_search(tmp_path, monkeypatch):
    monkeypatch.setenv("NEURALMIND_L3_PER_FILE", "2")
    sel = ContextSelector(StubEmbedder(tmp_path, RANKED), str(tmp_path))
    sel.get_l3_search("where is a handled")
    files = files_of(sel)
    assert Counter(files)["app/a.py"] == 2
    assert files == ["app/a.py", "app/a.py", "app/b.py", "app/c.py"]


def test_cap_still_fills_slots_when_only_one_file_matches():
    one_file = [hit(f"a{i}", "app/a.py", 1 - i / 10) for i in range(4)]
    assert len(l3_slots.allocate(one_file, 4, 2)) == 4


def test_spend_keeps_hits_no_pass_vacated():
    originals = [hit("a1", "a.py", 0.9), hit("b1", "b.py", 0.3)]
    refill = [hit("c1", "c.py", 0.8)]  # scores higher than b1, but b1 earned its slot
    out = l3_slots.spend(originals, refill, 2, cap=0)
    assert [h["id"] for h in out] == ["a1", "b1"]


# --------------------------------------------------------------------------- #
# Item 2: doc-to-code hand-off
# --------------------------------------------------------------------------- #
def test_mentions_find_paths_and_identifiers():
    paths, idents = l3_slots.mentions(
        "The rule lives in `app/billing.py`; see `apply_discount()` and RetryPolicy."
    )
    assert paths == ["app/billing.py"]
    assert "apply_discount" in idents and "RetryPolicy" in idents


def test_doc_hit_hands_off_to_the_code_it_names(tmp_path, monkeypatch):
    monkeypatch.setenv("NEURALMIND_DOC_HANDOFF", "1")
    ranked = [
        hit(
            "doc1", "docs/billing.md", 0.9, "document", document="Refunds run in `app/refunds.py`."
        ),
        hit("x1", "app/x.py", 0.8),
        hit("y1", "app/y.py", 0.7),
        hit("z1", "app/z.py", 0.6),
    ]
    nodes = [
        node("refunds", "app/refunds.py", label="refunds.py"),
        node("issue_refund", "app/refunds.py", label="issue_refund()"),
        node("void_card", "app/refunds.py", label="void_card()"),
    ]
    sel = ContextSelector(StubEmbedder(tmp_path, ranked, nodes), str(tmp_path))
    sel.get_l3_search("how are refunds issued")
    hits = sel._last_l3_boosted
    handed = [h for h in hits if h.get("_handoff_from") == "doc1"]
    assert [h["id"] for h in handed] == ["issue_refund"]
    assert handed[0]["score"] == pytest.approx(0.9 * l3_slots.HANDOFF_FACTOR)
    assert "app/z.py" not in files_of(sel)  # the weakest hit made room


def test_hand_off_skips_files_already_in_the_answer():
    catalog = l3_slots.NodeCatalog([node("f", "app/refunds.py", label="issue_refund()")])
    hits = [
        hit("doc", "docs/a.md", 0.9, "document", document="see app/refunds.py"),
        hit("r", "app/refunds.py", 0.8),
    ]
    assert l3_slots.handoff_candidates(hits, "refunds", catalog) == []


# --------------------------------------------------------------------------- #
# Item 3: hub dampening
# --------------------------------------------------------------------------- #
def test_hub_is_relative_to_chance():
    # 40 files, 4 per answer: a file gets ~10% by chance; the wiki is in all.
    answers = [{"docs/WIKI.md", f"m{i}.py", f"n{i}.py", f"o{i}.py"} for i in range(30)]
    stats = l3_slots.HubStats(answers, "query log", n_files=40)
    assert stats.factor("docs/WIKI.md") < 1.0
    assert stats.factor("docs/WIKI.md") >= l3_slots.HUB_FLOOR
    assert stats.factor("m3.py") == 1.0


def test_small_repo_is_not_all_hubs():
    # 6 files, 4 per answer: every file is in ~2/3 of answers by chance.
    files = [f"f{i}.py" for i in range(6)]
    answers = [set(files[i % 6 : i % 6 + 4]) | set(files[: max(0, i % 6 - 2)]) for i in range(30)]
    stats = l3_slots.HubStats(answers, "query log", n_files=6)
    assert stats.hubs() == []


def test_hub_dampening_lets_a_refill_take_the_slot(tmp_path, monkeypatch):
    monkeypatch.setenv("NEURALMIND_HUB_DAMPEN", "1")
    log = tmp_path / ".neuralmind" / "recent_queries.jsonl"
    log.parent.mkdir()
    import json

    lines = [
        json.dumps({"top_hits": [{"source_file": "docs/WIKI.md"}, {"source_file": f"m{i}.py"}]})
        for i in range(40)
    ]
    log.write_text("\n".join(lines) + "\n", encoding="utf-8")
    ranked = [
        hit("w", "docs/WIKI.md", 0.9, "document"),
        hit("a", "app/a.py", 0.85),
        hit("b", "app/b.py", 0.8),
        hit("c", "app/c.py", 0.75),
        hit("d", "app/d.py", 0.7),
    ]
    nodes = [node(f"m{i}", f"m{i}.py") for i in range(40)]
    sel = ContextSelector(StubEmbedder(tmp_path, ranked, nodes), str(tmp_path))
    sel.get_l3_search("order total")
    assert "docs/WIKI.md" not in files_of(sel)
    assert "app/d.py" in files_of(sel)


# --------------------------------------------------------------------------- #
# Item 4: intent
# --------------------------------------------------------------------------- #
# Question shapes the old classifier sent to the docs: each asks how the
# project behaves, so the implementation should outrank the docs.
REGRESSION_SHAPES = [
    "How does the session pick which adapter sends a request?",
    "Where is the redirect followed after a POST?",
    "Which hook runs before a request is sent?",
    "How does the cache avoid storing the same response twice?",
]


@pytest.mark.parametrize("question", REGRESSION_SHAPES)
def test_behaviour_questions_are_code(question):
    assert classify_behaviour_intent(question) == "code"


@pytest.mark.parametrize(
    "question",
    [
        "How do I install the hooks for Cursor?",
        "What does the README say about pricing?",
        "Where is the upgrade guide?",
    ],
)
def test_doc_and_setup_questions_are_docs(question):
    assert classify_behaviour_intent(question) == "docs"


def test_rules_are_behind_their_flag(tmp_path, monkeypatch):
    sel = ContextSelector(StubEmbedder(tmp_path, RANKED), str(tmp_path))
    q = REGRESSION_SHAPES[0]
    before = sel._resolve_intent(q)
    monkeypatch.setenv("NEURALMIND_INTENT_RULES", "1")
    assert sel._resolve_intent(q) == "code"
    assert sel._last_intent_source == "question shape"
    assert before == "docs"  # what v4.5 does with this shape


def test_docstrings_count_as_code_under_the_rules(tmp_path, monkeypatch):
    monkeypatch.setenv("NEURALMIND_INTENT_RULES", "1")
    sel = ContextSelector(StubEmbedder(tmp_path, []), str(tmp_path))
    docstring = hit("r", "app/orders.py", 1.0, "rationale")
    readme = hit("m", "README.md", 1.0, "document")
    out = {h["id"]: h["score"] for h in sel._apply_intent_boost([docstring, readme], "code")}
    assert out["r"] > out["m"]


def test_intent_is_reported_on_the_result(tmp_path, monkeypatch):
    monkeypatch.setenv("NEURALMIND_INTENT_RULES", "1")
    sel = ContextSelector(StubEmbedder(tmp_path, RANKED), str(tmp_path))
    result = sel.get_context(REGRESSION_SHAPES[1], include_l0=False, include_l1=False)
    assert result.intent == "code"
    assert result.intent_source == "question shape"


# --------------------------------------------------------------------------- #
# Item 5: symbol-name lexical pass
# --------------------------------------------------------------------------- #
def test_code_bm25_indexes_symbols_and_docstrings(tmp_path):
    (tmp_path / ".neuralmind").mkdir()
    catalog = l3_slots.NodeCatalog(
        [
            node("p", "app/billing.py", label="apply_discount()"),
            node("r", "app/comments.py", "rationale", label="Pin the creator's comment."),
            node("d", "docs/x.md", "document", label="Comments"),
        ]
    )
    idx = l3_slots.code_bm25_index(tmp_path, catalog)
    ids = [r["id"] for r in idx.search("apply discount", top_k=5)]
    assert ids[0] == "p"
    assert "d" not in ids  # docs stay in the document index


def test_code_bm25_joins_the_fusion_only_when_flagged(tmp_path, monkeypatch):
    (tmp_path / ".neuralmind").mkdir()
    ranked = [hit("doc", "docs/a.md", 0.9, "document"), hit("x", "app/x.py", 0.8)]
    nodes = [node("p", "app/billing.py", label="apply_discount()")]
    sel = ContextSelector(StubEmbedder(tmp_path, ranked, nodes), str(tmp_path))
    assert "p" not in [h["id"] for h in sel._fetch_search("apply discount", 4)]
    monkeypatch.setenv("NEURALMIND_BM25_CODE", "1")
    sel = ContextSelector(StubEmbedder(tmp_path, ranked, nodes), str(tmp_path))
    assert "p" in [h["id"] for h in sel._fetch_search("apply discount", 4)]


# --------------------------------------------------------------------------- #
# Round-2 variants
# --------------------------------------------------------------------------- #
def test_unified_bm25_holds_docs_and_code(tmp_path):
    (tmp_path / ".neuralmind").mkdir()
    catalog = l3_slots.NodeCatalog(
        [
            node("p", "app/billing.py", label="apply_discount()"),
            node("d", "docs/x.md", "document", label="Discounts", document="discount rules"),
        ]
    )
    assert l3_slots.unified_bm25_index(tmp_path, catalog) is None  # a query never builds it
    idx = l3_slots.unified_bm25_index(tmp_path, catalog, rebuild=True)
    ids = {r["id"] for r in idx.search("apply discount", top_k=5)}
    assert ids == {"p", "d"}


def test_unified_bm25_replaces_the_docs_only_list(tmp_path, monkeypatch):
    (tmp_path / ".neuralmind").mkdir()
    ranked = [hit("v", "app/v.py", 0.9)]
    nodes = [node("p", "app/billing.py", label="apply_discount()")]
    emb = StubEmbedder(tmp_path, ranked, nodes)
    emb.bm25_search = lambda q, n=10: [hit("docs-only", "docs/x.md", 1.0, "document")]
    # No unified index written yet (an index built before v4.6): the old list.
    sel = ContextSelector(emb, str(tmp_path))
    assert "docs-only" in [h["id"] for h in sel._fetch_search("apply discount", 4)]
    l3_slots.unified_bm25_index(tmp_path, l3_slots.NodeCatalog(nodes), rebuild=True)
    sel = ContextSelector(emb, str(tmp_path))
    ids = [h["id"] for h in sel._fetch_search("apply discount", 4)]
    assert "p" in ids and "docs-only" not in ids
    monkeypatch.setenv("NEURALMIND_BM25_UNIFIED", "0")  # v4.5 behaviour on request
    sel = ContextSelector(emb, str(tmp_path))
    assert "docs-only" in [h["id"] for h in sel._fetch_search("apply discount", 4)]


def test_intent_pool_promotes_a_code_hit_below_the_top_four(tmp_path, monkeypatch):
    ranked = [hit(f"doc{i}", f"docs/{i}.md", 0.9 - i / 100, "document") for i in range(4)]
    ranked.append(hit("impl", "app/orders.py", 0.8))
    monkeypatch.setenv("NEURALMIND_INTENT_RULES", "1")
    # Since v4.11.0 the roles pass gives the code a slot here on its own
    # (tests/test_l3_roles.py); this pins what the intent pool flag does.
    monkeypatch.setenv("NEURALMIND_L3_ROLES", "0")
    sel = ContextSelector(StubEmbedder(tmp_path, ranked), str(tmp_path))
    sel.get_l3_search(REGRESSION_SHAPES[0])
    assert "app/orders.py" not in files_of(sel)  # intent alone only re-orders the top four
    monkeypatch.setenv("NEURALMIND_INTENT_POOL", "1")
    sel = ContextSelector(StubEmbedder(tmp_path, ranked), str(tmp_path))
    sel.get_l3_search(REGRESSION_SHAPES[0])
    assert files_of(sel)[0] == "app/orders.py"
