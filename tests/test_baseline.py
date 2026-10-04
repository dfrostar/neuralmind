"""The reduction baseline: the code the index covers, in the context's own units.

``neuralmind benchmark`` — and every per-query ratio — reports how many times
smaller NeuralMind's context is than the code it stands in for. Before v4.5.0
"the code" was a fixed 50,000-token estimate, so the ratio was the same
function of context size on every repository. These tests pin what replaced
it, including the two ways the first measured version still drifted from
"the repository's code": it counted prose (a changelog was 15% of
psf/requests' baseline), and it counted with a different tokenizer than the
context whenever tiktoken happened to be installed.
"""

from __future__ import annotations

import importlib.util
import json
import shlex
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest

from neuralmind import baseline
from neuralmind.context_selector import ContextResult, ContextSelector, TokenBudget
from neuralmind.paths import baseline_path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "docs" / "community-benchmarks.schema.json"
ENTRIES_PATH = REPO_ROOT / "docs" / "community-benchmarks.json"


def _write(root: Path, rel: str, text: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _node(rel: str, file_type: str = "code", node_id: str | None = None) -> dict:
    return {"id": node_id or rel, "source_file": rel, "file_type": file_type}


def _graph(*nodes: dict) -> dict:
    return {"nodes": list(nodes)}


def _measure(project: Path, *nodes: dict) -> tuple[int, int, str]:
    measured = baseline.measure_graph_files(project, _graph(*nodes))
    return measured["tokens"], measured["files"], measured["scope"]


class TestWhatTheBaselineCounts:
    def test_each_indexed_code_file_once_at_four_chars_per_token(self, tmp_path):
        _write(tmp_path, "a.py", "x" * 400)
        _write(tmp_path, "pkg/b.py", "y" * 802)
        nodes = [
            _node("a.py"),
            _node("a.py", node_id="a.py::f"),
            _node("a.py", node_id="a.py::g"),
            _node("pkg/b.py"),
            _node("pkg/b.py", "rationale", node_id="pkg/b.py::doc"),
        ]
        # The two files concatenated (1,202 chars), never a file per node.
        assert _measure(tmp_path, *nodes) == (300, 2, "code")

    def test_files_the_index_does_not_cover_are_not_counted(self, tmp_path):
        # Whatever kept a file out of the graph — .gitignore,
        # .neuralmindignore, the default ignores — keeps it out of the baseline.
        _write(tmp_path, "a.py", "x" * 400)
        _write(tmp_path, "vendored/huge.py", "x" * 40_000)
        assert _measure(tmp_path, _node("a.py")) == (100, 1, "code")

    def test_prose_is_left_out_when_the_index_holds_code(self, tmp_path):
        _write(tmp_path, "a.py", "x" * 400)
        _write(tmp_path, "HISTORY.md", "y" * 60_000)
        _write(tmp_path, "docs/guide.rst", "z" * 4_000)
        nodes = [
            _node("a.py"),
            _node("HISTORY.md", "document"),
            _node("docs/guide.rst", "document"),
        ]
        assert _measure(tmp_path, *nodes) == (100, 1, "code")

    def test_a_prose_only_index_is_measured_over_its_documents(self, tmp_path):
        _write(tmp_path, "chapters/01.md", "x" * 400)
        _write(tmp_path, "chapters/02.md", "y" * 400)
        nodes = [_node("chapters/01.md", "document"), _node("chapters/02.md", "document")]
        assert _measure(tmp_path, *nodes) == (200, 2, "documents")

    def test_a_schema_only_index_is_measured_over_its_schema_documents(self, tmp_path):
        # graphgen emits SQL, Protobuf and OpenAPI files as "document" nodes;
        # an index of nothing else still has readable text to measure.
        _write(tmp_path, "db/schema.sql", "x" * 400)
        _write(tmp_path, "api/svc.proto", "y" * 400)
        _write(tmp_path, "api/openapi.yaml", "z" * 400)
        nodes = [
            _node("db/schema.sql", "document"),
            _node("api/svc.proto", "document"),
            _node("api/openapi.yaml", "document"),
        ]
        assert _measure(tmp_path, *nodes) == (300, 3, "documents")

    def test_schema_documents_are_left_out_when_the_index_holds_code(self, tmp_path):
        _write(tmp_path, "a.py", "x" * 400)
        _write(tmp_path, "db/schema.sql", "y" * 40_000)
        nodes = [_node("a.py"), _node("db/schema.sql", "document")]
        assert _measure(tmp_path, *nodes) == (100, 1, "code")

    def test_code_is_recognised_by_file_type_or_by_suffix(self, tmp_path):
        # graphify marks code nodes "code" whatever the language; a producer
        # that doesn't (the conftest graph says "function") is still read as
        # code by a suffix the built-in parser handles.
        _write(tmp_path, "app.kt", "x" * 400)
        _write(tmp_path, "svc.py", "y" * 400)
        assert _measure(tmp_path, _node("app.kt"), _node("svc.py", "function")) == (200, 2, "code")

    def test_binary_files_a_graph_names_are_never_read(self, tmp_path):
        (tmp_path / "diagram.png").write_bytes(b"\x89PNG" + bytes(4_000))
        (tmp_path / "paper.pdf").write_bytes(b"%PDF" + bytes(4_000))
        nodes = [_node("diagram.png", "image"), _node("paper.pdf", "paper")]
        assert _measure(tmp_path, *nodes) == (0, 0, "none")


class TestPathsTheGraphNames:
    def test_paths_outside_the_project_are_never_opened(self, tmp_path):
        # A repository can commit its graph, so it controls these paths.
        project = tmp_path / "project"
        _write(project, "a.py", "x" * 400)
        secret = _write(tmp_path, "secret.py", "s" * 40_000)
        nodes = [_node("a.py"), _node("../secret.py"), _node(str(secret))]
        assert _measure(project, *nodes) == (100, 1, "code")

    def test_a_symlink_out_of_the_project_is_not_followed(self, tmp_path):
        project = tmp_path / "project"
        _write(project, "a.py", "x" * 400)
        secret = _write(tmp_path, "secret.py", "s" * 40_000)
        try:
            (project / "link.py").symlink_to(secret)
        except (OSError, NotImplementedError):
            pytest.skip("symlinks unavailable on this host")
        assert _measure(project, _node("a.py"), _node("link.py")) == (100, 1, "code")

    def test_one_file_spelled_four_ways_counts_once(self, tmp_path):
        _write(tmp_path, "pkg/a.py", "x" * 400)
        spellings = ["pkg/a.py", "./pkg/a.py", "pkg\\a.py", str(tmp_path / "pkg" / "a.py")]
        assert _measure(tmp_path, *(_node(s) for s in spellings)) == (100, 1, "code")

    def test_a_file_gone_since_the_build_is_skipped(self, tmp_path):
        _write(tmp_path, "a.py", "x" * 400)
        assert _measure(tmp_path, _node("a.py"), _node("deleted.py")) == (100, 1, "code")


class TestSameUnitsAsTheContext:
    def test_it_is_the_selectors_own_estimate(self, tmp_path):
        text = "def handler(request):\n    return request.user\n" * 40
        _write(tmp_path, "a.py", text)
        expected = len(text) // ContextSelector.CHARS_PER_TOKEN
        assert baseline.count_file_tokens([tmp_path / "a.py"]) == expected

    def test_an_installed_tokenizer_does_not_move_it(self, tmp_path, monkeypatch):
        # The context is counted at ~4 chars/token whatever is installed, so
        # the baseline must be too — otherwise one index reports two ratios.
        _write(tmp_path, "a.py", "def f():\n    return 1\n" * 50)
        plain = _measure(tmp_path, _node("a.py"))

        class _Encoding:
            def encode(self, text):
                return [0] * (len(text) // 2)

        fake = types.ModuleType("tiktoken")
        fake.get_encoding = lambda name: _Encoding()
        monkeypatch.setitem(sys.modules, "tiktoken", fake)
        assert _measure(tmp_path, _node("a.py")) == plain

    def test_line_endings_do_not_change_it(self, tmp_path):
        (tmp_path / "lf").mkdir()
        (tmp_path / "crlf").mkdir()
        (tmp_path / "lf" / "a.py").write_bytes(b"a = 1\nb = 2\n" * 100)
        (tmp_path / "crlf" / "a.py").write_bytes(b"a = 1\r\nb = 2\r\n" * 100)
        lf = _measure(tmp_path / "lf", _node("a.py"))
        assert lf == _measure(tmp_path / "crlf", _node("a.py"))
        assert lf[0] > 0

    def test_undecodable_bytes_are_counted_not_fatal(self, tmp_path):
        (tmp_path / "a.py").write_bytes(b"x = '\xff\xfe'\n" * 100)
        assert _measure(tmp_path, _node("a.py"))[0] > 0


class TestTheBuildCache:
    def test_a_measurement_round_trips(self, tmp_path):
        (tmp_path / ".neuralmind").mkdir()
        _write(tmp_path, "a.py", "x" * 400)
        baseline.save(tmp_path, baseline.measure_graph_files(tmp_path, _graph(_node("a.py"))))
        resolved = baseline.resolve(tmp_path)
        assert (resolved["source"], resolved["tokens"], resolved["scope"]) == (
            "measured",
            100,
            "code",
        )
        assert resolved["label"] == "measured: 100 tokens in 1 indexed code files"

    def test_a_cache_from_before_the_code_only_count_is_ignored(self, tmp_path):
        (tmp_path / ".neuralmind").mkdir()
        baseline_path(tmp_path).write_text(json.dumps({"tokens": 110_058, "files": 41}), "utf-8")
        assert baseline.load(tmp_path) is None
        assert baseline.resolve(tmp_path)["source"] == "naive-50k"


# --------------------------------------------------------------------------- #
# benchmark — the ratio itself
# --------------------------------------------------------------------------- #
def _result(tokens: int) -> ContextResult:
    return ContextResult(context="", budget=TokenBudget(l3_search=tokens))


def _mind(project: Path, graph: dict, query_tokens: list[int], wakeup_tokens: int = 500):
    from neuralmind.core import NeuralMind

    mind = NeuralMind.__new__(NeuralMind)  # bypass the heavy __init__
    mind.project_path = project
    mind.embedder = SimpleNamespace(graph=graph, nodes=graph["nodes"])
    mind._ensure_built = lambda: None
    costs = iter(query_tokens)
    mind.wakeup = lambda: _result(wakeup_tokens)
    mind.query = lambda question, learn=None: _result(next(costs))
    return mind


def _questions(n: int) -> list[str]:
    return [f"question {i}" for i in range(n)]


class TestBenchmarkRatio:
    def test_is_the_measured_code_over_each_questions_tokens(self, tmp_path):
        _write(tmp_path, "a.py", "x" * 40_000)  # 10,000 tokens
        result = _mind(tmp_path, _graph(_node("a.py")), [500, 2_000]).benchmark(_questions(2))
        assert result["baseline"]["source"] == "measured"
        assert result["full_codebase_tokens"] == 10_000
        # wakeup (500 tokens), then the two questions
        assert [r["reduction"] for r in result["results"]] == [20.0, 20.0, 5.0]
        assert result["avg_reduction_ratio"] == 12.5

    def test_scales_with_the_size_of_the_repo(self, tmp_path):
        """The defect this replaced: the same context on two repos 100× apart gave one ratio."""
        reports = {}
        for name, chars in (("small", 8_000), ("large", 800_000)):
            project = tmp_path / name
            _write(project, "a.py", "x" * chars)
            graph = _graph(_node("a.py"))
            reports[name] = _mind(project, graph, [1_000, 1_000]).benchmark(_questions(2))
        assert reports["small"]["full_codebase_tokens"] == 2_000
        assert reports["large"]["full_codebase_tokens"] == 200_000
        assert reports["small"]["avg_reduction_ratio"] == 2.0
        assert reports["large"]["avg_reduction_ratio"] == 200.0
        # The fixed estimate can't tell them apart, which is why it's legacy.
        assert reports["small"]["legacy_avg_reduction_ratio"] == 50.0
        assert reports["large"]["legacy_avg_reduction_ratio"] == 50.0
        assert reports["large"]["estimated_full_codebase_tokens"] == 50_000

    def test_a_changelog_does_not_move_it(self, tmp_path):
        _write(tmp_path, "a.py", "x" * 40_000)
        code_only = _mind(tmp_path, _graph(_node("a.py")), [1_000]).benchmark(_questions(1))
        _write(tmp_path, "CHANGELOG.md", "y" * 400_000)
        graph = _graph(_node("a.py"), _node("CHANGELOG.md", "document"))
        with_docs = _mind(tmp_path, graph, [1_000]).benchmark(_questions(1))
        assert with_docs["avg_reduction_ratio"] == code_only["avg_reduction_ratio"] == 10.0

    def test_uses_the_build_cache_every_per_query_ratio_divides(self, tmp_path):
        # Files edited since the build aren't what the index answers from.
        (tmp_path / ".neuralmind").mkdir()
        _write(tmp_path, "a.py", "x" * 40_000)
        graph = _graph(_node("a.py"))
        baseline.save(tmp_path, baseline.measure_graph_files(tmp_path, graph))
        _write(tmp_path, "a.py", "x" * 4_000)
        assert (
            _mind(tmp_path, graph, [1_000]).benchmark(_questions(1))["full_codebase_tokens"]
            == 10_000
        )

    def test_an_index_built_before_the_baseline_is_measured_without_writing(self, tmp_path):
        (tmp_path / ".neuralmind").mkdir()
        _write(tmp_path, "a.py", "x" * 40_000)
        result = _mind(tmp_path, _graph(_node("a.py")), [1_000]).benchmark(_questions(1))
        assert (result["baseline"]["source"], result["full_codebase_tokens"]) == (
            "measured",
            10_000,
        )
        assert not baseline_path(tmp_path).exists()

    def test_naive_50k_reproduces_the_fixed_estimate(self, tmp_path):
        _write(tmp_path, "a.py", "x" * 40_000)
        result = _mind(tmp_path, _graph(_node("a.py")), [1_000]).benchmark(
            _questions(1), naive_50k=True
        )
        assert result["baseline"]["source"] == "naive-50k"
        assert result["full_codebase_tokens"] == 50_000
        assert result["avg_reduction_ratio"] == result["legacy_avg_reduction_ratio"] == 50.0

    def test_falls_back_to_the_estimate_only_when_nothing_is_readable(self, tmp_path):
        result = _mind(tmp_path, _graph(_node("gone.py")), [1_000]).benchmark(_questions(1))
        assert result["baseline"]["source"] == "naive-50k"
        assert result["full_codebase_tokens"] == 50_000
        assert "run neuralmind build" in result["baseline"]["label"]


# --------------------------------------------------------------------------- #
# --contribute — the community table keeps one comparable ratio
# --------------------------------------------------------------------------- #
def _submit(project: Path, result: dict, capsys) -> tuple[dict, str]:
    from neuralmind import cli

    args = SimpleNamespace(
        project_path=str(project),
        project_name="demo",
        language="Python",
        model="Local / other",
        repo_url="https://example.org/demo",
        notes=None,
        submitter="octocat",
    )
    # The shape NeuralMind.get_stats() returns — "nodes", which --contribute
    # used to miss by reading "total_nodes", so no real entry validated.
    mind = SimpleNamespace(get_stats=lambda: {"built": True, "nodes": 42})
    cli._emit_community_submission(args, result, mind)
    out = capsys.readouterr().out
    return json.loads(out.split("-" * 68)[1]), out


def _validator():
    jsonschema = pytest.importorskip("jsonschema")
    return jsonschema.Draft7Validator(json.loads(SCHEMA_PATH.read_text(encoding="utf-8")))


class TestContributePayload:
    def test_v2_keeps_the_table_ratio_and_adds_the_measured_one(self, tmp_path, capsys):
        _write(tmp_path, "a.py", "x" * 40_000)
        result = _mind(tmp_path, _graph(_node("a.py")), [1_000, 1_250]).benchmark(_questions(2))
        entry, out = _submit(tmp_path, result, capsys)
        assert entry["schema_version"] == 2
        assert entry["nodes"] == 42
        assert entry["avg_reduction_ratio"] == result["legacy_avg_reduction_ratio"] == 45.0
        assert entry["measured_avg_reduction_ratio"] == result["avg_reduction_ratio"] == 9.0
        assert entry["full_codebase_tokens"] == 10_000
        assert entry["avg_query_tokens"] == 1_125  # whole tokens, as the schema requires
        # The command a reviewer re-runs must reproduce avg_reduction_ratio.
        assert "--naive-50k" in entry["verification_command"]
        assert "Table ratio" in out
        assert not list(_validator().iter_errors(entry))

    def test_a_run_without_a_measurement_submits_the_table_ratio_only(self, tmp_path, capsys):
        _write(tmp_path, "a.py", "x" * 40_000)
        result = _mind(tmp_path, _graph(_node("a.py")), [1_000]).benchmark(
            _questions(1), naive_50k=True
        )
        entry, out = _submit(tmp_path, result, capsys)
        assert entry["avg_reduction_ratio"] == 50.0
        assert "measured_avg_reduction_ratio" not in entry
        assert "full_codebase_tokens" not in entry
        assert "not your code" in out
        assert not list(_validator().iter_errors(entry))

    def test_verification_command_survives_a_path_a_shell_would_split(self, tmp_path, capsys):
        project = tmp_path / "my repo; echo pwned"
        project.mkdir()
        _write(project, "a.py", "x" * 40_000)
        result = _mind(project, _graph(_node("a.py")), [1_000]).benchmark(_questions(1))
        entry, _ = _submit(project, result, capsys)
        argv = shlex.split(entry["verification_command"])
        assert argv == ["neuralmind", "benchmark", str(project), "--naive-50k", "--json"]

    def test_a_measured_ratio_cannot_travel_without_its_baseline(self):
        entry = json.loads(ENTRIES_PATH.read_text(encoding="utf-8"))["entries"][0]
        assert list(_validator().iter_errors({**entry, "measured_avg_reduction_ratio": 9.0}))

    def test_published_entries_still_validate(self):
        validator = _validator()
        for entry in json.loads(ENTRIES_PATH.read_text(encoding="utf-8"))["entries"]:
            assert not list(validator.iter_errors(entry)), entry["project_name"]


def test_readme_table_names_the_baseline_of_each_ratio():
    spec = importlib.util.spec_from_file_location(
        "render_community_table", REPO_ROOT / "scripts" / "render_community_table.py"
    )
    render = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(render)
    v1 = {
        "project_name": "old",
        "language": "Python",
        "nodes": 10,
        "avg_reduction_ratio": 46.0,
        "date_submitted": "2025-10-01",
        "submitted_by": "octocat",
    }
    v2 = {**v1, "project_name": "new", "measured_avg_reduction_ratio": 78.6}
    v2["full_codebase_tokens"] = 94_069
    table = render.render_table([v1, v2])
    assert "Reduction (vs fixed 50K)" in table and "Reduction (vs measured code)" in table
    rows = {line.split(" | ")[0]: line for line in table.splitlines() if line.startswith("| ")}
    assert "78.6× of 94,069 tok" in rows["| new"]
    assert "| **46.0×** | — |" in rows["| old"]
