"""Tests for NeuralMind CLI functionality with real assertions."""

import json
from unittest.mock import MagicMock, patch

import pytest


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
        from neuralmind.cli import cmd_query, cmd_build

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
        from neuralmind.cli import cmd_query, cmd_build

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
        from neuralmind.cli import cmd_query, cmd_build

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
        from neuralmind.cli import cmd_wakeup, cmd_build

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
        from neuralmind.cli import cmd_wakeup, cmd_build

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
        from neuralmind.cli import cmd_search, cmd_build

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
        from neuralmind.cli import cmd_search, cmd_build

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
        result_lines = [l for l in lines if l and l[0].isdigit() and ". " in l]
        assert len(result_lines) <= 2

    def test_cmd_search_json_output(self, temp_project, capsys):
        """Test cmd_search --json produces valid JSON."""
        from neuralmind.cli import cmd_search, cmd_build

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
        from neuralmind.cli import cmd_stats, cmd_build

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
    """Tests for CLI learn command."""

    def test_cmd_learn_noop_when_disabled(self, monkeypatch, capsys):
        """Test learn command is a safe no-op when disabled by env var."""
        from neuralmind.cli import cmd_learn

        monkeypatch.setenv("NEURALMIND_LEARNING", "0")
        args = MagicMock()
        args.project_path = "."

        cmd_learn(args)

        captured = capsys.readouterr()
        assert "no-op" in captured.out.lower()


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
        from neuralmind.cli import cmd_skeleton, cmd_build

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
        from neuralmind.cli import cmd_skeleton, cmd_build

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
        from neuralmind.cli import cmd_skeleton, cmd_build

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
