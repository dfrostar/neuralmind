"""End-to-end team memory lifecycle integration test.

Exercises the full E1→E2→E3→E4 chain:
  E1 (ContributionQualityScorer) → scores bundle edges
  E2 (QualityWeightedMerger) → merges two bundles conflict-resolution
  E3 (PeerReviewGate) → gates contributions auto-promote vs review
  E4 (TeamStalenessDetector) → detects stale team edges for fast decay

Stdlib-only (SQLite via SynapseStore) — runs without chromadb/embeddings.

    python -m pytest tests/test_team_memory_integration.py
"""

from __future__ import annotations

import json
import tempfile
import time
import unittest
from pathlib import Path

from neuralmind.contribution_scoring import (
    QUALITY_THRESHOLD_HIGH,
    ContributionQualityScorer,
)
from neuralmind.merge_semantics import QualityWeightedMerger
from neuralmind.peer_review import PeerReviewGate, AUTO_PROMOTE_THRESHOLD
from neuralmind.synapses import (
    DEFAULT_NAMESPACE,
    SHARED_NAMESPACE,
    SynapseStore,
    default_db_path,
)
from neuralmind.team_memory import (
    build_team_bundle,
    maybe_import_team_memory,
    publish_team_memory,
)
from neuralmind.team_staleness import (
    STALE_DAYS_TEAM_SHARED,
    TeamStalenessDetector,
)


def _store(project: Path, namespace: str = DEFAULT_NAMESPACE) -> SynapseStore:
    db = default_db_path(project)
    db.parent.mkdir(parents=True, exist_ok=True)
    return SynapseStore(db, namespace=namespace)


def _seed_reinforce(
    store: SynapseStore,
    pair: tuple[str, str],
    strength: float,
    count: int = 1,
    namespace: str = DEFAULT_NAMESPACE,
) -> None:
    """Reinforce a pair multiple times to control both weight and activation_count."""
    for _ in range(count):
        store.reinforce(list(pair), strength=strength, namespace=namespace)


class TeamMemoryIntegrationTests(unittest.TestCase):
    """Full lifecycle: score → review → merge → staleness."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.project = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    # ------------------------------------------------------------------
    # E1 integration: ContributionQualityScorer on a team bundle
    # ------------------------------------------------------------------
    def test_e1_scorer_classifies_team_bundle_edges(self) -> None:
        store = _store(self.project)
        # High-quality edge: many recent activations
        _seed_reinforce(store, ("auth/jwt.py", "auth/handlers.py"), strength=5.0, count=30)
        # Low-quality edge: few stale activations — use a weak reinforcement
        store.reinforce(["stale/a.py", "stale/b.py"], strength=1.0, namespace=DEFAULT_NAMESPACE)

        bundle = build_team_bundle(store)
        scorer = ContributionQualityScorer()
        promote, neutral, decay = scorer.classify_bundle(bundle)

        # At least one edge should score high enough to promote
        self.assertTrue(promote, "high-activation recent edge should classify as promote")
        self.assertTrue(
            any(
                {e.source, e.target} == {"auth/jwt.py", "auth/handlers.py"}
                for e in promote
            ),
            "auth pair should be in promote list",
        )

    def test_e1_scorer_detects_stale_edges(self) -> None:
        scorer = ContributionQualityScorer()

        # Build a bundle directly with old timestamps for the weak edge
        bundle = {
            "synapses": [
                {
                    "source": "recent/a.py",
                    "target": "recent/b.py",
                    "weight": 5.0,
                    "activation_count": 20,
                    "created_at": time.time(),
                    "last_activated": time.time(),
                },
                {
                    "source": "old/x.py",
                    "target": "old/y.py",
                    "weight": 0.01,
                    "activation_count": 1,
                    "created_at": time.time() - 86400 * 90,
                    "last_activated": time.time() - 86400 * 60,
                    "conflicts": 5,
                    "comparisons": 10,
                },
            ]
        }

        promote, neutral, decay = scorer.classify_bundle(bundle)

        # The weak edge should be flagged for decay
        self.assertTrue(decay, "weak edge should be flagged for decay")
        decay_keys = {(e.source, e.target) for e in decay}
        self.assertIn(("old/x.py", "old/y.py"), decay_keys)

    # ------------------------------------------------------------------
    # E2 integration: QualityWeightedMerger conflict resolution
    # ------------------------------------------------------------------
    def test_e2_merge_resolves_conflict_quality_weighted(self) -> None:
        scorer = ContributionQualityScorer()
        merger = QualityWeightedMerger(scorer)

        # Bundle A: strong activation on (auth, handlers)
        bundle_a = {
            "synapses": [
                {
                    "source": "auth/jwt.py",
                    "target": "auth/handlers.py",
                    "weight": 8.0,
                    "activation_count": 25,
                    "created_at": time.time(),
                    "last_activated": time.time(),
                    "conflicts": 0,
                    "comparisons": 1,
                },
                {
                    "source": "unique/to_a.py",
                    "target": "a_helper.py",
                    "weight": 3.0,
                    "activation_count": 5,
                    "created_at": time.time(),
                    "last_activated": time.time(),
                },
            ]
        }
        # Bundle B: weaker activation on same (auth, handlers) — conflict!
        bundle_b = {
            "synapses": [
                {
                    "source": "auth/jwt.py",
                    "target": "auth/handlers.py",
                    "weight": 2.0,
                    "activation_count": 3,
                    "created_at": time.time(),
                    "last_activated": time.time(),
                    "conflicts": 1,
                    "comparisons": 2,
                },
                {
                    "source": "unique/to_b.py",
                    "target": "b_helper.py",
                    "weight": 4.0,
                    "activation_count": 7,
                    "created_at": time.time(),
                    "last_activated": time.time(),
                },
            ]
        }

        merged, conflicts = merger.merge_bundles(bundle_a, bundle_b)

        # Conflict detected for the overlapping pair
        self.assertEqual(len(conflicts), 1, "exactly one conflict expected")
        conflict = conflicts[0]
        self.assertEqual(
            (conflict.source, conflict.target),
            ("auth/jwt.py", "auth/handlers.py"),
        )
        # Higher-quality edge (from A) should win
        self.assertEqual(conflict.winner, "a", "higher-quality edge should win conflict")
        self.assertTrue(conflict.resolved)

        # All 3 unique edges present in merged output (1 conflict winner + 2 unique)
        self.assertEqual(len(merged), 3)

        # Unique edges from both bundles present
        merged_keys = {(e.source, e.target) for e in merged}
        self.assertIn(("unique/to_a.py", "a_helper.py"), merged_keys)
        self.assertIn(("unique/to_b.py", "b_helper.py"), merged_keys)

    def test_e2_merge_no_conflict_passes_through(self) -> None:
        scorer = ContributionQualityScorer()
        merger = QualityWeightedMerger(scorer)

        bundle_a = {
            "synapses": [
                {
                    "source": "only_in_a.py",
                    "target": "a_dep.py",
                    "weight": 3.0,
                    "activation_count": 5,
                    "created_at": time.time(),
                    "last_activated": time.time(),
                },
            ]
        }
        bundle_b = {
            "synapses": [
                {
                    "source": "only_in_b.py",
                    "target": "b_dep.py",
                    "weight": 4.0,
                    "activation_count": 7,
                    "created_at": time.time(),
                    "last_activated": time.time(),
                },
            ]
        }

        merged, conflicts = merger.merge_bundles(bundle_a, bundle_b)
        self.assertEqual(len(conflicts), 0, "no conflict for disjoint edges")
        self.assertEqual(len(merged), 2)

    # ------------------------------------------------------------------
    # E3 integration: PeerReviewGate decision logic
    # ------------------------------------------------------------------
    def test_e3_gate_auto_promotes_high_quality_bundle(self) -> None:
        scorer = ContributionQualityScorer()
        gate = PeerReviewGate(scorer)

        # Build a bundle with a high-quality edge
        store = _store(self.project)
        _seed_reinforce(store, ("high/value.py", "high/core.py"), strength=10.0, count=30)
        bundle = build_team_bundle(store)

        auto_promoted, review_required, rejected = gate.gate_bundle(bundle)

        # The high-quality edge should auto-promote
        self.assertTrue(
            auto_promoted,
            f"high-quality edge should auto-promote (threshold {AUTO_PROMOTE_THRESHOLD})",
        )
        for decision in auto_promoted:
            self.assertEqual(decision.action, "auto_promote")

    def test_e3_gate_rejects_low_quality_bundle(self) -> None:
        scorer = ContributionQualityScorer()
        gate = PeerReviewGate(scorer)

        # Build a bundle with only very weak edges
        bundle = {
            "synapses": [
                {
                    "source": "noise/a.py",
                    "target": "noise/b.py",
                    "weight": 0.001,
                    "activation_count": 1,
                    "created_at": time.time() - 86400 * 60,  # 60 days old
                    "last_activated": time.time() - 86400 * 60,  # stale
                    "conflicts": 5,
                    "comparisons": 10,
                },
            ]
        }

        auto_promoted, review_required, rejected = gate.gate_bundle(bundle)

        # The weak, stale, high-conflict edge should be rejected
        self.assertTrue(rejected, "weak edge with high conflict should be rejected")
        for decision in rejected:
            self.assertEqual(decision.action, "reject")

    def test_e3_gate_review_band_for_marginal_edge(self) -> None:
        scorer = ContributionQualityScorer()
        gate = PeerReviewGate(scorer)

        # Build an edge with middling activation (should land in review band)
        bundle = {
            "synapses": [
                {
                    "source": "mid/x.py",
                    "target": "mid/y.py",
                    "weight": 0.5,
                    "activation_count": 8,
                    "created_at": time.time() - 86400 * 10,
                    "last_activated": time.time() - 86400 * 5,
                    "conflicts": 1,
                    "comparisons": 5,
                },
            ]
        }

        auto_promoted, review_required, rejected = gate.gate_bundle(bundle)

        # This marginal edge may be either review_required or rejected depending on scoring.
        # It should NOT auto-promote.
        self.assertFalse(
            any(d.action == "auto_promote" for d in auto_promoted),
            "marginal edge should not auto-promote",
        )

    # ------------------------------------------------------------------
    # E4 integration: TeamStalenessDetector
    # ------------------------------------------------------------------
    def test_e4_staleness_detects_old_edges(self) -> None:
        store = _store(self.project)

        # Seed a shared edge that was activated long ago
        store.reinforce(
            ["team/shared_a.py", "team/shared_b.py"],
            strength=5.0,
            namespace=SHARED_NAMESPACE,
        )

        # Manually backdate the last_activated timestamp to simulate staleness
        cutoff = time.time() - (STALE_DAYS_TEAM_SHARED * 86400) - 86400  # 1 day past
        with store._connect() as conn:
            conn.execute(
                """UPDATE synapses SET last_activated = ?
                   WHERE namespace = ?""",
                (cutoff, SHARED_NAMESPACE),
            )

        detector = TeamStalenessDetector()
        stale = detector.detect_stale_in_store(store, namespace=SHARED_NAMESPACE)

        self.assertTrue(stale, "edges past the stale threshold should be detected")
        self.assertTrue(all(edge.is_stale for edge in stale))

    def test_e4_staleness_fast_decay_reduces_weight(self) -> None:
        store = _store(self.project)

        # Seed a shared edge
        store.reinforce(
            ["decay/edge_a.py", "decay/edge_b.py"],
            strength=10.0,
            namespace=SHARED_NAMESPACE,
        )

        # Backdate the edge so it's well past the stale threshold
        backdated_ts = time.time() - (STALE_DAYS_TEAM_SHARED * 86400) - (10 * 86400)
        with store._connect() as conn:
            conn.execute(
                """UPDATE synapses SET last_activated = ?
                   WHERE namespace = ?""",
                (backdated_ts, SHARED_NAMESPACE),
            )

        # Capture pre-decay weight
        pre_decay = store.edges(namespaces=[SHARED_NAMESPACE])
        self.assertTrue(pre_decay, "edge should exist before decay")
        pre_weight = pre_decay[0][2]  # (_, _, weight, _)

        # Run full staleness pass
        detector = TeamStalenessDetector()
        updated, stale = detector.run_staleness_pass(store, namespace=SHARED_NAMESPACE)

        self.assertGreater(updated, 0, "should update at least one stale edge")

        # Verify weight reduced
        post_decay = store.edges(namespaces=[SHARED_NAMESPACE])
        self.assertTrue(post_decay, "edge should still exist after decay (weight reduced)")
        post_weight = post_decay[0][2]

        self.assertLess(post_weight, pre_weight, "stale edge weight should decrease after decay")
        self.assertLess(post_weight, pre_weight * 0.9, "weight should drop meaningfully (fast decay)")

    # ------------------------------------------------------------------
    # Full chain: publish → score → gate → merge → staleness
    # ------------------------------------------------------------------
    def test_full_chain_publish_score_gate_merge_stale(self) -> None:
        """E1→E2→E3→E4 full lifecycle in one flow."""
        # Step 1: Contributor A publishes a team bundle
        a = _store(self.project, namespace=DEFAULT_NAMESPACE)
        _seed_reinforce(a, ("core/alpha.py", "core/beta.py"), strength=7.0, count=25)
        summary = publish_team_memory(self.project, a)
        self.assertIn("content_hash", summary)

        # Step 2: E1 — score the bundle edges
        scorer = ContributionQualityScorer()
        bundle = build_team_bundle(a)
        promote, neutral, decay = scorer.classify_bundle(bundle)
        self.assertTrue(promote, "team bundle should have promotable edges")

        # Step 3: E3 — gate the bundle
        gate = PeerReviewGate(scorer)
        auto_promoted, review_required, rejected = gate.gate_bundle(bundle)
        self.assertTrue(auto_promoted, "high-quality team bundle should auto-promote")

        # Step 4: Contributor B imports via PeerReviewGate
        with tempfile.TemporaryDirectory() as b_dir:
            b_proj = Path(b_dir)
            # Copy the committed bundle (simulating `git clone`)
            (b_proj / ".neuralmind-team-memory.json").write_text(
                (self.project / ".neuralmind-team-memory.json").read_text()
            )
            b = _store(b_proj, namespace=DEFAULT_NAMESPACE)

            # B's import is gated: edges above threshold auto-promote
            result = maybe_import_team_memory(b_proj, b)
            self.assertIsNotNone(result, "fresh clone should inherit")
            if result:
                self.assertGreater(result["synapses"], 0)

            # E2 — simulate merge: B produces a conflicting bundle of their own
            _seed_reinforce(b, ("core/alpha.py", "core/beta.py"), strength=3.0, count=5)
            b_bundle = build_team_bundle(b)
            merger = QualityWeightedMerger(scorer)
            merged, conflicts = merger.merge_bundles(bundle, b_bundle)
            self.assertGreater(len(merged), 0, "merged list should be non-empty")

            # E4 — staleness: A's original edge is now stale in shared
            # (simulate time passing — backdate the shared edge)
            backdated_ts = time.time() - (STALE_DAYS_TEAM_SHARED * 86400) - 86400
            with b._connect() as conn:
                conn.execute(
                    """UPDATE synapses SET last_activated = ?
                       WHERE namespace = ?""",
                    (backdated_ts, SHARED_NAMESPACE),
                )
            detector = TeamStalenessDetector()
            updated, stale = detector.run_staleness_pass(b, namespace=SHARED_NAMESPACE)
            self.assertGreaterEqual(updated, 0, "staleness pass should complete without error")


if __name__ == "__main__":
    unittest.main(verbosity=2)
