"""Tests for NeuralMind CLI functionality with real assertions."""

import json
import sys
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
        """Test cmd_benchmark reports valid reduction ratios > 1.0."""
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
        assert data["avg_reduction_ratio"] > 1.0


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
        assert "neuralmind build" in content

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
        assert (bundle / "graphify-out" / "graph.json").is_file()
        assert (bundle / "auth" / "handlers.py").is_file()
        assert (bundle / "billing" / "invoices.py").is_file()

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
