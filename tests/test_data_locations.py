"""``neuralmind data-locations``: every place a project's data lives, from the code.

The data deletion procedure listed these by hand, and seven rounds of review
each found one it missed. Each location here is resolved by the helper that
writes it; these tests put data in every one and check the list finds it, and
that listing changes nothing on disk.
"""

from __future__ import annotations

import json
import os
import shlex
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
    monkeypatch.delenv("HERMES_DATA_DIR_SUFFIX", raising=False)
    # Hermes's default home on Windows is under LOCALAPPDATA, not HOME.
    monkeypatch.setenv("LOCALAPPDATA", str(home / "AppData" / "Local"))
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
    from neuralmind.cli import _post_commit_block

    hook = p / ".git" / "hooks" / "post-commit"
    hook.write_text("#!/bin/sh\n" + _post_commit_block(".", "neuralmind", False))
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
        anchor_checkpoints_path(env.project, env.project / "../anchor").resolve()
    )


def _tree(root: Path) -> dict[str, float]:
    return {str(p): p.stat().st_mtime_ns for p in sorted(root.rglob("*"))}


def test_every_remove_command_runs_as_printed(env, tmp_path, monkeypatch):
    # From any directory: absolute paths, and conditions as shell comments.
    _populate(env)
    monkeypatch.chdir(tmp_path)
    locations = dl.data_locations(env.project)
    for loc in locations:
        if loc.remove.startswith(("rm ", "neuralmind ")):
            words = shlex.split(loc.remove, comments=True)
            assert not [w for w in words if w.startswith("(")], loc.remove
        if loc.remove.startswith("rm "):
            paths = [
                w
                for w in shlex.split(loc.remove, comments=True)
                if w not in ("rm", "-rf", "-f", "&&")
            ]
            assert paths and all(Path(p).is_absolute() for p in paths), loc.remove
    hooks = {loc.name: loc for loc in locations}["Claude Code hooks"]
    assert shlex.split(hooks.remove)[2] == str(env.project)


def test_a_symlinked_export_is_removed_with_its_target(env):
    from neuralmind.synapse_memory import CLAUDE_AUTO_FILENAME, claude_auto_memory_dir

    target = env.tmp / "elsewhere" / CLAUDE_AUTO_FILENAME
    target.parent.mkdir()
    target.write_text("# NeuralMind", encoding="utf-8")
    link = claude_auto_memory_dir(env.project) / CLAUDE_AUTO_FILENAME
    link.parent.mkdir(parents=True)
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("can't create a symlink here")
    export = _by_name(env.project)["Claude Code synapse export"]
    assert export.present and export.path == str(target.resolve())
    assert shlex.split(export.remove) == [
        "rm", "-f", str(target.resolve()), "&&", "rm", str(link)
    ]  # fmt: skip


def test_chroma_journals_at_db_path_are_listed(env):
    # An interrupted ChromaDB process leaves -wal and -shm journals, and the
    # WAL can hold indexed text.
    index = env.tmp / "chroma-index"
    index.mkdir()
    for name in ("chroma.sqlite3", "chroma.sqlite3-wal", "chroma.sqlite3-shm"):
        (index / name).write_text("x", encoding="utf-8")
    (env.project / "neuralmind-backend.yaml").write_text(f"db_path: {index}\n", encoding="utf-8")
    found = _by_name(env.project)["index at db_path"]
    assert found.detail == "chroma.sqlite3, chroma.sqlite3-shm, chroma.sqlite3-wal"
    assert str(index / "chroma.sqlite3-wal") in shlex.split(found.remove, comments=True)


def test_a_symlinked_index_file_is_removed_with_its_target(env):
    index = env.tmp / "linked-index"
    index.mkdir()
    real = env.tmp / "other-disk" / "store.sqlite"
    real.parent.mkdir()
    real.write_text("x", encoding="utf-8")
    try:
        (index / "store.sqlite").symlink_to(real)
    except OSError:
        pytest.skip("can't create a symlink here")
    (env.project / "neuralmind-backend.yaml").write_text(f"db_path: {index}\n", encoding="utf-8")
    found = _by_name(env.project)["index at db_path"]
    words = shlex.split(found.remove, comments=True)
    target = str(real.resolve())
    assert words == [
        "rm", "-f", target, "&&",
        "rm", "-f", f"{target}-wal", f"{target}-shm", f"{target}-journal", "&&",
        "rm", str(index / "store.sqlite"),
    ]  # fmt: skip


def test_a_relative_team_audit_db_is_removed_by_absolute_path(env, monkeypatch, tmp_path):
    import neuralmind.tier2.config as tier2_config

    workdir = tmp_path / "work dir"
    (workdir / "logs").mkdir(parents=True)
    (workdir / "logs" / "audit.jsonl").write_text(
        json.dumps({"target": str(env.project)}) + "\n", encoding="utf-8"
    )
    monkeypatch.chdir(workdir)
    monkeypatch.setattr(
        tier2_config,
        "load_config",
        lambda *_a, **_k: SimpleNamespace(audit_db="logs/audit.jsonl"),
    )
    log = _by_name(env.project)["Team governance audit log"]
    absolute = str((workdir / "logs" / "audit.jsonl").resolve())
    assert log.present and log.path == absolute
    assert shlex.split(log.remove, comments=True) == ["rm", absolute]
    # Other processes' copies can't be found, so the list says it's incomplete.
    assert "relative path" in log.problem


def test_a_db_path_that_isnt_a_path_is_reported(env):
    (env.project / "neuralmind-backend.yaml").write_text("db_path: [shared]\n", encoding="utf-8")
    config = _by_name(env.project)["config file"]
    assert "db_path is ['shared'], not a path" in config.problem


def test_a_shared_hook_block_counts_only_for_the_project_it_names(env):
    # A monorepo's projects share one hooks directory, whose block names one.
    from neuralmind.cli import _post_commit_block

    repo = env.tmp / "mono"
    (repo / "app a").mkdir(parents=True)
    (repo / "app-b").mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    (repo / ".git" / "hooks" / "post-commit").write_text(
        "#!/bin/sh\n" + _post_commit_block(shlex.quote("app a"), "neuralmind", False)
    )
    assert _by_name((repo / "app a").resolve())["git hook blocks"].detail == "post-commit"
    assert not _by_name((repo / "app-b").resolve())["git hook blocks"].present
    assert not _by_name(repo.resolve())["git hook blocks"].present


def test_no_git_on_the_path_means_no_hook_blocks_to_list(env, monkeypatch):
    # git is found by absolute path before it runs; without one there's nothing to ask.
    subprocess.run(["git", "init", "-q", str(env.project)], check=True)
    monkeypatch.setattr(dl.shutil, "which", lambda name: None)
    assert "git hook blocks" not in _by_name(env.project)


def test_a_hooks_directory_that_cant_be_listed_is_a_problem(env, monkeypatch):
    subprocess.run(["git", "init", "-q", str(env.project)], check=True)
    hooks = (env.project / ".git" / "hooks").resolve()
    real_iterdir = Path.iterdir

    def denied(self):
        if self.resolve() == hooks:
            raise PermissionError(13, "Permission denied")
        return real_iterdir(self)

    monkeypatch.setattr(Path, "iterdir", denied)
    found = _by_name(env.project)["git hook blocks"]
    assert found.present and "can't be listed" in found.problem


def test_a_file_that_cant_be_read_is_a_problem_not_absent(env):
    # A directory where a file should be can't be read on any platform (a
    # chmod wouldn't stop root). Each would otherwise be listed as absent,
    # and the inventory would look complete.
    from neuralmind import memory
    from neuralmind.hermes_install import plugin_dir

    unreadable = {
        "Team governance audit log": env.audit_db,
        "global query log": memory.global_query_events_file(),
        "project registry": env.home / "config" / "projects.json",
        "Claude Code hooks": env.project / ".claude" / "settings.json",
        "Hermes plugin pin": plugin_dir() / "config.json",
        "CLAUDE.md import line": env.project / "CLAUDE.md",
    }
    for path in unreadable.values():
        path.mkdir(parents=True)
    found = _by_name(env.project)
    for name in unreadable:
        assert found[name].present and "can't be read" in found[name].problem, name


def test_shared_log_lines_that_cant_be_parsed_are_a_problem(env):
    # A line cut short may still hold this project's query text, and the
    # deletion script keeps lines it can't parse, so they can't count as absent.
    from neuralmind import memory

    log = memory.global_query_events_file()
    log.parent.mkdir(parents=True)
    log.write_text(f'{{"project_path": "{env.project}", "query": "where is au\n', encoding="utf-8")
    env.audit_db.parent.mkdir(parents=True)
    env.audit_db.write_text('{"target": "/elsewhere"}\n{"target": "/wor\n', encoding="utf-8")
    found = _by_name(env.project)
    for name in ("global query log", "Team governance audit log"):
        assert found[name].present and "can't be parsed" in found[name].problem, name


@pytest.mark.skipif(
    sys.platform == "win32", reason="Windows collapses .. before following a symlink"
)
def test_a_path_through_a_symlink_and_dot_dot_is_removed_where_the_os_finds_it(env):
    # link/../index is the index beside link's target, not <project>/index.
    real = env.tmp / "disk" / "sub"
    real.mkdir(parents=True)
    index = env.tmp / "disk" / "index"
    index.mkdir()
    (index / "store.sqlite").write_text("x", encoding="utf-8")
    try:
        (env.project / "link").symlink_to(real, target_is_directory=True)
    except OSError:
        pytest.skip("can't create a symlink here")
    (env.project / "neuralmind-backend.yaml").write_text(
        "db_path: link/../index\n", encoding="utf-8"
    )
    found = _by_name(env.project)["index at db_path"]
    assert shlex.split(found.remove, comments=True) == [
        "rm",
        "-f",
        str((index / "store.sqlite").resolve()),
    ]


def test_a_symlink_inside_the_state_directory_is_listed_by_its_target(env):
    # rm -rf .neuralmind/ would remove the link and leave the index it points to.
    external = env.tmp / "fast-disk" / "turbovec"
    external.mkdir(parents=True)
    (env.project / ".neuralmind").mkdir()
    try:
        (env.project / ".neuralmind" / "neuralmind_turbovec").symlink_to(
            external, target_is_directory=True
        )
    except OSError:
        pytest.skip("can't create a symlink here")
    linked = [loc for loc in dl.data_locations(env.project) if "a symlink in" in loc.name]
    assert len(linked) == 1 and linked[0].present
    assert linked[0].path == str(external.resolve()) and linked[0].kind == dl.OUTSIDE


def test_symlinks_inside_a_symlinked_state_directory_are_listed(env):
    state = env.tmp / "disk" / "state"
    state.mkdir(parents=True)
    index = env.tmp / "other" / "index"
    index.mkdir(parents=True)
    try:
        (env.project / ".neuralmind").symlink_to(state, target_is_directory=True)
        (state / "neuralmind_turbovec").symlink_to(index, target_is_directory=True)
    except OSError:
        pytest.skip("can't create a symlink here")
    linked = [loc for loc in dl.data_locations(env.project) if "a symlink in" in loc.name]
    assert [loc.path for loc in linked] == [str(index.resolve())]


def test_a_relative_config_dir_is_pinned_in_the_registry_command(env, monkeypatch, tmp_path):
    workdir = tmp_path / "work"
    (workdir / "cfg").mkdir(parents=True)
    (workdir / "cfg" / "projects.json").write_text(json.dumps([{"path": str(env.project)}]))
    monkeypatch.chdir(workdir)
    monkeypatch.setenv("NEURALMIND_CONFIG_DIR", "cfg")
    registry = _by_name(env.project)["project registry"]
    assert registry.present and registry.path == str((workdir / "cfg" / "projects.json").resolve())
    words = shlex.split(registry.remove)
    assert words[0] == f"NEURALMIND_CONFIG_DIR={(workdir / 'cfg').resolve()}"


@pytest.mark.parametrize("target_name", ["synapses.db", "synapses"])
def test_a_symlinked_sqlite_database_is_removed_with_its_journals(env, target_name):
    # SQLite writes -wal/-shm beside the database itself, not beside the link,
    # and the link's name is enough to know it's a database.
    real = env.tmp / "disk" / target_name
    real.parent.mkdir()
    real.write_text("x", encoding="utf-8")
    (env.tmp / "disk" / f"{target_name}-wal").write_text("x", encoding="utf-8")
    (env.project / ".neuralmind").mkdir()
    try:
        (env.project / ".neuralmind" / "synapses.db").symlink_to(real)
    except OSError:
        pytest.skip("can't create a symlink here")
    (linked,) = [loc for loc in dl.data_locations(env.project) if "a symlink in" in loc.name]
    words = shlex.split(linked.remove)
    assert f"{real.resolve()}-wal" in words and f"{real.resolve()}-shm" in words
    assert words[-1] == str(env.project / ".neuralmind" / "synapses.db")


def test_a_database_link_whose_target_is_gone_is_present_for_its_journals(env):
    # The WAL can outlive the database, and removing .neuralmind/ would lose
    # the only link to it.
    real = env.tmp / "disk" / "synapses.db"
    real.parent.mkdir()
    (env.tmp / "disk" / "synapses.db-wal").write_text("x", encoding="utf-8")
    (env.project / ".neuralmind").mkdir()
    try:
        (env.project / ".neuralmind" / "synapses.db").symlink_to(real)
    except OSError:
        pytest.skip("can't create a symlink here")
    (linked,) = [loc for loc in dl.data_locations(env.project) if "a symlink in" in loc.name]
    assert linked.present and f"{real.resolve()}-wal" in shlex.split(linked.remove)


def test_the_db_path_command_keeps_the_directory_out_of_its_comment(env):
    # A newline in the path would end the comment and run what follows.
    index = env.tmp / "idx"
    index.mkdir()
    (index / "store.sqlite").write_text("x", encoding="utf-8")
    (env.project / "neuralmind-backend.yaml").write_text(f"db_path: {index}\n", encoding="utf-8")
    remove = _by_name(env.project)["index at db_path"].remove
    assert remove.split("#", 1)[1] == " then the directory itself, if nothing else is in it"


@pytest.mark.skipif(sys.platform == "win32", reason="runs the printed command with sh")
def test_index_files_linked_to_each_other_are_all_removed(env):
    # A second rm of a file a link already took would fail and stop the rest.
    index = env.tmp / "index"
    index.mkdir()
    for name in (
        "index.b.tvim",
        "index.current.tvim",
        "store.v1.sqlite",
        "store.v1.sqlite-wal",
        "store.z.sqlite",
    ):
        (index / name).write_text("x", encoding="utf-8")
    try:
        (index / "index.a.tvim").symlink_to(index / "index.b.tvim")  # the link sorts first
        (index / "index.tvim").symlink_to(index / "index.current.tvim")  # its target does
        # The link's command takes store.v1.sqlite-wal too, before its own turn.
        (index / "store.sqlite").symlink_to(index / "store.v1.sqlite")
    except OSError:
        pytest.skip("can't create a symlink here")
    (env.project / "neuralmind-backend.yaml").write_text(f"db_path: {index}\n", encoding="utf-8")
    found = _by_name(env.project)["index at db_path"]
    subprocess.run(["sh", "-c", found.remove], check=True)
    assert list(index.iterdir()) == []


def test_a_state_subdirectory_that_cant_be_listed_is_a_problem(env, monkeypatch):
    # os.walk skips it without a word, and a symlink in it would go unlisted.
    locked = env.project / ".neuralmind" / "cache"
    locked.mkdir(parents=True)
    real_scandir = os.scandir

    def denied(path=".", *args, **kwargs):
        if isinstance(path, (str, os.PathLike)) and Path(path) == locked:
            raise PermissionError(13, "Permission denied", str(path))
        return real_scandir(path, *args, **kwargs)

    monkeypatch.setattr(os, "scandir", denied)
    state = _by_name(env.project)[".neuralmind/"]
    assert state.present and "can't be listed" in state.problem
    assert str(locked) in state.problem


def test_an_index_directory_that_cant_be_listed_is_a_problem(env, monkeypatch):
    index = env.tmp / "locked-index"
    index.mkdir()
    (env.project / "neuralmind-backend.yaml").write_text(f"db_path: {index}\n", encoding="utf-8")
    real_glob = Path.glob

    def denied(self, pattern):
        if self == index:
            raise PermissionError(13, "Permission denied")
        return real_glob(self, pattern)

    monkeypatch.setattr(Path, "glob", denied)
    found = _by_name(env.project)["index at db_path"]
    assert found.present and "can't be listed" in found.problem


def test_a_relative_hermes_home_is_pinned_in_the_unpin_command(env, monkeypatch, tmp_path):
    from neuralmind.hermes_install import plugin_dir

    workdir = tmp_path / "w"
    workdir.mkdir()
    monkeypatch.chdir(workdir)
    monkeypatch.setenv("HERMES_HOME", "hermes")
    pin = plugin_dir() / "config.json"
    pin.parent.mkdir(parents=True)
    pin.write_text(json.dumps({"project": str(env.project)}), encoding="utf-8")
    found = _by_name(env.project)["Hermes plugin pin"]
    assert found.present and Path(found.path).is_absolute()
    assert shlex.split(found.remove)[0] == f"HERMES_HOME={(workdir / 'hermes').resolve()}"


def test_a_team_config_no_loader_can_read_still_lists_the_log(env, monkeypatch):
    import neuralmind.tier2.config as tier2_config

    def load_config(*_a, **_k):
        raise ValueError("seats must be an integer")

    monkeypatch.setattr(tier2_config, "load_config", load_config)
    log = _by_name(env.project)["Team governance audit log"]
    assert "Team config can't be read" in log.problem


def test_a_team_audit_db_under_tilde_is_read_as_the_writers_read_it(env, monkeypatch):
    # The Team writers don't expand ~, so ~/logs/audit.jsonl is relative.
    import neuralmind.tier2.config as tier2_config

    monkeypatch.setattr(
        tier2_config,
        "load_config",
        lambda *_a, **_k: SimpleNamespace(audit_db="~/logs/audit.jsonl"),
    )
    assert "relative path" in _by_name(env.project)["Team governance audit log"].problem


def test_an_unreadable_team_config_is_reported(env, monkeypatch):
    import neuralmind.tier2.config as tier2_config

    def load_config(*_a, strict=False, **_k):
        if strict:
            raise ValueError("tier2.yaml: expected a mapping")
        return SimpleNamespace(audit_db=str(env.audit_db))

    monkeypatch.setattr(tier2_config, "load_config", load_config)
    log = _by_name(env.project)["Team governance audit log"]
    assert "Team config can't be read" in log.problem and "audit_db" in log.problem


def test_an_unreadable_config_is_reported_not_ignored(env, capsys):
    # A broken config hides the db_path index and anchor it names: say so.
    (env.project / "neuralmind-backend.yaml").write_text("db_path: [unclosed\n", encoding="utf-8")
    config = _by_name(env.project)["config file"]
    assert config.present and "can't be read" in config.problem
    assert "db_path" in config.problem
    from neuralmind.cli import cmd_data_locations

    cmd_data_locations(SimpleNamespace(project_path=str(env.project), json=False))
    out = capsys.readouterr().out
    assert "problem: can't be read" in out
    assert "the list may be incomplete" in out


def test_listing_changes_nothing_on_disk(env):
    _populate(env)
    before = _tree(env.tmp)
    dl.data_locations(env.project)
    assert _tree(env.tmp) == before


def test_the_team_audit_log_is_found_by_its_escaped_path(env):
    # The Team audit log is written with json.dumps, which escapes non-ASCII
    # characters (and, on Windows, backslashes) in the project's path.
    project = env.tmp / "projé"
    project.mkdir()
    env.audit_db.parent.mkdir(parents=True)
    env.audit_db.write_text(json.dumps({"target": str(project.resolve())}) + "\n")
    assert "\\u00e9" in env.audit_db.read_text()
    assert _by_name(project)["Team governance audit log"].present


def test_the_team_audit_log_isnt_claimed_for_a_path_that_only_starts_the_same(env):
    # Deleting the shared audit log erases every project's records, so a
    # record for project-old must not make it look like project's.
    env.audit_db.parent.mkdir(parents=True)
    other = f"{env.project}-old"
    env.audit_db.write_text(
        json.dumps({"target": other, "details": {"bundle": f"{other}/b.json"}}) + "\n"
    )
    assert not _by_name(env.project)["Team governance audit log"].present
    with env.audit_db.open("a") as log:
        log.write(json.dumps({"details": {"bundle": f"{env.project}/b.json"}}) + "\n")
    assert _by_name(env.project)["Team governance audit log"].present


def test_a_symlinked_state_directory_is_listed_by_its_target(env):
    target = env.tmp / "else where" / "state"  # a space: the command must quote it
    target.mkdir(parents=True)
    try:
        (env.project / ".neuralmind").symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("can't create a symlink here")
    state = _by_name(env.project)[".neuralmind/"]
    assert state.present and state.kind == dl.OUTSIDE
    assert state.path == str(target.resolve())
    # rm -rf on the link alone leaves the data, so both are named.
    link = env.project / ".neuralmind"
    assert (
        state.remove
        == f"rm -rf {shlex.quote(str(target.resolve()))} && rm {shlex.quote(str(link))}"
    )
    assert shlex.split(state.remove)[2] == str(target.resolve())


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
