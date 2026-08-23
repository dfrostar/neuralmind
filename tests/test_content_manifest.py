"""Tests for the incremental-ingest manifest.

Stdlib-only (like the synapse-layer tests) — these run without chromadb,
turbovec, or tree-sitter installed.
"""

import json
from pathlib import Path

import pytest

from neuralmind.content_manifest import (
    MANIFEST_FILENAME,
    ContentManifest,
    file_digest,
    manifest_path,
)


@pytest.fixture
def corpus(tmp_path: Path) -> Path:
    """A project root with a two-file content corpus."""
    (tmp_path / "chapters").mkdir()
    (tmp_path / "chapters" / "ch1.md").write_text("# One\n\nFirst chapter.\n")
    (tmp_path / "chapters" / "ch2.md").write_text("# Two\n\nSecond chapter.\n")
    return tmp_path


class TestFileDigest:
    def test_digest_is_stable_for_identical_bytes(self, tmp_path: Path):
        a = tmp_path / "a.md"
        b = tmp_path / "b.md"
        a.write_text("same content")
        b.write_text("same content")
        assert file_digest(a) == file_digest(b)

    def test_digest_changes_with_content(self, tmp_path: Path):
        path = tmp_path / "a.md"
        path.write_text("before")
        first = file_digest(path)
        path.write_text("after")
        assert file_digest(path) != first

    def test_missing_file_digests_to_empty_string(self, tmp_path: Path):
        assert file_digest(tmp_path / "nope.md") == ""


class TestStaleness:
    def test_unrecorded_file_is_changed(self, corpus: Path):
        manifest = ContentManifest(corpus)
        assert not manifest.is_unchanged(corpus / "chapters" / "ch1.md", chunk_size=500, overlap=50)

    def test_recorded_file_is_unchanged(self, corpus: Path):
        path = corpus / "chapters" / "ch1.md"
        manifest = ContentManifest(corpus)
        manifest.record(path, chunk_size=500, overlap=50, chunks=1, nodes=1)
        assert manifest.is_unchanged(path, chunk_size=500, overlap=50)

    def test_edited_file_is_changed(self, corpus: Path):
        path = corpus / "chapters" / "ch1.md"
        manifest = ContentManifest(corpus)
        manifest.record(path, chunk_size=500, overlap=50, chunks=1, nodes=1)
        path.write_text("# One\n\nFirst chapter, revised with more words.\n")
        assert not manifest.is_unchanged(path, chunk_size=500, overlap=50)

    def test_same_size_different_bytes_is_changed(self, corpus: Path):
        """A same-length edit must not slip past the size short-circuit."""
        path = corpus / "chapters" / "ch1.md"
        manifest = ContentManifest(corpus)
        manifest.record(path, chunk_size=500, overlap=50, chunks=1, nodes=1)
        original = path.read_text()
        path.write_text(original.replace("First", "FIRST"))
        assert len(path.read_text()) == len(original)
        assert not manifest.is_unchanged(path, chunk_size=500, overlap=50)

    @pytest.mark.parametrize(
        ("chunk_size", "overlap"),
        [(800, 50), (500, 100)],
        ids=["different-chunk-size", "different-overlap"],
    )
    def test_different_chunk_params_invalidate(self, corpus: Path, chunk_size: int, overlap: int):
        """Re-chunking produces different boundaries and different node ids,
        so identical bytes are still stale under new parameters."""
        path = corpus / "chapters" / "ch1.md"
        manifest = ContentManifest(corpus)
        manifest.record(path, chunk_size=500, overlap=50, chunks=1, nodes=1)
        assert not manifest.is_unchanged(path, chunk_size=chunk_size, overlap=overlap)

    def test_deleted_file_is_changed(self, corpus: Path):
        path = corpus / "chapters" / "ch1.md"
        manifest = ContentManifest(corpus)
        manifest.record(path, chunk_size=500, overlap=50, chunks=1, nodes=1)
        path.unlink()
        assert not manifest.is_unchanged(path, chunk_size=500, overlap=50)


class TestPersistence:
    def test_round_trip(self, corpus: Path):
        path = corpus / "chapters" / "ch1.md"
        manifest = ContentManifest(corpus)
        manifest.record(
            path, chunk_size=500, overlap=50, chunks=3, nodes=3, node_ids=["a", "b", "c"]
        )
        manifest.save()

        reloaded = ContentManifest.load(corpus)
        assert reloaded.is_unchanged(path, chunk_size=500, overlap=50)
        assert reloaded.node_ids(path) == ["a", "b", "c"]

    def test_saved_at_the_documented_location(self, corpus: Path):
        manifest = ContentManifest(corpus)
        manifest.record(
            corpus / "chapters" / "ch1.md", chunk_size=500, overlap=50, chunks=1, nodes=1
        )
        written = manifest.save()
        assert written == corpus / ".neuralmind" / MANIFEST_FILENAME
        assert written == manifest_path(corpus)
        assert written.exists()

    def test_keys_are_project_relative(self, corpus: Path):
        """Relative keys survive moving or cloning the project."""
        manifest = ContentManifest(corpus)
        manifest.record(
            corpus / "chapters" / "ch1.md", chunk_size=500, overlap=50, chunks=1, nodes=1
        )
        manifest.save()
        payload = json.loads((corpus / ".neuralmind" / MANIFEST_FILENAME).read_text())
        assert list(payload["files"]) == ["chapters/ch1.md"]

    def test_missing_manifest_loads_empty(self, corpus: Path):
        assert len(ContentManifest.load(corpus)) == 0

    def test_corrupt_manifest_loads_empty(self, corpus: Path):
        """A bad manifest costs a full re-ingest, never a crash."""
        target = manifest_path(corpus)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("{not json at all")
        assert len(ContentManifest.load(corpus)) == 0

    def test_future_schema_version_loads_empty(self, corpus: Path):
        target = manifest_path(corpus)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps({"schema_version": 999, "files": {"chapters/ch1.md": {}}}))
        assert len(ContentManifest.load(corpus)) == 0

    def test_save_leaves_no_temp_file(self, corpus: Path):
        manifest = ContentManifest(corpus)
        manifest.record(
            corpus / "chapters" / "ch1.md", chunk_size=500, overlap=50, chunks=1, nodes=1
        )
        manifest.save()
        leftovers = list((corpus / ".neuralmind").glob("*.tmp"))
        assert leftovers == []


class TestPruning:
    def test_prune_returns_keys_and_orphan_node_ids(self, corpus: Path):
        kept = corpus / "chapters" / "ch1.md"
        removed = corpus / "chapters" / "ch2.md"
        manifest = ContentManifest(corpus)
        manifest.record(kept, chunk_size=500, overlap=50, chunks=1, nodes=1, node_ids=["keep-1"])
        manifest.record(
            removed, chunk_size=500, overlap=50, chunks=2, nodes=2, node_ids=["gone-1", "gone-2"]
        )
        removed.unlink()

        gone, orphans = manifest.prune_missing()

        assert gone == ["chapters/ch2.md"]
        assert sorted(orphans) == ["gone-1", "gone-2"]
        assert manifest.node_ids(kept) == ["keep-1"]
        assert len(manifest) == 1

    def test_prune_is_a_noop_when_everything_exists(self, corpus: Path):
        manifest = ContentManifest(corpus)
        manifest.record(
            corpus / "chapters" / "ch1.md", chunk_size=500, overlap=50, chunks=1, nodes=1
        )
        assert manifest.prune_missing() == ([], [])

    def test_forget_drops_a_record(self, corpus: Path):
        path = corpus / "chapters" / "ch1.md"
        manifest = ContentManifest(corpus)
        manifest.record(path, chunk_size=500, overlap=50, chunks=1, nodes=1)
        assert manifest.forget(path) is True
        assert manifest.forget(path) is False
        assert not manifest.is_unchanged(path, chunk_size=500, overlap=50)


class TestSummary:
    def test_summary_aggregates_counts(self, corpus: Path):
        manifest = ContentManifest(corpus)
        manifest.record(
            corpus / "chapters" / "ch1.md", chunk_size=500, overlap=50, chunks=3, nodes=3
        )
        manifest.record(
            corpus / "chapters" / "ch2.md", chunk_size=500, overlap=50, chunks=4, nodes=4
        )
        summary = manifest.summary()
        assert summary["files"] == 2
        assert summary["chunks"] == 7
        assert summary["nodes"] == 7
        assert summary["last_indexed_at"]

    def test_empty_summary_has_no_timestamp(self, corpus: Path):
        summary = ContentManifest(corpus).summary()
        assert summary == {"files": 0, "chunks": 0, "nodes": 0, "last_indexed_at": None}
