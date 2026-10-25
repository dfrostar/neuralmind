"""The task-outcome harness on another repository: profiles, isolation, the index cache.

The pilot's runs must stay reproducible after the harness learned other
repositories, so the neuralmind profile's prompt is pinned to the pilot's
text. Stdlib-only.
"""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

from evals.task_outcome import harness, harvest, profiles, run

PILOT_PROMPT = (
    "Symptom here.\n\n"
    "You are working in a checkout of the NeuralMind repository. Find the cause and "
    "fix it in the source code. Don't add or change tests: the fix is judged by tests "
    "you can't see. You can run the existing tests with `python -m pytest <path>`. "
    "Stop when the fix is done."
)


def test_the_neuralmind_profile_renders_the_pilots_prompt_exactly() -> None:
    assert run.render_prompt("  Symptom here. ", profiles.get("neuralmind")) == PILOT_PROMPT


def test_another_profile_names_its_own_repository() -> None:
    text = run.render_prompt("Symptom here.", profiles.get("hermes-agent"))
    assert "a checkout of the hermes-agent repository" in text
    assert "NeuralMind" not in text


def test_profiles_decide_what_counts_as_source() -> None:
    changed = [
        "neuralmind/cli.py",
        "tests/test_cli.py",
        "hermes_cli/main.py",
        "run_agent.py",
        "website/docs/x.py",
        "README.md",
    ]
    assert profiles.get("neuralmind").source_files(changed) == ["neuralmind/cli.py"]
    assert profiles.get("hermes-agent").source_files(changed) == [
        "neuralmind/cli.py",
        "hermes_cli/main.py",
        "run_agent.py",
    ]


def test_eligibility_uses_the_profiles_cutoff() -> None:
    assert harvest.eligible("fix: x", "2026-08-01T00:00:00Z", ["a.py"]) is None
    late = profiles.get("hermes-agent").cutoff
    assert "before" in harvest.eligible("fix: x", "2026-08-01T00:00:00Z", ["a.py"], late)
    assert harvest.eligible("fix: x", f"{late}T00:00:00Z", ["a.py"], late) is None


def test_only_hermes_workspaces_get_their_own_hermes_home(tmp_path) -> None:
    assert harness.workspace_env(tmp_path, isolated_hermes_home=False) == {}
    env = harness.workspace_env(tmp_path, isolated_hermes_home=True, create=False)
    home = Path(env["HERMES_HOME"])
    assert home.parent == tmp_path and not home.exists()
    harness.workspace_env(tmp_path, isolated_hermes_home=True)
    assert home.is_dir()


def test_the_launcher_guard_sees_any_change(tmp_path) -> None:
    launchers = tmp_path / "bin"
    launchers.mkdir()
    (launchers / "hermes").write_text("exec /real/python3\n")
    before = harness.launcher_digest([launchers, tmp_path / "missing"])
    assert harness.launcher_digest([launchers]) == before
    (launchers / "hermes").write_text("exec /tmp/deleted/python3\n")
    assert harness.launcher_digest([launchers]) != before


def test_use_repo_points_git_at_another_clone(tmp_path) -> None:
    other = tmp_path / "other"
    other.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=other, check=True)
    original = harness.REPO
    try:
        harness.use_repo(other)
        top = harness.git("rev-parse", "--show-toplevel").decode().strip()
        assert Path(top).resolve() == other.resolve()
    finally:
        harness.use_repo(original)


def _fake_neuralmind(tmp_path: Path) -> tuple[str, Path]:
    """A `neuralmind` that counts its builds and writes a marker index."""
    counter = tmp_path / "builds"
    counter.write_text("0")
    script = tmp_path / "neuralmind"
    script.write_text(
        "#!/bin/sh\n"
        f'n=$(cat "{counter}"); echo $((n + 1)) > "{counter}"\n'
        'mkdir -p "$2/.neuralmind" && echo built > "$2/.neuralmind/graph.json"\n'
    )
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return str(script), counter


def test_the_index_cache_builds_once_and_restores_a_fresh_copy(tmp_path) -> None:
    nm, counter = _fake_neuralmind(tmp_path)
    cache = tmp_path / "cache"
    cache.mkdir()
    task = {"id": "abc123"}
    first, second = tmp_path / "ws1", tmp_path / "ws2"
    first.mkdir()
    second.mkdir()
    secs, cached = run._build_index(task, first, nm, dict(os.environ), cache)
    assert not cached and counter.read_text().strip() == "1"
    # A session writes into its index; the cache must not see it.
    (first / ".neuralmind" / "synapses.db").write_text("learned")
    again, cached = run._build_index(task, second, nm, dict(os.environ), cache)
    assert cached and again == secs
    assert counter.read_text().strip() == "1"
    assert (second / ".neuralmind" / "graph.json").read_text() == "built\n"
    assert not (second / ".neuralmind" / "synapses.db").exists()


def test_without_a_cache_every_run_builds(tmp_path) -> None:
    nm, counter = _fake_neuralmind(tmp_path)
    for name in ("ws1", "ws2"):
        ws = tmp_path / name
        ws.mkdir()
        run._build_index({"id": "abc123"}, ws, nm, dict(os.environ), None)
    assert counter.read_text().strip() == "2"
