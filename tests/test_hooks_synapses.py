"""Tests for the SessionStart / UserPromptSubmit / PreCompact hook actions."""

from __future__ import annotations

import io
import json
import sys

from neuralmind.hooks import _hook_block, install_hooks, run_hook
from neuralmind.synapses import SynapseStore, default_db_path


def _run(action: str, payload: dict) -> tuple[int, str]:
    """Drive run_hook with a stdin payload and capture stdout."""
    stdin_backup, stdout_backup = sys.stdin, sys.stdout
    sys.stdin = io.StringIO(json.dumps(payload))
    sys.stdout = io.StringIO()
    try:
        rc = run_hook(action)
        captured = sys.stdout.getvalue()
    finally:
        sys.stdin, sys.stdout = stdin_backup, stdout_backup
    return rc, captured


def test_hook_block_advertises_lifecycle_events():
    block = _hook_block()
    assert "SessionStart" in block
    assert "UserPromptSubmit" in block
    assert "PreCompact" in block
    cmds = []
    for event in ("SessionStart", "UserPromptSubmit", "PreCompact"):
        for matcher_block in block[event]:
            for h in matcher_block["hooks"]:
                cmds.append(h["command"])
    assert any("session-start" in c for c in cmds)
    assert any("prompt-submit" in c for c in cmds)
    assert any("pre-compact" in c for c in cmds)


def test_install_writes_lifecycle_event_blocks(tmp_path):
    install_hooks(scope="project", project_path=str(tmp_path))
    settings = json.loads((tmp_path / ".claude" / "settings.json").read_text())
    hooks = settings["hooks"]
    for event in ("SessionStart", "UserPromptSubmit", "PreCompact"):
        assert event in hooks
        # Each event has exactly one neuralmind-managed block on fresh install.
        assert len(hooks[event]) == 1


def test_install_idempotent_for_lifecycle_events(tmp_path):
    install_hooks(scope="project", project_path=str(tmp_path))
    install_hooks(scope="project", project_path=str(tmp_path))
    settings = json.loads((tmp_path / ".claude" / "settings.json").read_text())
    for event in ("SessionStart", "UserPromptSubmit", "PreCompact"):
        # Still exactly one block — repeated install must not duplicate.
        assert len(settings["hooks"][event]) == 1


def test_session_start_runs_decay_tick(tmp_path):
    # SessionStart should run decay() — verify by checking that an edge
    # weight strictly decreased after the hook fires.
    db = default_db_path(tmp_path)
    store = SynapseStore(db)
    store.reinforce(["a", "b"])
    before = dict(store.neighbors("a"))["b"]

    rc, _ = _run("session-start", {"cwd": str(tmp_path)})
    assert rc == 0

    fresh = SynapseStore(db)
    after = dict(fresh.neighbors("a")).get("b")
    assert after is not None
    assert after < before


def test_session_start_exports_synapse_memory(tmp_path, monkeypatch):
    # Isolate HOME so we don't touch a real Claude auto-memory dir.
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))

    store = SynapseStore(default_db_path(tmp_path))
    store.reinforce(["a", "b"])

    rc, _ = _run("session-start", {"cwd": str(tmp_path)})
    assert rc == 0

    out = tmp_path / ".neuralmind" / "SYNAPSE_MEMORY.md"
    assert out.exists()
    assert "Synapse Memory" in out.read_text()


def test_session_start_export_disabled_via_env(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))
    monkeypatch.setenv("NEURALMIND_SYNAPSE_EXPORT", "0")

    store = SynapseStore(default_db_path(tmp_path))
    store.reinforce(["a", "b"])

    rc, _ = _run("session-start", {"cwd": str(tmp_path)})
    assert rc == 0

    out = tmp_path / ".neuralmind" / "SYNAPSE_MEMORY.md"
    assert not out.exists()


def _write_query_events(project_path, n):
    """Write n high-overlap query events so the tuner has warm-up data."""
    from neuralmind.memory import project_query_events_file

    path = project_query_events_file(project_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "event_type": "query",
        "timestamp": "2026-05-07T00:00:00+00:00",
        "session_id": "s",
        "retrieval_summary": {
            "layers_used": ["L0:Identity", "L1:Summary", "L2:OnDemand(3 clusters)"],
            "communities_loaded": [1, 2],
        },
    }
    with path.open("w", encoding="utf-8") as f:
        for _ in range(n):
            f.write(json.dumps(event) + "\n")


def test_session_start_runs_tuner_when_autotune_enabled(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))
    monkeypatch.setenv("NEURALMIND_SELECTOR_AUTOTUNE", "1")
    _write_query_events(tmp_path, 60)  # high-overlap → tuner raises k

    rc, _ = _run("session-start", {"cwd": str(tmp_path)})
    assert rc == 0

    store = SynapseStore(default_db_path(tmp_path))
    assert store.get_meta("l2_recall_k") == "4"


def test_session_start_skips_tuner_when_autotune_disabled(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))
    monkeypatch.delenv("NEURALMIND_SELECTOR_AUTOTUNE", raising=False)
    _write_query_events(tmp_path, 60)

    rc, _ = _run("session-start", {"cwd": str(tmp_path)})
    assert rc == 0

    store = SynapseStore(default_db_path(tmp_path))
    assert store.get_meta("l2_recall_k") is None


def test_session_start_survives_tuner_failure(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))
    monkeypatch.setenv("NEURALMIND_SELECTOR_AUTOTUNE", "1")

    import neuralmind.self_improve as si

    def boom(*_a, **_k):
        raise RuntimeError("tuner exploded")

    monkeypatch.setattr(si, "tune_selector", boom)

    # Hook must still return 0 — tuner failures are swallowed.
    rc, _ = _run("session-start", {"cwd": str(tmp_path)})
    assert rc == 0


def test_pre_compact_normalizes_hubs(tmp_path):
    db = default_db_path(tmp_path)
    store = SynapseStore(db)
    # Build a clear hub so normalize_hubs has something to do.
    for i in range(120):
        store.reinforce(["HUB", f"spoke_{i}"])
    before = store.stats()["total_weight"]

    rc, _ = _run("pre-compact", {"cwd": str(tmp_path)})
    assert rc == 0

    after = SynapseStore(db).stats()["total_weight"]
    assert after < before


def test_prompt_submit_no_synapses_emits_nothing(tmp_path):
    # No graph built, no edges learned — hook must fail open silently.
    rc, captured = _run(
        "prompt-submit",
        {"cwd": str(tmp_path), "prompt": "How does auth work?"},
    )
    assert rc == 0
    assert captured == ""


def test_prompt_submit_disabled_via_env(tmp_path, monkeypatch):
    monkeypatch.setenv("NEURALMIND_SYNAPSE_INJECT", "0")
    rc, captured = _run(
        "prompt-submit",
        {"cwd": str(tmp_path), "prompt": "anything"},
    )
    assert rc == 0
    assert captured == ""


def test_prompt_submit_empty_prompt_is_skipped(tmp_path):
    rc, captured = _run("prompt-submit", {"cwd": str(tmp_path), "prompt": ""})
    assert rc == 0
    assert captured == ""


def test_unknown_action_is_noop(tmp_path):
    rc, captured = _run("not-a-real-action", {"cwd": str(tmp_path)})
    assert rc == 0
    assert captured == ""
