"""Tests for retrieval traces (PRD 3).

The trace data structure + redaction are pure/stdlib. The end-to-end test
(real retrieval populates a trace) needs the embedding stack + a built fixture,
so it's gated on NEURALMIND_QUALITY_EVAL like the quality harness — it runs in
the self-benchmark workflow where real embeddings are available.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from neuralmind import trace as trace_mod
from neuralmind.trace import RetrievalTrace

REPO_ROOT = Path(__file__).resolve().parents[1]


# --------------------------------------------------------------------------- #
# Pure trace structure
# --------------------------------------------------------------------------- #


def _candidates():
    return [
        {
            "id": "a",
            "metadata": {"label": "f()", "source_file": "src/auth/handlers.py"},
            "score": 0.9,
        },
        {"id": "b", "metadata": {"label": "g()", "source_file": "src/db/conn.py"}, "score": 0.5},
    ]


def test_record_candidates_keeps_longest_pool():
    tr = RetrievalTrace(query="how does auth work?")
    tr.record_candidates(_candidates()[:1])
    tr.record_candidates(_candidates())  # longer — should replace
    d = tr.to_dict()
    ev = [e for e in d["events"] if e["kind"] == "search"][0]
    assert len(ev["data"]["candidates"]) == 2
    assert ev["data"]["candidates"][0]["id"] == "a"


def test_record_cluster_scores_attributes_boost():
    tr = RetrievalTrace(query="q", verbose=True)
    tr.record_cluster_scores(
        vector_scores={0: 1.0, 1: 0.2},
        boosted_scores={0: 1.0, 1: 0.7},  # cluster 1 got +0.5 synapse boost
        selected=[0, 1],
        budget=2,
    )
    ev = [e for e in tr.to_dict()["events"] if e["kind"] == "cluster_scores"][0]
    by_cluster = {c["cluster"]: c for c in ev["data"]["clusters"]}
    assert by_cluster[1]["vector_score"] == 0.2
    assert round(by_cluster[1]["synapse_boost"], 4) == 0.5
    assert by_cluster[0]["selected"] is True


def test_record_synapse_boost_and_hits():
    tr = RetrievalTrace(query="q")
    tr.record_synapse_boost(["a", "b"], comm=3, energy=0.8, weighted=0.4)
    hits = _candidates()
    hits[0]["_synapse_recalled"] = True
    tr.record_hits(hits)
    d = tr.to_dict()
    kinds = {e["kind"] for e in d["events"]}
    assert "synapse_boost" in kinds and "hits" in kinds
    hit_ev = [e for e in d["events"] if e["kind"] == "hits"][0]
    assert "1 synapse-recalled" in hit_ev["summary"]


def test_record_budget():
    class B:
        l0_identity, l1_summary, l2_ondemand, l3_search, total = 100, 400, 300, 500, 1300

    tr = RetrievalTrace(query="q")
    tr.record_budget(["L0:Identity", "L3:Search(4)"], B(), 42.0)
    ev = [e for e in tr.to_dict()["events"] if e["kind"] == "budget"][0]
    assert ev["data"]["tokens"]["total"] == 1300
    assert ev["data"]["reduction_ratio"] == 42.0


def test_to_dict_is_json_safe():
    tr = RetrievalTrace(query="q")
    tr.record_candidates(_candidates())
    json.dumps(tr.to_dict())  # must not raise


def test_nonverbose_trims_candidates_verbose_keeps():
    big = [
        {"id": str(i), "metadata": {"label": f"n{i}", "source_file": f"f{i}.py"}, "score": 0.1}
        for i in range(20)
    ]
    terse = RetrievalTrace(query="q", verbose=False)
    terse.record_candidates(big)
    terse_ev = [e for e in terse.to_dict()["events"] if e["kind"] == "search"][0]
    assert len(terse_ev["data"]["candidates"]) == 10  # trimmed

    loud = RetrievalTrace(query="q", verbose=True)
    loud.record_candidates(big)
    loud_ev = [e for e in loud.to_dict()["events"] if e["kind"] == "search"][0]
    assert len(loud_ev["data"]["candidates"]) == 20  # verbose keeps all (under the cap)


def test_redaction_strips_paths_to_basename():
    tr = RetrievalTrace(query="how does auth work?")
    tr.record_candidates(_candidates())
    redacted = tr.to_dict(redact=True)
    cand = [e for e in redacted["events"] if e["kind"] == "search"][0]["data"]["candidates"]
    assert all("/" not in c["source_file"] for c in cand)
    assert cand[0]["source_file"] == "handlers.py"


def test_bounded_lists_cap_at_max_items():
    big = [{"id": str(i), "metadata": {"label": f"n{i}"}, "score": 0.1} for i in range(100)]
    tr = RetrievalTrace(query="q", verbose=True)
    tr.record_hits(big)
    ev = [e for e in tr.to_dict()["events"] if e["kind"] == "hits"][0]
    assert len(ev["data"]["hits"]) == trace_mod.MAX_ITEMS


def test_render_text_includes_layers():
    tr = RetrievalTrace(query="q")
    tr.record_candidates(_candidates())
    tr.record_hits(_candidates())
    text = tr.render_text()
    assert "candidates/search" in text
    assert "L3/hits" in text


# --------------------------------------------------------------------------- #
# End-to-end: real retrieval populates a trace
# --------------------------------------------------------------------------- #

_PY_FIXTURE = REPO_ROOT / "tests" / "fixtures" / "sample_project"


@pytest.mark.skipif(
    not os.environ.get("NEURALMIND_QUALITY_EVAL"),
    reason="needs real embeddings; runs in the self-benchmark workflow",
)
def test_e2e_query_trace_is_populated(tmp_path):
    import shutil

    from neuralmind import NeuralMind

    proj = tmp_path / "sample_project"
    shutil.copytree(_PY_FIXTURE, proj)
    nm = NeuralMind(str(proj))
    build = nm.build()
    if not build.get("success", True):
        pytest.skip(f"build failed: {build.get('error')}")

    result = nm.query("How does authentication work?", trace=True)
    assert result.trace is not None
    kinds = {e["kind"] for e in result.trace["events"]}
    # Candidate generation + final hits + budget should always be present.
    assert "search" in kinds
    assert "hits" in kinds
    assert "budget" in kinds

    # A non-traced query carries no trace (zero-overhead default).
    plain = nm.query("How does authentication work?")
    assert plain.trace is None
