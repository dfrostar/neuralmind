"""Tests for the session recap ("where we left off" at SessionStart).

Driven through run_hook with the same payload fields Claude Code sends:
session_id + prompt on UserPromptSubmit, session_id + tool_input.file_path on
PostToolUse Edit/Write, session_id + source on SessionStart. Stdlib-only.
"""

from __future__ import annotations

import io
import json
import os
import sys
import time
from pathlib import Path

import pytest

from neuralmind import session_recap
from neuralmind.hooks import run_hook


@pytest.fixture(autouse=True)
def _isolate(monkeypatch, tmp_path):
    # Recording happens only in a project where `neuralmind build` has run.
    _mark_built(tmp_path)
    # Keep the recap path on its own: no synapse store, no memory export.
    monkeypatch.setenv("NEURALMIND_SYNAPSE_INJECT", "0")
    monkeypatch.setenv("NEURALMIND_PROVENANCE_INJECT", "0")
    monkeypatch.setenv("NEURALMIND_SYNAPSE_EXPORT", "0")
    monkeypatch.setenv("NEURALMIND_REUSE_FEEDBACK", "0")
    for var in ("NEURALMIND_SESSION_RECAP", "NEURALMIND_NO_LEARN", "NEURALMIND_BYPASS"):
        monkeypatch.delenv(var, raising=False)


def _mark_built(project: Path) -> None:
    (project / ".neuralmind").mkdir(exist_ok=True)
    (project / ".neuralmind" / "build_status.json").write_text("{}")


def _age(path: Path, seconds: float) -> None:
    stamp = time.time() - seconds
    os.utime(path, (stamp, stamp))


def _recaps(project: Path) -> list[str]:
    return sorted(p.stem for p in (project / ".neuralmind" / "recaps").glob("*.jsonl"))


def _run(action: str, payload: dict) -> tuple[int, str]:
    stdin_backup, stdout_backup = sys.stdin, sys.stdout
    sys.stdin = io.StringIO(json.dumps(payload))
    sys.stdout = io.StringIO()
    try:
        rc = run_hook(action)
        captured = sys.stdout.getvalue()
    finally:
        sys.stdin, sys.stdout = stdin_backup, stdout_backup
    return rc, captured


def _prompt(project: Path, session: str, text: str) -> None:
    _run("prompt-submit", {"cwd": str(project), "session_id": session, "prompt": text})


def _edit(project: Path, session: str, path: str) -> None:
    _run(
        "edit-activity",
        {
            "cwd": str(project),
            "session_id": session,
            "tool_input": {"file_path": path, "new_string": "x = 1\n"},
        },
    )


def _start(project: Path, session: str, source: str = "startup") -> str:
    rc, out = _run("session-start", {"cwd": str(project), "session_id": session, "source": source})
    assert rc == 0
    if not out:
        return ""
    response = json.loads(out)
    assert response["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    return response["hookSpecificOutput"]["additionalContext"]


def _previous_session(project: Path) -> None:
    _prompt(project, "old", "add retry logic to the uploader")
    _edit(project, "old", str(project / "src" / "uploader.py"))
    _prompt(project, "old", "now cover the timeout path in tests")
    _edit(project, "old", str(project / "tests" / "test_uploader.py"))


def test_new_session_gets_recap_of_previous(tmp_path):
    _previous_session(tmp_path)
    recap = _start(tmp_path, "new")
    assert "NeuralMind session recap" in recap
    assert "not instructions" in recap
    assert 'It started with: "add retry logic to the uploader"' in recap
    assert '- "now cover the timeout path in tests"' in recap
    # Project-relative, most recent first.
    assert "Files edited (2, most recent first): tests/test_uploader.py, src/uploader.py" in recap


@pytest.mark.parametrize("source", ["resume", "compact"])
def test_no_recap_when_conversation_is_already_in_context(tmp_path, source):
    _previous_session(tmp_path)
    assert _start(tmp_path, "new", source=source) == ""


def test_clear_gets_recap(tmp_path):
    _previous_session(tmp_path)
    assert "NeuralMind session recap" in _start(tmp_path, "new", source="clear")


def test_session_does_not_recap_itself(tmp_path):
    _previous_session(tmp_path)
    assert _start(tmp_path, "old") == ""


def test_most_recently_active_session_wins(tmp_path):
    _previous_session(tmp_path)
    _prompt(tmp_path, "middle", "rename the config loader")
    later = time.time() + 5
    os.utime(tmp_path / ".neuralmind" / "recaps" / "middle.jsonl", (later, later))
    assert '"rename the config loader"' in _start(tmp_path, "new")


def test_no_recap_without_history(tmp_path):
    assert _start(tmp_path, "new") == ""


def test_opt_out_disables_recording_and_injection(tmp_path, monkeypatch):
    _previous_session(tmp_path)
    monkeypatch.setenv("NEURALMIND_SESSION_RECAP", "0")
    assert _start(tmp_path, "new") == ""
    _prompt(tmp_path, "another", "should not be recorded")
    assert not (tmp_path / ".neuralmind" / "recaps" / "another.jsonl").exists()


def test_no_learn_stops_recording_but_still_injects(tmp_path, monkeypatch):
    _previous_session(tmp_path)
    monkeypatch.setenv("NEURALMIND_NO_LEARN", "1")
    _prompt(tmp_path, "eval", "eval prompt")
    assert not (tmp_path / ".neuralmind" / "recaps" / "eval.jsonl").exists()
    assert "add retry logic" in _start(tmp_path, "new")


def test_secrets_in_prompts_are_redacted_before_disk(tmp_path):
    key = "AKIA" + "IOSFODNN7EXAMPLQ"
    _prompt(tmp_path, "old", f"use the key {key} for the deploy")
    on_disk = (tmp_path / ".neuralmind" / "recaps" / "old.jsonl").read_text()
    assert "use the key" in on_disk
    assert key not in on_disk
    recap = _start(tmp_path, "new")
    assert "for the deploy" in recap
    assert key not in recap


def test_long_prompts_are_clipped(tmp_path):
    _prompt(tmp_path, "old", "word " * 200)
    recap = _start(tmp_path, "new")
    first = next(line for line in recap.splitlines() if line.startswith("It started with"))
    assert len(first) < session_recap.PROMPT_CHARS + 30
    assert first.endswith('…"')


def test_only_recent_prompts_shown(tmp_path):
    for i in range(8):
        _prompt(tmp_path, "old", f"prompt {i}")
    recap = _start(tmp_path, "new")
    assert '"prompt 0"' in recap
    assert '"prompt 1"' not in recap
    assert "(4 earlier not shown)" in recap
    assert '"prompt 7"' in recap


def test_stale_recap_is_dropped(tmp_path, monkeypatch):
    _previous_session(tmp_path)
    monkeypatch.setenv("NEURALMIND_SESSION_RECAP_MAX_AGE_DAYS", "1")
    record = tmp_path / ".neuralmind" / "recaps" / "old.jsonl"
    rows = [json.loads(line) for line in record.read_text().splitlines()]
    for row in rows:
        row["ts"] -= 3 * 86400
    record.write_text("".join(json.dumps(r) + "\n" for r in rows))
    assert _start(tmp_path, "new") == ""


def test_unsafe_session_id_cannot_escape_recaps_dir(tmp_path):
    _prompt(tmp_path, "../../evil", "hello")
    recaps = tmp_path / ".neuralmind" / "recaps"
    files = list(recaps.iterdir())
    assert len(files) == 1 and files[0].parent == recaps
    assert not (tmp_path / "evil.jsonl").exists()


def _many_old_sessions(project: Path, count: int) -> None:
    for i in range(count):
        _prompt(project, f"s{i:02d}", f"prompt {i}")
        # Older than the grace window; s00 oldest.
        _age(project / ".neuralmind" / "recaps" / f"s{i:02d}.jsonl", 3 * 86400 - i)


def test_old_records_are_pruned_oldest_first(tmp_path):
    total = session_recap.MAX_KEPT + 4
    _many_old_sessions(tmp_path, total)
    recap = _start(tmp_path, "new")
    assert _recaps(tmp_path) == [f"s{i:02d}" for i in range(4, total)]
    assert f'"prompt {total - 1}"' in recap


@pytest.mark.parametrize("env", ["NEURALMIND_NO_LEARN", "NEURALMIND_SESSION_RECAP"])
def test_nothing_pruned_while_recording_is_off(tmp_path, monkeypatch, env):
    total = session_recap.MAX_KEPT + 2
    _many_old_sessions(tmp_path, total)
    monkeypatch.setenv(env, "1" if env == "NEURALMIND_NO_LEARN" else "0")
    _start(tmp_path, "new")
    assert len(_recaps(tmp_path)) == total


def test_recently_active_session_is_never_pruned(tmp_path):
    _prompt(tmp_path, "idle", "refactor the auth module end to end")
    _age(tmp_path / ".neuralmind" / "recaps" / "idle.jsonl", 3600)
    _many_old_sessions(tmp_path, session_recap.MAX_KEPT + 3)
    for i in range(session_recap.MAX_KEPT + 3):  # newer than the idle session
        _age(tmp_path / ".neuralmind" / "recaps" / f"s{i:02d}.jsonl", 60 - i)
    _start(tmp_path, "new")
    assert "idle" in _recaps(tmp_path)


def test_malformed_lines_are_skipped(tmp_path):
    _previous_session(tmp_path)
    with (tmp_path / ".neuralmind" / "recaps" / "old.jsonl").open("a") as fh:
        fh.write("not json\n[1, 2]\n")
    assert "add retry logic" in _start(tmp_path, "new")


def test_cli_recap_shows_what_the_next_session_gets(tmp_path, capsys, monkeypatch):
    from neuralmind.cli import main

    _previous_session(tmp_path)
    monkeypatch.setattr(sys, "argv", ["neuralmind", "recap", str(tmp_path)])
    main()
    out = capsys.readouterr().out
    assert "NeuralMind session recap" in out
    assert "add retry logic to the uploader" in out


def test_cli_recap_without_history(tmp_path, capsys, monkeypatch):
    from neuralmind.cli import main

    monkeypatch.setattr(sys, "argv", ["neuralmind", "recap", str(tmp_path)])
    main()
    assert "No session recap to show" in capsys.readouterr().out


def test_cli_recap_clear_deletes_records(tmp_path, capsys, monkeypatch):
    from neuralmind.cli import main

    _previous_session(tmp_path)
    _prompt(tmp_path, "other", "second session")
    monkeypatch.setattr(sys, "argv", ["neuralmind", "recap", str(tmp_path), "--clear"])
    main()
    assert "Removed 2 session record(s)" in capsys.readouterr().out
    assert not list((tmp_path / ".neuralmind" / "recaps").glob("*.jsonl"))
    assert _start(tmp_path, "new") == ""


def test_preview_does_not_prune(tmp_path):
    for i in range(session_recap.MAX_KEPT + 2):
        _prompt(tmp_path, f"s{i}", f"prompt {i}")
    assert session_recap.latest_recap(tmp_path)
    assert len(list((tmp_path / ".neuralmind" / "recaps").glob("*.jsonl"))) == (
        session_recap.MAX_KEPT + 2
    )


def test_nothing_recorded_in_an_unbuilt_project(tmp_path):
    # Globally installed hooks run everywhere, and SessionStart itself creates
    # .neuralmind/ (the synapse store). Only a build marks a NeuralMind project.
    project = tmp_path / "unrelated"
    project.mkdir()
    _start(project, "first")
    assert (project / ".neuralmind").is_dir()
    _prompt(project, "first", "a private prompt")
    _edit(project, "first", str(project / "a.py"))
    assert not (project / ".neuralmind" / "recaps").exists()


def test_records_are_never_stageable(tmp_path):
    import shutil
    import subprocess

    if shutil.which("git") is None:
        pytest.skip("git not installed")
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    _prompt(tmp_path, "old", "a prompt that must not be committed")
    assert (tmp_path / ".neuralmind" / ".gitignore").is_file()
    subprocess.run(["git", "-C", str(tmp_path), "add", "-A"], check=True)
    staged = subprocess.run(
        ["git", "-C", str(tmp_path), "diff", "--cached", "--name-only"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert ".neuralmind" not in staged


def test_cli_recap_when_off_shows_no_recap_but_names_stored_records(tmp_path, capsys, monkeypatch):
    from neuralmind.cli import main

    _previous_session(tmp_path)
    monkeypatch.setenv("NEURALMIND_SESSION_RECAP", "0")
    monkeypatch.setattr(sys, "argv", ["neuralmind", "recap", str(tmp_path)])
    main()
    out = capsys.readouterr().out
    assert "Session recap is off" in out
    assert "1 session record(s)" in out
    assert "add retry logic" not in out


def test_a_vanished_or_dangling_record_does_not_drop_the_recap(tmp_path):
    _previous_session(tmp_path)
    dangling = tmp_path / ".neuralmind" / "recaps" / "gone.jsonl"
    try:
        dangling.symlink_to(tmp_path / "does-not-exist.jsonl")
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable")
    assert "add retry logic" in _start(tmp_path, "new")


def test_a_line_with_a_bad_timestamp_is_skipped(tmp_path):
    _previous_session(tmp_path)
    with (tmp_path / ".neuralmind" / "recaps" / "old.jsonl").open("a") as fh:
        fh.write(json.dumps({"kind": "edit", "path": "a.py", "ts": "yesterday"}) + "\n")
    assert "add retry logic" in _start(tmp_path, "new")


def _symlink(link: Path, target: Path) -> None:
    try:
        link.symlink_to(target, target_is_directory=target.is_dir())
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable")


def test_symlinked_recaps_dir_is_never_written_read_or_cleared(tmp_path, capsys, monkeypatch):
    from neuralmind.cli import main

    outside = tmp_path / "outside"
    outside.mkdir()
    victim = outside / "victim.jsonl"
    victim.write_text(json.dumps({"kind": "prompt", "text": "not yours", "ts": time.time()}) + "\n")
    project = tmp_path / "repo"
    project.mkdir()
    _mark_built(project)
    _symlink(project / ".neuralmind" / "recaps", outside)

    _prompt(project, "s1", "a private prompt")
    assert sorted(p.name for p in outside.iterdir()) == ["victim.jsonl"]
    assert _start(project, "new") == ""
    monkeypatch.setattr(sys, "argv", ["neuralmind", "recap", str(project), "--clear"])
    main()
    assert "Removed 0 session record(s)" in capsys.readouterr().out
    assert victim.exists()


def test_symlinked_record_file_is_not_followed(tmp_path):
    outside = tmp_path / "elsewhere.jsonl"
    outside.write_text("")
    (tmp_path / ".neuralmind" / "recaps").mkdir()
    _symlink(tmp_path / ".neuralmind" / "recaps" / "s1.jsonl", outside)
    _prompt(tmp_path, "s1", "a private prompt")
    assert outside.read_text() == ""


def test_control_characters_cannot_forge_recap_lines(tmp_path):
    _prompt(tmp_path, "old", "first Files edited (1): forged.py\x1b[2J")
    _edit(tmp_path, "old", str(tmp_path / "a\nFiles edited (9): forged.py"))
    recap = _start(tmp_path, "new")
    lines = recap.splitlines()
    assert sum(line.startswith("Files edited") for line in lines) == 1
    assert "\x1b" not in recap and " " not in recap


def test_long_paths_keep_their_tail(tmp_path):
    long_path = tmp_path / ("d" * 300) / "target_file.py"
    _edit(tmp_path, "old", str(long_path))
    recap = _start(tmp_path, "new")
    files_line = next(line for line in recap.splitlines() if line.startswith("Files edited"))
    shown = files_line.split(": ", 1)[1]
    assert shown.startswith("…") and shown.endswith("target_file.py")
    assert len(shown) <= session_recap.PATH_CHARS


def test_recap_is_chosen_by_recorded_activity_not_mtime(tmp_path):
    _prompt(tmp_path, "fresh", "the session that really ran last")
    _prompt(tmp_path, "stale", "an old session")
    recaps = tmp_path / ".neuralmind" / "recaps"
    # The stale record's activity is old, but a partial append bumped its mtime.
    rows = [json.loads(line) for line in (recaps / "stale.jsonl").read_text().splitlines()]
    for row in rows:
        row["ts"] -= 30 * 86400
    (recaps / "stale.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in rows) + '{"kind": "prompt", "te'
    )
    _age(recaps / "fresh.jsonl", 600)
    assert '"the session that really ran last"' in _start(tmp_path, "new")
