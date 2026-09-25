"""Tests for synapse-prose integration — Hebbian learning for book content."""

from __future__ import annotations

from pathlib import Path

from neuralmind.synapse_dynamics import SynapseDynamics
from neuralmind.synapses import SynapseStore


class TestReinforceProse:
    """Tests for SynapseDynamics.reinforce_prose() — Hebbian update for chapters."""

    def _make_store(self, tmp_path: Path) -> SynapseStore:
        db_path = tmp_path / ".neuralmind" / "synapses.db"
        return SynapseStore(db_path)

    def test_reinforce_chapters(self, tmp_path: Path) -> None:
        store = self._make_store(tmp_path)
        dynamics = SynapseDynamics(store)
        assert dynamics.reinforce_prose(["ch01", "ch03", "ch05"]) is True

        # Verify edges were created
        with store._connect() as conn:
            cur = conn.execute("SELECT COUNT(*) FROM synapses")
            count = cur.fetchone()[0]
            assert count > 0

    def test_reinforce_with_sections(self, tmp_path: Path) -> None:
        store = self._make_store(tmp_path)
        dynamics = SynapseDynamics(store)
        assert (
            dynamics.reinforce_prose(
                ["ch01", "ch03"],
                section_ids=["sec-1.1", "sec-3.2"],
            )
            is True
        )

        with store._connect() as conn:
            cur = conn.execute("SELECT COUNT(*) FROM synapses")
            count = cur.fetchone()[0]
            assert count > 0

    def test_reinforce_with_query_terms(self, tmp_path: Path) -> None:
        store = self._make_store(tmp_path)
        dynamics = SynapseDynamics(store)
        assert (
            dynamics.reinforce_prose(
                ["ch01"],
                query_terms=["peptide therapy", "dosage"],
            )
            is True
        )

        with store._connect() as conn:
            cur = conn.execute("SELECT COUNT(*) FROM synapses")
            count = cur.fetchone()[0]
            assert count > 0

    def test_reinforce_empty_chapters(self, tmp_path: Path) -> None:
        store = self._make_store(tmp_path)
        dynamics = SynapseDynamics(store)
        assert dynamics.reinforce_prose([]) is False

    def test_reinforce_caps_query_terms(self, tmp_path: Path) -> None:
        store = self._make_store(tmp_path)
        dynamics = SynapseDynamics(store)
        # 5 query terms — should cap at 3
        assert (
            dynamics.reinforce_prose(
                ["ch01"],
                query_terms=["alpha", "beta", "gamma", "delta", "epsilon"],
            )
            is True
        )

        with store._connect() as conn:
            # Count edges that involve query pseudo-nodes (node_a or node_b)
            cur = conn.execute(
                "SELECT COUNT(*) FROM synapses WHERE node_a LIKE 'query_%' OR node_b LIKE 'query_%'"
            )
            count = cur.fetchone()[0]
            # 4 nodes (ch01 + 3 query terms) → C(4,2) = 6 edges total
            # All 6 edges involve at least one query pseudo-node
            assert count == 6


class TestSpreadProse:
    """Tests for SynapseDynamics.spread_prose() — spreading activation for chapters."""

    def _make_store(self, tmp_path: Path) -> SynapseStore:
        db_path = tmp_path / ".neuralmind" / "synapses.db"
        return SynapseStore(db_path)

    def test_spread_from_seed(self, tmp_path: Path) -> None:
        store = self._make_store(tmp_path)
        dynamics = SynapseDynamics(store)

        # Create a chain: ch01 → ch02 → ch03 → ch04
        store.reinforce(["ch01", "ch02"])
        store.reinforce(["ch02", "ch03"])
        store.reinforce(["ch03", "ch04"])

        results = dynamics.spread_prose(["ch01"], depth=2, top_k=5)
        assert len(results) > 0
        # Spreading activation goes FROM seed TO neighbors — ch01 itself
        # may not be in the results (it's the seed, not a neighbor).
        # We expect ch02 (direct neighbor) and ch03 (2-hop) to be present.
        result_ids = [r[0] for r in results]
        assert "ch02" in result_ids
        assert "ch03" in result_ids

    def test_spread_empty_seeds(self, tmp_path: Path) -> None:
        store = self._make_store(tmp_path)
        dynamics = SynapseDynamics(store)
        assert dynamics.spread_prose([]) == []

    def test_spread_no_edges(self, tmp_path: Path) -> None:
        store = self._make_store(tmp_path)
        dynamics = SynapseDynamics(store)
        # No edges created — spread returns empty
        results = dynamics.spread_prose(["ch01"], depth=2, top_k=5)
        assert results == []
