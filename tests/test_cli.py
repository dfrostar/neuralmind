"""Tests for NeuralMind CLI functionality with real assertions."""

import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestCLIEncoding:
    """Regression tests for the Windows cp1252 stdout crash — UnicodeEncodeError
    when printing arrows / em-dashes / box-drawing glyphs (e.g. `neuralmind query`
    output, and the em-dash in argparse --help) to a cp1252 console."""

    def test_force_utf8_io_lets_cp1252_stream_print_non_ascii(self, monkeypatch):
        import io

        from neuralmind.cli import _force_utf8_io

        buf = io.BytesIO()
        # A cp1252 text stream raises UnicodeEncodeError on these glyphs...
        cp1252_stream = io.TextIOWrapper(buf, encoding="cp1252", newline="")
        monkeypatch.setattr(sys, "stdout", cp1252_stream)

        _force_utf8_io()

        # ...but after the reconfigure the same print must succeed as UTF-8.
        # → = →, — = em-dash, ─ = box-drawing, é = é
        glyphs = "→ — ─ café"
        print(glyphs)
        sys.stdout.flush()
        assert glyphs.encode("utf-8") in buf.getvalue()

    def test_force_utf8_io_is_noop_when_reconfigure_missing(self, monkeypatch):
        from neuralmind.cli import _force_utf8_io

        class _NoReconfigure:
            pass

        monkeypatch.setattr(sys, "stdout", _NoReconfigure())
        monkeypatch.setattr(sys, "stderr", _NoReconfigure())
        _force_utf8_io()  # must not raise (e.g. under pytest capture objects)


class TestCLIBuild:
    """Tests for CLI build command."""

    def test_cmd_build_success(self, temp_project, capsys):
        """Test cmd_build returns success dict with node counts."""
        from neuralmind.cli import cmd_build

        args = MagicMock()
        args.project_path = str(temp_project)
        args.force = False
        args.rebuild_index = False

        cmd_build(args)

        captured = capsys.readouterr()
        assert "Build successful!" in captured.out
        assert "Nodes:" in captured.out

    def test_cmd_build_force_flag(self, temp_project, capsys):
        """Test cmd_build respects --force flag."""
        from neuralmind.cli import cmd_build

        args = MagicMock()
        args.project_path = str(temp_project)
        args.force = True
        args.rebuild_index = False

        cmd_build(args)

        captured = capsys.readouterr()
        assert "Force rebuild: True" in captured.out

    def test_cmd_build_nonexistent_path(self, capsys):
        """Test cmd_build fails on nonexistent path."""
        from neuralmind.cli import cmd_build

        args = MagicMock()
        args.project_path = "/nonexistent/path/12345"
        args.force = False
        args.rebuild_index = False

        with pytest.raises(SystemExit):
            cmd_build(args)

        captured = capsys.readouterr()
        assert "Build failed" in captured.out or "error" in captured.out.lower()

    @pytest.mark.parametrize("backend", ["chroma", "in_memory"])
    def test_cmd_build_off_turbovec_leaves_no_turbovec_store(
        self, temp_project, capsys, request, backend
    ):
        """The pre-build quarantine check used to construct TurboVecEmbedder
        whatever the backend, and its __init__ creates
        .neuralmind/neuralmind_turbovec/store.sqlite: every build of a chroma
        project left an empty turbovec store behind."""
        from neuralmind.cli import cmd_build

        if backend == "chroma":
            request.getfixturevalue("mock_chromadb")
        (temp_project / "neuralmind-backend.yaml").write_text(
            f"backend: {backend}\n", encoding="utf-8"
        )
        args = MagicMock()
        args.project_path = str(temp_project)
        args.force = False
        args.rebuild_index = False

        cmd_build(args)

        assert "Build successful!" in capsys.readouterr().out
        assert not (temp_project / ".neuralmind" / "neuralmind_turbovec").exists()


class TestTurbovecMismatchCheck:
    """``_check_turbovec_mismatch``: the quarantine heads-up cmd_build prints."""

    @pytest.mark.parametrize("backend", ["graph", "chroma", "chromadb", "in_memory"])
    def test_skipped_when_backend_is_not_turbovec(self, tmp_path, backend):
        from neuralmind.cli import _check_turbovec_mismatch

        (tmp_path / "neuralmind-backend.yaml").write_text(f"backend: {backend}\n", encoding="utf-8")
        assert _check_turbovec_mismatch(str(tmp_path)) is None
        assert not (tmp_path / ".neuralmind").exists()

    @pytest.mark.parametrize("config", [None, "backend: turbovec\n", "backend: turboquant\n"])
    def test_still_warns_on_a_quarantined_turbovec_index(self, tmp_path, config):
        from neuralmind.cli import _check_turbovec_mismatch

        if config:
            (tmp_path / "neuralmind-backend.yaml").write_text(config, encoding="utf-8")
        tv_dir = tmp_path / ".neuralmind" / "neuralmind_turbovec"
        tv_dir.mkdir(parents=True)
        (tv_dir / "index.tvim.stale").write_bytes(b"")

        warning = _check_turbovec_mismatch(str(tmp_path))
        assert warning is not None
        assert "quarantined" in warning


class TestCLIQuery:
    """Tests for CLI query command."""

    def test_cmd_query_outputs_context(self, temp_project, capsys):
        """Test cmd_query outputs relevant context for the question."""
        from neuralmind.cli import cmd_build, cmd_query

        # Build first
        build_args = MagicMock()
        build_args.project_path = str(temp_project)
        build_args.force = False
        build_args.rebuild_index = False
        cmd_build(build_args)
        capsys.readouterr()  # Clear build output

        args = MagicMock()
        args.project_path = str(temp_project)
        args.question = "authentication"
        args.json = False

        cmd_query(args)

        captured = capsys.readouterr()
        # Should output query confirmation and separator
        assert "Query:" in captured.out or "authentication" in captured.out
        assert "====" in captured.out

    def test_cmd_query_json_output(self, temp_project, capsys):
        """Test cmd_query --json produces valid JSON."""
        from neuralmind.cli import cmd_build, cmd_query

        # Build first
        build_args = MagicMock()
        build_args.project_path = str(temp_project)
        build_args.force = False
        build_args.rebuild_index = False
        cmd_build(build_args)
        capsys.readouterr()  # Clear build output

        args = MagicMock()
        args.project_path = str(temp_project)
        args.question = "function"
        args.json = True

        cmd_query(args)

        captured = capsys.readouterr()
        # Extract JSON from output (may have prefix lines)
        lines = captured.out.split("\n")
        json_start = None
        for i, line in enumerate(lines):
            if line.strip().startswith("{"):
                json_start = i
                break
        assert json_start is not None, f"No JSON found in output: {captured.out}"
        json_text = "\n".join(lines[json_start:])
        data = json.loads(json_text)
        assert "query" in data
        assert "tokens" in data
        assert "reduction_ratio" in data
        assert data["query"] == "function"

    def test_cmd_query_relevance_sidecar(self, temp_project, capsys):
        """--relevance --json attaches a structured relevance sidecar."""
        from neuralmind.cli import cmd_build, cmd_query

        build_args = MagicMock()
        build_args.project_path = str(temp_project)
        build_args.force = False
        build_args.rebuild_index = False
        cmd_build(build_args)
        capsys.readouterr()  # Clear build output

        args = MagicMock()
        args.project_path = str(temp_project)
        args.question = "authentication"
        args.json = True
        args.relevance = True
        args.trace = False
        args.trace_verbose = False

        cmd_query(args)

        captured = capsys.readouterr()
        lines = captured.out.split("\n")
        json_start = next(i for i, line in enumerate(lines) if line.strip().startswith("{"))
        data = json.loads("\n".join(lines[json_start:]))
        assert "relevance" in data
        assert data["relevance"]["version"] == 1
        assert "files" in data["relevance"]

    def test_cmd_query_has_token_reduction(self, temp_project, capsys):
        """Test cmd_query reports token reduction ratio."""
        from neuralmind.cli import cmd_build, cmd_query

        # Build first
        build_args = MagicMock()
        build_args.project_path = str(temp_project)
        build_args.force = False
        build_args.rebuild_index = False
        cmd_build(build_args)
        capsys.readouterr()  # Clear build output

        args = MagicMock()
        args.project_path = str(temp_project)
        args.question = "test"
        args.json = False

        cmd_query(args)

        captured = capsys.readouterr()
        # Should report reduction ratio > 1.0
        assert "x reduction" in captured.out or "reduction" in captured.out.lower()

    def test_cmd_query_tty_opt_in_prompt_writes_consent(self, capsys):
        """Test query prompts once and stores consent when eligible."""
        from neuralmind.cli import cmd_query

        args = MagicMock()
        args.project_path = "/tmp/project"
        args.question = "auth?"
        args.json = False

        mock_result = MagicMock()
        mock_result.budget.total = 42
        mock_result.reduction_ratio = 2.0
        mock_result.layers_used = ["L0", "L1"]
        mock_result.context = "ctx"

        with patch("neuralmind.cli.memory.should_prompt_for_consent", return_value=True):
            with patch("neuralmind.cli.memory.prompt_for_memory_consent", return_value=True):
                with patch("neuralmind.cli.memory.write_consent_sentinel") as mock_write:
                    with patch("neuralmind.cli.create_mind") as mock_create:
                        mock_create.return_value.query.return_value = mock_result
                        cmd_query(args)

        mock_write.assert_called_once_with(True)
        captured = capsys.readouterr()
        assert "memory logging enabled" in captured.out.lower()


class TestCLIWakeup:
    """Tests for CLI wakeup command."""

    def test_cmd_wakeup_outputs_context(self, temp_project, capsys):
        """Test cmd_wakeup produces context output."""
        from neuralmind.cli import cmd_build, cmd_wakeup

        # Build first
        build_args = MagicMock()
        build_args.project_path = str(temp_project)
        build_args.force = False
        build_args.rebuild_index = False
        cmd_build(build_args)
        capsys.readouterr()  # Clear build output

        args = MagicMock()
        args.project_path = str(temp_project)
        args.json = False

        cmd_wakeup(args)

        captured = capsys.readouterr()
        # Should output context header with token count
        assert "Wake-up Context" in captured.out or "tokens" in captured.out.lower()

    def test_cmd_wakeup_json_output(self, temp_project, capsys):
        """Test cmd_wakeup --json produces valid JSON."""
        from neuralmind.cli import cmd_build, cmd_wakeup

        # Build first
        build_args = MagicMock()
        build_args.project_path = str(temp_project)
        build_args.force = False
        build_args.rebuild_index = False
        cmd_build(build_args)
        capsys.readouterr()  # Clear build output

        args = MagicMock()
        args.project_path = str(temp_project)
        args.json = True

        cmd_wakeup(args)

        captured = capsys.readouterr()
        # Extract JSON from output (may have prefix lines)
        lines = captured.out.split("\n")
        json_start = None
        for i, line in enumerate(lines):
            if line.strip().startswith("{"):
                json_start = i
                break
        assert json_start is not None, f"No JSON found in output: {captured.out}"
        json_text = "\n".join(lines[json_start:])
        data = json.loads(json_text)
        assert "type" in data
        assert data["type"] == "wakeup"
        assert "tokens" in data
        assert "context" in data


class TestCLISearch:
    """Tests for CLI search command."""

    def test_cmd_search_returns_results(self, temp_project, capsys):
        """Test cmd_search returns formatted results."""
        from neuralmind.cli import cmd_build, cmd_search

        # Build first
        build_args = MagicMock()
        build_args.project_path = str(temp_project)
        build_args.force = False
        build_args.rebuild_index = False
        cmd_build(build_args)
        capsys.readouterr()  # Clear build output

        args = MagicMock()
        args.project_path = str(temp_project)
        args.query = "function"
        args.n = 5
        args.json = False

        cmd_search(args)

        captured = capsys.readouterr()
        # Should output search header
        assert "Search:" in captured.out or "function" in captured.out

    def test_cmd_search_respects_n_parameter(self, temp_project, capsys):
        """Test cmd_search --n parameter limits results."""
        from neuralmind.cli import cmd_build, cmd_search

        # Build first
        build_args = MagicMock()
        build_args.project_path = str(temp_project)
        build_args.force = False
        build_args.rebuild_index = False
        cmd_build(build_args)
        capsys.readouterr()  # Clear build output

        args = MagicMock()
        args.project_path = str(temp_project)
        args.query = "test"
        args.n = 2
        args.json = False

        cmd_search(args)

        captured = capsys.readouterr()
        # Count the number of numbered results (e.g., "1. ", "2. ")
        lines = captured.out.split("\n")
        result_lines = [line for line in lines if line and line[0].isdigit() and ". " in line]
        assert len(result_lines) <= 2

    def test_cmd_search_json_output(self, temp_project, capsys):
        """Test cmd_search --json produces valid JSON."""
        from neuralmind.cli import cmd_build, cmd_search

        # Build first
        build_args = MagicMock()
        build_args.project_path = str(temp_project)
        build_args.force = False
        build_args.rebuild_index = False
        cmd_build(build_args)
        capsys.readouterr()  # Clear build output

        args = MagicMock()
        args.project_path = str(temp_project)
        args.query = "code"
        args.n = 3
        args.json = True

        cmd_search(args)

        captured = capsys.readouterr()
        # Extract JSON from output (may have prefix lines)
        lines = captured.out.split("\n")
        json_start = None
        for i, line in enumerate(lines):
            if line.strip().startswith("[") or line.strip().startswith("{"):
                json_start = i
                break
        assert json_start is not None, f"No JSON found in output: {captured.out}"
        json_text = "\n".join(lines[json_start:])
        results = json.loads(json_text)
        assert isinstance(results, list)
        assert len(results) <= 3

    @pytest.mark.parametrize("bad", ["0", "-3"])
    def test_search_n_below_one_is_a_usage_error(self, temp_project, capsys, bad):
        """--n 0 / --n -3 used to return 1 result (the backend floors k at 1)."""
        from neuralmind.cli import build_parser

        with pytest.raises(SystemExit) as exc:
            build_parser().parse_args(["search", str(temp_project), "auth", f"--n={bad}"])
        assert exc.value.code == 2
        assert f"argument --n: must be at least 1, got {bad}" in capsys.readouterr().err

    def test_search_n_one_is_accepted(self, temp_project):
        from neuralmind.cli import build_parser

        args = build_parser().parse_args(["search", str(temp_project), "auth", "--n", "1"])
        assert args.n == 1


class TestCLIStats:
    """Tests for CLI stats command."""

    def test_cmd_stats_outputs_statistics(self, temp_project, capsys):
        """Test cmd_stats outputs project statistics."""
        from neuralmind.cli import cmd_stats

        args = MagicMock()
        args.project_path = str(temp_project)
        args.json = False

        cmd_stats(args)

        captured = capsys.readouterr()
        # Should output project name and built status
        assert "Project:" in captured.out
        assert "Built:" in captured.out

    def test_cmd_stats_json_output(self, temp_project, capsys):
        """Test cmd_stats --json produces valid JSON with statistics."""
        from neuralmind.cli import cmd_stats

        args = MagicMock()
        args.project_path = str(temp_project)
        args.json = True

        cmd_stats(args)

        captured = capsys.readouterr()
        stats = json.loads(captured.out)
        assert "project" in stats
        assert "built" in stats
        assert isinstance(stats["built"], bool)

    def test_cmd_stats_dot_names_the_directory(self, temp_project, capsys, monkeypatch):
        """`neuralmind stats .` printed "Project: " — Path(".").name is empty."""
        from neuralmind.cli import cmd_stats

        monkeypatch.setenv("NEURALMIND_NO_DAEMON", "1")
        monkeypatch.chdir(temp_project)
        args = MagicMock()
        args.project_path = "."
        args.json = False
        cmd_stats(args)
        assert f"Project: {temp_project.resolve().name}\n" in capsys.readouterr().out

        args.json = True
        cmd_stats(args)
        assert json.loads(capsys.readouterr().out)["project"] == temp_project.resolve().name

    def test_cmd_stats_node_count_matches_graph(self, temp_project, capsys):
        """Test cmd_stats reports correct node count for sample graph."""
        from neuralmind.cli import cmd_build, cmd_stats

        # Build first
        build_args = MagicMock()
        build_args.project_path = str(temp_project)
        build_args.force = False
        build_args.rebuild_index = False
        cmd_build(build_args)
        capsys.readouterr()  # Clear build output

        args = MagicMock()
        args.project_path = str(temp_project)
        args.json = True

        cmd_stats(args)

        captured = capsys.readouterr()
        stats = json.loads(captured.out)
        # sample_graph has 6 nodes
        assert stats.get("total_nodes") == 6


class TestCLIIngest:
    """Tests for `neuralmind ingest` and its `learn` alias."""

    # --- a file inside the project is indexed once ------------------------ #

    @staticmethod
    def _builtin_project(tmp_path):
        """A project built with the built-in graph, which indexes Markdown."""
        from neuralmind import graphgen
        from neuralmind.core import NeuralMind

        if not graphgen.is_available():
            pytest.skip("tree-sitter not installed")
        root = tmp_path / "proj"
        (root / "docs").mkdir(parents=True)
        (root / "app.py").write_text("def handler():\n    return 1\n", encoding="utf-8")
        (root / "docs" / "guide.md").write_text(
            "# Deployment Guide\n\nThe zebra-unicorn deployment uses blue green rollouts.\n",
            encoding="utf-8",
        )
        mind = NeuralMind(str(root))
        assert mind.build()["success"]
        return root.resolve()

    @staticmethod
    def _ingest(path, project):
        from neuralmind.cli import cmd_ingest

        args = MagicMock()
        args.file_path = str(path)
        args.type = "auto"
        args.json = True
        args.project_path = str(project)
        args.dry_run = False
        args.quiet = True
        args.no_recursive = False
        cmd_ingest(args)

    @staticmethod
    def _stored_sources(project, phrase: str) -> list[str]:
        """``source_file`` of every stored row a search can reach.

        Backend-agnostic (the default backend has no Chroma collection); the
        index is a handful of rows, so a wide search returns all of them.
        """
        from neuralmind.core import NeuralMind

        hits = NeuralMind(str(project)).search(phrase, n=50)
        return [str((h.get("metadata") or {}).get("source_file", "")) for h in hits]

    def test_ingest_markdown_the_graph_already_indexes_is_not_duplicated(self, tmp_path, capsys):
        """`ingest docs/guide.md` stored a second copy under the absolute path,
        so the same text came back twice in query context."""
        from neuralmind.core import NeuralMind

        root = self._builtin_project(tmp_path)
        capsys.readouterr()
        self._ingest(root / "docs" / "guide.md", root)
        data = json.loads(capsys.readouterr().out)

        context = NeuralMind(str(root)).query("zebra-unicorn deployment rollouts").context
        assert context.count("zebra-unicorn") == 1, context
        assert str(root / "docs" / "guide.md") not in self._stored_sources(root, "zebra-unicorn")
        assert data["success"] is True
        assert data["already_indexed"] == ["docs/guide.md"]
        assert data["total_nodes"] == 0

    def test_ingest_markdown_edited_since_the_build_reports_it_needs_one(self, tmp_path, capsys):
        """The graph holds the text as of the last build. Skipping an edited
        file as already indexed left the edit unsearchable without a word;
        ingesting it would sit beside the graph's old text."""
        from neuralmind.core import NeuralMind

        root = self._builtin_project(tmp_path)
        guide = root / "docs" / "guide.md"
        guide.write_text(
            "# Deployment Guide\n\nThe zebra-unicorn deployment uses canary rollouts.\n",
            encoding="utf-8",
        )
        capsys.readouterr()
        self._ingest(guide, root)
        data = json.loads(capsys.readouterr().out)
        assert data["needs_build"] == ["docs/guide.md"]
        assert data["already_indexed"] == [] and data["total_nodes"] == 0

        assert NeuralMind(str(root)).build()["success"]
        capsys.readouterr()
        self._ingest(guide, root)
        data = json.loads(capsys.readouterr().out)
        assert data["already_indexed"] == ["docs/guide.md"] and data["needs_build"] == []

    def test_ingest_in_project_file_outside_the_graph_uses_relative_path(self, tmp_path, capsys):
        """The graph doesn't index .txt, so it's ingested — under the
        project-relative path every other node uses, not the absolute one."""
        root = self._builtin_project(tmp_path)
        notes = root / "docs" / "notes.txt"
        notes.write_text("The quokka-lighthouse runbook covers paging.\n", encoding="utf-8")
        capsys.readouterr()
        self._ingest(notes, root)
        data = json.loads(capsys.readouterr().out)

        sources = self._stored_sources(root, "quokka-lighthouse runbook")
        assert "docs/notes.txt" in sources
        assert str(notes) not in sources
        assert data["total_nodes"] >= 1 and data["already_indexed"] == []

    def test_ingest_file_outside_the_project_keeps_absolute_path(self, tmp_path, capsys):
        root = self._builtin_project(tmp_path)
        outside = tmp_path / "elsewhere" / "ext.md"
        outside.parent.mkdir()
        outside.write_text("# External\n\nThe narwhal-teapot spec lives here.\n", encoding="utf-8")
        capsys.readouterr()
        self._ingest(outside, root)
        data = json.loads(capsys.readouterr().out)

        assert data["total_nodes"] >= 1
        assert str(outside.resolve()) in self._stored_sources(root, "narwhal-teapot spec")

    def test_ingest_document_api_skips_a_file_the_graph_already_indexes(self, tmp_path):
        """The MCP tool's path (NeuralMind.ingest_document) had the same
        double-indexing bug as `neuralmind ingest`."""
        from neuralmind.core import NeuralMind

        root = self._builtin_project(tmp_path)
        result = NeuralMind(str(root)).ingest_document(root / "docs" / "guide.md")

        assert result["success"] is True and result["node_count"] == 0
        assert result["already_indexed"] == ["docs/guide.md"] and result["needs_build"] == []
        context = NeuralMind(str(root)).query("zebra-unicorn deployment rollouts").context
        assert context.count("zebra-unicorn") == 1, context

    def test_ingest_document_api_reports_a_file_edited_since_the_build(self, tmp_path):
        from neuralmind.core import NeuralMind

        root = self._builtin_project(tmp_path)
        mind = NeuralMind(str(root))
        mind.query("zebra-unicorn")  # load the graph, as a cached MCP instance has
        guide = root / "docs" / "guide.md"
        guide.write_text("# Deployment Guide\n\nNow with canary rollouts.\n", encoding="utf-8")
        result = mind.ingest_document(guide)

        assert result["node_count"] == 0 and result["already_indexed"] == []
        assert result["needs_build"] == ["docs/guide.md"]
        assert "neuralmind build" in result["message"]

    def test_ingest_document_api_stores_an_in_project_file_under_its_relative_path(self, tmp_path):
        from neuralmind.core import NeuralMind

        root = self._builtin_project(tmp_path)
        notes = root / "docs" / "notes.txt"
        notes.write_text("The quokka-lighthouse runbook covers paging.\n", encoding="utf-8")
        result = NeuralMind(str(root)).ingest_document(notes)

        assert result["node_count"] >= 1 and result["already_indexed"] == []
        sources = self._stored_sources(root, "quokka-lighthouse runbook")
        assert "docs/notes.txt" in sources and str(notes) not in sources

    def test_ingest_single_markdown(self, temp_project, capsys):
        """Ingest a single markdown file and verify node count."""
        from neuralmind.cli import cmd_ingest

        dummy = temp_project / "notes.md"
        dummy.write_text("# Title\n\nSome important content here.")

        args = MagicMock()
        args.file_path = str(dummy)
        args.type = "auto"
        args.json = False
        args.project_path = str(temp_project)
        args.dry_run = False
        args.quiet = False
        args.no_recursive = False

        cmd_ingest(args)

        captured = capsys.readouterr()
        assert "ingested" in captured.out.lower()
        assert "content node" in captured.out.lower()

    def test_ingest_json_output(self, temp_project, capsys):
        """--json returns valid JSON with expected keys."""
        from neuralmind.cli import cmd_ingest

        dummy = temp_project / "data.txt"
        dummy.write_text("Line 1\nLine 2\nLine 3")

        args = MagicMock()
        args.file_path = str(dummy)
        args.type = "auto"
        args.json = True
        args.project_path = str(temp_project)
        args.dry_run = False
        args.quiet = True
        args.no_recursive = False

        cmd_ingest(args)

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["success"] is True
        assert data["total_nodes"] > 0
        assert data["files_processed"] == 1
        assert "wall_time_seconds" in data

    def test_ingest_nonexistent_file(self, capsys):
        """Error on nonexistent file."""
        from neuralmind.cli import cmd_ingest

        args = MagicMock()
        args.file_path = "/nonexistent/path/file.md"
        args.type = "auto"
        args.json = False
        args.project_path = None
        args.dry_run = False
        args.quiet = False
        args.no_recursive = False

        with pytest.raises(SystemExit):
            cmd_ingest(args)

    def test_ingest_directory(self, temp_project, capsys):
        """Ingest a directory of files recursively."""
        from neuralmind.cli import cmd_ingest

        subdir = temp_project / "docs"
        subdir.mkdir()
        (subdir / "a.md").write_text("# Doc A\nContent A")
        (subdir / "b.txt").write_text("Content B")
        (subdir / "c.md").write_text("# Doc C\nContent C")

        args = MagicMock()
        args.file_path = str(subdir)
        args.type = "auto"
        args.json = True
        args.project_path = str(temp_project)
        args.dry_run = False
        args.quiet = True
        args.no_recursive = False

        cmd_ingest(args)

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["success"] is True
        assert data["files_processed"] == 3
        assert data["total_nodes"] >= 3

    def test_ingest_dry_run(self, temp_project, capsys):
        """--dry-run lists files without ingesting."""
        from neuralmind.cli import cmd_ingest

        subdir = temp_project / "docs"
        subdir.mkdir()
        (subdir / "x.md").write_text("# X")
        (subdir / "y.txt").write_text("Y")

        args = MagicMock()
        args.file_path = str(subdir)
        args.type = "auto"
        args.json = False
        args.project_path = str(temp_project)
        args.dry_run = True
        args.quiet = False
        args.no_recursive = False

        cmd_ingest(args)

        captured = capsys.readouterr()
        assert "Would ingest" in captured.out
        assert "x.md" in captured.out
        assert "y.txt" in captured.out

    def test_ingest_no_recursive(self, temp_project, capsys):
        """--no-recursive does not descend into subdirectories."""
        from neuralmind.cli import cmd_ingest

        subdir = temp_project / "docs"
        subdir.mkdir()
        (subdir / "top.md").write_text("# Top")
        nested = subdir / "nested"
        nested.mkdir()
        (nested / "deep.md").write_text("# Deep")

        args = MagicMock()
        args.file_path = str(subdir)
        args.type = "auto"
        args.json = True
        args.project_path = str(temp_project)
        args.dry_run = False
        args.quiet = True
        args.no_recursive = True

        cmd_ingest(args)

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["files_processed"] == 1

    def test_ingest_quiet(self, temp_project, capsys):
        """--quiet suppresses progress output."""
        from neuralmind.cli import cmd_ingest

        dummy = temp_project / "q.md"
        dummy.write_text("# Quiet\nContent")

        args = MagicMock()
        args.file_path = str(dummy)
        args.type = "auto"
        args.json = False
        args.project_path = str(temp_project)
        args.dry_run = False
        args.quiet = True
        args.no_recursive = False

        cmd_ingest(args)

        captured = capsys.readouterr()
        assert captured.out == ""

    def test_learn_is_alias_for_ingest(self, temp_project, capsys):
        """`learn` calls the same code path as `ingest`."""
        from neuralmind.cli import cmd_learn

        dummy = temp_project / "alias.md"
        dummy.write_text("# Alias test")

        args = MagicMock()
        args.file_path = str(dummy)
        args.type = "auto"
        args.json = False
        args.project_path = str(temp_project)
        args.dry_run = False
        args.quiet = False
        args.no_recursive = False

        result = cmd_learn(args)
        assert result is None

        captured = capsys.readouterr()
        assert "ingested" in captured.out.lower()

    def test_learn_no_deprecation_warning(self, temp_project, capsys):
        """learn does not print deprecation warnings."""
        from neuralmind.cli import cmd_learn

        dummy = temp_project / "test.md"
        dummy.write_text("# Test\nContent")

        args = MagicMock()
        args.file_path = str(dummy)
        args.type = "auto"
        args.json = False
        args.project_path = str(temp_project)
        args.dry_run = False
        args.quiet = False
        args.no_recursive = False

        cmd_learn(args)

        captured = capsys.readouterr()
        assert "deprecated" not in captured.out.lower()

    def test_learn_no_patterns_file(self, temp_project, capsys):
        """learn must not write the old learned_patterns.json anymore."""
        from neuralmind.cli import cmd_learn

        dummy = temp_project / "test.md"
        dummy.write_text("# Test\nContent")

        args = MagicMock()
        args.file_path = str(dummy)
        args.type = "auto"
        args.json = False
        args.project_path = str(temp_project)
        args.dry_run = False
        args.quiet = False
        args.no_recursive = False

        cmd_learn(args)

        patterns_file = temp_project / ".neuralmind" / "learned_patterns.json"
        assert not patterns_file.exists()

    def test_ingest_empty_directory(self, temp_project, capsys):
        """Empty directory exits cleanly with a message."""
        from neuralmind.cli import cmd_ingest

        empty = temp_project / "empty"
        empty.mkdir()

        args = MagicMock()
        args.file_path = str(empty)
        args.type = "auto"
        args.json = False
        args.project_path = str(temp_project)
        args.dry_run = False
        args.quiet = False
        args.no_recursive = False

        # Exits 0 with a message
        with pytest.raises(SystemExit) as exc_info:
            cmd_ingest(args)
        assert exc_info.value.code == 0

        captured = capsys.readouterr()
        assert "no supported files" in captured.out.lower()

    def test_ingest_invalid_binary_rejected(self, temp_project, capsys):
        """Binary file with .md extension is rejected gracefully."""
        from neuralmind.cli import cmd_ingest

        fake_md = temp_project / "fake.md"
        fake_md.write_bytes(b"\x7fELF not actually markdown")

        args = MagicMock()
        args.file_path = str(fake_md)
        args.type = "auto"
        args.json = True
        args.project_path = str(temp_project)
        args.dry_run = False
        args.quiet = True
        args.no_recursive = False

        # Single-file error path: exits non-zero via sys.exit(1)
        with pytest.raises(SystemExit):
            cmd_ingest(args)

    def test_ingest_mixed_valid_invalid_directory(self, temp_project, capsys):
        """Mixed valid+invalid files in a directory: batch continues, errors reported, exit 1."""
        from neuralmind.cli import cmd_ingest

        subdir = temp_project / "mixed"
        subdir.mkdir()
        (subdir / "good.md").write_text("# Good\nContent")
        (subdir / "also_good.txt").write_text("Also good")
        (subdir / "bad.md").write_bytes(b"\x7fELF not markdown")

        args = MagicMock()
        args.file_path = str(subdir)
        args.type = "auto"
        args.json = True
        args.project_path = str(temp_project)
        args.dry_run = False
        args.quiet = True
        args.no_recursive = False

        # Should exit 1 because of the bad file
        with pytest.raises(SystemExit) as exc_info:
            cmd_ingest(args)
        assert exc_info.value.code == 1

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["success"] is False
        assert data["files_processed"] == 3
        assert data["total_nodes"] >= 2  # good.md + also_good.txt
        assert len(data["errors"]) == 1
        assert "bad.md" in data["errors"][0]["file"]

    def test_ingest_quiet_error_exits_nonzero(self, temp_project, capsys):
        """--quiet + error → must exit nonzero (catches silent-false-success bug)."""
        from neuralmind.cli import cmd_ingest

        fake_md = temp_project / "fake.md"
        fake_md.write_bytes(b"\x7fELF not markdown")

        args = MagicMock()
        args.file_path = str(fake_md)
        args.type = "auto"
        args.json = False  # No JSON, so --quiet would have hidden the error
        args.project_path = str(temp_project)
        args.dry_run = False
        args.quiet = True
        args.no_recursive = False

        # Must exit non-zero even with --quiet
        with pytest.raises(SystemExit) as exc_info:
            cmd_ingest(args)
        assert exc_info.value.code == 1

    def test_ingest_pdf_requires_pdfplumber(self, temp_project, capsys):
        """PDF ingestion fails gracefully when pdfplumber not installed."""
        from neuralmind.cli import cmd_ingest

        # Create a file with PDF magic bytes
        pdf_file = temp_project / "doc.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake pdf content")

        args = MagicMock()
        args.file_path = str(pdf_file)
        args.type = "auto"
        args.json = True
        args.project_path = str(temp_project)
        args.dry_run = False
        args.quiet = True
        args.no_recursive = False

        # Will fail because pdfplumber is not installed — graceful error
        with pytest.raises(SystemExit):
            cmd_ingest(args)


class TestCLIBenchmark:
    """Tests for CLI benchmark command."""

    def test_cmd_benchmark_outputs_results(self, temp_project, capsys):
        """Test cmd_benchmark outputs benchmark results."""
        from neuralmind.cli import cmd_benchmark, cmd_build

        # Build first
        build_args = MagicMock()
        build_args.project_path = str(temp_project)
        build_args.force = False
        build_args.rebuild_index = False
        cmd_build(build_args)
        capsys.readouterr()  # Clear build output

        args = MagicMock()
        args.project_path = str(temp_project)
        args.json = False

        cmd_benchmark(args)

        captured = capsys.readouterr()
        # Should output benchmark metrics
        assert "Project:" in captured.out
        assert "tokens" in captured.out.lower() or "Wake-up" in captured.out

    def test_cmd_benchmark_json_output(self, temp_project, capsys):
        """Test cmd_benchmark --json produces valid JSON with required keys."""
        from neuralmind.cli import cmd_benchmark, cmd_build

        # Build first
        build_args = MagicMock()
        build_args.project_path = str(temp_project)
        build_args.force = False
        build_args.rebuild_index = False
        cmd_build(build_args)
        capsys.readouterr()  # Clear build output

        args = MagicMock()
        args.project_path = str(temp_project)
        args.json = True

        cmd_benchmark(args)

        captured = capsys.readouterr()
        # Extract JSON from output (may have prefix lines)
        lines = captured.out.split("\n")
        json_start = None
        for i, line in enumerate(lines):
            if line.strip().startswith("{"):
                json_start = i
                break
        assert json_start is not None, f"No JSON found in output: {captured.out}"
        json_text = "\n".join(lines[json_start:])
        data = json.loads(json_text)
        # All required keys per issue #15
        assert "project" in data
        assert "wakeup_tokens" in data
        assert "avg_query_tokens" in data
        assert "avg_reduction_ratio" in data

    def test_cmd_benchmark_reduction_ratio_valid(self, temp_project, capsys):
        """cmd_benchmark's ratio divides by the baseline it names.

        Since v4.5.0 the default baseline is the measured token count of the
        indexed files, which for this stub fixture is a few dozen tokens — so
        the honest ratio is below 1. The pre-v4.5.0 guarantee (> 1.0 against
        the fixed 50K estimate) is checked with --naive-50k below.
        """
        from neuralmind.cli import cmd_benchmark, cmd_build

        # Build first
        build_args = MagicMock()
        build_args.project_path = str(temp_project)
        build_args.force = False
        build_args.rebuild_index = False
        cmd_build(build_args)
        capsys.readouterr()  # Clear build output

        args = MagicMock()
        args.project_path = str(temp_project)
        args.json = True

        cmd_benchmark(args)

        captured = capsys.readouterr()
        # Extract JSON from output (may have prefix lines)
        lines = captured.out.split("\n")
        json_start = None
        for i, line in enumerate(lines):
            if line.strip().startswith("{"):
                json_start = i
                break
        assert json_start is not None, f"No JSON found in output: {captured.out}"
        json_text = "\n".join(lines[json_start:])
        data = json.loads(json_text)
        assert data["baseline"]["source"] == "measured"
        assert data["full_codebase_tokens"] == data["baseline"]["tokens"]
        assert data["avg_reduction_ratio"] == pytest.approx(
            data["baseline"]["tokens"] / data["avg_query_tokens"], abs=0.1
        )
        # The fixed estimate rides along, so older numbers stay comparable —
        # and every question's two ratios come from its own token count.
        assert data["estimated_full_codebase_tokens"] == 50_000
        for r in data["results"]:
            assert r["reduction"] == round(data["full_codebase_tokens"] / r["tokens"], 1)
            assert r["legacy_reduction"] == round(50_000 / r["tokens"], 1)

        args.naive_50k = True
        cmd_benchmark(args)
        out = capsys.readouterr().out
        naive = json.loads(out[out.index("{") :])
        assert naive["baseline"]["source"] == "naive-50k"
        assert naive["avg_reduction_ratio"] > 1.0


class TestCLISkeleton:
    """Tests for CLI skeleton command."""

    def test_cmd_skeleton_outputs_skeleton(self, temp_project, capsys):
        """Test cmd_skeleton outputs skeleton for indexed file."""
        from neuralmind.cli import cmd_build, cmd_skeleton

        # Build first
        build_args = MagicMock()
        build_args.project_path = str(temp_project)
        build_args.force = False
        build_args.rebuild_index = False
        cmd_build(build_args)
        capsys.readouterr()  # Clear build output

        args = MagicMock()
        args.project_path = str(temp_project)
        args.file_path = "auth/handlers.py"  # From sample_graph
        args.json = False

        cmd_skeleton(args)

        captured = capsys.readouterr()
        # Should output skeleton structure
        assert len(captured.out) > 0

    def test_cmd_skeleton_json_output(self, temp_project, capsys):
        """Test cmd_skeleton --json produces valid JSON."""
        from neuralmind.cli import cmd_build, cmd_skeleton

        # Build first
        build_args = MagicMock()
        build_args.project_path = str(temp_project)
        build_args.force = False
        build_args.rebuild_index = False
        cmd_build(build_args)
        capsys.readouterr()  # Clear build output

        args = MagicMock()
        args.project_path = str(temp_project)
        args.file_path = "auth/handlers.py"
        args.json = True

        cmd_skeleton(args)

        captured = capsys.readouterr()
        # Extract JSON from output (may have prefix lines)
        lines = captured.out.split("\n")
        json_start = None
        for i, line in enumerate(lines):
            if line.strip().startswith("{"):
                json_start = i
                break
        assert json_start is not None, f"No JSON found in output: {captured.out}"
        json_text = "\n".join(lines[json_start:])
        data = json.loads(json_text)
        assert "file" in data
        assert "skeleton" in data
        assert "chars" in data

    def test_cmd_skeleton_unindexed_file_fails(self, temp_project, capsys):
        """Test cmd_skeleton fails with exit 1 for unindexed file."""
        from neuralmind.cli import cmd_build, cmd_skeleton

        # Build first
        build_args = MagicMock()
        build_args.project_path = str(temp_project)
        build_args.force = False
        build_args.rebuild_index = False
        cmd_build(build_args)
        capsys.readouterr()  # Clear build output

        args = MagicMock()
        args.project_path = str(temp_project)
        args.file_path = "src/nonexistent/file.py"
        args.json = False

        with pytest.raises(SystemExit) as exc_info:
            cmd_skeleton(args)

        assert exc_info.value.code == 1

        captured = capsys.readouterr()
        assert "No graph nodes found" in captured.out or "not indexed" in captured.out


class TestCLIMain:
    """Tests for CLI main entry point."""

    def test_main_no_command_prints_help(self, capsys):
        """Test main without command shows help."""
        from neuralmind.cli import main

        with patch("sys.argv", ["neuralmind"]):
            with pytest.raises(SystemExit):
                main()

        captured = capsys.readouterr()
        # Should show help text
        assert "usage" in captured.out.lower() or "neuralmind" in captured.out.lower()

    def test_main_with_build_command(self, temp_project, capsys):
        """Test main with build command works end-to-end."""
        from neuralmind.cli import main

        with patch("sys.argv", ["neuralmind", "build", str(temp_project)]):
            main()

        captured = capsys.readouterr()
        assert "Build successful!" in captured.out or "Build" in captured.out

    def test_main_with_stats_command(self, temp_project, capsys):
        """Test main with stats command works end-to-end."""
        from neuralmind.cli import main

        with patch("sys.argv", ["neuralmind", "stats", str(temp_project)]):
            main()

        captured = capsys.readouterr()
        assert "Project:" in captured.out


class TestCLIInstallHooks:
    """Tests for CLI install-hooks command."""

    def test_cmd_install_hooks_project_scope(self, tmp_path, capsys):
        """Test cmd_install_hooks installs hooks for project scope."""
        from neuralmind.cli import cmd_install_hooks

        args = MagicMock()
        args.project_path = str(tmp_path)
        args.global_ = False
        args.uninstall = False

        cmd_install_hooks(args)

        captured = capsys.readouterr()
        assert "✓" in captured.out or "NeuralMind hooks" in captured.out
        assert "installed" in captured.out

    def test_cmd_install_hooks_uninstall(self, tmp_path, capsys):
        """Test cmd_install_hooks --uninstall."""
        from neuralmind.cli import cmd_install_hooks

        # First install
        args = MagicMock()
        args.project_path = str(tmp_path)
        args.global_ = False
        args.uninstall = False
        cmd_install_hooks(args)
        capsys.readouterr()

        # Then uninstall
        args.uninstall = True
        cmd_install_hooks(args)

        captured = capsys.readouterr()
        assert "uninstalled" in captured.out

    def test_cmd_install_hooks_global_scope(self, tmp_path, monkeypatch, capsys):
        """Test cmd_install_hooks --global."""
        from neuralmind.cli import cmd_install_hooks

        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("USERPROFILE", str(tmp_path))

        args = MagicMock()
        args.project_path = str(tmp_path)
        args.global_ = True
        args.uninstall = False

        cmd_install_hooks(args)

        captured = capsys.readouterr()
        assert "installed" in captured.out


class TestCLIHook:
    """Tests for CLI _hook command (internal runtime)."""

    def test_cmd_hook_calls_run_hook(self, monkeypatch):
        """Test cmd_hook delegates to hooks.run_hook."""
        from neuralmind.cli import cmd_hook

        args = MagicMock()
        args.action = "compress-bash"

        with patch("neuralmind.hooks.run_hook", return_value=0) as mock_run:
            with pytest.raises(SystemExit) as exc_info:
                cmd_hook(args)
            assert exc_info.value.code == 0
            mock_run.assert_called_once_with("compress-bash")


class TestCLIInitHook:
    """Tests for CLI init-hook command."""

    def test_cmd_init_hook_creates_hook(self, tmp_path, capsys):
        """Test cmd_init_hook creates a post-commit hook."""
        from neuralmind.cli import cmd_init_hook

        # Create .git/hooks directory
        hooks_dir = tmp_path / ".git" / "hooks"
        hooks_dir.mkdir(parents=True)

        args = MagicMock()
        args.project_path = str(tmp_path)

        cmd_init_hook(args)

        captured = capsys.readouterr()
        assert "✓" in captured.out or "post-commit hook" in captured.out

        hook_path = hooks_dir / "post-commit"
        assert hook_path.exists()
        content = hook_path.read_text()
        assert "neuralmind-hook-start" in content
        assert '"$_nm_bin" build .' in content

    def test_cmd_init_hook_idempotent(self, tmp_path, capsys):
        """Running init-hook twice updates the block without duplicating."""
        from neuralmind.cli import cmd_init_hook

        hooks_dir = tmp_path / ".git" / "hooks"
        hooks_dir.mkdir(parents=True)

        args = MagicMock()
        args.project_path = str(tmp_path)

        cmd_init_hook(args)
        capsys.readouterr()
        cmd_init_hook(args)

        hook_path = hooks_dir / "post-commit"
        content = hook_path.read_text()
        # Should only have one copy of the block
        assert content.count("neuralmind-hook-start") == 1
        assert content.count("neuralmind-hook-end") == 1

    def test_cmd_init_hook_preserves_existing(self, tmp_path, capsys):
        """init-hook appends to an existing post-commit hook."""
        from neuralmind.cli import cmd_init_hook

        hooks_dir = tmp_path / ".git" / "hooks"
        hooks_dir.mkdir(parents=True)
        hook_path = hooks_dir / "post-commit"
        hook_path.write_text("#!/bin/sh\necho 'existing hook'\n")

        args = MagicMock()
        args.project_path = str(tmp_path)

        cmd_init_hook(args)

        content = hook_path.read_text()
        assert "existing hook" in content
        assert "neuralmind-hook-start" in content

    def test_cmd_init_hook_no_git_dir(self, tmp_path, capsys):
        """init-hook exits 1 when no .git/hooks directory."""
        from neuralmind.cli import cmd_init_hook

        args = MagicMock()
        args.project_path = str(tmp_path)

        with pytest.raises(SystemExit) as exc_info:
            cmd_init_hook(args)
        assert exc_info.value.code == 1

    @pytest.mark.skipif(sys.platform.startswith("win"), reason="Windows has no executable bit")
    def test_cmd_init_hook_makes_executable(self, tmp_path):
        """init-hook makes the hook file executable."""
        import os
        import stat

        from neuralmind.cli import cmd_init_hook

        hooks_dir = tmp_path / ".git" / "hooks"
        hooks_dir.mkdir(parents=True)

        args = MagicMock()
        args.project_path = str(tmp_path)

        cmd_init_hook(args)

        hook_path = hooks_dir / "post-commit"
        mode = os.stat(hook_path).st_mode
        assert mode & stat.S_IXUSR  # User execute bit set


class TestCLIBuildDryRun:
    """Tests for neuralmind build --dry-run (Gap 1: 1-click setup)."""

    def test_dry_run_scans_project_without_building(self, tmp_path, capsys):
        """--dry-run must report language/file counts without building an index."""
        from neuralmind.cli import cmd_build

        (tmp_path / "auth.py").write_text("def login(): pass")
        (tmp_path / "server.ts").write_text("const port = 3000;")

        args = MagicMock()
        args.project_path = str(tmp_path)
        args.force = False
        args.rebuild_index = False
        args.dry_run = True
        args.json = False

        cmd_build(args)

        captured = capsys.readouterr()
        assert "dry run" in captured.out.lower()
        assert "neuralmind build" in captured.out
        assert "No index was built" in captured.out

    def test_dry_run_json_output(self, tmp_path, capsys):
        """--dry-run --json returns structured scan data."""
        from neuralmind.cli import cmd_build

        (tmp_path / "main.py").write_text("# code\n" * 50)

        args = MagicMock()
        args.project_path = str(tmp_path)
        args.force = False
        args.rebuild_index = False
        args.dry_run = True
        args.json = True

        cmd_build(args)

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "total_files" in data
        assert "languages" in data
        assert "est_reduction_ratio" in data
        assert data["total_files"] >= 1

    def test_dry_run_requires_existing_path(self, capsys):
        """--dry-run on a non-existent path must exit non-zero."""
        from neuralmind.cli import cmd_build

        args = MagicMock()
        args.project_path = "/totally/nonexistent/path/12345"
        args.force = False
        args.rebuild_index = False
        args.dry_run = True
        args.json = False

        with pytest.raises(SystemExit):
            cmd_build(args)


class TestCLISavings:
    """Tests for neuralmind savings (Gap 5: per-query token savings dashboard)."""

    def test_savings_no_log_prints_message(self, tmp_path, capsys):
        """savings command gracefully handles a missing event log."""
        from neuralmind.cli import cmd_savings

        args = MagicMock()
        args.project_path = str(tmp_path)
        args.global_ = False
        args.json = False
        args.cost = False

        cmd_savings(args)

        captured = capsys.readouterr()
        assert "no" in captured.out.lower() or "not" in captured.out.lower()

    def test_savings_reads_event_log(self, tmp_path, capsys):
        """savings command reads the project event log and computes totals."""
        import json as _json

        from neuralmind import memory
        from neuralmind.cli import cmd_savings

        # Write a fake event log
        log_file = memory.project_query_events_file(tmp_path)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        events = [
            {
                "event_type": "query",
                "timestamp": "2025-01-01T00:00:00+00:00",
                "project_path": str(tmp_path),
                "session_id": "test-session",
                "query": "auth flow",
                "retrieval_summary": {
                    "tokens": 1200,
                    "reduction_ratio": 41.6,
                    "layers_used": ["L0", "L1", "L2"],
                    "communities_loaded": [0],
                    "search_hits": 4,
                },
            },
            {
                "event_type": "query",
                "timestamp": "2025-01-01T00:01:00+00:00",
                "project_path": str(tmp_path),
                "session_id": "test-session",
                "query": "database schema",
                "retrieval_summary": {
                    "tokens": 1800,
                    "reduction_ratio": 27.8,
                    "layers_used": ["L0", "L1", "L2", "L3"],
                    "communities_loaded": [1, 2],
                    "search_hits": 3,
                },
            },
        ]
        with log_file.open("w") as f:
            for e in events:
                f.write(_json.dumps(e) + "\n")

        args = MagicMock()
        args.project_path = str(tmp_path)
        args.global_ = False
        args.json = False
        args.cost = False

        cmd_savings(args)

        captured = capsys.readouterr()
        assert "Queries logged" in captured.out
        assert "2" in captured.out  # 2 queries
        assert "Tokens saved" in captured.out or "saved" in captured.out.lower()

    def test_savings_json_output(self, tmp_path, capsys):
        """savings --json returns structured data."""
        import json as _json

        from neuralmind import memory
        from neuralmind.cli import cmd_savings

        log_file = memory.project_query_events_file(tmp_path)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        event = {
            "event_type": "query",
            "timestamp": "2025-01-01T00:00:00+00:00",
            "project_path": str(tmp_path),
            "session_id": "s1",
            "query": "test",
            "retrieval_summary": {"tokens": 500, "reduction_ratio": 100.0},
        }
        log_file.write_text(_json.dumps(event) + "\n")

        args = MagicMock()
        args.project_path = str(tmp_path)
        args.global_ = False
        args.json = True
        args.cost = False

        cmd_savings(args)

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["total_queries"] == 1
        assert data["total_tokens_saved"] > 0
        assert "dollar_savings" not in data

    def test_savings_cost_json_math(self, tmp_path, capsys):
        """savings --cost --json reports dollar figures from the plain totals.

        One event with 500 tokens used against the 50,000-token baseline at
        claude-opus-4-8 input pricing ($5/MTok): the totals must come straight
        from the token totals (no re-scaling by event count), and the
        projection from the per-event average times queries/day.
        """
        import json as _json

        from neuralmind import memory
        from neuralmind.cli import cmd_savings

        log_file = memory.project_query_events_file(tmp_path)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        event = {
            "event_type": "query",
            "timestamp": "2025-01-01T00:00:00+00:00",
            "project_path": str(tmp_path),
            "session_id": "s1",
            "query": "test",
            "retrieval_summary": {"tokens": 500, "reduction_ratio": 100.0},
        }
        log_file.write_text(_json.dumps(event) + "\n")

        args = MagicMock()
        args.project_path = str(tmp_path)
        args.global_ = False
        args.json = True
        args.cost = True
        args.model = "claude-opus-4-8"
        args.queries_per_day = 100

        cmd_savings(args)

        data = json.loads(capsys.readouterr().out)
        ds = data["dollar_savings"]
        assert ds["model"] == "claude-opus-4-8"
        assert ds["price_per_mtok"] == 5.00
        assert ds["baseline_cost_total"] == 0.25  # 50,000 tok * $5/MTok
        assert ds["actual_cost_total"] == 0.0025  # 500 tok * $5/MTok
        assert ds["saved_total"] == 0.2475
        assert ds["daily_saved"] == 24.75  # 49,500 tok/event * 100/day * $5/MTok
        assert ds["monthly_saved"] == 742.5

    def test_savings_cost_surfaces_estimate_basis(self, tmp_path, capsys):
        """--cost --json marks the dollar figures as estimated and shows the basis."""
        import json as _json

        from neuralmind import memory
        from neuralmind.cli import cmd_savings

        log_file = memory.project_query_events_file(tmp_path)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        event = {
            "event_type": "query",
            "timestamp": "2026-01-01T00:00:00+00:00",
            "project_path": str(tmp_path),
            "session_id": "s1",
            "query": "test",
            "retrieval_summary": {"tokens": 500, "reduction_ratio": 100.0},
        }
        log_file.write_text(_json.dumps(event) + "\n")

        args = MagicMock()
        args.project_path = str(tmp_path)
        args.global_ = False
        args.json = True
        args.cost = True
        args.model = "claude-opus-4-8"
        args.queries_per_day = 100

        cmd_savings(args)
        ds = json.loads(capsys.readouterr().out)["dollar_savings"]
        # the measured cost is still present, now flagged as an estimate basis
        assert ds["actual_cost_total"] == 0.0025  # measured: 500 tok * $5/MTok
        assert ds["estimated"] is True
        assert ds["baseline_tokens_per_query"] == 50_000
        assert "basis" in ds and "estimated" in ds["basis"]

    def test_savings_cost_text_output(self, tmp_path, capsys):
        """savings --cost adds a dollar-savings block to the text report."""
        import json as _json

        from neuralmind import memory
        from neuralmind.cli import cmd_savings

        log_file = memory.project_query_events_file(tmp_path)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        event = {
            "event_type": "query",
            "timestamp": "2025-01-01T00:00:00+00:00",
            "project_path": str(tmp_path),
            "session_id": "s1",
            "query": "test",
            "retrieval_summary": {"tokens": 500, "reduction_ratio": 100.0},
        }
        log_file.write_text(_json.dumps(event) + "\n")

        args = MagicMock()
        args.project_path = str(tmp_path)
        args.global_ = False
        args.json = False
        args.cost = True
        args.model = None  # falls back to the default pricing model
        args.queries_per_day = 100

        cmd_savings(args)

        out = capsys.readouterr().out
        assert "Dollar savings" in out
        assert "/month" in out
        assert "claude-opus-4-8" in out

    def test_savings_cost_projection_not_diluted_by_wakeups(self, tmp_path, capsys):
        """A log mixing queries and wakeups projects off the query average only.

        Regression guard (PR #353 review): a wakeup event logs ~0 tokens
        saved, so if the projection's per-event average includes wakeups
        alongside queries, --queries-per-day (a *query* volume assumption)
        understates the true daily figure. One query saving 45,000 tokens
        plus four wakeup events (near-zero savings each) must project the
        same $/day as that one query alone would.
        """
        import json as _json

        from neuralmind import memory
        from neuralmind.cli import cmd_savings

        log_file = memory.project_query_events_file(tmp_path)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            _json.dumps(
                {
                    "event_type": "query",
                    "timestamp": "2025-01-01T00:00:00+00:00",
                    "project_path": str(tmp_path),
                    "session_id": "s1",
                    "query": "test",
                    "retrieval_summary": {"tokens": 5_000, "reduction_ratio": 6.0},
                }
            )
        ]
        for _ in range(4):
            lines.append(
                _json.dumps(
                    {
                        "event_type": "wakeup",
                        "timestamp": "2025-01-01T00:00:00+00:00",
                        "project_path": str(tmp_path),
                        "session_id": "s1",
                        "retrieval_summary": {"tokens": 49_900, "reduction_ratio": 1.0},
                    }
                )
            )
        log_file.write_text("\n".join(lines) + "\n")

        args = MagicMock()
        args.project_path = str(tmp_path)
        args.global_ = False
        args.json = True
        args.cost = True
        args.model = "claude-opus-4-8"  # $5/MTok
        args.queries_per_day = 100

        cmd_savings(args)

        data = json.loads(capsys.readouterr().out)
        ds = data["dollar_savings"]
        # Query alone: 50,000 baseline - 5,000 used = 45,000 saved ->
        # 45,000 * 100 / 1_000_000 * $5 = $22.50/day. If wakeups diluted the
        # average (dividing by 5 events instead of 1 query), this would come
        # out far lower.
        assert ds["daily_saved"] == 22.5


class TestCLIReview:
    """Tests for neuralmind review (Gap 4: diff-aware co-break warnings)."""

    def test_review_no_changes_message(self, tmp_path, capsys):
        """review with no git changes reports nothing to review."""
        import subprocess

        from neuralmind.cli import cmd_review

        # Init a bare git repo with no commits so diff against HEAD fails
        subprocess.run(["git", "init", str(tmp_path)], capture_output=True)
        subprocess.run(
            ["git", "-C", str(tmp_path), "config", "user.email", "test@test.com"],
            capture_output=True,
        )
        subprocess.run(
            ["git", "-C", str(tmp_path), "config", "user.name", "Test"],
            capture_output=True,
        )

        args = MagicMock()
        args.project_path = str(tmp_path)
        args.base = "HEAD"
        args.top_k = 10
        args.json = False

        # Should not crash — no changed files, no synapse graph
        with patch("neuralmind.cli.create_mind") as mock_create:
            mock_create.return_value.synapses = None
            mock_create.return_value.embedder.get_file_nodes.return_value = []
            # Will either print "no changed files" or handle gracefully
            try:
                cmd_review(args)
            except SystemExit:
                pass


class TestCLIDemo:
    """Tests for CLI demo command (bundled sample_project + graph.json)."""

    def test_demo_data_bundled_with_package(self):
        """The bundled fixture and pre-built graph.json must ship inside the
        package — the whole point of `neuralmind demo` is that it works
        right after `pip install neuralmind`, no git checkout needed."""
        from importlib import resources

        bundle = resources.files("neuralmind") / "demo_data" / "sample_project"
        assert (bundle / ".neuralmind" / "graph.json").is_file()
        assert (bundle / "auth" / "handlers.py").is_file()
        assert (bundle / "billing" / "invoices.py").is_file()

    @staticmethod
    def _aged_bundle(tmp_path):
        """A copy of the bundled fixture whose graph.json predates its sources.

        That's the shape an installed wheel can have: each file keeps its own
        mtime, and nothing orders the graph after the code it describes.
        """
        import shutil
        from importlib import resources

        with resources.as_file(resources.files("neuralmind") / "demo_data") as src:
            demo_data = tmp_path / "pkg" / "neuralmind" / "demo_data"
            shutil.copytree(src, demo_data)
        bundle = demo_data / "sample_project"
        for path in bundle.rglob("*"):
            if path.is_file():
                os.utime(path, (1_600_000_000, 1_600_000_000))  # 2020-09
        graph = bundle / ".neuralmind" / "graph.json"
        os.utime(graph, (1_500_000_000, 1_500_000_000))  # 2017-07: older than the code
        return bundle

    def test_demo_copy_is_not_stale(self, tmp_path):
        """`neuralmind demo` reported "N files changed since the graph was
        built" on every run: copytree kept the bundle's mtimes, and the
        freshness check compares source mtimes with graph.json's."""
        from neuralmind.cli import _copy_demo_fixture
        from neuralmind.freshness import OK, graph_freshness

        bundle = self._aged_bundle(tmp_path)
        work = tmp_path / "work" / "sample_project"
        _copy_demo_fixture(bundle, work)

        report = graph_freshness(work)
        assert report is not None
        assert report.changed_since_graph == []
        assert report.status == OK, report.render(str(work))
        # The copy is a byte-for-byte working copy of the bundle.
        assert (work / ".neuralmind" / "graph.json").read_bytes() == (
            bundle / ".neuralmind" / "graph.json"
        ).read_bytes()

    def test_cmd_demo_does_not_report_stale_files(self, tmp_path, monkeypatch, capsys):
        """End to end: a bundle with an old graph mtime still demos clean."""
        from importlib import resources

        from neuralmind.cli import cmd_demo

        bundle = self._aged_bundle(tmp_path)
        pkg_root = bundle.parent.parent  # .../pkg/neuralmind
        monkeypatch.setattr(resources, "files", lambda _pkg: pkg_root)

        args = MagicMock()
        args.keep = False
        args.quiet = False
        cmd_demo(args)

        captured = capsys.readouterr()
        assert "NeuralMind 30-second demo" in captured.out
        assert "changed since the graph" not in captured.out + captured.err

    def test_cmd_demo_runs_end_to_end(self, capsys):
        """Smoke test: demo subcommand copies the bundled fixture, builds
        the index, runs three queries, and prints the report banner."""
        from neuralmind.cli import cmd_demo

        args = MagicMock()
        args.keep = False
        args.quiet = True

        cmd_demo(args)

        captured = capsys.readouterr()
        assert "NeuralMind 30-second demo" in captured.out
        assert "Average reduction:" in captured.out
        # All three demo queries should appear in the output
        assert "How does authentication work" in captured.out
        assert "API endpoints" in captured.out
        assert "billing flow" in captured.out


class TestCLIDemoOffline:
    """`neuralmind demo` right after `pip install`, with no network.

    It used to download the 88 MB embedding model on first run, and crash with
    a traceback offline. It now ships the sample project's vector index and
    the vectors of its three questions (demo_data/prebuilt/, made by
    scripts/build_demo_index.py), and ranks exactly as the model would.
    """

    @staticmethod
    def _no_model(monkeypatch):
        """No model on disk, and no network: a download attempt fails, as offline."""
        from neuralmind.onnx_embedder import OnnxMiniLMEmbedder

        def no_download(self, dest):
            raise OSError("no network in this test")

        monkeypatch.setattr(OnnxMiniLMEmbedder, "local_model_dir", lambda self: None)
        monkeypatch.setattr(OnnxMiniLMEmbedder, "_download_into", no_download)

    @staticmethod
    def _prebuilt():
        from importlib import resources

        return resources.files("neuralmind") / "demo_data" / "prebuilt"

    def test_the_demo_runs_without_the_model_or_a_download(self, monkeypatch, capsys):
        from neuralmind.cli import cmd_demo

        self._no_model(monkeypatch)
        args = MagicMock()
        args.keep = False
        args.quiet = False
        cmd_demo(args)

        out = capsys.readouterr().out
        assert "bundled with NeuralMind, so nothing is downloaded" in out
        assert "Average reduction:" in out
        assert out.count("reduction =") == 3

    def test_the_bundled_vectors_are_the_demo_questions(self):
        from neuralmind import _demo_report

        data = json.loads((self._prebuilt() / "query_vectors.json").read_text(encoding="utf-8"))
        assert data["model"] == "all-MiniLM-L6-v2"
        assert set(data["vectors"]) == {q for _, q in _demo_report.DEMO_QUERIES}
        assert all(len(v) == 384 for v in data["vectors"].values())

    def test_the_bundled_index_covers_every_node(self, tmp_path, monkeypatch):
        """Every node the build indexes is already in the bundled store with
        the same content hash, so the build embeds nothing: if the sample
        project or its graph changes, this fails until the index is rebuilt."""
        import shutil
        from importlib import resources

        from neuralmind import _demo_report
        from neuralmind.cli import _copy_demo_fixture
        from neuralmind.core import NeuralMind
        from neuralmind.turbovec_backend import embed_fn_override

        self._no_model(monkeypatch)
        work = tmp_path / "sample_project"
        with resources.as_file(resources.files("neuralmind") / "demo_data") as demo_data:
            _copy_demo_fixture(Path(demo_data) / "sample_project", work)
            shutil.copytree(
                Path(demo_data) / "prebuilt" / "neuralmind_turbovec",
                work / ".neuralmind" / "neuralmind_turbovec",
            )
            embedder = _demo_report.BundledQueryEmbedder(
                Path(demo_data) / "prebuilt" / "query_vectors.json"
            )
        with embed_fn_override(embedder):
            result = NeuralMind(str(work)).build()
        assert result.get("success"), result.get("error")

    def test_the_bundled_embedder_refuses_other_text(self):
        from importlib import resources

        from neuralmind import _demo_report

        with resources.as_file(self._prebuilt()) as prebuilt:
            embedder = _demo_report.BundledQueryEmbedder(Path(prebuilt) / "query_vectors.json")
        question = _demo_report.DEMO_QUERIES[0][1]
        assert len(embedder([question])[0]) == 384
        with pytest.raises(_demo_report.DemoIndexStaleError):
            embedder(["How does logging work?"])

    @staticmethod
    def _stale_bundle(tmp_path, monkeypatch):
        """Package data whose question vectors don't cover the demo's questions."""
        import shutil
        from importlib import resources

        with resources.as_file(resources.files("neuralmind") / "demo_data") as src:
            demo_data = tmp_path / "pkg" / "neuralmind" / "demo_data"
            shutil.copytree(src, demo_data)
        vectors = demo_data / "prebuilt" / "query_vectors.json"
        data = json.loads(vectors.read_text(encoding="utf-8"))
        data["vectors"] = {"another question": next(iter(data["vectors"].values()))}
        vectors.write_text(json.dumps(data), encoding="utf-8")
        monkeypatch.setattr(resources, "files", lambda _pkg: demo_data.parent)

    def test_an_unusable_bundle_offline_fails_with_a_message_not_a_traceback(
        self, tmp_path, monkeypatch, capsys
    ):
        from neuralmind.cli import cmd_demo

        self._no_model(monkeypatch)
        self._stale_bundle(tmp_path, monkeypatch)
        args = MagicMock()
        args.keep = False
        args.quiet = True
        with pytest.raises(SystemExit) as exc:
            cmd_demo(args)
        assert exc.value.code == 1
        err = capsys.readouterr().err
        assert "building it with the embedding model instead" in err
        assert "the embedding model couldn't be downloaded (no network in this test)" in err

    def test_an_unusable_bundle_falls_back_to_the_model(self, tmp_path, monkeypatch, capsys):
        """Online, a bundle this install can't use (an older turbovec that can't
        read the index rebuilds it, which needs every node embedded) falls back
        to building with the model, as the demo did before it was bundled."""
        import hashlib

        from neuralmind.cli import cmd_demo
        from neuralmind.onnx_embedder import OnnxMiniLMEmbedder

        def fake_model(self, texts):
            # Stands in for the downloaded model: deterministic 384-d vectors.
            vectors = []
            for text in texts:
                digest = hashlib.sha256(text.encode()).digest()
                vectors.append([b / 255.0 for b in (digest * 12)[:384]])
            return vectors

        self._no_model(monkeypatch)
        self._stale_bundle(tmp_path, monkeypatch)
        monkeypatch.setattr(OnnxMiniLMEmbedder, "__call__", fake_model)
        monkeypatch.setattr(OnnxMiniLMEmbedder, "embed", fake_model)
        args = MagicMock()
        args.keep = False
        args.quiet = True
        cmd_demo(args)

        captured = capsys.readouterr()
        assert "building it with the embedding model instead" in captured.err
        assert captured.out.count("reduction =") == 3

    def test_the_bundled_index_loads_with_the_installed_turbovec(self, tmp_path):
        """The shipped index.tvim reads with this turbovec, holds a vector for
        every stored node, and isn't quarantined (which would need the model)."""
        import shutil
        from importlib import resources

        from neuralmind.cli import _copy_demo_fixture
        from neuralmind.turbovec_backend import TurboVecEmbedder

        work = tmp_path / "sample_project"
        with resources.as_file(resources.files("neuralmind") / "demo_data") as demo_data:
            _copy_demo_fixture(Path(demo_data) / "sample_project", work)
            shutil.copytree(
                Path(demo_data) / "prebuilt" / "neuralmind_turbovec",
                work / ".neuralmind" / "neuralmind_turbovec",
            )
        backend = TurboVecEmbedder(str(work))
        index = backend._load_index()
        assert index is not None
        assert not list((work / ".neuralmind" / "neuralmind_turbovec").glob("*.stale"))
        stored = backend._conn.execute("SELECT COUNT(*) AS c FROM nodes").fetchone()["c"]
        assert len(index) == stored

    def test_the_bundled_vectors_match_the_model(self):
        """Where the model is on disk: the shipped vectors are the model's."""
        from neuralmind import _demo_report
        from neuralmind.onnx_embedder import OnnxMiniLMEmbedder

        model = OnnxMiniLMEmbedder()
        if model.local_model_dir() is None:
            pytest.skip("needs the embedding model on disk; checked in ci-benchmark.yml")
        from importlib import resources

        with resources.as_file(self._prebuilt()) as prebuilt:
            bundled = _demo_report.BundledQueryEmbedder(Path(prebuilt) / "query_vectors.json")
        questions = [q for _, q in _demo_report.DEMO_QUERIES]
        for got, want in zip(bundled(questions), model(questions), strict=True):
            assert max(abs(a - b) for a, b in zip(got, want, strict=True)) < 1e-4


class TestCLIDemoWithoutTurbovec:
    """`neuralmind demo` where turbovec has no wheel (Intel macOS, Windows ARM).

    pyproject installs ChromaDB there instead, and the bundled index is a
    turbovec index, so the demo used to die with `ModuleNotFoundError: No
    module named 'turbovec'` from deep in the build. It now builds the sample
    project with ChromaDB, or exits 1 with one line when that's missing too.
    """

    @staticmethod
    def _no_turbovec(monkeypatch, *, chromadb: bool):
        import importlib.util

        from neuralmind import backend_manager

        real_find_spec = importlib.util.find_spec

        def find_spec(name, *a, **kw):
            if name.split(".")[0] == "turbovec":
                return None
            if name.split(".")[0] == "chromadb" and not chromadb:
                return None
            if name.split(".")[0] == "chromadb":
                return real_find_spec("json")  # any spec: "importable"
            return real_find_spec(name, *a, **kw)

        monkeypatch.setattr(importlib.util, "find_spec", find_spec)
        assert not backend_manager.turbovec_available()

    @staticmethod
    def _args():
        args = MagicMock()
        args.keep = False
        args.quiet = True
        return args

    def test_without_turbovec_or_chromadb_it_exits_1_with_one_line(self, monkeypatch, capsys):
        from neuralmind.cli import cmd_demo

        self._no_turbovec(monkeypatch, chromadb=False)
        with pytest.raises(SystemExit) as exc:
            cmd_demo(self._args())
        assert exc.value.code == 1
        err = capsys.readouterr().err
        assert err.count("\n") == 1
        assert "turbovec ships only for Linux, Apple Silicon macOS and 64-bit Windows" in err
        assert 'pip install "neuralmind[chromadb]"' in err
        assert "Traceback" not in err

    def test_without_turbovec_it_builds_with_chromadb(self, monkeypatch, capsys):
        from neuralmind import backend_manager
        from neuralmind.cli import cmd_demo
        from neuralmind.in_memory_backend import InMemoryEmbeddingBackend

        self._no_turbovec(monkeypatch, chromadb=True)
        backends = []
        real_create = backend_manager.create_backend

        def create_backend(backend, project_path, db_path=None, scope="all"):
            backends.append(backend)
            if backend in backend_manager.CHROMA_BACKENDS:
                # Stands in for ChromaDB and its model download.
                return InMemoryEmbeddingBackend(project_path, db_path=db_path)
            return real_create(backend, project_path, db_path, scope=scope)

        monkeypatch.setattr(backend_manager, "create_backend", create_backend)
        cmd_demo(self._args())

        captured = capsys.readouterr()
        assert backends and set(backends) == {"chroma"}
        assert "building the sample project with ChromaDB instead" in captured.err
        assert "Traceback" not in captured.err
        assert captured.out.count("reduction =") == 3

    def test_turbovec_without_the_model_stack_still_uses_the_bundle(self, monkeypatch, capsys):
        """The bundled question vectors replace the model, so a turbovec install
        missing onnxruntime or tokenizers still runs the demo from the bundle."""
        import importlib.util

        from neuralmind.cli import cmd_demo

        pytest.importorskip("turbovec")
        TestCLIDemoOffline._no_model(monkeypatch)
        real_find_spec = importlib.util.find_spec

        def find_spec(name, *a, **kw):
            if name.split(".")[0] in {"onnxruntime", "tokenizers"}:
                return None
            return real_find_spec(name, *a, **kw)

        monkeypatch.setattr(importlib.util, "find_spec", find_spec)
        args = self._args()
        args.quiet = False
        cmd_demo(args)

        captured = capsys.readouterr()
        assert "bundled with NeuralMind, so nothing is downloaded" in captured.out
        assert "ChromaDB" not in captured.err
        assert captured.out.count("reduction =") == 3

    def test_a_failing_chromadb_build_exits_1_with_one_line(self, monkeypatch, capsys):
        from neuralmind import backend_manager
        from neuralmind.cli import cmd_demo

        self._no_turbovec(monkeypatch, chromadb=True)

        def create_backend(backend, project_path, db_path=None, scope="all"):
            raise ConnectionError("no network in this test")

        monkeypatch.setattr(backend_manager, "create_backend", create_backend)
        with pytest.raises(SystemExit) as exc:
            cmd_demo(self._args())
        assert exc.value.code == 1
        err = capsys.readouterr().err
        assert "building the sample project with ChromaDB failed (no network in this test)" in err
        assert "Traceback" not in err


class TestCmdScanForSecrets:
    """The exit-code contract is a CI gate, so it needs CLI-level cover.

    The engine has unit tests, but nothing invoked the subcommand itself —
    so a regression in argument wiring or exit codes could silently make the
    gate pass, or change the machine-readable output, without a test
    noticing.
    """

    @staticmethod
    def _args(path, **overrides):
        from argparse import Namespace

        base = {
            "project_path": str(path),
            "high_confidence_only": False,
            "strict": False,
            "use_neuralmindignore": False,
            "json": False,
        }
        base.update(overrides)
        return Namespace(**base)

    @staticmethod
    def _run(args):
        """Invoke the handler, returning its exit code (0 when it returns)."""
        from neuralmind.cli import cmd_scan_for_secrets

        try:
            cmd_scan_for_secrets(args)
        except SystemExit as exc:  # noqa: PT012 - the exit code is the contract
            return exc.code
        return 0

    def test_clean_project_exits_zero(self, tmp_path):
        (tmp_path / "main.py").write_text("def main():\n    return 0\n")
        assert self._run(self._args(tmp_path)) == 0

    def test_high_confidence_finding_exits_one(self, tmp_path):
        (tmp_path / ".env").write_text("AWS_ACCESS_KEY_ID=AKIA" + "IOSFODNN7EXAMPLE\n")
        assert self._run(self._args(tmp_path)) == 1

    def test_heuristic_only_exits_zero_by_default(self, tmp_path):
        (tmp_path / "conf.py").write_text('client_secret = "9f8Kd2mQxZ7pLw3RtY6vNbHj4sA1"\n')
        assert self._run(self._args(tmp_path)) == 0

    def test_heuristic_only_exits_one_under_strict(self, tmp_path):
        (tmp_path / "conf.py").write_text('client_secret = "9f8Kd2mQxZ7pLw3RtY6vNbHj4sA1"\n')
        assert self._run(self._args(tmp_path, strict=True)) == 1

    def test_missing_path_exits_two(self, tmp_path):
        assert self._run(self._args(tmp_path / "nope")) == 2

    def test_high_confidence_only_suppresses_the_heuristic_tier(self, tmp_path, capsys):
        (tmp_path / "conf.py").write_text('client_secret = "9f8Kd2mQxZ7pLw3RtY6vNbHj4sA1"\n')
        code = self._run(self._args(tmp_path, high_confidence_only=True, json=True))
        payload = json.loads(capsys.readouterr().out)
        assert code == 0
        assert payload["findings"] == []
        assert payload["heuristic"] == 0

    def test_json_output_shape(self, tmp_path, capsys):
        (tmp_path / ".env").write_text("AWS_ACCESS_KEY_ID=AKIA" + "IOSFODNN7EXAMPLE\n")
        self._run(self._args(tmp_path, json=True))
        payload = json.loads(capsys.readouterr().out)

        assert payload["high_confidence"] == 1
        assert payload["project"] == str(tmp_path.resolve())
        finding = payload["findings"][0]
        assert finding["path"] == ".env"
        assert finding["line"] == 1
        assert finding["kind"] == "aws-access-key-id"
        assert finding["confidence"] == "high"

    def test_preview_never_carries_the_whole_secret(self, tmp_path, capsys):
        secret = "AKIA" + "IOSFODNN7EXAMPLE"
        (tmp_path / ".env").write_text(f"AWS_ACCESS_KEY_ID={secret}\n")
        self._run(self._args(tmp_path, json=True))
        out = capsys.readouterr().out
        assert secret not in out, "the scanner printed a full credential"

    def test_neuralmindignore_is_ignored_by_default(self, tmp_path):
        """The retrieval ignore file must not silence the scanner unasked."""
        (tmp_path / ".neuralmindignore").write_text("secrets/\n")
        (tmp_path / "secrets").mkdir()
        (tmp_path / "secrets" / "k.env").write_text("AWS_ACCESS_KEY_ID=AKIA" + "IOSFODNN7EXAMPLE\n")

        assert self._run(self._args(tmp_path)) == 1
        assert self._run(self._args(tmp_path, use_neuralmindignore=True)) == 0
