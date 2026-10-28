"""The session-start hook's store work, run after it on a large store (neuralmind/session_maintenance.py).

On a 1,272,023-edge store the decay tick and the memory export took about 6 s
of session-start's 6.3–7.7 s, and the Hermes plugin stops a hook after 8 s,
dropping the recap it had already written. These tests pin the contract: a
small store is still maintained inside the hook, a large one by a detached
process that holds none of the hook's pipes, and either way the store and
``SYNAPSE_MEMORY.md`` end up the same.
"""

from __future__ import annotations

import io
import json
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import pytest

from neuralmind import session_maintenance
from neuralmind.hooks import run_hook
from neuralmind.synapses import EPHEMERAL_NAMESPACE, SynapseStore, default_db_path

REPO_ROOT = Path(__file__).resolve().parents[1]
NOW = 1_800_000_000.0


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    # No real Claude auto-memory directory, and the switches at their defaults.
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "home"))
    for var in (
        "NEURALMIND_NO_LEARN",
        "NEURALMIND_SYNAPSE_EXPORT",
        "NEURALMIND_SYNAPSE_INJECT",
        "NEURALMIND_BYPASS",
    ):
        monkeypatch.delenv(var, raising=False)


def _record_starts(monkeypatch) -> list[tuple[list[str], dict]]:
    """Record the maintenance processes started; other processes (git) run."""
    calls: list[tuple[list[str], dict]] = []
    real = subprocess.Popen

    def popen(argv, **kw):
        if "neuralmind.session_maintenance" in argv:
            calls.append((argv, kw))
            return None
        return real(argv, **kw)

    monkeypatch.setattr(session_maintenance.subprocess, "Popen", popen)
    return calls


@pytest.fixture
def started(monkeypatch):
    """Every store counts as large; record the processes it would start."""
    monkeypatch.setattr(session_maintenance, "INLINE_MAX_BYTES", 0)
    return _record_starts(monkeypatch)


def _project(root: Path) -> Path:
    """A project whose store has every namespace, transitions and a last-touched file."""
    (root / ".neuralmind").mkdir(parents=True, exist_ok=True)
    # Built, so the recap records prompts here.
    (root / ".neuralmind" / "build_status.json").write_text("{}")
    db = default_db_path(root)
    for i, ns in enumerate(("personal", "shared", EPHEMERAL_NAMESPACE, "branch:x")):
        store = SynapseStore(db, namespace=ns)
        for j in range(12):
            store.reinforce([f"n{j}", f"n{(j * 7 + i) % 12}", f"n{(j + 3) % 12}"])
        store.record_sequence([f"n{(i + k) % 12}" for k in range(5)])
    SynapseStore(db).set_meta("_last_touched_file", "a.py")
    return root


def _session_start(project: Path, session_id: str = "s2") -> str:
    stdin, stdout = sys.stdin, sys.stdout
    sys.stdin = io.StringIO(
        json.dumps({"cwd": str(project), "session_id": session_id, "source": "startup"})
    )
    sys.stdout = io.StringIO()
    try:
        assert run_hook("session-start") == 0
        return sys.stdout.getvalue()
    finally:
        sys.stdin, sys.stdout = stdin, stdout


def _with_recap(project: Path) -> Path:
    from neuralmind.session_recap import record_prompt

    record_prompt(str(project), "s1", "Fix the rate-limit classifier")
    return project


def _memory(project: Path) -> Path:
    return project / ".neuralmind" / "SYNAPSE_MEMORY.md"


def _dump(project: Path) -> str:
    conn = sqlite3.connect(default_db_path(project))
    try:
        return "\n".join(conn.iterdump())
    finally:
        conn.close()


def _state(project: Path) -> tuple[str, str]:
    """The whole store, and the export without its timestamp."""
    text = _memory(project).read_text(encoding="utf-8")
    lines = [ln for ln in text.splitlines() if not ln.startswith("- Updated")]
    return _dump(project), "\n".join(lines)


def _weight(project: Path) -> float:
    return dict(SynapseStore(default_db_path(project)).neighbors("n0", k=100))["n3"]


def test_a_small_store_is_maintained_in_the_hook(tmp_path, monkeypatch):
    project = _project(tmp_path / "p")
    calls = _record_starts(monkeypatch)
    before = _weight(project)
    _session_start(project)
    assert not calls
    assert _weight(project) < before  # decayed
    assert _memory(project).exists()


def test_a_large_store_is_left_to_a_detached_process(tmp_path, started):
    project = _with_recap(_project(tmp_path / "p"))
    before = _weight(project)
    assert SynapseStore(default_db_path(project)).neighbors("n0", namespaces=[EPHEMERAL_NAMESPACE])

    out = _session_start(project)

    assert "Fix the rate-limit classifier" in out  # the recap is still emitted
    ((argv, kw),) = started
    assert argv[-2:] == ["neuralmind.session_maintenance", str(project.resolve())]
    # Its output goes nowhere: the Hermes plugin waits on the hook's pipes,
    # and would otherwise wait for this process too.
    for stream in ("stdin", "stdout", "stderr"):
        assert kw[stream] is subprocess.DEVNULL
    assert kw["start_new_session"] is True
    # The decay tick and the export are the child's; the session-boundary
    # resets stay in the hook, ahead of the session's first tool call.
    assert _weight(project) == before
    assert not _memory(project).exists()
    store = SynapseStore(default_db_path(project))
    assert store.get_meta("_last_touched_file") is None
    assert not store.neighbors("n0", namespaces=[EPHEMERAL_NAMESPACE])


def test_the_detached_process_leaves_what_the_hook_would(tmp_path, monkeypatch):
    # Same clock for both: decay is wall-clock, so only a pinned one compares exactly.
    monkeypatch.setattr(time, "time", lambda: NOW)
    inline = _project(tmp_path / "inline")
    detached = _project(tmp_path / "detached")
    assert _dump(inline) == _dump(detached)  # seeded under the same clock
    monkeypatch.setattr(time, "time", lambda: NOW + 9 * 86400)

    _session_start(inline)
    monkeypatch.setattr(session_maintenance, "INLINE_MAX_BYTES", 0)
    starts = _record_starts(monkeypatch)
    _session_start(detached)
    assert len(starts) == 1
    assert session_maintenance._main([str(detached)]) == 0

    assert _state(detached) == _state(inline)


def test_the_maintenance_process_runs_as_a_module(tmp_path):
    project = _project(tmp_path / "p")
    before = _weight(project)
    env = dict(os.environ, PYTHONPATH=str(REPO_ROOT))
    subprocess.run(
        [sys.executable, "-m", "neuralmind.session_maintenance", str(project)],
        env=env,
        check=True,
        timeout=120,
    )
    assert _weight(project) < before
    assert "Synapse Memory" in _memory(project).read_text(encoding="utf-8")


def test_a_hook_whose_store_is_large_returns_the_recap_without_waiting(tmp_path):
    """The real round trip the Hermes plugin makes, with every store counted as large."""
    project = _with_recap(_project(tmp_path / "p"))
    code = (
        "import sys\n"
        "from neuralmind import session_maintenance\n"
        "session_maintenance.INLINE_MAX_BYTES = 0\n"
        "from neuralmind.hooks import run_hook\n"
        "sys.exit(run_hook('session-start'))\n"
    )
    env = dict(os.environ, PYTHONPATH=str(REPO_ROOT))
    done = subprocess.run(
        [sys.executable, "-c", code],
        input=json.dumps({"cwd": str(project), "session_id": "s2", "source": "startup"}),
        capture_output=True,
        text=True,
        env=env,
        cwd=str(tmp_path),
        timeout=120,
        check=True,
    )
    context = json.loads(done.stdout)["hookSpecificOutput"]["additionalContext"]
    assert "Fix the rate-limit classifier" in context
    # The detached process finishes the job.
    deadline = time.monotonic() + 60
    while not _memory(project).exists() and time.monotonic() < deadline:
        time.sleep(0.1)
    assert _memory(project).exists()


@pytest.mark.skipif(sys.platform == "win32", reason="flock")
def test_a_second_process_leaves_it_to_the_first(tmp_path):
    import fcntl

    project = _project(tmp_path / "p")
    lock = project / ".neuralmind" / session_maintenance.LOCK_FILENAME
    fd = os.open(lock, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        assert session_maintenance._main([str(project)]) == 0
        assert not _memory(project).exists()
    finally:
        os.close(fd)
    assert session_maintenance._main([str(project)]) == 0
    assert _memory(project).exists()


def test_no_learn_exports_without_decaying(tmp_path, monkeypatch, started):
    project = _project(tmp_path / "p")
    before = _weight(project)
    monkeypatch.setenv("NEURALMIND_NO_LEARN", "1")
    _session_start(project)
    assert len(started) == 1
    assert session_maintenance._main([str(project)]) == 0
    assert _weight(project) == before
    assert _memory(project).exists()


def test_nothing_to_do_starts_nothing(tmp_path, monkeypatch, started):
    project = _project(tmp_path / "p")
    monkeypatch.setenv("NEURALMIND_NO_LEARN", "1")
    monkeypatch.setenv("NEURALMIND_SYNAPSE_EXPORT", "0")
    _session_start(project)
    assert not started


def test_a_process_that_cannot_start_is_skipped_not_run_in_the_hook(tmp_path, monkeypatch):
    project = _project(tmp_path / "p")
    before = _weight(project)
    monkeypatch.setattr(session_maintenance, "INLINE_MAX_BYTES", 0)

    def refuse(*_a, **_k):
        raise OSError("no process to spare")

    monkeypatch.setattr(session_maintenance.subprocess, "Popen", refuse)
    assert session_maintenance.run_or_start(project) is False
    assert _weight(project) == before
    assert not _memory(project).exists()
