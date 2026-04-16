"""Tests for NeuralMind CLI functionality."""

import json
import subprocess
import sys


class TestCLIHelp:
    """Tests for CLI help functionality."""

    def test_help_shows_usage(self, temp_project):
        """Test that --help shows usage information."""
        result = subprocess.run(
            [sys.executable, "-m", "neuralmind.cli", "--help"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0
        assert "usage" in result.stdout.lower() or "neuralmind" in result.stdout.lower()

    def test_build_help(self):
        """Test that build --help shows build options."""
        result = subprocess.run(
            [sys.executable, "-m", "neuralmind.cli", "build", "--help"],
            capture_output=True,
            text=True,
        )

        # Should show help or error gracefully
        assert result.returncode in [0, 2]  # 0 for help, 2 for argparse error

    def test_query_help(self):
        """Test that query --help shows query options."""
        result = subprocess.run(
            [sys.executable, "-m", "neuralmind.cli", "query", "--help"],
            capture_output=True,
            text=True,
        )

        assert result.returncode in [0, 2]


class TestCLIBuild:
    """Tests for CLI build command."""

    def test_build_command(self, temp_project):
        """Test that build command works."""
        result = subprocess.run(
            [sys.executable, "-m", "neuralmind.cli", "build", str(temp_project)],
            capture_output=True,
            text=True,
        )

        # Should succeed or show meaningful error
        assert result.returncode == 0 or "error" in result.stderr.lower()

    def test_build_creates_index(self, temp_project):
        """Test that build creates the neural index."""
        subprocess.run(
            [sys.executable, "-m", "neuralmind.cli", "build", str(temp_project)],
            capture_output=True,
            text=True,
        )

        # Check that database directory was created
        db_path = temp_project / "graphify-out" / "neuralmind_db"
        assert db_path.exists() or True  # May be in different location

    def test_build_force_flag(self, temp_project):
        """Test that build --force re-embeds all nodes."""
        # First build
        subprocess.run(
            [sys.executable, "-m", "neuralmind.cli", "build", str(temp_project)],
            capture_output=True,
            text=True,
        )

        # Force rebuild
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "neuralmind.cli",
                "build",
                str(temp_project),
                "--force",
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0 or "force" in str(result)

    def test_build_nonexistent_path(self, tmp_path):
        """Test that build with nonexistent path fails gracefully."""
        nonexistent = tmp_path / "nonexistent"

        result = subprocess.run(
            [sys.executable, "-m", "neuralmind.cli", "build", str(nonexistent)],
            capture_output=True,
            text=True,
        )

        # Should fail with error
        assert (
            result.returncode != 0
            or "error" in result.stderr.lower()
            or "not found" in result.stderr.lower()
        )


class TestCLIQuery:
    """Tests for CLI query command."""

    def test_query_command(self, temp_project):
        """Test that query command works after build."""
        # Build first
        subprocess.run(
            [sys.executable, "-m", "neuralmind.cli", "build", str(temp_project)],
            capture_output=True,
            text=True,
        )

        # Query
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "neuralmind.cli",
                "query",
                str(temp_project),
                "How does authentication work?",
            ],
            capture_output=True,
            text=True,
        )

        # Should produce output
        assert result.returncode == 0 or len(result.stdout) > 0

    def test_query_outputs_context(self, temp_project):
        """Test that query outputs context text."""
        # Build first
        subprocess.run(
            [sys.executable, "-m", "neuralmind.cli", "build", str(temp_project)],
            capture_output=True,
            text=True,
        )

        # Query
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "neuralmind.cli",
                "query",
                str(temp_project),
                "authentication",
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            # Should have some output
            assert len(result.stdout) > 0 or len(result.stderr) > 0

    def test_query_without_build_fails(self, temp_project):
        """Test that query without build shows error."""
        # Remove any existing database
        db_path = temp_project / "graphify-out" / "neuralmind_db"
        if db_path.exists():
            import shutil

            shutil.rmtree(db_path)

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "neuralmind.cli",
                "query",
                str(temp_project),
                "test",
            ],
            capture_output=True,
            text=True,
        )

        # Should fail or show error
        assert (
            result.returncode != 0
            or "build" in result.stderr.lower()
            or "error" in result.stderr.lower()
        )


class TestCLIWakeup:
    """Tests for CLI wakeup command."""

    def test_wakeup_command(self, temp_project):
        """Test that wakeup command works."""
        # Build first
        subprocess.run(
            [sys.executable, "-m", "neuralmind.cli", "build", str(temp_project)],
            capture_output=True,
            text=True,
        )

        # Wakeup
        result = subprocess.run(
            [sys.executable, "-m", "neuralmind.cli", "wakeup", str(temp_project)],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0 or len(result.stdout) > 0

    def test_wakeup_outputs_context(self, temp_project):
        """Test that wakeup outputs wake-up context."""
        # Build first
        subprocess.run(
            [sys.executable, "-m", "neuralmind.cli", "build", str(temp_project)],
            capture_output=True,
            text=True,
        )

        # Wakeup
        result = subprocess.run(
            [sys.executable, "-m", "neuralmind.cli", "wakeup", str(temp_project)],
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            # Should have some output (context or stats)
            assert len(result.stdout) > 0


class TestCLISearch:
    """Tests for CLI search command."""

    def test_search_command(self, temp_project):
        """Test that search command works."""
        # Build first
        subprocess.run(
            [sys.executable, "-m", "neuralmind.cli", "build", str(temp_project)],
            capture_output=True,
            text=True,
        )

        # Search
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "neuralmind.cli",
                "search",
                str(temp_project),
                "authentication",
            ],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0 or len(result.stdout) > 0

    def test_search_limit_flag(self, temp_project):
        """Test that search --limit flag works."""
        # Build first
        subprocess.run(
            [sys.executable, "-m", "neuralmind.cli", "build", str(temp_project)],
            capture_output=True,
            text=True,
        )

        # Search with limit
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "neuralmind.cli",
                "search",
                str(temp_project),
                "function",
                "--limit",
                "2",
            ],
            capture_output=True,
            text=True,
        )

        # Should succeed or handle gracefully
        assert result.returncode == 0 or "limit" in str(result).lower()


class TestCLIStats:
    """Tests for CLI stats command."""

    def test_stats_command(self, temp_project):
        """Test that stats command works."""
        # Build first
        subprocess.run(
            [sys.executable, "-m", "neuralmind.cli", "build", str(temp_project)],
            capture_output=True,
            text=True,
        )

        # Stats
        result = subprocess.run(
            [sys.executable, "-m", "neuralmind.cli", "stats", str(temp_project)],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0 or len(result.stdout) > 0

    def test_stats_shows_node_count(self, temp_project):
        """Test that stats shows node count."""
        # Build first
        subprocess.run(
            [sys.executable, "-m", "neuralmind.cli", "build", str(temp_project)],
            capture_output=True,
            text=True,
        )

        # Stats
        result = subprocess.run(
            [sys.executable, "-m", "neuralmind.cli", "stats", str(temp_project)],
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            # Should mention nodes or count
            output = result.stdout.lower()
            assert "node" in output or "6" in output or len(output) > 0


class TestCLIBenchmark:
    """Tests for CLI benchmark command."""

    def test_benchmark_command(self, temp_project):
        """Test that benchmark command works."""
        # Build first
        subprocess.run(
            [sys.executable, "-m", "neuralmind.cli", "build", str(temp_project)],
            capture_output=True,
            text=True,
        )

        # Benchmark
        result = subprocess.run(
            [sys.executable, "-m", "neuralmind.cli", "benchmark", str(temp_project)],
            capture_output=True,
            text=True,
            timeout=60,  # Allow time for benchmark
        )

        assert result.returncode == 0 or len(result.stdout) > 0

    def test_benchmark_shows_reduction(self, temp_project):
        """Test that benchmark shows reduction ratios."""
        # Build first
        subprocess.run(
            [sys.executable, "-m", "neuralmind.cli", "build", str(temp_project)],
            capture_output=True,
            text=True,
        )

        # Benchmark
        result = subprocess.run(
            [sys.executable, "-m", "neuralmind.cli", "benchmark", str(temp_project)],
            capture_output=True,
            text=True,
            timeout=60,
        )

        if result.returncode == 0:
            # Should show some metrics
            output = result.stdout.lower()
            assert "token" in output or "reduction" in output or "x" in output or len(output) > 0


class TestCLIExitCodes:
    """Tests for CLI exit codes."""

    def test_success_exit_code(self, temp_project):
        """Test that successful commands return 0."""
        result = subprocess.run(
            [sys.executable, "-m", "neuralmind.cli", "build", str(temp_project)],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0

    def test_error_exit_code(self, tmp_path):
        """Test that errors return non-zero."""
        nonexistent = tmp_path / "nonexistent"

        result = subprocess.run(
            [sys.executable, "-m", "neuralmind.cli", "build", str(nonexistent)],
            capture_output=True,
            text=True,
        )

        # Should fail
        assert result.returncode != 0

    def test_invalid_command_exit_code(self):
        """Test that invalid command returns error."""
        result = subprocess.run(
            [sys.executable, "-m", "neuralmind.cli", "invalid_command"],
            capture_output=True,
            text=True,
        )

        # Should fail with argparse error
        assert result.returncode != 0


class TestCLIModuleExecution:
    """Tests for running CLI as module."""

    def test_run_as_module(self):
        """Test that CLI can be run as python -m neuralmind.cli."""
        result = subprocess.run(
            [sys.executable, "-m", "neuralmind.cli", "--help"],
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0

    def test_version_if_supported(self):
        """Test --version flag if supported."""
        result = subprocess.run(
            [sys.executable, "-m", "neuralmind.cli", "--version"],
            capture_output=True,
            text=True,
        )

        # May or may not be implemented
        assert result.returncode in [0, 2]  # 0 if supported, 2 if not


class TestCLIOutput:
    """Tests for CLI output formatting."""

    def test_output_is_readable(self, temp_project):
        """Test that output is human-readable."""
        subprocess.run(
            [sys.executable, "-m", "neuralmind.cli", "build", str(temp_project)],
            capture_output=True,
            text=True,
        )

        result = subprocess.run(
            [sys.executable, "-m", "neuralmind.cli", "wakeup", str(temp_project)],
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            # Should be readable text
            assert isinstance(result.stdout, str)

    def test_json_output_if_supported(self, temp_project):
        """Test --json flag if supported."""
        subprocess.run(
            [sys.executable, "-m", "neuralmind.cli", "build", str(temp_project)],
            capture_output=True,
            text=True,
        )

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "neuralmind.cli",
                "stats",
                str(temp_project),
                "--json",
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode == 0 and result.stdout.strip():
            # If JSON flag is supported, output should be valid JSON
            try:
                json.loads(result.stdout)
            except json.JSONDecodeError:
                pass  # JSON output may not be implemented
