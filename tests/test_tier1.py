"""Tests for Tier 1 improvements: structural edges, time-based decay,
migration version check.

Stdlib-only, no neuralmind dependencies beyond what test_synapses.py uses.
"""

from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from neuralmind.synapses import (
    DECAY_RATE,
    HALF_LIFE_DAYS,
    LEARNING_RATE,
    LTP_FLOOR,
    LTP_THRESHOLD,
    PRUNE_THRESHOLD,
    RELATION_TO_EDGE_TYPE,
    STRUCTURAL_EDGE_TYPES,
    SynapseStore,
    decay_weight,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _store(tmp_path):
    return SynapseStore(tmp_path / "synapses.db")


# ---------------------------------------------------------------------------
# Structural edges
# ---------------------------------------------------------------------------


class TestStructuralEdges:
    def test_persist_structural_edges_basic(self, tmp_path):
        s = _store(tmp_path)
        edges = [
            {"source": "A", "target": "B", "relation": "calls"},
            {"source": "B", "target": "C", "relation": "imports_from"},
            {"source": "A", "target": "D", "relation": "inherits"},
        ]
        count = s.persist_structural_edges(edges)
        assert count == 3
        assert s.structural_edge_count() == 3

    def test_persist_structural_edges_idempotent(self, tmp_path):
        s = _store(tmp_path)
        edges = [{"source": "A", "target": "B", "relation": "calls"}]
        s.persist_structural_edges(edges)
        s.persist_structural_edges(edges)
        # Should still be 1 row, but call_count incremented
        assert s.structural_edge_count() == 1

    def test_persist_structural_edges_skip_unknown_relations(self, tmp_path):
        s = _store(tmp_path)
        edges = [
            {"source": "A", "target": "B", "relation": "calls"},
            {"source": "A", "target": "C", "relation": "rationale_for"},
            {"source": "A", "target": "D", "relation": "shares_data_with"},
        ]
        count = s.persist_structural_edges(edges)
        assert count == 1  # only 'calls' is persisted

    def test_persist_structural_edges_skip_self_loops(self, tmp_path):
        s = _store(tmp_path)
        edges = [{"source": "A", "target": "A", "relation": "calls"}]
        count = s.persist_structural_edges(edges)
        assert count == 0

    def test_persist_structural_edges_graphify_src_tgt(self, tmp_path):
        s = _store(tmp_path)
        edges = [{"_src": "A", "_tgt": "B", "label": "calls"}]
        count = s.persist_structural_edges(edges)
        assert count == 1

    def test_persist_structural_edges_empty(self, tmp_path):
        s = _store(tmp_path)
        assert s.persist_structural_edges([]) == 0

    def test_structural_edges_survive_rebuild(self, tmp_path):
        db_path = tmp_path / "synapses.db"
        s1 = SynapseStore(db_path)
        edges = [{"source": "A", "target": "B", "relation": "calls"}]
        s1.persist_structural_edges(edges)
        assert s1.structural_edge_count() == 1

        # Reopen same DB
        s2 = SynapseStore(db_path)
        assert s2.structural_edge_count() == 1

    def test_recall_structural_returns_callees(self, tmp_path):
        s = _store(tmp_path)
        edges = [
            {"source": "A", "target": "B", "relation": "calls"},
            {"source": "A", "target": "C", "relation": "calls"},
            {"source": "A", "target": "D", "relation": "imports_from"},
        ]
        s.persist_structural_edges(edges)
        results = s.recall_structural(["A"])
        ids = [nid for nid, _ in results]
        assert "B" in ids
        assert "C" in ids
        assert "D" in ids

    def test_recall_structural_excludes_seeds(self, tmp_path):
        s = _store(tmp_path)
        edges = [{"source": "A", "target": "B", "relation": "calls"}]
        s.persist_structural_edges(edges)
        results = s.recall_structural(["A", "B"])
        ids = [nid for nid, _ in results]
        assert "A" not in ids
        assert "B" not in ids  # B is a seed, excluded

    def test_recall_structural_with_relation_filter(self, tmp_path):
        s = _store(tmp_path)
        edges = [
            {"source": "A", "target": "B", "relation": "calls"},
            {"source": "A", "target": "C", "relation": "imports_from"},
        ]
        s.persist_structural_edges(edges)
        results = s.recall_structural(["A"], relations=["call"])
        ids = [nid for nid, _ in results]
        assert "B" in ids
        assert "C" not in ids

    def test_recall_structural_top_k(self, tmp_path):
        s = _store(tmp_path)
        edges = [{"source": "A", "target": f"X{i}", "relation": "calls"} for i in range(10)]
        s.persist_structural_edges(edges)
        results = s.recall_structural(["A"], top_k=3)
        assert len(results) == 3

    def test_recall_structural_empty(self, tmp_path):
        s = _store(tmp_path)
        assert s.recall_structural(["A"]) == []

    def test_recall_structural_respects_call_count(self, tmp_path):
        s = _store(tmp_path)
        edges = [
            {"source": "A", "target": "B", "relation": "calls"},
            {"source": "A", "target": "C", "relation": "calls"},
        ]
        s.persist_structural_edges(edges)
        # Reinforce B 5 times
        for _ in range(5):
            s.persist_structural_edges([{"source": "A", "target": "B", "relation": "calls"}])
        results = s.recall_structural(["A"])
        # B should rank higher than C due to higher call_count
        assert results[0][0] == "B"


# ---------------------------------------------------------------------------
# Time-based half-life decay
# ---------------------------------------------------------------------------


class TestDecayWeight:
    def test_zero_age_is_identity(self):
        now = time.time()
        assert abs(decay_weight(0.5, now, now=now) - 0.5) < 1e-9

    def test_half_life_math(self):
        # After exactly one half-life, weight should be halved
        now = time.time()
        last = now - HALF_LIFE_DAYS * 86400
        result = decay_weight(1.0, last, now=now)
        assert abs(result - 0.5) < 1e-6

    def test_two_half_lives_quarter(self):
        now = time.time()
        last = now - 2 * HALF_LIFE_DAYS * 86400
        result = decay_weight(1.0, last, now=now)
        assert abs(result - 0.25) < 1e-6

    def test_custom_half_life(self):
        now = time.time()
        last = now - 10 * 86400  # 10 days ago
        result = decay_weight(1.0, last, half_life_days=10.0, now=now)
        assert abs(result - 0.5) < 1e-6

    def test_zero_weight_stays_zero(self):
        assert decay_weight(0.0, time.time()) == 0.0

    def test_negative_weight_returns_zero(self):
        assert decay_weight(-1.0, time.time()) == 0.0

    def test_future_timestamp_unchanged(self):
        now = time.time()
        future = now + 86400
        assert decay_weight(0.5, future, now=now) == 0.5


class TestTimeDecay:
    def test_time_decay_reduces_old_edges(self, tmp_path):
        s = _store(tmp_path)
        # Create an edge with old timestamp
        old_ts = time.time() - 60 * 86400  # 60 days ago
        s.reinforce(["A", "B"], now=old_ts)
        # Create a fresh edge
        s.reinforce(["C", "D"], now=time.time())

        s.decay()

        ab_weight = dict(s.neighbors("A")).get("B", 0)
        cd_weight = dict(s.neighbors("C")).get("D", 1)
        # Old edge should be much smaller than fresh edge
        assert ab_weight < cd_weight

    def test_time_decay_ltp_floor_preserved(self, tmp_path):
        s = _store(tmp_path)
        # Create LTP edge with old timestamp
        old_ts = time.time() - 100 * 86400  # 100 days ago
        for _ in range(LTP_THRESHOLD + 2):
            s.reinforce(["strongA", "strongB"], now=old_ts)

        s.decay()
        weight = dict(s.neighbors("strongA")).get("strongB", 0)
        assert weight >= LTP_FLOOR - 1e-9

    def test_time_decay_prunes_weak_old_edges(self, tmp_path):
        s = _store(tmp_path)
        # Create a weak edge with old timestamp
        old_ts = time.time() - 200 * 86400  # 200 days ago
        s.reinforce(["weakA", "weakB"], now=old_ts)

        s.decay()
        assert "weakB" not in dict(s.neighbors("weakA"))

    def test_time_decay_fresh_edges_unchanged(self, tmp_path):
        s = _store(tmp_path)
        # Create a fresh edge (activated now)
        s.reinforce(["freshA", "freshB"], now=time.time())

        s.decay()
        weight = dict(s.neighbors("freshA")).get("freshB", 0)
        # Fresh edge should be essentially unchanged
        assert abs(weight - LEARNING_RATE) < 1e-6


# ---------------------------------------------------------------------------
# Migration version check
# ---------------------------------------------------------------------------


class TestMigrationCheck:
    def test_warning_fires_on_version_mismatch(self, tmp_path):
        from neuralmind.cli import _check_version_mismatch

        # Create ir_meta.json with old version
        nm_dir = tmp_path / ".neuralmind"
        nm_dir.mkdir()
        meta = {"neuralmind_version": "0.41.0", "ir_version": 1}
        (nm_dir / "ir_meta.json").write_text(json.dumps(meta))

        warning = _check_version_mismatch(str(tmp_path))
        assert warning is not None
        assert "v0.41.0" in warning
        assert "0.45.0" in warning
        assert "reindex" in warning

    def test_no_warning_when_versions_match(self, tmp_path):
        from neuralmind.cli import _check_version_mismatch

        nm_dir = tmp_path / ".neuralmind"
        nm_dir.mkdir()
        meta = {"neuralmind_version": "0.45.0", "ir_version": 1}
        (nm_dir / "ir_meta.json").write_text(json.dumps(meta))

        warning = _check_version_mismatch(str(tmp_path))
        assert warning is None

    def test_no_warning_without_ir_meta(self, tmp_path):
        from neuralmind.cli import _check_version_mismatch

        warning = _check_version_mismatch(str(tmp_path))
        assert warning is None

    def test_no_warning_with_missing_version_field(self, tmp_path):
        from neuralmind.cli import _check_version_mismatch

        nm_dir = tmp_path / ".neuralmind"
        nm_dir.mkdir()
        meta = {"ir_version": 1}  # no neuralmind_version
        (nm_dir / "ir_meta.json").write_text(json.dumps(meta))

        warning = _check_version_mismatch(str(tmp_path))
        assert warning is None

    def test_no_warning_with_malformed_json(self, tmp_path):
        from neuralmind.cli import _check_version_mismatch

        nm_dir = tmp_path / ".neuralmind"
        nm_dir.mkdir()
        (nm_dir / "ir_meta.json").write_text("not json")

        warning = _check_version_mismatch(str(tmp_path))
        assert warning is None


# ---------------------------------------------------------------------------
# Constants sanity
# ---------------------------------------------------------------------------


class TestConstants:
    def test_structural_edge_types_complete(self):
        assert "call" in STRUCTURAL_EDGE_TYPES
        assert "import" in STRUCTURAL_EDGE_TYPES
        assert "inherits" in STRUCTURAL_EDGE_TYPES

    def test_relation_mapping_consistency(self):
        # Every relation in RELATION_TO_EDGE_TYPE should map to a valid edge type
        for rel, edge_type in RELATION_TO_EDGE_TYPE.items():
            assert edge_type in STRUCTURAL_EDGE_TYPES, f"{rel} maps to unknown {edge_type}"

    def test_half_life_constants_positive(self):
        assert HALF_LIFE_DAYS > 0
        assert DECAY_RATE > 0
