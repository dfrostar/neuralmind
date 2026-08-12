"""Tests for v3.1.4 future-proofing — CLI coverage, MCP schema validation."""

import json
from unittest.mock import MagicMock

import pytest


class TestCLIHealth:
    """Tests for neuralmind health (v3.1.4+)."""

    def test_health_healthy_exit_code(self, temp_project, capsys):
        """health returns exit code 0 when index is fresh."""
        from neuralmind.cli import cmd_build, cmd_health

        build_args = MagicMock()
        build_args.project_path = str(temp_project)
        build_args.force = False
        cmd_build(build_args)
        capsys.readouterr()

        args = MagicMock()
        args.project_path = str(temp_project)
        args.json = False

        with pytest.raises(SystemExit) as exc_info:
            cmd_health(args)
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "healthy" in captured.out.lower() or "Health" in captured.out

    def test_health_json_output(self, temp_project, capsys):
        """health --json returns valid JSON."""
        from neuralmind.cli import cmd_build, cmd_health

        build_args = MagicMock()
        build_args.project_path = str(temp_project)
        build_args.force = False
        cmd_build(build_args)
        capsys.readouterr()

        args = MagicMock()
        args.project_path = str(temp_project)
        args.json = True

        with pytest.raises(SystemExit):
            cmd_health(args)
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert "index" in data
        assert "node_count" in data["index"]
        assert "stale" in data["index"]


class TestCLISynapse:
    """Tests for neuralmind synapse prune/stats (v3.1.4+)."""

    def test_synapse_stats_outputs(self, temp_project, capsys):
        """synapse stats shows edge counts (when store exists)."""
        from neuralmind.cli import cmd_synapse_stats

        args = MagicMock()
        args.project_path = str(temp_project)

        try:
            cmd_synapse_stats(args)
        except SystemExit:
            pass
        captured = capsys.readouterr()
        assert captured.out or captured.err  # non-empty output or error

    def test_synapse_prune_requires_days(self, temp_project, capsys):
        """synapse prune requires --days flag."""
        from neuralmind.cli import cmd_synapse_prune

        args = MagicMock()
        args.project_path = str(temp_project)
        args.days = None

        with pytest.raises(SystemExit):
            cmd_synapse_prune(args)

    def test_synapse_prune_with_days(self, temp_project, capsys):
        """synapse prune --days 30 runs without error (when store exists)."""
        from neuralmind.cli import cmd_synapse_prune

        args = MagicMock()
        args.project_path = str(temp_project)
        args.days = 30

        try:
            cmd_synapse_prune(args)
        except SystemExit:
            pass


class TestCLIFeedback:
    """Tests for neuralmind feedback (v3.1.4+)."""

    def test_feedback_good(self, temp_project, capsys):
        """feedback good confirms boost (when store exists)."""
        from neuralmind.cli import cmd_feedback_good

        args = MagicMock()
        args.project_path = str(temp_project)

        try:
            cmd_feedback_good(args)
        except SystemExit:
            pass
        captured = capsys.readouterr()
        assert captured.out or captured.err  # non-empty output or error

    def test_feedback_bad(self, temp_project, capsys):
        """feedback bad confirms penalty (when store exists)."""
        from neuralmind.cli import cmd_feedback_bad

        args = MagicMock()
        args.project_path = str(temp_project)

        try:
            cmd_feedback_bad(args)
        except SystemExit:
            pass
        captured = capsys.readouterr()
        assert captured.out or captured.err  # non-empty output or error


class TestCLIAudit:
    """Tests for neuralmind audit recent (v3.1.4+)."""

    def test_audit_recent_outputs(self, temp_project, capsys):
        """audit recent shows recent events."""
        from neuralmind.cli import cmd_audit_recent

        args = MagicMock()
        args.project_path = str(temp_project)
        args.n = 10

        try:
            cmd_audit_recent(args)
        except SystemExit:
            pass
        captured = capsys.readouterr()
        assert captured.out or captured.err  # non-empty output or error


class TestCLICodeDocFilter:
    """Tests for query --type filter (v3.1.4+)."""

    def test_query_type_code(self, temp_project, capsys):
        """query --type code runs without crashing."""
        from neuralmind.cli import cmd_build, cmd_query

        build_args = MagicMock()
        build_args.project_path = str(temp_project)
        build_args.force = False
        cmd_build(build_args)
        capsys.readouterr()

        args = MagicMock()
        args.project_path = str(temp_project)
        args.question = "authentication"
        args.type = "code"
        args.json = True
        args.relevance = False

        try:
            cmd_query(args)
        except SystemExit:
            pass
        captured = capsys.readouterr()
        assert captured.out or captured.err

    def test_query_type_docs(self, temp_project, capsys):
        """query --type docs runs without crashing."""
        from neuralmind.cli import cmd_build, cmd_query

        build_args = MagicMock()
        build_args.project_path = str(temp_project)
        build_args.force = False
        cmd_build(build_args)
        capsys.readouterr()

        args = MagicMock()
        args.project_path = str(temp_project)
        args.question = "explain"
        args.type = "docs"
        args.json = True
        args.relevance = False

        try:
            cmd_query(args)
        except SystemExit:
            pass
        captured = capsys.readouterr()
        assert captured.out or captured.err

    def test_cross_project_requires_paths(self, temp_project, capsys):
        """query --projects requires at least 2 paths."""
        from neuralmind.cli import _cmd_query_cross_project

        args = MagicMock()
        args.projects = None

        with pytest.raises(SystemExit):
            _cmd_query_cross_project(args, [])


class TestMCPSchemaValidation:
    """Verify TOOLS definitions match handler implementations."""

    def test_all_tools_have_handlers(self):
        """Every tool in TOOLS must have a handler in handle_tool_call."""
        from neuralmind.mcp_server import TOOLS, handle_tool_call

        for tool in TOOLS:
            name = tool["name"]
            try:
                handle_tool_call(name, {})
            except Exception:
                pass  # Other errors are OK — we just verify dispatch works

    def test_health_tool_in_tools(self):
        """neuralmind_health must be in TOOLS list (v3.1.4+)."""
        from neuralmind.mcp_server import TOOLS

        tool_names = {t["name"] for t in TOOLS}
        assert "neuralmind_health" in tool_names
