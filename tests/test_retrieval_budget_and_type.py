"""``query_type`` and ``context_budget`` do what ``NeuralMind.query`` documents.

* ``query_type='code'|'docs'`` (``neuralmind query --type``) ranks L3 with
  the requested intent instead of the detected one. It used to re-boost the
  already-boosted hits with the *detected* intent after the context was
  rendered, so the output never changed and the scores compounded.
* ``context_budget`` trims L3, then L2, then L1, at whole lines, and never
  L0. It looked for layer labels ("L3:Search(") that never appear in the
  context, so it always fell through to a raw character cut that truncated L0
  mid-word, and left the token budget describing the untrimmed context.
* With ``hybrid_context`` on, the highlights count against that budget; they
  used to be prepended after trimming (budget 100 -> 171 tokens).

Embeddings use a deterministic hashing function injected into the turbovec
backend, so nothing here needs the ONNX model.
"""

from __future__ import annotations

import hashlib
import io
import shutil
from pathlib import Path

import numpy as np
import pytest

from neuralmind import graphgen
from neuralmind.context_budget import count_tokens, trim_context_to_budget

pytest.importorskip("turbovec")
pytestmark = pytest.mark.skipif(not graphgen.is_available(), reason="tree-sitter not installed")

_FIXTURE = Path(__file__).parent / "fixtures" / "sample_project"
_DIM = 32

# _detect_intent calls this one "code" ("function", "implements", "routes.py").
_CODE_QUESTION = "which function in routes.py implements the webhook handler"

_QUESTION = "How does authentication work?"

_HEADERS = {
    "L1": "## Architecture Overview",
    "L2": "## Relevant Code Areas",
    "L3": "## Search Results",
}

_CODE_BOOSTS = {3.0, 0.5}
_DOC_BOOSTS = {2.0, 0.7}


def _fake_embed(texts: list[str]) -> list[list[float]]:
    out = []
    for t in texts:
        vec = np.zeros(_DIM, dtype=np.float32)
        for tok in t.lower().replace("\n", " ").split():
            vec[int.from_bytes(hashlib.md5(tok.encode()).digest()[:4], "little") % _DIM] += 1.0
        out.append(vec.tolist())
    return out


def _new_mind(root: Path, **kwargs):
    from neuralmind.core import NeuralMind

    mind = NeuralMind(str(root), backend_type="turbovec", enable_synapses=False, **kwargs)
    mind.embedder._embed_fn = _fake_embed
    mind.notice_stream = io.StringIO()
    return mind


@pytest.fixture(scope="module")
def project(tmp_path_factory) -> Path:
    root = tmp_path_factory.mktemp("retrieval") / "proj"
    shutil.copytree(_FIXTURE, root, ignore=shutil.ignore_patterns(".neuralmind"))
    mind = _new_mind(root)
    try:
        assert mind.build(regenerate_graph=True)["success"]
    finally:
        mind.close()
    return root


@pytest.fixture
def mind(project):
    m = _new_mind(project)
    yield m
    m.close()


# --------------------------------------------------------------------------- #
# query_type
# --------------------------------------------------------------------------- #
def test_query_type_sets_the_intent_l3_ranks_with(mind):
    auto = mind.query(_CODE_QUESTION, learn=False)
    code = mind.query(_CODE_QUESTION, query_type="code", learn=False)
    docs = mind.query(_CODE_QUESTION, query_type="docs", learn=False)

    assert auto.intent == "code"  # precondition: detected as a code question
    assert code.intent == "code"
    assert docs.intent == "docs"
    assert docs.intent_source == code.intent_source == "query_type"

    assert {h.get("_intent_boost") for h in code.top_search_hits} <= _CODE_BOOSTS
    assert {h.get("_intent_boost") for h in docs.top_search_hits} <= _DOC_BOOSTS


def test_query_type_changes_the_rendered_context(mind):
    code = mind.query(_CODE_QUESTION, query_type="code", learn=False)
    docs = mind.query(_CODE_QUESTION, query_type="docs", learn=False)
    assert code.context != docs.context


def test_query_type_matching_the_detected_intent_boosts_once(mind):
    auto = mind.query(_CODE_QUESTION, learn=False)
    code = mind.query(_CODE_QUESTION, query_type="code", learn=False)

    auto_scores = {h["id"]: h["score"] for h in auto.top_search_hits}
    code_scores = {h["id"]: h["score"] for h in code.top_search_hits}
    assert code_scores == pytest.approx(auto_scores)
    assert code.context == auto.context


# --------------------------------------------------------------------------- #
# context_budget
# --------------------------------------------------------------------------- #
def _sections(context: str) -> dict[str, str]:
    """Split an assembled context at its layer headers (the test's own view)."""
    cuts = [("L0", 0)]
    for layer, header in _HEADERS.items():
        pos = context.find("\n" + header + "\n")
        if pos >= 0:
            cuts.append((layer, pos + 1))
    cuts.sort(key=lambda c: c[1])
    out = {}
    for i, (layer, start) in enumerate(cuts):
        end = cuts[i + 1][1] - 1 if i + 1 < len(cuts) else len(context)
        out[layer] = context[start:end]
    return out


def test_budget_below_l0_returns_l0_whole(mind):
    full = mind.query(_QUESTION, learn=False)
    l0 = _sections(full.context)["L0"]

    res = mind.query(_QUESTION, context_budget=5, learn=False)

    assert res.context == l0  # never trimmed, never cut mid-word
    assert res.layers_used == ["L0:Identity"]
    assert res.budget.l0_identity == full.budget.l0_identity
    assert res.budget.l1_summary == res.budget.l2_ondemand == res.budget.l3_search == 0
    assert res.tokens == res.budget.l0_identity
    assert res.reduction_ratio == pytest.approx(
        full.reduction_ratio * full.budget.total / res.budget.total
    )


@pytest.mark.parametrize("fraction", [0.35, 0.6, 0.85])
def test_budget_trims_l3_then_l2_then_l1_at_whole_lines(mind, fraction):
    full = mind.query(_QUESTION, learn=False)
    whole = _sections(full.context)
    assert set(whole) == {"L0", "L1", "L2", "L3"}  # precondition: every layer present
    used = count_tokens(full.context)
    budget = max(count_tokens(whole["L0"]) + 1, int(used * fraction))

    res = mind.query(_QUESTION, context_budget=budget, learn=False)
    kept = _sections(res.context)

    assert count_tokens(res.context) <= budget
    assert kept["L0"] == whole["L0"]
    # Whole lines only: every line returned is a line of the untrimmed context.
    full_lines = set(full.context.split("\n"))
    assert all(line in full_lines for line in res.context.split("\n"))
    # L0 -> L3 order, and a layer survives only while every higher one is whole.
    order = [layer for layer in ("L0", "L1", "L2", "L3") if layer in kept]
    assert order == ["L0", "L1", "L2", "L3"][: len(order)]
    for layer in order[:-1]:
        assert kept[layer] == whole[layer]
    assert kept[order[-1]] == whole[order[-1]][: len(kept[order[-1]])]

    # The budget describes what was returned.
    est = mind.selector._estimate_tokens
    assert res.budget.l0_identity == est(kept["L0"])
    assert res.budget.l1_summary == est(kept.get("L1", ""))
    assert res.budget.l2_ondemand == est(kept.get("L2", ""))
    assert res.budget.l3_search == est(kept.get("L3", ""))
    assert res.budget.total < full.budget.total
    assert [label.split(":")[0] for label in res.layers_used] == order
    assert res.reduction_ratio == pytest.approx(
        full.reduction_ratio * full.budget.total / res.budget.total
    )


def test_budget_that_fits_changes_nothing(mind):
    full = mind.query(_QUESTION, learn=False)
    res = mind.query(_QUESTION, context_budget=count_tokens(full.context), learn=False)
    assert res.context == full.context
    assert res.budget.to_dict() == full.budget.to_dict()
    assert res.layers_used == full.layers_used


def _layered(n: int) -> tuple[list[str], str]:
    parts = [
        "## Project: demo\n\nA demo project for trimming\n\nType: Code repository",
        _HEADERS["L1"] + "\n\n" + "\n".join(f"- Cluster {i}: summary words" for i in range(n)),
        _HEADERS["L2"] + "\n\n" + "\n".join(f"- area_{i} (code) — mod_{i}.py" for i in range(n)),
        _HEADERS["L3"] + "\n\n" + "\n".join(f"{i}. **hit_{i}** (score: 1.00)" for i in range(n)),
    ]
    return parts, "\n".join(parts)


def test_trim_context_to_budget_keeps_l0_and_layer_order():
    parts, context = _layered(12)
    budget = count_tokens("\n".join(parts[:2])) + count_tokens(parts[2]) // 2

    out, trimmed = trim_context_to_budget(context, budget)

    assert count_tokens(out) <= budget
    assert out.startswith("\n".join(parts[:2]) + "\n" + _HEADERS["L2"])
    assert _HEADERS["L3"] not in out
    assert trimmed == ["L3", "L2"]
    assert all(line in context.split("\n") for line in out.split("\n"))


def test_trim_context_to_budget_never_cuts_l0():
    parts, context = _layered(12)
    out, trimmed = trim_context_to_budget(context, 3)
    assert out == parts[0]
    assert trimmed == ["L3", "L2", "L1"]


def test_trim_context_to_budget_with_explicit_markers():
    parts, context = _layered(12)
    budget = count_tokens("\n".join(parts[:3]))
    out, trimmed = trim_context_to_budget(context, budget, layer_markers=dict(_HEADERS))
    assert out == "\n".join(parts[:3])
    assert trimmed == ["L3"]


# --------------------------------------------------------------------------- #
# hybrid_context + context_budget
# --------------------------------------------------------------------------- #
@pytest.fixture
def hybrid_mind(project):
    m = _new_mind(project, hybrid_context=True)
    yield m
    m.close()


def test_hybrid_highlights_count_against_the_budget(hybrid_mind):
    full = hybrid_mind.query(_QUESTION, learn=False)
    highlights, layered = full.context.split("\n\n", 1)
    assert highlights.startswith("## Hybrid Highlights")  # precondition
    l0 = _sections(layered)["L0"]
    highlight_lines = set(highlights.split("\n"))

    for budget in (100, count_tokens(full.context) - 25):
        res = hybrid_mind.query(_QUESTION, context_budget=budget, learn=False)
        assert count_tokens(res.context) <= budget
        assert l0 in res.context
        if res.context.startswith("## Hybrid Highlights"):
            head, _ = res.context.split("\n\n", 1)
            assert set(head.split("\n")) <= highlight_lines


def test_hybrid_budget_that_fits_keeps_every_highlight(hybrid_mind):
    full = hybrid_mind.query(_QUESTION, learn=False)
    res = hybrid_mind.query(_QUESTION, context_budget=count_tokens(full.context), learn=False)
    assert res.context == full.context


def test_hybrid_highlights_count_in_the_reported_tokens(mind, hybrid_mind):
    """result.budget feeds the MCP response, the query log and the savings
    figures, so it has to describe the context returned, highlights included.
    They used to be left out: with no budget, and whenever a budget kept them."""
    base = mind.query(_QUESTION, learn=False)
    full = hybrid_mind.query(_QUESTION, learn=False)
    est = hybrid_mind.selector._estimate_tokens  # the selector loads on first query
    highlights, layered = full.context.split("\n\n", 1)
    assert highlights.startswith("## Hybrid Highlights")  # precondition
    assert layered == base.context  # precondition: same layers
    assert full.budget.total == base.budget.total + est(highlights)
    assert full.reduction_ratio < base.reduction_ratio

    fits = hybrid_mind.query(_QUESTION, context_budget=count_tokens(full.context), learn=False)
    assert fits.budget.total == full.budget.total

    for budget in (100, count_tokens(full.context) - 25):
        res = hybrid_mind.query(_QUESTION, context_budget=budget, learn=False)
        head = ""
        if res.context.startswith("## Hybrid Highlights"):
            head = res.context.split("\n\n", 1)[0]
        layer_tokens = sum(est(text) for _, text in res.layer_texts)
        assert res.budget.total == layer_tokens + est(head), budget
