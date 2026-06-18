"""Team-memory publish / inherit roundtrip.

stdlib-only (sqlite via SynapseStore) — runs without chromadb/embeddings, like
the rest of the synapse-layer tests.

    python -m pytest tests/test_team_memory.py
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from neuralmind.synapses import DEFAULT_NAMESPACE, SHARED_NAMESPACE, SynapseStore, default_db_path
from neuralmind.team_memory import (
    TEAM_BUNDLE_FILENAME,
    build_team_bundle,
    maybe_import_team_memory,
    publish_team_memory,
    team_bundle_path,
)


def _store(project: Path, namespace: str = DEFAULT_NAMESPACE) -> SynapseStore:
    db = default_db_path(project)
    db.parent.mkdir(parents=True, exist_ok=True)
    return SynapseStore(db, namespace=namespace)


class TeamMemoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.project = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _seed(self, store: SynapseStore) -> None:
        # Three co-edited modules → a triangle of personal synapses.
        store.reinforce(
            ["auth/handlers.py", "auth/jwt_utils.py", "users/crud.py"],
            strength=3.0,
            namespace=DEFAULT_NAMESPACE,
        )

    def test_publish_writes_committed_bundle_at_root(self) -> None:
        store = _store(self.project)
        self._seed(store)
        summary = publish_team_memory(self.project, store)

        path = team_bundle_path(self.project)
        self.assertEqual(path.name, TEAM_BUNDLE_FILENAME)
        self.assertEqual(path.parent, self.project)  # repo root, not under .neuralmind/
        self.assertTrue(path.exists())
        self.assertGreater(summary["counts"]["synapses"], 0)

        bundle = json.loads(path.read_text())
        self.assertEqual(bundle["namespace"], SHARED_NAMESPACE)  # imports into shared
        self.assertIn("content_hash", bundle)
        self.assertIn("provenance", bundle)

    def test_fresh_clone_inherits_into_shared_only(self) -> None:
        # Engineer A publishes from their personal memory.
        a = _store(self.project)
        self._seed(a)
        publish_team_memory(self.project, a)

        # Engineer B: a fresh clone (new DB) with no learned memory.
        with tempfile.TemporaryDirectory() as b_dir:
            b_proj = Path(b_dir)
            # Copy only the committed bundle (as `git clone` would).
            (b_proj / TEAM_BUNDLE_FILENAME).write_text(team_bundle_path(self.project).read_text())
            b = _store(b_proj)

            result = maybe_import_team_memory(b_proj, b)
            self.assertIsNotNone(result)
            self.assertGreater(result["synapses"], 0)

            # Inherited edges land in `shared`, not `personal`.
            shared = b.edges(namespaces=[SHARED_NAMESPACE])
            personal = b.edges(namespaces=[DEFAULT_NAMESPACE])
            self.assertTrue(shared, "inherited edges should be in the shared namespace")
            self.assertFalse(personal, "personal namespace must be untouched")

    def test_import_is_idempotent_by_content_hash(self) -> None:
        a = _store(self.project)
        self._seed(a)
        publish_team_memory(self.project, a)

        # A fresh clone (separate db) inherits; a second pass is a no-op.
        with tempfile.TemporaryDirectory() as b_dir:
            b_proj = Path(b_dir)
            (b_proj / TEAM_BUNDLE_FILENAME).write_text(team_bundle_path(self.project).read_text())
            b = _store(b_proj)
            first = maybe_import_team_memory(b_proj, b)
            self.assertIsNotNone(first)
            second = maybe_import_team_memory(b_proj, b)
            self.assertIsNone(second, "re-importing the same bundle must be a no-op")

    def test_publisher_does_not_reimport_own_bundle(self) -> None:
        # Publishing records the bundle hash, so the same machine won't
        # re-inherit what it just published (no self-pollution of `shared`).
        store = _store(self.project)
        self._seed(store)
        publish_team_memory(self.project, store)
        self.assertIsNone(maybe_import_team_memory(self.project, store))

    def test_off_switch_disables_inheritance(
        self,
    ) -> None:
        a = _store(self.project)
        self._seed(a)
        publish_team_memory(self.project, a)

        import os

        with tempfile.TemporaryDirectory() as b_dir:
            b_proj = Path(b_dir)
            (b_proj / TEAM_BUNDLE_FILENAME).write_text(team_bundle_path(self.project).read_text())
            b = _store(b_proj)
            os.environ["NEURALMIND_TEAM_MEMORY"] = "0"
            try:
                self.assertIsNone(maybe_import_team_memory(b_proj, b))
                self.assertFalse(b.edges(namespaces=[SHARED_NAMESPACE]))
            finally:
                del os.environ["NEURALMIND_TEAM_MEMORY"]

    def test_missing_or_corrupt_bundle_is_fail_open(self) -> None:
        b = _store(self.project)
        # No bundle present.
        self.assertIsNone(maybe_import_team_memory(self.project, b))
        # Corrupt bundle.
        team_bundle_path(self.project).write_text("{ not json")
        self.assertIsNone(maybe_import_team_memory(self.project, b))

    def test_malformed_entries_without_hash_are_fail_open(self) -> None:
        # A valid JSON object whose entries lack source/target and carries no
        # precomputed content_hash must be a silent no-op, not an exception.
        b = _store(self.project)
        team_bundle_path(self.project).write_text(
            json.dumps({"format": "neuralmind.synapses", "synapses": [{"weight": 1.0}]})
        )
        self.assertIsNone(maybe_import_team_memory(self.project, b))

    def test_meta_write_failure_keeps_successful_import(self) -> None:
        # If recording the idempotency hash fails *after* a successful import,
        # the import summary must survive — a meta-write failure can't discard
        # the inherited edges.
        a = _store(self.project)
        self._seed(a)
        publish_team_memory(self.project, a)

        with tempfile.TemporaryDirectory() as b_dir:
            b_proj = Path(b_dir)
            (b_proj / TEAM_BUNDLE_FILENAME).write_text(team_bundle_path(self.project).read_text())
            b = _store(b_proj)

            original = b.set_meta

            def _boom(*args, **kwargs):  # noqa: ANN002, ANN003
                raise RuntimeError("meta table is read-only")

            b.set_meta = _boom  # type: ignore[method-assign]
            try:
                result = maybe_import_team_memory(b_proj, b)
            finally:
                b.set_meta = original  # type: ignore[method-assign]
            self.assertIsNotNone(result)
            self.assertGreater(result["synapses"], 0)
            self.assertTrue(b.edges(namespaces=[SHARED_NAMESPACE]))

    def test_build_preserves_per_field_maxima(self) -> None:
        # personal asserts a high activation_count at a modest weight; shared
        # asserts a high weight at a single activation for the SAME pair. The
        # bundle must keep BOTH maxima, not the whole higher-weight entry (which
        # would drop the larger count and weaken post-import LTP/decay).
        store = _store(self.project)
        for _ in range(10):
            store.reinforce(["mod/a.py", "mod/b.py"], strength=1.0, namespace=DEFAULT_NAMESPACE)
        store.reinforce(["mod/a.py", "mod/b.py"], strength=50.0, namespace=SHARED_NAMESPACE)

        bundle = build_team_bundle(store)
        pair = next(
            e for e in bundle["synapses"] if {e["source"], e["target"]} == {"mod/a.py", "mod/b.py"}
        )
        rows = store.edges(namespaces=[DEFAULT_NAMESPACE]) + store.edges(
            namespaces=[SHARED_NAMESPACE]
        )
        max_weight = max(w for *_e, w, _c in rows)
        max_count = max(c for *_e, _w, c in rows)
        self.assertAlmostEqual(pair["weight"], max_weight, places=6)
        self.assertEqual(pair["activation_count"], max_count)

    def test_content_hash_stable_across_republish(self) -> None:
        store = _store(self.project)
        self._seed(store)
        h1 = build_team_bundle(store)["content_hash"]
        h2 = build_team_bundle(store)["content_hash"]
        self.assertEqual(h1, h2, "same learned content must hash identically")


if __name__ == "__main__":
    unittest.main(verbosity=2)
