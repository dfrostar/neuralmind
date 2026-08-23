"""Tests for the index half of `neuralmind status`.

`status` used to report only the synapse layer, so "did my ingest
actually land, and how stale is the index?" had no answer short of
running a query. These cover the index/content snapshot it now prints
alongside the learning diagnostic.

Stdlib-only: the snapshot reads the IR and the content manifest off disk
and deliberately never constructs a vector backend.
"""

import json
from argparse import Namespace
from pathlib import Path

import pytest

from neuralmind.cli_feedback_status import (
    _content_snapshot,
    _index_snapshot,
    cmd_status,
)
from neuralmind.content_manifest import ContentManifest


@pytest.fixture
def project(tmp_path: Path) -> Path:
    (tmp_path / ".neuralmind").mkdir()
    return tmp_path


def write_ir(project: Path, nodes: int = 0, edges: int = 0) -> Path:
    payload = {
        "ir_version": 1,
        "created_at": "2026-01-01T00:00:00+00:00",
        "nodes": [{"id": f"n{i}"} for i in range(nodes)],
        "edges": [{"source": "a", "target": "b"} for _ in range(edges)],
    }
    path = project / ".neuralmind" / "index_ir.json"
    path.write_text(json.dumps(payload))
    return path


class TestIndexSnapshot:
    def test_reports_absence_when_nothing_is_indexed(self, project: Path):
        snapshot = _index_snapshot(project)
        assert snapshot["exists"] is False
        assert snapshot["nodes"] is None

    def test_counts_nodes_and_edges(self, project: Path):
        write_ir(project, nodes=12, edges=5)
        snapshot = _index_snapshot(project)
        assert snapshot["exists"] is True
        assert snapshot["nodes"] == 12
        assert snapshot["edges"] == 5

    def test_reports_build_time_and_age(self, project: Path):
        write_ir(project, nodes=1)
        snapshot = _index_snapshot(project)
        assert snapshot["built_at"] == "2026-01-01T00:00:00+00:00"
        assert snapshot["age_hours"] is not None
        assert snapshot["age_hours"] >= 0

    def test_falls_back_to_mtime_without_a_timestamp(self, project: Path):
        (project / ".neuralmind" / "index_ir.json").write_text('{"ir_version": 1, "nodes": []}')
        assert _index_snapshot(project)["built_at"]

    def test_corrupt_ir_does_not_raise(self, project: Path):
        (project / ".neuralmind" / "index_ir.json").write_text("{{ not json")
        snapshot = _index_snapshot(project)
        assert snapshot["exists"] is True
        assert snapshot["nodes"] is None

    def test_oversize_ir_is_not_parsed(self, project: Path, monkeypatch):
        """A glance at project state must stay fast on a huge monorepo IR."""
        monkeypatch.setattr("neuralmind.cli_feedback_status.MAX_IR_PARSE_BYTES", 10)
        write_ir(project, nodes=100)
        snapshot = _index_snapshot(project)
        assert snapshot["exists"] is True
        assert snapshot["nodes"] is None
        assert snapshot["built_at"]


class TestContentSnapshot:
    def test_untracked_project(self, project: Path):
        snapshot = _content_snapshot(project)
        assert snapshot["tracked"] is False
        assert snapshot["files"] == 0

    def test_reports_manifest_totals(self, project: Path):
        doc = project / "ch1.md"
        doc.write_text("# One\n")
        manifest = ContentManifest(project)
        manifest.record(doc, chunk_size=500, overlap=50, chunks=4, nodes=4)
        manifest.save()

        snapshot = _content_snapshot(project)
        assert snapshot["tracked"] is True
        assert snapshot["files"] == 1
        assert snapshot["chunks"] == 4
        assert snapshot["last_indexed_at"]


class TestStatusCommand:
    def test_reports_the_index_with_no_synapse_store(self, project: Path, capsys):
        """A freshly ingested corpus has an index but no learned edges yet —
        status must still describe it."""
        write_ir(project, nodes=0)
        doc = project / "ch1.md"
        doc.write_text("# One\n")
        manifest = ContentManifest(project)
        manifest.record(doc, chunk_size=500, overlap=50, chunks=9, nodes=9)
        manifest.save()

        cmd_status(Namespace(project_path=str(project), json=False))
        out = capsys.readouterr().out
        assert "Code nodes:" in out
        assert "content-only project" in out
        assert "9 chunks" in out
        assert "No synapse memory yet" in out

    def test_json_carries_both_halves(self, project: Path, capsys):
        write_ir(project, nodes=3, edges=2)
        cmd_status(Namespace(project_path=str(project), json=True))
        payload = json.loads(capsys.readouterr().out)
        assert payload["index"]["nodes"] == 3
        assert payload["index"]["edges"] == 2
        assert payload["content"]["files"] == 0
        # The pre-existing synapse keys are untouched.
        assert payload["status"] == "no_store"
        assert payload["is_learning"] is False

    def test_index_appears_alongside_synapse_stats(self, project: Path, capsys):
        from neuralmind.synapses import SynapseStore, default_db_path

        write_ir(project, nodes=7)
        store = SynapseStore(default_db_path(project))
        store.reinforce(["a", "b", "c"])

        cmd_status(Namespace(project_path=str(project), json=True))
        payload = json.loads(capsys.readouterr().out)
        assert payload["index"]["nodes"] == 7
        assert payload["stats"]["edges"] > 0
