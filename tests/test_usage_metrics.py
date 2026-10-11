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


def test_each_build_reports_synapse_growth_since_the_last(built):
    """``Synapses: 3,612 edges (+47 since last build), 0 transitions (+0)``."""
    from neuralmind.cli import _synapse_line

    first = json.loads((built / ".neuralmind" / "build_status.json").read_text())["synapses"]
    mind = _mind(built)
    mind.query("where is auth handled")  # learning between builds
    mind.synapses.record_sequence(["auth.py", "billing.py"])  # as an edit hook would
    result = _mind(built).build()

    synapses = result["synapses"]
    assert synapses["transitions"] == first["transitions"] + 1
    assert synapses["transitions_delta"] == 1
    assert synapses["edges_delta"] == synapses["edges"] - first["edges"]
    line = _synapse_line(synapses)
    assert f"{synapses['edges']:,} edges ({synapses['edges_delta']:+,} since last build)" in line
    assert line.endswith(f"{synapses['transitions']:,} transitions (+1)")


def test_first_build_has_totals_but_no_delta():
    from neuralmind.cli import _synapse_line

    assert _synapse_line({"edges": 3612, "transitions": 0}) == "3,612 edges, 0 transitions"


def test_stats_shows_learning_over_the_window(built, capsys, monkeypatch):
    from argparse import Namespace

    from neuralmind.cli import TRANSITIONS_HINT, _learning_summary, cmd_stats

    monkeypatch.setenv("NEURALMIND_NO_DAEMON", "1")
    mind = _mind(built)
    mind.query("billing helper")
    mind.synapses.record_sequence(["auth.py", "billing.py"])
    _mind(built).build()

    learning = _learning_summary(built)
    assert (learning["queries"], learning["builds"]) == (1, 2)
    assert learning["transitions_delta"] == 1
    assert learning["last_query_ts"] > 0

    cmd_stats(Namespace(project_path=str(built), json=True))
    assert json.loads(capsys.readouterr().out)["learning"]["transitions_delta"] == 1
    cmd_stats(Namespace(project_path=str(built), json=False))
    text = capsys.readouterr().out
    assert "Learning (last 7 days):" in text
    assert "transitions (+1) across 2 build(s)" in text
    # With a transition learned, no hint about where they come from.
    assert TRANSITIONS_HINT not in text


def test_zero_transitions_says_what_teaches_them(built, capsys, monkeypatch):
    from argparse import Namespace

    from neuralmind.cli import TRANSITIONS_HINT, cmd_stats, cmd_synapse_stats

    monkeypatch.setenv("NEURALMIND_NO_DAEMON", "1")
    cmd_stats(Namespace(project_path=str(built), json=False))
    assert TRANSITIONS_HINT in capsys.readouterr().out
    cmd_synapse_stats(Namespace(project_path=str(built), json=False))
    assert TRANSITIONS_HINT in capsys.readouterr().out
    assert "neuralmind watch" in TRANSITIONS_HINT and "install-hooks" in TRANSITIONS_HINT


def test_stats_via_the_daemon_still_shows_learning(built, capsys, monkeypatch):
    """The CLI prefers a running daemon; the learning block must not vanish there."""
    from argparse import Namespace

    from neuralmind import cli

    _mind(built).query("billing helper")

    class FakeDaemon:
        def stats(self, path):
            return {"project": "proj", "built": True, "nodes": 7}

    monkeypatch.setattr(cli, "_try_daemon", lambda: FakeDaemon())
    cli.cmd_stats(Namespace(project_path=str(built), json=True))
    data = json.loads(capsys.readouterr().out)
    assert data["via"] == "daemon"
    assert data["learning"]["queries"] == 1
    cli.cmd_stats(Namespace(project_path=str(built), json=False))
    assert "Learning (last 7 days):" in capsys.readouterr().out
