"""Every query and build is counted in ``.neuralmind/metrics/``, content-free.

``recent_queries.jsonl`` keeps question text, so it waits for memory-logging
consent; a monitor that wants to know whether the index is used at all reads
these counters instead (``neuralmind metrics``). Embeddings use the hashing
function from ``test_index_freshness``, so nothing needs the ONNX model.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("turbovec")

from tests.test_index_freshness import _mind, _write_files  # noqa: E402


@pytest.fixture
def built(tmp_path, monkeypatch):
    from neuralmind import graphgen

    if not graphgen.is_available():
        pytest.skip("tree-sitter not installed")
    monkeypatch.delenv("NEURALMIND_NO_LEARN", raising=False)
    monkeypatch.setenv("NEURALMIND_MEMORY", "0")  # no consent for query text
    _write_files(tmp_path, ["auth.py", "billing.py"])
    assert _mind(tmp_path).build()["success"]
    return tmp_path


def _records(project: Path) -> list[dict]:
    return [
        json.loads(line)
        for f in sorted((project / ".neuralmind" / "metrics").glob("metrics_*.jsonl"))
        for line in f.read_text(encoding="utf-8").splitlines()
    ]


def test_a_build_is_recorded_with_the_synapse_totals(built):
    (build,) = [r for r in _records(built) if r["event"] == "build"]
    assert build["nodes_total"] > 0
    assert {"synapse_edges", "synapse_transitions", "duration_s"} <= set(build)


def test_queries_are_counted_without_their_text_or_consent(built):
    mind = _mind(built)
    mind.query("where is auth handled")
    mind.query("billing helper", learn=False)  # read-only: writes nothing

    queries = [r for r in _records(built) if r["event"] == "query"]
    assert len(queries) == 1
    (q,) = queries
    assert "query" not in q and "session_id" not in q
    assert q["tokens_used"] > 0 and q["latency_ms"] >= 0
    assert "where is auth" not in json.dumps(_records(built))
    # Consent was off, so the replay log stayed empty.
    assert not (built / ".neuralmind" / "recent_queries.jsonl").exists()


def test_explain_json_carries_the_reasons(built):
    """``query --explain --json`` used to drop the explanation; now it's data."""
    import json as _json

    from neuralmind.cli import _explain_data

    result = _mind(built).query("where is auth handled", trace=True)
    explain = _explain_data(result)
    _json.dumps(explain)  # serialisable as part of the --json output
    assert explain["budget"]["total"] == result.budget.total
    assert explain["layers"] == result.layers_used
    assert explain["top_hits"], "a query that found code names its top hits"
    top = explain["top_hits"][0]
    assert set(top) == {"id", "label", "source_file", "score"}
    assert any(h["source_file"].endswith("auth.py") for h in explain["top_hits"])
    assert isinstance(explain["synapses_fired"], list)
