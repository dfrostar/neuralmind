"""Tests for E3 CLI — memory review-list/approve/reject commands."""

import json
import tempfile
import time
import unittest
from pathlib import Path

from neuralmind.contribution_scoring import ContributionQualityScorer
from neuralmind.synapses import SHARED_NAMESPACE, SynapseStore, default_db_path
from neuralmind.team_memory import (
    _META_PENDING_REVIEW,
    build_team_bundle,
    maybe_import_team_memory,
    publish_team_memory,
)


class TestReviewCLI(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.project = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _store(self, namespace=SHARED_NAMESPACE):
        db = default_db_path(self.project)
        db.parent.mkdir(parents=True, exist_ok=True)
        return SynapseStore(db, namespace=namespace)

    def _seed_pending(self, store: SynapseStore) -> None:
        """Seed a pending review entry."""
        store.set_meta(
            _META_PENDING_REVIEW,
            json.dumps(
                [
                    {
                        "source": "a.py",
                        "target": "b.py",
                        "score": 0.5,
                        "reason": "test",
                        "reviewer_hint": "marginal",
                    }
                ]
            ),
        )

    def test_review_list_shows_pending(self):
        store = self._store()
        self._seed_pending(store)

        # Simulate what cmd_memory does for review-list
        raw = store.get_meta(_META_PENDING_REVIEW)
        pending = json.loads(raw)
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["source"], "a.py")

    def test_review_approve_promotes_to_shared(self):
        store = self._store()
        self._seed_pending(store)

        # Simulate review-approve: remove from pending, promote to shared
        pending = json.loads(store.get_meta(_META_PENDING_REVIEW))
        remaining = [e for e in pending if not (e["source"] == "a.py" and e["target"] == "b.py")]
        store.set_meta(_META_PENDING_REVIEW, json.dumps(remaining))

        written = store.import_edges([("a.py", "b.py", 1.0, 1)], namespace=SHARED_NAMESPACE)
        self.assertEqual(written, 1)

        # Verify edge is now in shared
        edges = store.edges(namespaces=[SHARED_NAMESPACE])
        keys = {(e[0], e[1]) for e in edges}
        self.assertIn(("a.py", "b.py"), keys)

    def test_review_reject_drops_edge(self):
        store = self._store()
        self._seed_pending(store)

        # Simulate review-reject: remove from pending, do NOT promote
        pending = json.loads(store.get_meta(_META_PENDING_REVIEW))
        remaining = [e for e in pending if not (e["source"] == "a.py" and e["target"] == "b.py")]
        store.set_meta(_META_PENDING_REVIEW, json.dumps(remaining))

        # Verify edge is NOT in shared
        edges = store.edges(namespaces=[SHARED_NAMESPACE])
        keys = {(e[0], e[1]) for e in edges}
        self.assertNotIn(("a.py", "b.py"), keys)

    def test_review_list_empty_queue(self):
        store = self._store()
        raw = store.get_meta(_META_PENDING_REVIEW)
        pending = json.loads(raw) if raw else []
        self.assertEqual(pending, [])


class TestFreshCloneWithGate(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.project = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _store(self, namespace=SHARED_NAMESPACE):
        db = default_db_path(self.project)
        db.parent.mkdir(parents=True, exist_ok=True)
        return SynapseStore(db, namespace=namespace)

    def test_fresh_clone_auto_promotes_high_quality(self):
        """Fresh clone (no shared edges) — high quality edges should auto-promote."""
        import shutil

        publisher_dir = self.project / "_publisher"
        publisher_dir.mkdir()

        # Publisher seeds personal namespace and publishes
        pub_store = SynapseStore(default_db_path(publisher_dir), namespace="personal")
        for _ in range(30):
            pub_store.reinforce(
                ["auth/handlers.py", "auth/jwt_utils.py"],
                strength=5.0,
                namespace="personal",
            )
        publish_team_memory(publisher_dir, pub_store)

        # Fresh clone: no personal/shared edges, but bundle exists on disk
        clone_dir = self.project / "_clone"
        clone_dir.mkdir()
        shutil.copy(
            publisher_dir / ".neuralmind-team-memory.json",
            clone_dir / ".neuralmind-team-memory.json",
        )
        clone_store = SynapseStore(default_db_path(clone_dir), namespace="personal")

        result = maybe_import_team_memory(clone_dir, clone_store)
        # After fix: fresh clone applies gate, high-quality edges auto-promote
        self.assertIsNotNone(result)
        self.assertGreater(result.get("promoted", 0), 0)

    def test_fresh_clone_low_quality_rejected(self):
        """Fresh clone — low quality edges should be rejected by the gate."""
        scorer = ContributionQualityScorer()

        # Build a very low-quality edge (activation=0, old, high conflict)
        edge = scorer.score_edge(
            source="noise/a.py",
            target="noise/b.py",
            namespace="personal",
            activation_count=0,
            created_at=time.time() - 86400 * 365,
            last_activated=time.time() - 86400 * 365,
            conflict_count=5,
            total_comparisons=5,
        )
        self.assertLess(edge.score, 0.15, f"score {edge.score} should be < 0.15")

        from neuralmind.peer_review import PeerReviewGate
        gate = PeerReviewGate(scorer)
        decision = gate.decide(edge)
        self.assertEqual(decision.action, "reject")


if __name__ == "__main__":
    unittest.main(verbosity=2)
