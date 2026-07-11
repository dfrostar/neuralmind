"""Tests for selector auto-tuning (self-improvement engine, subsystem A)."""

from __future__ import annotations

import json

from neuralmind import self_improve
from neuralmind.context_selector import ContextSelector
from neuralmind.memory import project_query_events_file
from neuralmind.self_improve import (
    L2_RECALL_K_DEFAULT,
    L2_RECALL_K_MAX,
    L2_RECALL_K_MIN,
    META_KEY,
    META_KEY_TUNED_AT,
    TRANSITION_MARGIN_HIGH,
    WINDOW_MIN_EVENTS,
    _decide,
    selector_report,
    transition_top1_margin,
    tune_selector,
)
from neuralmind.synapses import SynapseStore, default_db_path


def _write_events(project_path, events):
    """Write events straight to the JSONL file the tuner reads."""
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


def test_wakeup_events_do_not_count_toward_warmup(tmp_path):
    """Only query events carry re_query signal — a project flooded with
    wakeups but few queries must stay warmup-gated, not drift k down."""
    project = tmp_path / "project"
    project.mkdir()
    wakeups = [
        {
            "event_type": "wakeup",
            "timestamp": "2026-05-07T00:00:00+00:00",
            "session_id": f"w{i}",
            "retrieval_summary": {"layers_used": ["L0:Identity", "L1:Summary"]},
        }
        for i in range(100)
    ]
    queries = _query_events(10, communities=[1])  # well under WARMUP_MIN_EVENTS
    _write_events(project, wakeups + queries)

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
    events = [_query_events(1, session_id="s", communities=[i])[0] for i in range(60)]
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
    old = _query_events(55, session_id="old", communities=[1], ts="2026-01-01T00:00:00+00:00")
    recent = _query_events(WINDOW_MIN_EVENTS - 1, communities=[1], ts="2026-06-01T00:00:00+00:00")
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


# --- transition-margin dampener (v0.11+ extension) --------------------------


def test_transition_top1_margin_empty_when_cold(tmp_path):
    """No learned transitions → margin 0.0, never blocks the tuner."""
    project = tmp_path / "project"
    project.mkdir()
    store = SynapseStore(default_db_path(project))
    assert transition_top1_margin(store, "community_1") == 0.0
    assert transition_top1_margin(store, "") == 0.0


def test_transition_top1_margin_reads_distribution(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    store = SynapseStore(default_db_path(project))
    # A -> B fired many times, A -> C once: top-1 (B) dominates the mass.
    for _ in range(9):
        store.record_sequence(["community_1", "community_2"])
    store.record_sequence(["community_1", "community_3"])
    margin = transition_top1_margin(store, "community_1")
    assert margin > 0.5


def test_decide_dampens_raise_on_high_transition_margin():
    """A decisive transition margin suppresses an otherwise-warranted raise."""
    new, reason = _decide(3, 0.9, transition_margin=TRANSITION_MARGIN_HIGH)
    assert new == 3
    assert reason == "transition_dampened"


def test_decide_does_not_dampen_lower_or_dead_band():
    # Dampener only touches the raise path.
    assert _decide(3, 0.0, transition_margin=1.0) == (2, "lowered")
    assert _decide(3, 0.25, transition_margin=1.0) == (3, "dead_band")


def test_decide_raises_when_margin_below_threshold():
    new, reason = _decide(3, 0.9, transition_margin=TRANSITION_MARGIN_HIGH - 0.01)
    assert new == 4
    assert reason == "raised"


def test_tune_selector_transition_dampener_holds_raise(tmp_path):
    """End-to-end: high re_query_rate that would raise k is held when the
    most-recent recall seed has a decisive transition distribution."""
    project = tmp_path / "project"
    project.mkdir()
    # 60 high-overlap queries on community 1 → rate 1.0 → would raise.
    _write_events(project, _query_events(60, communities=[1]))
    store = SynapseStore(default_db_path(project))
    # Make community_1 -> community_2 a near-certain transition.
    for _ in range(20):
        store.record_sequence(["community_1", "community_2"])

    result = tune_selector(project)
    assert result["changed"] is False
    assert result["reason"] == "transition_dampened"
    assert store.get_meta(META_KEY) is None


# --- meta-table persistence round-trip & env-flag read-path gating ----------


def test_meta_persistence_round_trips_via_get_set(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    store = SynapseStore(default_db_path(project))
    assert store.get_meta(META_KEY) is None
    store.set_meta(META_KEY, 5)  # coerced via str()
    # A fresh store reads the same persisted value (carries across sessions).
    again = SynapseStore(default_db_path(project))
    assert again.get_meta(META_KEY) == "5"


def test_tuned_value_flows_to_selector_when_flag_on(tmp_path, monkeypatch):
    """With autotune on, core.build threads the persisted k into the selector."""
    monkeypatch.setenv("NEURALMIND_SELECTOR_AUTOTUNE", "1")
    from neuralmind.core import NeuralMind

    project = tmp_path / "project"
    project.mkdir()
    store = SynapseStore(default_db_path(project))
    store.set_meta(META_KEY, "5")

    mind = NeuralMind(str(project), enable_synapses=True)
    assert mind._tuned_l2_recall_k() == 5


def test_read_path_is_noop_when_flag_off(tmp_path, monkeypatch):
    """Default-off: the hot path does no meta read and keeps the default."""
    monkeypatch.delenv("NEURALMIND_SELECTOR_AUTOTUNE", raising=False)
    from neuralmind.core import NeuralMind

    project = tmp_path / "project"
    project.mkdir()
    store = SynapseStore(default_db_path(project))
    store.set_meta(META_KEY, "5")  # present but must be ignored

    mind = NeuralMind(str(project), enable_synapses=True)
    assert mind._tuned_l2_recall_k() is None


def test_selector_clamps_out_of_range_override():
    """A garbage persisted value can never widen recall out of bounds."""
    hi = ContextSelector(embedder=None, l2_recall_k=999)
    assert hi.l2_recall_k == ContextSelector.L2_RECALL_K_MAX
    lo = ContextSelector(embedder=None, l2_recall_k=0)
    assert lo.l2_recall_k == ContextSelector.L2_RECALL_K_MIN
    default = ContextSelector(embedder=None, l2_recall_k=None)
    assert default.l2_recall_k == ContextSelector.L2_RECALL_K_DEFAULT
