"""v4.5.0 measurement: what gets indexed, and numbers that can be trusted.

Spec 4 — the index covers what git covers (.gitignore honoured)
Spec 5 — read-only queries never train on their own test
Spec 6 — project eval with gold answers, stable probe sampling, one baseline
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import pytest

from tests.test_index_freshness import _fake_embed, _git, _mind, _write_files, needs_git

pytest.importorskip("turbovec")


@pytest.fixture
def builtin_available():
    from neuralmind import graphgen

    if not graphgen.is_available():
        pytest.skip("tree-sitter not installed")


def _indexed(root: Path) -> list[str]:
    from neuralmind import graphgen

    files = graphgen._iter_files(
        root, graphgen._DEFAULT_IGNORES, graphgen.SUPPORTED_SUFFIXES | graphgen._DOC_SUFFIXES
    )
    return [f.relative_to(root).as_posix() for f in files]


def _git_repo(root: Path) -> None:
    _git(root, "init", "-q")


# --------------------------------------------------------------------------- #
# Spec 4 — .gitignore
# --------------------------------------------------------------------------- #
@needs_git
class TestGitignoreInGitRepo:
    def test_ignored_dir_with_negation(self, tmp_path):
        _write_files(tmp_path, ["src/app.py", "projects/copy.py", "projects/keep.py"])
        # git can't re-include a file under an excluded *directory*
        # (`projects/`), so the negation needs `projects/*` — exactly as in git.
        (tmp_path / ".gitignore").write_text("projects/*\n!projects/keep.py\n", "utf-8")
        _git_repo(tmp_path)

        assert _indexed(tmp_path) == ["projects/keep.py", "src/app.py"]

    def test_untracked_not_ignored_file_is_indexed(self, tmp_path):
        _write_files(tmp_path, ["src/app.py"])
        _git_repo(tmp_path)
        _git(tmp_path, "add", "-A")
        _git(tmp_path, "commit", "-qm", "init")
        _write_files(tmp_path, ["src/new_module.py"])  # never added

        assert "src/new_module.py" in _indexed(tmp_path)

    def test_tracked_file_matching_an_ignore_rule_is_excluded(self, tmp_path):
        _write_files(tmp_path, ["src/app.py", "projects/copy.py"])
        (tmp_path / ".gitignore").write_text("projects/\n", "utf-8")
        _git_repo(tmp_path)
        _git(tmp_path, "add", "-A")
        _git(tmp_path, "add", "-f", "projects/copy.py")  # force-added despite the rule
        _git(tmp_path, "commit", "-qm", "init")

        assert _indexed(tmp_path) == ["src/app.py"]

    def test_include_ignored_pulls_paths_back(self, tmp_path):
        _write_files(tmp_path, ["src/app.py", "generated/api/client.py", "generated/junk.py"])
        (tmp_path / ".gitignore").write_text("generated/\n", "utf-8")
        (tmp_path / ".neuralmind.yaml").write_text(
            'include_ignored:\n  - "generated/api/**"\n', "utf-8"
        )
        _git_repo(tmp_path)

        assert _indexed(tmp_path) == ["generated/api/client.py", "src/app.py"]

    def test_respect_gitignore_false_restores_the_plain_walk(self, tmp_path):
        from neuralmind import graphgen

        _write_files(tmp_path, ["src/app.py", "projects/copy.py"])
        (tmp_path / ".gitignore").write_text("projects/\n", "utf-8")
        (tmp_path / ".neuralmind.yaml").write_text("respect_gitignore: false\n", "utf-8")
        _git_repo(tmp_path)

        suffixes = graphgen.SUPPORTED_SUFFIXES | graphgen._DOC_SUFFIXES
        plain = graphgen._walk_files(tmp_path, graphgen._DEFAULT_IGNORES, suffixes, ())
        assert _indexed(tmp_path) == [f.relative_to(tmp_path).as_posix() for f in plain]
        assert "projects/copy.py" in _indexed(tmp_path)

    def test_nested_gitignore_is_honoured(self, tmp_path):
        _write_files(tmp_path, ["pkg/a.py", "pkg/build_out/gen.py"])
        (tmp_path / "pkg" / ".gitignore").write_text("build_out/\n", "utf-8")
        _git_repo(tmp_path)

        assert _indexed(tmp_path) == ["pkg/a.py"]

    def test_project_in_a_dir_the_enclosing_repo_ignores(self, tmp_path):
        # A scratch dir or vendored checkout the outer repo ignores: git lists
        # nothing under it, so the project's own .gitignore decides instead.
        from neuralmind import ignore

        _write_files(tmp_path, ["outer.py", "scratch/app/a.py", "scratch/app/skip.py"])
        (tmp_path / ".gitignore").write_text("scratch/\n", "utf-8")
        (tmp_path / "scratch" / "app" / ".gitignore").write_text("skip.py\n", "utf-8")
        _git_repo(tmp_path)
        project = tmp_path / "scratch" / "app"

        assert ignore.git_visible_files(project) is None
        assert _indexed(project) == ["a.py"]

    def test_walk_order_matches_the_directory_walk(self, tmp_path):
        from neuralmind import graphgen

        _write_files(tmp_path, ["a.py", "a/b.py", "b/c.py", "ab.py"])
        _git_repo(tmp_path)
        suffixes = graphgen.SUPPORTED_SUFFIXES
        plain = graphgen._walk_files(tmp_path, graphgen._DEFAULT_IGNORES, suffixes, ())
        assert graphgen._iter_files(tmp_path, graphgen._DEFAULT_IGNORES, suffixes) == plain

    def test_listing_is_no_slower_than_the_walk(self, tmp_path):
        from neuralmind import graphgen

        _write_files(tmp_path, [f"pkg{i // 100}/m{i}.py" for i in range(2000)])
        _git_repo(tmp_path)
        suffixes = graphgen.SUPPORTED_SUFFIXES
        graphgen._iter_files(tmp_path, graphgen._DEFAULT_IGNORES, suffixes)  # warm

        start = time.perf_counter()
        graphgen._walk_files(tmp_path, graphgen._DEFAULT_IGNORES, suffixes, ())
        walk = time.perf_counter() - start
        start = time.perf_counter()
        files = graphgen._iter_files(tmp_path, graphgen._DEFAULT_IGNORES, suffixes)
        listing = time.perf_counter() - start

        assert len(files) == 2000
        assert listing <= walk * 2 + 0.25, f"git listing {listing:.3f}s vs walk {walk:.3f}s"


class TestGitignoreOutsideGit:
    def test_top_level_gitignore_with_negation(self, tmp_path):
        _write_files(tmp_path, ["src/app.py", "projects/copy.py", "projects/keep.py", "x.log.py"])
        (tmp_path / ".gitignore").write_text("projects/*\n!projects/keep.py\n*.log.py\n", "utf-8")

        assert _indexed(tmp_path) == ["projects/keep.py", "src/app.py"]


class TestNeuralmindignore:
    @pytest.mark.parametrize(
        ("pattern", "path", "ignored"),
        [
            ("docs/", "docs/a.md", True),
            ("docs/", "pkg/docs/a.md", True),  # unanchored dir: any depth
            ("/docs/", "pkg/docs/a.md", False),  # anchored: root only
            ("/docs/", "docs/a.md", True),
            ("src/*.py", "src/deep/a.py", False),  # '*' doesn't cross '/'
            ("src/**/*.py", "src/deep/a.py", True),
        ],
    )
    def test_gitignore_semantics(self, pattern, path, ignored):
        from neuralmind.graphgen import _is_ignored

        assert _is_ignored(path, (pattern,)) is ignored

    def test_negation(self, tmp_path):
        _write_files(tmp_path, ["docs/a.py", "docs/keep.py", "src/b.py"])
        (tmp_path / ".neuralmindignore").write_text("docs/*\n!docs/keep.py\n", "utf-8")

        assert _indexed(tmp_path) == ["docs/keep.py", "src/b.py"]


@needs_git
@pytest.mark.usefixtures("builtin_available")
class TestGitignoreBuild:
    def _repo(self, root: Path) -> None:
        _write_files(root, ["src/app.py", "examples/demo.py", "projects/demo.py"])
        (root / ".gitignore").write_text("projects/\n.neuralmind/\n", "utf-8")
        _git_repo(root)
        _git(root, "add", "-A")
        _git(root, "add", "-f", "projects/demo.py")
        _git(root, "commit", "-qm", "init")

    def test_build_excludes_and_notices_once(self, tmp_path):
        self._repo(tmp_path)
        first = _mind(tmp_path).build()
        graph = json.loads((tmp_path / ".neuralmind" / "graph.json").read_text())
        files = {n.get("source_file") for n in graph["nodes"]}
        assert "projects/demo.py" not in files
        assert "examples/demo.py" in files
        notices = "\n".join(first["notices"])
        assert "Honoring .gitignore (new in v4.5.0): 1 file (projects/ 1)" in notices

        second = _mind(tmp_path).build()
        assert not any("Honoring .gitignore" in n for n in second["notices"])

    def test_newly_ignored_file_leaves_an_incremental_graph(self, tmp_path):
        _write_files(tmp_path, ["src/app.py", "vendor/lib.py"])
        _git_repo(tmp_path)
        _mind(tmp_path).build()
        graph = json.loads((tmp_path / ".neuralmind" / "graph.json").read_text())
        assert "vendor/lib.py" in {n.get("source_file") for n in graph["nodes"]}

        (tmp_path / ".gitignore").write_text("vendor/\n", "utf-8")
        result = _mind(tmp_path).build()

        graph = json.loads((tmp_path / ".neuralmind" / "graph.json").read_text())
        assert "vendor/lib.py" not in {n.get("source_file") for n in graph["nodes"]}
        assert result["nodes_removed"] > 0

    def test_dry_run_reports_exclusions(self, tmp_path, capsys):
        from neuralmind import cli

        self._repo(tmp_path)
        scan = cli._dry_run_scan(str(tmp_path))
        assert scan["excluded_by_gitignore"]["files"] == 1
        assert scan["excluded_by_gitignore"]["paths"] == ["projects/demo.py"]
        assert scan["total_files"] == 2


# --------------------------------------------------------------------------- #
# Spec 5 — read-only queries
# --------------------------------------------------------------------------- #
def _db_state(root: Path) -> dict:
    out = {}
    for suffix in ("", "-wal"):
        f = root / ".neuralmind" / f"synapses.db{suffix}"
        data = f.read_bytes() if f.exists() else b""
        out[suffix] = hashlib.sha256(data).hexdigest()
    return out


@pytest.fixture
def learned_project(tmp_path, builtin_available):
    _write_files(tmp_path, ["pkg/alpha.py", "pkg/beta.py", "pkg/gamma.py"])
    mind = _mind(tmp_path)
    mind.build()
    mind.query("what does alpha_fn do")  # learn something first
    mind.close()
    return tmp_path


class TestReadOnlyQueries:
    def test_100_read_only_queries_leave_the_db_byte_identical(self, learned_project):
        before = _db_state(learned_project)
        mind = _mind(learned_project)
        for i in range(100):
            mind.query(f"how does beta_fn work {i % 3}", learn=False)
        assert _db_state(learned_project) == before

    def test_same_context_with_and_without_learning(self, learned_project):
        q = "what calls gamma_fn"
        read_only = _mind(learned_project).query(q, learn=False).context
        learning = _mind(learned_project).query(q).context
        assert read_only == learning

    def test_a_learning_query_does_write(self, learned_project):
        before = _db_state(learned_project)
        _mind(learned_project).query("alpha_fn beta_fn gamma_fn")
        assert _db_state(learned_project) != before

    def test_probe_and_benchmark_need_no_flag(self, learned_project):
        before = _db_state(learned_project)
        mind = _mind(learned_project)
        mind.benchmark()
        mind.retrieval_probe(sample_size=3)
        assert _db_state(learned_project) == before

    def test_env_switch(self, learned_project, monkeypatch):
        monkeypatch.setenv("NEURALMIND_NO_LEARN", "1")
        before = _db_state(learned_project)
        _mind(learned_project).query("alpha_fn beta_fn gamma_fn", learn=True)
        assert _db_state(learned_project) == before

    def test_query_logs_are_skipped(self, learned_project):
        recent = learned_project / ".neuralmind" / "recent_queries.jsonl"
        before = recent.read_text() if recent.exists() else ""
        _mind(learned_project).query("beta_fn", learn=False)
        after = recent.read_text() if recent.exists() else ""
        assert after == before

    def test_mcp_learn_false_uses_a_read_only_store(self, learned_project, monkeypatch):
        from neuralmind import mcp_server
        from neuralmind.synapses import SynapseStore

        stores: list[SynapseStore] = []
        real_connect = SynapseStore._connect

        def spy_connect(self):
            stores.append(self)
            return real_connect(self)

        def no_writes(*a, **k):
            raise AssertionError("read-only query reinforced the synapse layer")

        monkeypatch.setattr(SynapseStore, "_connect", spy_connect)
        monkeypatch.setattr(SynapseStore, "reinforce", no_writes)
        mcp_server.clear_all_caches()
        mind = _mind(learned_project)
        mind.ensure_ready()
        monkeypatch.setitem(mcp_server._mind_cache, str(learned_project.resolve()), mind)
        before = _db_state(learned_project)
        stores.clear()  # only what the read-only call itself opens

        out = mcp_server.handle_tool_call(
            "neuralmind_query",
            {"project_path": str(learned_project), "question": "beta_fn", "learn": False},
        )

        assert "context" in json.loads(out)
        assert stores and all(s.read_only for s in stores)
        assert _db_state(learned_project) == before
        mcp_server.clear_all_caches()

    def test_read_only_store_refuses_writes(self, learned_project):
        import sqlite3

        from neuralmind.synapses import SynapseStore, default_db_path

        store = SynapseStore(default_db_path(learned_project), read_only=True)
        with pytest.raises(sqlite3.OperationalError):
            store.set_meta("x", "y")

    def test_read_only_store_only_opens_neuralmind_state(self, learned_project, tmp_path):
        import shutil

        from neuralmind.synapses import SynapseStore, default_db_path

        stray = tmp_path / "elsewhere" / "synapses.db"
        stray.parent.mkdir()
        shutil.copy(default_db_path(learned_project), stray)
        with pytest.raises(ValueError, match=r"\.neuralmind"):
            SynapseStore(stray, read_only=True)
        escape = learned_project / ".neuralmind" / ".." / "synapses.db"
        with pytest.raises(ValueError):
            SynapseStore(escape, read_only=True)

    def test_read_only_query_never_builds(self, tmp_path, builtin_available):
        from neuralmind.core import GraphNotBuiltError

        _write_files(tmp_path, ["a.py"])
        with pytest.raises(GraphNotBuiltError, match="Read-only queries never build"):
            _mind(tmp_path).query("a_fn", learn=False)
        assert not (tmp_path / ".neuralmind" / "graph.json").exists()

    def test_hooks_skip_learning_under_the_env_switch(self, learned_project, monkeypatch):
        from neuralmind import hooks

        monkeypatch.setenv("NEURALMIND_NO_LEARN", "1")
        before = _db_state(learned_project)
        hooks._record_tool_transition(str(learned_project), "pkg/alpha.py")
        hooks._record_tool_transition(str(learned_project), "pkg/beta.py")
        assert _db_state(learned_project) == before

    def test_cli_flag_parses(self):
        from neuralmind.cli import build_parser

        args = build_parser().parse_args(["query", ".", "q", "--no-learn"])
        assert args.no_learn is True


# --------------------------------------------------------------------------- #
# Spec 6 — project eval, stable probe, one baseline
# --------------------------------------------------------------------------- #
def _eval_project(root: Path) -> None:
    _write_files(root, ["billing/invoice.py", "auth/login.py", "store/cache.py"])
    (root / ".neuralmind.eval.yaml").write_text(
        "- q: invoice_fn helper\n  gold: [billing/invoice.py]\n"
        "- q: login_fn helper\n  gold: auth/login.py\n"
        "- q: cache_fn helper\n  gold: [store/cache.py]\n",
        "utf-8",
    )


@pytest.mark.usefixtures("builtin_available")
class TestProjectEval:
    def test_metrics_follow_the_per_question_ranks(self, tmp_path):
        from neuralmind import project_eval

        _eval_project(tmp_path)
        _mind(tmp_path).build()
        report = project_eval.run_eval(tmp_path, mind=_mind(tmp_path))

        ranks = [r.rank for r in report.results]
        n = len(ranks)
        assert report.n_questions == 3
        assert report.hit_at_1 == round(sum(1 for r in ranks if r == 1) / n, 4)
        assert report.hit_at_5 == round(sum(1 for r in ranks if r and r <= 5) / n, 4)
        assert report.mrr == round(sum(1 / r for r in ranks if r) / n, 4)
        assert report.baseline_source == "measured"
        assert report.ratio_vs_indexed == round(
            report.baseline_tokens / report.avg_context_tokens, 1
        )

    def test_eval_is_read_only(self, tmp_path):
        from neuralmind import project_eval

        _eval_project(tmp_path)
        mind = _mind(tmp_path)
        mind.build()
        mind.query("invoice_fn")
        before = _db_state(tmp_path)
        project_eval.run_eval(tmp_path, mind=_mind(tmp_path))
        assert _db_state(tmp_path) == before

    def test_history_and_report(self, tmp_path):
        from neuralmind import project_eval

        _eval_project(tmp_path)
        _mind(tmp_path).build()
        for _ in range(2):
            project_eval.append_history(
                tmp_path, project_eval.run_eval(tmp_path, mind=_mind(tmp_path))
            )

        rows = project_eval.read_history(tmp_path)
        assert len(rows) == 2
        assert {"date", "git_sha", "version", "node_count", "hit_at_5", "mrr"} <= set(rows[0])
        table = project_eval.render_report(rows)
        assert table.startswith("| Date | Commit | NeuralMind | Nodes")
        assert "invoice_fn" not in table  # questions stay out unless asked for
        detailed = project_eval.render_report(rows, project_eval.read_last_run(tmp_path))
        assert "invoice_fn helper" in detailed

    def test_cli_eval_and_report(self, tmp_path, capsys, monkeypatch):
        from neuralmind import cli, core

        _eval_project(tmp_path)
        _mind(tmp_path).build()
        real = core.NeuralMind

        def factory(*a, **k):
            mind = real(*a, **k)
            mind.embedder._embed_fn = _fake_embed
            return mind

        monkeypatch.setattr(core, "NeuralMind", factory)
        monkeypatch.setattr("sys.argv", ["neuralmind", "eval", str(tmp_path)])
        cli.main()
        out = capsys.readouterr().out
        assert "NeuralMind eval" in out and "3 questions, read-only" in out
        monkeypatch.setattr("sys.argv", ["neuralmind", "eval", str(tmp_path), "--report"])
        cli.main()
        assert "| Date |" in capsys.readouterr().out

    def test_questions_file_is_validated(self, tmp_path):
        from neuralmind import project_eval

        (tmp_path / ".neuralmind.eval.yaml").write_text("- q: no gold here\n", "utf-8")
        with pytest.raises(ValueError, match="entry 1 needs both 'q' and 'gold'"):
            project_eval.load_questions(tmp_path)

    def test_suggest_drafts_questions_with_gold(self, tmp_path):
        from neuralmind import project_eval

        (tmp_path / "billing").mkdir()
        (tmp_path / "billing" / "invoices.py").write_text(
            '"""Render monthly invoices and email them to customers."""\n', "utf-8"
        )
        (tmp_path / "auth.py").write_text(
            '"""Verify passwords and issue session tokens for users."""\n', "utf-8"
        )
        (tmp_path / "README.md").write_text("# Demo\n\n## Invoices\n\nText.\n", "utf-8")

        drafts = project_eval.suggest_questions(tmp_path, n=10)
        golds = {d["gold"][0] for d in drafts}
        assert {"billing/invoices.py", "auth.py"} <= golds
        assert any(d["q"] == "How does invoices work?" for d in drafts)
        text = project_eval.render_suggestions(drafts)
        assert project_eval.load_questions(tmp_path, _write(tmp_path / "s.yaml", text))


def _write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


class TestStableProbe:
    def _nodes(self, n: int, prefix: str = "n") -> list[dict]:
        return [
            {
                "id": f"{prefix}{i}",
                "label": f"sym_{i}",
                "file_type": "code",
                "source_file": f"f{i}.py",
            }
            for i in range(n)
        ]

    def test_samples_survive_a_rebuild_that_adds_5_percent(self):
        from neuralmind.probe import sample_nodes

        base = self._nodes(1000)
        grown = base + self._nodes(50, prefix="new")
        a = {n["id"] for n in sample_nodes(base, 200, seed=0)}
        b = {n["id"] for n in sample_nodes(grown, 200, seed=0)}
        assert len(a & b) / 200 >= 0.90

    def test_seed_changes_the_sample(self):
        from neuralmind.probe import sample_nodes

        base = self._nodes(500)
        a = {n["id"] for n in sample_nodes(base, 50, seed=0)}
        b = {n["id"] for n in sample_nodes(base, 50, seed=1)}
        assert a != b

    def test_baseline_diff_uses_shared_symbols_only(self):
        from neuralmind import quality
        from neuralmind.probe import compare_on_shared

        def q(qid, rank):
            return quality.evaluate_query(qid, ["x.py"] if rank else ["y.py"], ["x.py"])

        baseline = quality.aggregate("p", [q("a", 1), q("b", 0), q("gone", 1)]).to_dict()
        current = quality.aggregate("p", [q("a", 1), q("b", 1), q("new", 0)])
        out = compare_on_shared(current, baseline)

        assert (out["shared"], out["added"], out["dropped"]) == (2, 1, 1)
        mrr = next(d for d in out["deltas"] if d["metric"] == "mrr")
        assert (mrr["baseline"], mrr["current"]) == (0.5, 1.0)


@pytest.mark.usefixtures("builtin_available")
class TestOneBaseline:
    def test_build_measures_and_benchmark_names_it(self, tmp_path):
        from neuralmind import baseline

        _write_files(tmp_path, ["a.py", "b.py"])
        _mind(tmp_path).build()
        measured = baseline.load(tmp_path)
        expected = baseline.count_file_tokens([tmp_path / "a.py", tmp_path / "b.py"])
        assert measured["tokens"] == expected and measured["files"] == 2

        result = _mind(tmp_path).benchmark()
        assert result["baseline"]["source"] == "measured"
        assert result["estimated_full_codebase_tokens"] == expected
        assert f"{expected:,} tokens in 2 indexed files" in result["summary"]

        naive = _mind(tmp_path).benchmark(naive_50k=True)
        assert naive["estimated_full_codebase_tokens"] == 50_000
        assert "--naive-50k" in naive["summary"]

    def test_benchmark_uses_the_project_questions(self, tmp_path):
        _eval_project(tmp_path)
        _mind(tmp_path).build()
        result = _mind(tmp_path).benchmark()
        assert result["questions"] == "project eval"
        assert [r["query"] for r in result["results"] if r["type"] == "query"] == [
            "invoice_fn helper",
            "login_fn helper",
            "cache_fn helper",
        ]

    def test_savings_divides_by_the_measured_baseline(self, tmp_path):
        from neuralmind import baseline
        from neuralmind.savings import compute_savings

        _write_files(tmp_path, ["a.py"])
        mind = _mind(tmp_path)
        mind.build()
        mind.query("a_fn")
        counted = compute_savings(tmp_path)["total_queries"]
        mind.query("a_fn", learn=False)  # measurement, not usage

        report = compute_savings(tmp_path)
        assert report["baseline_source"] == "measured"
        assert report["baseline_tokens_per_query"] == baseline.load(tmp_path)["tokens"]
        assert report["total_queries"] == counted
        assert compute_savings(tmp_path, naive_50k=True)["baseline_tokens_per_query"] == 50_000

    def test_dry_run_measures_the_files_a_build_would_index(self, tmp_path):
        from neuralmind import baseline, cli

        _write_files(tmp_path, ["a.py", "b.py"])
        scan = cli._dry_run_scan(str(tmp_path))
        assert scan["est_full_tokens"] == baseline.count_file_tokens(
            [tmp_path / "a.py", tmp_path / "b.py"]
        )
        assert scan["baseline"].startswith("measured:")
        assert cli._dry_run_scan(str(tmp_path), naive_50k=True)["est_full_tokens"] == 50_000


def test_neuralmind_config_parses_new_keys(tmp_path):
    from neuralmind.neuralmind_config import NeuralmindConfig

    (tmp_path / ".neuralmind.yaml").write_text(
        "respect_gitignore: no\ninclude_ignored: generated/**\n", "utf-8"
    )
    cfg = NeuralmindConfig.load(tmp_path)
    assert cfg.respect_gitignore is False
    assert cfg.include_ignored == ("generated/**",)
