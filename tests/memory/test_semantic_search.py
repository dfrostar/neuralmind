"""Semantic and hybrid decision search (spec LOCAL-API-SPEC.md §4.1, G1).

A deterministic concept embedder stands in for the MiniLM model: each vector
counts a text's words per concept, and every other word is ignored. So the
tests need neither onnxruntime nor the model on disk, and a question can
share a concept with a decision without sharing a word, which is exactly
what keyword search can't follow.
"""

from __future__ import annotations

import json
import re
import struct

import pytest

from neuralmind.cli import build_parser
from neuralmind.memory import mcp_tools, semantic
from neuralmind.memory.eval import QuerySetEval, load_query_set
from neuralmind.memory.semantic import DecisionEmbedder, SemanticSearchUnavailableError
from neuralmind.memory.store import DecisionStore

from .test_query_eval import FIXTURE

SHA = "a" * 40

CONCEPTS = {
    "auth": {"authenticate", "authentication", "middleware", "handler", "verify", "calling"},
    "logs": {"log", "logging", "level", "verbose", "production"},
    "storage": {"sqlite", "wal", "pooling", "connections", "handles"},
}

# Shares no word with the auth decision; shares its concept.
QUESTION = "where do we verify who is calling an endpoint?"


class ConceptEmbedder:
    """Counts each concept's words in a text; records every text it embeds."""

    def __init__(self, concepts=CONCEPTS, model_id="concept-v1"):
        self.concepts = list(concepts.values())
        self.calls: list[list[str]] = []
        self.embedder = DecisionEmbedder(model_id=model_id, embed=self._embed)

    def _embed(self, texts):
        self.calls.append(list(texts))
        rows = []
        for text in texts:
            words = re.findall(r"[a-z]+", text.lower())
            rows.append([float(sum(w in vocab for w in words)) for vocab in self.concepts])
        return rows


def _unavailable(*_args, **_kwargs):
    raise SemanticSearchUnavailableError("no model here")


def _seed(store: DecisionStore) -> None:
    store.record(
        id="auth",
        title="Use per-handler authentication middleware",
        rationale="Each API handler must authenticate via the shared middleware.",
        commit_sha=SHA,
    )
    store.record(
        id="logs",
        title="Set log level to INFO in production",
        rationale="INFO keeps log volume manageable.",
        commit_sha=SHA,
    )
    store.record(
        id="ci",
        title="Run the test matrix on three Python versions",
        rationale="Version-specific failures surface before a release.",
        commit_sha=SHA,
    )


@pytest.fixture
def fake():
    return ConceptEmbedder()


@pytest.fixture
def store(tmp_path, fake):
    s = DecisionStore(str(tmp_path), embedder=fake.embedder)
    _seed(s)
    return s


def _ids(records) -> list[str]:
    return [r.id for r in records]


def _vector_rows(store: DecisionStore) -> list[tuple[str, str]]:
    with store._connect() as conn:
        return sorted(conn.execute("SELECT decision_id, model_id FROM decision_vectors").fetchall())


# ------------------------------------------------------------------ #
# Modes
# ------------------------------------------------------------------ #


def test_semantic_finds_a_decision_that_shares_no_word(store):
    assert store.query(QUESTION, mode="keyword") == []
    found = store.search(QUESTION, mode="semantic")
    assert (found.mode, found.requested, found.notice) == ("semantic", "semantic", None)
    assert _ids(found.records) == ["auth"]


def test_semantic_leaves_out_decisions_below_the_floor(store):
    """Nothing near the question is not a reason to return the nearest anyway."""
    assert store.query("what colour is the company logo?", mode="semantic") == []


def test_hybrid_fuses_both_rankings(store):
    """auth: both lists; ci: keyword only ("matrix"); logs: semantic only
    ("verbose" shares its concept, no word). Found by both ranks first; the
    two found once tie, and the keyword hit wins the tie."""
    question = "authenticate handler verbose matrix"
    assert _ids(store.query(question, mode="keyword")) == ["auth", "ci"]
    assert _ids(store.query(question, mode="semantic")) == ["auth", "logs"]
    found = store.search(question, mode="hybrid")
    assert found.mode == "hybrid"
    assert _ids(found.records) == ["auth", "ci", "logs"]
    assert _ids(store.query(question, mode="hybrid", limit=1)) == ["auth"]


def test_modes_are_case_insensitive_and_unknown_ones_rejected(store):
    assert store.search(QUESTION, mode="SEMANTIC").mode == "semantic"
    with pytest.raises(ValueError, match="unknown search mode"):
        store.search(QUESTION, mode="fuzzy")


# ------------------------------------------------------------------ #
# Default mode
# ------------------------------------------------------------------ #


def test_default_mode_is_hybrid(store, monkeypatch):
    monkeypatch.delenv(semantic.MODE_ENV, raising=False)
    found = store.search(QUESTION)
    assert (found.requested, found.mode) == ("hybrid", "hybrid")
    assert _ids(found.records) == ["auth"]


def test_environment_sets_the_default_and_an_argument_overrides_it(store, monkeypatch):
    monkeypatch.setenv(semantic.MODE_ENV, "Semantic")
    assert store.search(QUESTION).requested == "semantic"
    assert store.search(QUESTION, mode="keyword").requested == "keyword"


def test_unknown_environment_value_is_ignored(store, monkeypatch, caplog):
    monkeypatch.setenv(semantic.MODE_ENV, "fuzzy")
    assert store.search(QUESTION).requested == semantic.DEFAULT_MODE
    assert "ignoring NEURALMIND_DECISION_SEARCH" in caplog.text


# ------------------------------------------------------------------ #
# When semantic ranking can't run
# ------------------------------------------------------------------ #


@pytest.fixture
def store_without_model(tmp_path, monkeypatch):
    monkeypatch.setattr(semantic, "load_default_embedder", _unavailable)
    s = DecisionStore(str(tmp_path))
    _seed(s)
    return s


def test_hybrid_falls_back_to_keyword_and_says_so(store_without_model):
    found = store_without_model.search("authentication middleware", mode="hybrid")
    assert (found.requested, found.mode) == ("hybrid", "keyword")
    assert "no model here" in found.notice
    assert _ids(found.records) == ["auth"]


def test_semantic_mode_raises_instead_of_answering_with_keywords(store_without_model):
    with pytest.raises(SemanticSearchUnavailableError, match="no model here"):
        store_without_model.search(QUESTION, mode="semantic")
    with pytest.raises(SemanticSearchUnavailableError):
        store_without_model.query(QUESTION, mode="semantic")


def test_an_embedding_failure_falls_back_too(tmp_path):
    def broken(texts):
        raise RuntimeError("onnx exploded")

    s = DecisionStore(str(tmp_path), embedder=DecisionEmbedder("broken", broken))
    _seed(s)
    found = s.search("authentication", mode="hybrid")
    assert found.mode == "keyword"
    assert "embedding failed: onnx exploded" in found.notice
    with pytest.raises(SemanticSearchUnavailableError, match="onnx exploded"):
        s.search("authentication", mode="semantic")


def test_search_never_downloads_the_model(monkeypatch):
    from neuralmind.onnx_embedder import OnnxMiniLMEmbedder

    def no_network(*_args):
        raise AssertionError("decision search must not download the model")

    monkeypatch.setattr(semantic.importlib.util, "find_spec", lambda name: object())
    monkeypatch.setattr(OnnxMiniLMEmbedder, "local_model_dir", lambda self: None)
    monkeypatch.setattr(OnnxMiniLMEmbedder, "_download_into", no_network)
    with pytest.raises(SemanticSearchUnavailableError, match="neuralmind build"):
        semantic.load_default_embedder()


def test_a_missing_runtime_is_named(monkeypatch):
    real = semantic.importlib.util.find_spec
    monkeypatch.setattr(
        semantic.importlib.util,
        "find_spec",
        lambda name: None if name == "onnxruntime" else real(name),
    )
    with pytest.raises(SemanticSearchUnavailableError, match="onnxruntime not installed"):
        semantic.load_default_embedder()


# ------------------------------------------------------------------ #
# The vector cache
# ------------------------------------------------------------------ #


def test_vectors_are_computed_once_then_reused(store, fake):
    store.search(QUESTION, mode="semantic")
    assert len(fake.calls) == 1
    assert len(fake.calls[0]) == 4  # three decisions + the question, one model call
    assert [d for d, _ in _vector_rows(store)] == ["auth", "ci", "logs"]
    store.search(QUESTION, mode="semantic")
    assert fake.calls[-1] == [QUESTION]


def test_amending_the_text_reembeds_only_that_decision(store, fake):
    store.search(QUESTION, mode="semantic")
    auth = store.get("auth")
    auth.rationale = "Every handler authenticates through the middleware, never inline."
    store.update(auth)
    store.search(QUESTION, mode="semantic")
    assert fake.calls[-1] == [f"{auth.title}\n{auth.rationale}", QUESTION]


def test_status_changes_do_not_reembed(store, fake):
    """Invalidation appends to evidence, which isn't embedded."""
    store.search(QUESTION, mode="semantic")
    store.invalidate("logs", reason="superseded")
    store.search(QUESTION, mode="semantic", status="ALL")
    assert fake.calls[-1] == [QUESTION]


def test_switching_models_reembeds(store, tmp_path):
    store.search(QUESTION, mode="semantic")
    other = ConceptEmbedder(model_id="concept-v2")
    DecisionStore(str(tmp_path), embedder=other.embedder).search(QUESTION, mode="semantic")
    assert len(other.calls[0]) == 4
    assert {model for _, model in _vector_rows(store)} == {"concept-v2"}


def test_deleting_a_decision_drops_its_vector(store):
    store.search(QUESTION, mode="semantic")
    store.delete("auth")
    assert [d for d, _ in _vector_rows(store)] == ["ci", "logs"]


def test_semantic_honours_status_and_confidence_filters(store):
    store.record(
        id="auth-unsure",
        title="Verify callers in the gateway",
        rationale="Maybe authenticate before the handler runs.",
        commit_sha=SHA,
        confidence=0.4,
    )
    assert _ids(store.query(QUESTION, mode="semantic", min_score=0.5)) == ["auth"]
    store.invalidate("auth")
    assert _ids(store.query(QUESTION, mode="semantic", min_score=0.5)) == []
    assert _ids(store.query(QUESTION, mode="semantic", status="ALL", min_score=0.5)) == ["auth"]


def _set_cached(store: DecisionStore, decision_id: str, blob: bytes, dim: int) -> None:
    with store._connect() as conn:
        conn.execute(
            "UPDATE decision_vectors SET vector = ?, dim = ? WHERE decision_id = ?",
            (blob, dim, decision_id),
        )


@pytest.mark.parametrize(
    "blob, dim",
    [
        (b"\x01\x02\x03", 3),  # not a whole number of float32s
        (struct.pack("<3f", 1.0, 0.0, 0.0), 5),  # stored dim disagrees with the bytes
        (struct.pack("<3f", float("nan"), 0.0, 0.0), 3),  # decodes, but not finite
    ],
    ids=["truncated", "dim-mismatch", "nan"],
)
def test_a_damaged_cached_vector_is_reembedded(store, fake, blob, dim):
    """It used to raise ValueError outside the guarded block, failing even the
    default hybrid search, or to rank a vector that can't be trusted."""
    store.search(QUESTION, mode="semantic")
    _set_cached(store, "auth", blob, dim)
    found = store.search(QUESTION, mode="hybrid")
    assert (found.mode, _ids(found.records)) == ("hybrid", ["auth"])
    assert fake.calls[-1] == [
        store.get("auth").title + "\n" + store.get("auth").rationale,
        QUESTION,
    ]
    with store._connect() as conn:
        assert conn.execute(
            "SELECT dim FROM decision_vectors WHERE decision_id = 'auth'"
        ).fetchone() == (3,)


def test_a_cached_vector_of_the_wrong_size_is_reembedded_not_dropped(store, fake):
    """A readable vector whose length isn't the model's used to be filtered out
    of the ranking for good: its text and model id still matched."""
    store.search(QUESTION, mode="semantic")
    _set_cached(store, "auth", struct.pack("<2f", 1.0, 0.0), 2)
    assert _ids(store.query(QUESTION, mode="semantic")) == ["auth"]
    assert fake.calls[-2:] == [
        [QUESTION],
        [store.get("auth").title + "\n" + store.get("auth").rationale],
    ]
    store.search(QUESTION, mode="semantic")
    assert fake.calls[-1] == [QUESTION]  # repaired in the cache


# ------------------------------------------------------------------ #
# Reciprocal rank fusion
# ------------------------------------------------------------------ #


def test_rrf_ranks_ids_in_both_lists_first():
    # a: in both lists; c: first in one list; b: second in one list.
    assert semantic.rrf([["a", "b"], ["c", "a"]]) == ["a", "c", "b"]


def test_rrf_breaks_ties_by_best_rank_then_earlier_list():
    assert semantic.rrf([["kw"], ["sem"]]) == ["kw", "sem"]
    assert semantic.rrf([["x", "kw"], ["sem", "x"]]) == ["x", "sem", "kw"]


# ------------------------------------------------------------------ #
# MCP tools
# ------------------------------------------------------------------ #


def _call(name, arguments):
    return json.loads(mcp_tools.handle_tool_call(name, arguments))


@pytest.mark.parametrize("tool", ["neuralmind_query_decisions", "neuralmind_memory_search"])
def test_tools_report_the_mode_that_ranked_the_results(tmp_path, monkeypatch, fake, tool):
    monkeypatch.setattr(semantic, "load_default_embedder", lambda: fake.embedder)
    _seed(DecisionStore(str(tmp_path)))
    data = _call(tool, {"project_path": str(tmp_path), "query": QUESTION, "mode": "semantic"})
    assert data["mode"] == "semantic"
    assert data["count"] == 1
    assert "notice" not in data


def test_tools_report_a_hybrid_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(semantic, "load_default_embedder", _unavailable)
    _seed(DecisionStore(str(tmp_path)))
    data = _call(
        "neuralmind_memory_search",
        {"project_path": str(tmp_path), "query": "authentication", "mode": "hybrid"},
    )
    assert data["mode"] == "keyword"
    assert "no model here" in data["notice"]
    assert [row["id"] for row in data["results"]] == ["auth"]


def test_tools_say_when_semantic_search_cannot_run(tmp_path, monkeypatch):
    monkeypatch.setattr(semantic, "load_default_embedder", _unavailable)
    data = _call(
        "neuralmind_query_decisions",
        {"project_path": str(tmp_path), "query": QUESTION, "mode": "semantic"},
    )
    assert data["code"] == "semantic_unavailable"
    assert "hybrid" in data["hint"]


@pytest.mark.parametrize("tool", ["neuralmind_query_decisions", "neuralmind_memory_search"])
def test_unknown_mode_is_invalid_request(tmp_path, tool):
    data = _call(tool, {"project_path": str(tmp_path), "query": "x", "mode": "fuzzy"})
    assert data["code"] == "invalid_request"
    assert "'mode'" in data["error"]


def test_main_dispatcher_rejects_an_unknown_mode(tmp_path):
    from neuralmind.mcp_server import handle_tool_call

    data = json.loads(
        handle_tool_call(
            "neuralmind_memory_search",
            {"project_path": str(tmp_path), "query": "x", "mode": "fuzzy"},
        )
    )
    assert data["code"] == "invalid_request"


@pytest.mark.parametrize("tool", ["neuralmind_query_decisions", "neuralmind_memory_search"])
def test_search_tools_advertise_the_mode(tool):
    schema = next(t for t in mcp_tools.TOOLS if t["name"] == tool)["inputSchema"]
    description = schema["properties"]["mode"]["description"]
    assert all(mode in description for mode in semantic.SEARCH_MODES)
    assert "mode" not in schema["required"]


# ------------------------------------------------------------------ #
# CLI
# ------------------------------------------------------------------ #


def _cli(argv, capsys):
    args = build_parser().parse_args(argv)
    args.func(args)
    return capsys.readouterr()


def test_cli_semantic_query(tmp_path, monkeypatch, fake, capsys):
    monkeypatch.setattr(semantic, "load_default_embedder", lambda: fake.embedder)
    _seed(DecisionStore(str(tmp_path)))
    out = _cli(["decisions", "query", QUESTION, str(tmp_path), "--mode", "semantic"], capsys).out
    assert f'"{QUESTION}" (semantic)' in out
    assert "Use per-handler authentication middleware" in out


def test_cli_hybrid_fallback_notice_goes_to_stderr(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(semantic, "load_default_embedder", _unavailable)
    _seed(DecisionStore(str(tmp_path)))
    argv = ["decisions", "query", "authentication", str(tmp_path), "--mode", "hybrid", "--json"]
    captured = _cli(argv, capsys)
    assert [d["id"] for d in json.loads(captured.out)] == ["auth"]
    assert "keyword results only" in captured.err


def test_cli_json_keeps_the_array_and_names_the_mode_on_stderr(tmp_path, monkeypatch, fake, capsys):
    monkeypatch.setattr(semantic, "load_default_embedder", lambda: fake.embedder)
    _seed(DecisionStore(str(tmp_path)))
    argv = ["decisions", "query", QUESTION, str(tmp_path), "--mode", "semantic", "--json"]
    captured = _cli(argv, capsys)
    assert [d["id"] for d in json.loads(captured.out)] == ["auth"]
    assert "[neuralmind] search mode: semantic" in captured.err


def test_cli_empty_result_names_the_mode(tmp_path, monkeypatch, fake, capsys):
    monkeypatch.setattr(semantic, "load_default_embedder", lambda: fake.embedder)
    _seed(DecisionStore(str(tmp_path)))
    out = _cli(["decisions", "query", QUESTION, str(tmp_path), "--mode", "keyword"], capsys).out
    assert f"No decisions found for: {QUESTION} (keyword search)" in out


def test_cli_semantic_unavailable_exits_nonzero(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(semantic, "load_default_embedder", _unavailable)
    with pytest.raises(SystemExit) as exc:
        _cli(["decisions", "query", QUESTION, str(tmp_path), "--mode", "semantic"], capsys)
    assert exc.value.code == 1
    assert "Semantic search unavailable" in capsys.readouterr().err


# ------------------------------------------------------------------ #
# Eval harness
# ------------------------------------------------------------------ #


def test_eval_scores_every_mode_side_by_side(fake):
    report = json.loads(QuerySetEval(load_query_set(FIXTURE), embedder=fake.embedder).run())
    assert list(report["modes"]) == ["keyword", "semantic", "hybrid"]
    assert report["not_run"] == {}
    assert "paraphrase" in report["modes"]["semantic"]["summary"]


def test_eval_never_scores_a_fallback_as_hybrid(monkeypatch):
    monkeypatch.setattr(semantic, "load_default_embedder", _unavailable)
    report = json.loads(QuerySetEval(load_query_set(FIXTURE)).run())
    assert list(report["modes"]) == ["keyword"]
    assert set(report["not_run"]) == {"semantic", "hybrid"}
    assert "no model here" in report["not_run"]["hybrid"]


def test_eval_cli_mode_flag(monkeypatch, capsys):
    monkeypatch.setattr(semantic, "load_default_embedder", _unavailable)
    argv = ["decisions", "eval", "--queries", str(FIXTURE), "--mode", "keyword", "--format", "md"]
    out = _cli(argv, capsys).out
    assert "**Modes**: keyword" in out
    assert "Not run" not in out
