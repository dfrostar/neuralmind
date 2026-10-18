"""``neuralmind data-locations``: every place a project's data lives, from the code.

The data deletion procedure listed these by hand, and seven rounds of review
each found one it missed. Each location here is resolved by the helper that
writes it; these tests put data in every one and check the list finds it, and
that listing changes nothing on disk.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from neuralmind import data_locations as dl
from neuralmind.audit_checkpoint import anchor_checkpoints_path
from neuralmind.hermes_install import plugin_dir
from neuralmind.synapse_memory import CLAUDE_AUTO_FILENAME, claude_auto_memory_dir


@pytest.fixture
def env(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("NEURALMIND_CONFIG_DIR", str(home / "config"))
    monkeypatch.delenv("HERMES_HOME", raising=False)
    audit_db = home / "config" / "audit.db"
    import neuralmind.tier2.config as tier2_config

    monkeypatch.setattr(
        tier2_config, "load_config", lambda *a, **k: SimpleNamespace(audit_db=str(audit_db))
    )
    project = tmp_path / "project"
    project.mkdir()
    return SimpleNamespace(home=home, project=project.resolve(), audit_db=audit_db, tmp=tmp_path)


def _by_name(project: Path) -> dict[str, dl.Location]:
    return {loc.name: loc for loc in dl.data_locations(project)}


def test_an_untouched_project_has_nothing_present(env):
    locations = dl.data_locations(env.project)
    assert locations and not [loc.name for loc in locations if loc.present]


def _populate(env) -> None:
    p, home = env.project, env.home
    (p / ".neuralmind").mkdir()
    (p / ".neuralmind-team-memory.json").write_text("{}", encoding="utf-8")
    index = env.tmp / "shared-index"
    index.mkdir()
    for name in ("store.sqlite", "store.sqlite-wal", "index.tvim.stale", "bm25_index.json"):
        (index / name).write_text("x", encoding="utf-8")
    (index / "unrelated.txt").write_text("keep me", encoding="utf-8")
    # A .yml config, with a db_path outside the project, an anchor directory,
    # and a malformed checkpoint key that must not hide the anchor.
    (p / "neuralmind-backend.yml").write_text(
        f"db_path: {index}\nsecurity:\n  audit_anchor_dir: ../anchor\n"
        "  audit_checkpoint_key: not-a-key\n",
        encoding="utf-8",
    )
    anchored = anchor_checkpoints_path(p, p / "../anchor")
    anchored.parent.mkdir(parents=True)
    anchored.write_text("{}\n", encoding="utf-8")

    export = claude_auto_memory_dir(p) / CLAUDE_AUTO_FILENAME
    export.parent.mkdir(parents=True)
    export.write_text("# NeuralMind", encoding="utf-8")
    log = home / ".neuralmind" / "memory" / "query_events.jsonl"
    log.parent.mkdir(parents=True)
    log.write_text(
        json.dumps({"project_path": str(p), "query": "a"})
        + "\n"
        + json.dumps({"project_path": "/elsewhere", "query": "b"})
        + "\nnot json\n",
        encoding="utf-8",
    )
    (home / "config").mkdir()
    (home / "config" / "projects.json").write_text(json.dumps([{"path": str(p)}]), encoding="utf-8")
    env.audit_db.write_text(json.dumps({"target": str(p)}) + "\n", encoding="utf-8")

    (p / ".claude").mkdir()
    (p / ".claude" / "settings.json").write_text(
        '{"command": "neuralmind _hook stale-guard"}', encoding="utf-8"
    )
    subprocess.run(["git", "init", "-q", str(p)], check=True)
    hook = p / ".git" / "hooks" / "post-commit"
    hook.write_text(
        "#!/bin/sh\n# neuralmind-hook-start\nneuralmind build .\n# neuralmind-hook-end\n"
    )
    pin = plugin_dir() / "config.json"
    pin.parent.mkdir(parents=True)
    pin.write_text(json.dumps({"project": str(p)}), encoding="utf-8")
    (p / "CLAUDE.md").write_text("# Notes\n@.neuralmind/SYNAPSE_MEMORY.md\n", encoding="utf-8")


def test_every_location_with_data_is_found(env):
    _populate(env)
    found = _by_name(env.project)
    expected_present = {
        ".neuralmind/",
        "team memory bundle",
        "config file",
        "index at db_path",
        "Claude Code synapse export",
        "global query log",
        "project registry",
        "anchored audit checkpoints",
        "Team governance audit log",
        "~/.neuralmind/",
        "Claude Code hooks",
        "git hook blocks",
        "Hermes plugin pin",
        "CLAUDE.md import line",
    }
    assert {name for name, loc in found.items() if loc.present} == expected_present
    assert found["config file"].path.endswith("neuralmind-backend.yml")
    index = found["index at db_path"]
    assert index.kind == dl.OUTSIDE
    assert index.detail == "bm25_index.json, index.tvim.stale, store.sqlite, store.sqlite-wal"
    assert "unrelated.txt" not in index.detail
    assert found["global query log"].detail == "1 line(s) from this project"
    assert found["git hook blocks"].detail == "post-commit"
    assert found["anchored audit checkpoints"].path == str(
        anchor_checkpoints_path(env.project, env.project / "../anchor")
    )


def _tree(root: Path) -> dict[str, float]:
    return {str(p): p.stat().st_mtime_ns for p in sorted(root.rglob("*"))}


def test_listing_changes_nothing_on_disk(env):
    _populate(env)
    before = _tree(env.tmp)
    dl.data_locations(env.project)
    assert _tree(env.tmp) == before


def test_a_symlinked_state_directory_is_listed_by_its_target(env):
    target = env.tmp / "elsewhere" / "state"
    target.mkdir(parents=True)
    try:
        (env.project / ".neuralmind").symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("can't create a symlink here")
    state = _by_name(env.project)[".neuralmind/"]
    assert state.present and state.kind == dl.OUTSIDE
    assert state.path == str(target.resolve())
    # rm -rf on the link alone leaves the data, so both are named.
    assert state.remove == f"rm -rf {target.resolve()} && rm {env.project / '.neuralmind'}"


def test_the_cli_prints_json(env, capsys):
    _populate(env)
    from neuralmind.cli import cmd_data_locations

    cmd_data_locations(SimpleNamespace(project_path=str(env.project), json=True))
    payload = json.loads(capsys.readouterr().out)
    assert payload["project"] == str(env.project)
    assert {loc["name"] for loc in payload["locations"] if loc["present"]} >= {"index at db_path"}


def test_the_cli_is_registered():
    out = subprocess.run(
        [sys.executable, "-m", "neuralmind.cli", "data-locations", "--help"],
        capture_output=True,
        text=True,
    )
    assert out.returncode == 0 and "read-only" in out.stdout
