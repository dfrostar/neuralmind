"""Tests for Tier 1 improvements: structural edges persistence, time-based
decay, migration version check.

Stdlib-only, no neuralmind dependencies beyond what test_synapses.py uses.
"""

from __future__ import annotations

import json
import time

from neuralmind.synapses import (
    HALF_LIFE_DAYS,
    LEARNING_RATE,
    LTP_FLOOR,
    LTP_THRESHOLD,
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


def _count_structural_edges(store: SynapseStore) -> int:
    with store._connect() as conn:
        return conn.execute("SELECT COUNT(*) FROM structural_edges").fetchone()[0]


# ---------------------------------------------------------------------------
# Structural edges persistence
# ---------------------------------------------------------------------------


class TestStructuralEdges:
    def test_persist_basic(self, tmp_path):
        s = _store(tmp_path)
        edges = [
            {"source": "A", "target": "B", "relation": "calls"},
            {"source": "B", "target": "C", "relation": "imports_from"},
            {"source": "A", "target": "D", "relation": "inherits"},
        ]
        count = s.persist_structural_edges(edges)
        assert count == 3
        assert _count_structural_edges(s) == 3

    def test_persist_idempotent(self, tmp_path):
        s = _store(tmp_path)
        edges = [{"source": "A", "target": "B", "relation": "calls"}]
        s.persist_structural_edges(edges)
        s.persist_structural_edges(edges)
        # Re-upsert should increment call_count, not add new rows
        assert _count_structural_edges(s) == 1

    def test_persist_skip_unknown_relations(self, tmp_path):
        s = _store(tmp_path)
        edges = [
            {"source": "A", "target": "B", "relation": "calls"},
            {"source": "A", "target": "C", "relation": "rationale_for"},
            {"source": "A", "target": "D", "relation": "shares_data_with"},
        ]
        count = s.persist_structural_edges(edges)
        assert count == 1  # only 'calls' is persisted

    def test_persist_skip_self_loops(self, tmp_path):
        s = _store(tmp_path)
        edges = [{"source": "A", "target": "A", "relation": "calls"}]
        count = s.persist_structural_edges(edges)
        assert count == 0

    def test_persist_graphify_src_tgt_keys(self, tmp_path):
        s = _store(tmp_path)
        edges = [{"_src": "A", "_tgt": "B", "label": "calls"}]
        count = s.persist_structural_edges(edges)
        assert count == 1

    def test_persist_empty(self, tmp_path):
        s = _store(tmp_path)
        assert s.persist_structural_edges([]) == 0

    def test_persist_survives_reopen(self, tmp_path):
        db_path = tmp_path / "synapses.db"
        s1 = SynapseStore(db_path)
        edges = [{"source": "A", "target": "B", "relation": "calls"}]
        s1.persist_structural_edges(edges)
        assert _count_structural_edges(s1) == 1
        s2 = SynapseStore(db_path)
        assert _count_structural_edges(s2) == 1


# ---------------------------------------------------------------------------
# Time-based half-life decay
# ---------------------------------------------------------------------------


class TestDecayWeight:
    def test_zero_age_is_identity(self):
        now = time.time()
        assert abs(decay_weight(0.5, now, now=now) - 0.5) < 1e-9

    def test_half_life_math(self):
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
        last = now - 10 * 86400
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
    def test_reduces_old_edges(self, tmp_path):
        s = _store(tmp_path)
        old_ts = time.time() - 60 * 86400
        s.reinforce(["A", "B"], now=old_ts)
        s.reinforce(["C", "D"], now=time.time())
        s.decay()
        ab = dict(s.neighbors("A")).get("B", 0)
        cd = dict(s.neighbors("C")).get("D", 1)
        assert ab < cd

    def test_ltp_floor_preserved(self, tmp_path):
        s = _store(tmp_path)
        old_ts = time.time() - 100 * 86400
        for _ in range(LTP_THRESHOLD + 2):
            s.reinforce(["strongA", "strongB"], now=old_ts)
        s.decay()
        weight = dict(s.neighbors("strongA")).get("strongB", 0)
        assert weight >= LTP_FLOOR - 1e-9

    def test_prunes_weak_old_edges(self, tmp_path):
        s = _store(tmp_path)
        old_ts = time.time() - 200 * 86400
        s.reinforce(["weakA", "weakB"], now=old_ts)
        s.decay()
        assert "weakB" not in dict(s.neighbors("weakA"))

    def test_fresh_edges_unchanged(self, tmp_path):
        s = _store(tmp_path)
        s.reinforce(["freshA", "freshB"], now=time.time())
        s.decay()
        weight = dict(s.neighbors("freshA")).get("freshB", 0)
        assert abs(weight - LEARNING_RATE) < 1e-6


# ---------------------------------------------------------------------------
# Migration version check
# ---------------------------------------------------------------------------


class TestMigrationCheck:
    def test_warning_fires_on_version_mismatch(self, tmp_path):
        from neuralmind.cli import _check_version_mismatch

        nm_dir = tmp_path / ".neuralmind"
        nm_dir.mkdir()
        meta = {"neuralmind_version": "0.41.0", "ir_version": 1}
        (nm_dir / "ir_meta.json").write_text(json.dumps(meta))

        warning = _check_version_mismatch(str(tmp_path))
        assert warning is not None
        assert "v0.41.0" in warning
        # Version mismatch message should mention reindex.
        assert "reindex" in warning

    def test_no_warning_when_versions_match(self, tmp_path):
        import neuralmind
        from neuralmind.cli import _check_version_mismatch

        nm_dir = tmp_path / ".neuralmind"
        nm_dir.mkdir()
        # Use the real in-repo version to ensure a match.
        meta = {"neuralmind_version": neuralmind.__version__, "ir_version": 1}
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
        meta = {"ir_version": 1}
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
        for rel, edge_type in RELATION_TO_EDGE_TYPE.items():
            assert edge_type in STRUCTURAL_EDGE_TYPES, f"{rel} maps to unknown {edge_type}"

    def test_half_life_constants_positive(self):
        assert HALF_LIFE_DAYS > 0
