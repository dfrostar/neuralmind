"""Recovery from an index no turbovec build can decode.

Quarantining an unreadable index is only half a recovery. `embed_nodes`
re-embeds `self.nodes` — the code graph — so anything ingested through
`embed_content` (docs, compliance practices) used to be left behind: its rows
survive in SQLite carrying a `content_hash` that makes the next
`embed_content` skip them, while its vectors no longer exist. Search then
returns nothing for that content, silently, and a document-only store has no
graph for `embed_nodes` to rebuild from at all.

This is the upgrade path users actually hit: turbovec 1.0.0 stopped decoding
pre-v5 indexes, and `neuralmind` does not pin below it.

The index is corrupted here rather than swapped for a real pre-v5 file, so the
test asserts the behaviour on whichever turbovec CI resolves instead of only
on the versions that happen to disagree about a format.
"""

from __future__ import annotations

import pytest

pytest.importorskip("turbovec", reason="turbovec backend not installed")
pytest.importorskip("onnxruntime", reason="needs real embeddings")

from neuralmind.turbovec_backend import TurboVecEmbedder  # noqa: E402

DOCS = [
    {
        "id": "doc_policy_1",
        "label": "AC-2 account management",
        "content_text": "Access control policy: accounts must be reviewed quarterly.",
    },
    {
        "id": "doc_policy_2",
        "label": "AU-6 audit review",
        "content_text": "Audit records are reviewed weekly by the security officer.",
    },
]
QUERY = "quarterly account review"


def _index_path(project):
    return project / "graphify-out" / "neuralmind_turbovec" / "index.tvim"


def _ingest(project):
    emb = TurboVecEmbedder(project)
    try:
        emb.embed_content(DOCS)
        assert [h["id"] for h in emb.search(QUERY, n=3)], "fixture never became searchable"
    finally:
        emb.close()


def test_content_only_store_survives_an_undecodable_index(tmp_path):
    """The case `embed_nodes` cannot reach: ingested content, no code graph."""
    _ingest(tmp_path)

    # What a turbovec major that drops the old on-disk format looks like.
    _index_path(tmp_path).write_bytes(b"not a decodable turbovec index \x00\x01\x02")

    emb = TurboVecEmbedder(tmp_path)
    try:
        assert emb.get_stats()["total_nodes"] == 2, "node rows should survive"
        found = {h["id"] for h in emb.search(QUERY, n=3)}
    finally:
        emb.close()

    assert found == {"doc_policy_1", "doc_policy_2"}, (
        "ingested content became unsearchable after the index was quarantined. "
        "Its SQLite rows still claim it is embedded, so embed_content() skips "
        "it on content_hash and nothing ever rebuilds those vectors."
    )


def test_unreadable_index_is_quarantined_not_deleted(tmp_path):
    # The bad file is kept for diagnosis rather than silently discarded.
    _ingest(tmp_path)
    _index_path(tmp_path).write_bytes(b"corrupt \x00")

    emb = TurboVecEmbedder(tmp_path)
    try:
        emb.search(QUERY, n=1)
    finally:
        emb.close()

    stale = _index_path(tmp_path).with_name("index.tvim.stale")
    assert stale.exists(), "the undecodable index should be kept as .stale"
    assert _index_path(tmp_path).exists(), "a fresh index should have been written"


def test_rebuild_is_a_noop_for_an_empty_store(tmp_path):
    # No rows to rebuild from: recovery must not invent an index or raise.
    emb = TurboVecEmbedder(tmp_path)
    try:
        assert emb._rebuild_index_from_store() == 0
    finally:
        emb.close()
