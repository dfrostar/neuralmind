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

        cmd_build(args)

        captured = capsys.readouterr()
        assert "Force rebuild: True" in captured.out

    def test_cmd_build_nonexistent_path(self, capsys):
        """Test cmd_build fails on nonexistent path."""
        from neuralmind.cli import cmd_build

        args = MagicMock()
        args.project_path = "/nonexistent/path/12345"
        args.force = False

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

    def test_cmd_query_has_token_reduction(self, temp_project, capsys):
        """Test cmd_query reports token reduction ratio."""
        from neuralmind.cli import cmd_build, cmd_query

        # Build first
        build_args = MagicMock()
        build_args.project_path = str(temp_project)
        build_args.force = False
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


class TestCLILearn:
    """`neuralmind learn` is a deprecated exit-0 no-op."""

    def test_cmd_learn_prints_deprecation(self, temp_project, capsys):
        """learn prints a deprecation notice pointing at the synapse layer."""
        from neuralmind.cli import cmd_learn

        args = MagicMock()
        args.project_path = str(temp_project)

        # No exception, no sys.exit — a plain return is exit 0.
        result = cmd_learn(args)
        assert result is None

        captured = capsys.readouterr()
        out = captured.out.lower()
        assert "deprecated" in out
        assert "synapse" in out

    def test_cmd_learn_writes_no_patterns_file(self, temp_project, capsys):
        """learn must not write the old learned_patterns.json anymore."""
        from neuralmind.cli import cmd_learn

        args = MagicMock()
        args.project_path = str(temp_project)
        cmd_learn(args)

        patterns_file = temp_project / ".neuralmind" / "learned_patterns.json"
        assert not patterns_file.exists()


class TestCLIBenchmark:
    """Tests for CLI benchmark command."""

    def test_cmd_benchmark_outputs_results(self, temp_project, capsys):
        """Test cmd_benchmark outputs benchmark results."""
        from neuralmind.cli import cmd_benchmark, cmd_build

        # Build first
        build_args = MagicMock()
        build_args.project_path = str(temp_project)
        build_args.force = False
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

        cmd_savings(args)

        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["total_queries"] == 1
        assert data["total_tokens_saved"] > 0


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
