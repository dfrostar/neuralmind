"""Tests for selector auto-tuning (self-improvement engine, subsystem A)."""

from __future__ import annotations

import json

from neuralmind import self_improve
from neuralmind.memory import project_query_events_file
from neuralmind.self_improve import (
    L2_RECALL_K_DEFAULT,
    L2_RECALL_K_MAX,
    L2_RECALL_K_MIN,
    META_KEY,
    META_KEY_TUNED_AT,
    WINDOW_MIN_EVENTS,
    _decide,
    selector_report,
    tune_selector,
)
from neuralmind.synapses import SynapseStore, default_db_path


def _write_events(project_path, events):
    """Write query events straight to the JSONL file the tuner reads."""
    path = project_query_events_file(project_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for e in events:
            f.write(json.dumps(e) + "\n")


def _query_events(n, *, session_id="s", communities, ts="2026-05-07T00:00:00+00:00"):
    """n query events in one session, all with the same communities_loaded.

    Identical communities → every consecutive pair fully overlaps →
    re_query_rate == 1.0 (when n >= 2).
    """
    return [
        {
            "event_type": "query",
            "timestamp": ts,
            "session_id": session_id,
            "retrieval_summary": {
                "layers_used": ["L0:Identity", "L1:Summary", "L2:OnDemand(3 clusters)"],
                "communities_loaded": list(communities),
            },
        }
        for _ in range(n)
    ]


# --- _decide: the pure tuning rule ------------------------------------------


def test_decide_raises_above_high_threshold():
    assert _decide(3, 0.9) == (4, "raised")


def test_decide_lowers_below_low_threshold():
    assert _decide(3, 0.0) == (2, "lowered")


def test_decide_holds_in_dead_band():
    assert _decide(3, 0.25) == (3, "dead_band")


def test_decide_caps_at_max():
    assert _decide(L2_RECALL_K_MAX, 0.9) == (L2_RECALL_K_MAX, "at_max")


def test_decide_floors_at_min():
    assert _decide(L2_RECALL_K_MIN, 0.0) == (L2_RECALL_K_MIN, "at_min")


# --- tune_selector: integration ---------------------------------------------


def test_warmup_gate_blocks_tuning_below_threshold(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    # 10 events — well under WARMUP_MIN_EVENTS.
    _write_events(project, _query_events(10, communities=[1]))

    result = tune_selector(project)

    assert result["changed"] is False
    assert result["reason"] == "warmup"
    store = SynapseStore(default_db_path(project))
    assert store.get_meta(META_KEY) is None


def test_raise_path_persists_higher_k(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    # 60 identical-community queries → re_query_rate == 1.0 → raise.
    _write_events(project, _query_events(60, communities=[1, 2]))

    result = tune_selector(project)

    assert result["changed"] is True
    assert result["reason"] == "raised"
    assert result["old"] == L2_RECALL_K_DEFAULT
    assert result["new"] == L2_RECALL_K_DEFAULT + 1
    store = SynapseStore(default_db_path(project))
    assert store.get_meta(META_KEY) == str(L2_RECALL_K_DEFAULT + 1)
    assert store.get_meta(META_KEY_TUNED_AT) is not None


def test_lower_path_persists_lower_k(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    # 60 queries each touching a distinct community → no overlap → rate 0.0.
    events = [
        _query_events(1, session_id="s", communities=[i])[0] for i in range(60)
    ]
    _write_events(project, events)

    result = tune_selector(project)

    assert result["changed"] is True
    assert result["reason"] == "lowered"
    assert result["new"] == L2_RECALL_K_DEFAULT - 1
    store = SynapseStore(default_db_path(project))
    assert store.get_meta(META_KEY) == str(L2_RECALL_K_DEFAULT - 1)


def test_step_is_bounded_to_one_per_tick(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    _write_events(project, _query_events(60, communities=[1]))
    # Pre-seed k at the default; one tick must move it by exactly 1.
    store = SynapseStore(default_db_path(project))
    store.set_meta(META_KEY, "3")

    result = tune_selector(project)
    assert result["new"] == 4


def test_windowing_uses_last_tuned_at_timestamp(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    # 40 old low-overlap events + 40 recent high-overlap events.
    old = [
        _query_events(1, session_id="old", communities=[i], ts="2026-01-01T00:00:00+00:00")[0]
        for i in range(40)
    ]
    recent = _query_events(40, communities=[7], ts="2026-06-01T00:00:00+00:00")
    _write_events(project, old + recent)

    store = SynapseStore(default_db_path(project))
    # Last tune happened between the two batches — only recent events count.
    store.set_meta(META_KEY_TUNED_AT, "2026-03-01T00:00:00+00:00")

    result = tune_selector(project)
    # Window is the 40 recent high-overlap events, not all 80.
    assert result["events"] == 40
    assert result["reason"] == "raised"


def test_empty_window_after_tune_holds_instead_of_lowering(tmp_path):
    """Regression: right after a tune, the window (keyed off the tune
    timestamp) is empty until fresh events arrive. An empty window is
    'no signal' — the tuner must hold, not read re_query_rate 0.0 as a
    reason to lower k."""
    project = tmp_path / "project"
    project.mkdir()
    _write_events(project, _query_events(60, communities=[1], ts="2026-05-07T00:00:00+00:00"))

    store = SynapseStore(default_db_path(project))
    # Last tune is dated *after* every logged event → window is empty.
    store.set_meta(META_KEY_TUNED_AT, "2026-09-01T00:00:00+00:00")
    store.set_meta(META_KEY, "4")

    result = tune_selector(project)
    assert result["changed"] is False
    assert result["reason"] == "insufficient_recent"
    assert store.get_meta(META_KEY) == "4"  # untouched


def test_insufficient_recent_events_holds(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    # 60 total events (passes warm-up) but fewer than WINDOW_MIN_EVENTS
    # fall inside the post-tune window.
    old = _query_events(
        55, session_id="old", communities=[1], ts="2026-01-01T00:00:00+00:00"
    )
    recent = _query_events(
        WINDOW_MIN_EVENTS - 1, communities=[1], ts="2026-06-01T00:00:00+00:00"
    )
    _write_events(project, old + recent)
    store = SynapseStore(default_db_path(project))
    store.set_meta(META_KEY_TUNED_AT, "2026-03-01T00:00:00+00:00")

    result = tune_selector(project)
    assert result["changed"] is False
    assert result["reason"] == "insufficient_recent"


def test_tune_selector_fails_open_on_corrupt_events_file(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    path = project_query_events_file(project)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("not json at all\n{partial", encoding="utf-8")

    # read_events skips bad lines, so this degrades to "too few events".
    result = tune_selector(project)
    assert result["changed"] is False


def test_tune_selector_never_raises_on_unwritable_db(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    _write_events(project, _query_events(60, communities=[1]))

    def boom(*_a, **_k):
        raise OSError("disk gone")

    monkeypatch.setattr(self_improve.SynapseStore, "set_meta", boom)
    result = tune_selector(project)
    assert result["changed"] is False
    assert result["reason"] == "error"


# --- selector_report: read-only view ----------------------------------------


def test_selector_report_is_read_only(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    _write_events(project, _query_events(60, communities=[1]))

    report = selector_report(project)
    assert report["l2_recall_k"] == L2_RECALL_K_DEFAULT
    assert report["total_events"] == 60
    assert report["warmed_up"] is True
    assert report["re_query_rate"] == 1.0
    # Nothing was persisted.
    store = SynapseStore(default_db_path(project))
    assert store.get_meta(META_KEY) is None


def test_selector_report_on_empty_project(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    report = selector_report(project)
    assert report["l2_recall_k"] == L2_RECALL_K_DEFAULT
    assert report["total_events"] == 0
    assert report["warmed_up"] is False
