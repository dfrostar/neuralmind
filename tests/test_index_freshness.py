"""v4.4.0 index freshness: the index must never be silently out of step.

Spec 1 — graph freshness check (doctor / health / build / MCP wakeup)
Spec 2 — escaping a stale graphify graph (--regenerate-graph, graph_source)
Spec 3 — purging orphaned vectors on every build
Spec 8 — read paths load the index as it stands: no rebuild, no output

Embeddings use a deterministic hashing function injected into the turbovec
backend, so nothing here needs the ONNX model.
"""

from __future__ import annotations

import builtins
import hashlib
import io
import json
import os
import pathlib
import shutil
import subprocess
import time
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from neuralmind import freshness
from neuralmind.freshness import FAIL, OK, WARN, graph_freshness

pytest.importorskip("turbovec")

_DIM = 32


def _fake_embed(texts: list[str]) -> list[list[float]]:
    out = []
    for t in texts:
        vec = np.zeros(_DIM, dtype=np.float32)
        for tok in t.lower().replace("\n", " ").split():
            vec[int.from_bytes(hashlib.md5(tok.encode()).digest()[:4], "little") % _DIM] += 1.0
        out.append(vec.tolist())
    return out


def _write_files(root: Path, rels: list[str]) -> None:
    for rel in rels:
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        stem = p.stem.replace("-", "_")
        p.write_text(
            f'def {stem}_fn():\n    """{stem} helper."""\n    return 1\n', encoding="utf-8"
        )


def _graphify_graph(rels: list[str], *, windows: bool = False, per_file: int = 1) -> dict:
    nodes = []
    for rel in rels:
        sf = rel.replace("/", "\\") if windows else rel
        for i in range(per_file):
            nodes.append(
                {
                    "id": f"{rel.replace('/', '_').replace('.', '_')}_{i}",
                    "label": f"{Path(rel).stem}_{i}",
                    "file_type": "code",
                    "source_file": sf,
                    "community": 0,
                }
            )
    return {"nodes": nodes, "links": []}


def _write_graphify(root: Path, graph: dict) -> Path:
    out = root / "graphify-out" / "graph.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(graph), encoding="utf-8")
    return out


def _bump_mtime(path: Path, seconds: float = 5.0) -> None:
    st = path.stat()
    os.utime(path, (st.st_atime + seconds, st.st_mtime + seconds))


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "GIT_AUTHOR_NAME": "t",
            "GIT_AUTHOR_EMAIL": "t@example.com",
            "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@example.com",
        },
    ).stdout


needs_git = pytest.mark.skipif(shutil.which("git") is None, reason="git not installed")

# '\\' in a node path only means "built on another OS" on a POSIX host.
POSIX = os.sep == "/"


def _mind(root: Path, **kwargs):
    from neuralmind.core import NeuralMind

    mind = NeuralMind(str(root), backend_type="turbovec", **kwargs)
    mind.embedder._embed_fn = _fake_embed
    mind.notice_stream = io.StringIO()
    return mind


def _set_graph_source(root: Path, value: str) -> None:
    (root / ".neuralmind.yaml").write_text(f"graph_source: {value}\n", encoding="utf-8")


# --------------------------------------------------------------------------- #
# Spec 1 — freshness report
# --------------------------------------------------------------------------- #
class TestFreshnessReport:
    def test_windows_graphify_graph_missing_modules_fails(self, tmp_path):
        known = [f"pkg/mod_{i}.py" for i in range(6)]
        new = ["pkg/new_a.py", "pkg/new_b.py", "tools/new_c.py"]
        _write_files(tmp_path, known + new)
        _write_graphify(tmp_path, _graphify_graph(known, windows=True, per_file=2))

        report = graph_freshness(tmp_path)

        assert report.status == FAIL  # 3 of 9 files missing: over the 10% bar
        assert report.source == "graphify"
        assert report.missing_from_graph == sorted(new)
        assert report.gone_from_disk == []  # '\\' paths normalise onto the tree
        text = report.render()
        for rel in new:
            assert rel in text
        assert "--regenerate-graph" in text
        if POSIX:
            assert report.foreign_separators == 12
            assert report.foreign_separator_files == 6
            assert "12 node paths (6 files) use '\\' separators" in text
        else:  # '\\' is the native separator on Windows, not a foreign one
            assert report.foreign_separators == 0

    def test_doctor_fails_and_names_the_modules(self, tmp_path):
        from neuralmind import doctor

        known = [f"pkg/mod_{i}.py" for i in range(6)]
        new = ["pkg/new_a.py", "pkg/new_b.py", "tools/new_c.py"]
        _write_files(tmp_path, known + new)
        _write_graphify(tmp_path, _graphify_graph(known, windows=True))

        check = doctor._check_graph(tmp_path)

        assert check.status == doctor.FAIL
        for rel in new:
            assert rel in check.detail
        assert ("separators" in check.detail) is POSIX
        assert "--regenerate-graph" in check.fix

    def test_built_in_graph_one_file_edited_warns(self, tmp_path):
        from neuralmind import graphgen

        if not graphgen.is_available():
            pytest.skip("tree-sitter not installed")
        _write_files(tmp_path, ["a.py", "b.py", "c.py"])
        mind = _mind(tmp_path)
        assert mind.build()["success"]
        assert graph_freshness(tmp_path).status == OK

        edited = tmp_path / "b.py"
        edited.write_text("def b_fn():\n    return 2\n", encoding="utf-8")
        _bump_mtime(edited)

        report = graph_freshness(tmp_path)
        assert report.status == WARN
        assert report.changed_since_graph == ["b.py"]
        assert "b.py" in report.render()

    def test_touch_without_content_change_is_not_reported(self, tmp_path):
        from neuralmind import graphgen

        if not graphgen.is_available():
            pytest.skip("tree-sitter not installed")
        _write_files(tmp_path, ["a.py", "b.py"])
        assert _mind(tmp_path).build()["success"]
        _bump_mtime(tmp_path / "a.py")  # same bytes, newer mtime

        assert graph_freshness(tmp_path).status == OK

    def test_gone_from_disk_is_reported(self, tmp_path):
        rels = [f"m{i}.py" for i in range(20)]
        _write_files(tmp_path, rels)
        _write_graphify(tmp_path, _graphify_graph(rels))
        (tmp_path / "m3.py").unlink()

        report = graph_freshness(tmp_path)
        assert report.gone_from_disk == ["m3.py"]
        assert report.status == WARN  # 1 of 19 files: below the 10% bar

    def test_fresh_graph_is_ok_and_fast(self, tmp_path):
        rels = [f"pkg{i // 40}/mod_{i}.py" for i in range(400)]
        _write_files(tmp_path, rels)
        _write_graphify(tmp_path, _graphify_graph(rels, per_file=3))

        graph_freshness(tmp_path)  # warm imports and grammar loading
        start = time.perf_counter()
        report = graph_freshness(tmp_path)
        elapsed = time.perf_counter() - start

        assert report.status == OK
        assert report.indexable_count == 400
        # Spec budget is 300 ms on a 400-file repo; leave headroom for slow CI.
        assert elapsed < 1.0, f"freshness check took {elapsed:.3f}s"

    def test_graphify_graph_without_markdown_does_not_flag_readmes(self, tmp_path):
        _write_files(tmp_path, ["a.py"])
        (tmp_path / "README.md").write_text("# hi\n", encoding="utf-8")
        _write_graphify(tmp_path, _graphify_graph(["a.py"]))

        assert graph_freshness(tmp_path).status == OK

    def test_graphify_graph_notices_a_new_language(self, tmp_path):
        from neuralmind import graphgen

        if not graphgen.language_available("typescript"):
            pytest.skip("typescript grammar not installed")
        _write_files(tmp_path, ["a.py"])
        (tmp_path / "web.ts").write_text("export const x = 1;\n", encoding="utf-8")
        _write_graphify(tmp_path, _graphify_graph(["a.py"]))  # Python only
        assert graph_freshness(tmp_path).missing_from_graph == ["web.ts"]

    def test_unknown_producer_with_no_file_paths_is_not_current(self, tmp_path):
        _write_files(tmp_path, ["a.py"])
        gpath = tmp_path / ".neuralmind" / "graph.json"
        gpath.parent.mkdir()
        gpath.write_text(
            json.dumps({"generated_by": "sometool", "nodes": [{"id": "x"}]}), encoding="utf-8"
        )
        assert graph_freshness(tmp_path).missing_from_graph == ["a.py"]

    def test_no_graph_returns_none(self, tmp_path):
        assert graph_freshness(tmp_path) is None

    def test_one_line_for_the_wakeup(self, tmp_path):
        _write_files(tmp_path, ["a.py", "b.py"])
        _write_graphify(tmp_path, _graphify_graph(["a.py"]))
        line = graph_freshness(tmp_path).one_line(".")
        assert line == (
            "Index is stale: 1 files missing from graph. "
            "Run neuralmind build . --regenerate-graph."
        )


@needs_git
class TestFreshnessWithGit:
    def _repo(self, root: Path, rels: list[str]) -> None:
        _write_files(root, rels)
        _write_graphify(root, _graphify_graph(rels))
        _git(root, "init", "-q")
        _git(root, "add", "-A")
        _git(root, "commit", "-q", "-m", "graph")

    def test_commits_behind_and_changed_files(self, tmp_path):
        self._repo(tmp_path, ["a.py", "b.py", "c.py"])
        (tmp_path / "b.py").write_text("def b_fn():\n    return 3\n", encoding="utf-8")
        _git(tmp_path, "commit", "-qam", "edit b")
        (tmp_path / "c.py").write_text("def c_fn():\n    return 4\n", encoding="utf-8")
        _git(tmp_path, "commit", "-qam", "edit c")

        report = graph_freshness(tmp_path)
        assert report.graph_age_commits == 2
        assert report.changed_method == "git"
        assert report.changed_since_graph == ["b.py", "c.py"]
        assert report.status == WARN
        assert "2 commits behind HEAD" in report.header()

    def test_project_in_a_subdirectory_of_a_larger_repo(self, tmp_path):
        """Paths and commit counts are the project's, not the whole repo's."""
        project = tmp_path / "services" / "api"
        project.mkdir(parents=True)
        _write_files(project, ["a.py", "b.py"])
        _write_graphify(project, _graphify_graph(["a.py", "b.py"]))
        _write_files(tmp_path, ["other/x.py"])
        _git(tmp_path, "init", "-q")
        _git(tmp_path, "add", "-A")
        _git(tmp_path, "commit", "-q", "-m", "graph")
        (project / "a.py").write_text("def a_fn():\n    return 5\n", encoding="utf-8")
        _git(tmp_path, "commit", "-qam", "edit a")
        (tmp_path / "other" / "x.py").write_text("X = 1\n", encoding="utf-8")
        _git(tmp_path, "commit", "-qam", "unrelated")

        report = graph_freshness(project)
        assert report.changed_method == "git"
        assert report.changed_since_graph == ["a.py"]
        assert report.graph_age_commits == 1  # the unrelated commit doesn't count

    def test_no_git_process_outside_a_repository(self, tmp_path, monkeypatch):
        _write_files(tmp_path, ["a.py"])
        _write_graphify(tmp_path, _graphify_graph(["a.py"]))
        calls: list[tuple] = []
        monkeypatch.setattr(freshness, "_git", lambda *a: calls.append(a))
        if any((p / ".git").exists() for p in (tmp_path, *tmp_path.parents)):
            pytest.skip("temp dir is inside a git work tree")

        assert graph_freshness(tmp_path).status == OK
        assert calls == []

    def test_fresh_clone_mtimes_never_count(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        self._repo(src, ["a.py", "b.py"])
        clone = tmp_path / "clone"
        _git(tmp_path, "clone", "-q", str(src), str(clone))
        for rel in ("a.py", "b.py"):  # checkout order can leave files newer than the graph
            _bump_mtime(clone / rel, 60)

        report = graph_freshness(clone)
        assert report.status == OK
        assert report.changed_since_graph == []
        assert report.graph_age_commits == 0

    def test_shallow_clone_reports_age_unknown(self, tmp_path):
        src = tmp_path / "src"
        src.mkdir()
        self._repo(src, ["a.py", "b.py"])
        (src / "b.py").write_text("def b_fn():\n    return 9\n", encoding="utf-8")
        _git(src, "commit", "-qam", "later")
        clone = tmp_path / "clone"
        _git(tmp_path, "clone", "-q", "--depth", "1", f"file://{src}", str(clone))

        report = graph_freshness(clone)
        assert report.graph_age_commits is None
        assert "shallow clone" in report.age_note
        assert "0 commits" not in report.header()
        assert report.graph_date is None  # the checkout date is not the graph's date


class TestHealth:
    def _run(self, root: Path, capsys) -> tuple[int, dict]:
        from neuralmind.cli_health import cmd_health

        with pytest.raises(SystemExit) as exc:
            cmd_health(SimpleNamespace(project_path=str(root), json=True))
        return exc.value.code, json.loads(capsys.readouterr().out)

    def _index(self, root: Path) -> None:
        nm = root / ".neuralmind"
        nm.mkdir(parents=True, exist_ok=True)
        (nm / "index_ir.json").write_text(json.dumps({"node_count": 1}), encoding="utf-8")

    def test_no_index_exits_2(self, tmp_path, capsys):
        code, data = self._run(tmp_path, capsys)
        assert code == 2
        assert data["status"] == "no_index"

    def test_fresh_graph_exits_0_whatever_its_age(self, tmp_path, capsys):
        _write_files(tmp_path, ["a.py"])
        _write_graphify(tmp_path, _graphify_graph(["a.py"]))
        self._index(tmp_path)
        old = time.time() - 3 * 86400
        os.utime(tmp_path / ".neuralmind" / "index_ir.json", (old, old))

        code, data = self._run(tmp_path, capsys)
        assert code == 0
        assert data["freshness"]["status"] == OK

    def test_stale_graph_exits_1(self, tmp_path, capsys):
        _write_files(tmp_path, ["a.py", "b.py"])
        _write_graphify(tmp_path, _graphify_graph(["a.py"]))
        self._index(tmp_path)

        code, data = self._run(tmp_path, capsys)
        assert code == 1
        assert data["status"] == "stale"
        assert data["freshness"]["missing_from_graph"] == ["b.py"]

    def test_no_graph_to_check_is_unknown_never_healthy(self, tmp_path, capsys):
        from neuralmind.mcp_server import tool_health

        _write_files(tmp_path, ["a.py"])
        self._index(tmp_path)  # an index, but no graph.json to compare it with

        code, data = self._run(tmp_path, capsys)
        assert code == 1
        assert data["status"] == "unknown"
        assert data["healthy"] is False
        mcp = tool_health(str(tmp_path))
        assert (mcp["status"], mcp["healthy"], mcp["exit_code"]) == ("unknown", False, 1)


class TestMcpWakeupLine:
    def test_stale_graph_prefixes_one_line(self, tmp_path):
        from neuralmind.mcp_server import _freshness_line

        _write_files(tmp_path, ["a.py", "b.py"])
        _write_graphify(tmp_path, _graphify_graph(["a.py"]))
        line = _freshness_line(str(tmp_path))
        assert line.startswith("Index is stale: 1 files missing from graph.")
        assert "--regenerate-graph" in line

    def test_fresh_graph_adds_nothing(self, tmp_path):
        from neuralmind.mcp_server import _freshness_line

        _write_files(tmp_path, ["a.py"])
        _write_graphify(tmp_path, _graphify_graph(["a.py"]))
        assert _freshness_line(str(tmp_path)) == ""

    def test_index_without_a_graph_is_unverified(self, tmp_path):
        from neuralmind.mcp_server import _freshness_line

        _write_files(tmp_path, ["a.py"])
        (tmp_path / ".neuralmind").mkdir()
        (tmp_path / ".neuralmind" / "index_ir.json").write_text("{}", encoding="utf-8")
        assert _freshness_line(str(tmp_path)).startswith("Index is unverified:")


@pytest.mark.usefixtures("builtin_available")
class TestIndexMatchesGraph:
    """A graph regenerated after the build (graphify update, a pull) is reported."""

    def _built(self, root: Path) -> Path:
        _write_files(root, ["a.py", "b.py"])
        assert _mind(root).build()["success"]
        return root / ".neuralmind" / "graph.json"

    def test_graph_changed_after_build_fails_with_build_as_the_fix(self, tmp_path):
        graph_path = self._built(tmp_path)
        assert graph_freshness(tmp_path, check_index=True).status == OK

        graph = json.loads(graph_path.read_text(encoding="utf-8"))
        graph["nodes"].append({"id": "extra", "label": "extra", "source_file": "a.py"})
        graph_path.write_text(json.dumps(graph), encoding="utf-8")
        _bump_mtime(graph_path)

        report = graph_freshness(tmp_path, check_index=True)
        assert report.index_mismatch == "the graph changed after the last build"
        assert report.status == FAIL
        assert report.fix_command(".") == "neuralmind build ."
        assert "graph changed since the last build" in report.one_line()
        # Build-time checks don't ask: the build is about to re-embed.
        assert graph_freshness(tmp_path).index_mismatch == ""

    def test_read_path_reports_the_mismatch_once_and_still_answers(self, tmp_path):
        graph_path = self._built(tmp_path)
        graph = json.loads(graph_path.read_text(encoding="utf-8"))
        graph["nodes"].append({"id": "extra", "label": "extra", "source_file": "a.py"})
        graph_path.write_text(json.dumps(graph), encoding="utf-8")
        _bump_mtime(graph_path)

        mind = _mind(tmp_path)
        mind.query("what does a_fn do")
        assert "Index out of step: the graph changed after the last build" in (
            mind.notice_stream.getvalue()
        )

        assert _mind(tmp_path).build()["success"]
        rebuilt = _mind(tmp_path)
        rebuilt.query("what does a_fn do")
        assert rebuilt.notice_stream.getvalue() == ""

    def test_same_bytes_with_a_new_mtime_is_not_a_mismatch(self, tmp_path):
        graph_path = self._built(tmp_path)
        graph_path.write_bytes(graph_path.read_bytes())  # a fresh clone or checkout
        _bump_mtime(graph_path)
        assert graph_freshness(tmp_path, check_index=True).index_mismatch == ""


@pytest.mark.usefixtures("builtin_available")
class TestSchemaFilesInFreshness:
    """SQL, Protobuf and OpenAPI files are indexed, so their drift counts too."""

    def test_schema_edits_and_additions_are_reported(self, tmp_path):
        _write_files(tmp_path, ["a.py"])
        (tmp_path / "db").mkdir()
        sql = tmp_path / "db" / "schema.sql"
        sql.write_text("CREATE TABLE orders (id INT);\n", encoding="utf-8")
        spec = tmp_path / "api.yaml"
        spec.write_text(
            json.dumps({"openapi": "3.0.0", "info": {"title": "t"}, "paths": {"/a": {}}}),
            encoding="utf-8",
        )
        (tmp_path / "ci.yml").write_text("on: push\n", encoding="utf-8")  # not a spec
        assert _mind(tmp_path).build()["success"]

        fresh = graph_freshness(tmp_path)
        assert fresh.status == OK  # ci.yml isn't a node, so it isn't "missing"

        sql.write_text("CREATE TABLE orders (id INT, total INT);\n", encoding="utf-8")
        spec.write_text(
            json.dumps({"openapi": "3.0.0", "info": {"title": "t"}, "paths": {"/b": {}}}),
            encoding="utf-8",
        )
        for path in (sql, spec):
            _bump_mtime(path, 60)
        (tmp_path / "db" / "events.proto").write_text(
            'syntax = "proto3";\nmessage Event { string id = 1; }\n', encoding="utf-8"
        )

        report = graph_freshness(tmp_path)
        assert report.changed_since_graph == ["api.yaml", "db/schema.sql"]
        assert report.missing_from_graph == ["db/events.proto"]
        assert "ci.yml" not in report.missing_from_graph


# --------------------------------------------------------------------------- #
# Spec 2 — graph source
# --------------------------------------------------------------------------- #
@pytest.fixture
def builtin_available():
    from neuralmind import graphgen

    if not graphgen.is_available():
        pytest.skip("tree-sitter not installed")


class TestGraphSourceConfig:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("auto", "auto"),
            ("builtin", "builtin"),
            ("built-in", "builtin"),
            ("graphify", "graphify"),
            ("nonsense", "auto"),
        ],
    )
    def test_parsing(self, tmp_path, raw, expected):
        from neuralmind.neuralmind_config import NeuralmindConfig

        _set_graph_source(tmp_path, raw)
        assert NeuralmindConfig.load(tmp_path).graph_source == expected

    def test_graph_json_path_honours_setting(self, tmp_path):
        from neuralmind.paths import graph_json_path

        _write_graphify(tmp_path, _graphify_graph(["a.py"]))
        assert graph_json_path(tmp_path).parts[-2] == "graphify-out"  # auto falls back
        _set_graph_source(tmp_path, "builtin")
        assert graph_json_path(tmp_path).parts[-2] == ".neuralmind"
        _set_graph_source(tmp_path, "graphify")
        (tmp_path / ".neuralmind").mkdir()
        (tmp_path / ".neuralmind" / "graph.json").write_text("{}", encoding="utf-8")
        assert graph_json_path(tmp_path).parts[-2] == "graphify-out"


@pytest.mark.usefixtures("builtin_available")
class TestGraphSourceBuild:
    def _stale_graphify_repo(self, root: Path) -> list[str]:
        known = [f"pkg/mod_{i}.py" for i in range(4)]
        new = ["pkg/new_a.py", "pkg/new_b.py"]
        _write_files(root, known + new)
        _write_graphify(root, _graphify_graph(known, windows=True))
        return new

    def test_regenerate_graph_then_incremental(self, tmp_path):
        self._stale_graphify_repo(tmp_path)
        legacy = tmp_path / "graphify-out" / "graph.json"
        before = legacy.read_bytes()

        mind = _mind(tmp_path)
        result = mind.build(regenerate_graph=True)
        assert result["success"]
        assert result["graph"]["kind"] == "built-in"
        assert result["graph"]["action"] == "regenerated"
        assert result["graph"]["path"] == ".neuralmind/graph.json"
        notices = "\n".join(result["notices"])
        assert "Graph source: built-in (tree-sitter)" in notices
        assert "Ignoring graphify-out/graph.json (graphify" in notices
        assert legacy.read_bytes() == before  # graphify-out is never written
        assert graph_freshness(tmp_path).status == OK

        again = _mind(tmp_path).build()
        assert again["graph"]["kind"] == "built-in"
        assert again["graph"]["action"] == "incremental"

    def test_auto_switches_past_a_failing_graphify_graph(self, tmp_path):
        self._stale_graphify_repo(tmp_path)
        before = (tmp_path / "graphify-out" / "graph.json").read_bytes()

        result = _mind(tmp_path).build()

        assert result["success"]
        assert result["graph"]["kind"] == "built-in"
        assert result["graph"]["replaced"]["status"] == FAIL
        notices = "\n".join(result["notices"])
        assert "failed the freshness check" in notices
        assert "set graph_source: graphify" in notices
        assert (tmp_path / "graphify-out" / "graph.json").read_bytes() == before

    def test_auto_keeps_a_current_graphify_graph(self, tmp_path):
        rels = ["a.py", "b.py"]
        _write_files(tmp_path, rels)
        _write_graphify(tmp_path, _graphify_graph(rels))

        result = _mind(tmp_path).build()

        assert result["success"]
        assert result["graph"] == {
            "path": "graphify-out/graph.json",
            "kind": "graphify",
            "action": "read-only",
            "nodes": 2,
        }
        assert not (tmp_path / ".neuralmind" / "graph.json").exists()
        assert (
            result["notices"][0] == "Graph: graphify-out/graph.json (graphify, read-only, 2 nodes)"
        )

    def test_builtin_setting_never_reads_graphify_out(self, tmp_path, monkeypatch):
        self._stale_graphify_repo(tmp_path)
        _set_graph_source(tmp_path, "builtin")
        legacy_dir = str(tmp_path / "graphify-out")
        opened: list[str] = []

        real_open = builtins.open
        real_path_open = pathlib.Path.open

        def guard(path) -> None:
            if str(path).startswith(legacy_dir):
                opened.append(str(path))

        def spy_open(file, *a, **k):
            if isinstance(file, (str, os.PathLike)):
                guard(os.fspath(file))
            return real_open(file, *a, **k)

        def spy_path_open(self, *a, **k):
            guard(self)
            return real_path_open(self, *a, **k)

        monkeypatch.setattr(builtins, "open", spy_open)
        monkeypatch.setattr(pathlib.Path, "open", spy_path_open)

        result = _mind(tmp_path).build()
        from neuralmind import doctor

        doctor._check_graph(tmp_path)
        graph_freshness(tmp_path)

        assert result["success"]
        assert result["graph"]["kind"] == "built-in"
        assert opened == []

    def test_graphify_setting_requires_the_graph(self, tmp_path):
        _write_files(tmp_path, ["a.py"])
        _set_graph_source(tmp_path, "graphify")

        result = _mind(tmp_path).build()

        assert not result["success"]
        assert "graph_source: graphify" in result["error"]
        assert not (tmp_path / ".neuralmind" / "graph.json").exists()

    def test_build_stops_when_every_indexable_file_is_gone(self, tmp_path):
        _write_files(tmp_path, ["a.py"])
        assert _mind(tmp_path).build()["success"]
        (tmp_path / "a.py").unlink()

        result = _mind(tmp_path).build()
        assert result["success"] is False
        assert "no indexable files left" in result["error"]

    def test_no_silent_fallback_after_canonical_graph_is_deleted(self, tmp_path):
        rels = ["a.py", "b.py"]
        _write_files(tmp_path, rels)
        assert _mind(tmp_path).build()["graph"]["kind"] == "built-in"
        # A current graphify graph appears later; then the built-in one is deleted.
        _write_graphify(tmp_path, _graphify_graph(rels))
        (tmp_path / ".neuralmind" / "graph.json").unlink()

        result = _mind(tmp_path).build()

        assert not result["success"]
        assert "--regenerate-graph" in result["error"]
        assert "graph_source: graphify" in result["error"]

        _set_graph_source(tmp_path, "graphify")
        ok = _mind(tmp_path).build()
        assert ok["success"]
        assert ok["graph"]["kind"] == "graphify"
        # The index really is the graphify graph now, not the IR left by the
        # built-in one (which named its nodes differently).
        mind = _mind(tmp_path)
        mind.ensure_ready()
        assert {n["id"] for n in mind.embedder.nodes} == {
            n["id"] for n in _graphify_graph(rels)["nodes"]
        }
        # A deliberate source switch orphans most of the store, so the safety
        # valve keeps the built-in vectors until --prune confirms it.
        assert ok["orphans_kept"] == ok["nodes_total"] - 2
        assert any("--prune" in n for n in ok["notices"])
        pruned = _mind(tmp_path).build(prune=True)
        assert pruned["nodes_total"] == 2

    def test_strict_exits_3_before_embedding(self, tmp_path):
        self._stale_graphify_repo(tmp_path)
        _set_graph_source(tmp_path, "graphify")

        mind = _mind(tmp_path)
        result = mind.build(strict=True)

        assert not result["success"]
        assert result["exit_code"] == 3
        assert result["freshness"]["status"] == FAIL
        assert mind.embedder.get_stats()["total_nodes"] == 0

    def test_non_strict_build_prints_the_report_and_continues(self, tmp_path):
        self._stale_graphify_repo(tmp_path)
        _set_graph_source(tmp_path, "graphify")

        result = _mind(tmp_path).build()

        assert result["success"]
        assert result["freshness"]["status"] == FAIL
        assert any("[FAIL] Code graph:" in n for n in result["notices"])


class TestBuildCli:
    def test_strict_exit_code_and_graph_line(self, tmp_path, capsys, monkeypatch):
        from neuralmind import cli

        known = ["a.py", "b.py"]
        _write_files(tmp_path, known + ["c.py", "d.py"])
        _write_graphify(tmp_path, _graphify_graph(known, windows=True))
        _set_graph_source(tmp_path, "graphify")

        real = cli.NeuralMind

        def factory(*a, **k):
            mind = real(*a, **k)
            mind.embedder._embed_fn = _fake_embed
            return mind

        monkeypatch.setattr(cli, "NeuralMind", factory)
        args = SimpleNamespace(
            project_path=str(tmp_path),
            force=False,
            rebuild_index=False,
            dry_run=False,
            strict=True,
            regenerate_graph=False,
            prune=False,
            json=False,
            scope="all",
            content_type="code",
            redact_secrets=False,
            bootstrap=None,
        )
        with pytest.raises(SystemExit) as exc:
            cli.cmd_build(args)
        out = capsys.readouterr().out
        assert exc.value.code == 3
        assert "Graph: graphify-out/graph.json (graphify, read-only, 2 nodes)" in out
        assert "[FAIL] Code graph:" in out


# --------------------------------------------------------------------------- #
# Spec 3 — orphaned vectors
# --------------------------------------------------------------------------- #
def _nodes(ids: list[str]) -> dict:
    return {
        "nodes": [
            {
                "id": i,
                "label": f"sym_{i}",
                "file_type": "code",
                "source_file": f"f/{i}.py",
                "community": 0,
            }
            for i in ids
        ],
        "links": [],
    }


def test_book_build_forwards_graph_flags_and_strict_stops_it(tmp_path, monkeypatch):
    from neuralmind import cli

    seen: dict = {}

    def failing_code_build(args) -> None:
        seen.update(vars(args))
        raise SystemExit(3)  # the code graph FAILs under --strict

    monkeypatch.setattr(cli, "cmd_build", failing_code_build)
    args = SimpleNamespace(regenerate_graph=True, strict=True, prune=True, redact_secrets=False)
    with pytest.raises(SystemExit) as exc:
        cli._cmd_build_book(args, str(tmp_path), False)  # no graph yet: regenerate builds it
    assert exc.value.code == 3
    assert seen["scope"] == "code"
    assert (seen["regenerate_graph"], seen["strict"], seen["prune"]) == (True, True, True)


class TestOrphanPurge:
    def _graph(self, root: Path, ids: list[str]) -> None:
        _write_files(root, [f"f/{i}.py" for i in ids])
        _set_graph_source(root, "graphify")
        _write_graphify(root, _nodes(ids))

    def test_swap_graph_removes_orphans(self, tmp_path):
        a = [f"n{i}" for i in range(100)]
        self._graph(tmp_path, a)
        assert _mind(tmp_path).build()["nodes_total"] == 100

        b = a[:60] + [f"m{i}" for i in range(20)]  # 80 nodes, 60 shared
        for i in a[60:]:
            (tmp_path / "f" / f"{i}.py").unlink()
        self._graph(tmp_path, b)
        result = _mind(tmp_path).build()

        assert result["nodes_removed"] == 40
        assert result["nodes_total"] == 80
        mind = _mind(tmp_path)
        assert mind.embedder.load_graph()
        assert mind.embedder.orphaned_node_ids() == (set(), 80)

    def test_safety_valve_then_prune(self, tmp_path):
        a = [f"n{i}" for i in range(100)]
        self._graph(tmp_path, a)
        _mind(tmp_path).build()

        self._graph(tmp_path, a[:40])  # shrinks by 60%
        kept = _mind(tmp_path).build()
        assert kept["nodes_removed"] == 0
        assert kept["orphans_kept"] == 60
        assert kept["nodes_total"] == 100
        assert any("--prune" in n for n in kept["notices"])

        pruned = _mind(tmp_path).build(prune=True)
        assert pruned["nodes_removed"] == 60
        assert pruned["nodes_total"] == 40

    def test_ingested_content_is_never_purged(self, tmp_path):
        a = [f"n{i}" for i in range(10)]
        self._graph(tmp_path, a)
        mind = _mind(tmp_path)
        mind.build()
        mind.embedder.embed_content(
            [
                {
                    "id": "doc:runbook.0",
                    "label": "Runbook",
                    "content_text": "How to deploy.",
                    "metadata": {"source": "runbook.md"},
                }
            ]
        )

        result = _mind(tmp_path).build()
        assert result["nodes_removed"] == 0
        assert result["nodes_total"] == 11

    def test_doctor_fails_on_extra_vectors(self, tmp_path):
        from neuralmind import doctor

        a = [f"n{i}" for i in range(10)]
        self._graph(tmp_path, a)
        mind = _mind(tmp_path)
        mind.build()
        # Seed 10 stored vectors that aren't in the graph.
        mind.embedder.nodes = mind.embedder.nodes + _nodes([f"x{i}" for i in range(10)])["nodes"]
        mind.embedder.embed_nodes()
        mind.close()

        check = doctor._check_index(tmp_path)
        assert check.status == doctor.FAIL
        assert check.detail.startswith("10 vectors not in graph")
        assert "--prune" not in check.fix  # 10 of 20: a plain build purges them

    def test_doctor_says_prune_when_the_safety_valve_would_keep_orphans(self, tmp_path):
        from neuralmind import doctor

        a = [f"n{i}" for i in range(100)]
        self._graph(tmp_path, a)
        _mind(tmp_path).build()
        self._graph(tmp_path, a[:40])  # shrinks by 60%: the build keeps them
        assert _mind(tmp_path).build()["orphans_kept"] == 60

        check = doctor._check_index(tmp_path)
        assert check.status == doctor.FAIL
        assert check.fix.endswith("--prune")

    def test_doctor_compares_a_scoped_store_with_its_scope(self, tmp_path):
        from neuralmind import doctor

        self._graph(tmp_path, [f"n{i}" for i in range(10)])
        assert _mind(tmp_path, scope="code").build()["success"]

        check = doctor._check_index(tmp_path)
        assert check.status == doctor.OK, check.detail

    def test_doctor_ok_when_store_matches_graph(self, tmp_path):
        from neuralmind import doctor

        self._graph(tmp_path, [f"n{i}" for i in range(5)])
        _mind(tmp_path).build()
        assert doctor._check_index(tmp_path).status == doctor.OK

    def test_search_never_returns_a_node_missing_from_the_graph(self, tmp_path):
        a = [f"n{i}" for i in range(60)]
        self._graph(tmp_path, a)
        _mind(tmp_path).build()
        b = a[:40] + [f"m{i}" for i in range(10)]
        self._graph(tmp_path, b)
        _mind(tmp_path).build()

        mind = _mind(tmp_path)
        mind.ensure_ready()
        current = set(b)
        rng = np.random.default_rng(0)
        vocab = [f"sym_{i}" for i in a + b] + ["code", "file", "community", "entity"]
        for _ in range(1000):
            q = " ".join(rng.choice(vocab, size=3))
            for hit in mind.embedder.search(q, n=5):
                assert hit["id"] in current


# --------------------------------------------------------------------------- #
# Spec 8 — read paths
# --------------------------------------------------------------------------- #
@pytest.mark.usefixtures("builtin_available")
class TestReadPaths:
    def test_query_on_a_built_index_runs_no_graphgen_and_no_output(
        self, tmp_path, monkeypatch, capfd
    ):
        from neuralmind import graphgen

        _write_files(tmp_path, ["a.py", "b.py"])
        assert _mind(tmp_path).build()["success"]
        capfd.readouterr()

        calls: list[str] = []
        monkeypatch.setattr(graphgen, "build_graph", lambda *a, **k: calls.append("x"))
        from neuralmind.core import NeuralMind

        mind = NeuralMind(str(tmp_path), backend_type="turbovec")
        mind.embedder._embed_fn = _fake_embed
        mind.query("what does a_fn do")
        mind.wakeup()

        out, err = capfd.readouterr()
        assert calls == []
        assert out == ""
        assert err == ""

    def test_first_query_on_an_unbuilt_project_still_builds(self, tmp_path, capfd):
        from neuralmind.core import NeuralMind

        _write_files(tmp_path, ["a.py"])
        mind = NeuralMind(str(tmp_path), backend_type="turbovec")
        mind.embedder._embed_fn = _fake_embed
        mind.query("a_fn")

        out, err = capfd.readouterr()
        assert mind._built
        assert out == ""  # notices go to stderr, never stdout
        assert "Graph: .neuralmind/graph.json" in err

    def test_load_path_matches_build_path(self, tmp_path):
        _write_files(tmp_path, ["a.py", "b.py", "c.py"])
        built = _mind(tmp_path, enable_synapses=False)
        built.build()
        loaded = _mind(tmp_path, enable_synapses=False)
        assert loaded.ensure_ready() == {"success": True, "loaded": True}
        q = "what does b_fn do"
        assert built.query(q).context == loaded.query(q).context


def test_embedding_progress_is_silent_when_not_a_tty(tmp_path, capfd, monkeypatch):
    from neuralmind.turbovec_backend import TurboVecEmbedder

    monkeypatch.delenv("NEURALMIND_NO_PROGRESS", raising=False)
    _write_graphify(tmp_path, _nodes([f"n{i}" for i in range(20)]))
    be = TurboVecEmbedder(str(tmp_path), db_path=str(tmp_path / "tv"), embed_fn=_fake_embed)
    be.embed_nodes()
    assert "Embedding" not in capfd.readouterr().err


def test_embedding_progress_shows_on_a_tty(tmp_path, capfd, monkeypatch):
    from neuralmind import turbovec_backend
    from neuralmind.turbovec_backend import TurboVecEmbedder

    monkeypatch.delenv("NEURALMIND_NO_PROGRESS", raising=False)
    monkeypatch.setattr(turbovec_backend, "stream_is_tty", lambda stream: True)
    _write_graphify(tmp_path, _nodes([f"n{i}" for i in range(20)]))
    be = TurboVecEmbedder(str(tmp_path), db_path=str(tmp_path / "tv"), embed_fn=_fake_embed)
    be.embed_nodes()
    out, err = capfd.readouterr()
    assert "Embedding" in err
    assert "Embedding" not in out


# The MCP server runs in a child process, so the fake embedder goes in by
# patching the backend's default before ``main()`` starts.
_MCP_BOOT = """
import hashlib
import neuralmind.turbovec_backend as tb

def fake(texts):
    out = []
    for t in texts:
        v = [0.0] * 384
        for tok in t.lower().split():
            v[int.from_bytes(hashlib.md5(tok.encode()).digest()[:4], "little") % 384] += 1.0
        out.append(v)
    return out

tb._default_embed_fn = lambda: fake
from neuralmind.mcp_server import main
main()
"""


@pytest.mark.integration
@pytest.mark.usefixtures("builtin_available")
def test_mcp_stdio_first_query_writes_only_jsonrpc_to_stdout(tmp_path):
    """The first query builds the index; none of that may reach the JSON-RPC stdout."""
    import queue
    import sys
    import threading

    pytest.importorskip("mcp")
    project = tmp_path / "proj"
    _write_files(project, ["a.py", "b.py"])
    env = {**os.environ, "NEURALMIND_ORT_THREADS": "1", "PYTHONUNBUFFERED": "1"}
    env.pop("NEURALMIND_NO_PROGRESS", None)
    proc = subprocess.Popen(
        [sys.executable, "-c", _MCP_BOOT],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        env=env,
    )
    lines: queue.Queue[str | None] = queue.Queue()
    seen: list[str] = []

    def read() -> None:
        for line in proc.stdout:
            lines.put(line)
        lines.put(None)

    threading.Thread(target=read, daemon=True).start()

    def send(message: dict) -> None:
        proc.stdin.write(json.dumps(message) + "\n")
        proc.stdin.flush()

    def recv(expect_id: int) -> dict:
        while True:
            line = lines.get(timeout=120)
            assert line is not None, f"server exited early: {proc.stderr.read()[-2000:]}"
            seen.append(line)
            if not line.strip():
                continue
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                pytest.fail(f"non-JSON line on the MCP stdout: {line!r}")
            if message.get("id") == expect_id:
                return message

    try:
        send(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "stdout-test", "version": "0"},
                },
            }
        )
        recv(1)
        send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        send(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "neuralmind_query",
                    "arguments": {"project_path": str(project), "question": "what does a_fn do"},
                },
            }
        )
        reply = recv(2)
    finally:
        proc.stdin.close()
        try:
            proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            proc.kill()
    while (line := lines.get(timeout=10)) is not None:
        seen.append(line)
    stderr = proc.stderr.read()

    payload = json.loads(reply["result"]["content"][0]["text"])
    assert "error" not in payload, payload
    assert (project / ".neuralmind" / "graph.json").exists()  # the query built it
    assert "Graph: .neuralmind/graph.json" in stderr  # build notices went to stderr
    for line in seen:
        if line.strip():
            assert json.loads(line).get("jsonrpc") == "2.0", line


def test_freshness_module_has_no_side_effects(tmp_path):
    _write_files(tmp_path, ["a.py"])
    _write_graphify(tmp_path, _graphify_graph(["a.py"]))
    before = sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*"))
    freshness.graph_freshness(tmp_path)
    after = sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*"))
    assert before == after


# --------------------------------------------------------------------------- #
# End to end: the trap found on a real repo
# --------------------------------------------------------------------------- #
@needs_git
@pytest.mark.usefixtures("builtin_available")
def test_stale_committed_graphify_graph_end_to_end(tmp_path, monkeypatch):
    """A committed Windows-path graphify graph, 3 modules added after it, and a
    gitignored copy dir (with force-added files): doctor FAILs; then
    ``build --regenerate-graph`` passes the graph and index checks."""
    from neuralmind import doctor
    from neuralmind.backend_manager import BackendManager

    original = ["app/orders.py", "app/billing.py", "lib/cache.py"]
    _write_files(tmp_path, original + ["examples/demo/render.py"])
    _write_graphify(tmp_path, _graphify_graph(original + ["examples/demo/render.py"], windows=True))
    (tmp_path / ".gitignore").write_text("projects/\n.neuralmind/\n", encoding="utf-8")
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-q", "-m", "graph built on windows")

    added = ["app/refunds.py", "app/invoices.py", "lib/retry.py"]
    _write_files(tmp_path, added)
    _write_files(tmp_path, ["projects/demo/render.py"])
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "add", "-f", "projects/demo/render.py")
    _git(tmp_path, "commit", "-q", "-m", "new modules")

    check = doctor._check_graph(tmp_path)
    assert check.status == doctor.FAIL
    for rel in added:
        assert rel in check.detail
    assert ("separators" in check.detail) is POSIX
    assert "1 commit behind HEAD" in check.detail

    # doctor's index check builds its own NeuralMind: give it the fake embedder.
    real_init = BackendManager.__init__

    def init(self, *a, **k):
        real_init(self, *a, **k)
        if hasattr(self.backend, "_embed_fn"):
            self.backend._embed_fn = _fake_embed

    monkeypatch.setattr(BackendManager, "__init__", init)

    result = _mind(tmp_path).build(regenerate_graph=True)
    assert result["success"]
    assert result["graph"]["kind"] == "built-in"

    assert doctor._check_graph(tmp_path).status == doctor.OK
    assert doctor._check_index(tmp_path).status == doctor.OK
