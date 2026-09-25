"""Tests for the Stop / SessionEnd hook actions (v4.3.0).

Both hooks derive their view of the session from the durable event log
(.neuralmind/events.jsonl) — hook processes are short-lived, so there is no
in-memory session state at a session boundary. These tests cover:

- hook block registration (Stop + SessionEnd advertised, idempotent install)
- session-end digest written from the event log
- session-end no-op when the log is empty or missing (fail-open)
- session-end opt-out via NEURALMIND_SESSION_END=0
- stop cadence tick: writes a summary only when enough fresh events exist
- stop respects an existing summaries directory (never creates it)
- stop no-ops without a summaries directory
- malformed log lines are skipped, not fatal
"""

from __future__ import annotations

import io
import json
import os
import sys
import time
from pathlib import Path

from neuralmind.hooks import _hook_block, install_hooks, run_hook

LIFECYCLE = ("Stop", "SessionEnd")


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


def _write_events(project: Path, events: list[dict]) -> None:
    log = project / ".neuralmind" / "events.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a", encoding="utf-8") as fh:
        for e in events:
            fh.write(json.dumps(e) + "\n")


def _event(ts: float | None = None, paths: list[str] | None = None) -> dict:
    return {
        "type": "file",
        "ts": ts if ts is not None else time.time(),
        "_pid": os.getpid(),
        "paths": paths or ["src/foo.py"],
        "count": 1,
    }


def test_hook_block_advertises_stop_and_session_end():
    block = _hook_block()
    for event in LIFECYCLE:
        assert event in block, f"{event} missing from hook block"
    cmds = []
    for event in LIFECYCLE:
        for matcher_block in block[event]:
            for h in matcher_block["hooks"]:
                cmds.append(h["command"])
    assert any("_hook stop" in c for c in cmds)
    assert any("_hook session-end" in c for c in cmds)


def test_install_writes_and_is_idempotent_for_new_events(tmp_path):
    install_hooks(scope="project", project_path=str(tmp_path))
    settings = json.loads((tmp_path / ".claude" / "settings.json").read_text())
    hooks = settings["hooks"]
    for event in LIFECYCLE:
        assert event in hooks
        assert len(hooks[event]) == 1
    # Re-install must not duplicate blocks.
    install_hooks(scope="project", project_path=str(tmp_path))
    settings2 = json.loads((tmp_path / ".claude" / "settings.json").read_text())
    for event in LIFECYCLE:
        assert len(settings2["hooks"][event]) == 1


def test_session_end_writes_digest_from_event_log(tmp_path):
    _write_events(tmp_path, [_event(paths=["src/a.py", "src/b.py"]) for _ in range(30)])
    rc, out = _run("session-end", {"cwd": str(tmp_path)})
    assert rc == 0
    assert out == ""  # side-effect hook: no stdout
    summaries = list((tmp_path / ".neuralmind" / "summaries").glob("*.md"))
    assert len(summaries) == 1
    body = summaries[0].read_text(encoding="utf-8")
    assert "30" in body  # event count in the title
    assert "src/a.py" in body  # files touched recorded


def test_session_end_noop_without_events(tmp_path):
    (tmp_path / ".neuralmind").mkdir(parents=True, exist_ok=True)
    rc, out = _run("session-end", {"cwd": str(tmp_path)})
    assert rc == 0
    assert not (tmp_path / ".neuralmind" / "summaries").exists()


def test_session_end_noop_when_log_missing(tmp_path):
    rc, out = _run("session-end", {"cwd": str(tmp_path)})
    assert rc == 0
    assert not (tmp_path / ".neuralmind" / "summaries").exists()


def test_session_end_opt_out(monkeypatch, tmp_path):
    monkeypatch.setenv("NEURALMIND_SESSION_END", "0")
    _write_events(tmp_path, [_event() for _ in range(5)])
    rc, _ = _run("session-end", {"cwd": str(tmp_path)})
    assert rc == 0
    assert not (tmp_path / ".neuralmind" / "summaries").exists()


def test_session_end_skips_malformed_lines(tmp_path):
    log = tmp_path / ".neuralmind" / "events.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(
        "not json\n"
        + json.dumps(_event(paths=["src/ok.py"])) + "\n"
        + "{broken\n",
        encoding="utf-8",
    )
    rc, _ = _run("session-end", {"cwd": str(tmp_path)})
    assert rc == 0
    summaries = list((tmp_path / ".neuralmind" / "summaries").glob("*.md"))
    assert len(summaries) == 1
    assert "src/ok.py" in summaries[0].read_text(encoding="utf-8")


def test_stop_writes_summary_when_cadence_reached(tmp_path):
    # Summaries directory must already exist — Stop never creates it.
    summaries_dir = tmp_path / ".neuralmind" / "summaries"
    summaries_dir.mkdir(parents=True, exist_ok=True)
    # every_n_turns defaults to 25; write 30 fresh events.
    _write_events(tmp_path, [_event() for _ in range(30)])
    rc, out = _run("stop", {"cwd": str(tmp_path)})
    assert rc == 0
    assert out == ""
    assert len(list(summaries_dir.glob("*.md"))) == 1


def test_stop_noop_below_cadence(tmp_path):
    summaries_dir = tmp_path / ".neuralmind" / "summaries"
    summaries_dir.mkdir(parents=True, exist_ok=True)
    _write_events(tmp_path, [_event() for _ in range(5)])  # below 25
    rc, _ = _run("stop", {"cwd": str(tmp_path)})
    assert rc == 0
    assert list(summaries_dir.glob("*.md")) == []


def test_stop_noop_without_summaries_dir(tmp_path):
    # No summaries dir -> Stop must not create it (config belongs to the user).
    _write_events(tmp_path, [_event() for _ in range(50)])
    rc, _ = _run("stop", {"cwd": str(tmp_path)})
    assert rc == 0
    assert not (tmp_path / ".neuralmind" / "summaries").exists()


def test_stop_opt_out(monkeypatch, tmp_path):
    monkeypatch.setenv("NEURALMIND_SESSION_END", "0")
    summaries_dir = tmp_path / ".neuralmind" / "summaries"
    summaries_dir.mkdir(parents=True, exist_ok=True)
    _write_events(tmp_path, [_event() for _ in range(30)])
    rc, _ = _run("stop", {"cwd": str(tmp_path)})
    assert rc == 0
    assert list(summaries_dir.glob("*.md")) == []


def test_stop_counts_only_fresh_events(tmp_path):
    """Events older than the newest summary must not count toward cadence."""
    summaries_dir = tmp_path / ".neuralmind" / "summaries"
    summaries_dir.mkdir(parents=True, exist_ok=True)
    # Old events, then a summary newer than all of them…
    _write_events(tmp_path, [_event(ts=time.time() - 3600) for _ in range(40)])
    marker = summaries_dir / "marker.md"
    marker.write_text("# earlier summary", encoding="utf-8")
    # …then only 3 fresh events — below cadence.
    _write_events(tmp_path, [_event() for _ in range(3)])
    rc, _ = _run("stop", {"cwd": str(tmp_path)})
    assert rc == 0
    # Only the marker exists; no new summary was written.
    assert [p.name for p in summaries_dir.glob("*.md")] == ["marker.md"]
