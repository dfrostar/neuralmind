"""The decision-search eval set, its harness, and the numbers the wiki quotes.

``tests/memory/fixtures/decision_queries.json`` holds agent-style questions
with gold decision ids. ``neuralmind decisions eval --queries <that file>``
scores search against them, and docs/wiki/Memory-Layer.md quotes the result:
``test_wiki_quotes_the_measured_numbers`` fails when search changes until the
page does.
"""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

import pytest

import neuralmind.memory.store as store_mod
from neuralmind.cli import build_parser
from neuralmind.memory.eval import (
    TITLE_KIND,
    MaintenanceEval,
    QuerySetEval,
    load_query_set,
)
from neuralmind.memory.store import DecisionStore, _search_terms

FIXTURE = Path(__file__).parent / "fixtures" / "decision_queries.json"
WIKI = Path(__file__).resolve().parents[2] / "docs" / "wiki" / "Memory-Layer.md"


def _sqlite_has_fts5() -> bool:
    """Whether this SQLite build can create the decision store's FTS5 table."""
    conn = sqlite3.connect(":memory:")
    try:
        conn.executescript(store_mod.FTS_SCHEMA)
        return True
    except sqlite3.OperationalError:
        return False
    finally:
        conn.close()


# Without FTS5 the store falls back to LIKE, which ranks differently; the
# wiki's table quotes FTS5 numbers (its LIKE row is measured separately).
requires_fts5 = pytest.mark.skipif(
    not _sqlite_has_fts5(), reason="SQLite built without FTS5; the wiki quotes FTS5 numbers"
)


def _summary(monkeypatch=None, *, like=False):
    if like:
        monkeypatch.setattr(store_mod, "_fts_available", lambda conn: False)
    harness = QuerySetEval(load_query_set(FIXTURE))
    return harness.summarize(harness.outcomes())


@pytest.fixture(scope="module")
def summary():
    return _summary()


def test_every_gold_id_is_an_active_decision():
    QuerySetEval(load_query_set(FIXTURE))  # raises ValueError otherwise


def test_paraphrases_share_no_search_word_with_their_answer():
    """A paraphrase is only a paraphrase if keyword search can't reach it.

    Keyword search prefix-matches each query term against the words of a
    decision's title and rationale, so no term of a paraphrase query may
    begin any of those words in a gold decision.
    """
    harness = QuerySetEval(load_query_set(FIXTURE))
    by_id = {d["id"]: d for d in harness.corpus}
    paraphrases = [q for q in harness.queries if q["kind"] == "paraphrase"]
    assert paraphrases
    shared = {}
    for q in paraphrases:
        for gold in q["gold"]:
            words = re.findall(
                r"[a-z0-9]+", f"{by_id[gold]['title']} {by_id[gold]['rationale']}".lower()
            )
            hits = [
                term
                for term in _search_terms(q["query"])
                for part in re.findall(r"[a-z0-9]+", term)
                if any(word.startswith(part) for word in words)
            ]
            if hits:
                shared[q["id"]] = hits
    assert not shared, f"paraphrase queries share search words with their answers: {shared}"


def test_unknown_gold_id_is_rejected():
    query_set = load_query_set(FIXTURE)
    query_set["queries"] = [
        {"id": "typo", "kind": "sentence", "query": "sqlite", "gold": ["dec-no-such-id"]}
    ]
    with pytest.raises(ValueError, match="dec-no-such-id"):
        QuerySetEval(query_set)


@pytest.mark.parametrize("like", [False, True], ids=["fts5", "like"])
def test_exact_titles_rank_first(monkeypatch, like):
    titles = _summary(monkeypatch, like=like)[TITLE_KIND]
    assert titles["queries"] == 30
    assert titles["not_ranked_first"] == []


def test_sentence_queries_find_their_answers(summary):
    sentences = summary["sentence"]
    assert sentences["returned_nothing"] == 0
    assert sentences["recall"]["mean"] >= 0.9


@requires_fts5
def test_wiki_quotes_the_measured_numbers(summary, monkeypatch):
    """Each row of the wiki's eval table is what the eval measures now."""

    def spread(s):
        return f"{s['mean']:.2f} ({s['min']:.2f}–{s['max']:.2f})"

    sentences, titles, negatives = summary["sentence"], summary[TITLE_KIND], summary["negative"]
    n = sentences["queries"]
    first = titles["queries"] - len(titles["not_ranked_first"])
    maintenance = json.loads(MaintenanceEval(".", task_count=5).run())["memory_on"]["aggregate"]
    like = _summary(monkeypatch, like=True)["sentence"]
    rows = [
        f"| Recall@5 on {n} questions, mean (range) | {spread(sentences['recall'])} |",
        f"| MRR on {n} questions, mean (range) | {spread(sentences['mrr'])} |",
        f"| Exact titles ranked first | {first} of {titles['queries']} |",
        (
            "| Questions nothing answers that still return decisions | "
            f"{len(negatives['false_positives'])} of {negatives['queries']} |"
        ),
        f"| Recall@5 without FTS5 (LIKE fallback), mean (range) | {spread(like['recall'])} |",
        (
            "| Maintenance tasks, recall / precision at limit 10 | "
            f"{maintenance['recall_rate']:.0%} / {maintenance['precision']:.0%} |"
        ),
    ]
    page = WIKI.read_text(encoding="utf-8")
    missing = [row for row in rows if row not in page]
    assert not missing, "Memory-Layer.md's eval table is out of date; measured:\n" + "\n".join(
        missing
    )


# ------------------------------------------------------------------ #
# The harness leaves the project alone
# ------------------------------------------------------------------ #


def test_evals_never_touch_the_project_store(tmp_path):
    """Both evals used to share the project's memory.db; the maintenance
    eval deleted it and left its synthetic decisions behind."""
    real = DecisionStore(str(tmp_path)).record(
        title="A real decision", rationale="Keep me.", commit_sha="a" * 40
    )
    MaintenanceEval(str(tmp_path), task_count=5).run()
    QuerySetEval(load_query_set(FIXTURE)).run()
    remaining = DecisionStore(str(tmp_path)).list_all(status=None)
    assert [d.id for d in remaining] == [real.id]


def test_cli_eval_markdown_and_query_set(tmp_path, capsys):
    """`--format md` used to raise ValueError ("md" vs "markdown")."""
    parser = build_parser()
    for argv in (
        ["decisions", "eval", str(tmp_path), "--format", "md"],
        ["decisions", "eval", "--queries", str(FIXTURE), "--format", "md"],
    ):
        args = parser.parse_args(argv)
        args.func(args)
    out = capsys.readouterr().out
    assert "# Maintenance Eval Benchmark Report" in out
    assert "# Decision Query Eval" in out
    assert not (tmp_path / ".neuralmind").exists()
